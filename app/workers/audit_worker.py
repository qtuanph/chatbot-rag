import json
import logging
import asyncio
import uuid
from app.core.celery_app import celery_app
from app.db.session import AsyncSessionLocal
from app.models.audit import SecurityAudit
from app.core.redis import redis_client
from app.core.config import settings

logger = logging.getLogger(__name__)

CONSUMER_GROUP = "audit-consumers"
CONSUMER_NAME_PREFIX = "worker"


@celery_app.task(name="app.workers.audit_worker.process_audit_stream")
def process_audit_stream(batch_size: int = 100):
    """
    Consumes audit events from Redis Stream using XREADGROUP consumer group.
    More reliable than XREAD — supports multiple consumers and pending message recovery.
    """

    async def _process():
        consumer_name = f"{CONSUMER_NAME_PREFIX}-{uuid.uuid4().hex[:8]}"
        stream_key = settings.audit_stream_name

        try:
            # Ensure consumer group exists (ignore if already exists)
            try:
                await redis_client.xgroup_create(stream_key, CONSUMER_GROUP, id="$", mkstream=True)
            except Exception:
                pass  # Group already exists

            # Read pending messages first (recovery from crash)
            pending = await redis_client.xpending_range(stream_key, CONSUMER_GROUP, min="-", max="+", count=batch_size)
            if pending:
                pending_ids = [p["message_id"] for p in pending]
                await _process_events(stream_key, pending_ids)

            # Read new messages with blocking
            streams = await redis_client.xreadgroup(
                CONSUMER_GROUP,
                consumer_name,
                {stream_key: ">"},
                count=batch_size,
                block=10000,
            )

            if not streams:
                return 0

            events = streams[0][1]
            if not events:
                return 0

            event_ids = [e[0] for e in events]
            count = await _process_events(stream_key, event_ids)

            return count
        except Exception as e:
            logger.error("Audit worker failed: %s", e)
            return 0

    count = asyncio.run(_process())
    if count > 0:
        logger.info("Processed %d audit events via XREADGROUP", count)
    return count


async def _process_events(stream_key: str, event_ids: list[str]) -> int:
    """Process events by ID and acknowledge them."""
    if not event_ids:
        return 0

    # Fetch events by ID
    raw_events = []
    for eid in event_ids:
        event = await redis_client.xrange(stream_key, min=eid, max=eid, count=1)
        if event:
            raw_events.append(event[0])

    if not raw_events:
        return 0

    async with AsyncSessionLocal() as session:
        for event_id, fields in raw_events:
            # Validate required fields — skip invalid events
            action = fields.get("action", "").strip()
            if not action:
                logger.warning("Skipping audit event with missing action: %s", event_id)
                await redis_client.xack(stream_key, CONSUMER_GROUP, event_id)
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

        # Acknowledge processed events
        await redis_client.xack(stream_key, CONSUMER_GROUP, *event_ids)

    return len(raw_events)
