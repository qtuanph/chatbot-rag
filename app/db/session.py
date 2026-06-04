from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.core.config import settings

from app.core.hardware import hardware

_pool_size = hardware.db_pool_size
_max_overflow = hardware.db_max_overflow

# Ensure psycopg driver for PostgreSQL (async support via psycopg v3)
async_url = settings.database_url
if "postgresql://" in async_url and "psycopg" not in async_url:
    async_url = async_url.replace("postgresql://", "postgresql+psycopg://")

engine = create_async_engine(
    async_url,
    pool_pre_ping=True,
    pool_size=_pool_size,
    max_overflow=_max_overflow,
    pool_recycle=3600,
    pool_timeout=30,
    connect_args={"options": "-c timezone=Asia/Ho_Chi_Minh"} if "postgresql+psycopg://" in async_url else {},
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
