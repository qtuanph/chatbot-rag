"""Repository for UserMemory data access."""

from __future__ import annotations


from sqlalchemy.orm import Session

from app.models.memory import UserMemory


class MemoryRepository:
    """Data access layer for UserMemory model."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def list_by_user(self, user_id: str) -> list[dict]:
        rows = (
            self.session.query(UserMemory)
            .filter(UserMemory.user_id == user_id)
            .order_by(UserMemory.created_at.desc())
            .all()
        )
        return [self._to_dict(r) for r in rows]

    def list_active_by_user(self, user_id: str, limit: int = 50) -> list[dict]:
        rows = (
            self.session.query(UserMemory)
            .filter(UserMemory.user_id == user_id, UserMemory.is_active.is_(True))
            .order_by(UserMemory.created_at.desc())
            .limit(limit)
            .all()
        )
        return [self._to_dict(r) for r in rows]

    def get_by_id(self, memory_id: str) -> dict | None:
        row = self.session.get(UserMemory, memory_id)
        return self._to_dict(row) if row else None

    def create(self, *, user_id: str, memory_type: str, content: str) -> dict:
        memory = UserMemory(user_id=user_id, memory_type=memory_type, content=content)
        self.session.add(memory)
        self.session.commit()
        self.session.refresh(memory)
        return self._to_dict(memory)

    def update(
        self,
        memory_id: str,
        *,
        content: str | None = None,
        memory_type: str | None = None,
        is_active: bool | None = None,
    ) -> dict | None:
        memory = self.session.get(UserMemory, memory_id)
        if memory is None:
            return None
        if content is not None:
            memory.content = content
        if memory_type is not None:
            memory.memory_type = memory_type
        if is_active is not None:
            memory.is_active = is_active
        self.session.commit()
        self.session.refresh(memory)
        return self._to_dict(memory)

    def delete(self, memory_id: str) -> bool:
        memory = self.session.get(UserMemory, memory_id)
        if memory is None:
            return False
        self.session.delete(memory)
        self.session.commit()
        return True

    # ── Private helpers ──────────────────────────────────────────────

    @staticmethod
    def _to_dict(memory: UserMemory) -> dict:
        return {
            "id": str(memory.id),
            "user_id": str(memory.user_id),
            "memory_type": memory.memory_type,
            "content": memory.content,
            "is_active": memory.is_active,
            "created_at": memory.created_at.isoformat(),
            "updated_at": memory.updated_at.isoformat(),
        }
