from sqlalchemy import text

from app.core.config import settings


def set_tenant_context(session) -> None:
    session.execute(text("select set_config('app.tenant_id', :tenant_id, true)"), {"tenant_id": settings.default_tenant_id})
