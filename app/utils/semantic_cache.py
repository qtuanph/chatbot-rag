"""
Semantic Cache: Redis Vector Search for ultra-fast RAG result caching.
Skips embedding + vector store + rerank for highly similar repeat questions.
"""

import logging
import json
import numpy as np
from typing import Any
from redis.commands.search.field import VectorField, TextField
from redis.commands.search.indexDefinition import IndexDefinition, IndexType
from redis.commands.search.query import Query

from app.api.deps import redis_client
from app.core.config import settings

logger = logging.getLogger(__name__)

class SemanticCache:
    """Handles semantic caching using Redis Vector Search (RediSearch)."""

    INDEX_NAME = "idx:semantic_cache"
    PREFIX = "cache:semantic:"
    @property
    def distance_threshold(self) -> float:
        return settings.retrieval_semantic_cache_threshold

    def __init__(self, vector_dim: int = 1024) -> None:
        self.client = redis_client
        self.vector_dim = vector_dim

    async def init_index(self) -> None:
        """Initialize the RediSearch index for vector similarity search."""
        try:
            # Check if index exists
            await self.client.ft(self.INDEX_NAME).info()
            logger.debug("Semantic cache index already exists")
        except Exception:
            # Create index
            schema = (
                TextField("query_text"),
                VectorField(
                    "vector",
                    "HNSW",
                    {
                        "TYPE": "FLOAT32",
                        "DIM": self.vector_dim,
                        "DISTANCE_METRIC": "COSINE",
                    },
                ),
            )
            try:
                await self.client.ft(self.INDEX_NAME).create_index(
                    fields=schema,
                    definition=IndexDefinition(prefix=[self.PREFIX], index_type=IndexType.HASH),
                )
                logger.info("Created semantic cache index: %s", self.INDEX_NAME)
            except Exception as e:
                logger.warning("Failed to create semantic cache index: %s", e)

    async def get(self, query_vector: list[float]) -> dict[str, Any] | None:
        """
        Search for a similar cached result.
        Returns cached data if distance < DISTANCE_THRESHOLD.
        """
        try:
            # Convert vector to bytes
            query_bytes = np.array(query_vector, dtype=np.float32).tobytes()
            
            # Prepare search query: find nearest neighbor with distance limit
            q = (
                Query(f"*=>[KNN 1 @vector $vec AS score]")
                .sort_by("score")
                .return_fields("score", "result_json")
                .dialect(2)
            )
            
            res = await self.client.ft(self.INDEX_NAME).search(
                q, query_params={"vec": query_bytes}
            )
            
            if res.total > 0:
                doc = res.docs[0]
                score = float(doc.score)
                
                # In COSINE distance, score is 1 - similarity. 
                # So distance 0.02 means 98% similarity.
                if score <= self.distance_threshold:
                    logger.info("[CACHE] Semantic Hit! Score: %.4f", score)
                    return json.loads(doc.result_json)
                
                logger.debug("[CACHE] Semantic Miss. Best score: %.4f", score)
        except Exception as e:
            logger.error("Semantic cache retrieval failed: %s", e)
        
        return None

    async def set(self, query_text: str, query_vector: list[float], result: dict[str, Any]) -> None:
        """Store a result in the semantic cache."""
        try:
            key = f"{self.PREFIX}{hash(query_text)}"
            query_bytes = np.array(query_vector, dtype=np.float32).tobytes()
            
            await self.client.hset(
                key,
                mapping={
                    "query_text": query_text,
                    "vector": query_bytes,
                    "result_json": json.dumps(result),
                },
            )
            # Expire cache after a while (e.g., 24h)
            await self.client.expire(key, 86400)
            
        except Exception as e:
            logger.error("Failed to store semantic cache: %s", e)
