# 01 — Architecture and Data Model

Single source of truth for system design, data model, and invariants. Security details in `03_API_CONTRACTS.md`.

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Frontend | Next.js 16 + shadcn/ui v4 + next-auth v5 (JWT) |
| Backend | FastAPI async |
| Workers | upload-pipeline (GPU, ingestion) + cleanup-pipeline (lightweight, deletion + beat) |
| Database | PostgreSQL 18 (metadata, auth, sessions, audit) |
| Vectors | Qdrant (chunk vectors + retrieval payload) |
| Object storage | RustFS (raw uploads + artifacts) |
| Queue/Cache | Redis (Celery broker, embedding cache, rate limiting, chat hot cache with pipeline atomic ops) |
| Embedding | AITeamVN/Vietnamese_Embedding_v2 (1024-dim, local, GPU fp16 / CPU ONNX) |
| Reranker | AITeamVN/Vietnamese_Reranker (GPU auto / CPU fallback, cross-encoder, top 5) |
| AI Provider | Google AI gemma-4-26b-a4b-it (singleton via lru_cache, x-goog-api-key header, httpx connection pool) |
| Ingestion | Docling iterate_items() (Method D) + PaddleOCR (RapidOCR ONNX, vi+en, force_full_page_ocr=True) + Rule-based refiner |
| Reverse proxy | nginx on port 80 (all traffic: SSE, NextAuth, API, static) |

## Storage Split

| Store | Responsibility |
|-------|---------------|
| PostgreSQL | Auth, roles, documents, **document_sections** (canonical tree order), chat sessions/messages, user_memories, audit |
| Qdrant | Chunk vectors + payload with `section_id` metadata |
| RustFS | Raw uploaded files + ingestion artifacts |
| Redis | Celery broker/backend (DB 0/1), app cache (DB 2), query embedding cache (MD5, 1h TTL), rate limiting, user memory cache (5min TTL), chat hot history. maxmemory 512mb, allkeys-lru |

## Core PostgreSQL Tables

| Table | Purpose |
|-------|---------|
| `roles` | Role definitions (admin, member) |
| `users` | Authenticated accounts with bcrypt hash |
| `documents` | File metadata, status lifecycle, version, ingestion state |
| `document_sections` | Hierarchical tree: parent_section_id, order_index, page_range, breadcrumb |
| `chat_sessions` | Per-user conversation sessions (CASCADE delete with messages) |
| `chat_messages` | Message history with citations, token counts (tokens_in, tokens_out, latency_ms, model_used, estimated_cost_usd) |
| `user_memories` | Persistent per-user facts/preferences/corrections |
| `security_audit` | Audit trail for sensitive actions |
| `data_sources` | SQL connector registry (Phase 2) |
| `data_source_schema_cache` | Connector schema cache (Phase 2) |
| `data_source_query_audit` | SQL query audit log (Phase 2) |

### documents Table Columns

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | pgcrypto generated |
| title / file_name | VARCHAR(500) | User-provided title / original filename |
| file_path | VARCHAR(1000) | RustFS object URI |
| sha256 | VARCHAR(64) | Duplicate detection |
| file_type | VARCHAR(50) | pdf, docx, xlsx, txt |
| file_size | BIGINT | Bytes |
| version | INTEGER ≥ 1 | Auto-incremented per filename |
| status | VARCHAR(50) | pending → processing → ready / failed |
| status_stage | VARCHAR(50) | Fine-grained processing stage |
| progress_percent | INTEGER 0-100 | Live progress for frontend |
| status_message | VARCHAR(500) | Human-readable status |
| status_updated_at | TIMESTAMPTZ | Last status change |
| parse_error | TEXT | Error detail when failed |
| extra_metadata | JSONB | Ingestion artifact, warnings, timing |
| deleted_at | TIMESTAMPTZ | Legacy; not used in hard-delete path |
| created_by | UUID FK → users | Uploader |
| created_at / updated_at | TIMESTAMPTZ | Auto-managed via trigger |

## Component Diagram

