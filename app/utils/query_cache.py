"""
Query Embedding Cache: Redis-backed cache for query vectors.
Supports both Async (FastAPI) and Sync (Celery) clients.
"""

from __future__ import annotations
import hashlib
import logging
import msgpack
import json
from typing import Any

logger = logging.getLogger(__name__)


class QueryEmbeddingCache:
    """Redis cache for query embedding vectors (Hybrid Sync/Async)."""

    PREFIX = "qembed:"
    TTL = 3600  # 1 hour

    def __init__(self, redis_client: Any, model_name: str = "") -> None:
        self._r = redis_client
        self._model_hash = (
            hashlib.md5(model_name.encode("utf-8"), usedforsecurity=False).hexdigest()[:8] if model_name else "default"
        )

    def _key(self, text: str) -> str:
        return f"{self.PREFIX}{self._model_hash}:{hashlib.md5(text.encode('utf-8'), usedforsecurity=False).hexdigest()}"

    # ── Async Methods ────────────────────────────────────────────────

    async def get(self, text: str) -> list[float] | None:
        """Get (Async)."""
        try:
            data = await self._r.get(self._key(text))
            return msgpack.unpackb(data) if data else None
        except Exception:
            return None

    async def set(self, text: str, vector: list[float]) -> None:
        """Set (Async)."""
        try:
            await self._r.set(self._key(text), msgpack.packb(vector), ex=self.TTL)
        except Exception:
            pass

    # ── Sync Methods (For Workers) ──────────────────────────────────

    def get_sync(self, text: str) -> list[float] | None:
        """Get (Sync)."""
        try:
            data = self._r.get(self._key(text))
            return msgpack.unpackb(data) if data else None
        except Exception:
            return None

    def set_sync(self, text: str, vector: list[float]) -> None:
        """Set (Sync)."""
        try:
            self._r.set(self._key(text), msgpack.packb(vector), ex=self.TTL)
        except Exception:
            pass


class RagResultCache:
    """Redis cache for final RAG context (Hybrid Sync/Async)."""

    PREFIX = "rag_cache:"
    TTL = 1800  # 30 minutes

    def __init__(self, redis_client: Any) -> None:
        self._r = redis_client

    def _key(self, query: str, document_ids: list[str] | None = None) -> str:
        doc_hash = hashlib.md5(str(sorted(document_ids or [])).encode()).hexdigest()[:8]
        query_hash = hashlib.md5(query.encode()).hexdigest()
        return f"{self.PREFIX}{doc_hash}:{query_hash}"

    # ── Async Methods ────────────────────────────────────────────────

    async def get(self, query: str, document_ids: list[str] | None = None) -> Any | None:
        """Get (Async)."""
        try:
            data = await self._r.get(self._key(query, document_ids))
            return json.loads(data) if data else None
        except Exception:
            return None

    async def set(self, query: str, document_ids: list[str] | None = None, result: Any = None) -> None:
        """Set (Async)."""
        if not result:
            return
        try:
            await self._r.set(self._key(query, document_ids), json.dumps(result), ex=self.TTL)
        except Exception:
            pass

    # ── Sync Methods (For Workers) ──────────────────────────────────

    def get_sync(self, query: str, document_ids: list[str] | None = None) -> Any | None:
        """Get (Sync)."""
        try:
            data = self._r.get(self._key(query, document_ids))
            return json.loads(data) if data else None
        except Exception:
            return None

    def set_sync(self, query: str, document_ids: list[str] | None = None, result: Any = None) -> None:
        """Set (Sync)."""
        if not result:
            return
        try:
            self._r.set(self._key(query, document_ids), json.dumps(result), ex=self.TTL)
        except Exception:
            pass
