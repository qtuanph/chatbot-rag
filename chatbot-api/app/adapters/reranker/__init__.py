"""Reranker — dynamically loaded from SQLite runtime config."""

import logging

from app.adapters.reranker.local_postprocessor import LocalRerankerPostprocessor
from app.adapters.reranker.nvidia_postprocessor import NvidiaRerankerPostprocessor
from app.core.config import settings

logger = logging.getLogger(__name__)


def build_reranker() -> LocalRerankerPostprocessor | NvidiaRerankerPostprocessor:
    return get_reranker()


def get_reranker(top_k: int | None = None) -> LocalRerankerPostprocessor | NvidiaRerankerPostprocessor:
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
            effective_key = runtime.get_reranker_api_key() or cfg.get("api_key") or "no-key"
            if effective_key == "no-key":
                logger.warning(
                    "Active reranker is NVIDIA but API key is missing. Falling back to local Docker reranker."
                )
                from app.modules.settings.repository import SettingsRepository

                repo = SettingsRepository()
                try:
                    dmr = repo.get_builtin_provider("reranker", "dmr")
                finally:
                    repo.close()
                kwargs["base_url"] = dmr.get("url") if dmr else "http://model-runner.docker.internal:12434"
                kwargs["embedding_url"] = f"{kwargs['base_url']}/engines/v1"
                kwargs["model_name"] = dmr.get("model") if dmr else None
                return LocalRerankerPostprocessor(**kwargs)
            kwargs["base_url"] = cfg.get("url") or "https://ai.api.nvidia.com/v1/retrieval/nvidia/llama-nemotron-rerank-1b-v2/reranking"
            kwargs["model_name"] = cfg.get("model") or "nvidia/llama-nemotron-rerank-1b-v2"
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
            from app.modules.settings.repository import SettingsRepository

            repo = SettingsRepository()
            try:
                dmr = repo.get_builtin_provider("reranker", "dmr")
            finally:
                repo.close()
            kwargs["base_url"] = cfg.get("url") or (dmr.get("url") if dmr else settings.ai_reranker_url)
            kwargs["model_name"] = cfg.get("model") or (dmr.get("model") if dmr else None)
            return LocalRerankerPostprocessor(**kwargs)

    # Fallback: local Docker-compatible reranker endpoint
    from app.modules.settings.repository import SettingsRepository

    repo = SettingsRepository()
    try:
        dmr = repo.get_builtin_provider("reranker", "dmr")
    finally:
        repo.close()
    kwargs["base_url"] = dmr.get("url") if dmr else settings.ai_reranker_url
    kwargs["model_name"] = dmr.get("model") if dmr else None
    return LocalRerankerPostprocessor(**kwargs)


__all__ = [
    "LocalRerankerPostprocessor",
    "NvidiaRerankerPostprocessor",
    "CohereRerankerPostprocessor",
    "build_reranker",
    "get_reranker",
]