```mermaid
graph TD
    Client[Browser] --> WebApp[Next.js 16]
    WebApp -->|/api/bep/ proxy| API[FastAPI Routes]
    API --> AuthSvc[AuthService → AuthRepository]
    API --> DocSvc[DocumentService → DocumentRepository]
    API --> ChatSvc[ChatService → ChatRepository]
    API --> TreeSvc[TreeService → SectionRepository]
    API --> MemSvc[MemoryService → UserMemoryService → MemoryRepository]
    API --> AnalyticSvc[AnalyticsService → AnalyticsRepository]
    API --> HealthSvc[HealthService]
    ChatSvc --> Retriever[RAG Retrieval → DocumentRepository + SectionRepository]
    Retriever --> Embedder[Vietnamese_Embedding_v2 → Qdrant]
    ChatSvc --> Memory[UserMemoryService → Redis + PostgreSQL]
    DocSvc --> Upload[Upload → Redis queue]
    Upload --> Worker[upload-pipeline · GPU]
    Worker --> Parser[ParserManager → Docling Method D + PaddleOCR]
    Parser --> Sections[SectionRepository → PostgreSQL]
    Parser --> EmbedWorker[Vietnamese_Embedding_v2 → Qdrant]
    Redis --> Cleanup[cleanup-pipeline + CleanupService + Beat]
```

## Controller-Service-Repository Architecture

Strict 3-layer separation enforced across all route files:

```
Route (Controller)              Service (Business Logic)        Repository (Data Access)
┌─────────────────────┐        ┌──────────────────────┐        ┌────────────────────┐
│ HTTP request parsing │──→     │ Validation           │──→     │ SELECT/INSERT/     │
│ Auth deps            │        │ Orchestration        │        │ UPDATE/DELETE      │
│ Response formatting  │←──     │ Calculations         │←──     │ Session management │
│ Status codes         │        │ Cross-service calls  │        │ Model → Dict       │
└─────────────────────┘        └──────────────────────┘        └────────────────────┘
```

| Layer | Location | Convention |
|-------|----------|-----------|
| Controller | `app/api/routes/*.py` | HTTP only — NO `SessionLocal`, NO business logic. Catches domain exceptions (`ValueError`/`RuntimeError`) from services and translates to `http_errors.*` |
| Service | `app/services/{domain}/*_service.py` | Takes Repository via constructor, contains all business logic. Raises `ValueError`/`RuntimeError` only — NEVER `http_errors.*` |
| Repository | `app/repositories/*_repository.py` | Takes `Session` via constructor, returns dicts (not ORM models) |
| DI Wiring | `app/api/deps.py` | FastAPI `Depends()` factories for all repos and services |

### Current Service/Repository Map

| Domain | Service | Repository |
|--------|---------|-----------|
| Auth | `AuthService` | `AuthRepository` |
| Chat | `ChatService` (prepare_chat, extract_memories) | `ChatRepository` |
| Documents | `DocumentService` (build_vector_store factory) | `DocumentRepository` (get_latest_active_document_ids, get_titles_by_ids, hard_delete) |
| Sections | `TreeService` | `SectionRepository` (get_sections_for_rag, get_section_ids_by_document) |
| Cleanup | `CleanupService` | `DocumentRepository` + `SectionRepository` |
| Memories | `MemoryService` → `UserMemoryService` | `MemoryRepository` |
| Analytics | `AnalyticsService` | `AnalyticsRepository` |
| Health | `HealthService` | (config-only, no repo) |

## Runtime Data Flow

| Stage | Path | Output |
|-------|------|--------|
| Upload | Browser → /api/bep/ → proxy → API → RustFS | File persisted, document row pending |
| Queue | API → Redis → Worker | Async task, task_id returned (202) |
| Parse | Worker → Docling Method D + PaddleOCR (force_full_page_ocr=True) → sections + chunks | Items with page spans, heading levels |
| Validate | HierarchyValidator (app/utils/) + RuleBasedRefiner (app/utils/text_refiner.py, 0GB VRAM, ~1ms) | Cleaned, validated text |
| Store | SectionRepository → PostgreSQL → Embed → Qdrant | document_sections rows + vectors |
| Retrieve | QueryCache → hybrid search (dense + BM25 RRF fusion) → section grouping (≥0.30) → cross-encoder rerank (top 5) → context assembly | Top sections + chunks with citations |
| Memory | UserMemoryService (redis.Redis + MemoryRepository via DI) → Redis cache → inject systemInstruction | Personalized prompt |
| Stream | AI Provider → strip_reasoning() → SSE → proxy → Browser | Grounded answer with citations, token stats, cost estimate |
| Extract | Post-response → async Gemini → user_memories | Learned facts for future turns |

