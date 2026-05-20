"""Admin REST API — model listing and usage stats."""

from __future__ import annotations

import httpx
import logging
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_async_session
from app.modules.chat.repositories.usage_repository import UsageRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/models")
async def list_models():
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
):
    """Daily token usage breakdown for quota tracking."""
    repo = UsageRepository(session)
    daily = await repo.get_daily_stats(days=days)
    breakdown = await repo.get_endpoint_breakdown(days=days)
    return {"daily": daily, "endpoint_breakdown": breakdown, "days": days}
