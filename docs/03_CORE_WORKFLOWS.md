# 03 — Core Workflows

Status: implementation workflow baseline — updated to reflect chunked pipeline, progress reporting, and hard-delete.

## Workflow 1: Upload → Queue → Parse → Index → Ready

```mermaid
sequenceDiagram
    participant Client
    participant API as FastAPI
    participant RustFS
    participant DB as PostgreSQL
    participant Redis
    participant Worker as Celery Worker
    participant Pipeline as IngestionPipeline
    participant Qdrant

    Client->>API: POST /api/v1/upload
    API->>API: validate auth and size
    API->>RustFS: store file
    API->>DB: INSERT document (status=pending)
    API->>Redis: enqueue parse_document_task (queue=ingestion)
    API-->>Client: 202 { task_id }

    Redis->>Worker: dequeue (ack_late=True)
    Worker->>DB: status=processing, stage=download, percent=10
    Worker->>RustFS: download file bytes

    Worker->>DB: stage=parse, percent=40
    Worker->>Pipeline: ingest(filename, bytes, progress_callback)

    Pipeline->>DB: stage=parse, percent=5  [callback]
    Pipeline->>Pipeline: Docling + EasyOCR → Markdown
    Pipeline->>DB: stage=parse, percent=30 [callback]
    Pipeline->>Pipeline: LlamaIndex → hierarchy nodes
    Pipeline->>DB: stage=validate, percent=35 [callback]
    Pipeline->>Pipeline: Hierarchy Validator

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
    participant Client
    participant API
    participant Redis
    participant Embedder as Gemini Embedding
    participant Retriever
    participant DB as PostgreSQL
    participant Qdrant
    participant Provider as AI Provider

    Client->>API: POST /api/v1/chat
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
    API->>Retriever: retrieve_context(query_vector, limit=5)
    Retriever->>DB: fetch latest active doc IDs
    Retriever->>Qdrant: search top-10 by cosine similarity
    Retriever->>Retriever: filter score < 0.35 (noise removal)
    Retriever-->>API: top-5 relevant nodes with citations
    API->>Provider: chat(history, context, citations)
    Provider-->>API: answer
    API->>DB: save ChatMessage
    API-->>Client: { session_id, answer, citations }
```

### Chat Invariants

| Rule | Requirement |
|------|-------------|
| Cache first | Check Redis for query embedding before calling API |
| Score threshold | Drop retrieval results with cosine similarity < 0.35 |
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
    participant Qdrant
    participant RustFS
    participant DB

    Client->>API: DELETE /api/v1/documents/{document_id}
    API->>API: validate auth (admin only)
    API->>Redis: enqueue delete_document_task (queue=cleanup)
    API-->>Client: 202 accepted

    Note over Registry,DB: Hard-delete sequence (order matters)
    Registry->>Registry: registry.delete() → status='deleted'
    Note right of Registry: /status now returns 'deleted' immediately
    Registry->>Qdrant: delete all vectors for document_id
    Qdrant->>RustFS: delete file object
    RustFS->>DB: DELETE document row
    DB->>Registry: registry.purge() → remove Redis keys
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

## Error Handling Baseline

| Error | Handling |
|-------|----------|
| Parse failure | `status=failed`, `parse_error` set, `SoftTimeLimitExceeded` handled |
| Chunk embed failure | Log error, continue remaining chunks (partial index) |
| Retrieval timeout (5s) | Return empty context, answer from LLM without grounding |
| Provider timeout | Graceful error response |
| Worker crash mid-task | Auto-requeue via `task_acks_late=True` |
