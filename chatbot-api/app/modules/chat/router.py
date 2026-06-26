"""Stateless internal chat API endpoints."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.modules.auth.deps import get_auth_context
from app.modules.auth.context import AuthContext
from app.modules.chat.deps import get_feedback_service
from app.core.deps import get_rate_limiter
from app.core import http_errors
from app.core.config import settings
from app.modules.inference.router import get_public_inference_service
from app.modules.inference.service import PublicInferenceService
from app.modules.chat.schemas import ChatFeedbackRequest, ChatFeedbackResponse
from app.modules.chat.services import FeedbackService
from app.utils.rate_limiter import RateLimiter

router = APIRouter(tags=["chat"])
logger = logging.getLogger(__name__)


def _resolve_tenant_id(auth: AuthContext, request_tenant_id: str | None) -> str:
    tenant_id = auth.tenant_id or request_tenant_id
    if not tenant_id:
        raise http_errors.bad_request("tenant_id is required for platform admin chat testing")
    return tenant_id


async def _sse_stream(
    *,
    tenant_id: str,
    user_id: str | None,
    messages: list[dict[str, str]],
    thinking_mode: bool,
    service: PublicInferenceService,
):
    try:
        if thinking_mode:
            yield f"data: {json.dumps({'chunk': '', 'thinking': True, 'done': False})}\n\n"

        citations: list[dict] = []
        usage: dict = {}
        model_name = ""

        async for sse_chunk in service.stream_complete(
            tenant_id=tenant_id,
            user_id=user_id,
            messages=messages,
        ):
            if sse_chunk.strip() == "data: [DONE]":
                break
            if not sse_chunk.startswith("data: "):
                continue
            try:
                payload = json.loads(sse_chunk[len("data: ") :])
            except json.JSONDecodeError:
                continue

            model_name = payload.get("model") or model_name
            choices = payload.get("choices") or [{}]
            choice = choices[0] if choices else {}
            delta = (choice.get("delta") or {}).get("content") or ""
            if delta:
                yield f"data: {json.dumps({'chunk': delta, 'done': False})}\n\n"

            if choice.get("finish_reason") == "stop":
                citations = payload.get("citations") or []
                usage = payload.get("usage") or {}

        if thinking_mode:
            yield f"data: {json.dumps({'chunk': '', 'thinking': False, 'done': False})}\n\n"

        yield f"data: {json.dumps({
            'chunk': '',
            'done': True,
            'citations': citations,
            'stats': usage | {'model': model_name},
        })}\n\n"
    except Exception as exc:
        logger.error("SSE stream error: %s", exc, exc_info=True)
        yield f"data: {json.dumps({'error': str(exc), 'done': True})}\n\n"


@router.post("/chat/stream")
async def chat_stream_sse(
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
    service: PublicInferenceService = Depends(get_public_inference_service),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
):
    """Stateless SSE endpoint for internal chat testing."""
    body = await request.json()
    query = str(body.get("query", "")).strip()
    thinking_mode = bool(body.get("thinking_mode", False))
    request_tenant_id = body.get("tenant_id")
    messages = body.get("messages") or []

    if not messages:
        if not query:
            raise http_errors.bad_request("Query cannot be empty")
        messages = [{"role": "user", "content": query}]

    tenant_id = _resolve_tenant_id(auth, request_tenant_id)

    throttle_scope = tenant_id if auth.role == "platform_admin" else auth.user_id
    if not await rate_limiter.is_allowed(
        f"chat:{throttle_scope}", limit=settings.effective_rate_limit(30), window_ms=60000
    ):
        raise http_errors.too_many_requests("Too many chat requests. Please wait.")

    return StreamingResponse(
        _sse_stream(
            tenant_id=tenant_id,
            user_id=auth.user_id,
            messages=messages,
            thinking_mode=thinking_mode,
            service=service,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/chat/feedback", response_model=ChatFeedbackResponse)
async def submit_chat_feedback(
    payload: ChatFeedbackRequest,
    auth: AuthContext = Depends(get_auth_context),
    feedback_service: FeedbackService = Depends(get_feedback_service),
) -> ChatFeedbackResponse:
    tenant_id = _resolve_tenant_id(auth, payload.tenant_id)
    result = await feedback_service.submit_feedback(
        tenant_id=tenant_id,
        user_id=auth.user_id,
        feedback_type=payload.feedback_type,
        query_text=payload.query_text,
        assistant_answer=payload.assistant_answer,
        citations=[citation.model_dump() for citation in payload.citations],
        metadata=payload.metadata,
    )
    return ChatFeedbackResponse(
        id=result["id"],
        tenant_id=result["tenant_id"],
        user_id=result["user_id"],
        feedback_type=result["feedback_type"],
        created_at=result["created_at"],
    )
