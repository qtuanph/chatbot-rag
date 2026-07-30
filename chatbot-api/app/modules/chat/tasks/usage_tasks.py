"""Celery task for async AI model usage logging and conversation history persistence (fire-and-forget)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.core.celery_app import celery_app
from app.core.config import settings
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
    is_cache_hit: bool = False,
    cached_type: str | None = None,
) -> None:
    """Persist AI model usage record asynchronously via Celery."""
    try:
        asyncio.run(
            _log_usage_async(
                model_name=model_name,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                endpoint=endpoint,
                cost_micros_vnd=cost_micros_vnd,
                latency_ms=latency_ms,
                model_type=model_type,
                tenant_id=tenant_id,
                user_id=user_id,
                is_cache_hit=is_cache_hit,
                cached_type=cached_type,
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
    is_cache_hit: bool = False,
    cached_type: str | None = None,
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
            is_cache_hit=is_cache_hit,
            cached_type=cached_type,
        )


@celery_app.task(name="chat.save_conversation_turn", ignore_result=True, max_retries=2)
def save_conversation_turn_task(
    *,
    tenant_id: str,
    conversation_id: str,
    user_content: str,
    assistant_content: str,
    citations: list[dict[str, Any]],
    usage: dict[str, Any],
    model_name: str,
    is_cache_hit: bool = False,
    cached_type: str | None = None,
    no_answer: bool = False,
) -> None:
    """Fire-and-forget: persist conversation turn to PostgreSQL for admin audit."""
    try:
        asyncio.run(
            _save_conversation_turn_async(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                user_content=user_content,
                assistant_content=assistant_content,
                citations=citations,
                usage=usage,
                model_name=model_name,
                is_cache_hit=is_cache_hit,
                cached_type=cached_type,
                no_answer=no_answer,
            )
        )
    except Exception as e:
        logger.warning("Failed to save conversation turn: %s", e)


async def _save_conversation_turn_async(
    *,
    tenant_id: str,
    conversation_id: str,
    user_content: str,
    assistant_content: str,
    citations: list[dict[str, Any]],
    usage: dict[str, Any],
    model_name: str,
    is_cache_hit: bool = False,
    cached_type: str | None = None,
    no_answer: bool = False,
) -> None:
    from app.modules.chat.repositories.conversation_repository import ConversationRepository

    async with AsyncSessionLocal() as session:
        repo = ConversationRepository(session)
        conv_pk = await repo.upsert_conversation(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            retention_days=settings.chat_retention_days,
        )
        # User message
        await repo.add_message(
            conversation_pk=conv_pk,
            tenant_id=tenant_id,
            role="user",
            content=user_content,
        )
        # Assistant message
        await repo.add_message(
            conversation_pk=conv_pk,
            tenant_id=tenant_id,
            role="assistant",
            content=assistant_content,
            model_name=model_name,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            latency_ms=usage.get("latency_ms", 0.0),
            cost_micros_vnd=usage.get("cost_micros_vnd", 0),
            is_cache_hit=is_cache_hit,
            cached_type=cached_type,
            citations=citations or [],
            no_answer=no_answer,
        )

        if no_answer:
            try:
                from app.modules.chat.repositories.escalation_repository import EscalationRepository

                esc_repo = EscalationRepository(session)
                await esc_repo.create(
                    tenant_id=tenant_id,
                    question=user_content,
                    answer=assistant_content,
                    status="open",
                    conversation_id=conversation_id,
                )
            except Exception as esc_err:
                logger.warning("Failed to record escalation: %s", esc_err)

        await session.commit()
