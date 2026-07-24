from datetime import datetime, timedelta, timezone
import uuid

import bcrypt
import jwt

from app.core.config import settings


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def hash_password(password: str) -> str:
    pwd_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password=pwd_bytes, salt=salt)
    return hashed_password.decode("utf-8")

def create_access_token(
    *, subject: str, role: str, tenant_id: str | None = None, expires_delta: timedelta | None = None
) -> str:
    to_encode = {"sub": subject, "role": role, "jti": str(uuid.uuid4())}
    if tenant_id:
        to_encode["tenant_id"] = tenant_id

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire_minutes = getattr(settings, "jwt_expire_minutes", 60)
        expire = datetime.now(timezone.utc) + timedelta(minutes=expire_minutes)
    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return encoded_jwt
