from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.modules.auth.deps import require_admin
from app.modules.auth.context import AuthContext
from app.modules.tenants.deps import get_tenant_service
from app.core import http_errors
from app.modules.tenants.schemas import (
    TenantApiKeyCreateRequest,
    TenantApiKeyCreateResponse,
    TenantApiKeyResponse,
    TenantCreateRequest,
    TenantResponse,
    TenantSettingResponse,
    TenantSettingUpdateRequest,
    TenantUpdateRequest,
)
from app.modules.tenants.service import TenantService

router = APIRouter(prefix="/admin/tenants", tags=["tenants"])


@router.get("", response_model=list[TenantResponse])
async def list_tenants(
    auth: AuthContext = Depends(require_admin),
    service: TenantService = Depends(get_tenant_service),
) -> list[TenantResponse]:
    rows = await service.list_tenants()
    return [TenantResponse(**row) for row in rows]


@router.post("", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    payload: TenantCreateRequest,
    auth: AuthContext = Depends(require_admin),
    service: TenantService = Depends(get_tenant_service),
) -> TenantResponse:
    try:
        data = payload.model_dump()
        if data.get("admin_username") and data.get("admin_password"):
            row = await service.create_tenant_with_admin(data)
        else:
            row = await service.create_tenant(data)
        return TenantResponse(**row)
    except ValueError as exc:
        msg = str(exc)
        if "already exists" in msg:
            raise http_errors.conflict(msg) from None
        raise http_errors.bad_request(msg) from None


@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: str,
    auth: AuthContext = Depends(require_admin),
    service: TenantService = Depends(get_tenant_service),
) -> TenantResponse:
    try:
        return TenantResponse(**(await service.get_tenant(tenant_id)))
    except ValueError as exc:
        raise http_errors.not_found(str(exc)) from None


@router.patch("/{tenant_id}", response_model=TenantResponse)
async def update_tenant(
    tenant_id: str,
    payload: TenantUpdateRequest,
    auth: AuthContext = Depends(require_admin),
    service: TenantService = Depends(get_tenant_service),
) -> TenantResponse:
    try:
        row = await service.update_tenant(tenant_id, payload.model_dump(exclude_unset=True))
        return TenantResponse(**row)
    except ValueError as exc:
        msg = str(exc)
        if "already exists" in msg:
            raise http_errors.conflict(msg) from None
        if "not found" in msg:
            raise http_errors.not_found(msg) from None
        raise http_errors.bad_request(msg) from None


@router.get("/{tenant_id}/settings", response_model=TenantSettingResponse)
async def get_tenant_setting(
    tenant_id: str,
    auth: AuthContext = Depends(require_admin),
    service: TenantService = Depends(get_tenant_service),
) -> TenantSettingResponse:
    try:
        return TenantSettingResponse(**(await service.get_setting(tenant_id)))
    except ValueError as exc:
        raise http_errors.not_found(str(exc)) from None


@router.put("/{tenant_id}/settings", response_model=TenantSettingResponse)
async def update_tenant_setting(
    tenant_id: str,
    payload: TenantSettingUpdateRequest,
    auth: AuthContext = Depends(require_admin),
    service: TenantService = Depends(get_tenant_service),
) -> TenantSettingResponse:
    try:
        row = await service.update_setting(tenant_id, payload.model_dump(exclude_unset=True))
        return TenantSettingResponse(**row)
    except ValueError as exc:
        raise http_errors.not_found(str(exc)) from None


@router.get("/{tenant_id}/api-keys", response_model=list[TenantApiKeyResponse])
async def list_tenant_api_keys(
    tenant_id: str,
    auth: AuthContext = Depends(require_admin),
    service: TenantService = Depends(get_tenant_service),
) -> list[TenantApiKeyResponse]:
    try:
        rows = await service.list_api_keys(tenant_id)
        return [TenantApiKeyResponse(**row) for row in rows]
    except ValueError as exc:
        raise http_errors.not_found(str(exc)) from None


@router.post("/{tenant_id}/api-keys", response_model=TenantApiKeyCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant_api_key(
    tenant_id: str,
    payload: TenantApiKeyCreateRequest,
    auth: AuthContext = Depends(require_admin),
    service: TenantService = Depends(get_tenant_service),
) -> TenantApiKeyCreateResponse:
    try:
        row = await service.create_api_key(
            tenant_id,
            name=payload.name,
            created_by=auth.user_id,
            expires_at=payload.expires_at,
        )
        return TenantApiKeyCreateResponse(**row)
    except ValueError as exc:
        raise http_errors.not_found(str(exc)) from None


@router.delete("/{tenant_id}/api-keys/{key_id}", response_model=TenantApiKeyResponse)
async def revoke_tenant_api_key(
    tenant_id: str,
    key_id: str,
    auth: AuthContext = Depends(require_admin),
    service: TenantService = Depends(get_tenant_service),
) -> TenantApiKeyResponse:
    try:
        row = await service.revoke_api_key(tenant_id, key_id)
        return TenantApiKeyResponse(**row)
    except ValueError as exc:
        msg = str(exc)
        if "not found" in msg:
            raise http_errors.not_found(msg) from None
        raise http_errors.bad_request(msg) from None
