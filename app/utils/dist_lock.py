"""
Distributed Lock: Redis-based Mutex for atomic operations.
Prevents race conditions in high-concurrency environments.
"""

import asyncio
import logging
import uuid
from app.core.redis import redis_client

logger = logging.getLogger(__name__)


class RedisLock:
    """Simple distributed lock using Redis SET NX."""

    def __init__(self, name: str, timeout_sec: int = 10) -> None:
        self.client = redis_client
        self.key = f"lock:{name}"
        self.timeout = timeout_sec
        self.token = str(uuid.uuid4())
        self._locked = False

    async def __aenter__(self) -> "RedisLock":
        if await self.acquire():
            return self
        raise RuntimeError(f"Could not acquire lock: {self.key}")

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.release()

    async def acquire(self, wait_sec: float = 5.0) -> bool:
        """Acquire lock with retry logic."""
        start_time = asyncio.get_running_loop().time()
        while (asyncio.get_running_loop().time() - start_time) < wait_sec:
            if await self.client.set(self.key, self.token, nx=True, ex=self.timeout):
                self._locked = True
                return True
            await asyncio.sleep(0.1)
        return False

    async def release(self) -> None:
        """Release lock only if we own it (atomic via Lua)."""
        if not self._locked:
            return

        script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        try:
            await self.client.eval(script, 1, self.key, self.token)
        finally:
            self._locked = False