## Non-Negotiable Invariants

| Rule | Behavior |
|------|----------|
| API contracts | Keep upload/status/chat/document endpoints stable |
| Async ingestion | Upload must never block on parsing |
| Provider boundary | Route handlers never call provider SDKs directly |
| Hierarchical retrieval | Never replace with flat chunk-only retrieval |
| Citation policy | Every grounded answer includes citations |
| Delete policy | Hard-delete 6-step order (see below) |
| Version policy | Latest active version preferred during retrieval |
| Rate limiting | Atomic Lua script — no INCR+EXPIRE race |

## Delete Policy (Authoritative)

Hard-delete removes all traces. **Order must not change:**

1. `registry.delete()` → marks deleted in Redis → `/status` returns 'deleted' immediately
2. `vector_store.delete()` → removes all Qdrant vectors → retrieval stops
3. `SectionRepository.delete()` → removes document_sections rows
4. `storage.delete_object()` → removes file from RustFS
5. `DocumentRepository.hard_delete()` → removes documents row from PostgreSQL
6. `registry.purge()` → removes all Redis registry keys

**Sections deleted before DB row** — referential integrity.

## Versioning Policy

| Policy | Behavior |
|--------|----------|
| Same filename + new content | New row with `version = max(version) + 1` |
| Retrieval default | Highest version per filename (subquery in retrieval_service.py) |
| Delete by version | Hard-delete only specified version |

## Access Model

| Role | Rights |
|------|--------|
| admin | Upload, delete, manage users, all member rights |
| member | Chat, retrieval, view documents, manage own memories |

JWT auth (PyJWT) + role checks. Role cached in JWT payload to eliminate DB queries per request. TokenBlacklist singleton with shared Redis connection. One shared project dataset, no tenant partitioning.

## User Memory System

ChatGPT-like persistent memory. Types: `preference`, `correction`, `instruction`, `fact`.

Flow: UserMemoryService (receives `redis.Redis` + `MemoryRepository` via DI) → load from Redis/PostgreSQL (cache TTL configurable via `MEMORY_CACHE_TTL`, default 5min) → inject into `systemInstruction` → AI generates response → async extract new memories via heuristic triggers + provider.chat() (uses cached singleton) → store in `user_memories`. MemoryService receives UserMemoryService via DI.

Frontend: Settings page `/settings` with full CRUD. Content limit: 1000 chars per memory.

## AI Thinking Control

Gemma 4 outputs chain-of-thought by default. 4 suppression layers:

| Layer | Mechanism | Location |
|-------|-----------|----------|
| API-level | `thinkingConfig: {thinkingLevel: "MINIMAL"}` | google.py generationConfig |
| Part filter | Skip `"thought": true` parts | google.py `_extract_text()` |
| Stream filter | `_ThoughtFilter` strips `<\|channel\|>thought...` tags | google.py |
| Post-process | `strip_reasoning()` + `strip_thought_blocks()` | google.py → chat.py |

**Only `MINIMAL` and `HIGH` accepted.** `thinkingBudget:0` causes 400. `includeThoughts:false` silently ignored.

## Multi-Turn Conversation

- Last N messages as Gemini `contents` array (assistant→model role mapping, configurable via `AI_MAX_HISTORY_MESSAGES`, default 20)
- RAG context embedded into current user message
- Messages persisted to PostgreSQL; Redis hot cache with configurable TTL (`CHAT_HISTORY_REDIS_TTL`, default 24h)
- `ChatStore.hydrate_from_db()` reloads from DB on TTL expiry (checks Redis first via `history_exists()`)
- Redis `append_message()` uses pipeline for atomic RPUSH + EXPIRE
- Auto-title from first user message (80 chars)
- `strip_thought_blocks()` cleans previous assistant messages before multi-turn send

