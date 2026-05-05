"""
Rate Limiter: Redis Lua-based Sliding Window implementation.
High-precision, atomic throttling for 200+ CCU environment.
"""

import time
import logging
from app.core.redis import redis_client

logger = logging.getLogger(__name__)

# Lua script for atomic sliding window rate limiting
LUA_SCRIPT = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])

-- Remove old entries
redis.call('ZREMRANGEBYSCORE', key, 0, now - window)

-- Count current entries
local current_count = redis.call('ZCARD', key)

if current_count < limit then
    -- Add current entry
    redis.call('ZADD', key, now, now)
    redis.call('EXPIRE', key, math.ceil(window / 1000))
    return 1
else
    return 0
end
"""


class RateLimiter:
    """Sliding window rate limiter using Redis ZSET."""

    def __init__(self, key_prefix: str = "rate_limit:") -> None:
        self.client = redis_client
        self.prefix = key_prefix
        self._script = self.client.register_script(LUA_SCRIPT)

    async def is_allowed(self, identifier: str, limit: int, window_ms: int) -> bool:
        """
        Check if request is allowed for the given identifier.
        Returns True if allowed, False otherwise.
        """
        key = f"{self.prefix}{identifier}"
        now_ms = int(time.time() * 1000)

        try:
            allowed = await self._script(keys=[key], args=[now_ms, window_ms, limit])
            return bool(allowed)
        except Exception as e:
            logger.error("Rate limiter failure: %s", e)
            # Fallback to allowed on Redis error to avoid blocking users
            return True
