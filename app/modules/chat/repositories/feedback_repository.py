from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.feedback import ChatFeedback
from app.utils.datetime_utils import to_vietnam_datetime


class FeedbackRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_feedback(self, payload: dict[str, Any]) -> dict[str, Any]:
        row = ChatFeedback(**payload)
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return self._to_dict(row)

    async def list_feedback(
        self,
        *,
        tenant_id: str | None = None,
        user_id: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        stmt = select(ChatFeedback).order_by(ChatFeedback.created_at.desc()).limit(limit)
        if tenant_id:
            stmt = stmt.where(ChatFeedback.tenant_id == tenant_id)
        if user_id:
            stmt = stmt.where(ChatFeedback.user_id == user_id)
        rows = (await self.session.execute(stmt)).scalars().all()
        return [self._to_dict(row) for row in rows]

    @staticmethod
    def _to_dict(row: ChatFeedback) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "tenant_id": str(row.tenant_id),
            "user_id": str(row.user_id) if row.user_id else None,
            "feedback_type": row.feedback_type,
            "query_text": row.query_text,
            "assistant_answer": row.assistant_answer,
            "llm_model": row.llm_model,
            "embedding_model": row.embedding_model,
            "reranker_model": row.reranker_model,
            "document_ids": list(row.document_ids or []),
            "section_ids": list(row.section_ids or []),
            "citations": list(row.citations or []),
            "metadata": dict(row.metadata_json or {}),
            "created_at": to_vietnam_datetime(row.created_at),
        }
