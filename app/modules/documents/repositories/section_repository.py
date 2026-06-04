import logging
from typing import Any

from sqlalchemy import func, select, delete, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DocumentStoreException
from app.models.document import DocumentSection
from app.modules.documents.base import BaseRepository

logger = logging.getLogger(__name__)


class SectionRepository(BaseRepository[DocumentSection]):
    """Repository for document sections in PostgreSQL."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, DocumentSection)

    async def store_sections(self, document_id: str, tenant_id: str, sections: list[dict[str, Any]]) -> list[str]:
        """Bulk insert sections for a document. Returns list of section DB IDs."""
        try:
            # Delete old sections first (atomic within outer transaction if applicable)
            await self.session.execute(delete(self.model).where(self.model.document_id == document_id))

            async with self.session.begin_nested() as savepoint:
                for sec in sections:
                    db_section = self.model(
                        tenant_id=tenant_id,
                        document_id=document_id,
                        section_id=sec["section_id"],
                        parent_section_id=sec.get("parent_section_id"),
                        title=sec["title"],
                        content=sec.get("content"),
                        section_type=sec.get("section_type", "section"),
                        level=sec.get("level", 1),
                        order_index=sec.get("order_index", 0),
                        page_range=sec.get("page_range"),
                        image_count=sec.get("image_count", 0),
                        table_count=sec.get("table_count", 0),
                        chunk_count=sec.get("chunk_count", 0),
                        breadcrumb=sec.get("breadcrumb", []),
                        artifact_metadata=sec.get("artifact_metadata", {}),
                    )
                    self.session.add(db_section)

                await self.session.flush()
                await savepoint.commit()

            await self.session.commit()

            # Fetch new IDs
            stmt = select(self.model.id).where(self.model.document_id == document_id)
            result = await self.session.execute(stmt)
            ids = [str(row[0]) for row in result.all()]

            logger.info("Stored %d sections for document %s", len(ids), document_id)
            return ids
        except Exception as e:
            await self.session.rollback()
            logger.error("Failed to store sections for %s: %s", document_id, e, exc_info=True)
            raise DocumentStoreException(
                f"Failed to store sections for {document_id}: {str(e)}",
                error_code="SECTION_STORE_FAILED",
            )

    async def get_sections_by_document(self, document_id: str) -> list[dict[str, Any]]:
        """Get all sections for a document, ordered by order_index."""
        stmt = select(self.model).where(self.model.document_id == document_id).order_by(self.model.order_index)
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        return [self._to_dict(s) for s in rows]

    async def get_sections_by_document_paginated(
        self, document_id: str, offset: int = 0, limit: int = 20
    ) -> tuple[list[dict[str, Any]], int]:
        """Get sections for a document with pagination."""
        count_stmt = select(func.count(self.model.id)).where(self.model.document_id == document_id)
        total = (await self.session.execute(count_stmt)).scalar() or 0

        data_stmt = (
            select(self.model)
            .where(self.model.document_id == document_id)
            .order_by(self.model.order_index)
            .offset(offset)
            .limit(limit)
        )
        rows = (await self.session.execute(data_stmt)).scalars().all()
        return [self._to_dict(s) for s in rows], total

    async def get_sections_by_ids(self, document_id: str, section_ids: list[str]) -> list[dict[str, Any]]:
        """Get specific sections by section_id within a document."""
        stmt = (
            select(self.model)
            .where(
                self.model.document_id == document_id,
                self.model.section_id.in_(section_ids),
            )
            .order_by(self.model.order_index)
        )
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        return [self._to_dict(s) for s in rows]

    async def get_section_by_section_id(self, document_id: str, section_id: str) -> dict[str, Any] | None:
        """Get a single section by section_id."""
        stmt = select(self.model).where(
            self.model.document_id == document_id,
            self.model.section_id == section_id,
        )
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        return self._to_dict(row) if row else None

    async def search_sections_by_document(self, document_id: str, query: str) -> list[dict[str, Any]]:
        """Search sections by title or content."""
        escaped = query.replace("%", r"\%").replace("_", r"\_")
        pattern = f"%{escaped}%"
        stmt = (
            select(self.model)
            .where(
                self.model.document_id == document_id,
                (self.model.title.ilike(pattern) | self.model.content.ilike(pattern)),
            )
            .order_by(self.model.order_index)
        )
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        return [self._to_dict(s) for s in rows]

    async def delete_sections(self, document_id: str) -> int:
        """Delete all sections for a document."""
        try:
            stmt = delete(self.model).where(self.model.document_id == document_id)
            result = await self.session.execute(stmt)
            await self.session.commit()
            return result.rowcount
        except Exception as e:
            await self.session.rollback()
            raise DocumentStoreException(
                f"Failed to delete sections for {document_id}: {str(e)}",
                error_code="SECTION_DELETE_FAILED",
            )

    async def get_sections_for_rag(self, section_doc_pairs: list[tuple[str, str]]) -> list[dict[str, Any]]:
        """Get sections by (document_id, section_id) pairs for RAG."""
        if not section_doc_pairs:
            return []

        conditions = [
            (self.model.document_id == doc_id) & (self.model.section_id == sec_id)
            for doc_id, sec_id in section_doc_pairs
        ]
        stmt = select(self.model).where(or_(*conditions))
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        return [self._to_dict(s) for s in rows]

    async def get_section_ids_by_document(self, document_id: str) -> set[str]:
        """Get all section IDs for a document."""
        stmt = select(self.model.section_id).where(self.model.document_id == document_id)
        result = await self.session.execute(stmt)
        rows = result.all()
        return {str(row[0]) for row in rows}

    def _to_dict(self, section: DocumentSection) -> dict[str, Any]:
        """Custom override for DocumentSection conversion."""
        if section is None:
            return {}
        data = super()._to_dict(section)
        data["id"] = str(section.id)
        data["tenant_id"] = str(section.tenant_id)
        data["document_id"] = str(section.document_id)
        data["breadcrumb"] = section.breadcrumb or []
        data["artifact_metadata"] = section.artifact_metadata or {}
        return data
