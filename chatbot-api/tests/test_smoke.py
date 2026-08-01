"""Smoke test suite for chatbot-api backend."""

from fastapi.testclient import TestClient
from app.main import app


def test_health_check_endpoint() -> None:
    """Verify that /v1/health endpoint returns status 200."""
    client = TestClient(app)
    response = client.get("/v1/health")
    assert response.status_code in (200, 202)
