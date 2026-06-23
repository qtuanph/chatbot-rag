"""Celery task for async AI model usage logging (fire-and-forget)."""

from __future__ import annotations

import asyncio
import logging

from app.core.celery_app import celery_app
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)


@celery_app.task(name="log_model_usage_task", bind=True, max_retries=3, default_retry_delay=5)
def log_model_usage_task(
    self,
    model_name: str,
    prompt_tokens: int,
    completion_tokens: int,
    endpoint: str,
    cost_micros_vnd: int = 0,
    latency_ms: float = 0.0,
    model_type: str = "llm",
    tenant_id: str | None = None,
    user_id: str | None = None,
) -> None:
    """Persist AI model usage record asynchronously via Celery."""
    try:
        asyncio.run(
            _log_usage_async(
                model_name,
                prompt_tokens,
                completion_tokens,
                endpoint,
                cost_micros_vnd,
                latency_ms,
                model_type,
                tenant_id,
                user_id,
            )
        )
    except Exception as e:
        logger.error("Failed to log model usage: %s", e, exc_info=True)
        raise self.retry(exc=e)


async def _log_usage_async(
    model_name: str,
    prompt_tokens: int,
    completion_tokens: int,
    endpoint: str,
    cost_micros_vnd: int,
    latency_ms: float,
    model_type: str,
    tenant_id: str | None,
    user_id: str | None,
) -> None:
    from app.modules.chat.repositories.usage_repository import UsageRepository

    async with AsyncSessionLocal() as session:
        repo = UsageRepository(session)
        await repo.log_usage(
            model_name=model_name,
            model_type=model_type,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            endpoint=endpoint,
            cost_micros_vnd=cost_micros_vnd,
            latency_ms=latency_ms,
            tenant_id=tenant_id,
            user_id=user_id,
        )
