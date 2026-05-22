"""
Celery tasks for maintenance operations — orphan cleanup.
"""

import asyncio
import logging

from app.core.celery_app import celery_app
from app.db.session import AsyncSessionLocal
from app.core.redis import get_sync_redis_client

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.workers.maintenance_tasks.cleanup_orphaned_vectors_task",
    acks_late=True,
    ignore_result=True,
)
def cleanup_orphaned_vectors_task() -> None:
    sync_redis = get_sync_redis_client()

    async def _run_cleanup():
        from app.modules.documents.ingestion.recovery_service import RecoveryService
        from app.modules.documents.repositories import DocumentRepository, SectionRepository

        async with AsyncSessionLocal() as session:
            doc_repo = DocumentRepository(session)
            section_repo = SectionRepository(session)

            recovery = RecoveryService(doc_repo=doc_repo, section_repo=section_repo, redis_client=sync_redis)
            doc_ids = await doc_repo.get_all_document_ids()
            total_cleaned = 0
            for doc_id in doc_ids:
                result = await recovery.cleanup_orphaned_vectors(document_id=doc_id)
                total_cleaned += result.get("cleaned", 0)

            return total_cleaned, len(doc_ids)

    try:
        total_cleaned, doc_count = asyncio.run(_run_cleanup())
        logger.info("Orphaned vector cleanup complete: %d vectors removed across %d docs", total_cleaned, doc_count)
    except Exception as e:
        logger.error("Orphaned vector cleanup failed: %s", e)
        raise
