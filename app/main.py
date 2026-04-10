import logging

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.routes import auth, chat, documents, health
from app.core.config import settings


logger = logging.getLogger(__name__)


app = FastAPI(title=settings.app_name)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=[host.strip() for host in settings.allowed_hosts.split(",") if host.strip()],
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

routers = [auth.router, health.router, documents.router, chat.router]

for router in routers:
    app.include_router(router, prefix=settings.api_v1_prefix)


@app.on_event("startup")
async def on_startup() -> None:
    # Schema is fully managed by ops/init.sql — no runtime DDL patches needed.
    # Any schema changes must go through ops/init.sql and a Docker rebuild.
    logger.info("Application started: %s [env=%s]", settings.app_name, settings.app_env)
