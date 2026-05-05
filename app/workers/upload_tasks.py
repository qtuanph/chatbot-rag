"""Celery task definitions for document upload and ingestion pipeline."""

from celery.exceptions import SoftTimeLimitExceeded

from app.core.celery_app import celery_app
from app.core.config import settings
from app.db.session import SessionLocal
from app.repositories.document_repository import DocumentRepository
from app.adapters.embeddings import build_embedding_service
from app.adapters.vector_stores.qdrant import QdrantVectorStore
from app.adapters.storage import build_storage
from app.services.ingestion.ingestion_service import IngestionService
from app.repositories.section_repository import SectionRepository
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


def _verify_ingestion(
    document_id: str,
    file_path: str,
    vector_store: QdrantVectorStore,
    storage,
) -> dict:
    """
    Post-ingestion verification: confirm vectors indexed and file stored.

    Returns a dict with verification results for logging and artifact storage.
    Does NOT raise — verification failure is logged as WARNING only.
    """
    qdrant_count = vector_store.count(document_id)
    file_ok = storage.file_exists(file_path)

    result = {
        "qdrant_vectors": qdrant_count,
        "qdrant_ok": qdrant_count > 0,
        "file_in_storage": file_ok,
        "passed": qdrant_count > 0 and file_ok,
    }

    if result["passed"]:
        logger.info(
            "[%s] ✓ Ingestion verified: qdrant_vectors=%d file_ok=%s",
            document_id,
            qdrant_count,
            file_ok,
        )
    else:
        logger.warning(
            "[%s] ✗ Ingestion verify FAILED: qdrant_vectors=%d file_ok=%s",
            document_id,
            qdrant_count,
            file_ok,
        )

    return result


