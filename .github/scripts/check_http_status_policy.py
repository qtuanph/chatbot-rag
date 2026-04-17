#!/usr/bin/env python3
"""Enforce HTTPException status and API error helper policy.

Policy:
- Use FastAPI status constants for HTTPException status_code.
- Do not use raw numeric literals (e.g., status_code=400).
- In API layer (`app/api/routes/*`, `app/api/deps.py`), raise route-level HTTP errors via
    `app.core.http_errors` helpers instead of constructing HTTPException directly.
"""

from __future__ import annotations

import ast
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
APP_DIR = ROOT / "app"

ALLOWED_HTTP_ERROR_HELPERS = {
    "bad_request",
    "unauthorized",
    "forbidden",
    "not_found",
    "conflict",
    "payload_too_large",
    "too_many_requests",
    "internal_server_error",
    "service_unavailable",
}


def is_httpexception_call(call: ast.Call) -> bool:
    func = call.func
    if isinstance(func, ast.Name):
        return func.id == "HTTPException"
    if isinstance(func, ast.Attribute):
        return func.attr == "HTTPException"
    return False


def is_valid_status_expression(expr: ast.AST) -> bool:
    # valid: status.HTTP_XXX
    if isinstance(expr, ast.Attribute) and isinstance(expr.value, ast.Name):
        return expr.value.id == "status" and expr.attr.startswith("HTTP_")

    return False


def check_file(path: Path) -> list[str]:
    errors: list[str] = []
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        errors.append(f"{path}: syntax error: {exc}")
        return errors

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not is_httpexception_call(node):
            continue

        status_kw = next((kw for kw in node.keywords if kw.arg == "status_code"), None)
        if status_kw is None:
            errors.append(
                f"{path}:{node.lineno}: HTTPException missing status_code keyword"
            )
            continue

        if isinstance(status_kw.value, ast.Constant) and isinstance(status_kw.value.value, int):
            errors.append(
                f"{path}:{node.lineno}: raw numeric status_code is forbidden; use status.HTTP_*"
            )
            continue

        if not is_valid_status_expression(status_kw.value):
            errors.append(
                f"{path}:{node.lineno}: unsupported status_code expression; use status.HTTP_*"
            )

    return errors


def is_api_layer_file(path: Path) -> bool:
    rel = path.relative_to(APP_DIR).as_posix()
    return rel.startswith("api/routes/") or rel == "api/deps.py"


def _is_http_error_helper_call(call: ast.Call) -> bool:
    func = call.func
    return (
        isinstance(func, ast.Attribute)
        and isinstance(func.value, ast.Name)
        and func.value.id == "http_errors"
    )


def check_api_layer_helper_policy(path: Path) -> list[str]:
    errors: list[str] = []
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        errors.append(f"{path}: syntax error: {exc}")
        return errors

    for node in ast.walk(tree):
        if not isinstance(node, ast.Raise) or node.exc is None:
            continue

        if isinstance(node.exc, ast.Call) and is_httpexception_call(node.exc):
            errors.append(
                f"{path}:{node.lineno}: direct raise HTTPException is forbidden in API layer; "
                "use http_errors.* helper"
            )
            continue

        if not isinstance(node.exc, ast.Call) or not _is_http_error_helper_call(node.exc):
            continue

        helper_name = node.exc.func.attr if isinstance(node.exc.func, ast.Attribute) else ""
        if helper_name not in ALLOWED_HTTP_ERROR_HELPERS:
            errors.append(
                f"{path}:{node.lineno}: unknown http_errors helper '{helper_name}'"
            )

    return errors


def main() -> int:
    py_files = sorted(APP_DIR.rglob("*.py"))
    all_errors: list[str] = []

    for file_path in py_files:
        all_errors.extend(check_file(file_path))
        if is_api_layer_file(file_path):
            all_errors.extend(check_api_layer_helper_policy(file_path))

    if all_errors:
        print("HTTP status policy violations found:\n")
        for err in all_errors:
            print(f"- {err}")
        return 1

    print("HTTP status policy check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
