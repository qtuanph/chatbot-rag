"""
Audit Stream Worker: Consumes security events from Redis Streams.
Uses loop-safe Async Redis with explicit pool management.
"""

import json
import logging
import asyncio
import uuid
from app.core.celery_app import celery_app
from app.db.session import AsyncSessionLocal
from app.models.audit import SecurityAudit
from app.core.config import settings
from app.core.redis import get_worker_redis

logger = logging.getLogger(__name__)

CONSUMER_GROUP = "audit-consumers"
CONSUMER_NAME_PREFIX = "worker"


@celery_app.task(name="app.workers.audit_worker.process_audit_stream")
def process_audit_stream(batch_size: int = 100):
    """
    Consumes audit events using loop-safe isolated async context.
    """

    async def _process_loop():
        # Using the Gold Standard: loop-safe context manager
        async with get_worker_redis() as local_redis:
            consumer_name = f"{CONSUMER_NAME_PREFIX}-{uuid.uuid4().hex[:8]}"
            stream_key = settings.audit_stream_name

            # 1. Ensure Group
            try:
                await local_redis.xgroup_create(stream_key, CONSUMER_GROUP, id="$", mkstream=True)
            except Exception:
                pass

            # 2. Process Pending (Recovery)
            pending = await local_redis.xpending_range(stream_key, CONSUMER_GROUP, min="-", max="+", count=batch_size)
            if pending:
                await _process_events(local_redis, stream_key, [p["message_id"] for p in pending])

            # 3. Read New (Blocking)
            streams = await local_redis.xreadgroup(
                CONSUMER_GROUP, consumer_name, {stream_key: ">"}, count=batch_size, block=5000
            )
            if not streams:
                return 0

            events = streams[0][1]
            event_ids = [e[0] for e in events]
            return await _process_events(local_redis, stream_key, event_ids)

    try:
        count = asyncio.run(_process_loop())
        if count > 0:
            logger.info("Processed %d audit events", count)
        return count
    except Exception as e:
        logger.error("Audit worker iteration failed: %s", e)
        return 0


async def _process_events(local_redis, stream_key: str, event_ids: list[str]) -> int:
    """Process and acknowledge audit events."""
    if not event_ids:
        return 0

    raw_events = []
    for eid in event_ids:
        event = await local_redis.xrange(stream_key, min=eid, max=eid, count=1)
        if event:
            raw_events.append(event[0])

    if not raw_events:
        return 0

    async with AsyncSessionLocal() as session:
        for event_id, fields in raw_events:
            action = fields.get("action", "").strip()
            if not action:
                await local_redis.xack(stream_key, CONSUMER_GROUP, event_id)
                continue

            audit_entry = SecurityAudit(
                action=action,
                actor_user_id=fields.get("actor_user_id") or None,
                subject_type=fields.get("subject_type") or None,
                subject_id=fields.get("subject_id") or None,
                ip_address=fields.get("ip_address") or None,
                user_agent=fields.get("user_agent") or None,
                details=json.loads(fields.get("details_json", "{}")),
            )
            session.add(audit_entry)

        await session.commit()
        await local_redis.xack(stream_key, CONSUMER_GROUP, *event_ids)

    return len(raw_events)
