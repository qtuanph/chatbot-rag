import os
import sqlite3
from pathlib import Path

_DEFAULT_DIR = "/app/data"
if not Path(_DEFAULT_DIR).exists():
    _DEFAULT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")
DB_DIR = os.environ.get("SETTINGS_DB_DIR", _DEFAULT_DIR)
DB_FILENAME = "settings.db"


def get_db_path() -> str:
    path = Path(DB_DIR)
    path.mkdir(parents=True, exist_ok=True)
    return str(path / DB_FILENAME)


def get_db() -> sqlite3.Connection:
    db = sqlite3.connect(get_db_path())
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    return db


def _migrate_schema(db: sqlite3.Connection) -> None:
    """Add new columns for existing databases (idempotent — ignores IF NOT EXISTS via try/except)."""
    migrations = [
        # ai_providers additions
        "ALTER TABLE ai_providers ADD COLUMN config TEXT NOT NULL DEFAULT '{}'",
        "ALTER TABLE ai_providers ADD COLUMN last_test_status TEXT NOT NULL DEFAULT 'unknown'",
        "ALTER TABLE ai_providers ADD COLUMN last_test_at TIMESTAMP",
        "ALTER TABLE ai_providers ADD COLUMN last_error TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE ai_providers ADD COLUMN last_error_at TIMESTAMP",
        # api_keys additions
        "ALTER TABLE api_keys ADD COLUMN rate_limited_until TIMESTAMP",
        "ALTER TABLE api_keys ADD COLUMN backoff_level INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE api_keys ADD COLUMN last_error TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE api_keys ADD COLUMN last_error_at TIMESTAMP",
    ]
    for sql in migrations:
        try:
            db.execute(sql)
        except sqlite3.OperationalError:
            pass  # column already exists
    db.commit()


def init_db() -> None:
    db = get_db()
    try:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS ai_providers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                service_type TEXT NOT NULL,
                provider_name TEXT NOT NULL,
                display_name TEXT NOT NULL,
                url TEXT NOT NULL DEFAULT '',
                model TEXT NOT NULL DEFAULT '',
                api_key TEXT NOT NULL DEFAULT '',
                is_active INTEGER NOT NULL DEFAULT 0,
                is_builtin INTEGER NOT NULL DEFAULT 0,
                priority INTEGER NOT NULL DEFAULT 0,
                config TEXT NOT NULL DEFAULT '{}',
                last_test_status TEXT NOT NULL DEFAULT 'unknown',
                last_test_at TIMESTAMP,
                last_error TEXT NOT NULL DEFAULT '',
                last_error_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider_id INTEGER NOT NULL REFERENCES ai_providers(id) ON DELETE CASCADE,
                key_value TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                failure_count INTEGER NOT NULL DEFAULT 0,
                rate_limited_until TIMESTAMP,
                backoff_level INTEGER NOT NULL DEFAULT 0,
                last_error TEXT NOT NULL DEFAULT '',
                last_error_at TIMESTAMP,
                last_used_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_providers_service_type ON ai_providers(service_type);
            CREATE INDEX IF NOT EXISTS idx_keys_provider_id ON api_keys(provider_id);
        """)
        db.commit()
        _migrate_schema(db)
        _seed_templates(db)
        _sync_builtin_defaults(db)
    finally:
        db.close()


def _seed_templates(db: sqlite3.Connection) -> None:
    count = db.execute("SELECT COUNT(*) FROM ai_providers").fetchone()[0]
    if count > 0:
        return

    templates = [
        # Embedding
        (
            "embedding",
            "dmr",
            "Docker Model Runner",
            "http://model-runner.docker.internal:12434/engines/v1",
            "ai/qwen3-embedding:0.6B-F16",
            "",
            1,
            1,
            0,
        ),
        ("embedding", "openai", "OpenAI", "https://api.openai.com/v1", "text-embedding-ada-002", "", 0, 0, 1),
        (
            "embedding",
            "openrouter",
            "OpenRouter",
            "https://openrouter.ai/api/v1",
            "openai/text-embedding-3-small",
            "",
            0,
            0,
            2,
        ),
        ("embedding", "nvidia", "NVIDIA NIM", "https://integrate.api.nvidia.com/v1", "baai/bge-m3", "", 0, 0, 3),
        (
            "embedding",
            "gemini",
            "Google Gemini",
            "https://generativelanguage.googleapis.com/v1",
            "text-embedding-004",
            "",
            0,
            0,
            4,
        ),
        ("embedding", "cohere", "Cohere", "https://api.cohere.com/v1", "embed-multilingual-v3.0", "", 0, 0, 5),
        # Reranker
        (
            "reranker",
            "dmr",
            "Docker Model Runner (Fallback)",
            "http://model-runner.docker.internal:12434",
            "ai/qwen3-reranker:0.6B",
            "",
            0,
            1,
            1,
        ),
        (
            "reranker",
            "nvidia",
            "NVIDIA NIM",
            "https://ai.api.nvidia.com/v1/retrieval/nvidia/llama-nemotron-rerank-1b-v2/reranking",
            "nvidia/llama-nemotron-rerank-1b-v2",
            "",
            1,
            0,
            0,
        ),
        ("reranker", "cohere", "Cohere", "https://api.cohere.com", "rerank-multilingual-v3.0", "", 0, 0, 2),
        # LLM (9Router built-in) — seeded from .env so webapp can manage it
        (
            "llm",
            "9router",
            "9Router (Built-in)",
            "http://ai-proxy:2908/v1",
            "chatbot-rag",
            "",
            1,
            1,
            0,
        ),
        # Parser Engine
        (
            "parser",
            "llamaparse",
            "LlamaParse (Cloud)",
            "https://api.cloud.llamaindex.ai",
            "",
            "",
            1,
            1,
            0,
        ),
        (
            "parser",
            "docling",
            "Docling (Local OCR)",
            "",
            "",
            "",
            0,
            1,
            1,
        ),
    ]

    db.executemany(
        """INSERT INTO ai_providers
           (service_type, provider_name, display_name, url, model, api_key, is_active, is_builtin, priority)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        templates,
    )
    db.commit()


def _sync_builtin_defaults(db: sqlite3.Connection) -> None:
    db.execute(
        """
        UPDATE ai_providers
        SET display_name = ?, url = ?, model = ?, updated_at = CURRENT_TIMESTAMP
        WHERE service_type = 'embedding' AND is_builtin = 1
        """,
        ("Docker Model Runner", "http://model-runner.docker.internal:12434/engines/v1", "ai/qwen3-embedding:0.6B-F16"),
    )
    db.execute(
        """
        UPDATE ai_providers
        SET provider_name = ?, display_name = ?, url = ?, model = ?, updated_at = CURRENT_TIMESTAMP
        WHERE service_type = 'reranker' AND is_builtin = 1
        """,
        (
            "dmr",
            "Docker Model Runner (Fallback)",
            "http://model-runner.docker.internal:12434",
            "ai/qwen3-reranker:0.6B",
        ),
    )
    db.commit()



