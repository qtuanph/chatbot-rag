"""Shared Redis client singleton — single source of truth for all layers."""

import redis.asyncio as redis
from redis.backoff import ExponentialBackoff
from redis.retry import Retry

from app.core.config import settings
from app.core.hardware import hardware

_pool = redis.ConnectionPool.from_url(
    settings.redis_url_auth,
    max_connections=hardware.redis_pool_size,
    retry=Retry(ExponentialBackoff(), retries=3),
    retry_on_timeout=True,
)
def get_redis_client() -> redis.Redis:
    """Return a fresh Redis client instance. Essential for avoiding 'Event loop closed' in isolated asyncio.run() blocks."""
    return redis.Redis(connection_pool=_pool)

# Global client for API (where the loop is persistent)
redis_client = get_redis_client()

