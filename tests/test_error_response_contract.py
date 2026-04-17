from starlette.requests import Request

from app.core.error_response import build_error_response, default_error_code


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
