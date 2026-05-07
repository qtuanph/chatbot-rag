"""FastAPI dependency injection — auth context + service factories."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession
import jwt

from app.core.config import settings
from app.core import http_errors
from app.db.session import get_async_session
from app.utils.token_blacklist import TokenBlacklist
from app.utils.document_registry import DocumentRegistry
from app.utils.chat_store import ChatStore

if TYPE_CHECKING:
    from app.modules.auth.repository import AuthRepository
    from app.modules.chat.repository import ChatRepository
    from app.modules.analytics.repository import AnalyticsRepository
    from app.modules.chat.memory_repository import MemoryRepository
    from app.modules.documents.repository import DocumentRepository
    from app.modules.documents.section_repository import SectionRepository
    from app.utils.rate_limiter import RateLimiter
    from app.utils.semantic_cache import SemanticCache
    from app.utils.query_cache import QueryEmbeddingCache, RagResultCache
    from app.modules.auth.service import AuthService
    from app.modules.chat.service import ChatService
    from app.modules.chat.memory_service import MemoryService
    from app.modules.analytics.service import AnalyticsService
    from app.modules.documents.tree_service import TreeService
    from app.modules.documents.task_service import TaskService
    from app.modules.system.service import HealthService
    from app.modules.documents.cleanup_service import CleanupService
    from app.modules.documents.service import DocumentService

# ── Redis Utility Getters ──────────────────


async def get_redis_client() -> Any:
    from app.core.redis import get_redis_client

    return get_redis_client()


async def get_token_blacklist(r_client: Any = Depends(get_redis_client)) -> TokenBlacklist:
    return TokenBlacklist(r_client)


async def get_document_registry(r_client: Any = Depends(get_redis_client)) -> DocumentRegistry:
    return DocumentRegistry(r_client)


async def get_chat_store(r_client: Any = Depends(get_redis_client)) -> ChatStore:
    return ChatStore(r_client)


async def get_rate_limiter(r_client: Any = Depends(get_redis_client)) -> RateLimiter:
    from app.utils.rate_limiter import RateLimiter

    return RateLimiter(client=r_client)


async def get_semantic_cache(r_client: Any = Depends(get_redis_client)) -> SemanticCache:
    from app.utils.semantic_cache import SemanticCache
    from app.core.config import settings

    return SemanticCache(vector_dim=settings.embedding_vector_size, client=r_client)


async def get_query_cache(r_client: Any = Depends(get_redis_client)) -> QueryEmbeddingCache:
    from app.utils.query_cache import QueryEmbeddingCache
    from app.core.config import settings

    return QueryEmbeddingCache(r_client, model_name=settings.embedding_hf_model)


async def get_rag_result_cache(r_client: Any = Depends(get_redis_client)) -> RagResultCache:
    from app.utils.query_cache import RagResultCache

    return RagResultCache(r_client)


@dataclass(frozen=True)
class AuthContext:
    user_id: str
    role: str
    token_id: str
    request_id: str = ""


async def get_auth_context(
    request: Request,
    authorization: str | None = Header(default=None),
    blacklist: TokenBlacklist = Depends(get_token_blacklist),
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
            request_id=request_id,
        )
    except (jwt.exceptions.PyJWTError, KeyError, TypeError, ValueError):
        raise http_errors.unauthorized("Invalid token") from None


async def require_admin(request: Request, auth: AuthContext | None = Depends(get_auth_context)) -> AuthContext:
    if request.method == "OPTIONS":
        return None  # type: ignore

    if auth is None:
        raise http_errors.unauthorized("Authentication required")

    if auth.role != "admin":
        raise http_errors.forbidden("Admin only")
    return auth


# ── Repository factories ───────────────────────────────────────────────


async def get_auth_repo(session: AsyncSession = Depends(get_async_session)):
    from app.modules.auth.repository import AuthRepository

    return AuthRepository(session)


async def get_chat_repo(session: AsyncSession = Depends(get_async_session)):
    from app.modules.chat.repository import ChatRepository

    return ChatRepository(session)


async def get_analytics_repo(session: AsyncSession = Depends(get_async_session)):
    from app.modules.analytics.repository import AnalyticsRepository

    return AnalyticsRepository(session)


async def get_memory_repo(session: AsyncSession = Depends(get_async_session)):
    from app.modules.chat.memory_repository import MemoryRepository

    return MemoryRepository(session)


async def get_doc_repo(session: AsyncSession = Depends(get_async_session)):
    from app.modules.documents.repository import DocumentRepository

    return DocumentRepository(session)


async def get_section_repo(session: AsyncSession = Depends(get_async_session)):
    from app.modules.documents.section_repository import SectionRepository

    return SectionRepository(session)


# ── Service factories ──────────────────────────────────────────────────


async def get_auth_service(
    repo: AuthRepository = Depends(get_auth_repo),
    blacklist: TokenBlacklist = Depends(get_token_blacklist),
) -> AuthService:
    from app.modules.auth.service import AuthService

    return AuthService(repo=repo, blacklist=blacklist)


async def get_chat_service(
    repo: ChatRepository = Depends(get_chat_repo),
    memory_repo: MemoryRepository = Depends(get_memory_repo),
    store: ChatStore = Depends(get_chat_store),
    r_client: Any = Depends(get_redis_client),
) -> ChatService:
    from app.modules.chat.service import ChatService
    from app.modules.chat.user_memory_service import UserMemoryService

    user_memory_service = UserMemoryService(redis_client=r_client, memory_repo=memory_repo)
    return ChatService(repo=repo, store=store, user_memory_service=user_memory_service)


async def get_analytics_service(repo: AnalyticsRepository = Depends(get_analytics_repo)) -> AnalyticsService:
    from app.modules.analytics.service import AnalyticsService

    return AnalyticsService(repo=repo)


async def get_memory_service(
    memory_repo: MemoryRepository = Depends(get_memory_repo),
    r_client: Any = Depends(get_redis_client),
) -> MemoryService:
    from app.modules.chat.memory_service import MemoryService
    from app.modules.chat.user_memory_service import UserMemoryService

    user_memory_service = UserMemoryService(redis_client=r_client, memory_repo=memory_repo)
    return MemoryService(repo=memory_repo, user_memory_service=user_memory_service)


async def get_task_service(
    doc_repo: DocumentRepository = Depends(get_doc_repo),
    registry: DocumentRegistry = Depends(get_document_registry),
) -> TaskService:
    from app.modules.documents.task_service import TaskService

    return TaskService(doc_repo=doc_repo, registry=registry)


async def get_tree_service(
    doc_repo: DocumentRepository = Depends(get_doc_repo),
    section_repo: SectionRepository = Depends(get_section_repo),
) -> TreeService:
    from app.modules.documents.tree_service import TreeService

    return TreeService(doc_repo=doc_repo, section_repo=section_repo)


async def get_document_service(
    doc_repo: DocumentRepository = Depends(get_doc_repo),
    section_repo: SectionRepository = Depends(get_section_repo),
    registry: DocumentRegistry = Depends(get_document_registry),
    task_service: TaskService = Depends(get_task_service),
    tree_service: TreeService = Depends(get_tree_service),
) -> DocumentService:
    from app.modules.documents.service import DocumentService

    return DocumentService(
        doc_repo=doc_repo,
        section_repo=section_repo,
        registry=registry,
        task_service=task_service,
        tree_service=tree_service,
    )


async def get_health_service() -> HealthService:
    from app.modules.system.service import HealthService

    return HealthService()


async def get_cleanup_service(
    doc_repo: DocumentRepository = Depends(get_doc_repo),
    section_repo: SectionRepository = Depends(get_section_repo),
    registry: DocumentRegistry = Depends(get_document_registry),
) -> CleanupService:
    from app.modules.documents.cleanup_service import CleanupService

    return CleanupService(doc_repo=doc_repo, section_repo=section_repo, registry=registry)


async def get_recovery_service(
    doc_repo: DocumentRepository = Depends(get_doc_repo),
    section_repo: SectionRepository = Depends(get_section_repo),
    r_client: Any = Depends(get_redis_client),
) -> Any:
    from app.modules.documents.ingestion.recovery_service import RecoveryService

    service = RecoveryService(doc_repo=doc_repo, section_repo=section_repo, redis_client=r_client)
    return await service.initialize()
