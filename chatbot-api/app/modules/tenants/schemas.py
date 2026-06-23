from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class TenantCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    slug: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    monthly_token_quota: int = Field(default=0, ge=0)
    monthly_request_quota: int = Field(default=0, ge=0)
    rate_limit_rpm: int = Field(default=60, ge=1, le=100000)
    allowed_origins: list[str] = Field(default_factory=list)
    admin_username: str | None = Field(default=None, min_length=3, max_length=64)
    admin_password: str | None = Field(default=None, min_length=6, max_length=256)

    @field_validator("slug")
    @classmethod
    def normalize_slug(cls, value: str) -> str:
        return value.strip().lower()


class TenantUpdateRequest(BaseModel):
    slug: str | None = Field(default=None, min_length=2, max_length=120)
    name: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    status: str | None = Field(default=None, min_length=1, max_length=30)
    monthly_token_quota: int | None = Field(default=None, ge=0)
    monthly_request_quota: int | None = Field(default=None, ge=0)
    rate_limit_rpm: int | None = Field(default=None, ge=1, le=100000)
    allowed_origins: list[str] | None = None

    @field_validator("slug")
    @classmethod
    def normalize_optional_slug(cls, value: str | None) -> str | None:
        return value.strip().lower() if value is not None else value


class TenantResponse(BaseModel):
    id: str
    slug: str
    name: str
    status: str
    description: str | None = None
    monthly_token_quota: int
    monthly_request_quota: int
    rate_limit_rpm: int
    allowed_origins: list[str]
    created_at: datetime
    updated_at: datetime


class TenantSettingResponse(BaseModel):
    tenant_id: str
    chatbot_display_name: str
    welcome_message: str
    system_instruction: str
    updated_at: datetime


class TenantSettingUpdateRequest(BaseModel):
    chatbot_display_name: str | None = Field(default=None, min_length=1, max_length=255)
    welcome_message: str | None = Field(default=None, min_length=1, max_length=4000)
    system_instruction: str | None = Field(default=None, max_length=20000)


class TenantApiKeyCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    expires_at: datetime | None = None


class TenantApiKeyResponse(BaseModel):
    id: str
    tenant_id: str
    name: str
    key_prefix: str
    status: str
    expires_at: datetime | None = None
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None
    created_at: datetime


class TenantApiKeyCreateResponse(TenantApiKeyResponse):
    raw_api_key: str
