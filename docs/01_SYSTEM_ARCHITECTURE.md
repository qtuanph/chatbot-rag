# 01 — System Architecture

Status: authoritative architecture baseline — updated to reflect Next.js 16 frontend and rule-based refiner.

## Core Direction

| Principle | Decision |
|-----------|----------|
| Deployment | Docker-first, self-hosted, single-project deployment |
| Frontend | **Next.js 16** with shadcn/ui v4, next-auth v5 (JWT), SSE streaming |
| Backend | FastAPI with async endpoints |
| Ingestion | Docling-first conversion to Markdown, then LlamaIndex hierarchy parsing |
| OCR | EasyOCR (vi + en) — mandatory, deep-learning, GPU auto-detected |
| Embedding | **BAAI/bge-m3 LOCAL** via sentence-transformers (1024-dim, fully offline) |
| AI Refiner | **Rule-based heuristics** (0GB VRAM, ~1ms per node) — NO AI in ingestion |
| Vector Store | Qdrant for vectors and retrieval payload |
| Metadata Store | PostgreSQL for users, documents, **sections**, sessions, audit, connector metadata |
| Queue/Cache | Redis for Celery broker/result, query embedding cache, rate limiting |
| Retrieval | **2-stage retrieval**: Sections (PostgreSQL) → Chunks (Qdrant with section_id) |
| Query routing | Document RAG default; SQL route only when explicitly required and approved |
| AI Provider | Google AI gemma-4-26b-a4b-it (demo); vLLM on-premise (production target) |

PostgreSQL is the system database for metadata, status, auth, audit, and connector state. Qdrant is the retrieval store for node vectors and payload. Redis is used for task queue, cache, and atomic rate limiting.

## High-Level Component Diagram

```mermaid
graph TD
    Client[Client Browser] --> WebApp[Next.js 16 App]
    WebApp --> |shadcn/ui v4| UI[User Interface]
    WebApp --> |next-auth v5 JWT| Auth[Auth Client]
    WebApp --> |SSE streaming| SSE[Chat Streaming]

    WebApp --> API[FastAPI Backend]
    API --> AuthSvc[Auth and RBAC]
    API --> Upload[Upload Endpoint]
    API --> Chat[Chat Endpoint]

    Upload --> Redis[(Redis broker)]
    Redis --> Worker[Celery Worker]

    Worker --> Parser[Docling Parser + EasyOCR]
    Parser --> SectionExtractor[Section + Chunk Extraction]
    SectionExtractor --> Validator[Hierarchy Validator]
    Validator --> SectionStore[SectionRepository → PostgreSQL]
    Validator --> Refiner[Rule-Based Refiner]
    Refiner --> |0GB VRAM ~1ms| Validator
    Validator --> Embedder[BAAI/bge-m3 Local — Parallel Batches]
    Embedder --> Qdrant[(Qdrant — chunks with section_id)]
    Validator --> PG[(PostgreSQL system DB)]

    Upload --> RustFS[(RustFS)]
    Worker --> RustFS

    Chat --> Throttle[Atomic Rate Limiter — Lua+Redis]
    Chat --> QueryCache[Query Embedding Cache — Redis]
    Chat --> Retriever[2-Stage Retriever: Sections → Chunks]
    Retriever --> PG
    Retriever --> Qdrant
    Retriever -. planned -.-> SQLConnector[SQL Connector — Phase 2]
    Chat --> LLM[AI Provider Adapter]
    LLM --> Google[Google AI gemma-4-26b-a4b-it]
    LLM --> vLLM[vLLM — Production On-Premise]
```

## Runtime Data Flow

| Stage | Path | Output |
|-------|------|--------|
| 1. Upload | Browser → Next.js → API → RustFS | File persisted, document row pending |
| 2. Queue | API → Redis → Worker | Async task created, task_id returned |
| 3. Parse | Worker → Docling + EasyOCR → Section extraction → Chunk splitting | Sections + chunks |
| 4. Validate | Worker → Hierarchy Validator | Parent-child consistency report |
| 5. Refine | Worker → Rule-Based Refiner (0GB VRAM, ~1ms) | Cleaned text, fixed OCR errors |
| 6. Store Sections | Worker → SectionRepository → PostgreSQL | document_sections rows |
| 7. Embed | Worker → BAAI/bge-m3 (parallel batches of 32) | Dense vectors per chunk |
| 8. Persist | Worker → Qdrant | Chunks with section_id metadata |
| 9. Retrieve | Chat → QueryCache → Embedder → Stage 1 (sections) → Stage 2 (chunks) | Top sections + chunks |
| 10. Stream | Chat → AI Provider → SSE stream | Grounded answer with citations |

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
