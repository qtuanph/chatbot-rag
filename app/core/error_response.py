"""Utilities to build a consistent API error response envelope."""

from __future__ import annotations

from http import HTTPStatus
from typing import Any

from fastapi import Request


def default_error_code(status_code: int) -> str:
    """Map HTTP status code to a stable machine-readable error code."""
    if status_code == 400:
        return "bad_request"
    if status_code == 401:
        return "unauthorized"
    if status_code == 403:
        return "forbidden"
    if status_code == 404:
        return "not_found"
    if status_code == 409:
        return "conflict"
    if status_code == 413:
        return "payload_too_large"
    if status_code == 422:
        return "validation_error"
    if status_code == 429:
        return "too_many_requests"
    if status_code == 500:
        return "internal_server_error"
    if status_code == 503:
        return "service_unavailable"

    try:
        return HTTPStatus(status_code).name.lower()
    except ValueError:
        return "http_error"


def build_error_response(
    request: Request,
    status_code: int,
    message: str,
    *,
    code: str | None = None,
    details: Any | None = None,
) -> dict[str, Any]:
    """Return a consistent error payload while preserving legacy detail field."""
    if not message or not message.strip():
        message = f"HTTP {status_code}"

    payload: dict[str, Any] = {
        "error": {
            "code": code or default_error_code(status_code),
            "message": message,
            "status": status_code,
            "path": request.url.path,
        },
        "detail": message,
    }

    if details is not None:
        payload["error"]["details"] = details

    return payload
