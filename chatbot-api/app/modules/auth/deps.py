from __future__ import annotations

from typing import Any
import jwt

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core import http_errors
from app.db.session import get_async_session
from app.core.deps import get_token_blacklist


from app.modules.auth.context import AuthContext


async def get_auth_context(
    request: Request,
    authorization: str | None = Header(default=None),
    blacklist: Any = Depends(get_token_blacklist),
) -> AuthContext | None:
    if request.method == "OPTIONS":
        return None

    if not authorization or not authorization.startswith("Bearer "):
        raise http_errors.unauthorized("Missing bearer token")

    token = authorization.removeprefix("Bearer ").strip()
    request_id = getattr(request.state, "correlation_id", "unknown")

    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        token_id = str(payload["jti"])
        if await blacklist.is_revoked(token_id):
            raise http_errors.unauthorized("Token revoked")

        role_name = payload.get("role")
        if not role_name:
            raise http_errors.unauthorized("Invalid token: missing role")

        return AuthContext(
            user_id=str(payload["sub"]),
            role=role_name,
            token_id=token_id,
            tenant_id=str(payload["tenant_id"]) if payload.get("tenant_id") else None,
            request_id=request_id,
        )
    except (jwt.exceptions.PyJWTError, KeyError, TypeError, ValueError):
        raise http_errors.unauthorized("Invalid token") from None


async def require_admin(request: Request, auth: AuthContext | None = Depends(get_auth_context)) -> AuthContext:
    if request.method == "OPTIONS":
        return None
    if auth is None:
        raise http_errors.unauthorized("Authentication required")
    if auth.role != "platform_admin":
        raise http_errors.forbidden("Admin only")
    return auth


async def get_auth_repo(session: AsyncSession = Depends(get_async_session)) -> Any:
    from app.modules.auth.repository import AuthRepository

    return AuthRepository(session)


async def get_auth_service(
    repo: Any = Depends(get_auth_repo),
    blacklist: Any = Depends(get_token_blacklist),
) -> Any:
    from app.modules.auth.service import AuthService

    return AuthService(repo=repo, blacklist=blacklist)
