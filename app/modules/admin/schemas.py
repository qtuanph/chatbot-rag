"""Pydantic schemas for Admin module."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class ProviderEntry(BaseModel):
    """An OpenAI-compatible provider entry in CLIProxyAPI."""

    name: str
    base_url: str
    api_key_entries: list[dict[str, Any]] = Field(default_factory=list)
    models: list[dict[str, str]] = Field(default_factory=list)
    disabled: bool = False


class ProviderCreate(BaseModel):
    """Create a new OpenAI-compatible provider."""

    name: str
    base_url: str
    api_key: str = ""
    models: list[str] = Field(default_factory=list, description="List of 'model_name|alias' entries")
    disabled: bool = False


class ProviderResponse(BaseModel):
    """Provider response for API."""

    name: str
    base_url: str
    enabled: bool
    model_count: int
    models: list[dict[str, str]] = Field(default_factory=list)


class ProviderToggle(BaseModel):
    """Toggle provider on/off."""

    name: str
    enabled: bool


class ProviderToggleResponse(BaseModel):
    """Response after toggling a provider."""

    status: str
    name: str
    disabled: bool


class ModelResponse(BaseModel):
    """Model info from CLIProxyAPI."""

    id: str
    provider: str = ""


class ActiveModelUpdate(BaseModel):
    """Set active model."""

    model: str
