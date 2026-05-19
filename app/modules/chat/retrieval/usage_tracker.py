"""Fire-and-forget AI model usage tracker.

Dispatches Celery task or inline async call to log every model invocation.
"""

from __future__ import annotations

import logging

from app.adapters.ai.proxy_bridge import AIProxyBridge
from app.core.config import settings

logger = logging.getLogger(__name__)


def track_usage(
    provider: AIProxyBridge,
    endpoint: str,
    user_id: str | None = None,
    session_id: str | None = None,
    message_id: str | None = None,
) -> None:
    """Dispatch a fire-and-forget usage log for the given AIProxyBridge call.

    Reads last_usage from the provider (populated after chat/chat_stream).
    Falls back to Celery task dispatch; if Celery is unavailable, tries inline async.
    """
    usage = getattr(provider, "last_usage", {})
    if not usage or not usage.get("total_tokens"):
        return

    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    model_name = provider.model_name
    total_tokens = prompt_tokens + completion_tokens

    cost_usd = _estimate_cost(prompt_tokens, completion_tokens)

    try:
        from app.modules.chat.tasks.usage_tasks import log_model_usage_task

        log_model_usage_task.delay(
            model_name=model_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            endpoint=endpoint,
            cost_usd=cost_usd,
            user_id=user_id,
            session_id=session_id,
            message_id=message_id,
        )
        logger.debug("Usage tracked: %s | %d tokens | %s", endpoint, total_tokens, model_name)
    except Exception as e:
        logger.warning("Failed to dispatch usage tracking: %s", e)


def _estimate_cost(prompt_tokens: int, completion_tokens: int) -> float:
    """Estimate cost in USD based on configured rates."""
    input_rate = settings.ai_input_cost_per_1m
    output_rate = settings.ai_output_cost_per_1m
    return (prompt_tokens * input_rate + completion_tokens * output_rate) / 1_000_000
