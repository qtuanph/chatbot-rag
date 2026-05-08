"""
Semantic Cache: Redis Vector Search for ultra-fast RAG result caching.
Supports both Async (FastAPI) and Sync (Celery) clients.

Note: This cache uses RediSearch vector index with KNN queries.
It has different semantics than simple key-value caches,
so it extends BaseRedisCache but overrides most methods.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

import numpy as np
from redis.commands.search.field import TextField, VectorField
from redis.commands.search.index_definition import IndexDefinition, IndexType
from redis.commands.search.query import Query

from app.core.config import settings
from app.utils.cache.base import BaseRedisCache

logger = logging.getLogger(__name__)


class SemanticCache(BaseRedisCache):
    """
    Handles semantic caching using Redis Vector Search (RediSearch).

    Note: Despite extending BaseRedisCache, this class overrides most methods
    due to different storage semantics (RediSearch index vs simple key-value).
    The inheritance is mainly for _is_async detection and potential future sharing.
    """

    INDEX_NAME = "idx:semantic_cache"
    PREFIX = "cache:semantic:"
    TTL = 86400  # 24 hours

    @property
    def distance_threshold(self) -> float:
        return settings.retrieval_semantic_cache_threshold

    def __init__(self, vector_dim: int = 1024, client: Any | None = None) -> None:
        if client is None:
            raise ValueError("redis_client is required for SemanticCache")
        super().__init__(client)
        self._r = client
        self.vector_dim = vector_dim
        self._is_async = hasattr(self._r, "pipeline") and callable(getattr(self._r, "pipeline", None))

    def _build_key(self, key: str) -> str:
        return f"{self.PREFIX}{hashlib.sha256(key.encode()).hexdigest()}"

    def _serialize(self, data: Any) -> bytes:
        return json.dumps(data).encode("utf-8")

    def _deserialize(self, data: bytes) -> Any:
        return json.loads(data.decode("utf-8"))

    async def init_index(self) -> None:
        """Initialize the RediSearch index (Async)."""
        try:
            await self._r.ft(self.INDEX_NAME).info()
        except Exception:
            schema = (
                TextField("query_text"),
                VectorField(
                    "vector",
                    "HNSW",
                    {"TYPE": "FLOAT32", "DIM": self.vector_dim, "DISTANCE_METRIC": "COSINE"},
                ),
                TextField("result_json"),
            )
            try:
                await self._r.ft(self.INDEX_NAME).create_index(
                    fields=schema,
                    definition=IndexDefinition(prefix=[self.PREFIX], index_type=IndexType.HASH),
                )
                logger.info("Created semantic cache index (Async): %s", self.INDEX_NAME)
            except Exception as e:
                logger.warning("Failed to create semantic cache index: %s", e)

    async def get(self, query_vector: list[float]) -> dict[str, Any] | None:
        """Search for a similar cached result (Async). TTL is refreshed on hit."""
        try:
            query_bytes = np.array(query_vector, dtype=np.float32).tobytes()
            q = (
                Query("*=>[KNN 1 @vector $vec AS score]")
                .sort_by("score")
                .return_fields("score", "result_json", "query_text")
                .dialect(2)
            )
            res = await self._r.ft(self.INDEX_NAME).search(q, query_params={"vec": query_bytes})

            if res.total > 0:
                doc = res.docs[0]
                if float(doc.score) <= self.distance_threshold:
                    key = self._build_key(doc.query_text)
                    await self._r.expire(key, 86400)
                    return json.loads(doc.result_json)
        except Exception as e:
            logger.error("Semantic cache retrieval failed (Async): %s", e)
        return None

    async def set(self, query_text: str, query_vector: list[float], result: dict[str, Any]) -> None:
        """Store a result in the semantic cache (Async)."""
        try:
            key = self._build_key(query_text)
            query_bytes = np.array(query_vector, dtype=np.float32).tobytes()
            await self._r.hset(
                key, mapping={"query_text": query_text, "vector": query_bytes, "result_json": json.dumps(result)}
            )
            await self._r.expire(key, 86400)
        except Exception as e:
            logger.error("Failed to store semantic cache (Async): %s", e)

    def init_index_sync(self) -> None:
        """Initialize the RediSearch index (Sync)."""
        try:
            self._r.ft(self.INDEX_NAME).info()
        except Exception:
            schema = (
                TextField("query_text"),
                VectorField(
                    "vector",
                    "HNSW",
                    {"TYPE": "FLOAT32", "DIM": self.vector_dim, "DISTANCE_METRIC": "COSINE"},
                ),
                TextField("result_json"),
            )
            try:
                self._r.ft(self.INDEX_NAME).create_index(
                    fields=schema,
                    definition=IndexDefinition(prefix=[self.PREFIX], index_type=IndexType.HASH),
                )
                logger.info("Created semantic cache index (Sync): %s", self.INDEX_NAME)
            except Exception as e:
                logger.warning("Failed to create semantic cache index (Sync): %s", e)

    def get_sync(self, query_vector: list[float]) -> dict[str, Any] | None:
        """Search for a similar cached result (Sync). TTL is refreshed on hit."""
        try:
            query_bytes = np.array(query_vector, dtype=np.float32).tobytes()
            q = (
                Query("*=>[KNN 1 @vector $vec AS score]")
                .sort_by("score")
                .return_fields("score", "result_json", "query_text")
                .dialect(2)
            )
            res = self._r.ft(self.INDEX_NAME).search(q, query_params={"vec": query_bytes})

            if res.total > 0:
                doc = res.docs[0]
                if float(doc.score) <= self.distance_threshold:
                    key = self._build_key(doc.query_text)
                    self._r.expire(key, 86400)
                    return json.loads(doc.result_json)
        except Exception as e:
            logger.debug("Semantic cache retrieval failed (Sync): %s", e)
        return None

    def set_sync(self, query_text: str, query_vector: list[float], result: dict[str, Any]) -> None:
        """Store a result in the semantic cache (Sync)."""
        try:
            key = self._build_key(query_text)
            query_bytes = np.array(query_vector, dtype=np.float32).tobytes()
            self._r.hset(
                key, mapping={"query_text": query_text, "vector": query_bytes, "result_json": json.dumps(result)}
            )
            self._r.expire(key, 86400)
        except Exception as e:
            logger.error("Failed to store semantic cache (Sync): %s", e)
