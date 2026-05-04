"""FastAPI dependency injection — auth context + service factories."""

from dataclasses import dataclass
from typing import Generator

from fastapi import Depends, Header, Request
import jwt

from app.core.config import settings
from app.core import http_errors
from app.db.session import SessionLocal
from app.models.auth import Role, User
from app.utils.token_blacklist import TokenBlacklist

import redis as redis_lib

# Module-level singletons — reuse Redis connections across requests
_blacklist = TokenBlacklist()
_redis_client = redis_lib.Redis.from_url(settings.redis_url, decode_responses=True)


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


# ── Repository factories ───────────────────────────────────────────────


def get_auth_repo() -> Generator:
    from app.repositories.auth_repository import AuthRepository

    with SessionLocal() as session:
        yield AuthRepository(session)


def get_chat_repo() -> Generator:
    from app.repositories.chat_repository import ChatRepository

    with SessionLocal() as session:
        yield ChatRepository(session)


def get_analytics_repo() -> Generator:
    from app.repositories.analytics_repository import AnalyticsRepository

    with SessionLocal() as session:
        yield AnalyticsRepository(session)


def get_memory_repo() -> Generator:
    from app.repositories.memory_repository import MemoryRepository

    with SessionLocal() as session:
        yield MemoryRepository(session)


def get_doc_repo() -> Generator:
    from app.repositories.document_repository import DocumentRepository

    with SessionLocal() as session:
        yield DocumentRepository(session)


def get_section_repo() -> Generator:
    from app.repositories.section_repository import SectionRepository

    with SessionLocal() as session:
        yield SectionRepository(session)


# ── Service factories ──────────────────────────────────────────────────


def get_auth_service(repo=Depends(get_auth_repo)):
    from app.services.auth.auth_service import AuthService

    return AuthService(repo=repo, blacklist=_blacklist)


def get_chat_service(repo=Depends(get_chat_repo)):
    from app.services.chat.chat_service import ChatService
    from app.services.chat.user_memory_service import UserMemoryService
    from app.utils.chat_store import ChatStore

    user_memory_service = UserMemoryService(redis_client=_redis_client)
    return ChatService(repo=repo, store=ChatStore(), user_memory_service=user_memory_service)


def get_analytics_service(repo=Depends(get_analytics_repo)):
    from app.services.analytics.analytics_service import AnalyticsService

    return AnalyticsService(repo=repo)


def get_memory_service(memory_repo=Depends(get_memory_repo)):
    from app.services.chat.memory_service import MemoryService
    from app.services.chat.user_memory_service import UserMemoryService

    user_memory_service = UserMemoryService(redis_client=_redis_client)
    return MemoryService(repo=memory_repo, user_memory_service=user_memory_service)


def get_document_service(doc_repo=Depends(get_doc_repo), section_repo=Depends(get_section_repo)):
    from app.services.documents.document_service import DocumentService

    return DocumentService(doc_repo=doc_repo, section_repo=section_repo)


def get_tree_service(doc_repo=Depends(get_doc_repo), section_repo=Depends(get_section_repo)):
    from app.services.documents.tree_service import TreeService

    return TreeService(doc_repo=doc_repo, section_repo=section_repo)


def get_health_service():
    from app.services.system.health_service import HealthService

    return HealthService()


def get_cleanup_service(doc_repo=Depends(get_doc_repo), section_repo=Depends(get_section_repo)):
    from app.services.documents.cleanup_service import CleanupService

    return CleanupService(doc_repo=doc_repo, section_repo=section_repo)
