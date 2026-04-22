# 01 — System Architecture

Status: authoritative architecture baseline — updated to reflect Method D, Smart OCR Strategy, and worker architecture refactor.

## Core Direction

| Principle | Decision |
|-----------|----------|
| Deployment | Docker-first, self-hosted, single-project deployment |
| Frontend | **Next.js 16** with shadcn/ui v4, next-auth v5 (JWT), SSE streaming |
| Backend | FastAPI with async endpoints |
| Ingestion | Docling `iterate_items()` (Method D) for direct item extraction — preserves page numbers, heading levels, table structures |
| OCR | **Smart OCR Strategy**: fast no-OCR first, OCR fallback only for scanned PDFs. EasyOCR (vi + en) backend. |
| Embedding | **BAAI/bge-m3 LOCAL** via sentence-transformers (1024-dim, fully offline) |
| AI Refiner | **Rule-based heuristics** (0GB VRAM, ~1ms per node) — NO AI in ingestion |
| Vector Store | Qdrant for vectors and retrieval payload |
| Metadata Store | PostgreSQL for users, documents, **sections**, sessions, audit, connector metadata |
| Queue/Cache | Redis for Celery broker/result, query embedding cache, rate limiting |
| Retrieval | **2-stage retrieval**: Sections (PostgreSQL canonical order) → Chunks (Qdrant with section_id) |
| Query routing | Document RAG default; SQL route only when explicitly required and approved |
| AI Provider | Google AI gemma-4-26b-a4b-it (demo); vLLM on-premise (production target) |
| Workers | `upload-pipeline` (GPU, ingestion) + `cleanup-pipeline` (lightweight, deletion + beat) |
| Chat sessions | Auto-delete after 1 day (`CHAT_SESSION_TTL_DAYS`) via Celery beat |
| User memory | ChatGPT-like persistent memory: facts, preferences, corrections injected into system prompt |
| AI thinking | `thinkingConfig: {thinkingLevel: "MINIMAL"}` disables Gemma 4 thought tokens; `thought:true` part filter + `_ThoughtFilter` stream + `strip_reasoning()` safety net |
| AI output | No limits: `maxOutputTokens: 1048576`, `max_context_chars: 500000`, streaming timeout 300s (5min) |

PostgreSQL is the system database for metadata, status, auth, audit, and connector state. Qdrant is the retrieval store for node vectors and payload. Redis is used for task queue, cache, and atomic rate limiting.

## High-Level Component Diagram

```mermaid
graph TD
    Client[Client Browser] --> WebApp[Next.js 16 App]
    WebApp --> |shadcn/ui v4| UI[User Interface]
    WebApp --> |next-auth v5 JWT| Auth[Auth Client]
    WebApp --> |SSE streaming| SSE[Chat Streaming]

    WebApp --> |API Gateway Proxy /api/bep/| APIProxy[Route Handler: getToken → Bearer]
    APIProxy --> |server-side internal| API[FastAPI Backend]
    API --> AuthSvc[Auth and RBAC]
    API --> Upload[Upload Endpoint]
    API --> Chat[Chat Endpoint]

    Upload --> Redis[(Redis broker)]
    Redis --> UploadPipeline[upload-pipeline · GPU Worker]
    Redis --> CleanupPipeline[cleanup-pipeline · Lightweight + Beat]

    UploadPipeline --> Parser[Docling iterate_items · Method D]
    Parser --> SmartOCR[Smart OCR · 2-Pass Strategy]
    SmartOCR --> SectionExtractor[Section + Chunk Extraction]
    SectionExtractor --> Validator[Hierarchy Validator]
    Validator --> SectionStore[SectionRepository → PostgreSQL]
    Validator --> Refiner[Rule-Based Refiner]
    Refiner --> |0GB VRAM ~1ms| Validator
    Validator --> Embedder[BAAI/bge-m3 Local — Parallel Batches]
    Embedder --> Qdrant[(Qdrant — chunks with section_id)]
    Validator --> PG[(PostgreSQL system DB)]

    Upload --> RustFS[(RustFS)]
    UploadPipeline --> RustFS

    CleanupPipeline --> |hard delete| Qdrant
    CleanupPipeline --> |hard delete| RustFS
    CleanupPipeline --> |hard delete| PG
    CleanupPipeline --> |beat: daily| TTL[Chat Session TTL Cleanup]

    Chat --> Throttle[Atomic Rate Limiter — Lua+Redis]
    Chat --> QueryCache[Query Embedding Cache — Redis]
    Chat --> DocIDCache[Document ID TTL Cache — 60s in-memory]
    Chat --> Retriever[2-Stage Retriever: single Qdrant query → in-memory re-rank]
    Retriever --> PG
    Retriever --> Qdrant
    Retriever -. planned -.-> SQLConnector[SQL Connector — Phase 2]
    Chat --> LLM[AI Provider Adapter]
    LLM --> Google[Google AI gemma-4-26b-a4b-it]
    LLM --> vLLM[vLLM — Production On-Premise]
    Chat --> MemorySvc[UserMemoryService]
    MemorySvc --> Redis[(Redis cache 5min TTL)]
    MemorySvc --> PG[(user_memories table)]
```

