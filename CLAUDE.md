# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Running the Stack

```bash
# Build and start all services
docker compose up --build

# Start with on-premise vLLM LLM (requires GPU)
docker compose --profile onprem up --build

# Stop all services
docker compose down

# View logs for specific service
docker compose logs -f api
docker compose logs -f worker

# Rebuild specific service after code changes
docker compose up --build api
```

### Database Management

```bash
# Access PostgreSQL directly
docker exec -it chatbot-rag-db-1 psql -U db-admin -d ragbot

# Reset database (WARNING: destroys all data)
docker compose down
docker volume rm chatbot-rag_pgdata
docker compose up --build

# Database initialization is automatic via ops/init.sql
# No manual migration scripts needed
```

### Testing and Linting

```bash
# Run tests (if pytest is configured in future)
docker exec chatbot-rag-api-1 pytest

# Check service health
curl http://localhost:8000/api/v1/health

# Check Celery worker status
docker exec chatbot-rag-worker-1 celery -A app.core.celery_app.celery_app inspect ping
```

## High-Level Architecture

This is a **Docker-first RAG chatbot** for Vietnamese enterprise documents with hierarchical indexing and async ingestion.

### Core Technology Stack

- **API Framework**: FastAPI with async endpoints
- **Task Queue**: Celery with Redis broker (`acks_late=True`, `prefetch=1`, 25-min soft timeout)
- **Databases**:
  - PostgreSQL (users, documents, sessions, audit)
  - Qdrant (vectors and retrieval payloads)
  - Redis (queue, cache, rate limiting, registry)
  - RustFS (S3-compatible object storage for uploaded files)
- **Ingestion**: Docling → EasyOCR → LlamaIndex hierarchy → parallel embedding
- **Embedding**: BAAI/bge-m3 LOCAL (sentence-transformers), 1024-dim vectors, parallel batch processing (32 nodes per batch)
- **AI Refiner**: Rule-based heuristics (NOT Qwen/Gemini) - fixes OCR errors, detects headers, validates hierarchy
- **LLM Providers**: Adapter-based (Google Gemini demo mode, vLLM on-premise production mode)
- **OCR**: EasyOCR (vi+en), GPU auto-detected

### Adapter Pattern

All external integrations use adapters under `app/adapters/`:

- **LLM**: `app/adapters/ai/` — `google.py` (Gemini API), `vllm.py` (local inference)
- **Parsers**: `app/adapters/parsers/` — `docling.py` (primary), `classic.py` (fallback)
- **Embeddings**: `app/adapters/embeddings/` — `sentence_transformer.py` (BAAI/bge-m3 local, parallel batches)
- **Vector Stores**: `app/adapters/vector_stores/` — `qdrant.py`

**Never call external provider SDKs directly from route handlers**. Always use adapters.

### Ingestion Pipeline

The ingestion workflow (`app/services/ingestion/pipeline.py`) is:

1. **Upload**: API saves file to RustFS, creates `documents` row with `status=pending`
2. **Queue**: Enqueues `parse_document_task` to Celery, returns `task_id` immediately
3. **Download**: Worker downloads file from RustFS to RAM
4. **Parse**: Docling converts to Markdown → LlamaIndex creates hierarchical nodes
5. **Validate**: Hierarchy validator ensures parent-child consistency
6. **Embed**: Parallel batch embedding (32 nodes per batch) via `ThreadPoolExecutor`
7. **Persist**: Vectors to Qdrant, metadata to PostgreSQL
8. **Verify**: Post-ingestion verification confirms vectors indexed and file stored
9. **Unload**: Embedding model unloaded from VRAM to free resources

**Progress reporting** happens via callback after each chunk (not after each node). Status updates are written to DB in real-time.

### Chat and Retrieval

1. **Rate Limiting**: Atomic Lua script in Redis (no INCR+EXPIRE race condition)
2. **Query Cache**: Redis-backed, MD5-keyed, TTL=1h — skip re-embedding on repeated questions
3. **Embed**: Query text → vector (via BAAI/bge-m3 local, 1024-dim, fully offline)
4. **Retrieve**: Qdrant search → drop chunks with cosine similarity < 0.35
5. **Generate**: AI provider produces grounded answer with citations

### Hierarchical Document Indexing

Documents are indexed as **hierarchies**: document → chapters → sections → subsections

Each node preserves:
- Parent/child relationships
- Section context for better retrieval
- Citation metadata (filename, page numbers, section path)

This is **not naive chunking**. Do not replace with flat chunk retrieval.

### Hard-Delete Workflow

Deletion order is critical for consistency:

1. `registry.delete(document_id)` → marks as deleted, /status returns "deleted" immediately
2. Delete vectors from Qdrant
3. Delete file from RustFS
4. Delete DB row from PostgreSQL
5. `registry.purge(document_id)` → removes from registry

This ensures API returns "deleted" instantly while cleanup happens asynchronously.

