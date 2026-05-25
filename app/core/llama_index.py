"""LlamaIndex global initialization: embed model, LLM, vector store."""

from __future__ import annotations

import asyncio
import threading
from functools import lru_cache

from llama_index.core import Settings
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openai_like import OpenAILike
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import AsyncQdrantClient, QdrantClient

from app.core.config import settings

_embed_async_semaphore = asyncio.Semaphore(1)
_embed_sync_semaphore = threading.Semaphore(1)


class SequentialOpenAIEmbedding(OpenAIEmbedding):
    """OpenAI-compatible embedding model that serializes embedding requests."""

    async def _aget_text_embedding(self, text: str):
        async with _embed_async_semaphore:
            return await super()._aget_text_embedding(text)

    async def _aget_query_embedding(self, query: str):
        async with _embed_async_semaphore:
            return await super()._aget_query_embedding(query)

    def _get_text_embedding(self, text: str):
        with _embed_sync_semaphore:
            return super()._get_text_embedding(text)

    def _get_query_embedding(self, query: str):
        with _embed_sync_semaphore:
            return super()._get_query_embedding(query)

    async def _aget_text_embeddings(self, texts: list[str]):
        async with _embed_async_semaphore:
            return await super()._aget_text_embeddings(texts)

    def _get_text_embeddings(self, texts: list[str]):
        with _embed_sync_semaphore:
            return super()._get_text_embeddings(texts)


def init_llama_index() -> None:
    """Initialize global LlamaIndex settings at application startup."""
    Settings.embed_model = SequentialOpenAIEmbedding(
        model_name=settings.embedding_hf_model,
        api_base=settings.embedding_api_base,
        api_key=settings.embedding_api_key or "no-key",
        embed_batch_size=settings.embedding_batch_size,
    )

    Settings.llm = OpenAILike(
        model=settings.ai_proxy_default_model or "default",
        api_base=f"{settings.ai_proxy_url}/v1",
        api_key=settings.ai_proxy_api_key or "no-key",
        is_chat_model=True,
        is_function_calling_model=True,
        context_window=128000,
        temperature=settings.ai_temperature,
        max_tokens=settings.ai_max_output_tokens,
        timeout=settings.ai_proxy_timeout,
    )

    from app.modules.settings.runtime_manager import RuntimeProviderManager

    RuntimeProviderManager.get_instance().init()


@lru_cache(maxsize=1)
def get_vector_store() -> QdrantVectorStore:
    """Return a singleton QdrantVectorStore.

    Note: current llama-index qdrant adapter initializes fastembed sparse encoders
    whenever enable_hybrid=True, so we pin sparse model to Qdrant/bm25 for
    lightweight and stable sparse generation.
    """
    return build_vector_store(enable_hybrid=settings.retrieval_hybrid_enabled)


def build_vector_store(enable_hybrid: bool) -> QdrantVectorStore:
    """Build a QdrantVectorStore with explicit hybrid mode."""
    client = QdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key or None,
        timeout=settings.qdrant_timeout,
    )
    aclient = AsyncQdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key or None,
        timeout=settings.qdrant_timeout,
    )
    return QdrantVectorStore(
        collection_name=settings.qdrant_collection,
        client=client,
        aclient=aclient,
        enable_hybrid=enable_hybrid,
        fastembed_sparse_model="Qdrant/bm25" if enable_hybrid else None,
    )
