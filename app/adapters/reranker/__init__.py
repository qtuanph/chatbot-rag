"""Reranker — dynamically loaded from SQLite runtime config."""

import logging

from app.adapters.reranker.tei_postprocessor import TEIRerankerPostprocessor
from app.adapters.reranker.nvidia_postprocessor import NvidiaRerankerPostprocessor
from app.core.config import settings

logger = logging.getLogger(__name__)


def build_reranker() -> TEIRerankerPostprocessor | NvidiaRerankerPostprocessor:
    return get_reranker()


def get_reranker(top_k: int | None = None) -> TEIRerankerPostprocessor | NvidiaRerankerPostprocessor:
    """Read the active reranker provider from RuntimeProviderManager and instantiate."""
    from app.modules.settings.runtime_manager import RuntimeProviderManager

    runtime = RuntimeProviderManager.get_instance()
    cfg = runtime.get_reranker_config()
    # Guard against stale/uninitialized in-process cache after container restart.
    # SQLite may already contain active provider, but runtime cache can still be None.
    if cfg is None:
        runtime.reload()
        cfg = runtime.get_reranker_config()
    kwargs = {"top_k": top_k or settings.retrieval_rerank_top_k}

    if cfg and cfg.get("provider_name"):
        name = cfg["provider_name"]
        if name == "nvidia":
            effective_key = runtime.get_reranker_api_key() or cfg.get("api_key") or settings.nvidia_api_key or "no-key"
            if effective_key == "no-key":
                logger.warning("Active reranker is NVIDIA but API key is missing. Falling back to local Docker reranker.")
                kwargs["base_url"] = settings.ai_reranker_url
                return TEIRerankerPostprocessor(**kwargs)
            kwargs["base_url"] = cfg.get("url", settings.nvidia_reranker_url)
            kwargs["model_name"] = cfg.get("model", settings.nvidia_reranker_model)
            kwargs["api_key"] = effective_key
            kwargs["timeout"] = settings.nvidia_reranker_timeout
            return NvidiaRerankerPostprocessor(**kwargs)
        elif name == "cohere":
            effective_key = runtime.get_reranker_api_key() or cfg.get("api_key") or "no-key"
            kwargs["base_url"] = cfg.get("url", "https://api.cohere.com")
            kwargs["model_name"] = cfg.get("model", "rerank-multilingual-v3.0")
            kwargs["api_key"] = effective_key
            kwargs["timeout"] = settings.ai_reranker_timeout
            from app.adapters.reranker.cohere_postprocessor import CohereRerankerPostprocessor

            return CohereRerankerPostprocessor(**kwargs)
        else:
            kwargs["base_url"] = cfg.get("url", settings.ai_reranker_url)
            return TEIRerankerPostprocessor(**kwargs)

    # Fallback: local Docker-compatible reranker endpoint
    kwargs["base_url"] = settings.ai_reranker_url
    return TEIRerankerPostprocessor(**kwargs)


__all__ = [
    "TEIRerankerPostprocessor",
    "NvidiaRerankerPostprocessor",
    "CohereRerankerPostprocessor",
    "build_reranker",
    "get_reranker",
]
