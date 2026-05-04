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
import json
import logging

logger = logging.getLogger(__name__)


class QueryEmbeddingCache:
    """Redis cache for query embedding vectors, keyed by model + query text."""

    PREFIX = "qembed:"
    TTL = 3600  # 1 hour in seconds

    def __init__(self, redis_client, model_name: str = "") -> None:
        self._r = redis_client
        # Include model name hash in cache key so swapping models
        # never serves stale vectors from a different model.
        self._model_hash = (
            hashlib.md5(model_name.encode("utf-8"), usedforsecurity=False).hexdigest()[:8] if model_name else "default"
        )

    def _key(self, text: str) -> str:
        return f"{self.PREFIX}{self._model_hash}:{hashlib.md5(text.encode('utf-8'), usedforsecurity=False).hexdigest()}"

    def get(self, text: str) -> list[float | None]:
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
