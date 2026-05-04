from functools import lru_cache
import logging

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


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
    ai_input_cost_per_1m: float = 0.0  # Gemma 4 26B free tier on Google AI Studio
    ai_output_cost_per_1m: float = 0.0  # Set to actual cost when switching models

    ingestion_engine: str = "docling"
    ingestion_min_non_empty_nodes: int = 1
    ingestion_min_total_text_chars: int = 80
    # Embedding pipeline tuning — 0 means auto-detect from hardware profile
    ingestion_embedding_chunk_size: int = 32  # nodes per embed+store batch
    ingestion_embed_parallelism: int = 0  # 0 = use hardware.embed_parallelism

    # Retrieval quality
    retrieval_min_score: float = 0.35  # Drop chunks below this cosine similarity

    # 2-stage retrieval settings
    retrieval_section_top_k: int = 3  # Stage 1: top sections to retrieve
    retrieval_chunk_top_k: int = 5  # Stage 2: top chunks per section
    retrieval_chunk_size: int = 400  # Target chunk size in tokens
    retrieval_chunk_overlap: int = 75  # Overlap between chunks in tokens
    retrieval_section_min_score: float = 0.30  # Lower threshold for sections (coarser search)

    # Hybrid search (Dense + BM25) — always on, no toggle
    retrieval_bm25_k1: float = 1.5  # BM25 term frequency saturation
    retrieval_bm25_b: float = 0.75  # BM25 length normalization

    # Cross-encoder reranker — off by default (full section context makes LLM self-rank effectively)
    retrieval_rerank_enabled: bool = False
    retrieval_rerank_top_k: int = 5  # Final number of chunks after reranking
    retrieval_rerank_model: str = "AITeamVN/Vietnamese_Reranker"  # Vietnamese cross-encoder

    # Multi-query expansion
    retrieval_query_expansion_enabled: bool = False  # Default OFF — opt-in
    retrieval_query_expansion_variants: int = 3  # Number of query variants to generate

    database_url: str = "replace-me"
    redis_url: str = "redis://redis:6379/2"  # App cache — DB 2 (separate from broker DB 0 and result DB 1)
    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/1"
    jwt_secret: str = "replace-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    max_upload_size_mb: int = 50

    # Allowed file types for upload (MIME types)
    allowed_file_types: str = (
        "application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/plain,application/vnd.ms-excel,application/msword"
    )
    max_filename_length: int = 255

    # Rate limiting behavior
    # In non-production environments, limits can be relaxed for integration testing.
    rate_limit_relaxed_mode: bool = True
    rate_limit_relaxed_floor: int = 10000

    storage_backend: str = "s3"
    s3_endpoint: str = "rustfs:9000"
    s3_access_key: str = ""
    s3_secret_key: str = "replace-me"
    s3_bucket: str = "rag-documents"
    s3_secure: bool = False
    allowed_hosts: str = "localhost,127.0.0.1,0.0.0.0"
    cors_origins: str = "http://localhost"  # All traffic through nginx port 80

    # Embedding — local/offline, on-premise
    embedding_model: str = "sentence-transformer"
    embedding_hf_model: str = (
        "AITeamVN/Vietnamese_Embedding_v2"  # 1024-dim, 8192 tokens, built-in Normalize layer, Vietnamese fine-tuned BGE-M3
    )
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
    chat_session_ttl_days: int = 30  # Sessions older than 30 days are auto-deleted
    chat_history_redis_ttl: int = 86400  # Redis hot cache TTL in seconds (default 24h)
    chat_history_limit: int = 40  # Max messages loaded from DB on cache miss

    # AI generation parameters — configurable per deployment
    ai_temperature: float = 0.3
    ai_max_output_tokens: int = 8192
    ai_max_history_messages: int = 20  # Multi-turn context window
    ai_stream_timeout: float = 300.0  # HTTP timeout for AI streaming (seconds)
    ai_http_max_connections: int = 50  # httpx connection pool size
    ai_http_keepalive_connections: int = 10  # httpx keepalive pool size

    # Celery tuning — configurable for server-grade hardware
    celery_task_time_limit: int = 1800  # 30 min hard kill
    celery_task_soft_time_limit: int = 1500  # 25 min → SoftTimeLimitExceeded
    celery_worker_max_memory_kb: int = 1_500_000  # 1.5GB — kill child if exceeded
    celery_visibility_timeout: int = 7200  # 2h — Redis re-delivery guard
    celery_result_expires: int = 86400  # 24h — task result TTL
    celery_max_tasks_per_child: int = 50  # Recycle child after N tasks
    celery_retry_backoff: int = 30  # Base retry delay in seconds (upload tasks)
    celery_retry_backoff_max: int = 600  # Max 10 min between retries
    celery_max_retries: int = 3  # Max retry attempts for transient failures

    # Rate limiting — global middleware
    rate_limit_global_rpm: int = 300  # Global requests per minute across all users

    # Cache TTLs — configurable for deployment scale
    memory_cache_ttl: int = 300  # User memory Redis cache TTL (seconds)
    doc_ids_cache_ttl: float = 60.0  # Active document IDs cache TTL (seconds)
    retrieval_max_rerank_candidates: int = 30  # Max candidates sent to cross-encoder

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
        if not self.s3_access_key:
            raise ValueError("S3_ACCESS_KEY must be configured")
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
        if self.vector_store not in {"qdrant"}:
            raise ValueError("VECTOR_STORE must be qdrant")
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
    s = Settings()
    if not s.google_api_key:
        logger.error("GOOGLE_API_KEY is not set — AI features will not work")
    if s.rate_limit_relaxed_mode and s.app_env != "development":
        logger.warning(
            "RATE_LIMIT_RELAXED_MODE is enabled in %s environment — rate limits are relaxed. "
            "Set RATE_LIMIT_RELAXED_MODE=false for production security.",
            s.app_env,
        )
    return s


settings = get_settings()
