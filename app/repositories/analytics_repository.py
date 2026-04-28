"""Repository for analytics/aggregation data access."""

from __future__ import annotations

from datetime import date

from sqlalchemy import cast, Date, func
from sqlalchemy.orm import Session

from app.models.chat import ChatMessage, ChatSession


class AnalyticsRepository:
    """Data access layer for analytics aggregation queries."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def _base_query(self, is_admin: bool, user_id: str):
        """Build base query for assistant messages with token data, scoped by role."""
        q = self.session.query(ChatMessage).filter(
            ChatMessage.role == "assistant",
            ChatMessage.tokens_in.isnot(None),
        )
        if not is_admin:
            user_session_ids = (
                self.session.query(ChatSession.id)
                .filter(
                    ChatSession.user_id == user_id,
                    ChatSession.deleted_at.is_(None),
                )
                .subquery()
            )
            q = q.filter(ChatMessage.session_id.in_(user_session_ids))
        return q

    def get_totals(self, is_admin: bool, user_id: str) -> dict:
        """Get overall token/message/latency totals."""
        q = self._base_query(is_admin, user_id)
        row = q.with_entities(
            func.count(ChatMessage.id).label("messages"),
            func.coalesce(func.sum(ChatMessage.tokens_in), 0).label("tokens_in"),
            func.coalesce(func.sum(ChatMessage.tokens_out), 0).label("tokens_out"),
            func.coalesce(func.avg(ChatMessage.latency_ms), 0).label("avg_latency_ms"),
        ).one()

        return {
            "messages": row.messages or 0,
            "tokens_in": int(row.tokens_in or 0),
            "tokens_out": int(row.tokens_out or 0),
            "avg_latency_ms": int(row.avg_latency_ms or 0),
        }

    def get_distinct_session_count(self, is_admin: bool, user_id: str) -> int:
        """Count distinct sessions with assistant messages."""
        q = self.session.query(func.count(func.distinct(ChatMessage.session_id))).filter(
            ChatMessage.role == "assistant",
            ChatMessage.tokens_in.isnot(None),
        )
        if not is_admin:
            user_session_ids = (
                self.session.query(ChatSession.id)
                .filter(
                    ChatSession.user_id == user_id,
                    ChatSession.deleted_at.is_(None),
                )
                .subquery()
            )
            q = q.filter(ChatMessage.session_id.in_(user_session_ids))
        return q.scalar() or 0

    def get_daily_stats(self, is_admin: bool, user_id: str, days_limit: int = 30) -> list[dict]:
        """Get daily breakdown of token usage, message count, and latency."""
        q = self.session.query(
            cast(ChatMessage.created_at, Date).label("day"),
            func.count(ChatMessage.id).label("messages"),
            func.coalesce(func.sum(ChatMessage.tokens_in), 0).label("tokens_in"),
            func.coalesce(func.sum(ChatMessage.tokens_out), 0).label("tokens_out"),
            func.coalesce(func.avg(ChatMessage.latency_ms), 0).label("avg_latency_ms"),
        ).filter(
            ChatMessage.role == "assistant",
            ChatMessage.tokens_in.isnot(None),
        )
        if not is_admin:
            user_session_ids = (
                self.session.query(ChatSession.id)
                .filter(
                    ChatSession.user_id == user_id,
                    ChatSession.deleted_at.is_(None),
                )
                .subquery()
            )
            q = q.filter(ChatMessage.session_id.in_(user_session_ids))
        q = q.group_by("day").order_by("day").limit(days_limit)

        results = []
        for row in q.all():
            results.append(
                {
                    "date": row.day.isoformat() if isinstance(row.day, date) else str(row.day),
                    "messages": row.messages,
                    "tokens_in": int(row.tokens_in or 0),
                    "tokens_out": int(row.tokens_out or 0),
                    "avg_latency_ms": int(row.avg_latency_ms or 0),
                }
            )
        return results
