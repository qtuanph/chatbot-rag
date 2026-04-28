"""Repository for document metadata in PostgreSQL."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.exceptions import DocumentStoreException
from app.models.document import Document

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
        """Insert or update document record."""
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
                "document_id": str(document.id),
                "user_id": user_id,
                "filename": document.file_name,
                "status": document.status,
                "status_stage": document.status_stage,
                "progress_percent": int(document.progress_percent),
                "status_message": document.status_message,
                "artifact_metadata": dict(document.extra_metadata or {}),
                "created_at": document.created_at.isoformat() if document.created_at else None,
                "updated_at": document.updated_at.isoformat() if document.updated_at else None,
            }
        except Exception as e:
            self.session.rollback()
            raise DocumentStoreException(
                f"Failed to upsert document {document_id}: {str(e)}",
                error_code="DOCUMENT_STORE_UPSERT_FAILED",
                details={"document_id": document_id, "error": str(e)},
            )

    def get_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Get document record by ID."""
        try:
            document = self.session.get(Document, document_id)
            if document is None:
                return None
            return {
                "document_id": str(document.id),
                "title": document.title,
                "file_name": document.file_name,
                "status": document.status,
                "status_stage": document.status_stage,
                "progress_percent": int(document.progress_percent),
                "status_message": document.status_message,
                "parse_error": document.parse_error,
                "artifact_metadata": dict(document.extra_metadata or {}),
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
            document.parse_error = error_msg[:2000] if error_msg else None
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

    def find_by_sha256(self, sha256: str) -> Optional[dict]:
        """Find a non-deleted document by SHA256 hash (for deduplication)."""
        document = (
            self.session.query(Document)
            .filter(Document.sha256 == sha256, Document.deleted_at.is_(None))
            .order_by(Document.created_at.desc())
            .first()
        )
        return self._doc_to_full_dict(document) if document else None

    def get_next_version(self, filename: str) -> int:
        """Get the next version number for a given filename."""
        max_ver = (
            self.session.query(func.coalesce(func.max(Document.version), 0))
            .filter(Document.file_name == filename, Document.deleted_at.is_(None))
            .scalar()
        )
        return (max_ver or 0) + 1

    def insert_document(
        self,
        *,
        document_id: str,
        title: str,
        file_name: str,
        file_path: str,
        sha256: str,
        file_type: str,
        file_size: int,
        version: int = 1,
    ) -> dict:
        """Insert a new document record."""
        document = Document(
            id=document_id,
            title=title,
            file_name=file_name,
            file_path=file_path,
            sha256=sha256,
            file_type=file_type,
            file_size=file_size,
            version=version,
            status="pending",
            status_stage="uploaded",
            progress_percent=1,
            status_message="File uploaded and awaiting queue.",
        )
        self.session.add(document)
        self.session.commit()
        return self._doc_to_full_dict(document)

    def list_paginated(self, offset: int = 0, limit: int = 20) -> Tuple[List[dict], int]:
        """List non-deleted documents with pagination. Returns (items, total)."""
        total = self.session.query(func.count(Document.id)).filter(Document.deleted_at.is_(None)).scalar() or 0
        rows = (
            self.session.query(Document)
            .filter(Document.deleted_at.is_(None))
            .order_by(Document.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [self._doc_to_full_dict(r) for r in rows], total

    def soft_delete(self, document_id: str) -> bool:
        """Soft-delete a document by setting deleted_at."""
        document = self.session.get(Document, document_id)
        if document is None:
            return False
        document.deleted_at = datetime.now(timezone.utc)
        document.status = "failed"
        document.status_stage = "enqueue_failed"
        document.progress_percent = 100
        document.status_message = "Failed to enqueue ingestion task."
        document.status_updated_at = datetime.now(timezone.utc)
        self.session.commit()
        return True

    def reset_for_retry(self, document_id: str) -> Optional[dict]:
        """Reset document status for retry. Returns updated dict or None."""
        document = self.session.get(Document, document_id)
        if document is None:
            return None
        document.status = "pending"
        document.status_stage = "queued"
        document.progress_percent = 5
        document.status_message = "Retrying: task queued for worker processing."
        document.parse_error = None
        document.status_updated_at = datetime.now(timezone.utc)
        self.session.commit()
        return self._doc_to_full_dict(document)

    def get_full_document(self, document_id: str) -> Optional[dict]:
        """Get full document details including all fields."""
        document = self.session.get(Document, document_id)
        return self._doc_to_full_dict(document) if document else None

    def get_latest_active_document_ids(self) -> set[str]:
        """Return IDs of latest-version, non-deleted, ready documents."""
        from sqlalchemy import and_

        latest_versions = (
            self.session.query(
                Document.file_name.label("file_name"),
                func.max(Document.version).label("max_version"),
            )
            .filter(Document.deleted_at.is_(None), Document.status == "ready")
            .group_by(Document.file_name)
            .subquery()
        )
        rows = (
            self.session.query(Document.id)
            .join(
                latest_versions,
                and_(
                    Document.file_name == latest_versions.c.file_name,
                    Document.version == latest_versions.c.max_version,
                ),
            )
            .filter(Document.deleted_at.is_(None), Document.status == "ready")
            .all()
        )
        return {str(row[0]) for row in rows if row and row[0]}

    def get_titles_by_ids(self, doc_ids: list[str]) -> dict[str, str]:
        """Fetch document titles by IDs. Returns {doc_id: title}."""
        rows = (
            self.session.query(Document.id, Document.title)
            .filter(
                Document.deleted_at.is_(None),
                Document.status == "ready",
                Document.id.in_(doc_ids),
            )
            .all()
        )
        return {str(doc_id): title for doc_id, title in rows}

    def hard_delete(self, document_id: str) -> bool:
        """Hard-delete a document row from PostgreSQL."""
        document = self.session.get(Document, document_id)
        if document is None:
            return False
        self.session.delete(document)
        self.session.commit()
        return True

    # ── Private helpers ──────────────────────────────────────────────

    def _doc_to_full_dict(self, document: Document) -> dict:
        return {
            "id": str(document.id),
            "title": document.title,
            "file_name": document.file_name,
            "file_path": document.file_path,
            "sha256": document.sha256,
            "file_type": document.file_type,
            "file_size": document.file_size,
            "version": document.version,
            "status": document.status,
            "status_stage": document.status_stage,
            "progress_percent": int(document.progress_percent),
            "status_message": document.status_message,
            "status_updated_at": document.status_updated_at.isoformat() if document.status_updated_at else None,
            "parse_error": document.parse_error,
            "extra_metadata": dict(document.extra_metadata or {}),
            "deleted_at": document.deleted_at.isoformat() if document.deleted_at else None,
            "created_at": document.created_at.isoformat() if document.created_at else None,
            "updated_at": document.updated_at.isoformat() if document.updated_at else None,
        }
