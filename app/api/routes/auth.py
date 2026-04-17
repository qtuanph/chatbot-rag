from fastapi import APIRouter, Depends, Header, Request
from jose import JWTError, jwt
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core import http_errors
from app.db.session import SessionLocal
from app.models.core import Role, User
from app.schemas.auth import CreateUserRequest, CreateUserResponse, LoginRequest, LogoutResponse, RoleResponse, TokenResponse
from app.services.auth.service import create_access_token, hash_password, verify_password
from app.services.system.audit import safe_record_audit
from app.api.deps import AuthContext, get_auth_context, require_admin
from app.services.auth.token_blacklist import TokenBlacklist
from app.services.auth.throttle import RequestThrottle


router = APIRouter(tags=["auth"])
throttle = RequestThrottle()


@router.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request) -> TokenResponse:
    client_ip = request.client.host if request.client else "unknown"
    normalized_username = payload.username.lower().strip()
    throttle_key = f"throttle:login:{client_ip}:{normalized_username}"
    if not throttle.allow(throttle_key, limit=settings.effective_rate_limit(50), window_seconds=60):
        raise http_errors.too_many_requests("Too many login attempts")

    with SessionLocal() as session:
        user = session.query(User).filter(User.username == normalized_username).one_or_none()
        if user is None or not verify_password(payload.password, user.password_hash):
            raise http_errors.unauthorized("Invalid credentials")
        role = session.get(Role, user.role_id)
        if role is None:
            raise http_errors.unauthorized("Invalid credentials")

        token = create_access_token(subject=str(user.id))
        safe_record_audit(
            action="auth.login",
            actor_user_id=str(user.id),
            subject_type="user",
            subject_id=str(user.id),
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            details={"role": role.name},
        )
        return TokenResponse(access_token=token, role=role.name)


@router.post("/auth/logout", response_model=LogoutResponse)
def logout(request: Request, authorization: str | None = Header(default=None)) -> LogoutResponse:
    if not authorization or not authorization.startswith("Bearer "):
        raise http_errors.unauthorized("Missing bearer token")

    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        jti = str(payload["jti"])
        expires_at = int(payload["exp"])
        TokenBlacklist().revoke(jti, expires_at)
        safe_record_audit(
            action="auth.logout",
            actor_user_id=str(payload["sub"]),
            subject_type="token",
            subject_id=jti,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            details={"expires_at": expires_at},
        )
        return LogoutResponse(status="logged_out")
    except (JWTError, KeyError, TypeError, ValueError):
        raise http_errors.unauthorized("Invalid token") from None


@router.post("/auth/users", response_model=CreateUserResponse)
def create_user(payload: CreateUserRequest, _auth=Depends(require_admin)) -> CreateUserResponse:
    with SessionLocal() as session:
        normalized_username = payload.username.lower().strip()
        existing_user = session.query(User).filter(User.username == normalized_username).one_or_none()
        if existing_user is not None:
            raise http_errors.conflict("Username already exists")

        role = session.query(Role).filter(Role.name == payload.role).one_or_none()
        if role is None:
            raise http_errors.bad_request("Invalid role")

        user = User(
            role_id=role.id,
            username=normalized_username,
            password_hash=hash_password(payload.password),
        )
        session.add(user)
        try:
            session.commit()
            session.refresh(user)
        except IntegrityError:
            session.rollback()
            raise http_errors.conflict("Username already exists") from None
        safe_record_audit(
            action="auth.user.create",
            actor_user_id=_auth.user_id,
            subject_type="user",
            subject_id=str(user.id),
            ip_address=None,
            user_agent=None,
            details={"username": user.username, "role": role.name},
        )
        return CreateUserResponse(id=str(user.id), username=user.username, role=role.name)


@router.get("/auth/roles", response_model=list[RoleResponse])
def get_roles(_auth=Depends(require_admin)) -> list[RoleResponse]:
    with SessionLocal() as session:
        roles = session.query(Role).order_by(Role.name.asc()).all()
        return [
            RoleResponse(id=str(role.id), name=role.name, description=role.description)
            for role in roles
        ]

@router.get("/auth/me")
def get_me(auth: AuthContext = Depends(get_auth_context)) -> dict:
    """Return current user info from JWT token."""
    with SessionLocal() as session:
        user = session.get(User, auth.user_id)
        if user is None:
            raise http_errors.unauthorized("User not found")
        role = session.get(Role, user.role_id)
        return {
            "user_id": str(user.id),
            "username": user.username,
            "role": role.name if role else "unknown",
            "is_active": user.is_active,
        }


@router.get("/auth/users", response_model=list[CreateUserResponse])
def get_users(_auth=Depends(require_admin)) -> list[CreateUserResponse]:
    with SessionLocal() as session:
        results = session.query(User, Role).join(Role, User.role_id == Role.id).all()
        return [
            CreateUserResponse(id=str(u.id), username=u.username, role=r.name)
            for u, r in results
        ]


@router.delete("/auth/users/{username}")
def delete_user(username: str, _auth=Depends(require_admin)) -> dict[str, str]:
    """Delete a user by username."""
    with SessionLocal() as session:
        # Normalize username for lookup
        normalized_username = username.lower().strip()

        # Find user
        user = session.query(User).filter(User.username == normalized_username).one_or_none()
        if user is None:
            raise http_errors.not_found("User not found")

        # Prevent deleting yourself
        if str(user.id) == _auth.user_id:
            raise http_errors.bad_request("Cannot delete your own account")

        # Delete user
        session.delete(user)
        session.commit()

        safe_record_audit(
            action="auth.user.delete",
            actor_user_id=_auth.user_id,
            subject_type="user",
            subject_id=str(user.id),
            ip_address=None,
            user_agent=None,
            details={"username": user.username},
        )

        return {"status": "deleted", "username": user.username}
