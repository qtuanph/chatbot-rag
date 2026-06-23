"""
Query Embedding Cache: Redis-backed cache using BaseRedisCache.
Supports both Async (FastAPI) and Sync (Celery) clients.
"""

from __future__ import annotations

import hashlib
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
