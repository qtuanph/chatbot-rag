from datetime import date, datetime, timedelta

from sqlalchemy import cast, Date, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatMessage, ChatSession
from app.models.usage import AiModelUsage


class AnalyticsRepository:
    """Data access layer for analytics aggregation queries."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _base_select(self, is_admin: bool, user_id: str):
        """Build base select for assistant messages (messages + latency scoped by role)."""
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
        """Overall stats: tokens from ai_model_usage, messages/latency from chat_messages."""
        # Chat-specific: messages + latency
        chat_stmt = self._base_select(is_admin, user_id).subquery()
        chat_query = select(
            func.count(chat_stmt.c.id).label("messages"),
            func.coalesce(func.avg(chat_stmt.c.latency_ms), 0).label("avg_latency_ms"),
        )
        chat_row = (await self.session.execute(chat_query)).one()

        # Token totals from ai_model_usage (ALL model calls, including auxiliary)
        token_query = select(
            func.coalesce(func.sum(AiModelUsage.prompt_tokens), 0).label("tokens_in"),
            func.coalesce(func.sum(AiModelUsage.completion_tokens), 0).label("tokens_out"),
        )
        if not is_admin:
            token_query = token_query.where(AiModelUsage.user_id == user_id)
        token_row = (await self.session.execute(token_query)).one()

        return {
            "messages": chat_row.messages or 0,
            "tokens_in": int(token_row.tokens_in or 0),
            "tokens_out": int(token_row.tokens_out or 0),
            "avg_latency_ms": int(chat_row.avg_latency_ms or 0),
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
        """Daily breakdown: tokens from ai_model_usage, messages/latency from chat_messages, merged by date."""
        cutoff = datetime.utcnow() - timedelta(days=days_limit)
        day_col = cast(AiModelUsage.created_at, Date).label("day")

        # Token daily from ai_model_usage
        token_query = select(
            day_col,
            func.coalesce(func.sum(AiModelUsage.prompt_tokens), 0).label("tokens_in"),
            func.coalesce(func.sum(AiModelUsage.completion_tokens), 0).label("tokens_out"),
        ).where(AiModelUsage.created_at >= cutoff)
        if not is_admin:
            token_query = token_query.where(AiModelUsage.user_id == user_id)
        token_query = token_query.group_by(day_col).order_by(day_col)

        token_by_day = {}
        for row in (await self.session.execute(token_query)).all():
            d = row.day.isoformat() if isinstance(row.day, date) else str(row.day)
            token_by_day[d] = {"tokens_in": int(row.tokens_in or 0), "tokens_out": int(row.tokens_out or 0)}

        # Message/latency daily from chat_messages
        msg_day_col = cast(ChatMessage.created_at, Date).label("day")
        msg_query = select(
            msg_day_col,
            func.count(ChatMessage.id).label("messages"),
            func.coalesce(func.avg(ChatMessage.latency_ms), 0).label("avg_latency_ms"),
        ).where(
            ChatMessage.role == "assistant",
            ChatMessage.tokens_in.isnot(None),
            ChatMessage.created_at >= cutoff,
        )
        if not is_admin:
            user_session_ids = (
                select(ChatSession.id)
                .where(ChatSession.user_id == user_id, ChatSession.deleted_at.is_(None))
                .subquery()
            )
            msg_query = msg_query.where(ChatMessage.session_id.in_(user_session_ids))
        msg_query = msg_query.group_by(msg_day_col).order_by(msg_day_col)

        msg_by_day = {}
        for row in (await self.session.execute(msg_query)).all():
            d = row.day.isoformat() if isinstance(row.day, date) else str(row.day)
            msg_by_day[d] = {"messages": row.messages, "avg_latency_ms": int(row.avg_latency_ms or 0)}

        # Merge both sets by date
        all_dates = sorted(set(list(token_by_day.keys()) + list(msg_by_day.keys())))

        results = []
        for d in all_dates:
            t = token_by_day.get(d, {"tokens_in": 0, "tokens_out": 0})
            m = msg_by_day.get(d, {"messages": 0, "avg_latency_ms": 0})
            results.append(
                {
                    "date": d,
                    "messages": m["messages"],
                    "tokens_in": t["tokens_in"],
                    "tokens_out": t["tokens_out"],
                    "avg_latency_ms": m["avg_latency_ms"],
                }
            )
        return results
