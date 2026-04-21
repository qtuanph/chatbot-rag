# 03 — Core Workflows

Status: implementation workflow baseline — updated to reflect Method D, Smart OCR Strategy, and worker architecture refactor.

## Workflow 1: Upload → Queue → Parse → Index → Ready

```mermaid
sequenceDiagram
    participant Browser
    participant API as FastAPI
    participant RustFS
    participant DB as PostgreSQL
    participant Redis
    participant Worker as upload-pipeline (GPU)
    participant Pipeline as IngestionPipeline
    participant Refiner as Rule-Based Refiner
    participant Qdrant

    Browser->>API: POST /api/v1/upload
    API->>API: validate auth and size
    API->>RustFS: store file
    API->>DB: INSERT document (status=pending)
    API->>Redis: enqueue parse_document_task (queue=ingestion)
    API-->>Browser: 202 { task_id }

    Redis->>Worker: dequeue (ack_late=True)
    Worker->>DB: status=processing, stage=download, percent=10
    Worker->>RustFS: download file bytes

    Worker->>DB: stage=parse, percent=40
    Worker->>Pipeline: ingest(filename, bytes, progress_callback)

    Pipeline->>DB: stage=parse, percent=5  [callback]
    Pipeline->>Pipeline: Docling iterate_items() — Method D
    Note over Pipeline: Smart OCR: Pass 1 fast (no OCR)
    Note over Pipeline: If scanned detected → Pass 2 with OCR
    Pipeline->>Pipeline: Extract items: SectionHeader, Text, Table, ListItem...
    Pipeline->>DB: stage=parse, percent=30 [callback]
    Pipeline->>Pipeline: Section + Chunk extraction with page spans
    Pipeline->>DB: stage=validate, percent=35 [callback]
    Pipeline->>Pipeline: Hierarchy Validator
    Pipeline->>Refiner: refine_text (0GB VRAM, ~1ms)
    Refiner->>Refiner: Fix OCR errors, detect headers
    Pipeline->>DB: stage=sections, percent=37 [callback]
    Pipeline->>DB: Store sections in document_sections table

    loop For each chunk of 32 nodes
        Pipeline->>Pipeline: embed_batch (ThreadPoolExecutor parallel)
        Pipeline->>Qdrant: upsert vectors on bounded background store workers
        Pipeline->>DB: stage=embed_store, percent=40→90 [callback]
    end

    Pipeline->>DB: stage=ready, percent=100 [callback]
    Worker->>DB: status=ready, extra_metadata saved
    Worker->>Worker: invalidate_doc_ids_cache() — new doc visible to chat immediately
```

### Upload Invariants

| Rule | Requirement |
|------|-------------|
| Non-blocking | Upload endpoint returns `task_id` immediately |
| Chunked embed | Embed + store in batches of 32 nodes, not all at once |
| Pipelined store | Embedding of chunk N overlaps with Qdrant store of chunk N-1 |
| Store window | In-flight Qdrant writes are bounded by `ingestion_embed_parallelism` or hardware profile |
| Progress live | `progress_percent` updates after each chunk via callback |
| Reliability | `task_acks_late=True` — task requeued if worker crashes |
| Timeout | `SoftTimeLimitExceeded` at 25 min → status=failed, not silent hang |

### Ordering Invariants

| Rule | Requirement |
|------|-------------|
| Canonical order | `document_sections.order_index` defines document order |
| Page grouping | Sections may span multiple pages; store page span, not only the first page |
| Tree/list display | Admin document detail should render the ordered PostgreSQL slice as a table/list, not Qdrant scroll order |
| Full text | Section content is preserved during extraction; tree summaries may show truncated previews, but chunk payloads keep the full indexed text |

## Workflow 2: Chat → Retrieve → Generate → JSON Response

```mermaid
sequenceDiagram
    participant Browser
    participant API
    participant Redis
    participant Embedder as BAAI/bge-m3 Local
    participant Retriever
    participant DB as PostgreSQL
    participant Qdrant
    participant Memory as UserMemoryService
    participant Provider as AI Provider

    Browser->>API: POST /api/v1/chat/stream (SSE)
    API->>API: validate auth and payload
    API->>Redis: check rate limit (atomic Lua script)
    API->>Redis: query embedding cache lookup (MD5 key)
    alt Cache HIT
        Redis-->>API: cached query vector (0ms, 0 API cost)
    else Cache MISS
        API->>Embedder: embed(query_text)
        Embedder-->>API: query vector
        API->>Redis: cache.set(query, vector, TTL=1h)
    end
    API->>Retriever: retrieve_context(query_vector, limit=20)
    Retriever->>Retriever: fetch TTL-cached doc IDs (60s, invalidated on upload/delete)
    Note over Retriever,Qdrant: Single Qdrant query (replaces old 2-query approach)
    Retriever->>Qdrant: search top-50~80 by cosine similarity (filtered to active docs)
    Note over Retriever: Stage 1 — In-memory section grouping
    Retriever->>Retriever: group by section_id → pick top 3 sections (score ≥ 0.30)
    Retriever->>DB: load section details from document_sections
    Note over Retriever: Stage 2 — In-memory chunk re-ranking
    Retriever->>Retriever: prioritise chunks within top sections (score ≥ 0.35)
    Retriever-->>API: top nodes with section context and citations

    API->>Memory: format_memories_for_prompt(user_id)
    Memory->>Redis: cache lookup (5min TTL)
    alt Cache HIT
        Redis-->>Memory: cached memories
    else Cache MISS
        Memory->>DB: SELECT user_memories WHERE user_id AND is_active
        Memory->>Redis: cache result (5min TTL)
    end
    Memory-->>API: formatted memory string for systemInstruction

    loop For each chunk of response
        API->>Provider: chat_stream (maxOutputTokens=1M, multi-turn contents)
        Provider-->>API: text chunk (thought:true parts filtered)
        API-->>Browser: SSE data: {"chunk": "...", "done": false}
    end
    API->>API: strip_reasoning(full_answer) — safety net
    API->>DB: save ChatMessage (clean answer)
    API->>Memory: extract_memories_from_turn() — async, best-effort
    API-->>Browser: SSE data: {"done": true, "session_id": "...", "citations": [...]}
```

