"""`/conversations` endpoints (docs/api-contract.md §3 "Conversaciones y mensajes")."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query

from app.api.v1.query import parse_cursor
from app.api.v1.schemas import (
    ConversationCreate,
    ConversationDetailOut,
    ConversationOut,
    ConversationPage,
    ConversationUpdate,
    MessageCreate,
    MessageOut,
    MessagePage,
)
from app.application.conversations import ConversationService
from app.core.dependencies import get_conversation_service

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
    conversation, messages = await service.get_conversation_detail(
        conversation_id,
        language_id=language_id,
        messages_limit=messages_limit,
        messages_after=parse_cursor(messages_cursor),
    )
    return ConversationDetailOut(
        **ConversationOut.from_entity(conversation).model_dump(),
        messages=MessagePage.from_page(messages),
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
