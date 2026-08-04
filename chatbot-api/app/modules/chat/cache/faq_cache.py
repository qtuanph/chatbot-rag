"""FAQ Redis Lookup: normalize query -> SHA-256 hash -> Redis HGET faq_idx:{tenant_id} {hash}.

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


def compute_query_hash(text: str) -> str | None:
    normalized = normalize_query(text, stopwords=ALL_DEFAULT_STOPWORDS)
    if not normalized:
        return None
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


async def faq_lookup(redis: aioredis.Redis, tenant_id: str, question: str) -> dict[str, Any] | None:
    """O(1) FAQ lookup in Redis. Returns payload dict on hit, None on miss/error."""
    try:
        query_hash = compute_query_hash(question)
        if not query_hash:
            return None
        key = f"faq_idx:{tenant_id}"
        raw = await redis.hget(key, query_hash)
        if raw is None:
            return None
        return json.loads(raw)
    except Exception as exc:
        logger.warning("faq_lookup error (circuit open): %s", exc)
        return None


async def faq_cache_sync_item(
    redis: aioredis.Redis, tenant_id: str, query_hashes: list[str], payload: dict[str, Any]
) -> None:
    """Sync a published FAQ entry's query hashes to Redis index using Redis 8 native batch HSET."""
    try:
        key = f"faq_idx:{tenant_id}"
        val = json.dumps(payload, ensure_ascii=False)
        mapping = {h: val for h in query_hashes if h}
        if mapping:
            await redis.hset(key, mapping=mapping)
    except Exception as exc:
        logger.warning("faq_cache_sync_item error: %s", exc)


async def faq_cache_remove_item(redis: aioredis.Redis, tenant_id: str, query_hashes: list[str]) -> None:
    """Remove query hashes for an unpublished/deleted FAQ entry from Redis index."""
    try:
        key = f"faq_idx:{tenant_id}"
        if query_hashes:
            await redis.hdel(key, *query_hashes)
    except Exception as exc:
        logger.warning("faq_cache_remove_item error: %s", exc)
