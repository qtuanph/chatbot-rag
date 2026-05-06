"""
Distributed Lock: Redis-based Mutex for atomic operations.
Supports both Async (FastAPI) and Sync (Celery) contexts.
"""

import asyncio
import logging
import uuid
import time
from typing import Any

logger = logging.getLogger(__name__)

RELEASE_LUA = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""


class RedisLock:
    """Distributed lock using Redis SET NX."""

    def __init__(self, name: str, timeout_sec: int = 10, client: Any | None = None) -> None:
        if client is None:
            raise ValueError("redis_client is required for RedisLock")
        self.client = client
        self.key = f"lock:{name}"
        self.timeout = timeout_sec
        self.token = str(uuid.uuid4())
        self._locked = False
        self._is_async = hasattr(self.client, "pipeline") and callable(self.client.pipeline)

    # ── Async Interface ───────────────────────────────────────────

    async def __aenter__(self) -> "RedisLock":
        if await self.acquire():
            return self
        raise RuntimeError(f"Could not acquire lock (Async): {self.key}")

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.release()

    async def acquire(self, wait_sec: float = 5.0) -> bool:
        """Acquire lock with retry (Async)."""
        start_time = time.monotonic()
        while (time.monotonic() - start_time) < wait_sec:
            if await self.client.set(self.key, self.token, nx=True, ex=self.timeout):
                self._locked = True
                return True
            await asyncio.sleep(0.1)
        return False

    async def release(self) -> None:
        """Release lock (Async)."""
        if not self._locked:
            return
        try:
            await self.client.eval(RELEASE_LUA, 1, self.key, self.token)
        finally:
            self._locked = False

    # ── Sync Interface (For Workers) ──────────────────────────────

    def __enter__(self) -> "RedisLock":
        if self.acquire_sync():
            return self
        raise RuntimeError(f"Could not acquire lock (Sync): {self.key}")

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.release_sync()

    def acquire_sync(self, wait_sec: float = 5.0) -> bool:
        """Acquire lock with retry (Sync)."""
        start_time = time.monotonic()
        while (time.monotonic() - start_time) < wait_sec:
            if self.client.set(self.key, self.token, nx=True, ex=self.timeout):
                self._locked = True
                return True
            time.sleep(0.1)
        return False

    def release_sync(self) -> None:
        """Release lock (Sync)."""
        if not self._locked:
            return
        try:
            self.client.eval(RELEASE_LUA, 1, self.key, self.token)
        finally:
            self._locked = False
