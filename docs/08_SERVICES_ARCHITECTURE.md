# Services Architecture (Reorganized April 17, 2026)

## Directory Structure

The `app/services/` module has been reorganized from a flat structure into **6 logical subpackages** for better maintainability and team development velocity:

```
app/services/
├── __init__.py                 # Backward-compatibility re-exports
├── auth/                       # Authentication & security services
│   ├── __init__.py
│   ├── service.py              # JWT token creation, password hashing/verification
│   ├── token_blacklist.py      # Redis-backed JWT revocation
│   └── throttle.py             # Atomic Lua-based rate limiting
├── documents/                  # Document management & cleanup
│   ├── __init__.py
│   ├── registry.py             # DocumentRegistry: Redis task/document tracking
│   └── cleanup.py              # hard_delete_document: 5-step ordered deletion
├── retrieval/                  # RAG & embeddings caching
│   ├── __init__.py
│   ├── rag.py                  # 2-stage retrieval: sections → chunks
│   └── cache.py                # QueryEmbeddingCache: MD5-keyed query vector cache
├── chat/                       # Chat session management
│   ├── __init__.py
│   └── store.py                # ChatStore: Redis-backed chat history & sessions
├── system/                     # System & monitoring services
│   ├── __init__.py
│   ├── health.py               # Health checks: database, Redis, storage, AI provider
│   └── audit.py                # Security audit logging
├── ingestion/                  # Document ingestion pipeline
│   ├── __init__.py
│   ├── pipeline.py             # IngestionPipeline: orchestrates parsing → embedding → storage
│   ├── parser_manager.py       # ParserManager: Docling (primary) + fallback parsers
│   ├── hierarchy_validator.py  # HierarchyValidator: validates document section hierarchy
│   ├── rule_based_refiner.py   # AI Refiner: rule-based text refinement (0GB VRAM)
│   └── recovery.py             # PipelineRecoveryManager: stuck document recovery, orphan cleanup
└── storage/                    # Object storage abstraction
    ├── __init__.py
    └── document_store.py       # S3-compatible interface (RustFS/MinIO)
```

## Import Patterns

### New Code (Preferred)
Import directly from subpackages:

```python
# Authentication
from app.services.auth.service import create_access_token, hash_password, verify_password
from app.services.auth.token_blacklist import TokenBlacklist
from app.services.auth.throttle import RequestThrottle

# Documents
from app.services.documents.registry import DocumentRegistry
from app.services.documents.cleanup import hard_delete_document

# Retrieval
from app.services.retrieval.rag import retrieve_context, build_answer
from app.services.retrieval.cache import QueryEmbeddingCache

# Chat
from app.services.chat.store import ChatStore

# System
from app.services.system.health import build_health_payload
from app.services.system.audit import safe_record_audit

# Ingestion
from app.services.ingestion.pipeline import IngestionPipeline
from app.services.ingestion.recovery import PipelineRecoveryManager
```

### Legacy Code (Still Works)
Backward-compatible re-exports in `app/services/__init__.py`:

```python
# All of these still work due to __init__.py re-exports
from app.services import create_access_token
from app.services import TokenBlacklist, RequestThrottle
from app.services import DocumentRegistry, hard_delete_document
from app.services import retrieve_context, build_answer, QueryEmbeddingCache
from app.services import ChatStore
from app.services import build_health_payload, safe_record_audit
from app.services import IngestionPipeline, PipelineRecoveryManager
```

## Service Responsibilities

### `auth/` — Authentication & Rate Limiting
- **service.py**: JWT creation (HS256, JTI-based), BCrypt password hashing
- **token_blacklist.py**: Redis-backed revocation via JWT ID (JTI)
- **throttle.py**: Atomic Lua sliding-window rate limiter (prevents INCR+EXPIRE race condition)

### `documents/` — Document Lifecycle
- **registry.py**: Tracks document/task state in Redis, supports idempotency
- **cleanup.py**: Hard-delete in 5 steps: `registry.delete()` → vectors → file → DB → registry.purge()`
  - Ensures `/status` immediately returns `deleted` to API clients

### `retrieval/` — RAG Engine
- **rag.py**: 2-stage retrieval (coarse sections → fine chunks), latest-version filtering, soft-delete exclusion
- **cache.py**: Query embedding cache (MD5-keyed, 1h TTL) to reduce repeated embedding calls

### `chat/` — Chat Sessions
- **store.py**: Redis-backed chat history and active session tracking (24h TTL)

### `system/` — Monitoring & Audit
- **health.py**: Dependency status checks (database, Redis, storage, AI provider)
- **audit.py**: Security audit event logging to PostgreSQL

### `ingestion/` — Document Processing
- **pipeline.py**: Orchestrates ingestion workflow with progress callbacks
- **parser_manager.py**: Docling (primary, Method D) + classic (fallback) parser routing
- **hierarchy_validator.py**: Validates section parent-child consistency (no orphans)
- **rule_based_refiner.py**: Lightweight text refinement (regex + patterns, 0GB VRAM, ~1ms per node)
- **recovery.py**: Pipeline failure recovery:
  - Stuck document detection (processing state > 30min)
  - Orphaned vector cleanup (vectors without matching sections)
  - Consistency validation
  - Idempotency checking

### `storage/` — Object Storage Abstraction
- **document_store.py**: S3-compatible interface (RustFS, MinIO, AWS S3)

## Key Design Principles

1. **Single Responsibility**: Each subpackage has a clear domain (auth, documents, retrieval, etc.)
2. **Clear Boundaries**: Services don't import between packages (loose coupling)
3. **Backward Compatibility**: Root `__init__.py` re-exports all public APIs
4. **Easy Discovery**: New developers can find related code in logical groups
5. **Testing**: Test fixtures can mock entire subpackages independently

## Migration Checklist for Developers

- [ ] New imports should use subpackage paths (`app.services.auth.service`)
- [ ] Existing imports from `app.services` continue to work (backward compatible)
- [ ] Old flat file imports (`app.services.rag`) are invalid — update to `app.services.retrieval.rag`
- [ ] IDE search works on directory names: `app/services/auth`, `app/services/retrieval`, etc.

## Related Documentation

- **CLAUDE.md**: Full system architecture and configuration
- **docs/03_CORE_WORKFLOWS.md**: Detailed ingestion, retrieval, chat workflows
- **docs/07_INGESTION_AND_RETRIEVAL_STRATEGY.md**: 2-stage retrieval implementation

---

*Last Updated: April 17, 2026 | Services Reorganization Phase*
