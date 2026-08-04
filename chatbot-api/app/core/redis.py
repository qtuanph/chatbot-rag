"""Shared Redis client factories — providing both Async and Sync clients for different contexts."""

import logging
import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Any

import redis.asyncio as redis
from redis.backoff import ExponentialBackoff
from redis.retry import Retry

from app.core.config import settings
from app.core.hardware import hardware

logger = logging.getLogger(__name__)


def create_redis_pool(max_connections: int | None = None) -> redis.ConnectionPool:
    """Create a new Async Redis ConnectionPool with health checking and auto-retry."""
    return redis.ConnectionPool.from_url(
        settings.redis_url_auth,
        max_connections=max_connections or hardware.redis_pool_size,
        decode_responses=True,
        health_check_interval=30,
        retry=Retry(ExponentialBackoff(), retries=3),
        retry_on_timeout=True,
    )


# ── Async Clients (For API & Async Workers) ──────────────────────────

_api_pool: redis.ConnectionPool | None = None
_api_loop: asyncio.AbstractEventLoop | None = None


def get_redis_client() -> redis.Redis:
    """Get an Async Redis client for the main API process."""
    global _api_pool, _api_loop

    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        return redis.Redis(connection_pool=create_redis_pool())

    if _api_pool is None or _api_loop is not current_loop:
        _api_pool = create_redis_pool()
        _api_loop = current_loop
        logger.debug("Initialized API Redis pool [loop=%s]", id(_api_loop))

    return redis.Redis(connection_pool=_api_pool)


@asynccontextmanager
async def get_worker_redis() -> AsyncGenerator[redis.Redis, None]:
    """Scoped Async Redis client for Celery tasks. Prevents loop leaks."""
    pool = create_redis_pool(max_connections=5)
    client = redis.Redis(connection_pool=pool)
    try:
        yield client
    finally:
        await client.aclose()
        await pool.disconnect()


# ── Sync Clients (For Simple Workers & Audit) ──────────────────────────


_sync_pool: Any = None


def get_sync_redis_client() -> Any:
    """
    Get a SYNCHRONOUS Redis client.
    The 'Gold Standard' for stability in Celery tasks that don't need async I/O.
    """
    global _sync_pool
    import redis as redis_sync
    from redis.backoff import ExponentialBackoff as SyncBackoff
    from redis.retry import Retry as SyncRetry

    if _sync_pool is None:
        _sync_pool = redis_sync.ConnectionPool.from_url(
            settings.redis_url_auth,
            max_connections=10,
            decode_responses=True,
            health_check_interval=30,
            retry=SyncRetry(SyncBackoff(), retries=3),
            retry_on_timeout=True,
        )
    return redis_sync.Redis(connection_pool=_sync_pool)


async def close_redis_pools() -> None:
    """Gracefully close all global API Redis connection pools on shutdown."""
    global _api_pool, _api_loop
    if _api_pool is not None:
        try:
            await _api_pool.disconnect()
            logger.info("Closed API Redis connection pool")
        except Exception as exc:
            logger.warning("Error disconnecting API Redis pool: %s", exc)
        finally:
            _api_pool = None
            _api_loop = None
