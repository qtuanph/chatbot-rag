"""Provider management via CLIProxyAPI Management API."""

from __future__ import annotations

import httpx
import logging
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


def has_enabled_providers() -> bool:
    """Quick check if at least one AI provider is enabled (sync, for asyncio.to_thread)."""
    try:
        resp = httpx.get(
            f"{settings.cliproxy_url.rstrip('/')}/v0/management/openai-compatibility",
            headers={"Authorization": f"Bearer {settings.cliproxy_management_password}"},
            timeout=5.0,
        )
        if resp.status_code != 200:
            return False
        data = resp.json()
        providers = data.get("openai-compatibility", []) if isinstance(data, dict) else data
        if not isinstance(providers, list):
            return False
        return any(not p.get("disabled", False) for p in providers)
    except Exception:
        return False


class ModelProviderService:
    """Manage AI providers via CLIProxyAPI's Management API.

    CLIProxyAPI exposes /v0/management/ endpoints for CRUD on providers.
    """

    def __init__(self) -> None:
        self.base_url = settings.cliproxy_url.rstrip("/")
        self.api_key = settings.cliproxy_api_key
        self.mgmt_password = settings.cliproxy_management_password

    async def _get_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.base_url,
            timeout=10.0,
        )

    def _mgmt_headers(self) -> dict[str, str]:
        """Auth header for CLIProxy management API."""
        return {"Authorization": f"Bearer {self.mgmt_password}"}

    async def list_providers(self) -> list[dict[str, Any]]:
        """List all OpenAI-compatible providers from CLIProxyAPI."""
        async with await self._get_client() as client:
            try:
                resp = await client.get(
                    "/v0/management/openai-compatibility",
                    headers=self._mgmt_headers(),
                )
                if resp.status_code == 200:
                    data = resp.json()
                    # Response is {"openai-compatibility": [...]}
                    return data.get("openai-compatibility", []) if isinstance(data, dict) else data
                logger.warning("list_providers failed: %s %s", resp.status_code, resp.text)
                return []
            except Exception as e:
                logger.error("list_providers error: %s", e)
                return []

    async def add_provider(self, provider: dict[str, Any]) -> bool:
        """Add a new provider."""
        existing = await self.list_providers()
        existing.append(provider)
        return await self._replace_all(existing)

    async def toggle_provider(self, name: str, enabled: bool) -> bool:
        """Enable or disable a provider."""
        existing = await self.list_providers()
        for p in existing:
            if p.get("name") == name:
                p["disabled"] = not enabled
                break
        return await self._replace_all(existing)

    async def remove_provider(self, name: str) -> bool:
        """Remove a provider by name."""
        existing = await self.list_providers()
        existing = [p for p in existing if p.get("name") != name]
        return await self._replace_all(existing)

    async def list_models(self) -> list[dict[str, str]]:
        """List available models from CLIProxyAPI."""
        async with await self._get_client() as client:
            try:
                resp = await client.get(
                    "/v1/models",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return [{"id": m["id"], "provider": m.get("provider", "")} for m in data.get("data", [])]
                return []
            except Exception as e:
                logger.error("list_models error: %s", e)
                return []

    async def _replace_all(self, providers: list[dict[str, Any]]) -> bool:
        """Replace the full openai-compatibility list via config.yaml PUT."""
        async with await self._get_client() as client:
            try:
                current_config = await self._get_config()
                current_config["openai-compatibility"] = providers
                resp = await client.put(
                    "/v0/management/config.yaml",
                    headers=self._mgmt_headers(),
                    json=current_config,
                )
                return resp.status_code in (200, 204)
            except Exception as e:
                logger.error("_replace_all error: %s", e)
                return False

    async def _get_config(self) -> dict[str, Any]:
        """Get the full CLIProxyAPI config."""
        async with await self._get_client() as client:
            try:
                resp = await client.get(
                    "/v0/management/config.yaml",
                    headers=self._mgmt_headers(),
                )
                if resp.status_code == 200:
                    return resp.json()
                return {}
            except Exception:
                return {}
