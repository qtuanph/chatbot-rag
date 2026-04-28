from dataclasses import dataclass

from fastapi import Depends, Header, Request
import jwt

from app.core.config import settings
from app.core import http_errors
from app.db.session import SessionLocal
from app.models.core import Role, User
from app.services.auth.token_blacklist import TokenBlacklist

# Module-level singleton — reuse Redis connection across requests
_blacklist = TokenBlacklist()


@dataclass(frozen=True)
class AuthContext:
    user_id: str
    role: str
    token_id: str
    request_id: str = ""


def get_auth_context(
    request: Request,
    authorization: str | None = Header(default=None),
) -> AuthContext | None:
    """
    Get authentication context from JWT token.
    Returns None for OPTIONS requests to support CORS preflight.
    """
    # Skip auth for OPTIONS preflight requests (CORS)
    if request.method == "OPTIONS":
        return None

    if not authorization or not authorization.startswith("Bearer "):
        raise http_errors.unauthorized("Missing bearer token")

    token = authorization.removeprefix("Bearer ").strip()
    # Get correlation ID from request state (set by CorrelationIDMiddleware)
    request_id = getattr(request.state, "correlation_id", "unknown")

    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        token_id = str(payload["jti"])
        if _blacklist.is_revoked(token_id):
            raise http_errors.unauthorized("Token revoked")

        # Get role from JWT payload (embedded at login to avoid DB query per request)
        role_name = payload.get("role", "")
        if not role_name:
            # Fallback: query DB for legacy tokens without role claim
            with SessionLocal() as session:
                user = session.get(User, str(payload["sub"]))
                if user is None or not user.is_active:
                    raise http_errors.unauthorized("Invalid token")
                role = session.get(Role, user.role_id)
                if role is None:
                    raise http_errors.unauthorized("Invalid token")
                role_name = role.name

        return AuthContext(
            user_id=str(payload["sub"]),
            role=role_name,
            token_id=token_id,
            request_id=request_id,
        )
    except (jwt.exceptions.PyJWTError, KeyError, TypeError, ValueError):
        raise http_errors.unauthorized("Invalid token") from None


def require_admin(request: Request, auth: AuthContext | None = Depends(get_auth_context)) -> AuthContext:
    """
    Require admin role.
    Allows OPTIONS requests to pass through for CORS preflight.
    """
    # Skip admin check for OPTIONS preflight requests (CORS)
    if request.method == "OPTIONS":
        return None  # type: ignore

    if auth is None:
        raise http_errors.unauthorized("Authentication required")

    if auth.role != "admin":
        raise http_errors.forbidden("Admin only")
    return auth
