"""
Celery task definitions for document cleanup and maintenance.
Uses LlamaIndex QdrantVectorStore for vector cleanup.
"""

import asyncio
import logging

from app.core.celery_app import celery_app
from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.core.redis import get_sync_redis_client
from app.adapters.storage import build_storage
from app.modules.documents.services import CleanupService
from app.modules.documents.repositories import DocumentRepository, SectionRepository
from app.utils.audit import safe_record_audit

logger = logging.getLogger(__name__)


async def _verify_deletion_async(document_id: str, file_path: str | None, storage) -> dict:
    from qdrant_client import QdrantClient
    from qdrant_client.http.exceptions import ApiException

    client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None)
    qdrant_count = 0
    try:
        exists = await asyncio.to_thread(client.collection_exists, collection_name=settings.qdrant_collection)
        if exists:
            result = await asyncio.to_thread(
                client.count,
                collection_name=settings.qdrant_collection,
                count_filter={"must": [{"key": "document_id", "match": {"value": document_id}}]},
            )
            qdrant_count = result.count if result else 0
    except ApiException as e:
        # Collection may be absent during/after cleanup; treat as no remaining vectors.
        logger.warning("[%s] Qdrant verify warning: %s", document_id, e)
    except Exception as e:
        logger.warning("[%s] Qdrant verify unexpected warning: %s", document_id, e)
    file_exists = await asyncio.to_thread(storage.file_exists, file_path) if file_path else False
    file_removed = not file_exists

    async with AsyncSessionLocal() as session:
        doc_repo = DocumentRepository(session)
        db_gone = (await doc_repo.get_full_document(document_id)) is None

    return {
        "qdrant_clean": qdrant_count == 0,
        "file_removed": file_removed,
        "db_row_gone": db_gone,
        "passed": qdrant_count == 0 and file_removed and db_gone,
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
    self.update_state(
        state="STARTED",
        meta={"stage": "deleting", "progress": {"percent": 20}, "document_id": document_id},
    )

    sync_redis = get_sync_redis_client()
    storage = build_storage()

    async def _delete_workflow():
        async with AsyncSessionLocal() as session:
            doc_repo = DocumentRepository(session)
            section_repo = SectionRepository(session)
            doc_info = await doc_repo.get_full_document(document_id)
            file_path = doc_info.get("file_path") if doc_info else None

            cleanup_svc = CleanupService(doc_repo=doc_repo, section_repo=section_repo, redis_client=sync_redis)
            cleanup_result = await cleanup_svc.hard_delete_document(document_id)

            verify = await _verify_deletion_async(document_id, file_path, storage)
            return cleanup_result, verify

    try:
        cleanup_result, verify = asyncio.run(_delete_workflow())

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