### Hardware Auto-Detection

`app/core/hardware.py` detects CPU/GPU at startup and derives optimal settings:

- `celery_concurrency = min(cpu_count, 4)` — Docling + EasyOCR are CPU-heavy
- `embed_parallelism = min(cpu_count * 2, 16)` — Embedding API calls are I/O-bound

## Configuration

All configuration is centralized in `app/core/config.py` with environment variable overrides.

Key environment variables:

- `AI_PROVIDER` — "google" (demo) or "vllm" (on-premise)
- `INGESTION_ENGINE` — "docling" (recommended) or "classic" (fallback)
- `INGESTION_EMBEDDING_CHUNK_SIZE` — nodes per batch (default: 32)
- `RETRIEVAL_MIN_SCORE` — cosine similarity threshold (default: 0.35)
- `EMBEDDING_MODEL` — "sentence-transformer" (BAAI/bge-m3 local, offline)
- `EMBEDDING_HF_MODEL` — "BAAI/bge-m3" (1024-dim, multilingual)
- `AI_REFINER_TYPE` — "rule_based" (lightweight, no AI needed, 0GB VRAM)
- `VECTOR_STORE` — "qdrant"
- `GOOGLE_API_KEY` — Required for Gemini API (chat LLM only)
- `VLLM_BASE_URL` — Required for on-premise vLLM (future)

## Database Initialization

**The database is automatically initialized on container startup** via PostgreSQL's init hook.

- **Schema file**: `ops/init.sql` (single comprehensive file)
- **Mount point**: `./ops/init.sql:/docker-entrypoint-initdb.d/init.sql:ro` in docker-compose.yml
- **Idempotent**: Safe to re-run; uses `CREATE IF NOT EXISTS` pattern
- **No migrations needed**: Schema is complete at startup

If you need schema changes:
1. Edit `ops/init.sql`
2. `docker compose down`
3. `docker volume rm chatbot-rag_pgdata`
4. `docker compose up --build`

**Do not add runtime DDL patches** in Python code.

## Key Invariants

| Rule | Required behavior |
|------|-------------------|
| Async ingestion | Upload endpoint must return immediately with `task_id` |
| Provider boundary | Route handlers must never call provider SDKs directly |
| Hierarchical retrieval | Preserve document hierarchy during retrieval |
| Citation policy | Every grounded answer must include citations |
| Hard-delete | Delete in order: registry → vectors → file → DB → purge |
| Score threshold | Drop retrieval results with cosine similarity < 0.35 |
| Rate limiting | Use atomic Lua script, not INCR+EXPIRE |
| Progress reporting | Update after each chunk (32 nodes), not each node |

## Project Structure Notes

- `app/main.py` — FastAPI app, no DDL at startup
- `app/worker.py` — Celery tasks: `parse_document_task`, `delete_document_task`
- `app/core/celery_app.py` — Celery configuration with reliability settings
- `app/services/ingestion/rule_based_refiner.py` — Rule-based text refinement (NO AI)
- `app/services/rag.py` — Retrieval: cache → embed → Qdrant → score filter
- `app/services/query_cache.py` — Redis query embedding cache
- `app/services/throttle.py` — Atomic Lua rate limiter
- `app/services/document_cleanup.py` — Hard-delete workflow
- `app/services/registry.py` — Redis registry for task/document tracking
- `docs/` — Comprehensive architecture documentation (7 detailed MD files)

## API Endpoints

All endpoints are under `/api/v1/`:

- `POST /api/v1/auth/login` — JWT authentication
- `POST /api/v1/auth/logout` — Revoke token
- `POST /api/v1/upload` — Upload document (admin only), enqueues Celery task
- `GET /api/v1/status/{task_id}` — Poll ingestion progress
- `POST /api/v1/chat` — Chat with RAG, returns answer + citations
- `GET /api/v1/documents` — List documents
- `DELETE /api/v1/documents/{id}` — Hard-delete document
- `GET /api/v1/health` — Health check with dependency status

## Default Credentials

```
Username: admin
Password: abc123

Username: member
Password: abc123
```

## Storage Access

- **RustFS API**: `http://localhost:9000` (S3-compatible)
- **RustFS Console**: `http://localhost:9001` (web UI)
- **Qdrant Console**: `http://localhost:6333/dashboard`
- **PostgreSQL**: `localhost:5432` (db/ragbot)
- **Redis**: `localhost:6379`

## Important Implementation Notes

- **Embedding model is loaded fresh per task** and unloaded after completion to free VRAM
- **Docling is the primary parser**; classic parser is fallback only
- **EasyOCR models are pre-downloaded** in Docker image via BuildKit cache
- **AI Refiner uses rule-based heuristics** (regex + pattern matching) - 0GB VRAM, ~1ms per node
- **HuggingFace cache is persisted** via volume mount (`hf-cache`)
- **Progress callbacks translate English messages to Vietnamese** for user-facing status
- **Score threshold filtering** removes low-relevance chunks before LLM generation
- **Query embedding cache** significantly reduces API calls for repeated questions

