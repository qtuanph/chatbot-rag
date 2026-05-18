"""Admin REST API — model listing from 9Router."""

from __future__ import annotations

import httpx
import logging
from fastapi import APIRouter

from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/models")
async def list_models():
    """List available models from 9Router's connected providers."""
    proxy_base = settings.ai_proxy_url.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{proxy_base}/v1/models")
            if resp.status_code == 200:
                data = resp.json()
                models = [{"id": m["id"], "provider": m.get("provider", "")} for m in data.get("data", [])]
                return {"models": models}
            return {"models": []}
    except Exception as e:
        logger.error("list_models error: %s", e)
        return {"models": []}
