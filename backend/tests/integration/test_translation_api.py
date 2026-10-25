"""Translation of a message and of a fragment (S1-S5, ADR-014).

The provider is the `FakeLlm` double (`tests/fakes/llm.py`): the tests assert what it was asked to
translate, so the direction of each call is checked instead of trusted.
"""

from app.adapters.db.seed import (
    CONVERSATION_EN_ROUTINE,
    CONVERSATION_FR_CAFE,
    LANGUAGE_INGLES,
)
from app.domain.errors import LlmTimeout, LlmUnavailable
from app.ports.llm import TranslationRequest
from tests.fakes.llm import FakeLlm

# French café conversation: a tutor message with no stored translation and one that the seed
# already translated.
FRENCH_TUTOR_MESSAGE = "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c03"
FRENCH_SEEDED_TRANSLATION = "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c04"
SEEDED_SPANISH = "¡Buenos días! ¿Qué le gustaría tomar?"

UNKNOWN_ID = "00000000-0000-4000-8000-000000000000"


def translate_message_url(conversation_id: str, message_id: str) -> str:
    return f"/api/v1/conversations/{conversation_id}/messages/{message_id}/translation"


def test_translate_returns_the_translation_and_the_source_used(
    api_client, fake_llm: FakeLlm
) -> None:
    response = api_client.post(
        "/api/v1/translate",
        json={"text": "Comment ça va ?", "source": "fr", "target": "es"},
    )

    assert response.status_code == 200
    assert response.json() == {"translation": "¿Cómo estás?", "detected_source": "fr"}
    assert fake_llm.translations == [
        TranslationRequest(text="Comment ça va ?", target_language="es", source_language="fr")
    ]


def test_translate_without_source_asks_the_provider_to_detect_it(
    api_client, fake_llm: FakeLlm
) -> None:
    response = api_client.post(
        "/api/v1/translate", json={"text": "Comment ça va ?", "target": "es"}
    )

    assert response.status_code == 200
    # The server does not invent a code it did not detect itself: none is echoed.
    assert response.json()["detected_source"] is None
    assert fake_llm.translations[0].source_language is None


def test_an_empty_text_is_a_validation_error(api_client, fake_llm: FakeLlm) -> None:
    response = api_client.post("/api/v1/translate", json={"text": "   ", "target": "es"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert fake_llm.translations == []


def test_a_provider_failure_is_an_error_envelope(api_client, fake_llm: FakeLlm) -> None:
    fake_llm.translation_failure = LlmUnavailable("provider down")

    response = api_client.post(
        "/api/v1/translate", json={"text": "Comment ça va ?", "target": "es"}
    )

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "llm_unavailable"


def test_a_provider_timeout_is_a_gateway_timeout(api_client, fake_llm: FakeLlm) -> None:
    fake_llm.translation_failure = LlmTimeout("provider slow")

    response = api_client.post(
        "/api/v1/translate", json={"text": "Comment ça va ?", "target": "es"}
    )

    assert response.status_code == 504
    assert response.json()["error"]["code"] == "llm_timeout"


def test_a_message_translation_is_stored_and_survives_a_reload(
    api_client, fake_llm: FakeLlm
) -> None:
    response = api_client.post(translate_message_url(CONVERSATION_FR_CAFE, FRENCH_TUTOR_MESSAGE))

    assert response.status_code == 200
    assert response.json()["translation"] == "¿Cómo estás?"

    detail = api_client.get(f"/api/v1/conversations/{CONVERSATION_FR_CAFE}")
    stored = {item["id"]: item for item in detail.json()["messages"]["items"]}
    assert stored[FRENCH_TUTOR_MESSAGE]["translation"] == "¿Cómo estás?"


def test_a_stored_translation_is_not_asked_twice(api_client, fake_llm: FakeLlm) -> None:
    response = api_client.post(
        translate_message_url(CONVERSATION_FR_CAFE, FRENCH_SEEDED_TRANSLATION)
    )

    assert response.status_code == 200
    assert response.json()["translation"] == SEEDED_SPANISH
    assert fake_llm.translations == []


def test_the_direction_comes_from_the_conversation_language(api_client, fake_llm: FakeLlm) -> None:
    # The seed leaves English active: a French conversation must still translate fr → es.
    assert api_client.get("/api/v1/languages").json()[0]["id"] == LANGUAGE_INGLES

    api_client.post(translate_message_url(CONVERSATION_FR_CAFE, FRENCH_TUTOR_MESSAGE))

    request = fake_llm.translations[0]
    assert request.source_language == "fr"
    assert request.target_language == "es"


def test_a_message_of_another_conversation_is_not_found(api_client, fake_llm: FakeLlm) -> None:
    response = api_client.post(translate_message_url(CONVERSATION_EN_ROUTINE, FRENCH_TUTOR_MESSAGE))

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "message_not_found"
    assert fake_llm.translations == []


def test_an_unknown_conversation_is_not_found(api_client, fake_llm: FakeLlm) -> None:
    response = api_client.post(translate_message_url(UNKNOWN_ID, FRENCH_TUTOR_MESSAGE))

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "conversation_not_found"
    assert fake_llm.translations == []
