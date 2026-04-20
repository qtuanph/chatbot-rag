"""
Query Embedding Cache: Redis-backed cache for query vectors.

Insight source: DoorDash "Applied Client-Side Caching to Improve Feature Store Performance by 70%"
Applied here: Cache local BAAI/bge-m3 query embedding vectors so repeated
questions (common during demos and training sessions) don't incur model cost.

Key:   "qembed:" + MD5(query_text)  — MD5 is collision-resistant enough for cache keys
Value: JSON-serialized List[float] (embedding vector)
TTL:   1 hour — query patterns are stable within a working session

Usage:
    vector = query_cache.get(query_text)
    if vector is None:
        vector = embedding_service.embed(query_text)
        query_cache.set(query_text, vector)
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class QueryEmbeddingCache:
    """Redis cache for query embedding vectors."""

    PREFIX = "qembed:"
    TTL = 3600  # 1 hour in seconds

    def __init__(self, redis_client) -> None:
        self._r = redis_client

    def _key(self, text: str) -> str:
        return self.PREFIX + hashlib.md5(text.encode("utf-8")).hexdigest()

    def get(self, text: str) -> Optional[list[float]]:
        """Return cached embedding vector or None if not found."""
        try:
            raw = self._r.get(self._key(text))
            if raw is None:
                return None
            vector = json.loads(raw)
            logger.debug("Query cache HIT (len=%d)", len(vector))
            return vector
        except Exception:
            logger.warning("Query cache GET failed", exc_info=True)
            return None  # cache miss is always safe

    def set(self, text: str, vector: list[float]) -> None:
        """Store embedding vector in cache with TTL."""
        try:
            self._r.setex(self._key(text), self.TTL, json.dumps(vector))
            logger.debug("Query cache SET (len=%d ttl=%ds)", len(vector), self.TTL)
        except Exception:
            logger.warning("Query cache SET failed", exc_info=True)
            # Never let cache write failure break the caller
