"""Chat API endpoints."""

from __future__ import annotations

import json
import logging
import time

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.api.deps import AuthContext, get_auth_context, get_chat_service
from app.core import http_errors
from app.modules.chat.schemas import MessageFeedbackRequest, MessageFeedbackResponse
from app.modules.chat.services import ChatService

router = APIRouter(tags=["chat"])
logger = logging.getLogger(__name__)


async def _sse_stream(auth: AuthContext, query: str, session_id: str | None, thinking_mode: bool, service: ChatService):
    """SSE generator that yields chat stream events."""
    start_time = time.monotonic()
    try:
        # Yield thinking status only when thinking_mode is enabled
        if thinking_mode:
            yield f"data: {json.dumps({'chunk': '', 'thinking': True, 'done': False})}\n\n"

        prep = await service.prepare_chat(user_id=auth.user_id, query=query, session_id=session_id)

        # Signal retrieval complete, starting AI generation (only if thinking was shown)
        if thinking_mode:
            yield f"data: {json.dumps({'chunk': '', 'thinking': False, 'done': False})}\n\n"

        async for chunk in service.stream_chat_events(
            user_id=auth.user_id, query=query, prepared_chat=prep, thinking_mode=thinking_mode, start_time=start_time
        ):
            if isinstance(chunk, str):
                yield chunk
            elif isinstance(chunk, dict):
                yield f"data: {json.dumps(chunk)}\n\n"
    except Exception as e:
        logger.error("SSE stream error: %s", e, exc_info=True)
        error_data = json.dumps({"error": str(e), "done": True})
        yield f"data: {error_data}\n\n"


@router.post("/chat/stream")
async def chat_stream_sse(
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
    service: ChatService = Depends(get_chat_service),
):
    """SSE endpoint for chat streaming."""
    body = await request.json()
    query = body.get("query", "")
    session_id = body.get("session_id") or None
    thinking_mode = body.get("thinking_mode", False)

    if not query or not query.strip():
        raise http_errors.bad_request("Query cannot be empty")

    return StreamingResponse(
        _sse_stream(auth, query, session_id, thinking_mode, service),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
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
