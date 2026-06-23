from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import User
from app.models.tenant import Tenant
from app.models.feedback import ChatFeedback
from app.models.usage import AiModelUsage
from app.utils.datetime_utils import to_vietnam_iso, utc_now


class AnalyticsRepository:
    """Tenant-aware analytics queries backed only by ai_model_usage."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _usage_scope(self, *, is_platform_admin: bool, user_id: str, tenant_id: str | None):
        stmt = select(AiModelUsage)
        if is_platform_admin:
            return stmt
        if tenant_id:
            return stmt.where(AiModelUsage.tenant_id == tenant_id)
        return stmt.where(AiModelUsage.user_id == user_id)

    async def get_totals(self, *, is_platform_admin: bool, user_id: str, tenant_id: str | None) -> dict:
        scoped = self._usage_scope(is_platform_admin=is_platform_admin, user_id=user_id, tenant_id=tenant_id).subquery()
        stmt = select(
            func.count(scoped.c.id).label("messages"),
            func.coalesce(func.sum(scoped.c.prompt_tokens), 0).label("tokens_in"),
            func.coalesce(func.sum(scoped.c.completion_tokens), 0).label("tokens_out"),
            func.coalesce(func.avg(scoped.c.latency_ms), 0).label("avg_latency_ms"),
        )
        row = (await self.session.execute(stmt)).one()
        return {
            "messages": int(row.messages or 0),
            "tokens_in": int(row.tokens_in or 0),
            "tokens_out": int(row.tokens_out or 0),
            "avg_latency_ms": int(row.avg_latency_ms or 0),
        }

    async def get_model_type_stats(
        self,
        *,
        is_platform_admin: bool,
        user_id: str,
        tenant_id: str | None,
        days: int = 30,
    ) -> dict:
        cutoff = utc_now() - timedelta(days=days)
        stmt = (
            select(
                AiModelUsage.model_type,
                func.coalesce(func.sum(AiModelUsage.prompt_tokens), 0).label("tokens_in"),
                func.coalesce(func.sum(AiModelUsage.completion_tokens), 0).label("tokens_out"),
                func.coalesce(func.avg(AiModelUsage.latency_ms), 0).label("avg_latency_ms"),
                func.count(AiModelUsage.id).label("call_count"),
                func.coalesce(func.sum(AiModelUsage.cost_micros_vnd), 0).label("cost_micros_vnd"),
            )
            .where(AiModelUsage.created_at >= cutoff)
            .group_by(AiModelUsage.model_type)
        )
        if not is_platform_admin:
            if tenant_id:
                stmt = stmt.where(AiModelUsage.tenant_id == tenant_id)
            else:
                stmt = stmt.where(AiModelUsage.user_id == user_id)

        rows = (await self.session.execute(stmt)).all()
        result = {
            "llm": {"tokens_in": 0, "tokens_out": 0, "avg_latency_ms": 0, "call_count": 0, "cost_micros_vnd": 0},
            "embedding": {"tokens_in": 0, "tokens_out": 0, "avg_latency_ms": 0, "call_count": 0, "cost_micros_vnd": 0},
            "reranker": {"tokens_in": 0, "tokens_out": 0, "avg_latency_ms": 0, "call_count": 0, "cost_micros_vnd": 0},
        }
        for row in rows:
            if row.model_type in result:
                result[row.model_type] = {
                    "tokens_in": int(row.tokens_in or 0),
                    "tokens_out": int(row.tokens_out or 0),
                    "avg_latency_ms": int(row.avg_latency_ms or 0),
                    "call_count": int(row.call_count or 0),
                    "cost_micros_vnd": int(row.cost_micros_vnd or 0),
                }
        return result

    async def get_daily_stats(
        self,
        *,
        is_platform_admin: bool,
        user_id: str,
        tenant_id: str | None,
        days_limit: int = 30,
    ) -> list[dict]:
        cutoff = utc_now() - timedelta(days=days_limit)
        day_col = cast(AiModelUsage.created_at, Date).label("day")
        stmt = (
            select(
                day_col,
                func.count(AiModelUsage.id).label("messages"),
                func.coalesce(func.sum(AiModelUsage.prompt_tokens), 0).label("tokens_in"),
                func.coalesce(func.sum(AiModelUsage.completion_tokens), 0).label("tokens_out"),
                func.coalesce(func.avg(AiModelUsage.latency_ms), 0).label("avg_latency_ms"),
            )
            .where(AiModelUsage.created_at >= cutoff)
            .group_by(day_col)
            .order_by(day_col)
        )
        if not is_platform_admin:
            if tenant_id:
                stmt = stmt.where(AiModelUsage.tenant_id == tenant_id)
            else:
                stmt = stmt.where(AiModelUsage.user_id == user_id)

        rows = (await self.session.execute(stmt)).all()
        return [
            {
                "date": row.day.isoformat() if isinstance(row.day, date) else str(row.day),
                "messages": int(row.messages or 0),
                "tokens_in": int(row.tokens_in or 0),
                "tokens_out": int(row.tokens_out or 0),
                "avg_latency_ms": int(row.avg_latency_ms or 0),
            }
            for row in rows
        ]

    async def get_daily_stats_by_model_type(
        self,
        *,
        is_platform_admin: bool,
        user_id: str,
        tenant_id: str | None,
        days_limit: int = 30,
    ) -> list[dict]:
        cutoff = utc_now() - timedelta(days=days_limit)
        day_col = cast(AiModelUsage.created_at, Date).label("day")
        stmt = (
            select(
                day_col,
                AiModelUsage.model_type,
                func.coalesce(func.sum(AiModelUsage.prompt_tokens), 0).label("tokens_in"),
                func.coalesce(func.sum(AiModelUsage.completion_tokens), 0).label("tokens_out"),
                func.coalesce(func.avg(AiModelUsage.latency_ms), 0).label("avg_latency_ms"),
                func.count(AiModelUsage.id).label("call_count"),
                func.coalesce(func.sum(AiModelUsage.cost_micros_vnd), 0).label("cost_micros_vnd"),
            )
            .where(AiModelUsage.created_at >= cutoff)
            .group_by(day_col, AiModelUsage.model_type)
            .order_by(day_col)
        )
        if not is_platform_admin:
            if tenant_id:
                stmt = stmt.where(AiModelUsage.tenant_id == tenant_id)
            else:
                stmt = stmt.where(AiModelUsage.user_id == user_id)

        rows = (await self.session.execute(stmt)).all()
        by_day: dict[str, dict] = {}
        for row in rows:
            d = row.day.isoformat() if isinstance(row.day, date) else str(row.day)
            if d not in by_day:
                by_day[d] = {
                    "date": d,
                    "llm": {
                        "tokens_in": 0,
                        "tokens_out": 0,
                        "avg_latency_ms": 0,
                        "call_count": 0,
                        "cost_micros_vnd": 0,
                    },
                    "embedding": {
                        "tokens_in": 0,
                        "tokens_out": 0,
                        "avg_latency_ms": 0,
                        "call_count": 0,
                        "cost_micros_vnd": 0,
                    },
                    "reranker": {
                        "tokens_in": 0,
                        "tokens_out": 0,
                        "avg_latency_ms": 0,
                        "call_count": 0,
                        "cost_micros_vnd": 0,
                    },
                }
            if row.model_type in by_day[d]:
                by_day[d][row.model_type] = {
                    "tokens_in": int(row.tokens_in or 0),
                    "tokens_out": int(row.tokens_out or 0),
                    "avg_latency_ms": int(row.avg_latency_ms or 0),
                    "call_count": int(row.call_count or 0),
                    "cost_micros_vnd": int(row.cost_micros_vnd or 0),
                }
        return sorted(by_day.values(), key=lambda item: item["date"])

    async def get_recent_requests(
        self,
        *,
        is_platform_admin: bool,
        user_id: str,
        tenant_id: str | None,
        limit: int = 20,
    ) -> list[dict]:
        stmt = (
            select(
                AiModelUsage.model_name,
                AiModelUsage.model_type,
                AiModelUsage.prompt_tokens,
                AiModelUsage.completion_tokens,
                AiModelUsage.latency_ms,
                AiModelUsage.cost_micros_vnd,
                AiModelUsage.created_at,
            )
            .order_by(AiModelUsage.created_at.desc())
            .limit(limit)
        )
        if not is_platform_admin:
            if tenant_id:
                stmt = stmt.where(AiModelUsage.tenant_id == tenant_id)
            else:
                stmt = stmt.where(AiModelUsage.user_id == user_id)
        rows = (await self.session.execute(stmt)).all()
        return [
            {
                "model_name": row.model_name,
                "model_type": row.model_type,
                "tokens_in": int(row.prompt_tokens or 0),
                "tokens_out": int(row.completion_tokens or 0),
                "latency_ms": int(row.latency_ms or 0),
                "cost_micros_vnd": int(row.cost_micros_vnd or 0),
                "created_at": to_vietnam_iso(row.created_at) or "",
            }
            for row in rows
        ]

    async def clear_all_usage(self) -> int:
        from sqlalchemy import delete

        result = await self.session.execute(delete(AiModelUsage))
        await self.session.commit()
        return result.rowcount

    async def get_user_usage_summary(self, days: int = 30) -> list[dict]:
        cutoff = utc_now() - timedelta(days=days)
        usage_subq = (
            select(
                AiModelUsage.user_id.label("user_id"),
                func.coalesce(func.sum(AiModelUsage.prompt_tokens), 0).label("tokens_in"),
                func.coalesce(func.sum(AiModelUsage.completion_tokens), 0).label("tokens_out"),
                func.coalesce(func.sum(AiModelUsage.cost_micros_vnd), 0).label("cost_micros_vnd"),
                func.coalesce(func.count(AiModelUsage.id), 0).label("call_count"),
            )
            .where(AiModelUsage.user_id.isnot(None), AiModelUsage.created_at >= cutoff)
            .group_by(AiModelUsage.user_id)
            .subquery()
        )
        stmt = (
            select(
                User.id.label("user_id"),
                User.username.label("username"),
                func.coalesce(usage_subq.c.tokens_in, 0).label("tokens_in"),
                func.coalesce(usage_subq.c.tokens_out, 0).label("tokens_out"),
                func.coalesce(usage_subq.c.cost_micros_vnd, 0).label("cost_micros_vnd"),
                func.coalesce(usage_subq.c.call_count, 0).label("call_count"),
            )
            .outerjoin(usage_subq, usage_subq.c.user_id == User.id)
            .order_by(User.username.asc())
        )
        rows = (await self.session.execute(stmt)).all()
        return [
            {
                "user_id": str(row.user_id),
                "username": row.username,
                "tokens_in": int(row.tokens_in or 0),
                "tokens_out": int(row.tokens_out or 0),
                "total_tokens": int((row.tokens_in or 0) + (row.tokens_out or 0)),
                "cost_micros_vnd": int(row.cost_micros_vnd or 0),
                "call_count": int(row.call_count or 0),
                "window_days": days,
            }
            for row in rows
        ]

    async def get_tenant_usage_summary(self, days: int = 30) -> list[dict]:
        cutoff = utc_now() - timedelta(days=days)
        usage_subq = (
            select(
                AiModelUsage.tenant_id.label("tenant_id"),
                func.coalesce(func.sum(AiModelUsage.prompt_tokens), 0).label("tokens_in"),
                func.coalesce(func.sum(AiModelUsage.completion_tokens), 0).label("tokens_out"),
                func.coalesce(func.sum(AiModelUsage.cost_micros_vnd), 0).label("cost_micros_vnd"),
                func.coalesce(func.count(AiModelUsage.id), 0).label("call_count"),
                func.coalesce(func.avg(AiModelUsage.latency_ms), 0).label("avg_latency_ms"),
            )
            .where(AiModelUsage.tenant_id.isnot(None), AiModelUsage.created_at >= cutoff)
            .group_by(AiModelUsage.tenant_id)
            .subquery()
        )
        stmt = (
            select(
                Tenant.id.label("tenant_id"),
                Tenant.slug.label("tenant_slug"),
                Tenant.name.label("tenant_name"),
                func.coalesce(usage_subq.c.tokens_in, 0).label("tokens_in"),
                func.coalesce(usage_subq.c.tokens_out, 0).label("tokens_out"),
                func.coalesce(usage_subq.c.cost_micros_vnd, 0).label("cost_micros_vnd"),
                func.coalesce(usage_subq.c.call_count, 0).label("call_count"),
                func.coalesce(usage_subq.c.avg_latency_ms, 0).label("avg_latency_ms"),
            )
            .outerjoin(usage_subq, usage_subq.c.tenant_id == Tenant.id)
            .order_by(func.coalesce(usage_subq.c.cost_micros_vnd, 0).desc(), Tenant.name.asc())
        )
        rows = (await self.session.execute(stmt)).all()
        return [
            {
                "tenant_id": str(row.tenant_id),
                "tenant_slug": row.tenant_slug,
                "tenant_name": row.tenant_name,
                "tokens_in": int(row.tokens_in or 0),
                "tokens_out": int(row.tokens_out or 0),
                "total_tokens": int((row.tokens_in or 0) + (row.tokens_out or 0)),
                "cost_micros_vnd": int(row.cost_micros_vnd or 0),
                "call_count": int(row.call_count or 0),
                "avg_latency_ms": int(row.avg_latency_ms or 0),
                "window_days": days,
            }
            for row in rows
        ]

    async def get_feedback_rows(
        self,
        *,
        is_platform_admin: bool,
        user_id: str,
        tenant_id: str | None,
        days: int = 30,
    ) -> list[dict]:
        cutoff = utc_now() - timedelta(days=days)
        stmt = (
            select(
                ChatFeedback.tenant_id,
                ChatFeedback.user_id,
                ChatFeedback.feedback_type,
                ChatFeedback.document_ids,
                ChatFeedback.section_ids,
                ChatFeedback.citations,
                ChatFeedback.created_at,
            )
            .where(ChatFeedback.created_at >= cutoff)
            .order_by(ChatFeedback.created_at.desc())
        )
        if not is_platform_admin:
            if tenant_id:
                stmt = stmt.where(ChatFeedback.tenant_id == tenant_id)
            else:
                stmt = stmt.where(ChatFeedback.user_id == user_id)
        rows = (await self.session.execute(stmt)).all()
        return [
            {
                "tenant_id": str(row.tenant_id),
                "user_id": str(row.user_id) if row.user_id else None,
                "feedback_type": row.feedback_type,
                "document_ids": list(row.document_ids or []),
                "section_ids": list(row.section_ids or []),
                "citations": list(row.citations or []),
                "created_at": to_vietnam_iso(row.created_at) or "",
            }
            for row in rows
        ]

    async def get_tenant_feedback_summary(self, days: int = 30) -> dict[str, dict]:
        cutoff = utc_now() - timedelta(days=days)
        stmt = (
            select(
                ChatFeedback.tenant_id,
                ChatFeedback.feedback_type,
                func.count(ChatFeedback.id).label("count"),
            )
            .where(ChatFeedback.created_at >= cutoff)
            .group_by(ChatFeedback.tenant_id, ChatFeedback.feedback_type)
        )
        rows = (await self.session.execute(stmt)).all()
        result: dict[str, dict] = {}
        for row in rows:
            tenant_id = str(row.tenant_id)
            bucket = result.setdefault(tenant_id, {"like_count": 0, "dislike_count": 0})
            if row.feedback_type == "like":
                bucket["like_count"] = int(row.count or 0)
            elif row.feedback_type == "dislike":
                bucket["dislike_count"] = int(row.count or 0)
        return result