## Development Guidelines

### Must (Required Practices)

1. **Use hierarchical RAG**, not naive chunking — Document structure must be preserved
2. **Default to answering from uploaded documents** — This is a document Q&A system first
3. **Use PostgreSQL as primary DB and Redis only for queue/cache** — PostgreSQL is the system of record
4. **Keep endpoints stable** — `/upload`, `/status/{task_id}`, `/chat`, `/documents/{document_id}` are public APIs
5. **Apply soft-delete exclusion and latest-version preference before retrieval** — Deleted docs must not appear in new answers
6. **Return citations for every grounded answer** — Transparency is required
7. **Prefer Docker-first implementation** — Everything must run in containers
8. **Keep code clean and readable** — Use clear service/adapter boundaries and recognizable design patterns
9. **Update README.md** whenever file or folder structure changes — Project tree must stay accurate
10. **Only route to SQL Server when the question clearly requires live business data** and an approved connector exists

### Must Not (Prohibited Practices)

1. **Do not implement binary-tree retrieval** — Use the existing hierarchical indexing
2. **Do not expose provider-specific payloads in public APIs** — Keep internal details abstracted
3. **Do not block upload requests on parsing** — Return immediately with `task_id`
4. **Do not hallucinate when citations are missing** — State "Information not found in documents"
5. **Do not open raw SQL connections from route handlers** — Use repository/service layer
6. **Do not let the model execute unrestricted SQL** — Use validated connectors only
7. **Do not replace hierarchical retrieval with flat chunking** — Context preservation is critical

### Retrieval Rules

1. **Parse document structure into a ToC tree** — Preserve hierarchy during ingestion
2. **Retrieve full sections plus parent context** — Not just individual chunks
3. **Apply soft-delete exclusion before retrieval** — Deleted documents must not appear in results
4. **Apply latest-version preference before retrieval** — Multiple versions of same document: use latest
5. **Soft-deleted docs must be excluded from new answers but preserved in history** — Show as `[Đã xóa]` in chat history

### Query Routing Rules

1. **Use document RAG by default** — This is a document-focused system
2. **Only route to SQL Server when the question clearly requires live business data** — Explicit user request or obvious business query
3. **Keep SQL access read-only, policy-checked, audited, and behind a connector/service layer** — No direct SQL execution
4. **If SQL is unavailable or not configured, answer from documents or state the limitation explicitly** — Graceful degradation
5. **Never mix SQL results with document results without clear attribution** — User must know source of each fact

### Build Style

1. **Make the smallest correct change** — Don't over-engineer
2. **Keep code provider-agnostic behind adapters** — Easy to swap providers
3. **Prefer explicit, boring, production-safe code over clever code** — Maintainability > cleverness
4. **Prefer clean code that another engineer can read and recognize quickly** — Obvious patterns > custom abstractions
5. **Keep design patterns obvious** — Adapters for providers/connectors, services for workflows, repositories for persistence
6. **After producing new code, always run a subagent review pass** — Catch duplication, broken wiring, and obvious regressions before considering task complete

## Documentation Reference

When exploring the codebase, read these documents first:

1. **`docs/01_SYSTEM_ARCHITECTURE.md`** — Overall system design
2. **`docs/02_DATABASE_AND_PROJECT.md`** — Database schema and project structure
3. **`docs/03_CORE_WORKFLOWS.md`** — Ingestion, retrieval, and chat workflows
4. **`docs/04_API_CONTRACT_AND_SECURITY.md`** — API endpoints, security, and authentication
5. **`docs/05_RESOURCE_OPTIMIZATION_AND_EDGE_CASES.md`** — Performance tuning and edge cases
6. **`docs/06_DEPLOYMENT_AND_OBSERVABILITY.md`** — Deployment guide and monitoring
7. **`docs/07_INGESTION_AND_RETRIEVAL_STRATEGY.md`** — Deep dive into RAG implementation

## Project Status

**Current Phase:** Production Hardening (85% complete)

**Completed:**
- ✅ Hierarchical document indexing with BAAI/bge-m3 local embedding
- ✅ Rule-based refiner (0GB VRAM, 500x faster than AI-based)
- ✅ Streamlit tree visualizer with full feature set
- ✅ Async ingestion pipeline with Celery
- ✅ Hard-delete workflow with proper ordering
- ✅ Security hardened (strong passwords, CORS configured)

**In Progress:**
- ⏳ Docker image rebuild (code out of sync)
- ⏳ Service health verification
- ⏳ Testing verification

**Not Implemented:**
- ❌ Structured logging
- ❌ Monitoring/metrics collection
- ❌ Backup procedures automation

**Goal:** On-premise, hierarchical RAG chatbot for Vietnamese enterprise documents with local-first architecture (except temporary Gemini API for chat LLM)
