"""Chat API — streaming chat endpoint."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.deps import AuthContext, get_auth_context, get_chat_service
from app.core.config import settings
from app.core import http_errors
from app.schemas.chat import ChatRequest, MessageFeedbackRequest, MessageFeedbackResponse
from app.services.chat.chat_service import ChatService
from app.utils.rate_limiter import RateLimiter

router = APIRouter(tags=["chat"])
rate_limiter = RateLimiter()
logger = logging.getLogger(__name__)


@router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    auth: AuthContext = Depends(get_auth_context),
    service: ChatService = Depends(get_chat_service),
):
    """Streaming chat endpoint — SSE format."""
    if not await rate_limiter.is_allowed(auth.user_id, limit=settings.effective_rate_limit(30), window_ms=60000):
        raise http_errors.too_many_requests("Too many chat requests. Please wait a moment before trying again.")

    try:
        prep = await service.prepare_chat(
            user_id=auth.user_id,
            query=request.query,
            session_id=request.session_id,
        )
    except ValueError as e:
        raise http_errors.bad_request(str(e)) from None
    except Exception as e:
        logger.error("Error preparing chat context: %s", e, exc_info=True)
        raise http_errors.internal_server_error("Failed to prepare chat context. Please try again.") from None

    return StreamingResponse(
        service.stream_chat_events(user_id=auth.user_id, query=request.query, prepared_chat=prep),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.post("/chat/sessions")
async def create_chat_session(
    auth: AuthContext = Depends(get_auth_context), service: ChatService = Depends(get_chat_service)
) -> dict:
    return await service.create_session(user_id=auth.user_id)


@router.get("/chat/sessions")
async def get_chat_sessions(
    auth: AuthContext = Depends(get_auth_context), service: ChatService = Depends(get_chat_service)
) -> list[dict]:
    return await service.list_sessions(auth.user_id)


@router.get("/chat/messages")
async def get_chat_messages(
    session_id: str,
    limit: int = 20,
    offset: int = 0,
    auth: AuthContext = Depends(get_auth_context),
    service: ChatService = Depends(get_chat_service),
) -> dict:
    try:
        return await service.list_messages(session_id=session_id, user_id=auth.user_id, limit=limit, offset=offset)
    except ValueError as e:
        msg = str(e)
        if "not found" in msg:
            raise http_errors.not_found(msg) from None
        if "not belong" in msg:
            raise http_errors.forbidden(msg) from None
        raise http_errors.bad_request(msg) from None


@router.post("/chat/messages/{message_id}/feedback")
async def set_message_feedback(
    message_id: str,
    request: MessageFeedbackRequest,
    auth: AuthContext = Depends(get_auth_context),
    service: ChatService = Depends(get_chat_service),
) -> MessageFeedbackResponse:
    """Record user feedback (Like/Dislike) for a specific assistant message."""
    try:
        updated = await service.set_message_feedback(
            message_id=message_id, user_id=auth.user_id, feedback=request.feedback
        )
        return MessageFeedbackResponse(message_id=message_id, feedback=updated["feedback"])
    except ValueError as e:
        raise http_errors.not_found(str(e)) from None
    except Exception as e:
        logger.error("Error recording message feedback: %s", e, exc_info=True)
        raise http_errors.internal_server_error("Failed to record feedback") from None
