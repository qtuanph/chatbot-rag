"""Fire-and-forget AI model usage tracker.

Dispatches Celery task to log every model invocation.
No longer tied to AIProxyBridge — accepts stats directly.
"""

from __future__ import annotations

import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


def track_usage(
    provider: object,
    endpoint: str,
    user_id: str | None = None,
    session_id: str | None = None,
    message_id: str | None = None,
) -> None:
    """Dispatch a fire-and-forget usage log.

    Reads last_usage from the provider (populated after chat/chat_stream).
    Falls back to Celery task dispatch.
    """
    usage = getattr(provider, "last_usage", {})
    if not usage or not usage.get("total_tokens"):
        return

    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    model_name = usage.get("model", "unknown")
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
    input_rate = settings.ai_input_cost_per_1m
    output_rate = settings.ai_output_cost_per_1m
    return (prompt_tokens * input_rate + completion_tokens * output_rate) / 1_000_000
