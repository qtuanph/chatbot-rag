from datetime import UTC, datetime

from fastapi import APIRouter, Response, status

from app.services.health import build_health_payload


router = APIRouter(tags=["health"])


@router.get("/health")
async def healthcheck(response: Response) -> dict[str, object]:
    payload = build_health_payload()
    payload["timestamp"] = datetime.now(UTC).isoformat()
    if payload["status"] == "unhealthy":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return payload
