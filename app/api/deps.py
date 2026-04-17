from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, Request, status
from jose import JWTError, jwt

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.core import Role, User
from app.services.token_blacklist import TokenBlacklist


@dataclass(frozen=True)
class AuthContext:
    user_id: str
    role: str
    token_id: str


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
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        token_id = str(payload["jti"])
        if TokenBlacklist().is_revoked(token_id):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token revoked")
        with SessionLocal() as session:
            user = session.get(User, str(payload["sub"]))
            if user is None or not user.is_active:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
            role = session.get(Role, user.role_id)
            if role is None:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
            role_name = role.name
        return AuthContext(
            user_id=str(payload["sub"]),
            role=role_name,
            token_id=token_id,
        )
    except (JWTError, KeyError, TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from None


def require_admin(request: Request, auth: AuthContext | None = Depends(get_auth_context)) -> AuthContext:
    """
    Require admin role.
    Allows OPTIONS requests to pass through for CORS preflight.
    """
    # Skip admin check for OPTIONS preflight requests (CORS)
    if request.method == "OPTIONS":
        return None  # type: ignore

    if auth is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    if auth.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return auth
