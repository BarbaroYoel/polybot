"""`/conversations` endpoints (docs/api-contract.md §3 "Conversaciones y mensajes")."""

import json
from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import StreamingResponse

from app.api.v1.errors import describe_domain_error
from app.api.v1.query import parse_cursor
from app.api.v1.schemas import (
    ConversationCreate,
    ConversationDetailOut,
    ConversationOut,
    ConversationPage,
    ConversationUpdate,
    DrillAnswerOut,
    DrillAnswerRequest,
    MessageCreate,
    MessageFeedbackOut,
    MessageOut,
    MessagePage,
    blocks_out,
)
from app.application.blocks import BlockService
from app.application.conversations import ConversationService
from app.application.translation import TranslationService
from app.application.tutor import (
    TurnBlocksReady,
    TurnCompleted,
    TurnError,
    TurnFeedbackReady,
    TurnState,
    TurnToken,
    TutorService,
)
from app.core.dependencies import (
    get_block_service,
    get_conversation_service,
    get_translation_service,
    get_tutor_service,
)
from app.core.errors import error_body

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=ConversationPage, summary="History of one language")
async def list_conversations(
    language_id: str = Query(min_length=1, description="Language whose history is read"),
    limit: int = Query(default=20, ge=1, le=50),
    cursor: str | None = Query(default=None, description="Opaque cursor from a previous page"),
    service: ConversationService = Depends(get_conversation_service),
) -> ConversationPage:
    page = await service.list_conversations(
        language_id=language_id, limit=limit, after=parse_cursor(cursor)
    )
    return ConversationPage.from_page(page)


@router.post("", response_model=ConversationOut, status_code=201, summary="Create a conversation")
async def create_conversation(
    payload: ConversationCreate,
    service: ConversationService = Depends(get_conversation_service),
) -> ConversationOut:
    conversation = await service.create_conversation(
        language_id=payload.language_id, mode=payload.mode, title=payload.title
    )
    return ConversationOut.from_entity(conversation)


@router.get(
    "/{conversation_id}",
    response_model=ConversationDetailOut,
    summary="A conversation with its messages",
)
async def get_conversation(
    conversation_id: str,
    language_id: str | None = Query(
        default=None, description="Reject the conversation when it belongs to another language"
    ),
    messages_limit: int = Query(default=50, ge=1, le=50),
    messages_cursor: str | None = Query(default=None),
    service: ConversationService = Depends(get_conversation_service),
) -> ConversationDetailOut:
    conversation, messages, feedback = await service.get_conversation_detail(
        conversation_id,
        language_id=language_id,
        messages_limit=messages_limit,
        messages_after=parse_cursor(messages_cursor),
    )
    return ConversationDetailOut(
        **ConversationOut.from_entity(conversation).model_dump(),
        messages=MessagePage.from_page(messages, feedback=feedback),
    )


@router.patch("/{conversation_id}", response_model=ConversationOut, summary="Rename a conversation")
async def rename_conversation(
    conversation_id: str,
    payload: ConversationUpdate,
    service: ConversationService = Depends(get_conversation_service),
) -> ConversationOut:
    return ConversationOut.from_entity(
        await service.rename_conversation(conversation_id, payload.title)
    )


@router.delete("/{conversation_id}", status_code=204, summary="Delete a conversation")
async def delete_conversation(
    conversation_id: str,
    service: ConversationService = Depends(get_conversation_service),
) -> None:
    await service.delete_conversation(conversation_id)


@router.post(
    "/{conversation_id}/messages",
    response_model=MessageOut,
    status_code=201,
    summary="Send a user message (F3)",
)
async def send_message(
    conversation_id: str,
    payload: MessageCreate,
    idempotency_key: Annotated[
        str | None,
        Header(
            alias="Idempotency-Key",
            max_length=120,
            description="Retrying with the same key resolves to the same turn",
        ),
    ] = None,
    service: ConversationService = Depends(get_conversation_service),
) -> MessageOut:
    message = await service.send_message(
        conversation_id, content=payload.content, idempotency_key=idempotency_key
    )
    return MessageOut.from_entity(message)


