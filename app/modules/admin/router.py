"""Admin REST API — model listing and usage stats."""

from __future__ import annotations

import httpx
import logging
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_async_session
from app.modules.analytics.repository import AnalyticsRepository
from app.modules.chat.repositories.usage_repository import UsageRepository
from app.api.deps import require_admin, AuthContext

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/models")
async def list_models(auth: AuthContext = Depends(require_admin)):
    """List available models from 9Router's connected providers."""
    proxy_base = settings.ai_proxy_url.rstrip("/")
    headers = {}
    if settings.ai_proxy_api_key:
        headers["Authorization"] = f"Bearer {settings.ai_proxy_api_key}"
    try:
        async with httpx.AsyncClient(timeout=settings.ai_proxy_timeout) as client:
            resp = await client.get(f"{proxy_base}/v1/models", headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                models = [{"id": m["id"], "provider": m.get("provider", "")} for m in data.get("data", [])]
                return {"models": models}
            return {"models": []}
    except Exception as e:
        logger.error("list_models error: %s", e)
        return {"models": []}


@router.get("/usage/daily")
async def get_daily_usage(
    days: int = Query(30, ge=1, le=365),
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_admin),
):
    """Daily token usage breakdown for quota tracking."""
    repo = UsageRepository(session)
    daily = await repo.get_daily_stats(days=days)
    breakdown = await repo.get_endpoint_breakdown(days=days)
    return {"daily": daily, "endpoint_breakdown": breakdown, "days": days}


@router.get("/users/usage")
async def get_users_usage(
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_admin),
):
    """Per-user usage summary in last 30 days.

    Note: token in/out in this summary is LLM-only.
    """
    repo = AnalyticsRepository(session)
    items = await repo.get_user_usage_summary(days=30)
    return {"items": items}


@router.get("/users/{user_id}/usage")
async def get_user_usage_detail(
    user_id: str,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_admin),
):
    """Usage detail for a specific user in last 30 days with 3 model types."""
    repo = AnalyticsRepository(session)
    days = 30
    daily = await repo.get_daily_stats(is_admin=False, user_id=user_id, days_limit=days)
    by_model_type = await repo.get_model_type_stats(is_admin=False, user_id=user_id, days=days)
    tokens_in = sum(int(row.get("tokens_in", 0)) for row in daily)
    tokens_out = sum(int(row.get("tokens_out", 0)) for row in daily)
    total_cost = sum(
        ((int(row.get("tokens_in", 0)) * settings.ai_input_cost_per_1m) / 1_000_000)
        + ((int(row.get("tokens_out", 0)) * settings.ai_output_cost_per_1m) / 1_000_000)
        for row in daily
    )

    return {
        "user_id": user_id,
        "window_30d": {
            "days": days,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "total_tokens": tokens_in + tokens_out,
            "estimated_cost_usd": round(float(total_cost), 6),
            "daily": [
                {
                    "date": row["date"],
                    "tokens_in": int(row.get("tokens_in", 0)),
                    "tokens_out": int(row.get("tokens_out", 0)),
                }
                for row in daily
            ],
            "by_model_type": by_model_type,
        },
        "pricing": {
            "input_per_1m": settings.ai_input_cost_per_1m,
            "output_per_1m": settings.ai_output_cost_per_1m,
        },
    }
