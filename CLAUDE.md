# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 🚨 CRITICAL: Memory Update Rule

**MANDATORY**: Khi có bất kỳ thay đổi hoặc tính năng mới được implement, **PHẢI CẬP NHẬT FILE NÀY NGAY LẬP TỨC** với:
- Kiến thức mới nhất về architecture
- Stack và dependencies mới nhất
- Breaking changes và migration notes
- Các pattern và practices mới được áp dụng

Đặc biệt quan trọng khi:
- ✅ Thay đổi AI model, embedding model, hoặc parser
- ✅ Thay đổi database schema
- ✅ Thay đổi API contracts
- ✅ Bổ sung features mới

**ĐỪNG để file này trở thành legacy knowledge!** Claude Code luôn đọc file này đầu tiên, nên nó phải phản ánh state hiện tại của system.

---

## AI Docs-First Protocol (Mandatory)

Mọi AI agent (Claude/Copilot/automation) phải đọc tài liệu theo thứ tự này trước khi sửa code:

1. `CLAUDE.md` (source of truth)
2. `docs/01_SYSTEM_ARCHITECTURE.md`
3. `docs/03_CORE_WORKFLOWS.md`
4. `docs/07_INGESTION_AND_RETRIEVAL_STRATEGY.md`
5. Task-specific docs:
  - API/Security: `docs/04_API_CONTRACT_AND_SECURITY.md`
  - Database/Schema: `docs/02_DATABASE_AND_PROJECT.md` + `ops/init.sql`
  - Deployment/Monitoring: `docs/06_DEPLOYMENT_AND_OBSERVABILITY.md`
  - Performance/Edge cases: `docs/05_RESOURCE_OPTIMIZATION_AND_EDGE_CASES.md`

Before implementation, agent must verify it can answer:
- Retrieval strategy currently used?
- Where sections and chunks are stored?
- Current embedding model and dimension?
- Hard-delete ordering and why it exists?

If any answer is unclear, stop and re-read docs before coding.

Enforcement in repository:
- CI guardrail: `.github/workflows/docs-first-guardrail.yml` (PR fails if code changes without docs/memory updates)
- CI guardrail: `.github/workflows/status-code-guardrail.yml` (fails on numeric status codes and direct `raise HTTPException(...)` in API layer)
- PR template: `.github/pull_request_template.md` (mandatory Docs-First confirmations)

---

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
docker compose logs -f upload-pipeline
docker compose logs -f cleanup-pipeline

# Rebuild specific service after code changes
docker compose up --build api
docker compose up --build upload-pipeline
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

### Health and Validation

```bash
# Check service health
curl http://localhost:8000/api/v1/health

# Check Celery worker status
docker exec chatbot-rag-worker-1 celery -A app.core.celery_app.celery_app inspect ping
docker exec chatbot-rag-cleanup-pipeline-1 celery -A app.core.celery_app.celery_app inspect ping
```

## High-Level Architecture

This is a **Docker-first RAG chatbot** for Vietnamese enterprise documents with hierarchical indexing and async ingestion.

### Core Technology Stack (Updated 2026-04-15)

- **Frontend**: Next.js 16 with shadcn/ui v4, next-auth v5 (JWT), SSE streaming
- **API Framework**: FastAPI with async endpoints
- **Task Queue**: Celery with Redis broker (`acks_late=True`, `prefetch=1`, 25-min soft timeout)
- **Databases**:
  - PostgreSQL (users, documents, sections, sessions, audit)
  - Qdrant (vectors and retrieval payloads with section_id metadata)
  - Redis (queue, cache, rate limiting, registry)
  - RustFS (S3-compatible object storage for uploaded files)
- **Ingestion**: Docling `iterate_items()` (Method D) → Smart OCR (2-pass) → Section extraction → Chunk splitting → parallel embedding
- **Embedding**: BAAI/bge-m3 LOCAL (sentence-transformers), 1024-dim vectors, parallel batch processing (32 nodes per batch)
- **AI Refiner**: Rule-based heuristics (NOT Qwen/Gemini) - 0GB VRAM, ~1ms per node
- **Retrieval**: 2-stage (Sections → Chunks) with PostgreSQL section store + Qdrant vector search
- **LLM Providers**: Adapter-based
  - **Google AI**: `gemma-4-26b-a4b-it` (26B parameters, high quality)
  - **vLLM**: On-premise mode (future)
