import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware

from app.modules.analytics import router as analytics
from app.modules.auth import router as auth
from app.modules.chat import router as chat
from app.modules.documents import router as documents
from app.modules.system import router as system
from app.modules.chat import memories_router as memories
from app.modules.admin import router as admin
from app.api.routes.websocket import router as websocket_router
from app.api.middleware import (
    SecurityHeadersMiddleware,
    RequestLoggingMiddleware,
    RateLimitMiddleware,
    CorrelationIDMiddleware,
)
from app.core.config import settings
from app.core.error_response import build_error_response

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Application lifespan: startup and shutdown events."""
    # ── Startup ────────────────────────────────────────────────────────
    logger.info("Application started: %s [env=%s]", settings.app_name, settings.app_env)

    # Pre-warm embedding model at startup to avoid cold-start on first chat request.
    # This loads Vietnamese_Embedding_v2 into memory (GPU if available) once, so the first
    # query embedding is fast instead of taking 60-160 seconds.
    import asyncio
    import time

    async def _warm_models():
        start = time.time()
        try:
            # 1. Warm Embedding
            from app.modules.chat.retrieval.retrieval_service import build_embedding_service

            embed_svc = build_embedding_service()
            embed_fn = getattr(embed_svc, "embed_query", None) or embed_svc.embed
            await embed_fn("warmup")

            # 2. Warm Reranker
            from app.adapters.reranker import get_reranker

            reranker = get_reranker()
            await reranker.rerank("warmup", [{"text": "warmup", "full_text": "warmup", "score": 0.0}], top_k=1)

            # 3. Warm Semantic Cache Index (for 200+ CCU fast lookup)
            from app.core.redis import get_redis_client
            from app.utils.cache import SemanticCache

            redis = await get_redis_client()
            sem_cache = SemanticCache(vector_dim=settings.embedding_vector_size, client=redis)
            await sem_cache.init_index()
            logger.info("Semantic cache index warmed")

            # 4. Warm Active Doc IDs (avoid DB hit on first query)
            from app.db.session import AsyncSessionLocal
            from app.modules.documents.repositories import DocumentRepository

            async with AsyncSessionLocal() as db_session:
                doc_repo = DocumentRepository(db_session)
                ids = await doc_repo.get_latest_active_document_ids()
                if ids:
                    from app.modules.documents.utils.document_registry import DocumentRegistry

                    registry = DocumentRegistry(redis)
                    await registry.set_active_ids_async(ids)
                    logger.info("Active doc IDs warmed: %d docs", len(ids))

            elapsed = time.time() - start
            logger.info("AI models pre-warmed in %.1fs", elapsed)
        except Exception as e:
            logger.warning("AI model pre-warm failed (will lazy-load): %s", e)

    loop = asyncio.get_running_loop()
    loop.create_task(_warm_models())

    # Security: Warn if running in production with insecure settings
    if settings.app_env == "production":
        if "*" in settings.allowed_hosts:
            logger.warning("SECURITY: ALLOWED_HOSTS contains wildcard - this is unsafe for production!")
        if "http://" in settings.cors_origins:
            logger.warning("SECURITY: CORS allows HTTP origins - this is unsafe for production!")
        if settings.s3_secure is False:
            logger.warning("SECURITY: S3_SECURE is False - files transferred without encryption!")

    yield

    # ── Shutdown ───────────────────────────────────────────────────────
    logger.info("Application shutting down: %s", settings.app_name)


app = FastAPI(title=settings.app_name, docs_url=None, redoc_url=None, lifespan=lifespan)

# Security: Correlation ID middleware (must be early to set request.state.correlation_id)
app.add_middleware(CorrelationIDMiddleware)

# Security: HTTPS redirect in production (disable for local development)
if settings.app_env == "production":
    app.add_middleware(HTTPSRedirectMiddleware)

# Security: Trusted host middleware to prevent host header attacks
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=[host.strip() for host in settings.allowed_hosts.split(",") if host.strip()],
)

# Security: CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# Security: Add security headers to all responses
app.add_middleware(SecurityHeadersMiddleware, enable_hsts=settings.app_env == "production")

# Security: Request logging with IP sanitization
app.add_middleware(RequestLoggingMiddleware)

# Security: coarse global rate-limit fallback (production only).
# Fine-grained limits remain at route level.
if settings.app_env == "production":
    app.add_middleware(RateLimitMiddleware, requests_per_minute=settings.rate_limit_global_rpm)

routers = [
    auth.router,
    system.router,
    documents.router,
    chat.router,
    memories.router,
    analytics.router,
    admin,
    websocket_router,
]

for router in routers:
    app.include_router(router, prefix=settings.api_v1_prefix)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, (list, dict)):
        message = "Validation or processing error"
        details = exc.detail
    else:
        message = str(exc.detail) if exc.detail else "Request failed"
        details = None
    return JSONResponse(
        status_code=exc.status_code,
        content=build_error_response(request, exc.status_code, message, details=details),
    )


def _safe_validation_errors(errors: list[dict]) -> list[dict]:
    """Make Pydantic validation errors JSON-serializable."""
    safe = []
    for err in errors:
        entry = {k: v for k, v in err.items() if k != "ctx"}
        if "ctx" in err:
            ctx = {}
            for ck, cv in err["ctx"].items():
                try:
                    json.dumps(cv)
                    ctx[ck] = cv
                except (TypeError, ValueError):
                    ctx[ck] = str(cv)
            entry["ctx"] = ctx
        safe.append(entry)
    return safe


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=build_error_response(
            request,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Validation error",
            details=_safe_validation_errors(exc.errors()),
        ),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, _exc: Exception) -> JSONResponse:
    logger.exception("Unhandled API exception on %s", request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=build_error_response(
            request,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Internal server error",
        ),
    )
