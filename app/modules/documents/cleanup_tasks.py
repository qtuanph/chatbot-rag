"""
Celery task definitions for document cleanup and maintenance.
Uses SYNCHRONOUS Redis for reliability in cleanup flows.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone


from app.core.celery_app import celery_app
from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.modules.chat.repositories import ChatRepository
from app.modules.documents.repositories import DocumentRepository
from app.core.redis import get_sync_redis_client
from app.modules.documents.utils.document_registry import DocumentRegistry
from app.utils.audit import safe_record_audit

logger = logging.getLogger(__name__)


async def _verify_deletion_async(
    document_id: str,
    file_path: str | None,
    vector_store,
    storage,
) -> dict:
    """Post-delete verification (Async)."""
    qdrant_count = await vector_store.count(document_id)
    file_gone = await asyncio.to_thread(storage.file_exists, file_path) if file_path else True

    async with AsyncSessionLocal() as session:
        doc_repo = DocumentRepository(session)
        db_gone = (await doc_repo.get_full_document(document_id)) is None

    return {
        "qdrant_clean": qdrant_count == 0,
        "file_removed": file_gone,
        "db_row_gone": db_gone,
        "passed": qdrant_count == 0 and file_gone and db_gone,
    }


@celery_app.task(
    name="app.workers.cleanup_tasks.delete_document_task",
    bind=True,
    acks_late=True,
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=5,
    max_retries=settings.celery_max_retries,
)
def delete_document_task(self, task_id: str, document_id: str, user_id: str | None = None) -> dict:
    """
    Celery task: hard-delete document using Sync Redis for state management.
    """
    # 1. Sync State Update
    self.update_state(
        state="STARTED",
        meta={"stage": "deleting", "progress": {"percent": 20}, "document_id": document_id},
    )

    # 2. Initialize Sync Resources
    sync_redis = get_sync_redis_client()
    registry = DocumentRegistry(sync_redis)
    from app.adapters.storage import build_storage

    storage = build_storage()

    async def _delete_workflow():
        # Inner Async context for Qdrant/DB
        from app.adapters.vector_stores.qdrant import QdrantVectorStore
        from app.modules.documents.services import CleanupService
        from app.modules.documents.repositories import DocumentRepository, SectionRepository

        # We need an ASYNC registry for the service (using its own loop-safe pool)
        from app.core.redis import get_worker_redis

        async with get_worker_redis() as local_async_redis:
            async_registry = DocumentRegistry(local_async_redis)

            async with AsyncSessionLocal() as session:
                doc_repo = DocumentRepository(session)
                section_repo = SectionRepository(session)
                doc_info = await doc_repo.get_full_document(document_id)
                file_path = doc_info.get("file_path") if doc_info else None

                cleanup_svc = CleanupService(doc_repo=doc_repo, section_repo=section_repo, registry=async_registry)
                cleanup_result = await cleanup_svc.hard_delete_document(document_id)

                vector_store = QdrantVectorStore(
                    url=settings.qdrant_url,
                    api_key=settings.qdrant_api_key or None,
                    collection_name=settings.qdrant_collection,
                    vector_size=settings.embedding_vector_size,
                )
                verify = await _verify_deletion_async(document_id, file_path, vector_store, storage)
                return cleanup_result, verify

    try:
        cleanup_result, verify = asyncio.run(_delete_workflow())

        # 3. Sync Finalization
        registry.purge_sync(document_id)

        # Audit (Truly sync call now)
        safe_record_audit(
            action="document.hard_delete_complete",
            actor_user_id=user_id,
            subject_type="document",
            subject_id=document_id,
            details={"cleanup": cleanup_result, "verify": verify},
        )

        return {"status": "deleted", "document_id": document_id, "verify": verify}

    except Exception as e:
        logger.error("[%s] Delete failed: %s", document_id, e)
        raise e


@celery_app.task(
    name="app.workers.cleanup_tasks.cleanup_old_chat_sessions_task",
    acks_late=True,
    ignore_result=True,
)
def cleanup_old_chat_sessions_task() -> dict:
    """Periodic sync cleanup task."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.chat_session_ttl_days)

    async def _run_cleanup():
        async with AsyncSessionLocal() as session:
            return await ChatRepository(session).delete_sessions_older_than(cutoff)

    count = asyncio.run(_run_cleanup())
    logger.info("Cleaned up %d old chat sessions", count)
    return {"deleted_count": count}