## Runtime Data Flow

| Stage | Path | Output |
|-------|------|--------|
| 1. Upload | Browser → `/api/bep/` → Next.js proxy → API → RustFS | File persisted, document row pending |
| 2. Queue | API → Redis → Worker | Async task created, task_id returned |
| 3. Parse | Worker → Docling `iterate_items()` (Method D) + Smart OCR → Section extraction → Chunk splitting | Sections + chunks with page spans, heading levels |
| 4. Validate | Worker → Hierarchy Validator | Parent-child consistency report |
| 5. Refine | Worker → Rule-Based Refiner (0GB VRAM, ~1ms) | Cleaned text, fixed OCR errors |
| 6. Store Sections | Worker → SectionRepository → PostgreSQL | document_sections rows |
| 7. Embed | Worker → BAAI/bge-m3 (parallel batches of 32) | Dense vectors per chunk |
| 8. Persist | Worker → Qdrant | Chunks with section_id metadata |
| 9. Retrieve | Chat → QueryCache → Embedder → single Qdrant query → in-memory section grouping → chunk re-ranking | Top sections + chunks |
| 10. Memory | Chat → UserMemoryService → Redis cache (5min TTL) → PostgreSQL fallback → inject into systemInstruction | Personalized prompt context |
| 11. Stream | Chat → AI Provider (maxOutputTokens: 1M, timeout 5min) → strip_reasoning() safety net → SSE stream via proxy → Browser | Grounded answer with citations, no chain-of-thought |
| 12. Extract | Post-response → UserMemoryService.extract_memories_from_turn() → async Gemini call → store in user_memories | Learned facts for future turns |

## Non-Negotiable Invariants

| Rule | Required behavior |
|------|-------------------|
| API contracts | Keep upload/status/chat/document endpoints stable |
| Async ingestion | Upload endpoint must never block on parsing |
| Provider boundary | Route handlers must never call provider SDKs directly |
| Hierarchical retrieval | Do not replace with naive chunk-only retrieval |
| Citation policy | Every grounded answer must include citations |
| Delete policy | Hard-delete: vectors → file → DB row (registry.delete first, purge last) |
| Version policy | Latest active version preferred during retrieval |
| Rate limiting | Atomic Lua script in Redis — no INCR+EXPIRE race condition |

## Planned Features (Phase 2)

### SQL Connector (Text-to-SQL)

DB schema is already prepared in `ops/init.sql`:

| Table | Purpose |
|-------|---------|
| `data_sources` | Registered SQL Server / PostgreSQL connections |
| `data_source_schema_cache` | Cached table/column metadata with join hints |
| `data_source_query_audit` | Audit log for every SQL query executed |

When implemented, the connector will:
- Route only when question clearly requires live business data
- Use LLM to generate **read-only SELECT** statements from natural language
- Policy-check against approved table whitelist before execution
- Log every query to `data_source_query_audit`
- Fall back to document RAG if connector is unavailable

