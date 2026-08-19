from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, DateTime, Float, Index, Integer, String, func, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AiModelUsage(Base):
    __tablename__ = "ai_model_usage"
    __table_args__ = (Index("ix_usage_tenant_created", "tenant_id", "created_at"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    model_type: Mapped[str] = mapped_column(String(20), nullable=False, default="llm", server_default="llm")
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_micros_vnd: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default=text("0"))
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False, default="VND", server_default="VND")
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, server_default=text("0"))
    endpoint: Mapped[str] = mapped_column(String(100), nullable=False)
    tenant_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    user_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    is_cache_hit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    cached_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
