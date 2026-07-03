"""Auth API — login, logout, user management."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.utils.rate_limiter import RateLimiter
import jwt

from app.modules.auth.deps import get_auth_context, get_auth_service, require_admin
from app.modules.auth.context import AuthContext
from app.core.deps import get_rate_limiter
from app.core.config import settings
from app.core import http_errors
from app.modules.auth.schemas import (
    CreateUserRequest,
    CreateUserResponse,
    LoginRequest,
    LogoutResponse,
    RoleResponse,
    TokenResponse,
    UpdateProfileRequest,
)
from app.modules.auth.service import AuthService

router = APIRouter(tags=["auth"])


@router.post("/auth/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    service: AuthService = Depends(get_auth_service),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
) -> TokenResponse:
    client_ip = request.client.host if request.client else "unknown"
    normalized_username = payload.username.strip()
    if not await rate_limiter.is_allowed(
        f"login:{client_ip}:{normalized_username}", limit=settings.effective_rate_limit(10), window_ms=60000
    ):
        raise http_errors.too_many_requests("Too many login attempts")

    try:
        result = await service.login(
            username=normalized_username,
            password=payload.password,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    except ValueError as e:
        raise http_errors.unauthorized(str(e)) from None
    return TokenResponse(access_token=result["access_token"], role=result["role"], tenant_id=result.get("tenant_id"))


@router.post("/auth/logout", response_model=LogoutResponse)
async def logout(
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
    service: AuthService = Depends(get_auth_service),
) -> LogoutResponse:
    # Decode token to get expiry for blacklist TTL
    authorization = request.headers.get("authorization", "")
    token = authorization.removeprefix("Bearer ").strip() if authorization.startswith("Bearer ") else ""
    expires_at = 0
    if token:
        try:
            payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
            expires_at = int(payload["exp"])
        except (jwt.exceptions.PyJWTError, KeyError, TypeError, ValueError):
            pass  # AuthContext already validated the token; proceed with logout

    await service.logout(
        jti=auth.token_id,
        expires_at=expires_at,
        user_id=auth.user_id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return LogoutResponse(status="logged_out")


@router.post("/auth/users", response_model=CreateUserResponse)
async def create_user(
    payload: CreateUserRequest,
    _auth=Depends(require_admin),
    service: AuthService = Depends(get_auth_service),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
) -> CreateUserResponse:
    if not await rate_limiter.is_allowed(
        f"user:create:{_auth.user_id}", limit=settings.effective_rate_limit(5), window_ms=60000
    ):
        raise http_errors.too_many_requests("Too many user creation requests")

    try:
        result = await service.create_user(
            username=payload.username,
            password=payload.password,
            role_name=payload.role,
            admin_user_id=_auth.user_id,
            tenant_id=payload.tenant_id,
        )
    except ValueError as e:
        msg = str(e)
        if "already exists" in msg:
            raise http_errors.conflict(msg) from None
        raise http_errors.bad_request(msg) from None

    return CreateUserResponse(
        id=result["id"],
        username=result["username"],
        role=result["role"],
        tenant_id=result.get("tenant_id"),
    )


@router.get("/auth/roles", response_model=list[RoleResponse])
async def get_roles(
    _auth=Depends(require_admin), service: AuthService = Depends(get_auth_service)
) -> list[RoleResponse]:
    roles = await service.list_roles()
    return [RoleResponse(id=r["id"], name=r["name"], description=r["description"]) for r in roles]


@router.get("/auth/me")
async def get_me(
    auth: AuthContext = Depends(get_auth_context), service: AuthService = Depends(get_auth_service)
) -> dict:
    try:
        return await service.get_current_user(auth.user_id)
    except ValueError as e:
        raise http_errors.unauthorized(str(e)) from None


@router.patch("/auth/me")
async def update_me(
    payload: UpdateProfileRequest,
    auth: AuthContext = Depends(get_auth_context),
    service: AuthService = Depends(get_auth_service),
) -> dict:
    try:
        return await service.update_profile(
            user_id=auth.user_id,
            username=payload.username,
            current_password=payload.current_password,
            new_password=payload.new_password,
        )
    except ValueError as e:
        msg = str(e)
        if "already exists" in msg:
            raise http_errors.conflict(msg) from None
        if "không chính xác" in msg or "required" in msg:
            raise http_errors.bad_request(msg) from None
        raise http_errors.bad_request(msg) from None


@router.get("/auth/users", response_model=list[CreateUserResponse])
async def get_users(
    _auth=Depends(require_admin), service: AuthService = Depends(get_auth_service)
) -> list[CreateUserResponse]:
    users = await service.list_users()
    return [
        CreateUserResponse(id=u["id"], username=u["username"], role=u["role"], tenant_id=u.get("tenant_id"))
        for u in users
    ]


@router.delete("/auth/users/{username}")
async def delete_user(
    username: str,
    _auth=Depends(require_admin),
    service: AuthService = Depends(get_auth_service),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
) -> dict[str, str]:
    if not await rate_limiter.is_allowed(
        f"user:delete:{_auth.user_id}", limit=settings.effective_rate_limit(5), window_ms=60000
    ):
        raise http_errors.too_many_requests("Too many user delete requests")

    try:
        return await service.delete_user(username=username, admin_user_id=_auth.user_id)
    except ValueError as e:
        msg = str(e)
        if "not found" in msg:
            raise http_errors.not_found(msg) from None
        if "own account" in msg:
            raise http_errors.bad_request(msg) from None
        raise http_errors.bad_request(msg) from None
