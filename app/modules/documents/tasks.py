"""
Celery task definitions for document upload and ingestion pipeline.
Uses SYNCHRONOUS Redis for status updates to ensure 100% stability.
"""

from app.core.celery_app import celery_app
from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.modules.documents.repositories import DocumentRepository, SectionRepository
from app.adapters.embeddings import build_embedding_service
from app.adapters.vector_stores.qdrant import QdrantVectorStore
from app.adapters.storage import build_storage
from app.modules.documents.ingestion.ingestion_service import IngestionService
from app.core.redis import get_sync_redis_client
from app.modules.documents.utils.document_registry import DocumentRegistry
from app.utils.audit import safe_record_audit
import asyncio
import logging

logger = logging.getLogger(__name__)


def _build_vector_store(embedding_service) -> QdrantVectorStore:
    """Build a QdrantVectorStore instance."""
    return QdrantVectorStore(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key or None,
        collection_name=settings.qdrant_collection,
        vector_size=settings.embedding_vector_size,
        timeout=settings.qdrant_timeout,
    )


async def _verify_ingestion(
    document_id: str,
    file_path: str,
    vector_store: QdrantVectorStore,
    storage,
) -> dict:
    """Post-ingestion verification (Async)."""
    qdrant_count = await vector_store.count(document_id)
    file_exists = await asyncio.to_thread(storage.file_exists, file_path)
    return {
        "qdrant_count": qdrant_count,
        "storage_exists": file_exists,
        "passed": qdrant_count > 0 and file_exists,
    }


@celery_app.task(
    name="app.workers.upload_tasks.parse_document_task",
    bind=True,
    acks_late=True,
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=settings.celery_retry_backoff,
    max_retries=settings.celery_max_retries,
    soft_time_limit=settings.celery_task_soft_time_limit,
    time_limit=settings.celery_task_time_limit,
)
def parse_document_task(self, task_id: str, document_id: str, file_path: str, user_id: str | None = None) -> dict:
    """
    Ingestion task with Synchronous status management for reliability.
    """
    # 1. Initialize Sync Resources
    sync_redis = get_sync_redis_client()
    registry = DocumentRegistry(sync_redis)
    storage = build_storage()
    filename = file_path.split("/")[-1]

    # 2. Local Async Execution Block
    async def _run_async_pipeline():
        async with AsyncSessionLocal() as session:
            doc_repo = DocumentRepository(session)

            # Update status to processing
            await doc_repo.update_status(
                document_id,
                status="processing",
                stage="initializing",
                progress_percent=5,
                status_message="[1/4] Đang khởi tạo môi trường nạp liệu...",
            )

            try:
                content = await asyncio.to_thread(storage.download_bytes, file_path)
                embedding_service = build_embedding_service()
                vector_store = _build_vector_store(embedding_service)
                section_repo = SectionRepository(session)

                # Create an isolated async redis client for the pipeline (Loop-safe)
                from app.core.redis import get_redis_client

                async_redis = get_redis_client()

                pipeline = IngestionService(
                    redis_client=async_redis,
                    embedding_service=embedding_service,
                    vector_store=vector_store,
                    db_session=session,
                    section_repo=section_repo,
                )

                async def _progress_callback(stage: str, percent: int, message: str = ""):
                    """Async callback to update DB status using a fresh session for 100% stability."""
                    logger.info("[%s] Progress: %d%% - %s", document_id, percent, message)
                    try:
                        # Use a fresh session for each update to avoid transaction sharing issues
                        async with AsyncSessionLocal() as fresh_session:
                            fresh_repo = DocumentRepository(fresh_session)
                            await fresh_repo.update_status(
                                document_id,
                                status="processing",
                                stage=stage,
                                progress_percent=percent,
                                status_message=message,
                            )
                    except Exception as status_err:
                        logger.warning("[%s] Failed to update progress in DB: %s", document_id, status_err)

                # Core Ingestion (The only truly async part)
                ingestion_result = await pipeline.ingest(
                    filename=filename,
                    content=content,
                    user_id=user_id or "system",
                    document_id=document_id,
                    progress_callback=_progress_callback,
                )

                # Verification
                verify = await _verify_ingestion(document_id, file_path, vector_store, storage)

                # Finalize DB
                if ingestion_result.success:
                    artifact_dict = ingestion_result.parse_metadata.to_dict() if ingestion_result.parse_metadata else {}
                    artifact_dict["verification"] = verify
                    await doc_repo.finalize_ingestion(
                        document_id,
                        artifact_dict=artifact_dict,
                        node_count=ingestion_result.node_count,
                        total_text_chars=ingestion_result.total_text_chars,
                        progress_percent=100,
                    )
                else:
                    raise ValueError(f"Ingestion failed: {', '.join(ingestion_result.errors)}")

                # Cleanup async resources
                await async_redis.aclose()
                return ingestion_result

            except Exception as e:
                await doc_repo.update_status(
                    document_id,
                    status="failed",
                    stage="failed",
                    status_message=f"Lỗi: {str(e)}",
                )
                raise e

    # 3. Execute Async Pipeline
    try:
        result = asyncio.run(_run_async_pipeline())

        # 4. Sync Finalization (Safe from loop errors)
        registry.purge_sync(document_id)
        registry.invalidate_active_ids_sync()

        # Audit (Truly sync call now)
        safe_record_audit(
            action="document.ingestion_complete",
            actor_user_id=user_id,
            subject_type="document",
            subject_id=document_id,
            details={"node_count": result.node_count},
        )

        # Trigger maintenance
        from app.modules.system.tasks import rebuild_bm25_index_task

        rebuild_bm25_index_task.delay()

        return {"status": "success", "document_id": document_id}

    except Exception as e:
        logger.error("[%s] Sync wrapper caught error: %s", document_id, e)
        # Audit failure (Truly sync call now)
        safe_record_audit(
            action="document.ingestion_failed",
            actor_user_id=user_id,
            subject_type="document",
            subject_id=document_id,
            details={"error": str(e)},
        )
        raise e
