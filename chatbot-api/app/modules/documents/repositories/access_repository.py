from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant import Tenant
from app.models.tenant_document_access import TenantDocumentAccess

logger = logging.getLogger(__name__)


class DocumentAccessRepository:
    """Repository for tenant_document_access permission mapping in PostgreSQL."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_tenant_ids_for_document(self, document_id: str) -> list[str]:
        """Get list of tenant UUIDs granted access to a document."""
        doc_uuid = UUID(document_id)
        stmt = select(TenantDocumentAccess.tenant_id).where(TenantDocumentAccess.document_id == doc_uuid)
        result = await self.session.execute(stmt)
        return [str(row[0]) for row in result.all()]

    async def get_tenants_with_name_for_document(self, document_id: str) -> list[dict[str, str]]:
        """Get list of tenants with id and name granted access to a document."""
        doc_uuid = UUID(document_id)
        stmt = (
            select(Tenant.id, Tenant.name)
            .join(TenantDocumentAccess, Tenant.id == TenantDocumentAccess.tenant_id)
            .where(TenantDocumentAccess.document_id == doc_uuid)
            .order_by(Tenant.name.asc())
        )
        result = await self.session.execute(stmt)
        return [{"id": str(row[0]), "name": row[1]} for row in result.all()]

    async def get_document_ids_for_tenant(self, tenant_id: str) -> list[str]:
        """Get list of document UUIDs accessible by a given tenant."""
        tenant_uuid = UUID(tenant_id)
        stmt = select(TenantDocumentAccess.document_id).where(TenantDocumentAccess.tenant_id == tenant_uuid)
        result = await self.session.execute(stmt)
        return [str(row[0]) for row in result.all()]

    async def set_tenants_for_document(
        self, document_id: str, tenant_ids: list[str], granted_by: str | None = None
    ) -> list[dict[str, str]]:
        """Replace all tenant access entries for a document with the provided tenant_ids."""
        doc_uuid = UUID(document_id)
        granted_by_uuid = UUID(granted_by) if granted_by else None

        # Delete existing entries
        del_stmt = delete(TenantDocumentAccess).where(TenantDocumentAccess.document_id == doc_uuid)
        await self.session.execute(del_stmt)

        # Insert new entries
        unique_tenant_ids = list(set(tenant_ids))
        for t_id in unique_tenant_ids:
            new_entry = TenantDocumentAccess(
                tenant_id=UUID(t_id),
                document_id=doc_uuid,
                granted_by=granted_by_uuid,
            )
            self.session.add(new_entry)

        await self.session.commit()
        return await self.get_tenants_with_name_for_document(document_id)
