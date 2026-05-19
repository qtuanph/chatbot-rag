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
    cost_usd: float = 0.0,
    user_id: str | None = None,
    session_id: str | None = None,
    message_id: str | None = None,
) -> None:
    """Persist AI model usage record asynchronously via Celery."""
    try:
        asyncio.run(
            _log_usage_async(
                model_name, prompt_tokens, completion_tokens, endpoint, cost_usd, user_id, session_id, message_id
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
    cost_usd: float,
    user_id: str | None,
    session_id: str | None,
    message_id: str | None,
) -> None:
    from app.modules.chat.repositories.usage_repository import UsageRepository

    async with AsyncSessionLocal() as session:
        repo = UsageRepository(session)
        await repo.log_usage(
            model_name=model_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            endpoint=endpoint,
            cost_usd=cost_usd,
            user_id=user_id,
            session_id=session_id,
            message_id=message_id,
        )
