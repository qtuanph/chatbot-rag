from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "chatbot-rag"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    api_v1_prefix: str = "/api/v1"
    log_level: str = "INFO"

    ai_provider: str = "google"
    google_api_key: str = ""
    google_api_keys: str = ""
    google_model: str = "gemini-2.5-flash"
    vllm_base_url: str = "http://vllm:8000/v1"

    ocr_provider: str = "paddle"
    ocr_language: str = "vi"
    ocr_use_angle_cls: bool = True
    ocr_use_gpu: str = "auto"
    ocr_strategy: str = "hybrid"
    ocr_markdown_engine: str = "builtin"
    ocr_layout_analysis: bool = True
    ingestion_min_non_empty_nodes: int = 1
    ingestion_min_total_text_chars: int = 80

    database_url: str = "replace-me"
    redis_url: str = "redis://redis:6379/0"
    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/1"
    jwt_secret: str = "replace-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 720

    max_upload_size_mb: int = 50

    storage_backend: str = "minio"
    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "minio-admin"
    minio_secret_key: str = "replace-me"
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
        self.api_v1_prefix = str(self.api_v1_prefix).strip() or "/api/v1"
        if not self.api_v1_prefix.startswith("/"):
            raise ValueError("API_V1_PREFIX must start with '/'")
        if self.ocr_provider.lower().strip() != "paddle":
            raise ValueError("OCR_PROVIDER must be 'paddle'")
        self.ocr_use_gpu = str(self.ocr_use_gpu).strip().lower() or "auto"
        if self.ocr_use_gpu not in {"auto", "true", "false", "gpu", "cpu", "1", "0", "yes", "no"}:
            raise ValueError("OCR_USE_GPU must be auto/true/false")
        self.ocr_strategy = str(self.ocr_strategy).strip().lower() or "hybrid"
        if self.ocr_strategy not in {"traditional", "markdown", "hybrid"}:
            raise ValueError("OCR_STRATEGY must be traditional/markdown/hybrid")
        self.ocr_markdown_engine = str(self.ocr_markdown_engine).strip().lower() or "builtin"
        if self.ocr_markdown_engine not in {"builtin", "marker", "auto"}:
            raise ValueError("OCR_MARKDOWN_ENGINE must be builtin/marker/auto")
        if self.ingestion_min_non_empty_nodes < 1:
            raise ValueError("INGESTION_MIN_NON_EMPTY_NODES must be >= 1")
        if self.ingestion_min_total_text_chars < 1:
            raise ValueError("INGESTION_MIN_TOTAL_TEXT_CHARS must be >= 1")

    def get_google_api_keys(self) -> list[str]:
        keys: list[str] = []
        if self.google_api_key.strip():
            keys.append(self.google_api_key.strip())
        if self.google_api_keys.strip():
            keys.extend([item.strip() for item in self.google_api_keys.split(",") if item.strip()])

        deduped: list[str] = []
        seen: set[str] = set()
        for key in keys:
            if key not in seen:
                deduped.append(key)
                seen.add(key)
        return deduped


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
