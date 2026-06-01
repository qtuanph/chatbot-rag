from pydantic import BaseModel, Field
from typing import Any, Optional


class ProviderCreate(BaseModel):
    service_type: str = Field(pattern=r"^(embedding|reranker|llm|parser)$")
    provider_name: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=128)
    url: str = Field(default="", max_length=512)
    model: str = Field(default="", max_length=256)
    api_key: str = Field(default="", max_length=1024)
    priority: int = Field(default=0, ge=0)
    config: Optional[dict[str, Any]] = None


class ProviderUpdate(BaseModel):
    display_name: Optional[str] = None
    url: Optional[str] = None
    model: Optional[str] = None
    api_key: Optional[str] = None
    priority: Optional[int] = None
    config: Optional[dict[str, Any]] = None


class ProviderResponse(BaseModel):
    id: int
    service_type: str
    provider_name: str
    display_name: str
    url: str
    model: str
    api_key: str
    is_active: bool
    is_builtin: bool
    priority: int
    config: dict[str, Any] = {}
    key_count: int = 0
    has_key: bool = False
    last_test_status: str = "unknown"
    last_test_at: Optional[str] = None
    last_error: str = ""
    last_error_at: Optional[str] = None
    created_at: str
    updated_at: str


class ApiKeyCreate(BaseModel):
    key_value: str = Field(min_length=1, max_length=2048)


class ApiKeyResponse(BaseModel):
    id: int
    provider_id: int
    key_value: str
    is_active: bool
    failure_count: int
    rate_limited_until: Optional[str] = None
    backoff_level: int = 0
    last_error: str = ""
    last_error_at: Optional[str] = None
    last_used_at: Optional[str] = None
    created_at: str


class ProviderTemplate(BaseModel):
    service_type: str
    provider_name: str
    display_name: str
    url: str
    model: str


class TestResult(BaseModel):
    success: bool
    message: str


class BillingSettingsResponse(BaseModel):
    ai_input_price_vnd_per_1m: int = 0
    ai_output_price_vnd_per_1m: int = 0
    quota_hard_budget_vnd: int = 0
    quota_user_rate_per_min: int = 6
    quota_user_daily_requests: int = 0
    quota_cost_alert_pct_warn: int = 70
    quota_cost_alert_pct_alert: int = 85
    quota_cost_alert_pct_cutoff: int = 100


class BillingSettingsUpdate(BaseModel):
    ai_input_price_vnd_per_1m: int = Field(ge=0)
    ai_output_price_vnd_per_1m: int = Field(ge=0)
    quota_hard_budget_vnd: int = Field(ge=0)
    quota_user_rate_per_min: int = Field(ge=1, le=1000)
    quota_user_daily_requests: int = Field(ge=0, le=1000000)
    quota_cost_alert_pct_warn: int = Field(ge=1, le=100)
    quota_cost_alert_pct_alert: int = Field(ge=1, le=100)
    quota_cost_alert_pct_cutoff: int = Field(ge=1, le=100)
