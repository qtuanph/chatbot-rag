from __future__ import annotations
from typing import Any

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_session
from app.core.deps import get_redis_client


async def get_doc_repo(session: AsyncSession = Depends(get_async_session)) -> Any:
    from app.modules.documents.repositories import DocumentRepository

    return DocumentRepository(session)


async def get_section_repo(session: AsyncSession = Depends(get_async_session)) -> Any:
    from app.modules.documents.repositories import SectionRepository

    return SectionRepository(session)


async def get_task_service(
    doc_repo: Any = Depends(get_doc_repo),
    r_client: Any = Depends(get_redis_client),
) -> Any:
    from app.modules.documents.services import TaskService

    return TaskService(doc_repo=doc_repo, redis_client=r_client)


async def get_tree_service(
    doc_repo: Any = Depends(get_doc_repo),
    section_repo: Any = Depends(get_section_repo),
) -> Any:
    from app.modules.documents.services import TreeService

    return TreeService(doc_repo=doc_repo, section_repo=section_repo)


async def get_document_service(
    doc_repo: Any = Depends(get_doc_repo),
    section_repo: Any = Depends(get_section_repo),
    r_client: Any = Depends(get_redis_client),
    task_service: Any = Depends(get_task_service),
    tree_service: Any = Depends(get_tree_service),
) -> Any:
    from app.modules.documents.services import DocumentService

    return DocumentService(
        doc_repo=doc_repo,
        section_repo=section_repo,
        redis_client=r_client,
        task_service=task_service,
        tree_service=tree_service,
    )


async def get_cleanup_service(
    doc_repo: Any = Depends(get_doc_repo),
    section_repo: Any = Depends(get_section_repo),
    r_client: Any = Depends(get_redis_client),
) -> Any:
    from app.modules.documents.services import CleanupService

    return CleanupService(doc_repo=doc_repo, section_repo=section_repo, redis_client=r_client)


async def get_recovery_service(
    doc_repo: Any = Depends(get_doc_repo),
    section_repo: Any = Depends(get_section_repo),
    r_client: Any = Depends(get_redis_client),
) -> Any:
    from app.modules.documents.ingestion.recovery_service import RecoveryService

    return RecoveryService(doc_repo=doc_repo, section_repo=section_repo, redis_client=r_client)
