"""
Query Embedding Cache & RAG Result Cache: Redis-backed caches using BaseRedisCache.
Supports both Async (FastAPI) and Sync (Celery) clients.
"""

from __future__ import annotations

import hashlib
import json
import logging
import msgpack
from typing import Any

from app.utils.cache.base import BaseRedisCache

logger = logging.getLogger(__name__)


class QueryEmbeddingCache(BaseRedisCache):
    """
    Redis cache for query embedding vectors.

    Key format: qembed:{model_hash}:{query_md5}
    TTL: 4 hours (14400 seconds)
    """

    PREFIX = "qembed:"
    TTL = 14400

    def __init__(self, redis_client: Any, model_name: str = "") -> None:
        super().__init__(redis_client)
        self._model_hash = (
            hashlib.md5(model_name.encode("utf-8"), usedforsecurity=False).hexdigest()[:8] if model_name else "default"
        )

    def _key(self, text: str) -> str:
        return f"{self._model_hash}:{hashlib.md5(text.encode('utf-8'), usedforsecurity=False).hexdigest()}"

    def _serialize(self, data: Any) -> bytes:
        return msgpack.packb(data)

    def _deserialize(self, data: bytes) -> Any:
        return msgpack.unpackb(data)

    async def get(self, text: str) -> list[float] | None:
        return await super().get(self._key(text))

    async def set(self, text: str, vector: list[float]) -> None:
        await super().set(self._key(text), vector)

    def get_sync(self, text: str) -> list[float] | None:
        return super().get_sync(self._key(text))

    def set_sync(self, text: str, vector: list[float]) -> None:
        super().set_sync(self._key(text), vector)


class RagResultCache(BaseRedisCache):
    """
    Redis cache for final RAG context.

    Key format: rag_cache:{doc_hash}:{query_hash}
    TTL: 4 hours (14400 seconds)
    """

    PREFIX = "rag_cache:"
    TTL = 14400

    def _key(self, query: str, document_ids: list[str] | None = None) -> str:
        doc_hash = hashlib.md5(str(sorted(document_ids or [])).encode()).hexdigest()[:8]
        query_hash = hashlib.md5(query.encode()).hexdigest()
        return f"{doc_hash}:{query_hash}"

    def _serialize(self, data: Any) -> bytes:
        return json.dumps(data).encode("utf-8")

    def _deserialize(self, data: bytes) -> Any:
        return json.loads(data.decode("utf-8"))

    async def get(self, query: str, document_ids: list[str] | None = None) -> Any | None:
        return await super().get(self._key(query, document_ids))

    async def set(self, query: str, document_ids: list[str] | None = None, result: Any = None) -> None:
        if not result:
            return
        await super().set(self._key(query, document_ids), result)

    def get_sync(self, query: str, document_ids: list[str] | None = None) -> Any | None:
        return super().get_sync(self._key(query, document_ids))

    def set_sync(self, query: str, document_ids: list[str] | None = None, result: Any = None) -> None:
        if not result:
            return
        super().set_sync(self._key(query, document_ids), result)
