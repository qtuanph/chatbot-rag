"""Escalation model."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Escalation(Base):
    __tablename__ = "escalations"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    conversation_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    citations: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"), nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    user_consent: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), server_default=text("'open'"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
