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

    ingestion_engine: str = "docling"
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

    storage_backend: str = "s3"
    s3_endpoint: str = "rustfs:9000"
    s3_access_key: str = "rustfs"
    s3_secret_key: str = "replace-me"
    s3_bucket: str = "rag-documents"
    s3_secure: bool = False
    allowed_hosts: str = "localhost,127.0.0.1,0.0.0.0"

    # Embedding and vector store configuration
    embedding_model: str = "bge-m3"  # Model name for embeddings
    embedding_batch_size: int = 32
    embedding_normalize: bool = True
    vector_store: str = "qdrant"  # Vector store backend (qdrant, chroma, etc.)
    qdrant_url: str = "http://qdrant:6333"
    qdrant_api_key: str = ""  # Empty for in-memory; set for cloud Qdrant
    qdrant_collection: str = "documents_vectors"
    qdrant_timeout: int = 30  # Seconds

    def model_post_init(self, __context) -> None:
        if not self.jwt_secret or self.jwt_secret == "replace-me":
            raise ValueError("JWT_SECRET must be configured")
        if not self.s3_secret_key or self.s3_secret_key == "replace-me":
            raise ValueError("S3_SECRET_KEY must be configured")
        if not self.database_url or self.database_url == "replace-me":
            raise ValueError("DATABASE_URL must be configured")
        self.api_v1_prefix = str(self.api_v1_prefix).strip() or "/api/v1"
        if not self.api_v1_prefix.startswith("/"):
            raise ValueError("API_V1_PREFIX must start with '/'")
        self.ingestion_engine = str(self.ingestion_engine).strip().lower() or "docling"
        if self.ingestion_engine not in {"docling", "classic"}:
            raise ValueError("INGESTION_ENGINE must be docling/classic")
        if self.ingestion_min_non_empty_nodes < 1:
            raise ValueError("INGESTION_MIN_NON_EMPTY_NODES must be >= 1")
        if self.ingestion_min_total_text_chars < 1:
            raise ValueError("INGESTION_MIN_TOTAL_TEXT_CHARS must be >= 1")
        
        # Embedding and vector store validation
        self.embedding_model = str(self.embedding_model).strip().lower() or "bge-m3"
        self.vector_store = str(self.vector_store).strip().lower() or "qdrant"
        if self.vector_store not in {"qdrant", "chroma", "weaviate"}:
            raise ValueError("VECTOR_STORE must be qdrant/chroma/weaviate")
        if self.embedding_batch_size < 1:
            raise ValueError("EMBEDDING_BATCH_SIZE must be >= 1")
        self.qdrant_url = str(self.qdrant_url).strip() or "http://qdrant:6333"
        if self.qdrant_timeout < 1:
            raise ValueError("QDRANT_TIMEOUT must be >= 1")

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