@celery_app.task(
    name="app.workers.upload_tasks.parse_document_task",
    bind=True,
    acks_late=True,
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=settings.celery_retry_backoff,
    retry_backoff_max=settings.celery_retry_backoff_max,
    retry_jitter=True,
    max_retries=settings.celery_max_retries,
)
def parse_document_task(self, task_id: str, document_id: str, file_path: str, user_id: str = None) -> dict:
    """
    Celery task: download → parse → embed → store → verify → unload.

    The embedding model is loaded fresh per task and unloaded after completion
    to release VRAM for the vLLM chat model.
    """
    storage = build_storage()
    content = b""
    metadata: dict = {}
    embedding_service = None
    vector_store = None
    db_session = None

    try:
        # ── Step 1: Download ─────────────────────────────────────────────────
        with SessionLocal() as _s:
            DocumentRepository(_s).update_status(
                document_id,
                status="processing",
                stage="downloading",
                progress_percent=10,
                status_message="[1/4] Đang tải file an toàn từ S3 Object Storage xuống RAM...",
            )
        logger.info("[%s] Downloading from %s...", document_id, file_path)
        content = storage.download_bytes(file_path)
        filename = file_path.rsplit("/", 1)[-1]

        # ── Step 2: Load embedding model ─────────────────────────────────────
        # Model is loaded fresh per task; unloaded in finally block.
        import torch

        device_name = "GPU" if torch.cuda.is_available() else "CPU"

        with SessionLocal() as _s:
            DocumentRepository(_s).update_status(
                document_id,
                status="processing",
                stage="parsing",
                progress_percent=15,
                status_message=f"[2/4] Đang khởi tạo Model trên {device_name} & Cắt file {filename} thành các Node...",
            )
        embedding_service = build_embedding_service()
        vector_store = _build_vector_store(embedding_service)

        # ── Step 3: Parse & embed ────────────────────────────────────────────
        logger.info("[%s] Parsing with pipeline...", document_id)

        # Open a DB session for section storage during ingestion
        db_session = SessionLocal()
        section_repo = SectionRepository(db_session)

        pipeline = IngestionService(
            embedding_service=embedding_service,
            vector_store=vector_store,
            db_session=db_session,
            section_repo=section_repo,
        )

        def _progress_callback(stage: str, percent: int, message: str = "") -> None:
            # Map default English texts to Vietnamese if possible
            translated_msg = message
            if "Extracting text" in message:
                translated_msg = "[2/4] Đang dùng AI trích xuất chữ (OCR) & Bóc tách bố cục..."
            elif "Processing section" in message or "Processing chunk" in message:
                translated_msg = "[3/4] Đang băm văn bản và nhúng (Embed) thành số liệu Vector..."

            with SessionLocal() as _s:
                DocumentRepository(_s).update_status(
                    document_id,
                    status="processing",
                    stage=stage,
                    progress_percent=percent,
                    status_message=translated_msg or stage,
                )

        ingestion_result = pipeline.ingest(
            filename=filename,
            content=content,
            user_id=user_id or "system",
            document_id=document_id,
            progress_callback=_progress_callback,
        )

        if not ingestion_result.success:
            raise Exception(f"Pipeline failed: {', '.join(ingestion_result.errors)}")

        if ingestion_result.node_count > 0 and not ingestion_result.storage_ids:
            raise ValueError("Vector store did not persist any node IDs for this document")

        # ── Step 4: Post-ingestion verification ──────────────────────────────
        with SessionLocal() as _s:
            DocumentRepository(_s).update_status(
                document_id,
                status="processing",
                stage="verifying",
                progress_percent=95,
                status_message="[4/4] Khâu cuối: Đang đối soát và verify kết quả trên Qdrant...",
            )
        verify = _verify_ingestion(document_id, file_path, vector_store, storage)

        # ── Step 5: Persist metadata ─────────────────────────────────────────
        with SessionLocal() as _s:
            DocumentRepository(_s).update_status(
                document_id,
                status="processing",
                stage="verifying",
                progress_percent=95,
                status_message="Persisting ingestion artifact and finalizing document.",
            )
        logger.info("[%s] Storing ingestion metadata to PostgreSQL...", document_id)

        if (
            ingestion_result.validation_report
            and ingestion_result.validation_report.node_count < settings.ingestion_min_non_empty_nodes
        ):
            raise ValueError(
                f"Extraction quality too low: {ingestion_result.node_count} nodes "
                f"< {settings.ingestion_min_non_empty_nodes} minimum"
            )
        if ingestion_result.total_text_chars < settings.ingestion_min_total_text_chars:
            raise ValueError(
                f"Extraction quality too low: {ingestion_result.total_text_chars} chars "
                f"< {settings.ingestion_min_total_text_chars} minimum"
            )

        artifact_dict = (
            ingestion_result.parse_metadata.to_dict() if getattr(ingestion_result, "parse_metadata", None) else {}
        )
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
        metadata = {"ingestion_artifact": artifact_dict}

        with SessionLocal() as session:
            doc_repo = DocumentRepository(session)
            doc_repo.finalize_ingestion(
                document_id,
                artifact_dict=artifact_dict,
                node_count=ingestion_result.node_count,
                total_text_chars=ingestion_result.total_text_chars,
            )

            # Invalidate cached doc IDs so next chat request picks up new document
            from app.services.retrieval.retrieval_service import invalidate_doc_ids_cache

            invalidate_doc_ids_cache()

            # Rebuild BM25 index from all Qdrant chunks (includes new document)
            logger.info("[%s] Dispatching BM25 index rebuild...", document_id)
            from app.workers.maintenance_tasks import rebuild_bm25_index_task

            rebuild_bm25_index_task.delay()

            logger.info("[%s] ✓ Document metadata persisted", document_id)

    except SoftTimeLimitExceeded:
        logger.error("[%s] Task exceeded soft time limit", document_id)
        if db_session is not None:
            try:
                db_session.close()
            except Exception as e:
                logger.warning("Failed to close DB session: %s", e)
            db_session = None
        with SessionLocal() as _s:
            DocumentRepository(_s).update_status(
                document_id,
                status="failed",
                stage="failed",
                progress_percent=0,
                status_message="Document processing timed out. Try a smaller file.",
                parse_error="SoftTimeLimitExceeded",
            )
        raise

    except Exception as exc:
        if db_session is not None:
            try:
                db_session.close()
            except Exception as e:
                logger.warning("Failed to close DB session: %s", e)
            db_session = None
        logger.error("[%s] ✗ Pipeline failed: %s", document_id, exc)
        with SessionLocal() as _s:
            DocumentRepository(_s).update_status(
                document_id,
                status="failed",
                stage="failed",
                progress_percent=100,
                status_message="Ingestion failed.",
                parse_error=str(exc),
            )
        raise

    finally:
        # Always release VRAM/RAM after task — whether success or failure.
        # Next ingestion task will load the model fresh from disk cache.
        if embedding_service is not None:
            unload_fn = getattr(embedding_service, "unload", None)
            if callable(unload_fn):
                unload_fn()
        # Close the DB session used for section storage
        if db_session is not None:
            try:
                db_session.close()
            except Exception as e:
                logger.warning("Failed to close DB session: %s", e)

    return {
        "task_id": task_id,
        "document_id": document_id,
        "file_path": file_path,
        "status": "ready",
        "stage": "ready",
        "progress": {"step": "ready", "percent": 100},
        "bytes": len(content),
        "node_count": ingestion_result.node_count,
        "duration_ms": ingestion_result.duration_ms,
        "ingestion_artifact": metadata.get("ingestion_artifact", {}),
    }
