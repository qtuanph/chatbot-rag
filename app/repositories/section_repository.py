"""Repository for document sections in PostgreSQL."""

import logging

from sqlalchemy.orm import Session

from app.core.exceptions import DocumentStoreException
from app.models.document import DocumentSection

logger = logging.getLogger(__name__)


class SectionRepository:
    """Repository for document sections in PostgreSQL."""

    def __init__(self, session: Session):
        self.session = session

    def store_sections(self, document_id: str, sections: list[dict]) -> list[str]:
        """Bulk insert sections for a document. Returns list of section DB IDs.

        Uses savepoint so that a failure during insert preserves old sections.
        """
        try:
            self.session.query(DocumentSection).filter(DocumentSection.document_id == document_id).delete()
            savepoint = self.session.begin_nested()

            ids = []
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
                    extra_metadata=sec.get("metadata", {}),
                )
                self.session.add(db_section)

            self.session.flush()
            ids = [
                str(s.id)
                for s in self.session.query(DocumentSection).filter(DocumentSection.document_id == document_id).all()
            ]

            savepoint.commit()
            self.session.commit()
            logger.info("Stored %d sections for document %s", len(ids), document_id)
            return ids
        except Exception as e:
            self.session.rollback()
            raise DocumentStoreException(
                f"Failed to store sections for {document_id}: {str(e)}",
                error_code="SECTION_STORE_FAILED",
            )

    def get_sections_by_document(self, document_id: str) -> list[dict]:
        """Get all sections for a document, ordered by order_index."""
        rows = (
            self.session.query(DocumentSection)
            .filter(DocumentSection.document_id == document_id)
            .order_by(DocumentSection.order_index)
            .all()
        )
        return [self._section_to_dict(s) for s in rows]

    def get_sections_by_ids(self, document_id: str, section_ids: list[str]) -> list[dict]:
        """Get specific sections by section_id within a document."""
        rows = (
            self.session.query(DocumentSection)
            .filter(
                DocumentSection.document_id == document_id,
                DocumentSection.section_id.in_(section_ids),
            )
            .order_by(DocumentSection.order_index)
            .all()
        )
        return [self._section_to_dict(s) for s in rows]

    def get_section_by_section_id(self, document_id: str, section_id: str) -> dict | None:
        """Get a single section by section_id within a document."""
        row = (
            self.session.query(DocumentSection)
            .filter(
                DocumentSection.document_id == document_id,
                DocumentSection.section_id == section_id,
            )
            .one_or_none()
        )
        return self._section_to_dict(row) if row else None

    def search_sections_by_document(self, document_id: str, query: str) -> list[dict]:
        """Search sections by title or content within a document."""
        escaped = query.replace("%", r"\%").replace("_", r"\_")
        pattern = f"%{escaped}%"
        rows = (
            self.session.query(DocumentSection)
            .filter(
                DocumentSection.document_id == document_id,
                (DocumentSection.title.ilike(pattern) | DocumentSection.content.ilike(pattern)),
            )
            .order_by(DocumentSection.order_index)
            .all()
        )
        return [self._section_to_dict(s) for s in rows]

    def count_by_document(self, document_id: str) -> int:
        """Count sections for a document."""
        from sqlalchemy import func

        return (
            self.session.query(func.count(DocumentSection.id))
            .filter(DocumentSection.document_id == document_id)
            .scalar()
            or 0
        )

    def delete_sections(self, document_id: str) -> int:
        """Delete all sections for a document."""
        try:
            count = self.session.query(DocumentSection).filter(DocumentSection.document_id == document_id).delete()
            self.session.commit()
            logger.info("Deleted %d sections for document %s", count, document_id)
            return count
        except Exception as e:
            self.session.rollback()
            raise DocumentStoreException(
                f"Failed to delete sections for {document_id}: {str(e)}",
                error_code="SECTION_DELETE_FAILED",
            )

    def get_sections_for_rag(self, section_doc_pairs: list[tuple[str, str]]) -> list[dict]:
        """Get sections by (document_id, section_id) pairs for RAG retrieval.

        Prevents cross-product: section_ids like sec_0001 reset per document,
        so querying doc_ids × section_ids can return sections from wrong documents.
        """
        if not section_doc_pairs:
            return []
        from sqlalchemy import or_

        conditions = [
            (DocumentSection.document_id == doc_id) & (DocumentSection.section_id == sec_id)
            for doc_id, sec_id in section_doc_pairs
        ]
        rows = self.session.query(DocumentSection).filter(or_(*conditions)).all()
        return [self._section_to_dict(s) for s in rows]

    def get_section_ids_by_document(self, document_id: str) -> set[str]:
        """Get all section IDs for a document."""
        rows = self.session.query(DocumentSection.section_id).filter(DocumentSection.document_id == document_id).all()
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
            "metadata": section.extra_metadata or {},
        }
