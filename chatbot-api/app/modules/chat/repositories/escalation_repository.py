"""Repository for escalations and published FAQs."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.escalation import Escalation


class EscalationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, escalation_id: str) -> Escalation | None:
        stmt = select(Escalation).where(Escalation.id == UUID(escalation_id))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_faqs_for_tenant(self, tenant_id: str) -> list[Escalation]:
        stmt = (
            select(Escalation)
            .where(
                Escalation.tenant_id == UUID(tenant_id),
                Escalation.status == "published_faq",
            )
            .order_by(Escalation.updated_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_open_escalations_for_tenant(self, tenant_id: str) -> list[Escalation]:
        stmt = (
            select(Escalation)
            .where(
                Escalation.tenant_id == UUID(tenant_id),
                Escalation.status == "open",
            )
            .order_by(Escalation.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(
        self,
        *,
        tenant_id: str,
        question: str,
        answer: str,
        question_variants: list[str] | None = None,
        query_hashes: list[str] | None = None,
        citations: list[dict[str, Any]] | None = None,
        status: str = "published_faq",
        conversation_id: str | None = None,
    ) -> Escalation:
        entry = Escalation(
            tenant_id=UUID(tenant_id),
            question=question,
            answer=answer,
            question_variants=question_variants or [],
            query_hashes=query_hashes or [],
            citations=citations or [],
            status=status,
            conversation_id=conversation_id,
        )
        self.session.add(entry)
        await self.session.commit()
        await self.session.refresh(entry)
        return entry

    async def update_faq(
        self,
        escalation_id: str,
        *,
        question: str | None = None,
        answer: str | None = None,
        question_variants: list[str] | None = None,
        query_hashes: list[str] | None = None,
        citations: list[dict[str, Any]] | None = None,
        status: str | None = None,
    ) -> Escalation | None:
        entry = await self.get_by_id(escalation_id)
        if not entry:
            return None

        if question is not None:
            entry.question = question
        if answer is not None:
            entry.answer = answer
        if question_variants is not None:
            entry.question_variants = question_variants
        if query_hashes is not None:
            entry.query_hashes = query_hashes
        if citations is not None:
            entry.citations = citations
        if status is not None:
            entry.status = status

        await self.session.commit()
        await self.session.refresh(entry)
        return entry

    async def delete(self, escalation_id: str) -> bool:
        entry = await self.get_by_id(escalation_id)
        if not entry:
            return False
        entry.status = "closed"
        await self.session.commit()
        return True
