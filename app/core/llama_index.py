"""LlamaIndex global initialization: embed model, LLM, and dual Qdrant stores."""

from __future__ import annotations

import asyncio
import threading
from functools import lru_cache

from llama_index.core import Settings
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openai_like import OpenAILike
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import AsyncQdrantClient, QdrantClient
from qdrant_client.http import models as rest

from app.core.config import settings

_embed_async_semaphore = asyncio.Semaphore(8)
_embed_sync_semaphore = threading.Semaphore(8)


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
def get_qdrant_client() -> QdrantClient:
    return QdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key or None,
        timeout=settings.qdrant_timeout,
    )


@lru_cache(maxsize=1)
def get_async_qdrant_client() -> AsyncQdrantClient:
    return AsyncQdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key or None,
        timeout=settings.qdrant_timeout,
    )


def get_payload_indexes() -> list[dict[str, rest.PayloadSchemaType]]:
    return [
        {"field_name": "tenant_id", "field_schema": rest.PayloadSchemaType.KEYWORD},
        {"field_name": "document_id", "field_schema": rest.PayloadSchemaType.KEYWORD},
        {"field_name": "section_id", "field_schema": rest.PayloadSchemaType.KEYWORD},
        {"field_name": "section_code", "field_schema": rest.PayloadSchemaType.KEYWORD},
        {"field_name": "parent_section_id", "field_schema": rest.PayloadSchemaType.KEYWORD},
        {"field_name": "document_title", "field_schema": rest.PayloadSchemaType.TEXT},
        {"field_name": "heading", "field_schema": rest.PayloadSchemaType.TEXT},
        {"field_name": "breadcrumb_text", "field_schema": rest.PayloadSchemaType.TEXT},
        {"field_name": "level", "field_schema": rest.PayloadSchemaType.INTEGER},
        {"field_name": "order_index", "field_schema": rest.PayloadSchemaType.INTEGER},
        {"field_name": "node_kind", "field_schema": rest.PayloadSchemaType.KEYWORD},
    ]


def build_vector_store(*, collection_name: str, enable_hybrid: bool) -> QdrantVectorStore:
    """Build a Qdrant vector store for a specific collection."""
    return QdrantVectorStore(
        collection_name=collection_name,
        client=get_qdrant_client(),
        aclient=get_async_qdrant_client(),
        enable_hybrid=enable_hybrid,
        fastembed_sparse_model="Qdrant/bm25" if enable_hybrid else None,
        payload_indexes=get_payload_indexes(),
        flat_metadata=False,
    )


@lru_cache(maxsize=1)
def get_section_vector_store() -> QdrantVectorStore:
    return build_vector_store(
        collection_name=settings.qdrant_section_collection,
        enable_hybrid=settings.retrieval_hybrid_enabled,
    )


@lru_cache(maxsize=1)
def get_chunk_vector_store() -> QdrantVectorStore:
    return build_vector_store(
        collection_name=settings.qdrant_chunk_collection,
        enable_hybrid=settings.retrieval_hybrid_enabled,
    )


@lru_cache(maxsize=1)
def get_vector_store() -> QdrantVectorStore:
    """Backward-compatible alias for the chunk vector store."""
    return get_chunk_vector_store()


async def delete_document_vectors(document_id: str) -> None:
    """Delete vectors for one document from both section and chunk collections."""
    for vector_store in (get_section_vector_store(), get_chunk_vector_store()):
        try:
            await vector_store.adelete(ref_doc_id=document_id)
        except Exception:
            continue
