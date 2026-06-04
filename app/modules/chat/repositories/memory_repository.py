from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memory import UserMemory
from app.utils.datetime_utils import to_vietnam_iso


class MemoryRepository:
    """Data access layer for UserMemory model."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_by_user(self, user_id: str) -> list[dict]:
        stmt = select(UserMemory).where(UserMemory.user_id == user_id).order_by(UserMemory.created_at.desc())
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        return [self._to_dict(r) for r in rows]

    async def list_active_by_user(self, user_id: str, limit: int = 50) -> list[dict]:
        stmt = (
            select(UserMemory)
            .where(UserMemory.user_id == user_id, UserMemory.is_active.is_(True))
            .order_by(UserMemory.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        return [self._to_dict(r) for r in rows]

    async def get_by_id(self, memory_id: str) -> dict | None:
        row = await self.session.get(UserMemory, memory_id)
        return self._to_dict(row) if row else None

    async def create(self, *, user_id: str, memory_type: str, content: str) -> dict:
        memory = UserMemory(user_id=user_id, memory_type=memory_type, content=content)
        self.session.add(memory)
        await self.session.commit()
        await self.session.refresh(memory)
        return self._to_dict(memory)

    async def update(
        self,
        memory_id: str,
        *,
        content: str | None = None,
        memory_type: str | None = None,
        is_active: bool | None = None,
    ) -> dict | None:
        memory = await self.session.get(UserMemory, memory_id)
        if memory is None:
            return None
        if content is not None:
            memory.content = content
        if memory_type is not None:
            memory.memory_type = memory_type
        if is_active is not None:
            memory.is_active = is_active
        await self.session.commit()
        await self.session.refresh(memory)
        return self._to_dict(memory)

    async def delete(self, memory_id: str) -> bool:
        memory = await self.session.get(UserMemory, memory_id)
        if memory is None:
            return False
        await self.session.delete(memory)
        await self.session.commit()
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
            "created_at": to_vietnam_iso(memory.created_at),
            "updated_at": to_vietnam_iso(memory.updated_at),
        }
