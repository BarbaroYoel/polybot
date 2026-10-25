"""`/translate`: the stateless translation of a selected fragment (S4, ADR-014).

The message translation lives under `/conversations/{id}/messages/{id}/translation`, because it
stores a row that belongs to that conversation.
"""

from fastapi import APIRouter, Depends

from app.api.v1.schemas import TranslateOut, TranslateRequest
from app.application.translation import TranslationService
from app.core.dependencies import get_translation_service

router = APIRouter(tags=["translation"])


@router.post("/translate", response_model=TranslateOut, summary="Translate a text")
async def translate(
    payload: TranslateRequest,
    service: TranslationService = Depends(get_translation_service),
) -> TranslateOut:
    result = await service.translate_text(
        text=payload.text, source=payload.source, target=payload.target
    )
    return TranslateOut(translation=result.text, detected_source=result.detected_source)
