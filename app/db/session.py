from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

# Pool sizing from hardware profile — scales with uvicorn workers.
# Dev (1 worker): pool_size=10, overflow=10 → 20 connections
# Server (8 workers): pool_size=40, overflow=40 → 80 connections
try:
    from app.core.hardware import hardware

    _pool_size = hardware.db_pool_size
    _max_overflow = hardware.db_max_overflow
except Exception:
    _pool_size = 10
    _max_overflow = 10

engine = create_engine(
    settings.database_url,
    connect_args={"options": "-c timezone=Asia/Ho_Chi_Minh"},
    pool_pre_ping=True,
    pool_size=_pool_size,
    max_overflow=_max_overflow,
    pool_recycle=3600,
    pool_timeout=30,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
