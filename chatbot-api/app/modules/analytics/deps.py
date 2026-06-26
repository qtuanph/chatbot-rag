from __future__ import annotations
from typing import Any

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_session


async def get_analytics_repo(session: AsyncSession = Depends(get_async_session)) -> Any:
    from app.modules.analytics.repository import AnalyticsRepository

    return AnalyticsRepository(session)


async def get_analytics_service(repo: Any = Depends(get_analytics_repo)) -> Any:
    from app.modules.analytics.service import AnalyticsService

    return AnalyticsService(repo=repo)
