from __future__ import annotations

from time import perf_counter
from typing import Any

import boto3
import httpx
import psycopg
import redis
from botocore.client import Config
from botocore.exceptions import ClientError

from app.core.config import settings


def _latency_ms(start: float) -> int:
    return int((perf_counter() - start) * 1000)


def _redact(value: str) -> str:
    if "@" in value:
        return value.split("@", 1)[-1]
    return value


def check_database() -> dict[str, Any]:
    start = perf_counter()
    try:
        with psycopg.connect(settings.database_url.replace("+psycopg", ""), connect_timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        return {"status": "up", "latency_ms": _latency_ms(start), "dsn": _redact(settings.database_url)}
    except Exception:
        return {"status": "down", "latency_ms": _latency_ms(start), "dsn": _redact(settings.database_url), "error": "database_unreachable"}


def check_redis() -> dict[str, Any]:
    start = perf_counter()
    try:
        client = redis.Redis.from_url(settings.redis_url, socket_connect_timeout=3, socket_timeout=3)
        client.ping()
        return {"status": "up", "latency_ms": _latency_ms(start), "url": _redact(settings.redis_url)}
    except Exception:
        return {"status": "down", "latency_ms": _latency_ms(start), "url": _redact(settings.redis_url), "error": "redis_unreachable"}


def check_storage() -> dict[str, Any]:
    start = perf_counter()
    endpoint = f"http{'s' if settings.s3_secure else ''}://{settings.s3_endpoint}/{settings.s3_bucket}"
    try:
        client = boto3.client(
            "s3",
            endpoint_url=f"http{'s' if settings.s3_secure else ''}://{settings.s3_endpoint}",
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            config=Config(signature_version='s3v4'),
            region_name='us-east-1'
        )
        client.head_bucket(Bucket=settings.s3_bucket)
        return {
            "status": "up",
            "latency_ms": _latency_ms(start),
            "backend": settings.storage_backend,
            "endpoint": endpoint,
            "bucket_exists": True,
        }
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code", "")
        # Health endpoint must be read-only: do not create bucket here.
        if error_code in {"404", "NoSuchBucket", "NotFound"}:
            return {
                "status": "degraded",
                "latency_ms": _latency_ms(start),
                "backend": settings.storage_backend,
                "endpoint": endpoint,
                "bucket_exists": False,
                "error": "bucket_not_initialized",
            }
        return {
            "status": "down",
            "latency_ms": _latency_ms(start),
            "backend": settings.storage_backend,
            "endpoint": endpoint,
            "error": "storage_unreachable",
        }
    except Exception:
        return {
            "status": "down",
            "latency_ms": _latency_ms(start),
            "backend": settings.storage_backend,
            "endpoint": endpoint,
            "error": "storage_unreachable",
        }


def check_ai_provider() -> dict[str, Any]:
    provider = settings.ai_provider
    if provider == "google":
        configured = bool(settings.google_api_key and settings.google_api_key != "replace-me")
        return {
            "status": "up" if configured else "degraded",
            "provider": provider,
            "model": settings.google_model,
            "endpoint": "google-ai-studio",
            "configured": configured,
        }

    if provider == "vllm":
        start = perf_counter()
        try:
            with httpx.Client(timeout=3.0) as client:
                response = client.get(f"{settings.vllm_base_url.rstrip('/')}/models")
                response.raise_for_status()
            return {
                "status": "up",
                "provider": provider,
                "endpoint": settings.vllm_base_url,
                "configured": True,
                "latency_ms": _latency_ms(start),
            }
        except Exception:
            return {
                "status": "down",
                "provider": provider,
                "endpoint": settings.vllm_base_url,
                "configured": True,
                "latency_ms": _latency_ms(start),
                "error": "vllm_unreachable",
            }

    return {"status": "down", "provider": provider, "configured": False, "error": "Unsupported AI provider"}


def build_health_payload() -> dict[str, Any]:
    checks = {
        "database": check_database(),
        "redis": check_redis(),
        "storage": check_storage(),
        "ai_provider": check_ai_provider(),
    }
    overall = "healthy"
    if any(check["status"] == "down" for check in checks.values()):
        overall = "unhealthy"
    elif any(check["status"] == "degraded" for check in checks.values()):
        overall = "degraded"

    public_checks = {
        name: {"status": check["status"]}
        for name, check in checks.items()
    }
    return {"status": overall, "checks": public_checks}
