from fastapi import APIRouter, Depends, HTTPException, status

from app.db.session import SessionLocal
from app.models.core import Role, User
from app.schemas.auth import CreateUserRequest, CreateUserResponse, LoginRequest, TokenResponse
from app.services.auth import create_access_token, hash_password, verify_password
from app.api.deps import require_admin


router = APIRouter(tags=["auth"])


@router.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest) -> TokenResponse:
    with SessionLocal() as session:
        user = session.query(User).filter(User.username == payload.username).one_or_none()
        if user is None or not verify_password(payload.password, user.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        role = session.get(Role, user.role_id)
        if role is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

        token = create_access_token(subject=str(user.id))
        return TokenResponse(access_token=token, role=role.name)


@router.post("/auth/users", response_model=CreateUserResponse)
def create_user(payload: CreateUserRequest, _auth=Depends(require_admin)) -> CreateUserResponse:
    with SessionLocal() as session:
        role = session.query(Role).filter(Role.name == payload.role).one_or_none()
        if role is None:
            raise HTTPException(status_code=400, detail="Invalid role")

        user = User(
            role_id=role.id,
            username=payload.username,
            password_hash=hash_password(payload.password),
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return CreateUserResponse(id=str(user.id), username=user.username, role=role.name)