See: Pinterest Text-to-SQL, Swiggy Hermes, Uber QueryGPT for reference patterns.

## Explicitly Removed / Changed

| Changed | Reason |
|---------|--------|
| Tesseract OCR | Replaced by EasyOCR (mandatory) — better Vietnamese support |
| Sequential embedding loop | Replaced by `ThreadPoolExecutor` parallel batches — ~16x faster |
| DDL patches in `main.py` startup | Removed — schema fully managed by `ops/init.sql` |
| Non-atomic INCR+EXPIRE rate limit | Replaced by atomic Lua script |
| Hardcoded `local-model` in vLLM adapter | Now reads `settings.vllm_model` from env |
| AI-based text refiner (Qwen/Gemini) | Replaced by rule-based refiner — 0GB VRAM, ~1ms per node |
| Nuxt.js frontend | Replaced by Next.js 16 with shadcn/ui v4 |
| Streamlit frontend | Removed — replaced by Next.js app |
| Google API key rotation | Removed — single key only |
| `export_to_markdown()` path | Replaced by Method D (`iterate_items()`) — preserves page numbers, heading levels, table structures |
| `_build_page_map()` / `_find_page_for_section()` | Removed — page numbers now extracted directly from Docling provenance data |
| `app/worker.py` (single worker) | Refactored to `app/workers/upload_pipeline.py` + `app/workers/cleanup_pipeline.py` |
| `app/workflows/` directory | Removed — was empty, tasks moved to `app/workers/` |
| `do_ocr=True` on all PDFs | Replaced by Smart OCR Strategy — fast no-OCR first, OCR fallback only for scanned PDFs |
| 2-query retrieval (Stage 1 → Stage 2) | Replaced by single Qdrant query + in-memory section grouping and re-ranking — eliminates one round-trip |
| Direct PostgreSQL subquery per chat request | Replaced by TTL-cached document IDs (60s), explicitly invalidated on upload/delete |
| Duplicate system instruction in `chat()` and `chat_stream()` | Refactored to shared `_SYSTEM_INSTRUCTION` constant; `chat()` now reuses `chat_stream()` |
| Direct port access (localhost:3000, localhost:8000) | Replaced by nginx reverse proxy on port 80 — SSE streaming, NextAuth routing, rate limiting, security headers |
| Browser Bearer token exposure | Replaced by API gateway proxy — browser calls `/api/bep/` only, token read server-side via `getToken()` |
| Client-side session.accessToken | Removed from Session type — `accessToken` stays in JWT callback, never exposed to client components |
| Admin pages without server auth | Added server-side `auth()` guards in admin/chat/settings layouts |

## User Memory Architecture

ChatGPT-like persistent memory system that allows the AI to learn user preferences, corrections, and instructions over time.

### Storage

| Layer | Store | TTL |
|-------|-------|-----|
| Primary | PostgreSQL `user_memories` table | Persistent |
| Cache | Redis `user_memories:{user_id}` | 5 minutes |
| API endpoint | `GET/POST/PATCH/DELETE /api/v1/memories` | Per-request |

### Memory Types

| Type | Description | Example |
|------|-------------|---------|
| `preference` | User preferences | "Trả lời ngắn gọn" |
| `correction` | User corrections | "Đừng dùng bullet points" |
| `instruction` | Explicit instructions | "Luôn trích dẫn nguồn" |
| `fact` | Facts about user | "Làm việc ở phòng marketing" |

### Flow

1. **Load**: Before streaming, `UserMemoryService.format_memories_for_prompt()` loads active memories (Redis → PostgreSQL fallback)
2. **Inject**: Memories appended to `systemInstruction` in Gemini API payload
3. **Generate**: AI generates personalized response using memory context
4. **Extract**: After response, async `extract_memories_from_turn()` uses heuristic triggers + Gemini to extract new facts
5. **Store**: New memories saved to PostgreSQL + Redis cache invalidated

### Frontend

Settings page (`/settings`) provides full CRUD:
- View all memories with type badges (color-coded)
- Add new memory (type selector + content input)
- Toggle active/inactive
- Delete memory

