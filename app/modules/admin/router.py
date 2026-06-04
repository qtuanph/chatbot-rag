"""Admin REST API — model listing and usage stats."""

from __future__ import annotations

import httpx
import logging
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_async_session
from app.modules.analytics.repository import AnalyticsRepository
from app.modules.analytics.service import AnalyticsService
from app.modules.chat.repositories.usage_repository import UsageRepository
from app.api.deps import require_admin, AuthContext
from app.utils.money import build_money_payload

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
    normalized_daily = []
    for row in daily:
        item = dict(row)
        item.update(build_money_payload(row["cost_micros_vnd"]))
        normalized_daily.append(item)
    return {"daily": normalized_daily, "endpoint_breakdown": breakdown, "days": days}


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
    normalized = []
    for item in items:
        enriched = dict(item)
        enriched.update(build_money_payload(item["cost_micros_vnd"]))
        normalized.append(enriched)
    return {"items": normalized}


@router.get("/users/{user_id}/usage")
async def get_user_usage_detail(
    user_id: str,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_admin),
):
    """Usage detail for a specific user in last 30 days with 3 model types."""
    repo = AnalyticsRepository(session)
    days = 30
    daily = await repo.get_daily_stats(is_platform_admin=False, user_id=user_id, tenant_id=None, days_limit=days)
    by_model_type = await repo.get_model_type_stats(is_platform_admin=False, user_id=user_id, tenant_id=None, days=days)
    tokens_in = sum(int(row.get("tokens_in", 0)) for row in daily)
    tokens_out = sum(int(row.get("tokens_out", 0)) for row in daily)
    total_cost_micros = sum(int(row.get("cost_micros_vnd", 0)) for row in by_model_type.values())

    result = {
        "user_id": user_id,
        "window_30d": {
            "days": days,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "total_tokens": tokens_in + tokens_out,
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
            "currency_code": settings.billing_currency_code,
            "input_price_vnd_per_1m": settings.ai_input_price_vnd_per_1m,
            "output_price_vnd_per_1m": settings.ai_output_price_vnd_per_1m,
        },
    }
    result["window_30d"].update(build_money_payload(total_cost_micros))
    return result


@router.get("/tenants/usage")
async def get_tenants_usage(
    days: int = Query(30, ge=1, le=365),
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_admin),
):
    """Per-tenant usage summary in the selected time window, sorted by spend descending."""
    service = AnalyticsService(AnalyticsRepository(session))
    return await service.get_tenant_usage_summary(days=days)
