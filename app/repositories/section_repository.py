import logging

from sqlalchemy import func, select, delete, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DocumentStoreException
from app.models.document import DocumentSection

logger = logging.getLogger(__name__)


class SectionRepository:
    """Repository for document sections in PostgreSQL."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def store_sections(self, document_id: str, sections: list[dict]) -> list[str]:
        """Bulk insert sections for a document. Returns list of section DB IDs.

        Uses savepoint so that a failure during insert preserves old sections.
        """
        try:
            # Delete old sections
            await self.session.execute(delete(DocumentSection).where(DocumentSection.document_id == document_id))
            
            async with self.session.begin_nested() as savepoint:
                for sec in sections:
                    db_section = DocumentSection(
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
                        extra_metadata=sec.get("artifact_metadata", {}),
                    )
                    self.session.add(db_section)

                await self.session.flush()
                await savepoint.commit()

            await self.session.commit()
            
            # Fetch new IDs
            stmt = select(DocumentSection.id).where(DocumentSection.document_id == document_id)
            result = await self.session.execute(stmt)
            ids = [str(row[0]) for row in result.all()]
            
            logger.info("Stored %d sections for document %s", len(ids), document_id)
            return ids
        except Exception as e:
            await self.session.rollback()
            raise DocumentStoreException(
                f"Failed to store sections for {document_id}: {str(e)}",
                error_code="SECTION_STORE_FAILED",
            )

    async def get_sections_by_document(self, document_id: str) -> list[dict]:
        """Get all sections for a document, ordered by order_index."""
        stmt = (
            select(DocumentSection)
            .where(DocumentSection.document_id == document_id)
            .order_by(DocumentSection.order_index)
        )
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        return [self._section_to_dict(s) for s in rows]

    async def get_sections_by_ids(self, document_id: str, section_ids: list[str]) -> list[dict]:
        """Get specific sections by section_id within a document."""
        stmt = (
            select(DocumentSection)
            .where(
                DocumentSection.document_id == document_id,
                DocumentSection.section_id.in_(section_ids),
            )
            .order_by(DocumentSection.order_index)
        )
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        return [self._section_to_dict(s) for s in rows]

    async def get_section_by_section_id(self, document_id: str, section_id: str) -> dict | None:
        """Get a single section by section_id within a document."""
        stmt = (
            select(DocumentSection)
            .where(
                DocumentSection.document_id == document_id,
                DocumentSection.section_id == section_id,
            )
        )
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        return self._section_to_dict(row) if row else None

    async def search_sections_by_document(self, document_id: str, query: str) -> list[dict]:
        """Search sections by title or content within a document."""
        escaped = query.replace("%", r"\%").replace("_", r"\_")
        pattern = f"%{escaped}%"
        stmt = (
            select(DocumentSection)
            .where(
                DocumentSection.document_id == document_id,
                (DocumentSection.title.ilike(pattern) | DocumentSection.content.ilike(pattern)),
            )
            .order_by(DocumentSection.order_index)
        )
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        return [self._section_to_dict(s) for s in rows]

    async def count_by_document(self, document_id: str) -> int:
        """Count sections for a document."""
        stmt = select(func.count(DocumentSection.id)).where(DocumentSection.document_id == document_id)
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def delete_sections(self, document_id: str) -> int:
        """Delete all sections for a document."""
        try:
            stmt = delete(DocumentSection).where(DocumentSection.document_id == document_id)
            result = await self.session.execute(stmt)
            await self.session.commit()
            count = result.rowcount
            logger.info("Deleted %d sections for document %s", count, document_id)
            return count
        except Exception as e:
            await self.session.rollback()
            raise DocumentStoreException(
                f"Failed to delete sections for {document_id}: {str(e)}",
                error_code="SECTION_DELETE_FAILED",
            )

    async def get_sections_for_rag(self, section_doc_pairs: list[tuple[str, str]]) -> list[dict]:
        """Get sections by (document_id, section_id) pairs for RAG retrieval."""
        if not section_doc_pairs:
            return []
        
        conditions = [
            (DocumentSection.document_id == doc_id) & (DocumentSection.section_id == sec_id)
            for doc_id, sec_id in section_doc_pairs
        ]
        stmt = select(DocumentSection).where(or_(*conditions))
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        return [self._section_to_dict(s) for s in rows]

    async def get_section_ids_by_document(self, document_id: str) -> set[str]:
        """Get all section IDs for a document."""
        stmt = select(DocumentSection.section_id).where(DocumentSection.document_id == document_id)
        result = await self.session.execute(stmt)
        rows = result.all()
        return {str(row[0]) for row in rows}

    # ── Private helpers ──────────────────────────────────────────────

    @staticmethod
    def _section_to_dict(section: DocumentSection) -> dict:
        return {
            "id": str(section.id),
            "document_id": str(section.document_id),
            "section_id": section.section_id,
            "parent_section_id": section.parent_section_id,
            "title": section.title,
            "content": section.content,
            "section_type": section.section_type,
            "level": section.level,
            "order_index": section.order_index,
            "page_range": section.page_range,
            "image_count": section.image_count,
            "table_count": section.table_count,
            "chunk_count": section.chunk_count,
            "breadcrumb": section.breadcrumb or [],
            "artifact_metadata": section.extra_metadata or {},
        }

    # ── Private helpers ──────────────────────────────────────────────

    @staticmethod
    def _section_to_dict(section: DocumentSection) -> dict:
        return {
            "id": str(section.id),
            "document_id": str(section.document_id),
            "section_id": section.section_id,
            "parent_section_id": section.parent_section_id,
            "title": section.title,
            "content": section.content,
            "section_type": section.section_type,
            "level": section.level,
            "order_index": section.order_index,
            "page_range": section.page_range,
            "image_count": section.image_count,
            "table_count": section.table_count,
            "chunk_count": section.chunk_count,
            "breadcrumb": section.breadcrumb or [],
            "artifact_metadata": section.extra_metadata or {},
        }
