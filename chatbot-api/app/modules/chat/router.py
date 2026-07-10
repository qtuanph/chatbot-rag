"""Stateless internal chat API endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from app.modules.tenants.deps import get_tenant_api_context
from app.modules.tenants.context import TenantApiContext
from app.modules.chat.deps import get_feedback_service
from app.core import http_errors
from app.modules.chat.schemas import ChatFeedbackRequest, ChatFeedbackResponse
from app.modules.chat.services import FeedbackService

router = APIRouter(tags=["chat"])
logger = logging.getLogger(__name__)


@router.post("/chat/feedback", response_model=ChatFeedbackResponse)
async def submit_chat_feedback(
    payload: ChatFeedbackRequest,
    api_context: TenantApiContext = Depends(get_tenant_api_context),
    feedback_service: FeedbackService = Depends(get_feedback_service),
) -> ChatFeedbackResponse:
    result = await feedback_service.submit_feedback(
        tenant_id=api_context.tenant_id,
        user_id=None,
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
