"""Celery tasks for maintenance operations — BM25 rebuild, orphan cleanup, audit logging."""

import asyncio
import logging

from app.core.celery_app import celery_app
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.workers.maintenance_tasks.rebuild_bm25_index_task",
    acks_late=True,
    ignore_result=True,
    autoretry_for=(Exception,),
    retry_backoff=5,
    retry_jitter=True,
    max_retries=2,
)
def rebuild_bm25_index_task() -> None:
    """Rebuild BM25 vocabulary from Qdrant. Called after document upload/delete."""
    try:
        from app.utils.bm25_index import build_bm25_index_from_qdrant

        count = asyncio.run(build_bm25_index_from_qdrant())
        logger.info("BM25 index rebuilt: %d chunks indexed", count)
    except Exception as e:
        logger.error("BM25 index rebuild failed: %s", e, exc_info=True)
        raise


@celery_app.task(
    name="app.workers.maintenance_tasks.cleanup_orphaned_vectors_task",
    acks_late=True,
    ignore_result=True,
)
def cleanup_orphaned_vectors_task() -> None:
    """Remove Qdrant vectors that have no matching section in PostgreSQL."""

    async def _run_cleanup():
        from app.services.ingestion.recovery_service import RecoveryService
        from app.repositories.document_repository import DocumentRepository
        from app.repositories.section_repository import SectionRepository

        async with AsyncSessionLocal() as session:
            doc_repo = DocumentRepository(session)
            section_repo = SectionRepository(session)
            recovery = RecoveryService(doc_repo=doc_repo, section_repo=section_repo)

            doc_ids = await doc_repo.get_all_document_ids()
            total_cleaned = 0
            for doc_id in doc_ids:
                result = await recovery.cleanup_orphaned_vectors(document_id=doc_id)
                total_cleaned += result.get("cleaned", 0)
            logger.info(
                "Orphaned vector cleanup complete: %d vectors removed across %d documents", total_cleaned, len(doc_ids)
            )

    try:
        asyncio.run(_run_cleanup())
    except Exception as e:
        logger.error("Orphaned vector cleanup failed: %s", e, exc_info=True)
        raise
