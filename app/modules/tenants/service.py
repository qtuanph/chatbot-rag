from __future__ import annotations

import hashlib
import re
import secrets

from app.modules.auth.utils.auth import hash_password
from app.modules.tenants.repository import TenantRepository
from app.utils.datetime_utils import utc_now


class TenantService:
    def __init__(self, repo: TenantRepository, auth_repo=None) -> None:
        self.repo = repo
        self.auth_repo = auth_repo

    async def list_tenants(self) -> list[dict]:
        return await self.repo.list_tenants()

    async def get_tenant(self, tenant_id: str) -> dict:
        tenant = await self.repo.get_tenant(tenant_id)
        if tenant is None:
            raise ValueError("Tenant not found")
        return tenant

    async def create_tenant(self, data: dict) -> dict:
        slug = self._normalize_slug(data["slug"])
        if await self.repo.get_tenant_by_slug(slug):
            raise ValueError("Tenant slug already exists")
        clean = {
            "slug": slug,
            "name": data["name"].strip(),
            "description": (data.get("description") or "").strip() or None,
            "monthly_token_quota": int(data.get("monthly_token_quota", 0)),
            "monthly_request_quota": int(data.get("monthly_request_quota", 0)),
            "rate_limit_rpm": int(data.get("rate_limit_rpm", 60)),
            "allowed_origins": data.get("allowed_origins") or [],
        }
        return await self.repo.create_tenant(clean)

    async def create_tenant_with_admin(self, data: dict) -> dict:
        if self.auth_repo is None:
            raise RuntimeError("Auth repository is required for tenant provisioning")

        admin_username = (data.get("admin_username") or "").strip()
        admin_password = data.get("admin_password") or ""
        if not admin_username or not admin_password:
            raise ValueError("admin_username and admin_password are required")
        if len(admin_password) < 6:
            raise ValueError("Password must be at least 6 characters long")
        if await self.auth_repo.get_user_by_username(admin_username):
            raise ValueError("Username already exists")

        tenant_admin_role = await self.auth_repo.get_role_by_name("tenant_admin")
        if tenant_admin_role is None:
            raise ValueError("tenant_admin role is missing")

        slug = self._normalize_slug(data["slug"])
        if await self.repo.get_tenant_by_slug(slug):
            raise ValueError("Tenant slug already exists")

        clean = {
            "slug": slug,
            "name": data["name"].strip(),
            "description": (data.get("description") or "").strip() or None,
            "monthly_token_quota": int(data.get("monthly_token_quota", 0)),
            "monthly_request_quota": int(data.get("monthly_request_quota", 0)),
            "rate_limit_rpm": int(data.get("rate_limit_rpm", 60)),
            "allowed_origins": data.get("allowed_origins") or [],
        }

        try:
            tenant = await self.repo.create_tenant(clean, commit=False)
            await self.auth_repo.create_user_with_tenant(
                username=admin_username,
                password_hash=hash_password(admin_password),
                role_id=tenant_admin_role["id"],
                tenant_id=tenant["id"],
                commit=False,
            )
            await self.repo.session.commit()
            return tenant
        except Exception:
            await self.repo.session.rollback()
            raise

    async def update_tenant(self, tenant_id: str, data: dict) -> dict:
        existing = await self.repo.get_tenant(tenant_id)
        if existing is None:
            raise ValueError("Tenant not found")
        clean: dict = {}
        if "slug" in data and data["slug"] is not None:
            slug = self._normalize_slug(data["slug"])
            duplicate = await self.repo.get_tenant_by_slug(slug)
            if duplicate is not None and duplicate["id"] != tenant_id:
                raise ValueError("Tenant slug already exists")
            clean["slug"] = slug
        for key in (
            "name",
            "description",
            "status",
            "monthly_token_quota",
            "monthly_request_quota",
            "rate_limit_rpm",
            "allowed_origins",
        ):
            if key in data and data[key] is not None:
                clean[key] = data[key].strip() if isinstance(data[key], str) else data[key]
        updated = await self.repo.update_tenant(tenant_id, clean)
        if updated is None:
            raise ValueError("Tenant not found")
        return updated

    async def get_setting(self, tenant_id: str) -> dict:
        await self.get_tenant(tenant_id)
        setting = await self.repo.get_setting(tenant_id)
        if setting is None:
            return await self.repo.upsert_setting(
                tenant_id,
                {
                    "chatbot_display_name": "Assistant",
                    "welcome_message": "Xin chao, toi co the ho tro gi cho ban?",
                    "system_instruction": "",
                },
            )
        return setting

    async def update_setting(self, tenant_id: str, data: dict) -> dict:
        await self.get_tenant(tenant_id)
        clean = {key: value for key, value in data.items() if value is not None}
        return await self.repo.upsert_setting(tenant_id, clean)

    async def list_api_keys(self, tenant_id: str) -> list[dict]:
        await self.get_tenant(tenant_id)
        return await self.repo.list_api_keys(tenant_id)

    async def create_api_key(self, tenant_id: str, *, name: str, created_by: str, expires_at=None) -> dict:
        await self.get_tenant(tenant_id)
        raw_api_key = f"trg_{secrets.token_urlsafe(32)}"
        key_hash = hashlib.sha256(raw_api_key.encode("utf-8")).hexdigest()
        row = await self.repo.create_api_key(
            {
                "tenant_id": tenant_id,
                "name": name.strip(),
                "key_prefix": raw_api_key[:12],
                "key_hash": key_hash,
                "status": "active",
                "expires_at": expires_at,
                "created_by": created_by,
            }
        )
        row["raw_api_key"] = raw_api_key
        return row

    async def revoke_api_key(self, tenant_id: str, key_id: str) -> dict:
        await self.get_tenant(tenant_id)
        row = await self.repo.revoke_api_key(tenant_id, key_id, utc_now())
        if row is None:
            raise ValueError("API key not found")
        return row

    @staticmethod
    def _normalize_slug(value: str) -> str:
        normalized = re.sub(r"[^a-z0-9-]+", "-", value.strip().lower())
        normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
        if len(normalized) < 2:
            raise ValueError("Tenant slug is invalid")
        return normalized
