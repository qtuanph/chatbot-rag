"""Health service — passive service status reporting."""

from __future__ import annotations

from app.core.config import settings
from app.modules.documents.repositories import DocumentRepository
from app.modules.settings.runtime_manager import RuntimeProviderManager
from app.utils.datetime_utils import to_vietnam_iso, utc_now


class HealthService:
    """Passive health check — reports which services are configured and basic stats."""

    def __init__(self, doc_repo: DocumentRepository | None = None) -> None:
        self.doc_repo = doc_repo

    async def get_health_data(self) -> dict:
        """Return service configuration status and basic document stats."""
        runtime = RuntimeProviderManager.get_instance()
        llm_cfg = runtime.get_llm_config()
        data = {
            "status": "up",
            "services": {
                "database": {"configured": bool(settings.database_url)},
                "redis": {"configured": bool(settings.redis_url)},
                "storage": {"configured": bool(settings.s3_endpoint)},
                "ai_provider": {
                    "configured": bool(llm_cfg.get("url") if llm_cfg else settings.ai_proxy_url),
                    "provider": "9router",
                    "model": runtime.get_llm_model() or "default",
                },
                "vector_db": {"configured": bool(settings.qdrant_url)},
                "workers": {"broker": "celery+redis"},
            },
            "timestamp": to_vietnam_iso(utc_now()),
        }

        if self.doc_repo:
            counts = await self.doc_repo.get_counts()
            data.update(counts)

        return data
