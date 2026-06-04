"""Analytics service — token usage, cost estimation, latency aggregation."""

from __future__ import annotations

from app.modules.analytics.repository import AnalyticsRepository
from app.core.config import settings
from app.utils.money import build_money_payload, compute_cost_micros_vnd


class AnalyticsService:
    """Business logic for analytics aggregation."""

    def __init__(self, repo: AnalyticsRepository) -> None:
        self.repo = repo

    async def get_stats(self, *, is_platform_admin: bool, user_id: str, tenant_id: str | None, days: int = 30) -> dict:
        """Get aggregated token/cost/latency stats, scoped by role.

        Returns overall stats + per-model-type breakdown (llm, embedding, reranker).
        """
        totals = await self.repo.get_totals(is_platform_admin=is_platform_admin, user_id=user_id, tenant_id=tenant_id)
        daily_rows = await self.repo.get_daily_stats(
            is_platform_admin=is_platform_admin, user_id=user_id, tenant_id=tenant_id, days_limit=days
        )
        model_type_stats = await self.repo.get_model_type_stats(
            is_platform_admin=is_platform_admin, user_id=user_id, tenant_id=tenant_id, days=days
        )
        daily_by_type = await self.repo.get_daily_stats_by_model_type(
            is_platform_admin=is_platform_admin, user_id=user_id, tenant_id=tenant_id, days_limit=days
        )
        recent_requests = await self.repo.get_recent_requests(
            is_platform_admin=is_platform_admin, user_id=user_id, tenant_id=tenant_id, limit=20
        )

        total_tokens_in = totals["tokens_in"]
        total_tokens_out = totals["tokens_out"]

        # Compute cost per day and total
        daily_stats = []
        for row in daily_rows:
            day_cost_micros = self._compute_cost_micros(row["tokens_in"], row["tokens_out"])
            daily_stats.append(
                {
                    "date": row["date"],
                    "messages": row["messages"],
                    "tokens_in": row["tokens_in"],
                    "tokens_out": row["tokens_out"],
                    "avg_latency_ms": row["avg_latency_ms"],
                    **build_money_payload(day_cost_micros),
                }
            )

        estimated_cost_micros = self._compute_cost_micros(total_tokens_in, total_tokens_out)

        result = {
            "total_messages": totals["messages"],
            "total_tokens_in": total_tokens_in,
            "total_tokens_out": total_tokens_out,
            "total_tokens": total_tokens_in + total_tokens_out,
            "avg_latency_ms": totals["avg_latency_ms"],
            "model_used": "multiple (tracked in ai_model_usage)",
            "daily": daily_stats,
            "by_model_type": model_type_stats,
            "daily_by_model_type": daily_by_type,
            "recent_requests": recent_requests,
            "pricing": {
                "currency_code": settings.billing_currency_code,
                "input_price_vnd_per_1m": settings.ai_input_price_vnd_per_1m,
                "output_price_vnd_per_1m": settings.ai_output_price_vnd_per_1m,
                "model": settings.ai_proxy_default_model or "unknown",
                "note": "Free tier" if settings.ai_input_price_vnd_per_1m == 0 else "",
            },
        }
        result.update(build_money_payload(estimated_cost_micros))
        return result

    async def clear_stats(self) -> int:
        """Delete all ai_model_usage records. Admin only."""
        return await self.repo.clear_all_usage()

    async def get_my_usage_windows(self, *, user_id: str) -> dict:
        """User-scoped usage in 1/7/30 day windows with LLM/Embedding/Reranker breakdown."""
        windows: dict[str, dict] = {}
        for days in (1, 7, 30):
            by_type = await self.repo.get_model_type_stats(
                is_platform_admin=False, user_id=user_id, tenant_id=None, days=days
            )
            totals_in = int(sum(int(v.get("tokens_in", 0)) for v in by_type.values()))
            totals_out = int(sum(int(v.get("tokens_out", 0)) for v in by_type.values()))
            total_cost_micros = int(sum(int(v.get("cost_micros_vnd", 0)) for v in by_type.values()))
            windows[str(days)] = {
                "days": days,
                "total": {
                    "tokens_in": totals_in,
                    "tokens_out": totals_out,
                    "total_tokens": totals_in + totals_out,
                    **build_money_payload(total_cost_micros),
                },
                "by_model_type": by_type,
            }

        return {
            "user_id": user_id,
            "windows": windows,
            "pricing": {
                "currency_code": settings.billing_currency_code,
                "input_price_vnd_per_1m": settings.ai_input_price_vnd_per_1m,
                "output_price_vnd_per_1m": settings.ai_output_price_vnd_per_1m,
            },
        }

    async def get_tenant_usage_summary(self, *, days: int = 30) -> dict:
        items = await self.repo.get_tenant_usage_summary(days=days)
        normalized = []
        for item in items:
            enriched = dict(item)
            enriched.update(build_money_payload(item["cost_micros_vnd"]))
            normalized.append(enriched)
        return {
            "items": normalized,
            "window_days": days,
            "pricing": {
                "currency_code": settings.billing_currency_code,
                "input_price_vnd_per_1m": settings.ai_input_price_vnd_per_1m,
                "output_price_vnd_per_1m": settings.ai_output_price_vnd_per_1m,
            },
        }

    @staticmethod
    def _compute_cost_micros(tokens_in: int, tokens_out: int) -> int:
        return compute_cost_micros_vnd(tokens_in, tokens_out)
