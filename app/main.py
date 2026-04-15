import logging

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware

from app.api.routes import auth, chat, documents, health, tree
from app.api.middleware import SecurityHeadersMiddleware, RequestLoggingMiddleware
from app.core.config import settings


logger = logging.getLogger(__name__)


app = FastAPI(title=settings.app_name, docs_url=None, redoc_url=None)

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
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# Security: Add security headers to all responses
app.add_middleware(SecurityHeadersMiddleware, enable_hsts=settings.app_env == "production")

# Security: Request logging with IP sanitization
app.add_middleware(RequestLoggingMiddleware)

routers = [auth.router, health.router, documents.router, chat.router, tree.router]

for router in routers:
    app.include_router(router, prefix=settings.api_v1_prefix)


@app.on_event("startup")
async def on_startup() -> None:
    # Schema is fully managed by ops/init.sql — no runtime DDL patches needed.
    # Any schema changes must go through ops/init.sql and a Docker rebuild.
    # Security: Log startup without exposing sensitive configuration
    logger.info("Application started: %s [env=%s]", settings.app_name, settings.app_env)

    # Security: Warn if running in production with insecure settings
    if settings.app_env == "production":
        if "*" in settings.allowed_hosts:
            logger.warning("SECURITY: ALLOWED_HOSTS contains wildcard - this is unsafe for production!")
        if "http://" in settings.cors_origins:
            logger.warning("SECURITY: CORS allows HTTP origins - this is unsafe for production!")
        if settings.s3_secure is False:
            logger.warning("SECURITY: S3_SECURE is False - files transferred without encryption!")
