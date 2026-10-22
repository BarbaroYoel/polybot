"""Contract rules for the liveness endpoint.

docs/api-contract.md §3 "Sistema"; odd/tasks/f2-backend-skeleton.md S3.
"""

from fastapi.testclient import TestClient

from app.main import create_app


def test_health_reports_ok_and_version(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"status", "version"}
    assert body["status"] == "ok"
    assert isinstance(body["version"], str) and body["version"]


def test_health_sets_the_request_id_header(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.headers["x-request-id"]


def test_health_does_not_need_the_database(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:////nonexistent/polybot.db")

    response = TestClient(create_app()).get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