- **OCR**: EasyOCR (vi+en), GPU auto-detected, pre-downloaded in Docker image

### Current AI Model Configuration

**Chat LLM (Google AI):**
- Model: `gemma-4-26b-a4b-it`
- Provider: Google Generative AI (API key required)
- Default in config: `gemma-4-26b-a4b-it`
- Environment: `GOOGLE_API_KEY` (single key, no rotation)

**Embedding Model:**
- Model: `BAAI/bge-m3` (sentence-transformers)
- Dimension: 1024
- Max tokens: 8192
- Languages: Multilingual (optimized for Vietnamese)
- Deployment: LOCAL, offline, no external calls

### 2-Stage Retrieval Architecture (Implemented)

**Architecture overview:**
- **Section extraction**: Markdown → split by headings → sections (Level 1)
- **Chunk splitting**: Each section → chunks (Level 2, ~400 tokens, ~75 token overlap)
- **Dual storage**: Sections → PostgreSQL (`document_sections` table), Chunks → Qdrant (with `section_id` metadata)
- **2-stage retrieval**: Query → Stage 1 (coarse section search, top 3) → Stage 2 (fine chunk search within sections, top 5)
- **Fallback**: If no sections found, falls back to flat vector retrieval

**Key components:**
- `DoclingParser._extract_sections_from_markdown()` — Section + chunk extraction from Markdown
- `SectionRepository` — PostgreSQL section storage/query
- `IngestionPipeline` — Orchestrates section storage + vector indexing
- `retrieve_context()` — 2-stage retrieval (sections → chunks)

**Performance targets:**
  - Section retrieval: <0.5s
  - Chunk retrieval: <1s
  - Total query time: <2s
  - Large documents (300-500 pages): 5-10 min ingestion

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
2. **Queue**: Enqueues `parse_document_task` to Celery (upload-pipeline worker), returns `task_id` immediately
3. **Download**: Worker downloads file from RustFS to RAM
4. **Parse**: Docling `iterate_items()` (Method D) extracts items directly with 100% metadata fidelity (page numbers, heading levels, table structures)
5. **Smart OCR**: 2-pass strategy — fast extraction first (no OCR for native PDFs), OCR fallback only for scanned PDFs
6. **Validate**: Hierarchy validator ensures parent-child consistency
7. **Refine**: Rule-based refiner fixes OCR errors, detects headers (0GB VRAM, ~1ms per node)
8. **Store Sections**: Sections persisted to PostgreSQL `document_sections` table via `SectionRepository`
9. **Embed**: Parallel batch embedding (32 nodes per batch) via `ThreadPoolExecutor`
10. **Persist**: Chunks (with `section_id` metadata) to Qdrant
11. **Verify**: Post-ingestion verification confirms vectors indexed and file stored
12. **Unload**: Embedding model unloaded from VRAM to free resources

**Progress reporting** happens via callback after each chunk (not after each node). Status updates are written to DB in real-time.

### Chat and Retrieval (2-Stage)

1. **Rate Limiting**: Atomic Lua script in Redis (no INCR+EXPIRE race condition)
2. **Query Cache**: Redis-backed, MD5-keyed, TTL=1h — skip re-embedding on repeated questions
3. **Embed**: Query text → vector (via BAAI/bge-m3 local, 1024-dim, fully offline)
4. **Stage 1 - Section Retrieval**: Qdrant search → group by section_id → pick top 3 sections (threshold ≥ 0.30)
5. **Stage 2 - Chunk Retrieval**: Qdrant search within top sections → get detailed chunks (threshold ≥ 0.35)
6. **Generate**: AI provider produces grounded answer with citations from sections + chunks

### Hierarchical Document Indexing

Documents are indexed as **2-level hierarchies**: document → sections → chunks

