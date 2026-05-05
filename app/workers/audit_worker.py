import json
import logging
import asyncio
from app.core.celery_app import celery_app
from app.db.session import AsyncSessionLocal
from app.models.audit import SecurityAudit
from app.api.deps import redis_client
from app.core.config import settings

logger = logging.getLogger(__name__)


@celery_app.task(name="app.workers.audit_worker.process_audit_stream")
def process_audit_stream(batch_size: int = 100):
    """
    Consumes a batch of audit events from Redis and writes them to the database (Async).
    This task should be scheduled periodically via Celery Beat.
    """

    async def _process():
        try:
            # XREAD from stream
            streams = await redis_client.xread({settings.audit_stream_name: "0"}, count=batch_size)
            if not streams:
                return 0

            events = streams[0][1]  # [(id, fields), ...]
            if not events:
                return 0

            async with AsyncSessionLocal() as session:
                for event_id, fields in events:
                    audit_entry = SecurityAudit(
                        action=fields.get("action"),
                        actor_user_id=fields.get("actor_user_id") or None,
                        subject_type=fields.get("subject_type") or None,
                        subject_id=fields.get("subject_id") or None,
                        ip_address=fields.get("ip_address") or None,
                        user_agent=fields.get("user_agent") or None,
                        details=json.loads(fields.get("details_json", "{}")),
                    )
                    session.add(audit_entry)

                await session.commit()

                # Acknowledge by deleting processed events from the stream
                event_ids = [e[0] for e in events]
                await redis_client.xdel(settings.audit_stream_name, *event_ids)

            return len(events)
        except Exception as e:
            logger.error("Audit worker failed to process stream: %s", e)
            return 0

    # Run the async loop in the sync Celery worker context
    count = asyncio.run(_process())
    if count > 0:
        logger.info("Processed %d audit events from stream", count)
    return count
