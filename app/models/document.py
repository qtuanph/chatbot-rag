from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.auth import TimestampMixin


class Document(Base, TimestampMixin):
    __tablename__ = "documents"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    file_name: Mapped[str] = mapped_column(String(500), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    status: Mapped[str] = mapped_column(String(50), nullable=False, server_default=text("'pending'"))
    status_stage: Mapped[str] = mapped_column(String(50), nullable=False, server_default=text("'uploaded'"))
    progress_percent: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    status_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    parse_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    artifact_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb"), name="metadata"
    )
    created_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DocumentSection(Base, TimestampMixin):
    """Level 1 hierarchical storage for 2-stage retrieval (RAG v2)."""

    __tablename__ = "document_sections"

    __table_args__ = (UniqueConstraint("document_id", "section_id", name="uq_document_section"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    section_id: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_section_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str] = mapped_column(String(1000), nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    section_type: Mapped[str] = mapped_column(String(50), server_default=text("'section'"))
    level: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    order_index: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    page_range: Mapped[str | None] = mapped_column(String(100), nullable=True)
    image_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    table_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    chunk_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    breadcrumb: Mapped[dict] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    artifact_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb"), name="metadata"
    )
