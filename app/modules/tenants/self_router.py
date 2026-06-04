from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import AuthContext, get_auth_context, get_tenant_service
from app.core import http_errors
from app.modules.tenants.schemas import TenantResponse, TenantSettingResponse, TenantSettingUpdateRequest
from app.modules.tenants.service import TenantService

router = APIRouter(prefix="/tenants/me", tags=["tenant-self"])


def _require_tenant_context(auth: AuthContext) -> str:
    if auth.role != "tenant_admin" or not auth.tenant_id:
        raise http_errors.forbidden("Tenant admin access required")
    return auth.tenant_id


@router.get("", response_model=TenantResponse)
async def get_my_tenant(
    auth: AuthContext = Depends(get_auth_context),
    service: TenantService = Depends(get_tenant_service),
) -> TenantResponse:
    tenant_id = _require_tenant_context(auth)
    try:
        return TenantResponse(**(await service.get_tenant(tenant_id)))
    except ValueError as exc:
        raise http_errors.not_found(str(exc)) from None


@router.get("/settings", response_model=TenantSettingResponse)
async def get_my_tenant_setting(
    auth: AuthContext = Depends(get_auth_context),
    service: TenantService = Depends(get_tenant_service),
) -> TenantSettingResponse:
    tenant_id = _require_tenant_context(auth)
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
    tenant_id = _require_tenant_context(auth)
    try:
        return TenantSettingResponse(**(await service.update_setting(tenant_id, payload.model_dump(exclude_unset=True))))
    except ValueError as exc:
        raise http_errors.not_found(str(exc)) from None
