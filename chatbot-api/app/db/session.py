from typing import Any
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.core.config import settings

from app.core.hardware import hardware

_pool_size = hardware.db_pool_size
_max_overflow = hardware.db_max_overflow

# Ensure psycopg driver for PostgreSQL (async support via psycopg v3)
async_url = settings.database_url
if "postgresql://" in async_url and "psycopg" not in async_url:
    async_url = async_url.replace("postgresql://", "postgresql+psycopg://")

engine_kwargs: dict[str, Any] = {
    "pool_pre_ping": True,
}
if "sqlite" not in async_url:
    engine_kwargs.update(
        {
            "pool_size": _pool_size,
            "max_overflow": _max_overflow,
            "pool_recycle": 1800,
            "pool_timeout": 30,
        }
    )
if "postgresql+psycopg://" in async_url:
    engine_kwargs["connect_args"] = {"options": "-c timezone=Asia/Ho_Chi_Minh"}

engine = create_async_engine(
    async_url,
    **engine_kwargs,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_async_session():
    """Dependency for getting an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
