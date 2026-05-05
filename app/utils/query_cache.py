"""
Query Embedding Cache: Redis-backed cache for query vectors.

Caches query embedding vectors in Redis so repeated questions (common during
demos and training sessions) skip local model inference entirely.

Key:   "qembed:{model_hash}:" + MD5(query_text) — model-aware for correctness
Value: JSON-serialized list[float] (embedding vector)
TTL:   1 hour — query patterns are stable within a working session

Usage:
    vector = query_cache.get(query_text)
    if vector is None:
        vector = embedding_service.embed(query_text)
        query_cache.set(query_text, vector)
"""

from __future__ import annotations

import hashlib
import logging
import msgpack
from typing import Any

logger = logging.getLogger(__name__)


class QueryEmbeddingCache:
    """Redis cache for query embedding vectors, keyed by model + query text."""

    PREFIX = "qembed:"
    TTL = 3600  # 1 hour in seconds

    def __init__(self, redis_client, model_name: str = "") -> None:
        self._r = redis_client
        self._model_hash = (
            hashlib.md5(model_name.encode("utf-8"), usedforsecurity=False).hexdigest()[:8] if model_name else "default"
        )

    def _key(self, text: str) -> str:
        return f"{self.PREFIX}{self._model_hash}:{hashlib.md5(text.encode('utf-8'), usedforsecurity=False).hexdigest()}"

    async def get(self, text: str) -> list[float] | None:
        """Return cached embedding vector or None if not found."""
        try:
            data = await self._r.get(self._key(text))
            return msgpack.unpackb(data) if data else None
        except Exception:
            return None

    async def set(self, text: str, vector: list[float]) -> None:
        """Store embedding vector in cache with TTL."""
        try:
            key = self._key(text)
            packed = msgpack.packb(vector)
            await self._r.set(key, packed, ex=self.TTL)
        except Exception:
            pass


class RagResultCache:
    """Redis cache for the final RagContext results, skipping the entire pipeline."""

    PREFIX = "rag_cache:"
    TTL = 1800  # 30 minutes

    def __init__(self, redis_client) -> None:
        self._r = redis_client

    def _key(self, query: str, document_ids: list[str] | None = None) -> str:
        # Key includes query and document filters to ensure isolation
        doc_hash = hashlib.md5(str(sorted(document_ids or [])).encode()).hexdigest()[:8]
        query_hash = hashlib.md5(query.encode()).hexdigest()
        return f"{self.PREFIX}{doc_hash}:{query_hash}"

    async def get(self, query: str, document_ids: list[str] | None = None) -> Any | None:
        """Retrieve cached RagContext if exists."""
        try:
            data = await self._r.get(self._key(query, document_ids))
            if data:
                import json

                return json.loads(data)
            return None
        except Exception:
            return None

    async def set(self, query: str, document_ids: list[str] | None = None, result: Any = None) -> None:
        """Cache the RagContext result."""
        if not result:
            return
        try:
            import json

            key = self._key(query, document_ids)
            await self._r.set(key, json.dumps(result), ex=self.TTL)
        except Exception:
            pass