**Sections (Level 1):** Stored in PostgreSQL `document_sections` table
- Based on document headings (H1-H6)
- Contains: title, content, level, breadcrumb, parent_section_id
- Used for coarse-grained Stage 1 retrieval

**Chunks (Level 2):** Stored in Qdrant with `section_id` metadata
- ~400 tokens each, ~75 token overlap
- Linked to parent section via `section_id` in metadata
- Used for fine-grained Stage 2 retrieval

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

- `AI_PROVIDER` — "google" (current) or "vllm" (on-premise, future)
- `INGESTION_ENGINE` — "docling" (recommended) or "classic" (fallback)
- `INGESTION_EMBEDDING_CHUNK_SIZE` — nodes per batch (default: 32)
- `RETRIEVAL_MIN_SCORE` — cosine similarity threshold for chunks (default: 0.35)
- `RETRIEVAL_SECTION_TOP_K` — Stage 1: top sections to retrieve (default: 3)
- `RETRIEVAL_CHUNK_TOP_K` — Stage 2: top chunks per section (default: 5)
- `RETRIEVAL_CHUNK_SIZE` — target chunk size in tokens (default: 400)
- `RETRIEVAL_CHUNK_OVERLAP` — overlap between chunks in tokens (default: 75)
- `RETRIEVAL_SECTION_MIN_SCORE` — lower threshold for section search (default: 0.30)
- `EMBEDDING_MODEL` — "sentence-transformer" (BAAI/bge-m3 local, offline)
- `EMBEDDING_HF_MODEL` — "BAAI/bge-m3" (1024-dim, multilingual)
- `AI_REFINER_TYPE` — "rule_based" (lightweight, no AI needed, 0GB VRAM)
- `VECTOR_STORE` — "qdrant"
- `GOOGLE_API_KEY` — Required for Google AI API (single key, no rotation)
- `GOOGLE_MODEL` — Model name (default: `gemma-4-26b-a4b-it`)
- `VLLM_BASE_URL` — Required for on-premise vLLM (future)

**Production-only guardrails**: `app/core/config.py` rejects wildcard `ALLOWED_HOSTS`, localhost `CORS_ORIGINS`, `RATE_LIMIT_RELAXED_MODE=true`, and `S3_SECURE=false` when `APP_ENV=production`.

**Note**: Google API key rotation has been REMOVED. Only use single `GOOGLE_API_KEY`.

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
| 2-stage retrieval | Section search (coarse) → Chunk search (fine) within sections |
| Section storage | Sections stored in PostgreSQL, chunks in Qdrant with section_id |
| Citation policy | Every grounded answer must include citations |
| Hard-delete | Delete in order: registry → vectors → sections → file → DB → purge |
| Score threshold | Sections ≥ 0.30, Chunks ≥ 0.35 |
| Rate limiting | Use atomic Lua script, not INCR+EXPIRE |
| Progress reporting | Update after each chunk (32 nodes), not each node |
| Error contract | JSON errors use unified envelope (`error.*`) and keep `detail` for compatibility |

## Project Structure Notes

### Core Application
- `app/main.py` — FastAPI app, no DDL at startup
- `app/core/celery_app.py` — Celery configuration with reliability settings
- `app/core/http_errors.py` — Centralized HTTPException helper functions (status-consistent API errors)
- `app/core/config.py` — Pydantic Settings with production guardrails

### Workers & Tasks
- `app/workers/upload_pipeline.py` — Celery ingestion tasks (GPU worker): `parse_document_task`
- `app/workers/cleanup_pipeline.py` — Celery cleanup tasks (lightweight worker + beat): `delete_document_task`, `cleanup_old_chat_sessions_task`

### Services (Reorganized into 6 subpackages for clarity)
- `app/services/auth/` — Authentication & rate limiting
  - `service.py` — JWT creation, password hashing
  - `token_blacklist.py` — Redis-backed JWT revocation
  - `throttle.py` — Atomic Lua-based rate limiter (prevents race conditions)
- `app/services/documents/` — Document lifecycle
  - `registry.py` — Redis registry for task/document tracking
  - `cleanup.py` — Hard-delete workflow (5-step ordered deletion)
