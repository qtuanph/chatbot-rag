from functools import lru_cache
import logging
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "chatbot-rag"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    api_v1_prefix: str = "/api/v1"
    api_timeout_keep_alive: int = 75
    ai_embedding_url: str = "http://ai-embedding:80"
    ai_reranker_url: str = "http://ai-reranker:80"
    reranker_backend: str = "tei"  # "tei" (local TEI) | "nvidia" (NVIDIA NIM API)
    nvidia_api_key: str = ""
    nvidia_reranker_model: str = "nvidia/llama-nemotron-rerank-vl-1b-v2"
    nvidia_reranker_url: str = "https://ai.api.nvidia.com/v1/retrieval/nvidia/llama-nemotron-rerank-vl-1b-v2/reranking"
    nvidia_reranker_timeout: float = 30.0
    log_level: str = "INFO"

    celery_include: str = "all"

    ai_proxy_url: str = "http://ai-proxy:2908"
    ai_proxy_api_key: str = ""
    ai_proxy_default_model: str = ""
    ai_input_cost_per_1m: float = 0.0
    ai_output_cost_per_1m: float = 0.0

    retrieval_semantic_cache_enabled: bool = True
    retrieval_semantic_cache_threshold: float = 0.08

    llm_cache_enabled: bool = True
    llm_cache_ttl: int = 14400
    llm_cache_exact_first: bool = True

    query_normalize_enabled: bool = True
    retrieval_query_refinement_enabled: bool = True
    retrieval_query_refinement_timeout: float = 5.0
    retrieval_query_expansion_enabled: bool = True
    retrieval_query_expansion_timeout: float = 5.0
    ragas_evaluation_enabled: bool = False

    llama_cloud_api_key: str = ""
    llama_cloud_api_base: str = "https://api.cloud.llamaindex.ai"
    llama_cloud_timeout: float = 120.0

    kg_entity_extract_limit: int = 50
    kg_connected_entity_limit: int = 20

    retrieval_chunk_size: int = 600
    retrieval_chunk_overlap: int = 120

    ingestion_engine: str = "docling"
    ingestion_min_non_empty_nodes: int = 1
    ingestion_min_total_text_chars: int = 80
    ingestion_min_quality_score: float = 0.5
    ingestion_min_section_chars: int = 200
    ingestion_parsing_timeout: int = 3600
    ingestion_ocr_languages: Any = ["vi", "en"]

    @field_validator("ingestion_ocr_languages", mode="before")
    @classmethod
    def parse_ocr_languages(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("[") and v.endswith("]"):
                try:
                    import json

                    return json.loads(v)
                except Exception:
                    pass
            return [lang.strip() for lang in v.split(",") if lang.strip()]
        return v

    ingestion_chunk_size: int = 600
    ingestion_chunk_overlap: int = 120

    retrieval_chunk_top_k: int = 20
    retrieval_rerank_top_k: int = 10
    retrieval_hybrid_top_k: int = 20
    retrieval_context_max_chars: int = 30000

    database_url: str = "replace-me"
    redis_password: str = ""
    redis_url: str = "redis://redis:6379/0"
    redis_broker_db: int = 2
    redis_result_db: int = 1

    @property
    def redis_url_auth(self) -> str:
        pwd = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{pwd}redis:6379/0"

    @property
    def celery_broker_url_auth(self) -> str:
        pwd = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{pwd}redis:6379/{self.redis_broker_db}"

    @property
    def celery_result_backend_auth(self) -> str:
        pwd = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{pwd}redis:6379/{self.redis_result_db}"

    jwt_secret: str = "replace-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    max_upload_size_mb: int = 2048
    allowed_file_types: str = (
        "application/pdf,"
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document,"
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,"
        "text/plain,text/markdown,"
        "application/vnd.ms-excel,application/msword"
    )
    max_filename_length: int = 255

    rate_limit_relaxed_mode: bool = True
    rate_limit_relaxed_floor: int = 10000

    storage_backend: str = "s3"
    s3_endpoint: str = "rustfs:9000"
    s3_access_key: str = ""
    s3_secret_key: str = "replace-me"
    s3_bucket: str = "rag-documents"
    s3_secure: bool = False
    allowed_hosts: str = "localhost,127.0.0.1,0.0.0.0"
    cors_origins: str = "http://localhost"

    embedding_model: str = "tei"
    embedding_hf_model: str = "Alibaba-NLP/gte-multilingual-base"
    embedding_vector_size: int = 768
    embedding_batch_size: int = 8
    embedding_api_base: str = "http://ai-embedding:80/v1"
    embedding_api_key: str = ""
    vector_store: str = "qdrant"
    qdrant_url: str = "http://qdrant:6333"
    qdrant_api_key: str | None = None
    qdrant_collection: str = "documents_vectors"
    qdrant_timeout: int = 30

    chat_session_ttl_days: int = 30
    chat_history_redis_ttl: int = 86400
    chat_history_limit: int = 40

    ai_temperature: float = 0.3
    ai_max_output_tokens: int = 8192
    ai_max_history_messages: int = 6
    ai_stream_timeout: float = 1800.0
    ai_http_max_connections: int = 50
    ai_http_keepalive_connections: int = 10
    ai_proxy_timeout: float = 120.0

    celery_task_time_limit: int = 3600
    celery_task_soft_time_limit: int = 3300
    celery_worker_max_memory_kb: int = 1_500_000
    celery_visibility_timeout: int = 7200
    celery_result_expires: int = 86400
    celery_max_tasks_per_child: int = 50
    celery_retry_backoff: int = 30
    celery_retry_backoff_max: int = 600
    celery_max_retries: int = 3

    rate_limit_global_rpm: int = 5000

    audit_stream_name: str = "audit:stream"
    audit_stream_batch_size: int = 100
    audit_stream_process_interval: float = 10.0
    audit_stream_maxlen: int = 50000

    memory_cache_ttl: int = 300
    doc_ids_cache_ttl: float = 60.0

    def model_post_init(self, __context) -> None:
        if not self.jwt_secret or self.jwt_secret == "replace-me":
            raise ValueError("JWT_SECRET must be configured")
        if len(self.jwt_secret) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters for security")
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
        if self.max_upload_size_mb < 1 or self.max_upload_size_mb > 4096:
            raise ValueError("MAX_UPLOAD_SIZE_MB must be between 1 and 4096")
        if self.max_filename_length < 20 or self.max_filename_length > 512:
            raise ValueError("MAX_FILENAME_LENGTH must be between 20 and 512")
        if not self.allowed_file_types:
            raise ValueError("ALLOWED_FILE_TYPES must not be empty")

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
        if base_limit < 1:
            raise ValueError("base_limit must be >= 1")
        if self.app_env == "production":
            return base_limit
        if self.rate_limit_relaxed_mode:
            return max(base_limit, self.rate_limit_relaxed_floor)
        return base_limit

    def get_allowed_file_types(self) -> set[str]:
        return set(t.strip() for t in self.allowed_file_types.split(",") if t.strip())


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    if not s.ai_proxy_api_key:
        logger.debug("AI_PROXY_API_KEY is not set — requests to 9Router will be unauthenticated")
    if s.rate_limit_relaxed_mode and s.app_env != "development":
        logger.warning(
            "RATE_LIMIT_RELAXED_MODE is enabled in %s environment — rate limits are relaxed. "
            "Set RATE_LIMIT_RELAXED_MODE=false for production security.",
            s.app_env,
        )
    return s


settings = get_settings()