## AI Thinking Control

Gemma 4 26B A4B is a thinking model that outputs chain-of-thought reasoning by default. Three layers suppress this:

| Layer | Mechanism | Location |
|-------|-----------|----------|
| **API-level** | `thinkingConfig: {thinkingLevel: "MINIMAL"}` — Gemma 4 only accepts `MINIMAL` and `HIGH` | `app/adapters/ai/google.py` generationConfig |
| **Part filter** | Skip parts with `"thought": true` in `_extract_text()` | `app/adapters/ai/google.py` |
| **Stream filter** | `_ThoughtFilter` state machine strips `<\|channel\|>thought...<channel\|>` tags real-time | `app/adapters/ai/google.py` |
| **Post-process** | `strip_reasoning()` + `strip_thought_blocks()` on saved text | `app/adapters/ai/google.py` → `chat.py` |

**Note:** `thinkingBudget: 0` causes 400 error with Gemma 4. `includeThoughts: false` is silently ignored (bug). Only `thinkingLevel: "MINIMAL"` works. Source: google-gemini/cookbook#1198.

The `strip_reasoning()` function detects markers like "Question:", "Source Material:", "Structure:", "Drafting", "Self-Correction", "Final Polish:" and strips everything before the actual answer. Applied to saved text in both streaming and non-streaming routes.

## Multi-Turn Conversation

Chat supports multi-turn context via Gemini `contents` array format:
- History mapped: `assistant` → `model`, `user` → `user` roles
- Last 20 messages included for performance
- RAG context embedded into current user message (not separate field)
- Session managed by `ChatStore` with Redis-backed history

## Security Architecture

### API Gateway Proxy (JWT Hiding)

Browser **never** sends or receives Bearer tokens. All browser API calls go through the Next.js API gateway proxy:

```
Browser → /api/bep/... → Next.js Route Handler → getToken() (HttpOnly cookie) → Bearer header → FastAPI backend
```

| Layer | Mechanism |
|-------|-----------|
| **Client** | Calls `/api/bep/v1/...` — no token in JS, no token in Network tab |
| **Route Handler** | `webapp/app/api/bep/[...path]/route.ts` — reads JWT via `getToken()` from encrypted HttpOnly cookie |
| **Backend** | Receives standard Bearer token — no changes to auth logic |
| **Session type** | Client `Session` has `role` + `userId` only — `accessToken` stays server-side |

### Server-Side Auth Guards

All page layouts enforce authentication at the server component level:

| Layout | Auth Level | Redirect |
|--------|-----------|----------|
| `webapp/app/(main)/admin/layout.tsx` | `session.role === "admin"` | → `/login` or `/chat` |
| `webapp/app/(main)/chat/layout.tsx` | `session exists` | → `/login` |
| `webapp/app/(main)/settings/layout.tsx` | `session exists` | → `/login` |

### Security Headers

Applied via `next.config.ts` `headers()` config on all routes:

| Header | Value |
|--------|-------|
| X-Frame-Options | DENY |
| X-Content-Type-Options | nosniff |
| Referrer-Policy | strict-origin-when-cross-origin |
| Permissions-Policy | geolocation=(), microphone=(), camera=(), payment=() |
| X-DNS-Prefetch-Control | on |
| Strict-Transport-Security | max-age=31536000; includeSubDomains |

### Rate Limiting Summary

| Endpoint | Limit | Key |
|----------|-------|-----|
| `POST /memories` | 20/min per user | `throttle:memory:create:{user_id}` |
| `PATCH /memories/{id}` | 20/min per user | `throttle:memory:update:{user_id}` |
| `DELETE /memories/{id}` | 20/min per user | `throttle:memory:delete:{user_id}` |
| `POST /auth/users` | 5/min per admin | `throttle:user:create:{user_id}` |
| `DELETE /auth/users/{username}` | 5/min per admin | `throttle:user:delete:{user_id}` |
| `POST /chat/stream` | 30/min per user | existing chat throttle |
| `POST /auth/login` | 50/min per IP+user | existing login throttle |
