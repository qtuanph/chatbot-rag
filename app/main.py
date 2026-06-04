import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from llama_index.core import Settings
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware

from app.modules.analytics import router as analytics
from app.modules.auth import router as auth
from app.modules.chat import router as chat
from app.modules.chat import memories_router as memories
from app.modules.documents import router as documents
from app.modules.inference import router as inference
from app.modules.settings import router as settings_router
from app.modules.system import router as system
from app.modules.admin import router as admin
from app.modules.tenants import router as tenants
from app.modules.tenants import self_router as tenant_self_router
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
    logger.info("Application started: %s [env=%s]", settings.app_name, settings.app_env)

    from app.core.llama_index import init_llama_index

    init_llama_index()

    import asyncio
    import time

    async def _warm_models():
        start = time.time()
        try:
            # 1. Warm Embedding via Settings.embed_model (OpenAIEmbedding)
            embed_model = Settings.embed_model
            await embed_model.aget_text_embedding("warmup")
            logger.info("Embedding model warmed")

            from app.core.redis import get_redis_client
            from app.utils.cache import SemanticCache

            redis = get_redis_client()
            sem_cache = SemanticCache(vector_dim=settings.embedding_vector_size, client=redis)
            await sem_cache.init_index()
            logger.info("Semantic cache index warmed")

            # 3. Warm Active Doc lookup path
            from app.db.session import AsyncSessionLocal
            from app.modules.documents.repositories import DocumentRepository

            async with AsyncSessionLocal() as db_session:
                doc_repo = DocumentRepository(db_session)
                ids = await doc_repo.get_latest_active_document_ids()
                logger.info("Active doc IDs counted for warmup: %d docs", len(ids))

            elapsed = time.time() - start
            logger.info("AI models pre-warmed in %.1fs", elapsed)
        except Exception as e:
            logger.warning("AI model pre-warm failed (will lazy-load): %s", e)

    loop = asyncio.get_running_loop()
    loop.create_task(_warm_models())

    if settings.app_env == "production":
        if "*" in settings.allowed_hosts:
            logger.warning("SECURITY: ALLOWED_HOSTS contains wildcard - this is unsafe for production!")
        if "http://" in settings.cors_origins:
            logger.warning("SECURITY: CORS allows HTTP origins - this is unsafe for production!")
        if settings.s3_secure is False:
            logger.warning("SECURITY: S3_SECURE is False - files transferred without encryption!")

    yield

    logger.info("Application shutting down: %s", settings.app_name)


app = FastAPI(title=settings.app_name, docs_url=None, redoc_url=None, lifespan=lifespan)

app.add_middleware(CorrelationIDMiddleware)

if settings.app_env == "production":
    app.add_middleware(HTTPSRedirectMiddleware)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=[host.strip() for host in settings.allowed_hosts.split(",") if host.strip()],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.add_middleware(SecurityHeadersMiddleware, enable_hsts=settings.app_env == "production")

app.add_middleware(RequestLoggingMiddleware)

if settings.app_env == "production":
    app.add_middleware(RateLimitMiddleware, requests_per_minute=settings.rate_limit_global_rpm)

routers = [
    auth.router,
    system.router,
    documents.router,
    chat.router,
    memories.router,
    inference,
    analytics.router,
    settings_router,
    admin,
    tenants,
    tenant_self_router,
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
async def request_validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
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
        content=build_error_response(request, status.HTTP_500_INTERNAL_SERVER_ERROR, "Internal server error"),
    )
