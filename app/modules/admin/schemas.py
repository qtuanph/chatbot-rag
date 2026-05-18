"""Pydantic schemas for Admin module."""

from __future__ import annotations

from pydantic import BaseModel


class ModelResponse(BaseModel):
    """Model info from 9Router."""

    id: str
    provider: str = ""


class ActiveModelUpdate(BaseModel):
    """Set active model."""

    model: str
