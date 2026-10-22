"""Every error leaves in the contract envelope (docs/api-contract.md §1 and §4, S4)."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import create_app

ENVELOPE_KEYS = {"code", "message", "details", "request_id"}


def _error(response) -> dict:
    body = response.json()
    assert set(body) == {"error"}, body
    error = body["error"]
    assert ENVELOPE_KEYS <= set(error), error
    return error


def test_unknown_route_returns_the_error_envelope(client: TestClient) -> None:
    response = client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")
    error = _error(response)
    assert error["code"] == "not_found"
    assert error["message"]


def test_method_not_allowed_returns_the_error_envelope(client: TestClient) -> None:
    response = client.put("/api/v1/health")

    assert response.status_code == 405
    assert _error(response)["code"] == "method_not_allowed"


def test_validation_error_returns_the_error_envelope() -> None:
    app = create_app()

    @app.get("/api/v1/echo")
    def echo(value: int) -> dict[str, int]:
        return {"value": value}

    response = TestClient(app).get("/api/v1/echo?value=not-a-number")

    assert response.status_code == 422
    error = _error(response)
    assert error["code"] == "validation_error"
    assert error["details"]["fields"], "the envelope must say which field failed"


def test_unhandled_exception_returns_a_generic_envelope_without_leaking_details() -> None:
    app: FastAPI = create_app()

    @app.get("/api/v1/boom")
    def boom() -> None:
        raise RuntimeError("secret provider token")

    response = TestClient(app, raise_server_exceptions=False).get("/api/v1/boom")

    assert response.status_code == 500
    error = _error(response)
    assert error["code"] == "internal_error"
    assert "secret provider token" not in response.text
    assert "Traceback" not in response.text


def test_error_body_request_id_matches_the_response_header(client: TestClient) -> None:
    response = client.get("/api/v1/does-not-exist")

    assert _error(response)["request_id"] == response.headers["x-request-id"]
