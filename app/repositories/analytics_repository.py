from datetime import date

from sqlalchemy import cast, Date, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatMessage, ChatSession


class AnalyticsRepository:
    """Data access layer for analytics aggregation queries."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _base_select(self, is_admin: bool, user_id: str):
        """Build base select statement for assistant messages with token data, scoped by role."""
        stmt = select(ChatMessage).where(
            ChatMessage.role == "assistant",
            ChatMessage.tokens_in.isnot(None),
        )
        if not is_admin:
            user_session_ids = (
                select(ChatSession.id)
                .where(
                    ChatSession.user_id == user_id,
                    ChatSession.deleted_at.is_(None),
                )
                .subquery()
            )
            stmt = stmt.where(ChatMessage.session_id.in_(user_session_ids))
        return stmt

    async def get_totals(self, is_admin: bool, user_id: str) -> dict:
        """Get overall token/message/latency totals."""
        base_stmt = self._base_select(is_admin, user_id)
        # Wrap the base stmt to perform aggregations
        stmt = select(
            func.count(ChatMessage.id).label("messages"),
            func.coalesce(func.sum(ChatMessage.tokens_in), 0).label("tokens_in"),
            func.coalesce(func.sum(ChatMessage.tokens_out), 0).label("tokens_out"),
            func.coalesce(func.avg(ChatMessage.latency_ms), 0).label("avg_latency_ms"),
        ).select_from(base_stmt.subquery())
        
        result = await self.session.execute(stmt)
        row = result.one()

        return {
            "messages": row.messages or 0,
            "tokens_in": int(row.tokens_in or 0),
            "tokens_out": int(row.tokens_out or 0),
            "avg_latency_ms": int(row.avg_latency_ms or 0),
        }

    async def get_distinct_session_count(self, is_admin: bool, user_id: str) -> int:
        """Count distinct sessions with assistant messages."""
        stmt = select(func.count(func.distinct(ChatMessage.session_id))).where(
            ChatMessage.role == "assistant",
            ChatMessage.tokens_in.isnot(None),
        )
        if not is_admin:
            user_session_ids = (
                select(ChatSession.id)
                .where(
                    ChatSession.user_id == user_id,
                    ChatSession.deleted_at.is_(None),
                )
                .subquery()
            )
            stmt = stmt.where(ChatMessage.session_id.in_(user_session_ids))
        
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def get_daily_stats(self, is_admin: bool, user_id: str, days_limit: int = 30) -> list[dict]:
        """Get daily breakdown of token usage, message count, and latency."""
        day_col = cast(ChatMessage.created_at, Date).label("day")
        stmt = (
            select(
                day_col,
                func.count(ChatMessage.id).label("messages"),
                func.coalesce(func.sum(ChatMessage.tokens_in), 0).label("tokens_in"),
                func.coalesce(func.sum(ChatMessage.tokens_out), 0).label("tokens_out"),
                func.coalesce(func.avg(ChatMessage.latency_ms), 0).label("avg_latency_ms"),
            )
            .where(
                ChatMessage.role == "assistant",
                ChatMessage.tokens_in.isnot(None),
            )
        )
        
        if not is_admin:
            user_session_ids = (
                select(ChatSession.id)
                .where(
                    ChatSession.user_id == user_id,
                    ChatSession.deleted_at.is_(None),
                )
                .subquery()
            )
            stmt = stmt.where(ChatMessage.session_id.in_(user_session_ids))
        
        stmt = stmt.group_by(day_col).order_by(day_col).limit(days_limit)
        
        result = await self.session.execute(stmt)
        rows = result.all()

        results = []
        for row in rows:
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
