from __future__ import annotations
from typing import Any

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_session
from app.core.deps import get_semantic_cache


async def get_feedback_repo(session: AsyncSession = Depends(get_async_session)) -> Any:
    from app.modules.chat.repositories.feedback_repository import FeedbackRepository

    return FeedbackRepository(session)


async def get_feedback_service(
    repo: Any = Depends(get_feedback_repo), semantic_cache: Any = Depends(get_semantic_cache)
) -> Any:
    from app.modules.chat.services import FeedbackService
    return FeedbackService(repo=repo, semantic_cache=semantic_cache)



