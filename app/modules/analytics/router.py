"""Analytics API — token usage, cost estimation, latency stats."""

from fastapi import APIRouter, Depends, Query

from app.api.deps import AuthContext, get_analytics_service, get_auth_context, get_rate_limiter
from app.core import http_errors
from app.core.config import settings
from app.utils.rate_limiter import RateLimiter
from app.modules.analytics.service import AnalyticsService

router = APIRouter(tags=["analytics"])


@router.get("/analytics/stats")
async def get_analytics_stats(
    days: int = Query(default=30, ge=1, le=365, description="Number of days to look back (1=today, 7=week, 30=month)"),
    auth: AuthContext = Depends(get_auth_context),
    service: AnalyticsService = Depends(get_analytics_service),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
) -> dict:
    """Get aggregated token/cost/latency stats. Admin: system-wide. Member: own data.

    Query params:
    - days: 1 (today), 7 (week), 30 (month), or custom (1-365)
    """
    if not await rate_limiter.is_allowed(
        f"analytics:{auth.user_id}", limit=settings.effective_rate_limit(60), window_ms=60000
    ):
        raise http_errors.too_many_requests("Too many requests. Please wait.")

    is_platform_admin = auth.role == "platform_admin"
    return await service.get_stats(
        is_platform_admin=is_platform_admin,
        user_id=auth.user_id,
        tenant_id=auth.tenant_id,
        days=days,
    )


@router.delete("/analytics/stats")
async def clear_analytics_stats(
    auth: AuthContext = Depends(get_auth_context),
    service: AnalyticsService = Depends(get_analytics_service),
) -> dict:
    """Clear all analytics stats (admin only). Resets ai_model_usage table."""
    if auth.role != "platform_admin":
        raise http_errors.forbidden("Only admins can clear analytics data")

    deleted = await service.clear_stats()
    return {"status": "cleared", "deleted_records": deleted}


@router.get("/analytics/me/usage")
async def get_my_usage_windows(
    auth: AuthContext = Depends(get_auth_context),
    service: AnalyticsService = Depends(get_analytics_service),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
) -> dict:
    """Get current user's usage windows (1/7/30 days) with LLM/Embedding/Reranker breakdown."""
    if not await rate_limiter.is_allowed(
        f"analytics:me:{auth.user_id}", limit=settings.effective_rate_limit(60), window_ms=60000
    ):
        raise http_errors.too_many_requests("Too many requests. Please wait.")
    return await service.get_my_usage_windows(user_id=auth.user_id)
