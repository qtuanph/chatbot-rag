"""
Rate limiting service using atomic Lua script to prevent race conditions.

Bug fixed: Previous implementation used separate INCR + EXPIRE calls,
which are not atomic. Under concurrent requests, two threads could both
read count=0, both increment, and only one would set the expiry — leading
to keys that never expire (memory leak) or windows that reset incorrectly.

Fix: Single Lua script executed atomically by Redis.
Redis guarantees single-threaded script execution — no race condition possible.
"""

import redis
from app.core.config import settings

# Atomic rate-limit script (Lua)
_RATE_LIMIT_SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return count
"""


class RequestThrottle:
    """Atomic sliding-window rate limiter using standard Lua scripting."""

    def __init__(self) -> None:
        self._client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        self._script = self._client.register_script(_RATE_LIMIT_SCRIPT)

    def allow(self, key: str, limit: int, window_seconds: int) -> bool:
        """Return True if within limit, False otherwise. Fails if Redis fails."""
        count = int(self._script(keys=[key], args=[window_seconds]))
        return count <= limit
