from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "chatbot-rag"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    ai_provider: str = "google"
    google_api_key: str = ""
    google_model: str = "gemini-2.5-flash"
    vllm_base_url: str = "http://vllm:8000/v1"

    database_url: str = "postgresql+psycopg://app_rw:quoctuan@db:5432/ragbot"
    redis_url: str = "redis://redis:6379/0"
    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/1"
    jwt_secret: str = "quoctuan"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 720

    max_upload_size_mb: int = 50

    storage_backend: str = "minio"
    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "minio-admin"
    minio_secret_key: str = "quoctuan"
    minio_bucket: str = "rag-documents"
    minio_secure: bool = False
    allowed_hosts: str = "localhost,127.0.0.1,0.0.0.0"

    def model_post_init(self, __context) -> None:
        if not self.jwt_secret or self.jwt_secret == "replace-me":
            raise ValueError("JWT_SECRET must be configured")
        if not self.minio_secret_key or self.minio_secret_key == "replace-me":
            raise ValueError("MINIO_SECRET_KEY must be configured")
        if not self.database_url or self.database_url == "replace-me":
            raise ValueError("DATABASE_URL must be configured")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
