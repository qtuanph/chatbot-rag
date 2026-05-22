"""Analytics service — token usage, cost estimation, latency aggregation."""

from __future__ import annotations

from app.core.config import settings
from app.modules.analytics.repository import AnalyticsRepository


class AnalyticsService:
    """Business logic for analytics aggregation."""

    def __init__(self, repo: AnalyticsRepository) -> None:
        self.repo = repo

    async def get_stats(self, *, is_admin: bool, user_id: str, days: int = 30) -> dict:
        """Get aggregated token/cost/latency stats, scoped by role.

        Returns overall stats + per-model-type breakdown (llm, embedding, reranker).
        """
        totals = await self.repo.get_totals(is_admin, user_id)
        total_sessions = await self.repo.get_distinct_session_count(is_admin, user_id)
        daily_rows = await self.repo.get_daily_stats(is_admin, user_id, days_limit=days)
        model_type_stats = await self.repo.get_model_type_stats(is_admin, user_id, days=days)
        daily_by_type = await self.repo.get_daily_stats_by_model_type(is_admin, user_id, days_limit=days)
        recent_requests = await self.repo.get_recent_requests(is_admin, user_id, limit=20)

        total_tokens_in = totals["tokens_in"]
        total_tokens_out = totals["tokens_out"]

        # Compute cost per day and total
        daily_stats = []
        for row in daily_rows:
            day_cost = self._compute_cost(row["tokens_in"], row["tokens_out"])
            daily_stats.append(
                {
                    "date": row["date"],
                    "messages": row["messages"],
                    "tokens_in": row["tokens_in"],
                    "tokens_out": row["tokens_out"],
                    "avg_latency_ms": row["avg_latency_ms"],
                    "cost_usd": round(day_cost, 6),
                }
            )

        estimated_cost = self._compute_cost(total_tokens_in, total_tokens_out)

        return {
            "total_messages": totals["messages"],
            "total_sessions": total_sessions,
            "total_tokens_in": total_tokens_in,
            "total_tokens_out": total_tokens_out,
            "total_tokens": total_tokens_in + total_tokens_out,
            "avg_latency_ms": totals["avg_latency_ms"],
            "estimated_cost_usd": round(estimated_cost, 6),
            "model_used": "multiple (tracked in ai_model_usage)",
            "daily": daily_stats,
            "by_model_type": model_type_stats,
            "daily_by_model_type": daily_by_type,
            "recent_requests": recent_requests,
            "pricing": {
                "input_per_1m": settings.ai_input_cost_per_1m,
                "output_per_1m": settings.ai_output_cost_per_1m,
                "model": settings.ai_proxy_default_model or "unknown",
                "note": "Free tier" if settings.ai_input_cost_per_1m == 0 else "",
            },
        }

    async def clear_stats(self) -> int:
        """Delete all ai_model_usage records. Admin only."""
        return await self.repo.clear_all_usage()

    @staticmethod
    def _compute_cost(tokens_in: int, tokens_out: int) -> float:
        return (tokens_in * settings.ai_input_cost_per_1m + tokens_out * settings.ai_output_cost_per_1m) / 1_000_000
