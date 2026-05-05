from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import SessionLocal, AsyncSessionLocal
from app.models.audit import SecurityAudit

logger = logging.getLogger(__name__)

def record_audit(
    session: Session,
    *,
    action: str,
    actor_user_id: str | None = None,
    subject_type: str | None = None,
    subject_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    session.add(
        SecurityAudit(
            actor_user_id=actor_user_id,
            action=action,
            subject_type=subject_type,
            subject_id=subject_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details or {},
        )
    )

async def async_record_audit(
    session: AsyncSession,
    *,
    action: str,
    actor_user_id: str | None = None,
    subject_type: str | None = None,
    subject_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    session.add(
        SecurityAudit(
            actor_user_id=actor_user_id,
            action=action,
            subject_type=subject_type,
            subject_id=subject_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details or {},
        )
    )

async def safe_record_audit(
    *,
    action: str,
    actor_user_id: str | None = None,
    subject_type: str | None = None,
    subject_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    try:
        async with AsyncSessionLocal() as session:
            await async_record_audit(
                session,
                action=action,
                actor_user_id=actor_user_id,
                subject_type=subject_type,
                subject_id=subject_id,
                ip_address=ip_address,
                user_agent=user_agent,
                details=details,
            )
            await session.commit()
    except Exception:
        logger.warning("Failed to write security audit event (Async)", exc_info=True)
