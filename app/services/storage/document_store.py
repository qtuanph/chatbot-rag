"""
Document Store Repository: PostgreSQL wrapper for document metadata and status.
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.core.exceptions import DocumentStoreException
from app.models.core import Document

logger = logging.getLogger(__name__)


class DocumentRepository:
    """Repository for document metadata in PostgreSQL."""

    def __init__(self, session: Session):
        self.session = session

    def upsert_document(
        self,
        document_id: str,
        user_id: str,
        filename: str,
        status: str = "pending",
        artifact_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Insert or update document record.
        
        Args:
            document_id: Unique document ID
            user_id: User who uploaded document
            filename: Original filename
            status: Upload status (pending, processing, success, failed)
            artifact_metadata: JSON metadata from ingestion
        
        Returns:
            Document record as dict
        """
        try:
            metadata = dict(artifact_metadata or {})
            document = self.session.get(Document, document_id)

            if document is None:
                document = Document(
                    id=document_id,
                    title=metadata.get("title") or filename,
                    file_name=filename,
                    file_path=metadata.get("file_path") or "",
                    sha256=metadata.get("sha256") or "",
                    file_type=metadata.get("file_type") or "application/octet-stream",
                    file_size=int(metadata.get("file_size") or 0),
                    version=int(metadata.get("version") or 1),
                    status=status,
                    status_stage=str(metadata.get("status_stage") or "uploaded"),
                    progress_percent=int(metadata.get("progress_percent") or 0),
                    status_message=metadata.get("status_message"),
                    status_updated_at=datetime.now(timezone.utc),
                    extra_metadata=metadata,
                )
                self.session.add(document)
            else:
                current_metadata = dict(document.extra_metadata or {})
                current_metadata.update(metadata)
                document.title = metadata.get("title") or filename
                document.file_name = filename
                document.status = status
                if "status_stage" in metadata:
                    document.status_stage = str(metadata["status_stage"])
                if "progress_percent" in metadata:
                    document.progress_percent = int(metadata["progress_percent"])
                if "status_message" in metadata:
                    document.status_message = metadata.get("status_message")
                document.status_updated_at = datetime.now(timezone.utc)
                document.extra_metadata = current_metadata
                document.updated_at = datetime.now(timezone.utc)

            self.session.commit()

            return {
                'document_id': str(document.id),
                'user_id': user_id,
                'filename': document.file_name,
                'status': document.status,
                'status_stage': document.status_stage,
                'progress_percent': int(document.progress_percent),
                'status_message': document.status_message,
                'artifact_metadata': dict(document.extra_metadata or {}),
                'created_at': document.created_at.isoformat() if document.created_at else None,
                'updated_at': document.updated_at.isoformat() if document.updated_at else None,
            }
        except Exception as e:
            self.session.rollback()
            raise DocumentStoreException(
                f"Failed to upsert document {document_id}: {str(e)}",
                error_code="DOCUMENT_STORE_UPSERT_FAILED",
                details={'document_id': document_id, 'error': str(e)}
            )

    def get_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Get document record by ID."""
        try:
            document = self.session.get(Document, document_id)
            if document is None:
                return None
            return {
                'document_id': str(document.id),
                'title': document.title,
                'file_name': document.file_name,
                'status': document.status,
                'status_stage': document.status_stage,
                'progress_percent': int(document.progress_percent),
                'status_message': document.status_message,
                'parse_error': document.parse_error,
                'artifact_metadata': dict(document.extra_metadata or {}),
            }
        except Exception as e:
            raise DocumentStoreException(
                f"Failed to get document {document_id}: {str(e)}",
                error_code="DOCUMENT_STORE_GET_FAILED",
            )

    def update_status(
        self,
        document_id: str,
        status: str,
        error_msg: Optional[str] = None,
        stage: Optional[str] = None,
        progress_percent: Optional[int] = None,
        status_message: Optional[str] = None,
    ) -> bool:
        """Update document status."""
        try:
            document = self.session.get(Document, document_id)
            if document is None:
                return False
            document.status = status
            document.parse_error = (error_msg[:2000] if error_msg else None)
            if stage is not None:
                document.status_stage = stage
            if progress_percent is not None:
                document.progress_percent = max(0, min(100, int(progress_percent)))
            if status_message is not None:
                document.status_message = status_message
            document.status_updated_at = datetime.now(timezone.utc)
            document.updated_at = datetime.now(timezone.utc)
            self.session.commit()
            logger.info(f"Document {document_id} status → {status}")
            return True
        except Exception as e:
            self.session.rollback()
            raise DocumentStoreException(
                f"Failed to update status for {document_id}: {str(e)}",
                error_code="DOCUMENT_STORE_UPDATE_FAILED",
            )
