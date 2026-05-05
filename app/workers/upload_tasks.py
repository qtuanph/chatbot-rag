"""
Celery task definitions for document upload and ingestion pipeline.
"""

from celery.exceptions import SoftTimeLimitExceeded

from app.core.celery_app import celery_app
from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.repositories.document_repository import DocumentRepository
from app.adapters.embeddings import build_embedding_service
from app.adapters.vector_stores.qdrant import QdrantVectorStore
from app.adapters.storage import build_storage
from app.services.ingestion.ingestion_service import IngestionService
from app.repositories.section_repository import SectionRepository
import asyncio
import logging

logger = logging.getLogger(__name__)


def _build_vector_store(embedding_service) -> QdrantVectorStore:
    """Build a QdrantVectorStore instance with the current embedding dimension."""
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
    """
    Post-ingestion verification: confirm vectors exist in Qdrant and file exists in storage.
    """
    # Qdrant check
    qdrant_count = await vector_store.count(document_id)

    # Storage check (wrapped in to_thread as boto3 is sync)
    file_exists = await asyncio.to_thread(storage.file_exists, file_path)

    result = {
        "qdrant_count": qdrant_count,
        "storage_exists": file_exists,
        "passed": qdrant_count > 0 and file_exists,
    }

    if result["passed"]:
        logger.info("[%s] ✓ Ingestion verified: qdrant=%d storage=OK", document_id, qdrant_count)
    else:
        logger.warning(
            "[%s] ✗ Ingestion verify FAILED: qdrant=%d storage=%s",
            document_id,
            qdrant_count,
            "OK" if file_exists else "MISSING",
        )

    return result


@celery_app.task(
    name="app.workers.upload_tasks.parse_document_task",
    bind=True,
    acks_late=True,
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=settings.celery_retry_backoff,
    retry_jitter=True,
    max_retries=settings.celery_max_retries,
    soft_time_limit=settings.celery_soft_time_limit,
    time_limit=settings.celery_time_limit,
)
def parse_document_task(self, task_id: str, document_id: str, file_path: str, user_id: str | None = None) -> dict:
    """
    Synchronous Celery task wrapper for the asynchronous ingestion pipeline.
    """

    async def _run_task():
        async with AsyncSessionLocal() as session:
            doc_repo = DocumentRepository(session)

            await doc_repo.update_status(
                document_id,
                status="processing",
                stage="initializing",
                progress_percent=5,
                status_message="Đang chuẩn bị môi trường nạp liệu...",
            )

            try:
                # ── Step 1: Download (wrapped in to_thread as boto3 is sync) ───────────
                storage = build_storage()
                content = await asyncio.to_thread(storage.download_bytes, file_path)
                filename = file_path.split("/")[-1]

                import torch

                device_name = "GPU" if torch.cuda.is_available() else "CPU"

                await doc_repo.update_status(
                    document_id,
                    status="processing",
                    stage="parsing",
                    progress_percent=15,
                    status_message=f"[2/4] Đang khởi tạo Model trên {device_name} & Cắt file {filename} thành các Node...",
                )

                embedding_service = build_embedding_service()
                vector_store = _build_vector_store(embedding_service)
                section_repo = SectionRepository(session)

                pipeline = IngestionService(
                    embedding_service=embedding_service,
                    vector_store=vector_store,
                    db_session=session,
                    section_repo=section_repo,
                )

                async def _progress_callback(stage: str, percent: int, message: str = ""):
                    # Optimized progress update: dedicated connection for atomicity during parallel ingestion
                    translated_msg = message
                    if "Extracting text" in message:
                        translated_msg = "[2/4] Đang dùng AI trích xuất chữ (OCR) & Bóc tách bố cục..."
                    elif "Indexing section" in message:
                        translated_msg = "[3/4] Đang băm văn bản và nhúng (Embed) thành số liệu Vector..."

                    async with AsyncSessionLocal() as p_session:
                        p_repo = DocumentRepository(p_session)
                        await p_repo.update_status(
                            document_id,
                            status="processing",
                            stage=stage,
                            progress_percent=percent,
                            status_message=translated_msg or stage,
                        )


                # ── Step 3: Parse & embed ────────────────────────────────────────────
                logger.info("[%s] Parsing with pipeline...", document_id)
                ingestion_result = await pipeline.ingest(
                    filename=filename,
                    content=content,
                    user_id=user_id or "system",
                    document_id=document_id,
                    progress_callback=lambda s, p, m: asyncio.create_task(_progress_callback(s, p, m)),
                )

                # ── Step 4: Verification ──────────────────────────────────────────────
                await doc_repo.update_status(
                    document_id,
                    status="processing",
                    stage="verifying",
                    progress_percent=95,
                    status_message="[4/4] Khâu cuối: Đang đối soát và verify kết quả trên Qdrant...",
                )

                verify = await _verify_ingestion(document_id, file_path, vector_store, storage)

                # ── Step 5: Finalize ──────────────────────────────────────────────────
                if not ingestion_result.success:
                    raise ValueError(f"Ingestion failed: {', '.join(ingestion_result.errors)}")

                artifact_dict = ingestion_result.parse_metadata.to_dict() if ingestion_result.parse_metadata else {}
                artifact_dict.update(
                    {
                        "valid": ingestion_result.success,
                        "node_count": ingestion_result.node_count,
                        "total_chars": ingestion_result.total_text_chars,
                        "errors": ingestion_result.errors,
                        "warnings": ingestion_result.warnings,
                        "duration_ms": ingestion_result.duration_ms,
                        "verification": verify,
                    }
                )

                await doc_repo.finalize_ingestion(
                    document_id,
                    artifact_dict=artifact_dict,
                    node_count=ingestion_result.node_count,
                    total_text_chars=ingestion_result.total_text_chars,
                )

                # Invalidate cache
                from app.services.retrieval.retrieval_service import invalidate_doc_ids_cache

                await invalidate_doc_ids_cache()

                # Rebuild BM25
                from app.workers.maintenance_tasks import rebuild_bm25_index_task

                rebuild_bm25_index_task.delay()

                # Unload model
                if hasattr(embedding_service, "unload"):
                    embedding_service.unload()

                return {"status": "success", "document_id": document_id}

            except Exception as e:
                logger.error("[%s] Task error: %s", document_id, e)
                await doc_repo.update_status(
                    document_id,
                    status="failed",
                    stage="failed",
                    progress_percent=0,
                    status_message=f"Lỗi: {str(e)}",
                    parse_error=str(e),
                )
                raise e

    try:
        return asyncio.run(_run_task())
    except SoftTimeLimitExceeded:
        logger.error("[%s] Task soft timeout", document_id)

        # Final desperate status update
        async def _timeout_update():
            async with AsyncSessionLocal() as session:
                await DocumentRepository(session).update_status(
                    document_id,
                    status="failed",
                    stage="failed",
                    status_message="Processing timed out.",
                    parse_error="SoftTimeLimitExceeded",
                )

        asyncio.run(_timeout_update())
        raise
