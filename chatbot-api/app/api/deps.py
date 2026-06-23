"""FastAPI dependency injection — auth context + service factories."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import TYPE_CHECKING, Any

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession
import jwt

from app.core.config import settings
from app.core import http_errors
from app.db.session import get_async_session
from app.modules.auth.utils.token_blacklist import TokenBlacklist
from app.utils.datetime_utils import utc_now

if TYPE_CHECKING:
    from app.modules.auth.repository import AuthRepository
    from app.modules.chat.repositories.feedback_repository import FeedbackRepository
    from app.modules.analytics.repository import AnalyticsRepository
    from app.modules.documents.repositories import DocumentRepository, SectionRepository
    from app.utils.rate_limiter import RateLimiter
    from app.utils.cache import SemanticCache, QueryEmbeddingCache
    from app.modules.auth.service import AuthService
    from app.modules.chat.services import FeedbackService
    from app.modules.analytics.service import AnalyticsService
    from app.modules.documents.services import TreeService, TaskService, CleanupService, DocumentService
    from app.modules.system.service import HealthService


async def get_redis_client() -> Any:
    from app.core.redis import get_redis_client

    return get_redis_client()


async def get_token_blacklist(r_client: Any = Depends(get_redis_client)) -> TokenBlacklist:
    return TokenBlacklist(r_client)


async def get_rate_limiter(r_client: Any = Depends(get_redis_client)) -> RateLimiter:
    from app.utils.rate_limiter import RateLimiter

    return RateLimiter(client=r_client)


async def get_semantic_cache(r_client: Any = Depends(get_redis_client)) -> SemanticCache:
    from app.utils.cache import SemanticCache

    return SemanticCache(vector_dim=settings.embedding_vector_size, client=r_client)


async def get_query_cache(r_client: Any = Depends(get_redis_client)) -> QueryEmbeddingCache:
    from app.utils.cache import QueryEmbeddingCache

    return QueryEmbeddingCache(r_client, model_name=settings.embedding_hf_model)


@dataclass(frozen=True)
class AuthContext:
    user_id: str
    role: str
    token_id: str
    tenant_id: str | None = None
    actor_type: str = "platform_user"
    api_key_id: str | None = None
    request_id: str = ""


@dataclass(frozen=True)
class TenantApiContext:
    tenant_id: str
    api_key_id: str
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
            tenant_id=str(payload["tenant_id"]) if payload.get("tenant_id") else None,
            request_id=request_id,
        )
    except (jwt.exceptions.PyJWTError, KeyError, TypeError, ValueError):
        raise http_errors.unauthorized("Invalid token") from None


async def require_admin(request: Request, auth: AuthContext | None = Depends(get_auth_context)) -> AuthContext:
    if request.method == "OPTIONS":
        return None

    if auth is None:
        raise http_errors.unauthorized("Authentication required")
    if auth.role != "platform_admin":
        raise http_errors.forbidden("Admin only")
    return auth


async def get_tenant_api_context(
    request: Request,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_async_session),
) -> TenantApiContext:
    if not authorization or not authorization.startswith("Bearer "):
        raise http_errors.unauthorized("Missing API key")

    raw_key = authorization.removeprefix("Bearer ").strip()
    if not raw_key:
        raise http_errors.unauthorized("Missing API key")

    key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    from app.modules.tenants.repository import TenantRepository

    tenant_repo = TenantRepository(session)
    row = await tenant_repo.get_active_api_key_by_hash(key_hash)
    if row is None:
        raise http_errors.unauthorized("Invalid API key")
    if row["status"] != "active":
        raise http_errors.forbidden("API key is not active")
    if row.get("revoked_at"):
        raise http_errors.forbidden("API key is revoked")
    expires_at = row.get("expires_at")
    if expires_at and expires_at <= utc_now():
        raise http_errors.forbidden("API key is expired")

    await tenant_repo.touch_api_key_last_used(row["id"], utc_now())
    request_id = getattr(request.state, "correlation_id", "unknown")
    return TenantApiContext(tenant_id=row["tenant_id"], api_key_id=row["id"], request_id=request_id)


# ── Repository factories ───────────────────────────────────────────────


async def get_auth_repo(session: AsyncSession = Depends(get_async_session)):
    from app.modules.auth.repository import AuthRepository

    return AuthRepository(session)


async def get_analytics_repo(session: AsyncSession = Depends(get_async_session)):
    from app.modules.analytics.repository import AnalyticsRepository

    return AnalyticsRepository(session)


async def get_feedback_repo(session: AsyncSession = Depends(get_async_session)):
    from app.modules.chat.repositories.feedback_repository import FeedbackRepository

    return FeedbackRepository(session)


async def get_doc_repo(session: AsyncSession = Depends(get_async_session)):
    from app.modules.documents.repositories import DocumentRepository

    return DocumentRepository(session)


async def get_section_repo(session: AsyncSession = Depends(get_async_session)):
    from app.modules.documents.repositories import SectionRepository

    return SectionRepository(session)


async def get_tenant_repo(session: AsyncSession = Depends(get_async_session)):
    from app.modules.tenants.repository import TenantRepository

    return TenantRepository(session)


# ── Service factories ──────────────────────────────────────────────────


async def get_auth_service(
    repo: AuthRepository = Depends(get_auth_repo),
    blacklist: TokenBlacklist = Depends(get_token_blacklist),
) -> AuthService:
    from app.modules.auth.service import AuthService

    return AuthService(repo=repo, blacklist=blacklist)


async def get_analytics_service(repo: AnalyticsRepository = Depends(get_analytics_repo)) -> AnalyticsService:
    from app.modules.analytics.service import AnalyticsService

    return AnalyticsService(repo=repo)


async def get_feedback_service(repo: FeedbackRepository = Depends(get_feedback_repo)) -> FeedbackService:
    from app.modules.chat.services import FeedbackService

    return FeedbackService(repo=repo)


async def get_task_service(
    doc_repo: DocumentRepository = Depends(get_doc_repo),
    r_client: Any = Depends(get_redis_client),
) -> TaskService:
    from app.modules.documents.services import TaskService

    return TaskService(doc_repo=doc_repo, redis_client=r_client)


async def get_tree_service(
    doc_repo: DocumentRepository = Depends(get_doc_repo),
    section_repo: SectionRepository = Depends(get_section_repo),
) -> TreeService:
    from app.modules.documents.services import TreeService

    return TreeService(doc_repo=doc_repo, section_repo=section_repo)


async def get_document_service(
    doc_repo: DocumentRepository = Depends(get_doc_repo),
    section_repo: SectionRepository = Depends(get_section_repo),
    r_client: Any = Depends(get_redis_client),
    task_service: TaskService = Depends(get_task_service),
    tree_service: TreeService = Depends(get_tree_service),
) -> DocumentService:
    from app.modules.documents.services import DocumentService

    return DocumentService(
        doc_repo=doc_repo,
        section_repo=section_repo,
        redis_client=r_client,
        task_service=task_service,
        tree_service=tree_service,
    )


async def get_tenant_service(tenant_repo=Depends(get_tenant_repo), auth_repo=Depends(get_auth_repo)):
    from app.modules.tenants.service import TenantService

    return TenantService(repo=tenant_repo, auth_repo=auth_repo)


async def get_health_service(doc_repo: DocumentRepository = Depends(get_doc_repo)) -> HealthService:
    from app.modules.system.service import HealthService

    return HealthService(doc_repo=doc_repo)


async def get_cleanup_service(
    doc_repo: DocumentRepository = Depends(get_doc_repo),
    section_repo: SectionRepository = Depends(get_section_repo),
    r_client: Any = Depends(get_redis_client),
) -> CleanupService:
    from app.modules.documents.services import CleanupService

    return CleanupService(doc_repo=doc_repo, section_repo=section_repo, redis_client=r_client)


async def get_recovery_service(
    doc_repo: DocumentRepository = Depends(get_doc_repo),
    section_repo: SectionRepository = Depends(get_section_repo),
    r_client: Any = Depends(get_redis_client),
) -> Any:
    from app.modules.documents.ingestion.recovery_service import RecoveryService

    return RecoveryService(doc_repo=doc_repo, section_repo=section_repo, redis_client=r_client)
