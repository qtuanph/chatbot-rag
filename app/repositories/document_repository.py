import logging
from datetime import datetime, timezone

from sqlalchemy import func, select, update, delete, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DocumentStoreException
from app.models.document import Document

logger = logging.getLogger(__name__)


class DocumentRepository:
    """Repository for document metadata in PostgreSQL."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def update_status(
        self,
        document_id: str,
        status: str,
        parse_error: str | None = None,
        stage: str | None = None,
        progress_percent: int | None = None,
        status_message: str | None = None,
    ) -> bool:
        """Update document status."""
        try:
            document = await self.session.get(Document, document_id)
            if document is None:
                return False
            document.status = status
            document.parse_error = parse_error[:2000] if parse_error else None
            if stage is not None:
                document.status_stage = stage
            if progress_percent is not None:
                document.progress_percent = max(0, min(100, int(progress_percent)))
            if status_message is not None:
                document.status_message = status_message
            document.status_updated_at = datetime.now(timezone.utc)
            document.updated_at = datetime.now(timezone.utc)
            await self.session.commit()
            logger.info("Document %s status → %s", document_id, status)
            return True
        except Exception as e:
            await self.session.rollback()
            raise DocumentStoreException(
                f"Failed to update status for {document_id}: {str(e)}",
                error_code="DOCUMENT_STORE_UPDATE_FAILED",
            )

    async def find_by_sha256(self, sha256: str) -> dict | None:
        """Find a non-deleted document by SHA256 hash (for deduplication)."""
        stmt = (
            select(Document)
            .where(Document.sha256 == sha256, Document.deleted_at.is_(None))
            .order_by(Document.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        document = result.scalar_one_or_none()
        return self._doc_to_full_dict(document) if document else None

    async def get_next_version(self, filename: str) -> int:
        """Get the next version number for a given filename."""
        stmt = (
            select(func.coalesce(func.max(Document.version), 0))
            .where(Document.file_name == filename, Document.deleted_at.is_(None))
        )
        result = await self.session.execute(stmt)
        max_ver = result.scalar()
        return (max_ver or 0) + 1

    async def insert_document(
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
        await self.session.commit()
        await self.session.refresh(document)
        return self._doc_to_full_dict(document)

    async def list_paginated(self, offset: int = 0, limit: int = 20) -> tuple[list[dict], int]:
        """List non-deleted documents with pagination. Returns (items, total)."""
        count_stmt = select(func.count(Document.id)).where(Document.deleted_at.is_(None))
        count_result = await self.session.execute(count_stmt)
        total = count_result.scalar() or 0

        stmt = (
            select(Document)
            .where(Document.deleted_at.is_(None))
            .order_by(Document.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        return [self._doc_to_full_dict(r) for r in rows], total

    async def soft_delete(self, document_id: str) -> bool:
        """Soft-delete a document by setting deleted_at."""
        document = await self.session.get(Document, document_id)
        if document is None:
            return False
        document.deleted_at = datetime.now(timezone.utc)
        document.status = "failed"
        document.status_stage = "failed"
        document.progress_percent = 100
        document.status_message = "Failed to enqueue ingestion task."
        document.status_updated_at = datetime.now(timezone.utc)
        await self.session.commit()
        return True

    async def reset_for_retry(self, document_id: str) -> dict | None:
        """Reset document status for retry. Returns updated dict or None."""
        document = await self.session.get(Document, document_id)
        if document is None:
            return None
        document.status = "pending"
        document.status_stage = "queued"
        document.progress_percent = 5
        document.status_message = "Retrying: task queued for worker processing."
        document.parse_error = None
        document.status_updated_at = datetime.now(timezone.utc)
        await self.session.commit()
        await self.session.refresh(document)
        return self._doc_to_full_dict(document)

    async def get_full_document(self, document_id: str) -> dict | None:
        """Get full document details including all fields."""
        document = await self.session.get(Document, document_id)
        return self._doc_to_full_dict(document) if document else None

    async def finalize_ingestion(
        self,
        document_id: str,
        *,
        artifact_dict: dict,
        node_count: int,
        total_text_chars: int,
    ) -> bool:
        """Set document to ready state with ingestion artifact metadata."""
        try:
            document = await self.session.get(Document, document_id)
            if document is None:
                return False

            metadata = dict(document.extra_metadata or {})
            metadata["ingestion_artifact"] = artifact_dict
            document.extra_metadata = metadata
            document.status = "ready"
            document.status_stage = "ready"
            document.progress_percent = 100
            document.status_message = "Ingestion completed successfully."
            document.status_updated_at = datetime.now(timezone.utc)
            document.parse_error = None
            document.updated_at = datetime.now(timezone.utc)
            await self.session.commit()
            return True
        except Exception as e:
            await self.session.rollback()
            raise DocumentStoreException(
                f"Failed to finalize ingestion for {document_id}: {str(e)}",
                error_code="DOCUMENT_STORE_UPDATE_FAILED",
            )

    async def find_stuck_documents(self, timeout_threshold: datetime) -> list[str]:
        """Find documents stuck in processing state before timeout_threshold."""
        stmt = (
            select(Document)
            .where(Document.status == "processing", Document.status_updated_at < timeout_threshold)
        )
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        return [str(doc.id) for doc in rows]

    async def get_latest_active_document_ids(self) -> set[str]:
        """Return IDs of latest-version, non-deleted, ready documents."""
        latest_versions_stmt = (
            select(
                Document.file_name.label("file_name"),
                func.max(Document.version).label("max_version"),
            )
            .where(Document.deleted_at.is_(None), Document.status == "ready")
            .group_by(Document.file_name)
        ).subquery()

        stmt = (
            select(Document.id)
            .join(
                latest_versions_stmt,
                and_(
                    Document.file_name == latest_versions_stmt.c.file_name,
                    Document.version == latest_versions_stmt.c.max_version,
                ),
            )
            .where(Document.deleted_at.is_(None), Document.status == "ready")
        )
        result = await self.session.execute(stmt)
        rows = result.all()
        return {str(row[0]) for row in rows if row and row[0]}

    async def get_all_document_ids(self) -> list[str]:
        """Return all non-deleted document IDs for bulk operations."""
        stmt = select(Document.id).where(Document.deleted_at.is_(None))
        result = await self.session.execute(stmt)
        rows = result.all()
        return [str(row[0]) for row in rows if row and row[0]]

    async def get_titles_by_ids(self, doc_ids: list[str]) -> dict[str, str]:
        """Fetch document titles by IDs. Returns {doc_id: title}."""
        stmt = (
            select(Document.id, Document.title)
            .where(
                Document.deleted_at.is_(None),
                Document.status == "ready",
                Document.id.in_(doc_ids),
            )
        )
        result = await self.session.execute(stmt)
        rows = result.all()
        return {str(doc_id): title for doc_id, title in rows}

    async def hard_delete(self, document_id: str) -> bool:
        """Hard-delete a document row from PostgreSQL."""
        document = await self.session.get(Document, document_id)
        if document is None:
            return False
        await self.session.delete(document)
        await self.session.commit()
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
            "artifact_metadata": dict(document.extra_metadata or {}),
            "deleted_at": document.deleted_at.isoformat() if document.deleted_at else None,
            "created_at": document.created_at.isoformat() if document.created_at else None,
            "updated_at": document.updated_at.isoformat() if document.updated_at else None,
        }

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
            "artifact_metadata": dict(document.extra_metadata or {}),
            "deleted_at": document.deleted_at.isoformat() if document.deleted_at else None,
            "created_at": document.created_at.isoformat() if document.created_at else None,
            "updated_at": document.updated_at.isoformat() if document.updated_at else None,
        }
