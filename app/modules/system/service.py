"""Health service — passive service status reporting."""

from __future__ import annotations

from datetime import UTC, datetime

from app.core.config import settings


class HealthService:
    """Passive health check — reports which services are configured, no active probing."""

    @staticmethod
    def get_health_data() -> dict:
        """Return service configuration status (no active health probing)."""
        return {
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
