"""Health service — passive service status reporting."""

from __future__ import annotations

from datetime import UTC, datetime

from app.core.config import settings


from app.modules.documents.repositories import DocumentRepository


class HealthService:
    """Passive health check — reports which services are configured and basic stats."""

    def __init__(self, doc_repo: DocumentRepository | None = None) -> None:
        self.doc_repo = doc_repo

    async def get_health_data(self) -> dict:
        """Return service configuration status and basic document stats."""
        data = {
            "status": "up",
            "services": {
                "database": {"configured": bool(settings.database_url)},
                "redis": {"configured": bool(settings.redis_url)},
                "storage": {"configured": bool(settings.s3_endpoint)},
                "ai_provider": {
                    "configured": bool(settings.google_api_key and settings.google_api_key != "replace-me"),
                    "provider": settings.ai_provider,
                    "model": settings.google_model,
                },
                "vector_db": {"configured": bool(settings.qdrant_url)},
                "workers": {"broker": "celery+redis"},
            },
            "timestamp": datetime.now(UTC).isoformat(),
        }

        if self.doc_repo:
            counts = await self.doc_repo.get_counts()
            data.update(counts)

        return data
