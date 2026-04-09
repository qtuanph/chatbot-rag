"""Celery task definitions for document ingestion and processing."""

import logging
from datetime import datetime, timezone

from app.core.celery_app import celery_app
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.core import Document
from app.adapters.embeddings.bge_m3 import BGEM3Embedding
from app.adapters.vector_stores.qdrant import QdrantVectorStore
from app.services.storage import build_storage
from app.services.ingestion.pipeline import IngestionPipeline
from app.services.ingestion.parser_manager import ParserManager

logger = logging.getLogger(__name__)


def _set_document_status(
    *,
    document_id: str,
    status: str,
    stage: str,
    progress_percent: int,
    status_message: str,
    parse_error: str | None = None,
) -> None:
    with SessionLocal() as session:
        document = session.get(Document, document_id)
        if document is None:
            return
        document.status = status
        document.status_stage = stage
        document.progress_percent = max(0, min(100, progress_percent))
        document.status_message = status_message
        document.status_updated_at = datetime.now(timezone.utc)
        if parse_error is not None:
            document.parse_error = parse_error[:2000] if parse_error else None
        document.updated_at = datetime.now(timezone.utc)
        session.commit()


@celery_app.task(name="app.worker.parse_document_task", bind=True)
def parse_document_task(self, task_id: str, document_id: str, file_path: str, user_id: str = None) -> dict:
    """
    Celery task for document ingestion using new pipeline.
    
    Args:
        task_id: Celery task ID
        document_id: Document ID
        file_path: Path in storage (e.g., s3://bucket/key)
        user_id: User who uploaded document
    
    Returns:
        Result dict with status and metadata
    """
    storage = build_storage()
    content = b""
    
    try:
        # Step 1: Download file
        self.update_state(
            task_id=task_id,
            state="STARTED",
            meta={
                "stage": "download",
                "progress": {"step": "download", "percent": 10},
                "document_id": document_id,
            },
        )
        _set_document_status(
            document_id=document_id,
            status="processing",
            stage="download",
            progress_percent=10,
            status_message="Downloading source file from object storage.",
            parse_error="",
        )
        logger.info(f"[{document_id}] Downloading from {file_path}...")
        content = storage.download_bytes(file_path)
        filename = file_path.rsplit("/", 1)[-1]
        
        # Step 2: Parse document with new pipeline
        self.update_state(
            task_id=task_id,
            state="STARTED",
            meta={
                "stage": "parse",
                "progress": {"step": "parse", "percent": 40},
                "document_id": document_id,
            },
        )
        _set_document_status(
            document_id=document_id,
            status="processing",
            stage="parse",
            progress_percent=40,
            status_message="Parsing document and building hierarchical nodes.",
        )
        logger.info(f"[{document_id}] Parsing with new pipeline...")

        parser_manager = ParserManager()

        with SessionLocal() as pipeline_session:
            pipeline = IngestionPipeline(
                parser_manager=parser_manager,
                embedding_service=BGEM3Embedding(
                    model_name="BAAI/bge-m3",
                    batch_size=settings.embedding_batch_size,
                    normalize=settings.embedding_normalize,
                ),
                vector_store=QdrantVectorStore(
                    url=settings.qdrant_url,
                    api_key=settings.qdrant_api_key or None,
                    collection_name=settings.qdrant_collection,
                    timeout=settings.qdrant_timeout,
                ),
            )

            ingestion_result = pipeline.ingest(
                filename=filename,
                content=content,
                user_id=user_id or "system",
                document_id=document_id,
            )
        
        if not ingestion_result.success:
            raise Exception(f"Pipeline failed: {', '.join(ingestion_result.errors)}")

        if ingestion_result.node_count > 0 and not ingestion_result.storage_ids:
            raise ValueError("Vector store did not persist any node IDs for this document")
        
        # Step 3: Persist document metadata
        self.update_state(
            task_id=task_id,
            state="STARTED",
            meta={
                "stage": "persist",
                "progress": {"step": "persist", "percent": 75},
                "document_id": document_id,
            },
        )
        _set_document_status(
            document_id=document_id,
            status="processing",
            stage="persist",
            progress_percent=75,
            status_message="Persisting ingestion artifact and finalizing document.",
        )
        logger.info(f"[{document_id}] Storing ingestion metadata to PostgreSQL...")
        
        with SessionLocal() as session:
            document = session.get(Document, document_id)
            if document is None:
                raise ValueError(f"Document not found: {document_id}")
            
            # Validate quality thresholds
            if ingestion_result.validation_report and ingestion_result.validation_report.node_count < settings.ingestion_min_non_empty_nodes:
                raise ValueError(
                    f"Extraction quality too low: {ingestion_result.node_count} nodes "
                    f"< {settings.ingestion_min_non_empty_nodes} minimum"
                )
            if ingestion_result.total_text_chars < settings.ingestion_min_total_text_chars:
                raise ValueError(
                    f"Extraction quality too low: {ingestion_result.total_text_chars} chars "
                    f"< {settings.ingestion_min_total_text_chars} minimum"
                )
            
            # Store artifact metadata
            metadata = dict(document.extra_metadata or {})
            artifact_dict = ingestion_result.parse_metadata.to_dict() if ingestion_result.parse_metadata else {}
            artifact_dict.update({
                'valid': ingestion_result.success,
                'node_count': ingestion_result.node_count,
                'total_chars': ingestion_result.total_text_chars,
                'errors': ingestion_result.errors,
                'warnings': ingestion_result.warnings,
                'duration_ms': ingestion_result.duration_ms,
            })
            metadata['ingestion_artifact'] = artifact_dict
            document.extra_metadata = metadata
            
            # Mark document as ready
            document.status = "ready"
            document.status_stage = "ready"
            document.progress_percent = 100
            document.status_message = "Ingestion completed successfully."
            document.status_updated_at = datetime.now(timezone.utc)
            document.parse_error = None
            document.updated_at = datetime.now(timezone.utc)
            session.commit()
            
            logger.info(f"[{document_id}] ✓ Document metadata persisted")
    
    except Exception as exc:
        logger.error(f"[{document_id}] ✗ Pipeline failed: {str(exc)}")
        _set_document_status(
            document_id=document_id,
            status="failed",
            stage="failed",
            progress_percent=100,
            status_message="Ingestion failed.",
            parse_error=str(exc),
        )
        
        raise
    
    result = {
        "task_id": task_id,
        "document_id": document_id,
        "file_path": file_path,
        "status": "ready",
        "stage": "done",
        "progress": {"step": "done", "percent": 100},
        "bytes": len(content),
        "node_count": ingestion_result.node_count,
        "duration_ms": ingestion_result.duration_ms,
        "ingestion_artifact": metadata.get("ingestion_artifact", {}),
    }
    
    return result
