from typing import Any, TypeVar, Generic, Type
from sqlalchemy.ext.asyncio import AsyncSession


T = TypeVar("T")

class BaseRepository(Generic[T]):
    """Base repository with common patterns to reduce boilerplate."""
    
    def __init__(self, session: AsyncSession, model: Type[T]) -> None:
        self.session = session
        self.model = model

    async def get_by_id(self, id: Any) -> T | None:
        return await self.session.get(self.model, id)

    async def delete_by_id(self, id: Any) -> bool:
        obj = await self.get_by_id(id)
        if obj:
            await self.session.delete(obj)
            await self.session.commit()
            return True
        return False

    def _to_dict(self, obj: T) -> dict[str, Any]:
        """Convert ORM model to dict, handling common conversions."""
        if obj is None:
            return {}
        
        data = {}
        for column in obj.__table__.columns:
            val = getattr(obj, column.name)
            # Handle UUIDs and Datetimes if needed (usually handled by Pydantic, but good to have)
            data[column.name] = val
        return data
