"""Reranker — dynamically loaded from SQLite runtime config."""

from app.adapters.reranker.tei_postprocessor import TEIRerankerPostprocessor
from app.adapters.reranker.nvidia_postprocessor import NvidiaRerankerPostprocessor
from app.core.config import settings


def build_reranker() -> TEIRerankerPostprocessor | NvidiaRerankerPostprocessor:
    return get_reranker()


def get_reranker(top_k: int | None = None) -> TEIRerankerPostprocessor | NvidiaRerankerPostprocessor:
    """Read the active reranker provider from RuntimeProviderManager and instantiate."""
    from app.modules.settings.runtime_manager import RuntimeProviderManager

    cfg = RuntimeProviderManager.get_instance().get_reranker_config()
    kwargs = {"top_k": top_k or settings.retrieval_rerank_top_k}

    if cfg and cfg.get("provider_name"):
        name = cfg["provider_name"]
        if name == "nvidia":
            kwargs["base_url"] = cfg.get("url", settings.nvidia_reranker_url)
            kwargs["model_name"] = cfg.get("model", settings.nvidia_reranker_model)
            kwargs["api_key"] = cfg.get("api_key") or settings.nvidia_api_key or "no-key"
            kwargs["timeout"] = settings.nvidia_reranker_timeout
            return NvidiaRerankerPostprocessor(**kwargs)
        elif name == "cohere":
            kwargs["base_url"] = cfg.get("url", settings.ai_reranker_url)
            return TEIRerankerPostprocessor(**kwargs)
        else:
            kwargs["base_url"] = cfg.get("url", settings.ai_reranker_url)
            return TEIRerankerPostprocessor(**kwargs)

    # Fallback: TEI local
    kwargs["base_url"] = settings.ai_reranker_url
    return TEIRerankerPostprocessor(**kwargs)


__all__ = ["TEIRerankerPostprocessor", "NvidiaRerankerPostprocessor", "build_reranker", "get_reranker"]
