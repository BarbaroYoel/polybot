"""Shared fixtures for the integration tests (API surface over httpx/TestClient)."""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client() -> TestClient:
    """A client over a freshly built app, without a database and without a .env file."""
    return TestClient(create_app())
