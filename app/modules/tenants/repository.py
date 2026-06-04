from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant import Tenant, TenantApiKey, TenantSetting
from app.utils.datetime_utils import to_vietnam_datetime


class TenantRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_tenants(self) -> list[dict]:
        stmt = select(Tenant).order_by(Tenant.created_at.desc())
        rows = (await self.session.execute(stmt)).scalars().all()
        return [self._tenant_to_dict(row) for row in rows]

    async def get_tenant(self, tenant_id: str) -> dict | None:
        row = await self.session.get(Tenant, tenant_id)
        return self._tenant_to_dict(row) if row else None

    async def get_tenant_by_slug(self, slug: str) -> dict | None:
        stmt = select(Tenant).where(Tenant.slug == slug)
        row = (await self.session.execute(stmt)).scalar_one_or_none()
        return self._tenant_to_dict(row) if row else None

    async def create_tenant(self, data: dict[str, Any], *, commit: bool = True) -> dict:
        tenant = Tenant(**data)
        self.session.add(tenant)
        if commit:
            await self.session.commit()
        else:
            await self.session.flush()
        await self.session.refresh(tenant)
        return self._tenant_to_dict(tenant)

    async def update_tenant(self, tenant_id: str, data: dict[str, Any]) -> dict | None:
        tenant = await self.session.get(Tenant, tenant_id)
        if tenant is None:
            return None
        for key, value in data.items():
            setattr(tenant, key, value)
        await self.session.commit()
        await self.session.refresh(tenant)
        return self._tenant_to_dict(tenant)

    async def get_setting(self, tenant_id: str) -> dict | None:
        stmt = select(TenantSetting).where(TenantSetting.tenant_id == tenant_id)
        row = (await self.session.execute(stmt)).scalar_one_or_none()
        return self._setting_to_dict(row) if row else None

    async def upsert_setting(self, tenant_id: str, data: dict[str, Any]) -> dict:
        stmt = select(TenantSetting).where(TenantSetting.tenant_id == tenant_id)
        setting = (await self.session.execute(stmt)).scalar_one_or_none()
        if setting is None:
            setting = TenantSetting(tenant_id=tenant_id, **data)
            self.session.add(setting)
        else:
            for key, value in data.items():
                setattr(setting, key, value)
        await self.session.commit()
        await self.session.refresh(setting)
        return self._setting_to_dict(setting)

    async def list_api_keys(self, tenant_id: str) -> list[dict]:
        stmt = select(TenantApiKey).where(TenantApiKey.tenant_id == tenant_id).order_by(TenantApiKey.created_at.desc())
        rows = (await self.session.execute(stmt)).scalars().all()
        return [self._api_key_to_dict(row) for row in rows]

    async def create_api_key(self, data: dict[str, Any]) -> dict:
        row = TenantApiKey(**data)
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return self._api_key_to_dict(row)

    async def get_active_api_key_by_hash(self, key_hash: str) -> dict | None:
        stmt = select(TenantApiKey).where(TenantApiKey.key_hash == key_hash)
        row = (await self.session.execute(stmt)).scalar_one_or_none()
        return self._api_key_to_dict(row) if row else None

    async def touch_api_key_last_used(self, key_id: str, last_used_at) -> None:
        row = await self.session.get(TenantApiKey, key_id)
        if row is None:
            return
        row.last_used_at = last_used_at
        await self.session.commit()

    async def revoke_api_key(self, tenant_id: str, key_id: str, revoked_at) -> dict | None:
        row = await self.session.get(TenantApiKey, key_id)
        if row is None or str(row.tenant_id) != tenant_id:
            return None
        row.status = "revoked"
        row.revoked_at = revoked_at
        await self.session.commit()
        await self.session.refresh(row)
        return self._api_key_to_dict(row)

    @staticmethod
    def _tenant_to_dict(row: Tenant) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "slug": row.slug,
            "name": row.name,
            "status": row.status,
            "description": row.description,
            "monthly_token_quota": row.monthly_token_quota,
            "monthly_request_quota": row.monthly_request_quota,
            "rate_limit_rpm": row.rate_limit_rpm,
            "allowed_origins": list(row.allowed_origins or []),
            "created_at": to_vietnam_datetime(row.created_at),
            "updated_at": to_vietnam_datetime(row.updated_at),
        }

    @staticmethod
    def _setting_to_dict(row: TenantSetting) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "tenant_id": str(row.tenant_id),
            "chatbot_display_name": row.chatbot_display_name,
            "welcome_message": row.welcome_message,
            "system_instruction": row.system_instruction,
            "updated_at": to_vietnam_datetime(row.updated_at),
        }

    @staticmethod
    def _api_key_to_dict(row: TenantApiKey) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "tenant_id": str(row.tenant_id),
            "name": row.name,
            "key_prefix": row.key_prefix,
            "status": row.status,
            "expires_at": to_vietnam_datetime(row.expires_at),
            "last_used_at": to_vietnam_datetime(row.last_used_at),
            "revoked_at": to_vietnam_datetime(row.revoked_at),
            "created_at": to_vietnam_datetime(row.created_at),
        }
