from __future__ import annotations
from typing import Any

from fastapi import Depends

from app.modules.documents.deps import get_doc_repo


async def get_health_service(doc_repo: Any = Depends(get_doc_repo)) -> Any:
    from app.modules.system.service import HealthService

    return HealthService(doc_repo=doc_repo)
