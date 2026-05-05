"""FastAPI dependency injection — auth context + service factories."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession
import jwt

from app.core.config import settings
from app.core import http_errors
from app.core.redis import redis_client
from app.db.session import get_async_session
from app.utils.token_blacklist import TokenBlacklist
from app.utils.document_registry import DocumentRegistry
from app.utils.chat_store import ChatStore

if TYPE_CHECKING:
    from app.repositories.auth_repository import AuthRepository
    from app.repositories.chat_repository import ChatRepository
    from app.repositories.analytics_repository import AnalyticsRepository
    from app.repositories.memory_repository import MemoryRepository
    from app.repositories.document_repository import DocumentRepository
    from app.repositories.section_repository import SectionRepository
    from app.services.auth.auth_service import AuthService
    from app.services.chat.chat_service import ChatService
    from app.services.chat.memory_service import MemoryService
    from app.services.analytics.analytics_service import AnalyticsService
    from app.services.documents.document_service import DocumentService
    from app.services.documents.tree_service import TreeService
    from app.services.system.health_service import HealthService
    from app.services.documents.cleanup_service import CleanupService

# Module-level singletons — reuse Redis connections across processes/requests
_blacklist = TokenBlacklist(redis_client)
_registry = DocumentRegistry(redis_client)
_chat_store = ChatStore(redis_client)


@dataclass(frozen=True)
class AuthContext:
    user_id: str
    role: str
    token_id: str
    request_id: str = ""


async def get_auth_context(
    request: Request,
    authorization: str | None = Header(default=None),
) -> AuthContext | None:
    """
    Get authentication context from JWT token.
    Returns None for OPTIONS requests to support CORS preflight.
    """
    if request.method == "OPTIONS":
        return None

    if not authorization or not authorization.startswith("Bearer "):
        raise http_errors.unauthorized("Missing bearer token")

    token = authorization.removeprefix("Bearer ").strip()
    request_id = getattr(request.state, "correlation_id", "unknown")

    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        token_id = str(payload["jti"])
        if await _blacklist.is_revoked(token_id):
            raise http_errors.unauthorized("Token revoked")

        role_name = payload.get("role")
        if not role_name:
            raise http_errors.unauthorized("Invalid token: missing role")

        return AuthContext(
            user_id=str(payload["sub"]),
            role=role_name,
            token_id=token_id,
            request_id=request_id,
        )
    except (jwt.exceptions.PyJWTError, KeyError, TypeError, ValueError):
        raise http_errors.unauthorized("Invalid token") from None


async def require_admin(request: Request, auth: AuthContext | None = Depends(get_auth_context)) -> AuthContext:
    """Require admin role."""
    if request.method == "OPTIONS":
        return None  # type: ignore

    if auth is None:
        raise http_errors.unauthorized("Authentication required")

    if auth.role != "admin":
        raise http_errors.forbidden("Admin only")
    return auth


# ── Repository factories ───────────────────────────────────────────────


async def get_auth_repo(session: AsyncSession = Depends(get_async_session)):
    from app.repositories.auth_repository import AuthRepository

    return AuthRepository(session)


async def get_chat_repo(session: AsyncSession = Depends(get_async_session)):
    from app.repositories.chat_repository import ChatRepository

    return ChatRepository(session)


async def get_analytics_repo(session: AsyncSession = Depends(get_async_session)):
    from app.repositories.analytics_repository import AnalyticsRepository

    return AnalyticsRepository(session)


async def get_memory_repo(session: AsyncSession = Depends(get_async_session)):
    from app.repositories.memory_repository import MemoryRepository

    return MemoryRepository(session)


async def get_doc_repo(session: AsyncSession = Depends(get_async_session)):
    from app.repositories.document_repository import DocumentRepository

    return DocumentRepository(session)


async def get_section_repo(session: AsyncSession = Depends(get_async_session)):
    from app.repositories.section_repository import SectionRepository

    return SectionRepository(session)


# ── Service factories ──────────────────────────────────────────────────


async def get_auth_service(repo: AuthRepository = Depends(get_auth_repo)) -> AuthService:
    from app.services.auth.auth_service import AuthService

    return AuthService(repo=repo, blacklist=_blacklist)


async def get_chat_service(
    repo: ChatRepository = Depends(get_chat_repo),
    memory_repo: MemoryRepository = Depends(get_memory_repo),
) -> ChatService:
    from app.services.chat.chat_service import ChatService
    from app.services.chat.user_memory_service import UserMemoryService

    user_memory_service = UserMemoryService(redis_client=redis_client, memory_repo=memory_repo)
    return ChatService(repo=repo, store=_chat_store, user_memory_service=user_memory_service)


async def get_analytics_service(repo: AnalyticsRepository = Depends(get_analytics_repo)) -> AnalyticsService:
    from app.services.analytics.analytics_service import AnalyticsService

    return AnalyticsService(repo=repo)


async def get_memory_service(memory_repo: MemoryRepository = Depends(get_memory_repo)) -> MemoryService:
    from app.services.chat.memory_service import MemoryService
    from app.services.chat.user_memory_service import UserMemoryService

    user_memory_service = UserMemoryService(redis_client=redis_client, memory_repo=memory_repo)
    return MemoryService(repo=memory_repo, user_memory_service=user_memory_service)


async def get_document_service(
    doc_repo: DocumentRepository = Depends(get_doc_repo),
    section_repo: SectionRepository = Depends(get_section_repo),
) -> DocumentService:
    from app.services.documents.document_service import DocumentService

    return DocumentService(doc_repo=doc_repo, section_repo=section_repo, registry=_registry)


async def get_tree_service(
    doc_repo: DocumentRepository = Depends(get_doc_repo),
    section_repo: SectionRepository = Depends(get_section_repo),
) -> TreeService:
    from app.services.documents.tree_service import TreeService

    return TreeService(doc_repo=doc_repo, section_repo=section_repo)


async def get_health_service() -> HealthService:
    from app.services.system.health_service import HealthService

    return HealthService()


async def get_cleanup_service(
    doc_repo: DocumentRepository = Depends(get_doc_repo),
    section_repo: SectionRepository = Depends(get_section_repo),
) -> CleanupService:
    from app.services.documents.cleanup_service import CleanupService

    return CleanupService(doc_repo=doc_repo, section_repo=section_repo, registry=_registry)
