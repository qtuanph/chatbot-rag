"""FastAPI router for FAQ and Escalation CRUD operations."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis_client
from app.db.session import get_async_session
from app.modules.auth.deps import get_auth_context
from app.modules.auth.context import AuthContext
from app.modules.chat.repositories.escalation_repository import EscalationRepository
from app.modules.chat.services.faq_service import FAQService

router = APIRouter(tags=["faqs"])
logger = logging.getLogger(__name__)


class FAQCreateSchema(BaseModel):
    question: str = Field(..., min_length=2)
    answer: str = Field(..., min_length=2)
    question_variants: list[str] = Field(default_factory=list)
    citations: list[dict[str, Any]] = Field(default_factory=list)


class FAQUpdateSchema(BaseModel):
    question: str | None = Field(default=None, min_length=2)
    answer: str | None = Field(default=None, min_length=2)
    question_variants: list[str] | None = None
    citations: list[dict[str, Any]] | None = None
    status: str | None = Field(default=None, pattern="^(published|draft|archived)$")


class FAQPromoteSchema(BaseModel):
    question: str | None = None
    answer: str = Field(..., min_length=2)
    question_variants: list[str] = Field(default_factory=list)
    citations: list[dict[str, Any]] = Field(default_factory=list)


def _verify_platform_admin(ctx: AuthContext = Depends(get_auth_context)) -> None:
    """Only platform_admin — used for non-tenant-scoped operations (update/delete by faq_id)."""
    if ctx.role != "platform_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Only platform admin can manage FAQs and escalations",
        )


def _verify_tenant_faq_access(tenant_id: str, ctx: AuthContext = Depends(get_auth_context)) -> None:
    """C-08: Allow platform_admin (all tenants) or tenant_admin (their own tenant only)."""
    if ctx.role == "platform_admin":
        return
    if ctx.role == "tenant_admin" and ctx.tenant_id == tenant_id:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Forbidden: tenant_admin can only manage FAQs for their own tenant",
    )


def _get_faq_service(db: AsyncSession = Depends(get_async_session)) -> FAQService:
    repo = EscalationRepository(db)
    redis_client = get_redis_client()
    return FAQService(repo=repo, redis_client=redis_client)


@router.get("/tenants/{tenant_id}/faqs")
async def list_published_faqs(
    tenant_id: str,
    ctx: AuthContext = Depends(get_auth_context),
    service: FAQService = Depends(_get_faq_service),
) -> list[dict[str, Any]]:
    _verify_tenant_faq_access(tenant_id, ctx)
    return await service.list_faqs(tenant_id)


@router.post("/tenants/{tenant_id}/faqs", status_code=status.HTTP_201_CREATED)
async def create_faq(
    tenant_id: str,
    payload: FAQCreateSchema,
    ctx: AuthContext = Depends(get_auth_context),
    service: FAQService = Depends(_get_faq_service),
) -> dict[str, Any]:
    _verify_tenant_faq_access(tenant_id, ctx)
    return await service.create_faq(
        tenant_id=tenant_id,
        question=payload.question,
        answer=payload.answer,
        question_variants=payload.question_variants,
        citations=payload.citations,
    )


@router.put("/faqs/{faq_id}")
async def update_faq(
    faq_id: str,
    payload: FAQUpdateSchema,
    ctx: AuthContext = Depends(get_auth_context),
    service: FAQService = Depends(_get_faq_service),
) -> dict[str, Any]:
    _verify_platform_admin(ctx)
    try:
        return await service.update_faq(
            faq_id,
            question=payload.question,
            answer=payload.answer,
            question_variants=payload.question_variants,
            citations=payload.citations,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/faqs/{faq_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_faq(
    faq_id: str,
    ctx: AuthContext = Depends(get_auth_context),
    service: FAQService = Depends(_get_faq_service),
) -> None:
    _verify_platform_admin(ctx)
    success = await service.delete_faq(faq_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FAQ not found")


@router.get("/tenants/{tenant_id}/escalations")
async def list_open_escalations(
    tenant_id: str,
    ctx: AuthContext = Depends(get_auth_context),
    service: FAQService = Depends(_get_faq_service),
) -> list[dict[str, Any]]:
    _verify_tenant_faq_access(tenant_id, ctx)
    return await service.list_open_escalations(tenant_id)


@router.post("/escalations/{escalation_id}/promote")
async def promote_escalation_to_faq(
    escalation_id: str,
    payload: FAQPromoteSchema,
    ctx: AuthContext = Depends(get_auth_context),
    service: FAQService = Depends(_get_faq_service),
) -> dict[str, Any]:
    _verify_platform_admin(ctx)
    try:
        return await service.promote_escalation(
            escalation_id,
            question=payload.question,
            answer=payload.answer,
            question_variants=payload.question_variants,
            citations=payload.citations,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