@router.post(
    "/{conversation_id}/messages/{message_id}/translation",
    response_model=MessageOut,
    summary="Translate and store one message (ADR-014)",
    responses={404: {"description": "`conversation_not_found` or `message_not_found`"}},
)
async def translate_message(
    conversation_id: str,
    message_id: str,
    service: TranslationService = Depends(get_translation_service),
) -> MessageOut:
    """Translate the whole message and keep it: a second call reuses the stored translation."""
    result = await service.translate_message(conversation_id=conversation_id, message_id=message_id)
    return MessageOut.from_entity(result.message, result.feedback)


@router.post(
    "/{conversation_id}/messages/{message_id}/blocks/{block_id}/answers",
    response_model=DrillAnswerOut,
    summary="Answer one drill of a turn (ADR-020)",
    responses={
        400: {"description": "`block_not_answerable` when the block is not a drill"},
        404: {"description": "`conversation_not_found`, `message_not_found` or `block_not_found`"},
    },
)
async def answer_block(
    conversation_id: str,
    message_id: str,
    block_id: str,
    payload: DrillAnswerRequest,
    service: BlockService = Depends(get_block_service),
) -> DrillAnswerOut:
    """Grade the answer deterministically; nothing is stored, so a second attempt grades again."""
    result = await service.answer(
        conversation_id=conversation_id,
        message_id=message_id,
        block_id=block_id,
        answer=payload.answer,
    )
    return DrillAnswerOut.from_entity(result)


@router.get(
    "/{conversation_id}/stream",
    summary="Stream the tutor turn over SSE (F3)",
    responses={
        200: {"content": {"text/event-stream": {}}},
        400: {"description": "The message is not a user message (`invalid_turn_message`)"},
        404: {"description": "`conversation_not_found` or `message_not_found`"},
    },
)
async def stream_turn(
    conversation_id: str,
    request: Request,
    message_id: str = Query(min_length=1, description="The user message that starts the turn"),
    service: TutorService = Depends(get_tutor_service),
) -> StreamingResponse:
    """Open a turn and stream it: `token`*, then `message_end`, or `error` (S5, S6)."""
    # Validation runs before the response starts, so its failures still use the JSON envelope.
    state = await service.begin_turn(conversation_id, message_id)
    return StreamingResponse(
        _turn_events(service, state, getattr(request.state, "request_id", "")),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _turn_events(
    service: TutorService, state: TurnState, request_id: str
) -> AsyncIterator[str]:
    async for event in service.stream_turn(state):
        if isinstance(event, TurnToken):
            yield _sse("token", {"message_id": event.message_id, "delta": event.delta})
        elif isinstance(event, TurnCompleted):
            yield _sse("message_end", MessageOut.from_entity(event.message).model_dump(mode="json"))
        elif isinstance(event, TurnError):
            _, code, message = describe_domain_error(event.error)
            yield _sse("error", error_body(code, message, request_id=request_id))
        elif isinstance(event, TurnBlocksReady):
            # Before the feedback events: the blocks belong to the tutor message that just ended.
            yield _sse(
                "blocks",
                {
                    "message_id": event.message_id,
                    "items": [item.model_dump(mode="json") for item in blocks_out(event.blocks)],
                },
            )
        elif isinstance(event, TurnFeedbackReady):
            # After `message_end`, and only now: the rows are committed before these leave (S7).
            for chunk in _feedback_events(event):
                yield chunk


def _feedback_events(event: TurnFeedbackReady) -> list[str]:
    """`correction` and then `vocabulary`, with the id of the user message that opened the turn."""
    feedback = MessageFeedbackOut.from_turn_feedback(event.feedback)
    events: list[str] = []
    if feedback.corrections:
        events.append(
            _sse(
                "correction",
                {
                    "message_id": event.message_id,
                    "items": [item.model_dump(mode="json") for item in feedback.corrections],
                },
            )
        )
    if feedback.vocabulary:
        events.append(
            _sse(
                "vocabulary",
                {
                    "message_id": event.message_id,
                    "items": [item.model_dump(mode="json") for item in feedback.vocabulary],
                },
            )
        )
    return events


def _sse(name: str, payload: dict[str, Any]) -> str:
    """One contract event: `event: <name>\ndata: <json>` closed by a blank line."""
    return f"event: {name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
