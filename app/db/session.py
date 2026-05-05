from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.core.config import settings

from app.core.hardware import hardware

_pool_size = hardware.db_pool_size
_max_overflow = hardware.db_max_overflow

# Ensure asyncpg driver for PostgreSQL
async_url = settings.database_url
if "postgresql://" in async_url and "asyncpg" not in async_url:
    async_url = async_url.replace("postgresql://", "postgresql+asyncpg://")

engine = create_async_engine(
    async_url,
    connect_args={"server_settings": {"timezone": "Asia/Ho_Chi_Minh"}},
    pool_pre_ping=True,
    pool_size=_pool_size,
    max_overflow=_max_overflow,
    pool_recycle=3600,
    pool_timeout=30,
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
