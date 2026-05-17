"""Admin REST API — provider and model management."""

from __future__ import annotations

import logging
from fastapi import APIRouter, HTTPException

from app.modules.admin.schemas import ProviderCreate
from app.modules.admin.services.model_provider_service import ModelProviderService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


def _get_service() -> ModelProviderService:
    return ModelProviderService()


@router.get("/providers")
async def list_providers():
    """List all configured AI providers."""
    svc = _get_service()
    providers = await svc.list_providers()
    return {
        "providers": [
            {
                "name": p.get("name", "unknown"),
                "base_url": p.get("base-url", p.get("base_url", "")),
                "disabled": p.get("disabled", False),
                "model_count": len(p.get("models", [])),
                "models": p.get("models", []),
            }
            for p in providers
        ]
    }


@router.post("/providers", status_code=201)
async def add_provider(data: ProviderCreate):
    """Add a new OpenAI-compatible provider."""
    svc = _get_service()
    entry = {
        "name": data.name,
        "base-url": data.base_url.rstrip("/"),
        "api-key-entries": [{"api-key": data.api_key}] if data.api_key else [],
        "models": [_parse_model(m) for m in data.models if m.strip()],
        "disabled": data.disabled,
    }
    ok = await svc.add_provider(entry)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to add provider")
    return {"status": "ok"}


@router.patch("/providers/{name}/toggle")
async def toggle_provider(name: str):
    """Toggle a provider on/off based on its current state."""
    svc = _get_service()
    providers = await svc.list_providers()
    current = next((p for p in providers if p.get("name") == name), None)
    if not current:
        raise HTTPException(status_code=404, detail="Provider not found")
    currently_disabled = current.get("disabled", False)
    ok = await svc.toggle_provider(name, enabled=currently_disabled)
    if not ok:
        raise HTTPException(status_code=500, detail="Toggle failed")
    return {"status": "ok", "name": name, "disabled": not currently_disabled}


@router.delete("/providers/{name}", status_code=204)
async def remove_provider(name: str):
    """Remove a provider."""
    svc = _get_service()
    ok = await svc.remove_provider(name)
    if not ok:
        raise HTTPException(status_code=404, detail="Provider not found")
    return None


@router.get("/models")
async def list_models():
    """List available models from CLIProxyAPI."""
    svc = _get_service()
    models = await svc.list_models()
    return {"models": models}


def _parse_model(entry: str) -> dict[str, str]:
    """Parse 'model_name|alias' or just 'model_name'."""
    parts = entry.split("|")
    name = parts[0].strip()
    alias = parts[1].strip() if len(parts) > 1 else ""
    return {"name": name, "alias": alias or None}
