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
    Pipeline->>Pipeline: Section + Chunk extraction with page numbers
    Pipeline->>DB: stage=validate, percent=35 [callback]
    Pipeline->>Pipeline: Hierarchy Validator
    Pipeline->>Refiner: refine_text (0GB VRAM, ~1ms)
    Refiner->>Refiner: Fix OCR errors, detect headers
    Pipeline->>DB: stage=sections, percent=37 [callback]
    Pipeline->>DB: Store sections in document_sections table

    loop For each chunk of 32 nodes
        Pipeline->>Pipeline: embed_batch (ThreadPoolExecutor parallel)
        Pipeline->>Qdrant: upsert vectors
        Pipeline->>DB: stage=embed_store, percent=40→90 [callback]
    end

    Pipeline->>DB: stage=ready, percent=100 [callback]
    Worker->>DB: status=ready, extra_metadata saved
```

### Upload Invariants

| Rule | Requirement |
|------|-------------|
| Non-blocking | Upload endpoint returns `task_id` immediately |
| Chunked embed | Embed + store in batches of 32 nodes, not all at once |
| Progress live | `progress_percent` updates after each chunk via callback |
| Reliability | `task_acks_late=True` — task requeued if worker crashes |
| Timeout | `SoftTimeLimitExceeded` at 25 min → status=failed, not silent hang |

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
    Retriever->>DB: fetch latest active doc IDs
    Note over Retriever,Qdrant: Stage 1 — Coarse section search
    Retriever->>Qdrant: search top-50 by cosine similarity
    Retriever->>Retriever: group by section_id → pick top 3 sections (score ≥ 0.30)
    Retriever->>DB: load section details from document_sections
    Note over Retriever,Qdrant: Stage 2 — Fine chunk search within sections
    Retriever->>Qdrant: search within top sections (score ≥ 0.35)
    Retriever->>Retriever: prioritize in-section chunks
    Retriever-->>API: top nodes with section context and citations

    loop For each chunk of response
        API->>Provider: chat_stream (generate next chunk)
        Provider-->>API: text chunk
        API-->>Browser: SSE data: {"chunk": "...", "done": false}
    end
    API->>DB: save ChatMessage
    API-->>Browser: SSE data: {"done": true, "session_id": "...", "citations": [...]}
```

### Chat Invariants

| Rule | Requirement |
|------|-------------|
| Cache first | Check Redis for query embedding before calling API |
| 2-stage retrieval | Stage 1: sections (≥ 0.30) → Stage 2: chunks within sections (≥ 0.35) |
| Citation required | Return citation payload for every grounded answer |
| Retrieval filters | Exclude deleted docs, prefer latest version |
| Rate limiting | Atomic Lua script — 30 requests/min per user |
| Provider swap safety | Chat route stays provider-agnostic via adapter |

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