- `app/services/retrieval/` — RAG engine
  - `rag.py` — 2-stage retrieval: sections → chunks, with soft-delete & version filtering
  - `cache.py` — Redis query embedding cache (MD5-keyed, 1h TTL)
- `app/services/chat/` — Chat sessions
  - `store.py` — Redis-backed chat history
- `app/services/system/` — System & monitoring
  - `health.py` — Dependency health checks (database, Redis, storage, AI provider)
  - `audit.py` — Security audit logging
- `app/services/ingestion/` — Document processing pipeline
  - `pipeline.py` — Orchestrates full ingestion workflow
  - `parser_manager.py` — Docling (primary) + classic (fallback) parsers
  - `hierarchy_validator.py` — Validates section hierarchy
  - `rule_based_refiner.py` — Rule-based text refinement (0GB VRAM, ~1ms per node)
  - `recovery.py` — Pipeline recovery: stuck detection, orphan cleanup, consistency validation
- `app/services/storage/` — Object storage abstraction
  - `document_store.py` — S3-compatible interface (RustFS/MinIO)

### Documentation
- `docs/01_SYSTEM_ARCHITECTURE.md` — Overall system design
- `docs/02_DATABASE_AND_PROJECT.md` — Database schema
- `docs/03_CORE_WORKFLOWS.md` — Ingestion, retrieval, chat workflows
- `docs/04_API_CONTRACT_AND_SECURITY.md` — API endpoints & security
- `docs/05_RESOURCE_OPTIMIZATION_AND_EDGE_CASES.md` — Performance & edge cases
- `docs/06_DEPLOYMENT_AND_OBSERVABILITY.md` — Deployment guide
- `docs/07_INGESTION_AND_RETRIEVAL_STRATEGY.md` — 2-stage RAG implementation
- `docs/08_SERVICES_ARCHITECTURE.md` — Services module organization (NEW)

## API Endpoints

All endpoints are under `/api/v1/`:

### Auth
- `POST /api/v1/auth/login` — JWT authentication
- `POST /api/v1/auth/logout` — Revoke token
- `GET /api/v1/auth/me` — Get current user info
- `POST /api/v1/auth/users` — Create user (admin only)
- `GET /api/v1/auth/users` — List users (admin only)
- `DELETE /api/v1/auth/users/{username}` — Delete user (admin only)

### Documents & Ingestion
- `POST /api/v1/upload` — Upload document (admin only), enqueues Celery task
- `GET /api/v1/status/{task_id}` — Poll ingestion progress
- `GET /api/v1/documents` — List documents
- `GET /api/v1/documents/{id}` — Get document details
- `DELETE /api/v1/documents/{id}` — Hard-delete document

### Chat
- `POST /api/v1/chat` — Chat with RAG, returns answer + citations (non-streaming)
- `POST /api/v1/chat/stream` — SSE streaming chat endpoint
- `GET /api/v1/chat/sessions` — List user's chat sessions

### Tree API
- `GET /api/v1/tree/{document_id}` — Get document tree structure
- `GET /api/v1/tree/{document_id}/nodes/{node_id}` — Get node details
- `GET /api/v1/tree/{document_id}/search` — Search nodes in tree

### Health & Monitoring
- `GET /api/v1/health` — Health check with dependency status
- `GET /api/v1/health/data` — Detailed health data with checks
- `GET /api/v1/health/nodes` — List Qdrant nodes for a document
- `GET /api/v1/health/node` — Get single Qdrant node details

## Default Credentials

```
Username: admin
Password: abc123

Username: member
Password: abc123
```

## Storage Access

- **Webapp**: `http://localhost:3000` (Next.js 16 frontend)
- **API**: `http://localhost:8000` (FastAPI backend)
- **RustFS API**: `http://localhost:9000` (S3-compatible)
- **RustFS Console**: `http://localhost:9001` (web UI)
- **Qdrant Console**: `http://localhost:6333/dashboard`
- **PostgreSQL**: `localhost:5432` (db/ragbot)
- **Redis**: `localhost:6379`

