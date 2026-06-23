"""
LLM Response Cache: Cache full LLM responses with 2-layer lookup.
Extends BaseRedisCache for async/sync pattern support.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from app.core.config import settings
from app.utils.cache.base import BaseRedisCache

logger = logging.getLogger(__name__)

LLM_CACHE_PREFIX = "llm_response:"
LLM_CACHE_TTL = getattr(settings, "llm_cache_ttl", 14400)


class LLMResponseCache(BaseRedisCache):
    """
    Cache LLM responses with 2-layer lookup:
    1. Exact match: hash(normalized_query + doc_ids)
    2. Metadata stored separately for potential future semantic lookup

    Only instantiates if LLM_CACHE_ENABLED is True.
    """

    PREFIX = LLM_CACHE_PREFIX
    TTL = LLM_CACHE_TTL

    def __init__(self, redis_client: Any, ttl: int | None = None) -> None:
        super().__init__(redis_client)
        self._ttl = ttl or LLM_CACHE_TTL

    def _exact_key(self, query: str, doc_ids: list[str] | None = None) -> str:
        """Generate exact match cache key."""
        doc_hash = hashlib.md5(str(sorted(doc_ids or [])).encode()).hexdigest()[:12]
        query_hash = hashlib.md5(query.encode()).hexdigest()[:24]
        return f"exact:{doc_hash}:{query_hash}"

    def _metadata_key(self, query: str, doc_ids: list[str] | None = None) -> str:
        """Generate key for storing normalized query metadata."""
        return self._exact_key(query, doc_ids).replace("exact:", "meta:")

    def _build_key(self, key: str) -> str:
        return f"{self.PREFIX}{key}"

    def _serialize(self, data: Any) -> bytes:
        return json.dumps(data, ensure_ascii=False).encode("utf-8")

    def _deserialize(self, data: bytes) -> Any:
        return json.loads(data.decode("utf-8"))

    async def get(self, query: str, doc_ids: list[str] | None = None) -> dict[str, Any] | None:
        """Get cached LLM response by exact match (Async)."""
        try:
            key = self._exact_key(query, doc_ids)
            data = await self._r.get(key)
            if data:
                logger.debug("[LLM-CACHE] Exact hit for query: %s", query[:50])
                return self._deserialize(data)
        except Exception as e:
            logger.warning("[LLM-CACHE] Get failed: %s", e)
        return None

    async def set(self, query: str, doc_ids: list[str] | None, response_data: dict[str, Any]) -> None:
        """Store LLM response in cache (Async)."""
        if not response_data:
            return
        try:
            key = self._exact_key(query, doc_ids)
            await self._r.set(key, self._serialize(response_data), ex=self._ttl)

            metadata_key = self._metadata_key(query, doc_ids)
            metadata = {
                "query": query,
                "doc_ids": sorted(doc_ids) if doc_ids else [],
                "cached_at": (await self._r.time())[0] if hasattr(self._r, "time") else None,
            }
            await self._r.set(metadata_key, self._serialize(metadata), ex=self._ttl)
            logger.debug("[LLM-CACHE] Stored response for query: %s", query[:50])
        except Exception as e:
            logger.warning("[LLM-CACHE] Set failed: %s", e)

    async def exists(self, query: str, doc_ids: list[str] | None = None) -> bool:
        """Check if response exists in cache (exact match, Async)."""
        try:
            key = self._exact_key(query, doc_ids)
            return await self._r.exists(key) > 0
        except Exception:
            return False

    async def delete(self, query: str, doc_ids: list[str] | None = None) -> None:
        """Delete cached response (Async)."""
        try:
            key = self._exact_key(query, doc_ids)
            metadata_key = self._metadata_key(query, doc_ids)
            await self._r.delete(key, metadata_key)
        except Exception as e:
            logger.warning("[LLM-CACHE] Delete failed: %s", e)

    async def invalidate_all(self) -> int:
        """Invalidate all LLM response cache entries. Returns count deleted."""
        try:
            pattern = f"{self.PREFIX}*"
            cursor = 0
            deleted = 0
            while True:
                cursor, keys = await self._r.scan(cursor, match=pattern, count=100)
                if keys:
                    await self._r.delete(*keys)
                    deleted += len(keys)
                if cursor == 0:
                    break
            logger.info("[LLM-CACHE] Invalidated %d entries", deleted)
            return deleted
        except Exception as e:
            logger.warning("[LLM-CACHE] Invalidate all failed: %s", e)
            return 0

    def get_sync(self, query: str, doc_ids: list[str] | None = None) -> dict[str, Any] | None:
        """Get cached response (Sync)."""
        try:
            key = self._exact_key(query, doc_ids)
            data = self._r.get(key)
            return self._deserialize(data) if data else None
        except Exception as e:
            logger.warning("[LLM-CACHE] Get sync failed: %s", e)
            return None

    def set_sync(self, query: str, doc_ids: list[str] | None, response_data: dict[str, Any]) -> None:
        """Store response (Sync)."""
        if not response_data:
            return
        try:
            key = self._exact_key(query, doc_ids)
            self._r.set(key, self._serialize(response_data), ex=self._ttl)
        except Exception as e:
            logger.warning("[LLM-CACHE] Set sync failed: %s", e)
