from __future__ import annotations

import asyncio

from fastapi import HTTPException, Request
from fastapi.testclient import TestClient

from app.api import middleware as api_middleware
from app.core.error_response import build_error_response, default_error_code
from app.main import app
from app.services.auth import throttle as throttle_module


def _make_request(path: str = "/api/v1/test") -> Request:
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("utf-8"),
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
        "root_path": "",
    }
    return Request(scope)


def _ensure_test_routes() -> None:
    routes = {route.path for route in app.routes}

    if "/__test/http-error" not in routes:
        @app.get("/__test/http-error")
        def raise_http_error() -> None:
            raise HTTPException(status_code=418, detail="teapot")

    if "/__test/unhandled-error" not in routes:
        @app.get("/__test/unhandled-error")
        def raise_unhandled_error() -> None:
            raise ValueError("boom")

    if "/__test/validation" not in routes:
        @app.get("/__test/validation")
        def validation_route(value: int) -> dict[str, int]:
            return {"value": value}


def test_default_error_code_known_mappings() -> None:
    assert default_error_code(400) == "bad_request"
    assert default_error_code(422) == "validation_error"
    assert default_error_code(503) == "service_unavailable"


def test_default_error_code_fallback_for_unknown_status() -> None:
    assert default_error_code(418) == "im_a_teapot"
    assert default_error_code(999) == "http_error"


def test_build_error_response_uses_unified_envelope_and_detail() -> None:
    request = _make_request("/api/v1/chat")

    payload = build_error_response(
        request,
        400,
        "Query cannot be empty",
        details=[{"loc": ["body", "query"], "msg": "required"}],
    )

    assert payload["detail"] == "Query cannot be empty"
    assert payload["error"]["code"] == "bad_request"
    assert payload["error"]["message"] == "Query cannot be empty"
    assert payload["error"]["status"] == 400
    assert payload["error"]["path"] == "/api/v1/chat"
    assert "details" in payload["error"]


def test_build_error_response_falls_back_on_blank_message() -> None:
    request = _make_request("/api/v1/documents")

    payload = build_error_response(request, 500, "   ")

    assert payload["detail"] == "HTTP 500"
    assert payload["error"]["message"] == "HTTP 500"
    assert payload["error"]["code"] == "internal_server_error"


def test_fastapi_http_exception_handler_returns_unified_envelope() -> None:
    _ensure_test_routes()

    with TestClient(app) as client:
        response = client.get("/__test/http-error")

    assert response.status_code == 418
    body = response.json()
    assert body["detail"] == "teapot"
    assert body["error"]["code"] == "im_a_teapot"
    assert body["error"]["message"] == "teapot"
    assert body["error"]["status"] == 418
    assert body["error"]["path"] == "/__test/http-error"


def test_fastapi_validation_and_unhandled_exception_handlers_return_unified_envelope() -> None:
    _ensure_test_routes()

    with TestClient(app, raise_server_exceptions=False) as client:
        validation_response = client.get("/__test/validation")
        unhandled_response = client.get("/__test/unhandled-error")

    validation_body = validation_response.json()
    assert validation_response.status_code == 422
    assert validation_body["detail"] == "Validation error"
    assert validation_body["error"]["code"] == "validation_error"
    assert validation_body["error"]["status"] == 422
    assert validation_body["error"]["path"] == "/__test/validation"
    assert "details" in validation_body["error"]

    unhandled_body = unhandled_response.json()
    assert unhandled_response.status_code == 500
    assert unhandled_body["detail"] == "Internal server error"
    assert unhandled_body["error"]["code"] == "internal_server_error"
    assert unhandled_body["error"]["status"] == 500
    assert unhandled_body["error"]["path"] == "/__test/unhandled-error"


def test_rate_limit_middleware_returns_unified_envelope_without_redis_dependency() -> None:
    class FakeThrottle:
        def allow(self, key: str, limit: int, window_seconds: int) -> bool:
            return False

    original_throttle = throttle_module.RequestThrottle
    throttle_module.RequestThrottle = lambda: FakeThrottle()  # type: ignore[assignment]
    try:
        middleware = api_middleware.RateLimitMiddleware(app=lambda scope, receive, send: None)
        request = _make_request("/api/v1/health")

        async def call_next(_request: Request):
            raise AssertionError("call_next should not be reached when rate-limited")

        response = asyncio.run(middleware.dispatch(request, call_next))
        body = response.body.decode("utf-8")
    finally:
        throttle_module.RequestThrottle = original_throttle

    assert response.status_code == 429
    assert '"detail":"Rate limit exceeded. Please try again later."' in body
    assert '"error":' in body
    assert '"code":"too_many_requests"' in body