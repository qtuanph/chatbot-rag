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

    # Celery worker: which task modules to load ("all" | "upload" | "cleanup")
    celery_include: str = "all"

    ai_provider: str = "google"
    google_api_key: str = ""
    google_model: str = "gemma-4-26b-a4b-it"

    ingestion_engine: str = "docling"
    ingestion_min_non_empty_nodes: int = 1
    ingestion_min_total_text_chars: int = 80
    # Embedding pipeline tuning — 0 means auto-detect from hardware profile
    ingestion_embedding_chunk_size: int = 32   # nodes per embed+store batch
    ingestion_embed_parallelism: int = 0       # 0 = use hardware.embed_parallelism

    # Retrieval quality
    retrieval_min_score: float = 0.35          # Drop chunks below this cosine similarity

    # 2-stage retrieval settings
    retrieval_section_top_k: int = 3           # Stage 1: top sections to retrieve
    retrieval_chunk_top_k: int = 5             # Stage 2: top chunks per section
    retrieval_chunk_size: int = 400            # Target chunk size in tokens
    retrieval_chunk_overlap: int = 75          # Overlap between chunks in tokens
    retrieval_section_min_score: float = 0.30  # Lower threshold for sections (coarser search)

    database_url: str = "replace-me"
    redis_url: str = "redis://redis:6379/0"
    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/1"
    jwt_secret: str = "replace-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    max_upload_size_mb: int = 50
    
    # Allowed file types for upload (MIME types)
    allowed_file_types: str = "application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/plain,application/vnd.ms-excel,application/msword"
    max_filename_length: int = 255

    # Rate limiting behavior
    # In non-production environments, limits can be relaxed for integration testing.
    rate_limit_relaxed_mode: bool = True
    rate_limit_relaxed_floor: int = 10000

    storage_backend: str = "s3"
    s3_endpoint: str = "rustfs:9000"
    s3_access_key: str = "rustfs"
    s3_secret_key: str = "replace-me"
    s3_bucket: str = "rag-documents"
    s3_secure: bool = False
    allowed_hosts: str = "localhost,127.0.0.1,0.0.0.0"
    cors_origins: str = "http://localhost:8000,http://localhost:9001,http://localhost:3000"

    # Embedding — local/offline, on-premise
    embedding_model: str = "sentence-transformer"
    embedding_hf_model: str = "BAAI/bge-m3"          # 1024-dim, 8192 tokens, multilingual
    embedding_vector_size: int = 1024
    embedding_query_prefix: str = ""
    embedding_passage_prefix: str = ""
    embedding_batch_size: int = 32
    embedding_normalize: bool = True
    vector_store: str = "qdrant"
    qdrant_url: str = "http://qdrant:6333"
    qdrant_api_key: str = ""  # Empty for in-memory; set for cloud Qdrant
    qdrant_collection: str = "documents_vectors"
    qdrant_timeout: int = 30  # Seconds

    # Chat history auto-delete
    chat_session_ttl_days: int = 1  # Sessions older than 1 day are auto-deleted

    def model_post_init(self, __context) -> None:
        # Security: Validate JWT secret meets minimum requirements
        if not self.jwt_secret or self.jwt_secret == "replace-me":
            raise ValueError("JWT_SECRET must be configured")
        if len(self.jwt_secret) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters for security")
        # Check for sufficient entropy (at least 3 character types)
        char_types = 0
        if any(c.islower() for c in self.jwt_secret):
            char_types += 1
        if any(c.isupper() for c in self.jwt_secret):
            char_types += 1
        if any(c.isdigit() for c in self.jwt_secret):
            char_types += 1
        if any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in self.jwt_secret):
            char_types += 1
        if char_types < 3:
            raise ValueError("JWT_SECRET must contain at least 3 of: lowercase, uppercase, digits, special characters")

        # Security: Validate other secrets
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
        
        # Embedding validation
        self.vector_store = str(self.vector_store).strip().lower() or "qdrant"
        if self.vector_store not in {"qdrant", "chroma", "weaviate"}:
            raise ValueError("VECTOR_STORE must be qdrant/chroma/weaviate")
        if self.embedding_batch_size < 1:
            raise ValueError("EMBEDDING_BATCH_SIZE must be >= 1")
        if self.embedding_vector_size < 1:
            raise ValueError("EMBEDDING_VECTOR_SIZE must be >= 1")
        self.qdrant_url = str(self.qdrant_url).strip() or "http://qdrant:6333"
        if self.qdrant_timeout < 1:
            raise ValueError("QDRANT_TIMEOUT must be >= 1")
        if self.max_upload_size_mb < 1 or self.max_upload_size_mb > 500:
            raise ValueError("MAX_UPLOAD_SIZE_MB must be between 1 and 500")
        if self.max_filename_length < 20 or self.max_filename_length > 512:
            raise ValueError("MAX_FILENAME_LENGTH must be between 20 and 512")
        if not self.allowed_file_types:
            raise ValueError("ALLOWED_FILE_TYPES must not be empty")

        # Production-only constraints: fail fast on unsafe defaults.
        if self.app_env == "production":
            if "*" in self.allowed_hosts:
                raise ValueError("ALLOWED_HOSTS must not contain wildcard in production")
            if not self.cors_origins or "http://localhost" in self.cors_origins:
                raise ValueError("CORS_ORIGINS must be production-safe in production")
            if self.rate_limit_relaxed_mode:
                raise ValueError("RATE_LIMIT_RELAXED_MODE must be false in production")
            if self.s3_secure is False:
                raise ValueError("S3_SECURE must be true in production")

    def effective_rate_limit(self, base_limit: int) -> int:
        """
        Return the effective rate-limit threshold.

        - Production: keep strict configured limits.
        - Non-production: optionally relax to a high floor for testing.
        """
        if base_limit < 1:
            raise ValueError("base_limit must be >= 1")
        if self.app_env == "production":
            return base_limit
        if self.rate_limit_relaxed_mode:
            return max(base_limit, self.rate_limit_relaxed_floor)
        return base_limit

    def get_allowed_file_types(self) -> set[str]:
        """Parse ALLOWED_FILE_TYPES string into a set of MIME types."""
        return set(t.strip() for t in self.allowed_file_types.split(",") if t.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
