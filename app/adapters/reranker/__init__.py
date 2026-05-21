"""Reranker adapter — switchable backend (TEI local | NVIDIA API)."""

from app.core.config import settings
from app.adapters.reranker.reranker import TEIReranker, get_reranker as get_tei_reranker
from app.adapters.reranker.nvidia_reranker import NvidiaReranker

_shared_instance = None


def build_reranker():
    """Factory: return reranker instance based on RERANKER_BACKEND env var."""
    global _shared_instance
    if _shared_instance is not None:
        return _shared_instance

    backend = settings.reranker_backend.lower()
    if backend == "nvidia":
        if not settings.nvidia_api_key:
            raise ValueError("NVIDIA_API_KEY must be set when RERANKER_BACKEND=nvidia")
        _shared_instance = NvidiaReranker()
    else:
        _shared_instance = get_tei_reranker()

    return _shared_instance


__all__ = ["TEIReranker", "NvidiaReranker", "build_reranker"]
