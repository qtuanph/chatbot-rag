from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from jose import JWTError, jwt
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.core import Role, User
from app.schemas.auth import CreateUserRequest, CreateUserResponse, LoginRequest, LogoutResponse, TokenResponse
from app.services.auth import create_access_token, hash_password, verify_password
from app.services.audit import safe_record_audit
from app.api.deps import require_admin
from app.services.token_blacklist import TokenBlacklist
from app.services.throttle import RequestThrottle


router = APIRouter(tags=["auth"])
throttle = RequestThrottle()


@router.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request) -> TokenResponse:
    client_ip = request.client.host if request.client else "unknown"
    normalized_username = payload.username.lower().strip()
    throttle_key = f"throttle:login:{client_ip}:{normalized_username}"
    if not throttle.allow(throttle_key, limit=10, window_seconds=300):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many login attempts")

    with SessionLocal() as session:
        user = session.query(User).filter(User.username == normalized_username).one_or_none()
        if user is None or not verify_password(payload.password, user.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        role = session.get(Role, user.role_id)
        if role is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

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
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

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
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from None


@router.post("/auth/users", response_model=CreateUserResponse)
def create_user(payload: CreateUserRequest, _auth=Depends(require_admin)) -> CreateUserResponse:
    with SessionLocal() as session:
        normalized_username = payload.username.lower().strip()
        existing_user = session.query(User).filter(User.username == normalized_username).one_or_none()
        if existing_user is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists")

        role = session.query(Role).filter(Role.name == payload.role).one_or_none()
        if role is None:
            raise HTTPException(status_code=400, detail="Invalid role")

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
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists") from None
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
