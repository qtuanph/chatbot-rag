"""
Semantic Cache: Redis Vector Search for ultra-fast RAG result caching.
Supports both Async (FastAPI) and Sync (Celery) clients.
"""

import logging
import json
import numpy as np
from typing import Any
from redis.commands.search.field import VectorField, TextField
from redis.commands.search.index_definition import IndexDefinition, IndexType
from redis.commands.search.query import Query

from app.core.config import settings

logger = logging.getLogger(__name__)


class SemanticCache:
    """Handles semantic caching using Redis Vector Search (RediSearch)."""

    INDEX_NAME = "idx:semantic_cache"
    PREFIX = "cache:semantic:"

    @property
    def distance_threshold(self) -> float:
        return settings.retrieval_semantic_cache_threshold

    def __init__(self, vector_dim: int = 1024, client: Any | None = None) -> None:
        if client is None:
            raise ValueError("redis_client is required for SemanticCache")
        self.client = client
        self.vector_dim = vector_dim
        # Detect if the client is asynchronous
        self._is_async = hasattr(self.client, "pipeline") and callable(self.client.pipeline)

    # ── Async Methods ────────────────────────────────────────────────

    async def init_index(self) -> None:
        """Initialize the RediSearch index (Async)."""
        try:
            await self.client.ft(self.INDEX_NAME).info()
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
                await self.client.ft(self.INDEX_NAME).create_index(
                    fields=schema,
                    definition=IndexDefinition(prefix=[self.PREFIX], index_type=IndexType.HASH),
                )
                logger.info("Created semantic cache index (Async): %s", self.INDEX_NAME)
            except Exception as e:
                logger.warning("Failed to create semantic cache index: %s", e)

    async def get(self, query_vector: list[float]) -> dict[str, Any] | None:
        """Search for a similar cached result (Async)."""
        try:
            query_bytes = np.array(query_vector, dtype=np.float32).tobytes()
            q = (
                Query("*=>[KNN 1 @vector $vec AS score]")
                .sort_by("score")
                .return_fields("score", "result_json")
                .dialect(2)
            )
            res = await self.client.ft(self.INDEX_NAME).search(q, query_params={"vec": query_bytes})

            if res.total > 0:
                doc = res.docs[0]
                if float(doc.score) <= self.distance_threshold:
                    return json.loads(doc.result_json)
        except Exception as e:
            logger.error("Semantic cache retrieval failed (Async): %s", e)
        return None

    async def set(self, query_text: str, query_vector: list[float], result: dict[str, Any]) -> None:
        """Store a result in the semantic cache (Async)."""
        try:
            import hashlib

            key = f"{self.PREFIX}{hashlib.sha256(query_text.encode()).hexdigest()}"
            query_bytes = np.array(query_vector, dtype=np.float32).tobytes()
            await self.client.hset(
                key, mapping={"query_text": query_text, "vector": query_bytes, "result_json": json.dumps(result)}
            )
            await self.client.expire(key, 86400)
        except Exception as e:
            logger.error("Failed to store semantic cache (Async): %s", e)

    # ── Sync Methods (For Workers) ──────────────────────────────────

    def init_index_sync(self) -> None:
        """Initialize the RediSearch index (Sync)."""
        try:
            self.client.ft(self.INDEX_NAME).info()
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
                self.client.ft(self.INDEX_NAME).create_index(
                    fields=schema,
                    definition=IndexDefinition(prefix=[self.PREFIX], index_type=IndexType.HASH),
                )
                logger.info("Created semantic cache index (Sync): %s", self.INDEX_NAME)
            except Exception as e:
                logger.warning("Failed to create semantic cache index (Sync): %s", e)

    def get_sync(self, query_vector: list[float]) -> dict[str, Any] | None:
        """Search for a similar cached result (Sync)."""
        try:
            query_bytes = np.array(query_vector, dtype=np.float32).tobytes()
            q = (
                Query("*=>[KNN 1 @vector $vec AS score]")
                .sort_by("score")
                .return_fields("score", "result_json")
                .dialect(2)
            )
            res = self.client.ft(self.INDEX_NAME).search(q, query_params={"vec": query_bytes})

            if res.total > 0:
                doc = res.docs[0]
                if float(doc.score) <= self.distance_threshold:
                    return json.loads(doc.result_json)
        except Exception as e:
            logger.debug("Semantic cache retrieval failed (Sync): %s", e)
        return None

    def set_sync(self, query_text: str, query_vector: list[float], result: dict[str, Any]) -> None:
        """Store a result in the semantic cache (Sync)."""
        try:
            import hashlib

            key = f"{self.PREFIX}{hashlib.sha256(query_text.encode()).hexdigest()}"
            query_bytes = np.array(query_vector, dtype=np.float32).tobytes()
            self.client.hset(
                key, mapping={"query_text": query_text, "vector": query_bytes, "result_json": json.dumps(result)}
            )
            self.client.expire(key, 86400)
        except Exception as e:
            logger.error("Failed to store semantic cache (Sync): %s", e)
