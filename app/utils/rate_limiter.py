"""
Rate Limiter: Redis Lua-based Sliding Window implementation.
Supports both Async (FastAPI) and Sync (Celery) clients.
"""

import time
import logging
from typing import Any

logger = logging.getLogger(__name__)

LUA_SCRIPT = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])

redis.call('ZREMRANGEBYSCORE', key, 0, now - window)
local current_count = redis.call('ZCARD', key)

if current_count < limit then
    redis.call('ZADD', key, now, now)
    redis.call('EXPIRE', key, math.ceil(window / 1000))
    return 1
else
    return 0
end
"""


class RateLimiter:
    """Sliding window rate limiter using Redis ZSET."""

    def __init__(self, key_prefix: str = "rate_limit:", client: Any | None = None) -> None:
        if client is None:
            raise ValueError("redis_client is required for RateLimiter")
        self.client = client
        self.prefix = key_prefix
        # Register script once
        self._script = self.client.register_script(LUA_SCRIPT)

    async def is_allowed(self, identifier: str, limit: int, window_ms: int) -> bool:
        """Check if request is allowed (Async)."""
        key = f"{self.prefix}{identifier}"
        now_ms = int(time.time() * 1000)
        try:
            allowed = await self._script(keys=[key], args=[now_ms, window_ms, limit])
            return bool(allowed)
        except Exception as e:
            logger.error("Rate limiter failure (Async): %s", e)
            return True

    def is_allowed_sync(self, identifier: str, limit: int, window_ms: int) -> bool:
        """Check if request is allowed (Sync)."""
        key = f"{self.prefix}{identifier}"
        now_ms = int(time.time() * 1000)
        try:
            # redis-py's script object is callable and handles execution
            allowed = self._script(keys=[key], args=[now_ms, window_ms, limit])
            return bool(allowed)
        except Exception as e:
            logger.error("Rate limiter failure (Sync): %s", e)
            return True