## Important Implementation Notes

- **Embedding model is loaded fresh per task** and unloaded after completion to free VRAM
- **Docling is the primary parser** using `iterate_items()` (Method D) — extracts page numbers, heading levels, table structures directly from document items
- **Smart OCR**: 2-pass strategy — fast no-OCR first, OCR fallback only when scanned PDF detected (images always OCR)
- **Classic parser** is fallback only
- **EasyOCR models are pre-downloaded** in Docker image via BuildKit cache
- **AI Refiner uses rule-based heuristics** (regex + pattern matching) - 0GB VRAM, ~1ms per node — NO AI in ingestion pipeline
- **HuggingFace cache is persisted** via volume mount (`hf-cache`)
- **Progress callbacks translate English messages to Vietnamese** for user-facing status
- **Score threshold filtering** removes low-relevance chunks before LLM generation
- **Query embedding cache** significantly reduces API calls for repeated questions
- **SSE streaming** for real-time chat responses via `/api/v1/chat/stream`
- **Next.js 16 frontend** with shadcn/ui v4 components and next-auth v5 (JWT strategy)
- **Webapp Docker runtime** uses Next.js standalone artifacts only (no full dev `node_modules` in runner image)
- **Docker Compose published ports** default to `127.0.0.1` bindings for safer local/dev exposure; production should still sit behind an ingress/proxy

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

## Project Status (Updated 2026-04-17)

**Current Phase:** Production Hardening

**Completed:**
- ✅ Hierarchical document indexing with BAAI/bge-m3 local embedding
- ✅ 2-stage retrieval architecture (Sections → Chunks)
- ✅ `document_sections` table in PostgreSQL for section-level storage
- ✅ **Method D**: Docling `iterate_items()` for direct item extraction — preserves page numbers, heading levels, table structures with 100% metadata fidelity
- ✅ **Smart OCR Strategy**: 2-pass — fast no-OCR for native PDFs, OCR fallback only for scanned PDFs
- ✅ Chunk splitting (~400 tokens, ~75 token overlap) with section_id linking
- ✅ Rule-based refiner (0GB VRAM, 500x faster than AI-based) — restored as default
- ✅ Async ingestion pipeline with Celery + section storage
- ✅ **Worker architecture refactor**: `upload-pipeline` (GPU) + `cleanup-pipeline` (lightweight + beat)
- ✅ **Chat session auto-delete**: TTL=1 day via Celery beat daily cleanup
- ✅ Hard-delete workflow with proper ordering
- ✅ Security hardened (strong passwords, CORS configured)
- ✅ Google API key rotation removed (single key only)
- ✅ AI model updated to `gemma-4-26b-a4b-it`
- ✅ Next.js 16 frontend with shadcn/ui v4
- ✅ next-auth v5 with JWT strategy and Credentials provider
- ✅ SSE streaming chat with thinking tags parsing
- ✅ Admin dashboard (health monitoring, document management, user management)
- ✅ Role-based routing (admin vs member)
- ✅ Tree API for hierarchical document exploration
- ✅ User CRUD operations (admin only)
- ✅ Document detail page with react-flow tree visualization
- ✅ Dead-code cleanup: removed unused `app/adapters/embeddings/gemini.py` adapter
- ✅ **Services reorganization**: Refactored flat `app/services/` into 6 logical subpackages (auth/, documents/, retrieval/, chat/, system/, ingestion/) for improved team development velocity and code discoverability — backward-compatible re-exports maintained

**In Progress:**
- ⏳ Docker build + integration testing of Method D + Smart OCR

**Upcoming:**
- 🔜 Performance optimization for large documents (300-500 pages)
- 🔜 Monitoring/metrics collection
- 🔜 Phase 3 pipeline recovery test suite completion

**Not Implemented:**
- ❌ Structured logging
- ❌ Backup procedures automation
- ❌ Automated pytest suite (removed from runtime repo)

**Goal:** On-premise, hierarchical RAG chatbot for Vietnamese enterprise documents with 2-stage retrieval for optimal performance on large documents.
