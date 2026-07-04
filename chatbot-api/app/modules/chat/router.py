"""Stateless internal chat API endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from app.modules.auth.deps import get_auth_context
from app.modules.auth.context import AuthContext
from app.modules.chat.deps import get_feedback_service
from app.core import http_errors
from app.modules.chat.schemas import ChatFeedbackRequest, ChatFeedbackResponse
from app.modules.chat.services import FeedbackService

router = APIRouter(tags=["chat"])
logger = logging.getLogger(__name__)


def _resolve_tenant_id(auth: AuthContext, request_tenant_id: str | None) -> str:
    tenant_id = auth.tenant_id or request_tenant_id
    if not tenant_id:
        raise http_errors.bad_request("tenant_id is required for platform admin chat testing")
    return tenant_id


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
