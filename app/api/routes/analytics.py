"""Analytics API — token usage, cost estimation, latency stats."""

from fastapi import APIRouter, Depends

from app.api.deps import AuthContext, get_analytics_service, get_auth_context
from app.core import http_errors
from app.core.config import settings
from app.utils.throttle import RequestThrottle
from app.services.analytics.analytics_service import AnalyticsService

router = APIRouter(tags=["analytics"])
throttle = RequestThrottle()


@router.get("/analytics/stats")
async def get_analytics_stats(
    auth: AuthContext = Depends(get_auth_context),
    service: AnalyticsService = Depends(get_analytics_service),
) -> dict:
    """Get aggregated token/cost/latency stats. Admin: system-wide. Member: own data."""
    if not throttle.allow(
        f"throttle:analytics:{auth.user_id}", limit=settings.effective_rate_limit(60), window_seconds=60
    ):
        raise http_errors.too_many_requests("Too many requests. Please wait.")

    is_admin = auth.role == "admin"
    return await service.get_stats(is_admin=is_admin, user_id=auth.user_id)
