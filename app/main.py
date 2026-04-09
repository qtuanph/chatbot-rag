import logging

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy.exc import ProgrammingError
from sqlalchemy import text

from app.api.routes import auth, chat, documents, health
from app.core.config import settings
from app.db.session import engine


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
async def apply_runtime_schema_patches() -> None:
    statements = [
        "ALTER TABLE documents ADD COLUMN IF NOT EXISTS status_stage VARCHAR(50) DEFAULT 'uploaded' NOT NULL",
        "ALTER TABLE documents ADD COLUMN IF NOT EXISTS progress_percent INTEGER DEFAULT 0 NOT NULL",
        "ALTER TABLE documents ADD COLUMN IF NOT EXISTS status_message VARCHAR(500)",
        "ALTER TABLE documents ADD COLUMN IF NOT EXISTS status_updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL",
        "ALTER TABLE documents DROP CONSTRAINT IF EXISTS ck_documents_status",
        "ALTER TABLE documents ADD CONSTRAINT ck_documents_status CHECK (status IN ('pending', 'processing', 'ready', 'failed', 'deleted'))",
        "ALTER TABLE documents DROP CONSTRAINT IF EXISTS ck_documents_progress_percent",
        "ALTER TABLE documents ADD CONSTRAINT ck_documents_progress_percent CHECK (progress_percent >= 0 AND progress_percent <= 100)",
        "CREATE INDEX IF NOT EXISTS idx_documents_status_stage ON documents(status_stage)",
    ]
    with engine.connect() as connection:
        for statement in statements:
            try:
                with connection.begin():
                    connection.execute(text(statement))
            except ProgrammingError as exc:
                message = str(exc)
                # Allow app startup with least-privilege DB users; schema ownership changes must be done via migration/admin account.
                if "InsufficientPrivilege" in message or "must be owner of table" in message:
                    logger.warning("Skipping runtime schema patch due to insufficient privileges: %s", statement)
                    continue
                raise
