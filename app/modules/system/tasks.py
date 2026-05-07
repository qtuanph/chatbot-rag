"""
Celery tasks for maintenance operations — BM25 rebuild, orphan cleanup.
Uses Sync-Primary architecture for maximum stability.
"""

import asyncio
import logging

from app.core.celery_app import celery_app
from app.db.session import AsyncSessionLocal
from app.core.redis import get_sync_redis_client
from app.utils.bm25_index import build_bm25_index_from_qdrant

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.workers.maintenance_tasks.rebuild_bm25_index_task",
    acks_late=True,
    ignore_result=True,
    autoretry_for=(ConnectionError, TimeoutError, OSError),
    retry_backoff=5,
    max_retries=2,
)
def rebuild_bm25_index_task() -> None:
    """Rebuild BM25 vocabulary (Isolated Async)."""
    try:

        async def _run_rebuild():
            from app.core.redis import get_redis_client

            async_redis = get_redis_client()
            count = await build_bm25_index_from_qdrant(redis_client=async_redis)
            await async_redis.aclose()
            return count

        count = asyncio.run(_run_rebuild())
        logger.info("BM25 index rebuilt: %d chunks indexed", count)
    except Exception as e:
        logger.error("BM25 index rebuild failed: %s", e)
        raise


@celery_app.task(
    name="app.workers.maintenance_tasks.cleanup_orphaned_vectors_task",
    acks_late=True,
    ignore_result=True,
)
def cleanup_orphaned_vectors_task() -> None:
    """Remove orphaned vectors using Sync-Primary architecture."""
    # 1. Sync Infrastructure
    sync_redis = get_sync_redis_client()

    async def _run_cleanup():
        from app.modules.documents.ingestion.recovery_service import RecoveryService
        from app.modules.documents.repository import DocumentRepository
        from app.modules.documents.section_repository import SectionRepository

        # Isolated Async context
        async with AsyncSessionLocal() as session:
            doc_repo = DocumentRepository(session)
            section_repo = SectionRepository(session)

            # RecoveryService handles its own internal loop-safe async redis if needed,
            # but we pass the sync_redis if it supports hybrid (it will detect context).
            recovery = RecoveryService(doc_repo=doc_repo, section_repo=section_repo, redis_client_override=sync_redis)

            doc_ids = await doc_repo.get_all_document_ids()
            total_cleaned = 0
            for doc_id in doc_ids:
                result = await recovery.cleanup_orphaned_vectors(document_id=doc_id)
                total_cleaned += result.get("cleaned", 0)

            return total_cleaned, len(doc_ids)

    try:
        total_cleaned, doc_count = asyncio.run(_run_cleanup())
        logger.info(
            "Orphaned vector cleanup complete: %d vectors removed across %d documents", total_cleaned, doc_count
        )
    except Exception as e:
        logger.error("Orphaned vector cleanup failed: %s", e)
        raise