### Chat Invariants

| Rule | Requirement |
|------|-------------|
| Cache first | Check Redis for query embedding before calling API |
| Doc ID cache | TTL-cached 60s, invalidated on upload/delete — avoids PostgreSQL subquery per request |
| 2-stage retrieval | Single Qdrant query → in-memory section grouping (≥ 0.30) → chunk re-ranking within sections (≥ 0.35) |
| Citation required | Return citation payload for every grounded answer |
| Retrieval filters | Exclude deleted docs, prefer latest version |
| Rate limiting | Atomic Lua script — 30 requests/min per user |
| Provider swap safety | Chat route stays provider-agnostic via adapter |
| Multi-turn context | Last 20 messages via Gemini `contents` array with role mapping (assistant→model) |
| Memory injection | User memories loaded from Redis/PostgreSQL, injected into systemInstruction |
| Memory extraction | Async post-response: heuristic trigger detection + Gemini extraction → store in user_memories |
| Thinking suppressed | `thinkingConfig: {thinkingLevel: "MINIMAL"}` + `thought:true` filter + `_ThoughtFilter` stream + `strip_reasoning()` — 4 layers |
| History clean | `strip_thought_blocks()` removes `<\|channel\|>thought...<channel\|>` from previous assistant messages before sending as multi-turn context |
| No output limits | `maxOutputTokens: 1048576`, `max_context_chars: 500000`, streaming timeout 300s (5min) |
| Clean saved text | `strip_reasoning()` applied to answer before saving to DB |

## Workflow 3: Delete → Hard Delete

```mermaid
sequenceDiagram
    participant Client
    participant API
    participant Registry as Redis Registry
    participant Cleanup as cleanup-pipeline
    participant Qdrant
    participant RustFS
    participant DB

    Client->>API: DELETE /api/v1/documents/{document_id}
    API->>API: validate auth (admin only)
    API->>Redis: enqueue delete_document_task (queue=cleanup)
    API-->>Client: 202 accepted

    Note over Cleanup,DB: Hard-delete sequence (order matters)
    Cleanup->>Registry: registry.delete() → status='deleted'
    Note right of Registry: /status now returns 'deleted' immediately
    Cleanup->>Qdrant: delete all vectors for document_id
    Cleanup->>DB: delete sections from document_sections
    Cleanup->>RustFS: delete file object
    Cleanup->>DB: DELETE document row
    Cleanup->>Cleanup: invalidate_doc_ids_cache() — deleted doc removed from chat scope immediately
    Cleanup->>Registry: registry.purge() → remove Redis keys
```

### Delete Invariants

| Rule | Requirement |
|------|-------------|
| Hard delete | All traces removed: vectors, file, DB row, registry |
| Registry first | `registry.delete()` called before anything else — /status updates instantly |
| Purge last | `registry.purge()` only after DB row is gone |
| No recovery | Hard delete is irreversible — no trash/recycle |

## Workflow 4: Optional SQL Connector Route (Phase 2 — Not Yet Implemented)

| Condition | Behavior |
|-----------|----------|
| Question answerable by documents | Stay on document RAG route |
| Explicit live business-data request + approved connector | Route to SQL connector |
| SQL connector unavailable or not configured | Return explicit limitation message |

Implementation notes when building:
- Use `data_sources` table to look up connector config
- Load schema from `data_source_schema_cache`
- LLM generates **SELECT only** SQL — no DDL/DML
- Policy-check against approved table whitelist
- Log every query to `data_source_query_audit`

## Workflow 5: Chat Session Auto-Delete

```mermaid
sequenceDiagram
    participant Beat as Celery Beat (cleanup-pipeline)
    participant DB as PostgreSQL

    Note over Beat: Runs daily (every 86400s)
    Beat->>Beat: cleanup_old_chat_sessions_task
    Beat->>DB: DELETE chat_sessions WHERE created_at < NOW() - TTL
    DB->>DB: CASCADE DELETE associated chat_messages
```

### Chat Session TTL Invariants

| Rule | Requirement |
|------|-------------|
| TTL | `CHAT_SESSION_TTL_DAYS` (default: 1 day) |
| Cleanup | Celery beat task in `cleanup-pipeline` worker |
| Delete behavior | CASCADE — messages deleted automatically with session |
| Config | `app/core/config.py` → `chat_session_ttl_days` |

## Error Handling Baseline

| Error | Handling |
|-------|----------|
| Parse failure | `status=failed`, `parse_error` set, `SoftTimeLimitExceeded` handled |
| Chunk embed failure | Log error, continue remaining chunks (partial index) |
| Retrieval timeout (5s) | Return empty context, answer from LLM without grounding |
| Provider timeout | Graceful error response |
| Worker crash mid-task | Auto-requeue via `task_acks_late=True` |
