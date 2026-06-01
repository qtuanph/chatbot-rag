from fastapi import APIRouter, Depends

from app.modules.settings.schemas import (
    ApiKeyCreate,
    ApiKeyResponse,
    ProviderCreate,
    ProviderResponse,
    ProviderTemplate,
    ProviderUpdate,
    TestResult,
    BillingSettingsResponse,
    BillingSettingsUpdate,
)
from app.modules.settings.service import SettingsService
from app.modules.auth.deps import require_admin

router = APIRouter(prefix="/settings", tags=["settings"])


def get_settings_service() -> SettingsService:
    return SettingsService()


# ── Templates ──────────────────────────────────────────────────────


@router.get("/templates", response_model=list[ProviderTemplate])
async def list_templates(_auth=Depends(require_admin), service: SettingsService = Depends(get_settings_service)):
    return service.get_templates()


# ── Providers ──────────────────────────────────────────────────────


@router.get("/providers", response_model=list[ProviderResponse])
async def list_providers(
    service_type: str | None = None,
    _auth=Depends(require_admin),
    service: SettingsService = Depends(get_settings_service),
):
    return service.list_providers(service_type)


@router.post("/providers", response_model=ProviderResponse, status_code=201)
async def create_provider(
    data: ProviderCreate,
    _auth=Depends(require_admin),
    service: SettingsService = Depends(get_settings_service),
):
    return service.create_provider(data)


@router.get("/providers/{provider_id}", response_model=ProviderResponse)
async def get_provider(
    provider_id: int,
    _auth=Depends(require_admin),
    service: SettingsService = Depends(get_settings_service),
):
    provider = service.get_provider(provider_id)
    if not provider:
        from app.core import http_errors

        raise http_errors.not_found("Provider not found")
    return provider


@router.put("/providers/{provider_id}", response_model=ProviderResponse)
async def update_provider(
    provider_id: int,
    data: ProviderUpdate,
    _auth=Depends(require_admin),
    service: SettingsService = Depends(get_settings_service),
):
    provider = service.update_provider(provider_id, data)
    if not provider:
        from app.core import http_errors

        raise http_errors.not_found("Provider not found")
    from app.modules.settings.runtime_manager import RuntimeProviderManager

    RuntimeProviderManager.get_instance().reload()
    return provider


@router.delete("/providers/{provider_id}")
async def delete_provider(
    provider_id: int,
    _auth=Depends(require_admin),
    service: SettingsService = Depends(get_settings_service),
):
    ok = service.delete_provider(provider_id)
    if not ok:
        from app.core import http_errors

        raise http_errors.bad_request("Cannot delete built-in provider or not found")
    return {"status": "deleted"}


@router.post("/providers/{provider_id}/activate", response_model=ProviderResponse)
async def activate_provider(
    provider_id: int,
    _auth=Depends(require_admin),
    service: SettingsService = Depends(get_settings_service),
):
    provider = service.activate_provider(provider_id)
    if not provider:
        from app.core import http_errors

        raise http_errors.not_found("Provider not found")
    from app.modules.settings.runtime_manager import RuntimeProviderManager

    RuntimeProviderManager.get_instance().reload()
    return provider


@router.post("/providers/{provider_id}/deactivate", response_model=ProviderResponse)
async def deactivate_provider(
    provider_id: int,
    _auth=Depends(require_admin),
    service: SettingsService = Depends(get_settings_service),
):
    provider = service.deactivate_provider(provider_id)
    if not provider:
        from app.core import http_errors

        raise http_errors.not_found("Provider not found")
    from app.modules.settings.runtime_manager import RuntimeProviderManager

    RuntimeProviderManager.get_instance().reload()
    return provider


@router.post("/providers/{provider_id}/test", response_model=TestResult)
async def test_provider(
    provider_id: int,
    _auth=Depends(require_admin),
    service: SettingsService = Depends(get_settings_service),
):
    return await service.test_provider(provider_id)


# ── API Keys ───────────────────────────────────────────────────────


@router.get("/providers/{provider_id}/keys", response_model=list[ApiKeyResponse])
async def list_keys(
    provider_id: int,
    _auth=Depends(require_admin),
    service: SettingsService = Depends(get_settings_service),
):
    return service.list_keys(provider_id)


@router.post("/providers/{provider_id}/keys", response_model=ApiKeyResponse, status_code=201)
async def add_key(
    provider_id: int,
    data: ApiKeyCreate,
    _auth=Depends(require_admin),
    service: SettingsService = Depends(get_settings_service),
):
    return service.add_key(provider_id, data.key_value)


@router.delete("/providers/{provider_id}/keys/{key_id}")
async def delete_key(
    provider_id: int,
    key_id: int,
    _auth=Depends(require_admin),
    service: SettingsService = Depends(get_settings_service),
):
    ok = service.delete_key(provider_id, key_id)
    if not ok:
        from app.core import http_errors

        raise http_errors.not_found("Key not found")
    return {"status": "deleted"}


# ── Platform Billing & Quota ───────────────────────────────────────────────────────


@router.get("/billing", response_model=BillingSettingsResponse)
async def get_billing_settings(_auth=Depends(require_admin)):
    """Get platform billing & quota settings."""
    from app.modules.settings.runtime_manager import RuntimeProviderManager

    rtm = RuntimeProviderManager.get_instance()
    billing = rtm.get_all_billing()
    return BillingSettingsResponse(
        ai_input_price_vnd_per_1m=int(billing.get("ai_input_price_vnd_per_1m", "0")),
        ai_output_price_vnd_per_1m=int(billing.get("ai_output_price_vnd_per_1m", "0")),
        quota_hard_budget_vnd=int(billing.get("quota_hard_budget_vnd", "0")),
        quota_user_rate_per_min=int(billing.get("quota_user_rate_per_min", "6")),
        quota_user_daily_requests=int(billing.get("quota_user_daily_requests", "100")),
        quota_cost_alert_pct_warn=int(billing.get("quota_cost_alert_pct_warn", "70")),
        quota_cost_alert_pct_alert=int(billing.get("quota_cost_alert_pct_alert", "85")),
        quota_cost_alert_pct_cutoff=int(billing.get("quota_cost_alert_pct_cutoff", "100")),
    )


@router.put("/billing", response_model=BillingSettingsResponse)
async def update_billing_settings(
    data: BillingSettingsUpdate,
    _auth=Depends(require_admin),
):
    """Update platform billing & quota settings. Changes take effect immediately."""
    from app.modules.settings.runtime_manager import RuntimeProviderManager
    from app.modules.settings.repository import SettingsRepository

    updates = {
        "ai_input_price_vnd_per_1m": str(data.ai_input_price_vnd_per_1m),
        "ai_output_price_vnd_per_1m": str(data.ai_output_price_vnd_per_1m),
        "quota_hard_budget_vnd": str(data.quota_hard_budget_vnd),
        "quota_user_rate_per_min": str(data.quota_user_rate_per_min),
        "quota_user_daily_requests": str(data.quota_user_daily_requests),
        "quota_cost_alert_pct_warn": str(data.quota_cost_alert_pct_warn),
        "quota_cost_alert_pct_alert": str(data.quota_cost_alert_pct_alert),
        "quota_cost_alert_pct_cutoff": str(data.quota_cost_alert_pct_cutoff),
    }
    repo = SettingsRepository()
    try:
        for key, value in updates.items():
            repo.set_platform_setting(key, value)
    finally:
        repo.close()

    rtm = RuntimeProviderManager.get_instance()
    rtm.reload_billing()

    return await get_billing_settings(_auth=_auth)
