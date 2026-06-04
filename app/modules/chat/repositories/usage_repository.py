"""Repository for AI model usage logging and daily stats."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.usage import AiModelUsage
from app.core.config import settings
from app.utils.datetime_utils import utc_now

logger = logging.getLogger(__name__)


class UsageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def log_usage(
        self,
        model_name: str,
        prompt_tokens: int,
        completion_tokens: int,
        endpoint: str,
        cost_micros_vnd: int = 0,
        latency_ms: float = 0.0,
        model_type: str = "llm",
        tenant_id: str | UUID | None = None,
        user_id: str | UUID | None = None,
    ) -> None:
        """Log an AI model usage event asynchronously."""
        tid = UUID(tenant_id) if isinstance(tenant_id, str) and tenant_id else tenant_id
        uid = UUID(user_id) if isinstance(user_id, str) and user_id else user_id

        total = prompt_tokens + completion_tokens
        entry = AiModelUsage(
            model_name=model_name,
            model_type=model_type,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total,
            cost_micros_vnd=int(cost_micros_vnd),
            currency_code=settings.billing_currency_code,
            latency_ms=latency_ms,
            endpoint=endpoint,
            tenant_id=tid if isinstance(tid, UUID) else None,
            user_id=uid if isinstance(uid, UUID) else None,
        )
        self.session.add(entry)
        await self.session.commit()

    async def get_daily_stats(self, days: int = 30) -> list[dict[str, Any]]:
        """Aggregate usage by day for the last N days."""
        cutoff = utc_now() - timedelta(days=days)
        stmt = text("""
            SELECT
                DATE(created_at) AS day,
                SUM(prompt_tokens) AS prompt_tokens,
                SUM(completion_tokens) AS completion_tokens,
                SUM(total_tokens) AS total_tokens,
                SUM(cost_micros_vnd) AS cost_micros_vnd,
                COUNT(*) AS call_count
            FROM ai_model_usage
            WHERE created_at >= :cutoff
            GROUP BY DATE(created_at)
            ORDER BY day DESC
        """)
        result = await self.session.execute(stmt, {"cutoff": cutoff})
        rows = result.fetchall()
        return [
            {
                "day": str(r[0]),
                "prompt_tokens": int(r[1]),
                "completion_tokens": int(r[2]),
                "total_tokens": int(r[3]),
                "cost_micros_vnd": int(r[4] or 0),
                "call_count": int(r[5]),
            }
            for r in rows
        ]

    async def get_endpoint_breakdown(self, days: int = 7) -> list[dict[str, Any]]:
        """Breakdown by endpoint for the last N days."""
        cutoff = utc_now() - timedelta(days=days)
        stmt = text("""
            SELECT
                endpoint,
                SUM(total_tokens) AS total_tokens,
                COUNT(*) AS call_count
            FROM ai_model_usage
            WHERE created_at >= :cutoff
            GROUP BY endpoint
            ORDER BY total_tokens DESC
        """)
        result = await self.session.execute(stmt, {"cutoff": cutoff})
        rows = result.fetchall()
        return [
            {
                "endpoint": str(r[0]),
                "total_tokens": int(r[1]),
                "call_count": int(r[2]),
            }
            for r in rows
        ]
