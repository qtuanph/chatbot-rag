"""L1 Exact cache: normalize query -> SHA-256 key -> Redis GET/SET.

Cache key format: exact_cache:{tenant_id}:{sha256(normalized_query)}
Circuit breaker: redis errors are logged and caught, failing open.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

import redis.asyncio as aioredis

from app.modules.chat.utils.query_normalizer import ALL_DEFAULT_STOPWORDS, normalize_query

logger = logging.getLogger(__name__)
_EXACT_CACHE_PREFIX = "exact_cache"


def _build_cache_key(tenant_id: str, normalized_query: str) -> str:
    digest = hashlib.sha256(normalized_query.encode("utf-8")).hexdigest()
    return f"{_EXACT_CACHE_PREFIX}:{tenant_id}:{digest}"


async def exact_cache_get(redis: aioredis.Redis, tenant_id: str, question: str) -> dict[str, Any] | None:
    """L1 lookup. Returns None on miss, error, or empty normalized query."""
    try:
        normalized = normalize_query(question, stopwords=ALL_DEFAULT_STOPWORDS)
        if not normalized:
            return None
        key = _build_cache_key(tenant_id, normalized)
        raw = await redis.get(key)
        if raw is None:
            return None
        return json.loads(raw)
    except Exception as exc:
        logger.warning("exact_cache_get error (circuit open): %s", exc)
        return None


async def exact_cache_set(
    redis: aioredis.Redis,
    tenant_id: str,
    question: str,
    payload: dict[str, Any],
    ttl_seconds: int = 2592000,
) -> None:
    """L1 write. Silently skips on error (circuit breaker)."""
    try:
        normalized = normalize_query(question, stopwords=ALL_DEFAULT_STOPWORDS)
        if not normalized:
            return
        key = _build_cache_key(tenant_id, normalized)
        await redis.setex(key, ttl_seconds, json.dumps(payload, ensure_ascii=False))
    except Exception as exc:
        logger.warning("exact_cache_set error: %s", exc)


async def exact_cache_invalidate_tenant(redis: aioredis.Redis, tenant_id: str) -> int:
    """Clear all L1 cache entries for a tenant (called on KB publish/rollback)."""
    try:
        pattern = f"{_EXACT_CACHE_PREFIX}:{tenant_id}:*"
        keys = await redis.keys(pattern)
        if keys:
            return await redis.delete(*keys)
        return 0
    except Exception as exc:
        logger.warning("exact_cache_invalidate_tenant error: %s", exc)
        return 0
