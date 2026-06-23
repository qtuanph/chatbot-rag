import logging
from typing import Any
from datetime import datetime
from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DocumentStoreException
from app.models.document import Document
from app.modules.documents.base import BaseRepository
from app.utils.datetime_utils import to_vietnam_iso, utc_now

logger = logging.getLogger(__name__)


class DocumentRepository(BaseRepository[Document]):
    """Repository for document metadata in PostgreSQL."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Document)

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
            document = await self.get_by_id(document_id)
            if document is None or document.deleted_at is not None:
                return False
            document.status = status
            document.parse_error = parse_error[:2000] if parse_error else None
            if stage is not None:
                document.status_stage = stage
            if progress_percent is not None:
                document.progress_percent = max(0, min(100, int(progress_percent)))
            if status_message is not None:
                document.status_message = status_message[:500]
            document.status_updated_at = utc_now()
            document.updated_at = utc_now()
            await self.session.commit()
            logger.info("Document %s status \u2192 %s", document_id, status)
            return True
        except Exception as e:
            await self.session.rollback()
            raise DocumentStoreException(
                f"Failed to update status for {document_id}: {str(e)}",
                error_code="DOCUMENT_STORE_UPDATE_FAILED",
            )

    async def find_by_sha256(self, sha256: str, tenant_id: str) -> dict | None:
        """Find a non-deleted document by SHA256 hash (for deduplication)."""
        stmt = (
            select(self.model)
            .where(self.model.sha256 == sha256, self.model.tenant_id == tenant_id, self.model.deleted_at.is_(None))
            .order_by(self.model.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        document = result.scalar_one_or_none()
        return self._to_dict(document) if document else None

    async def get_next_version(self, filename: str, tenant_id: str) -> int:
        """Get the next version number for a given filename."""
        stmt = select(func.coalesce(func.max(self.model.version), 0)).where(
            self.model.file_name == filename, self.model.tenant_id == tenant_id, self.model.deleted_at.is_(None)
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
        tenant_id: str,
        version: int = 1,
    ) -> dict:
        """Insert a new document record."""
        document = self.model(
            id=document_id,
            tenant_id=tenant_id,
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
        return self._to_dict(document)

    async def list_paginated(
        self, offset: int = 0, limit: int = 20, tenant_id: str | None = None
    ) -> tuple[list[dict], int]:
        """List non-deleted documents with pagination. Returns (items, total)."""
        count_stmt = select(func.count(self.model.id)).where(self.model.deleted_at.is_(None))
        if tenant_id:
            count_stmt = count_stmt.where(self.model.tenant_id == tenant_id)
        count_result = await self.session.execute(count_stmt)
        total = count_result.scalar() or 0

        stmt = select(self.model).where(self.model.deleted_at.is_(None))
        if tenant_id:
            stmt = stmt.where(self.model.tenant_id == tenant_id)
        stmt = stmt.order_by(self.model.created_at.desc()).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        return [self._to_dict(r) for r in rows], total

    async def soft_delete(self, document_id: str) -> bool:
        """Soft-delete a document by setting deleted_at."""
        document = await self.get_by_id(document_id)
        if document is None:
            return False
        document.deleted_at = utc_now()
        document.status = "failed"
        document.status_stage = "failed"
        document.progress_percent = 100
        document.status_message = "Failed to enqueue ingestion task."
        document.status_updated_at = utc_now()
        await self.session.commit()
        return True

    async def reset_for_retry(self, document_id: str) -> dict | None:
        """Reset document status for retry. Returns updated dict or None."""
        document = await self.get_by_id(document_id)
        if document is None:
            return None
        document.status = "pending"
        document.status_stage = "queued"
        document.progress_percent = 5
        document.status_message = "Retrying: task queued for worker processing."
        document.parse_error = None
        document.status_updated_at = utc_now()
        await self.session.commit()
        await self.session.refresh(document)
        return self._to_dict(document)

    async def get_full_document(self, document_id: str, tenant_id: str | None = None) -> dict | None:
        """Get full document details including all fields."""
        document = await self.get_by_id(document_id)
        if document is None:
            return None
        if tenant_id and str(document.tenant_id) != tenant_id:
            return None
        return self._to_dict(document) if document else None

    async def finalize_ingestion(
        self,
        document_id: str,
        *,
        artifact_dict: dict,
        node_count: int,
        total_text_chars: int,
        progress_percent: int = 100,
    ) -> dict:
        """Set document to ready state with ingestion artifact metadata."""
        try:
            document = await self.get_by_id(document_id)
            if document is None or document.deleted_at is not None:
                return {}

            artifact_metadata = dict(document.artifact_metadata or {})
            artifact_metadata["ingestion_artifact"] = artifact_dict
            artifact_metadata["stats"] = {
                "node_count": node_count,
                "total_text_chars": total_text_chars,
            }
            document.artifact_metadata = artifact_metadata
            document.progress_percent = progress_percent
            document.status = "ready"
            document.status_stage = "ready"
            document.status_message = "Ingestion completed successfully."
            document.status_updated_at = utc_now()
            document.parse_error = None
            document.updated_at = utc_now()
            await self.session.commit()
            return self._to_dict(document)
        except Exception as e:
            await self.session.rollback()
            raise DocumentStoreException(
                f"Failed to finalize ingestion for {document_id}: {str(e)}",
                error_code="DOCUMENT_STORE_UPDATE_FAILED",
            )

    async def find_stuck_documents(self, timeout_threshold: datetime) -> list[str]:
        """Find documents stuck in processing state before timeout_threshold."""
        stmt = select(self.model).where(
            self.model.status == "processing", self.model.status_updated_at < timeout_threshold
        )
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        return [str(doc.id) for doc in rows]

    async def get_latest_active_document_ids(self, tenant_id: str | None = None) -> set[str]:
        """Return IDs of latest-version, non-deleted, ready documents."""
        latest_versions_stmt = select(
            self.model.file_name.label("file_name"),
            func.max(self.model.version).label("max_version"),
        ).where(self.model.deleted_at.is_(None), self.model.status == "ready")
        if tenant_id:
            latest_versions_stmt = latest_versions_stmt.where(self.model.tenant_id == tenant_id)
        latest_versions_stmt = latest_versions_stmt.group_by(self.model.file_name).subquery()

        stmt = (
            select(self.model.id)
            .join(
                latest_versions_stmt,
                and_(
                    self.model.file_name == latest_versions_stmt.c.file_name,
                    self.model.version == latest_versions_stmt.c.max_version,
                ),
            )
            .where(self.model.deleted_at.is_(None), self.model.status == "ready")
        )
        if tenant_id:
            stmt = stmt.where(self.model.tenant_id == tenant_id)
        result = await self.session.execute(stmt)
        rows = result.all()
        return {str(row[0]) for row in rows if row and row[0]}

    async def get_all_document_ids(self) -> list[str]:
        """Return all non-deleted document IDs for bulk operations."""
        stmt = select(self.model.id).where(self.model.deleted_at.is_(None))
        result = await self.session.execute(stmt)
        rows = result.all()
        return [str(row[0]) for row in rows if row and row[0]]

    async def get_titles_by_ids(self, doc_ids: list[str]) -> dict[str, str]:
        """Fetch document titles by IDs. Returns {doc_id: title}."""
        stmt = select(self.model.id, self.model.title).where(
            self.model.deleted_at.is_(None),
            self.model.status == "ready",
            self.model.id.in_(doc_ids),
        )
        result = await self.session.execute(stmt)
        rows = result.all()
        return {str(doc_id): title for doc_id, title in rows}

    async def update_title(self, document_id: str, new_title: str) -> bool:
        """Update document title after extracting from content."""
        try:
            document = await self.get_by_id(document_id)
            if document is None or document.deleted_at is not None:
                return False
            document.title = new_title
            document.updated_at = utc_now()
            await self.session.commit()
            logger.info("Document %s title updated: %s", document_id, new_title)
            return True
        except Exception as e:
            await self.session.rollback()
            raise DocumentStoreException(
                f"Failed to update title for {document_id}: {str(e)}",
                error_code="DOCUMENT_STORE_UPDATE_FAILED",
            )

    async def get_counts(self) -> dict[str, int]:
        """Get active and total document counts."""
        total_stmt = select(func.count(self.model.id)).where(self.model.deleted_at.is_(None))
        active_stmt = select(func.count(self.model.id)).where(
            self.model.deleted_at.is_(None), self.model.status == "ready"
        )
        total_result = await self.session.execute(total_stmt)
        active_result = await self.session.execute(active_stmt)
        return {
            "total_docs": total_result.scalar() or 0,
            "active_docs": active_result.scalar() or 0,
        }

    async def mark_as_deleted(self, document_id: str) -> bool:
        """Mark a document as deleted (soft-delete) before hard-delete begins."""
        try:
            document = await self.get_by_id(document_id)
            if document is None:
                return False
            document.deleted_at = utc_now()
            document.status = "deleted"
            document.status_stage = "deleted"
            document.status_updated_at = utc_now()
            document.updated_at = utc_now()
            await self.session.commit()
            logger.info("Document %s marked as deleted", document_id)
            return True
        except Exception as e:
            await self.session.rollback()
            raise DocumentStoreException(
                f"Failed to mark document {document_id} as deleted: {str(e)}",
                error_code="DOCUMENT_STORE_UPDATE_FAILED",
            )

    async def hard_delete(self, document_id: str) -> bool:
        """Hard-delete a document row from PostgreSQL."""
        document = await self.get_by_id(document_id)
        if document is None:
            return False
        await self.session.delete(document)
        await self.session.commit()
        return True

    def _to_dict(self, obj: Document) -> dict[str, Any]:
        """Custom override for Document to include stats from metadata."""
        if obj is None:
            return {}

        data = super()._to_dict(obj)
        # Re-map some fields to match the old API format if they were renamed
        data["id"] = str(obj.id)
        data["tenant_id"] = str(obj.tenant_id)
        data["artifact_metadata"] = obj.artifact_metadata or {}
        data["status_updated_at"] = to_vietnam_iso(obj.status_updated_at)
        data["deleted_at"] = to_vietnam_iso(obj.deleted_at)
        data["created_at"] = to_vietnam_iso(obj.created_at)
        data["updated_at"] = to_vietnam_iso(obj.updated_at)

        # Virtual fields from artifact_metadata
        stats = data["artifact_metadata"].get("stats", {})
        data["node_count"] = stats.get("node_count", 0)
        data["total_text_chars"] = stats.get("total_text_chars", 0)
        return data
