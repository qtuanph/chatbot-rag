from __future__ import annotations

import hashlib
from typing import Any

from fastapi import BackgroundTasks, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import http_errors
from app.db.session import get_async_session
from app.utils.datetime_utils import utc_now
from app.modules.auth.deps import get_auth_repo


from app.modules.tenants.context import TenantApiContext


async def _touch_api_key_bg(api_key_id: str, touch_time: Any):
    from app.db.session import AsyncSessionLocal
    from app.modules.tenants.repository import TenantRepository

    async with AsyncSessionLocal() as bg_session:
        repo = TenantRepository(bg_session)
        await repo.touch_api_key_last_used(api_key_id, touch_time)
        await bg_session.commit()


async def get_tenant_api_context(
    request: Request,
    background_tasks: BackgroundTasks,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_async_session),
) -> TenantApiContext:
    if not authorization or not authorization.startswith("Bearer "):
        raise http_errors.unauthorized("Missing API key")

    raw_key = authorization.removeprefix("Bearer ").strip()
    if not raw_key:
        raise http_errors.unauthorized("Missing API key")

    key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    from app.modules.tenants.repository import TenantRepository

    tenant_repo = TenantRepository(session)
    row = await tenant_repo.get_active_api_key_by_hash(key_hash)
    if row is None:
        raise http_errors.unauthorized("Invalid API key")
    if row["status"] != "active":
        raise http_errors.forbidden("API key is not active")
    if row.get("revoked_at"):
        raise http_errors.forbidden("API key is revoked")
    expires_at = row.get("expires_at")
    if expires_at and expires_at <= utc_now():
        raise http_errors.forbidden("API key is expired")

    background_tasks.add_task(_touch_api_key_bg, row["id"], utc_now())
    request_id = getattr(request.state, "correlation_id", "unknown")
    return TenantApiContext(tenant_id=row["tenant_id"], api_key_id=row["id"], request_id=request_id)


async def get_tenant_repo(session: AsyncSession = Depends(get_async_session)) -> Any:
    from app.modules.tenants.repository import TenantRepository

    return TenantRepository(session)


async def get_tenant_service(
    tenant_repo: Any = Depends(get_tenant_repo), auth_repo: Any = Depends(get_auth_repo)
) -> Any:
    from app.modules.tenants.service import TenantService

    return TenantService(repo=tenant_repo, auth_repo=auth_repo)
