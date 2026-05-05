"""
Audit Logging: Decoupled event logging via Redis Streams.
Ensures zero-latency impact on the main request-response cycle.
"""

from __future__ import annotations
import logging
import json
from typing import Any
from app.api.deps import redis_client

logger = logging.getLogger(__name__)

async def safe_record_audit(
    *,
    action: str,
    actor_user_id: str | None = None,
    subject_type: str | None = None,
    subject_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """
    Fire-and-forget audit logging using Redis Streams (XADD).
    The AuditStreamWorker will consume these events and persist them to DB.
    """
    try:
        # Prepare payload for Redis Stream (all values must be strings/bytes)
        payload = {
            "action": action,
            "actor_user_id": actor_user_id or "",
            "subject_type": subject_type or "",
            "subject_id": subject_id or "",
            "ip_address": ip_address or "",
            "user_agent": user_agent or "",
            "details_json": json.dumps(details or {}),
        }
        
        from app.core.config import settings
        await redis_client.xadd(settings.audit_stream_name, payload)
        
    except Exception as e:
        logger.warning("Failed to fire audit event to Redis Stream: %s", e)
        # We don't raise here to keep the main business logic moving
