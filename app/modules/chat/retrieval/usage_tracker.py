"""Fire-and-forget AI model usage tracker.

Dispatches Celery task to log every model invocation.
No longer tied to AIProxyBridge — accepts stats directly.
"""

from __future__ import annotations

import logging

from llama_index.core import Settings as LlamaSettings
from app.utils.money import compute_cost_micros_vnd

logger = logging.getLogger(__name__)


def track_usage(
    provider: object,
    endpoint: str,
    tenant_id: str | None = None,
    user_id: str | None = None,
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
    model_name = (
        usage.get("model")
        or usage.get("model_name")
        or getattr(provider, "model_name", None)
        or getattr(getattr(LlamaSettings, "llm", None), "model", None)
        or "unknown"
    )
    total_tokens = prompt_tokens + completion_tokens

    cost_micros_vnd = compute_cost_micros_vnd(prompt_tokens, completion_tokens)

    try:
        from app.modules.chat.tasks.usage_tasks import log_model_usage_task

        log_model_usage_task.delay(
            model_name=model_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            endpoint=endpoint,
            cost_micros_vnd=cost_micros_vnd,
            tenant_id=tenant_id,
            user_id=user_id,
        )
        logger.debug("Usage tracked: %s | %d tokens | %s", endpoint, total_tokens, model_name)
    except Exception as e:
        logger.warning("Failed to dispatch usage tracking: %s", e)
