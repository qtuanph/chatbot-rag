"""
Audit Logging: Hybrid Sync/Async event logging via Redis Streams.
"""

from __future__ import annotations
import logging
import json
import asyncio
from typing import Any
from app.core.redis import get_sync_redis_client

logger = logging.getLogger(__name__)


def safe_record_audit(**kwargs) -> None:
    """
    The universal entry point for audit logging.
    Can be called from BOTH sync and async code WITHOUT await.
    """
    try:
        loop = None
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            pass

        if loop and loop.is_running():
            # We are in an ASYNC context (FastAPI)
            # We schedule the async audit as a background task to not block
            r_client = kwargs.pop("redis_client_override", None)
            if r_client is None:
                # If no client provided in async context, we cannot log reliably without risking loop issues
                logger.warning("Audit log skipped: redis_client_override is required in async context")
                return
            loop.create_task(_record_audit_async(r_client, **kwargs))
        else:
            # We are in a SYNC context (Celery worker)
            # We use the synchronous client directly
            sync_client = get_sync_redis_client()
            _record_audit_sync(sync_client, **kwargs)

    except Exception as e:
        logger.warning("Audit logging failed (silently): %s", e)


async def _record_audit_async(client: Any, **kwargs) -> None:
    """Internal async implementation."""
    from app.core.config import settings

    payload = _prepare_payload(**kwargs)
    try:
        await client.xadd(settings.audit_stream_name, payload, maxlen=settings.audit_stream_maxlen)
    except Exception as e:
        logger.warning("Async audit failed: %s", e)


def _record_audit_sync(client: Any, **kwargs) -> None:
    """Internal sync implementation."""
    from app.core.config import settings

    payload = _prepare_payload(**kwargs)
    try:
        client.xadd(settings.audit_stream_name, payload, maxlen=settings.audit_stream_maxlen)
    except Exception as e:
        logger.warning("Sync audit failed: %s", e)


def _prepare_payload(**kwargs) -> dict:
    """Standardize payload format."""
    return {
        "action": kwargs.get("action", "unknown"),
        "actor_user_id": str(kwargs.get("actor_user_id", "")),
        "subject_type": kwargs.get("subject_type", ""),
        "subject_id": str(kwargs.get("subject_id", "")),
        "ip_address": kwargs.get("ip_address", ""),
        "user_agent": kwargs.get("user_agent", ""),
        "details_json": json.dumps(kwargs.get("details", {})),
    }
