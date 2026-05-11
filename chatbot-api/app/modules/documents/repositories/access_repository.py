from __future__ import annotations

import json
import logging
from typing import Any
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

    async def get_document_ids_for_tenant(self, tenant_id: str, redis: Any = None) -> list[str]:
        """Get list of document UUIDs accessible by a given tenant with Redis L1 caching (< 0.5ms latency)."""
        cache_key = f"doc_access:{tenant_id}"
        if redis:
            try:
                cached = await redis.get(cache_key)
                if cached:
                    return json.loads(cached)
            except Exception as exc:
                logger.warning("Redis get_document_ids_for_tenant cache read error: %s", exc)

        tenant_uuid = UUID(tenant_id)
        stmt = select(TenantDocumentAccess.document_id).where(TenantDocumentAccess.tenant_id == tenant_uuid)
        result = await self.session.execute(stmt)
        doc_ids = [str(row[0]) for row in result.all()]

        if redis and doc_ids:
            try:
                await redis.setex(cache_key, 3600, json.dumps(doc_ids))
            except Exception as exc:
                logger.warning("Redis get_document_ids_for_tenant cache write error: %s", exc)

        return doc_ids

    async def get_tenants_for_documents(self, document_ids: list[str]) -> dict[str, list[dict[str, str]]]:
        """Batch fetch tenants for multiple documents in a single SQL query (prevents N+1 query lag)."""
        if not document_ids:
            return {}
        doc_uuids = [UUID(d) for d in document_ids]
        stmt = (
            select(TenantDocumentAccess.document_id, Tenant.id, Tenant.name)
            .join(Tenant, Tenant.id == TenantDocumentAccess.tenant_id)
            .where(TenantDocumentAccess.document_id.in_(doc_uuids))
            .order_by(Tenant.name.asc())
        )
        result = await self.session.execute(stmt)
        mapping: dict[str, list[dict[str, str]]] = {d: [] for d in document_ids}
        for row in result.all():
            doc_id_str = str(row[0])
            if doc_id_str in mapping:
                mapping[doc_id_str].append({"id": str(row[1]), "name": row[2]})
        return mapping

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
