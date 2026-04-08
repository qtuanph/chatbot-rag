from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.core import SecurityAudit


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


def safe_record_audit(
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
        with SessionLocal() as session:
            record_audit(
                session,
                action=action,
                actor_user_id=actor_user_id,
                subject_type=subject_type,
                subject_id=subject_id,
                ip_address=ip_address,
                user_agent=user_agent,
                details=details,
            )
            session.commit()
    except Exception:
        pass
