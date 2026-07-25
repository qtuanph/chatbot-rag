"""Product and ProductVersion models."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.auth import TimestampMixin


class Product(Base, TimestampMixin):
    __tablename__ = "products"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), nullable=False)


class ProductVersion(Base):
    __tablename__ = "product_versions"
    __table_args__ = (UniqueConstraint("product_id", "version_code", name="uq_product_version"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    product_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    version_code: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), nullable=False)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class TenantProduct(Base):
    __tablename__ = "tenant_products"
    __table_args__ = (UniqueConstraint("tenant_id", "product_version_id", name="uq_tenant_product_version"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    product_version_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("product_versions.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'active'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
