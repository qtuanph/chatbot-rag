from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings


engine = create_engine(
	settings.database_url,
	connect_args={"options": "-c timezone=Asia/Ho_Chi_Minh"},
	pool_pre_ping=True,
	pool_size=10,
	max_overflow=10,
	pool_recycle=3600,
	pool_timeout=30,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