## Chat Session Lifecycle

| Policy | Detail |
|--------|--------|
| Default view | Empty "Chat mới" on page load (no auto-restore) |
| History | Sidebar ordered by `updated_at DESC` |
| New session | `POST /chat/sessions` creates empty session |
| Switch | Click in sidebar → ChatPanel loads messages via `sessionId` prop |
| Auto-title | First user query truncated to 80 chars |
| Cleanup | Hard-delete after 30 days by Celery Beat (`CHAT_SESSION_TTL_DAYS`) |
| Cascade | Messages deleted with session automatically |
| `updated_at` | Auto-touched on message activity for sidebar ordering |

## Analytics & Cost Tracking

| Aspect | Detail |
|--------|--------|
| Endpoint | `GET /analytics/stats` — admin sees system-wide, member sees own sessions |
| Pricing | Configurable via `AI_INPUT_COST_PER_1M` / `AI_OUTPUT_COST_PER_1M` (default 0.0 for free tier) |
| Aggregation | Tokens stored per ChatMessage → aggregated by SQL query → endpoint |
| Frontend | Admin: `/admin/analytics` (KPI cards, daily chart, cost comparison). Member: welcome screen stats |
| Rate limit | `throttle:analytics:{user_id}`, 60/min |

## Hardware Auto-Detection

`app/core/hardware.py` — singleton detected once at startup. **3-tier VRAM-aware scaling.**

| Mode | Condition | uvicorn workers | celery pool | celery concurrency | DB pool |
|------|-----------|-----------------|-------------|-------------------|---------|
| TIGHT GPU | CUDA + VRAM headroom < 6GB | 1 | solo | min(cpu, 4) | 10+10 |
| COMFORTABLE GPU | CUDA + VRAM headroom ≥ 6GB | min(cpu, ram//2, 8) | prefork | min(cpu, 8) | auto |
| CPU only | No CUDA | min(cpu, ram//2, 8) | prefork | min(cpu, 8) | auto |

VRAM headroom = total VRAM − 2GB (embedding ~1.1GB + reranker ~0.5GB). Example: GTX 1650 4GB → headroom 2GB → TIGHT. RTX 4090 24GB → headroom 22GB → COMFORTABLE.

DB pool size (`db_pool_size`) auto-scales: `max(10, uvicorn_workers * 5)`.

## Celery Configuration

All values configurable via env vars (see `app/core/config.py`). Defaults designed for dev laptop (GTX 1650 4GB).

| Setting | Default | Purpose |
|---------|---------|---------|
| CELERY_TASK_TIME_LIMIT | 1800s (30 min) | Hard kill |
| CELERY_TASK_SOFT_TIME_LIMIT | 1500s (25 min) | Graceful SoftTimeLimitExceeded |
| CELERY_WORKER_MAX_MEMORY_KB | 1,500,000 (1.5GB) | Kill child if RSS exceeded |
| CELERY_VISIBILITY_TIMEOUT | 7200s (2h) | Prevent Redis re-delivery |
| CELERY_RESULT_EXPIRES | 86400s (24h) | Task result TTL |
| CELERY_MAX_TASKS_PER_CHILD | 50 | Recycle child after N tasks |
| CELERY_RETRY_BACKOFF | 30s (upload) | Exponential backoff base |
| CELERY_MAX_RETRIES | 3 | Max retry attempts |
| broker_connection_retry_on_startup | true | Don't crash if Redis unavailable |
| worker_disable_rate_limits | true | Rate limit at API level |
| Redis DB 0 | Celery broker | Task messages |
| Redis DB 1 | Result backend | Task results |
| Redis DB 2 | App cache | Query cache, rate limits, chat history |
| Queue routing | ingestion → upload-pipeline, cleanup → cleanup-pipeline | VRAM-aware separation |

## Planned (Phase 2)

SQL connector: tables `data_sources`, `data_source_schema_cache`, `data_source_query_audit` ready in `ops/init.sql`. Only SELECT allowed. LLM generates SQL from natural language. Policy-checked against approved table whitelist. Falls back to document RAG if unavailable.
