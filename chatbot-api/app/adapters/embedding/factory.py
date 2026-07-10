from __future__ import annotations

import logging
from typing import Any

from app.adapters.embedding.adapter import EmbeddingAdapter
from app.core.config import settings

logger = logging.getLogger(__name__)


def get_embedding_adapter(provider: dict[str, Any] | None = None) -> EmbeddingAdapter:
    """Create an ``EmbeddingAdapter`` from a provider dict.

    If ``provider`` is ``None`` the active embedding provider is loaded
    from the settings database.  Falls back to env-var defaults when
    no active provider exists.
    """
    if provider is None:
        provider = _load_active_provider()

    if provider:
        url = provider.get("url")
        if not url:
            raise ValueError("Embedding API base URL is not configured.")
        api_base = url.rstrip("/")
        api_key = _resolve_key(provider) or provider.get("api_key") or ""
        model = provider.get("model")
        if not model:
            raise ValueError("Embedding model name is not configured.")
        config = provider.get("config") or {}
    else:
        from app.modules.settings.repository import SettingsRepository

        repo = SettingsRepository()
        try:
            dmr = repo.get_builtin_provider("embedding", "dmr")
        finally:
            repo.close()

        if dmr:
            url = dmr.get("url")
            if not url:
                raise ValueError("Built-in DMR URL is not configured.")
            api_base = url.rstrip("/")
            api_key = dmr.get("api_key") or ""
            model = dmr.get("model")
            if not model:
                raise ValueError("Built-in DMR model is not configured.")
            config = dmr.get("config") or {}
        else:
            raise ValueError("No active embedding provider and built-in DMR is missing.")

    return EmbeddingAdapter(
        api_base=api_base,
        api_key=api_key,
        model=model,
        config=config,
    )


def _load_active_provider() -> dict[str, Any] | None:
    try:
        from app.modules.settings.repository import SettingsRepository

        repo = SettingsRepository()
        try:
            return repo.get_active_provider("embedding")
        finally:
            repo.close()
    except Exception as exc:
        logger.warning("Failed to load active embedding provider: %s", exc)
        return None


def _resolve_key(provider: dict[str, Any]) -> str | None:
    try:
        from app.modules.settings.repository import SettingsRepository

        repo = SettingsRepository()
        try:
            return repo.get_next_key(provider["id"])
        finally:
            repo.close()
    except Exception:
        return None
