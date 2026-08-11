"""L1 Exact cache: normalize query -> SHA-256 key -> Redis GET/SET.

Cache key format: exact_cache:{doc_key_or_tenant_id}:{sha256(normalized_query)}
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


def _build_cache_key(doc_key_or_tenant_id: str, normalized_query: str) -> str:
    digest = hashlib.sha256(normalized_query.encode("utf-8")).hexdigest()
    return f"{_EXACT_CACHE_PREFIX}:{doc_key_or_tenant_id}:{digest}"


async def exact_cache_get(
    redis: aioredis.Redis, doc_key_or_tenant_id: str, question: str, ttl_seconds: int = 2592000
) -> dict[str, Any] | None:
    """L1 lookup with automatic sliding TTL extension on cache hit."""
    try:
        normalized = normalize_query(question, stopwords=ALL_DEFAULT_STOPWORDS)
        if not normalized:
            return None
        key = _build_cache_key(doc_key_or_tenant_id, normalized)
        # Atomic read + TTL extension in single Redis command
        raw = await redis.getex(key, ex=ttl_seconds)
        if raw is None:
            return None
        return json.loads(raw)
    except Exception as exc:
        logger.warning("exact_cache_get error (circuit open): %s", exc)
        return None


async def exact_cache_set(
    redis: aioredis.Redis,
    doc_key_or_tenant_id: str,
    question: str,
    payload: dict[str, Any],
    ttl_seconds: int = 2592000,
) -> None:
    """L1 write. Silently skips on error or if payload is a negative fallback response."""
    try:
        content = str((payload or {}).get("content") or "")
        if any(neg in content for neg in ["chưa tìm thấy dữ liệu", "chưa được phân quyền", "không có trong tài liệu"]):
            return

        normalized = normalize_query(question, stopwords=ALL_DEFAULT_STOPWORDS)
        if not normalized:
            return
        key = _build_cache_key(doc_key_or_tenant_id, normalized)
        await redis.setex(key, ttl_seconds, json.dumps(payload, ensure_ascii=False))
    except Exception as exc:
        logger.warning("exact_cache_set error: %s", exc)


async def exact_cache_invalidate_tenant(redis: aioredis.Redis, tenant_id: str) -> int:
    """Clear all L1 cache entries for a tenant (called on KB publish/rollback)."""
    try:
        pattern = f"{_EXACT_CACHE_PREFIX}:{tenant_id}:*"
        keys = [key async for key in redis.scan_iter(match=pattern)]
        if keys:
            return await redis.delete(*keys)
        return 0
    except Exception as exc:
        logger.warning("exact_cache_invalidate_tenant error: %s", exc)
        return 0


async def exact_cache_delete(redis: aioredis.Redis, tenant_id: str, question: str) -> None:
    """Delete L1 exact cache for a specific query upon dislike feedback."""
    try:
        normalized = normalize_query(question, stopwords=ALL_DEFAULT_STOPWORDS)
        if not normalized:
            return
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        pattern = f"{_EXACT_CACHE_PREFIX}:*:{digest}"
        keys = [key async for key in redis.scan_iter(match=pattern)]
        if keys:
            await redis.delete(*keys)
    except Exception as exc:
        logger.warning("exact_cache_delete error: %s", exc)
