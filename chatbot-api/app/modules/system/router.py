"""Health API — liveness probe and service configuration status."""

from fastapi import APIRouter, Depends

from app.api.deps import AuthContext, get_health_service, require_admin
from app.modules.system.service import HealthService

router = APIRouter(tags=["health"])


@router.get("/health")
async def healthcheck():
    """Public liveness probe for load balancers — no auth required."""
    return {"status": "up"}


@router.get("/health/data")
async def health_data(
    _auth: AuthContext = Depends(require_admin), service: HealthService = Depends(get_health_service)
):
    """Service configuration overview — admin only."""
    return await service.get_health_data()
