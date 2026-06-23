"""
Base Redis Cache: Abstract base class with async/sync pattern for Redis caches.
Reduces ~300 lines of duplication across cache classes.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class BaseRedisCache(ABC):
    """
    Abstract base for async/sync Redis cache implementations.

    Subclasses must implement:
    - _prefix: str - Cache key prefix
    - _ttl: int - Time to live in seconds
    - _key(self, *args) -> str - Generate cache key
    - _serialize(self, data: Any) -> bytes - Serialize data for storage
    - _deserialize(self, data: bytes) -> Any - Deserialize data from storage
    """

    _prefix: str = "cache:"
    _ttl: int = 14400  # 4 hours default

    def __init__(self, client: Any) -> None:
        self._r = client
        self._is_async = hasattr(client, "pipeline") and callable(getattr(client, "pipeline", None))

    def _build_key(self, key: str) -> str:
        """Build full cache key with prefix."""
        return f"{self._prefix}{key}"

    async def get(self, key: str) -> Any | None:
        """Get cached value by key (Async)."""
        try:
            data = await self._r.get(self._build_key(key))
            return self._deserialize(data) if data else None
        except Exception as e:
            logger.debug("[%s] Get failed: %s", self.__class__.__name__, e)
            return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Set cache value (Async)."""
        try:
            expire = ttl if ttl is not None else self._ttl
            await self._r.set(self._build_key(key), self._serialize(value), ex=expire)
        except Exception as e:
            logger.debug("[%s] Set failed: %s", self.__class__.__name__, e)

    async def delete(self, key: str) -> None:
        """Delete cache entry (Async)."""
        try:
            await self._r.delete(self._build_key(key))
        except Exception as e:
            logger.debug("[%s] Delete failed: %s", self.__class__.__name__, e)

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache (Async)."""
        try:
            return await self._r.exists(self._build_key(key)) > 0
        except Exception:
            return False

    def get_sync(self, key: str) -> Any | None:
        """Get cached value by key (Sync)."""
        try:
            data = self._r.get(self._build_key(key))
            return self._deserialize(data) if data else None
        except Exception as e:
            logger.debug("[%s] Get sync failed: %s", self.__class__.__name__, e)
            return None

    def set_sync(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Set cache value (Sync)."""
        try:
            expire = ttl if ttl is not None else self._ttl
            self._r.set(self._build_key(key), self._serialize(value), ex=expire)
        except Exception as e:
            logger.debug("[%s] Set sync failed: %s", self.__class__.__name__, e)

    def delete_sync(self, key: str) -> None:
        """Delete cache entry (Sync)."""
        try:
            self._r.delete(self._build_key(key))
        except Exception as e:
            logger.debug("[%s] Delete sync failed: %s", self.__class__.__name__, e)

    def exists_sync(self, key: str) -> bool:
        """Check if key exists in cache (Sync)."""
        try:
            return self._r.exists(self._build_key(key)) > 0
        except Exception:
            return False

    @abstractmethod
    def _serialize(self, data: Any) -> bytes:
        """Serialize data to bytes for Redis storage."""
        pass

    @abstractmethod
    def _deserialize(self, data: bytes) -> Any:
        """Deserialize bytes from Redis to Python object."""
        pass
