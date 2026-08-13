from __future__ import annotations

from fastapi import APIRouter, Depends

from app.modules.auth.deps import get_auth_context
from app.modules.auth.context import AuthContext
from app.modules.tenants.deps import get_tenant_service
from app.core import http_errors
from app.modules.tenants.schemas import TenantResponse, TenantSettingResponse, TenantSettingUpdateRequest
from app.modules.tenants.service import TenantService

router = APIRouter(prefix="/tenants/me", tags=["tenant-self"])


async def _resolve_tenant_id(auth: AuthContext, service: TenantService) -> str:
    if auth.tenant_id:
        return auth.tenant_id
    if auth.role == "platform_admin":
        # C-06: platform_admin has no personal tenant — /tenants/me is meaningless for them.
        # Previously this silently grabbed tenants[0] which could corrupt another tenant's config.
        raise http_errors.forbidden(
            "platform_admin has no personal tenant. Use /admin/tenants/{tenant_id} endpoints instead."
        )
    raise http_errors.forbidden("Tenant access required")


@router.get("", response_model=TenantResponse)
async def get_my_tenant(
    auth: AuthContext = Depends(get_auth_context),
    service: TenantService = Depends(get_tenant_service),
) -> TenantResponse:
    tenant_id = await _resolve_tenant_id(auth, service)
    try:
        return TenantResponse(**(await service.get_tenant(tenant_id)))
    except ValueError as exc:
        raise http_errors.not_found(str(exc)) from None


@router.get("/settings", response_model=TenantSettingResponse)
async def get_my_tenant_setting(
    auth: AuthContext = Depends(get_auth_context),
    service: TenantService = Depends(get_tenant_service),
) -> TenantSettingResponse:
    tenant_id = await _resolve_tenant_id(auth, service)
    try:
        return TenantSettingResponse(**(await service.get_setting(tenant_id)))
    except ValueError as exc:
        raise http_errors.not_found(str(exc)) from None


@router.put("/settings", response_model=TenantSettingResponse)
async def update_my_tenant_setting(
    payload: TenantSettingUpdateRequest,
    auth: AuthContext = Depends(get_auth_context),
    service: TenantService = Depends(get_tenant_service),
) -> TenantSettingResponse:
    tenant_id = await _resolve_tenant_id(auth, service)
    try:
        return TenantSettingResponse(
            **(await service.update_setting(tenant_id, payload.model_dump(exclude_unset=True)))
        )
    except ValueError as exc:
        raise http_errors.not_found(str(exc)) from None
