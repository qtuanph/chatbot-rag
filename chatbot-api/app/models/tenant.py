from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.auth import TimestampMixin


class Tenant(Base, TimestampMixin):
    __tablename__ = "tenants"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_tenants_slug"),
        Index("ix_tenants_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default=text("'active'"))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    monthly_token_quota: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    monthly_request_quota: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    rate_limit_rpm: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("60"))
    allowed_origins: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))


class TenantApiKey(Base):
    __tablename__ = "tenant_api_keys"
    __table_args__ = (
        Index("ix_tenant_api_keys_tenant_id", "tenant_id"),
        Index("ix_tenant_api_keys_status", "status"),
        UniqueConstraint("key_hash", name="uq_tenant_api_keys_key_hash"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(32), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default=text("'active'"))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class TenantSetting(Base, TimestampMixin):
    __tablename__ = "tenant_settings"
    __table_args__ = (UniqueConstraint("tenant_id", name="uq_tenant_settings_tenant_id"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    system_instruction: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
