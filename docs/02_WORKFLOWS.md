# 02 — Core Workflows

All system workflows with diagrams and invariants. Architecture and data model in `01_ARCHITECTURE.md`.

## Workflow 1: Upload → Parse → Index → Ready

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

    Pipeline->>Pipeline: Docling iterate_items() — Method D
    Note over Pipeline: Smart OCR: Pass 1 fast (no OCR)
    Note over Pipeline: If scanned → Pass 2 with OCR
    Pipeline->>Pipeline: Extract items: SectionHeader, Text, Table, ListItem...
    Pipeline->>Refiner: refine_text (0GB VRAM, ~1ms)
    Pipeline->>DB: Store sections in document_sections table

    loop For each chunk of 32 nodes
        Pipeline->>Pipeline: embed_batch (ThreadPoolExecutor parallel)
        Pipeline->>Qdrant: upsert vectors with section_id metadata
        Pipeline->>DB: stage=embed_store, percent=40→90 [callback]
    end

    Pipeline->>DB: stage=ready, percent=100 [callback]
    Worker->>Worker: invalidate_doc_ids_cache()
```

### Upload Invariants

| Rule | Requirement |
|------|-------------|
| Non-blocking | Upload returns task_id immediately (202) |
| Chunked embed | Embed + store in batches of 32, not all at once |
| Pipelined store | Embedding of chunk N overlaps with Qdrant store of chunk N-1 |
| Progress live | progress_percent updates after each chunk via callback |
| Reliability | `task_acks_late=True` — task requeued if worker crashes |
| Timeout | SoftTimeLimitExceeded at 25 min → status=failed |

## Workflow 2: Chat → Retrieve → Generate → Response

```mermaid
sequenceDiagram
    participant Browser
    participant API
    participant Redis
    participant Embedder as Vietnamese_Embedding_v2 Local
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
        Redis-->>API: cached query vector
    else Cache MISS
        API->>Embedder: embed(query_text)
        Embedder-->>API: query vector
        API->>Redis: cache.set(query, vector, TTL=1h)
    end
    API->>Retriever: retrieve_context(query_vector)
    Retriever->>Qdrant: search top-50~80 (filtered to active docs)
    Note over Retriever: Stage 1: group by section_id → top 3 sections (≥0.30)
    Retriever->>DB: load section details from document_sections
    Note over Retriever: Stage 2: re-rank chunks within sections (≥0.35)
    Retriever-->>API: top chunks with section context and citations

    API->>Memory: format_memories_for_prompt(user_id)
    Memory-->>API: formatted memory string for systemInstruction

    loop For each chunk of response
        API->>Provider: chat_stream (maxOutputTokens=8192)
        Provider-->>API: text chunk (thought:true parts filtered)
        API-->>Browser: SSE data: {"chunk": "...", "done": false}
    end
    API->>DB: save user + assistant ChatMessage to PostgreSQL (tokens_in, tokens_out, latency_ms)
    API->>Memory: extract_memories_from_turn() — async (tracked in _background_tasks)
    API-->>Browser: SSE data: {"done": true, "session_id": "...", "citations": [...], "stats": {"total_ms", "ttft_ms", "tokens", "estimated_cost_usd"}}
```

### Chat Invariants

| Rule | Requirement |
|------|-------------|
| Cache first | Check Redis for query embedding before calling model |
| Doc ID cache | TTL-cached 60s, invalidated on upload/delete |
| 2-stage retrieval | Single Qdrant query → section grouping (≥0.30) → chunk re-ranking (≥0.35) |
| Citation required | Return citation payload for every grounded answer |
| Rate limiting | Atomic Lua script — 30 req/min per user |
| Provider swap safety | Chat route stays provider-agnostic via adapter |
| Multi-turn | Last 20 messages via Gemini contents array (assistant→model) |
| Memory injection | User memories loaded from Redis/PostgreSQL, injected into systemInstruction |
| Memory extraction | Async post-response: heuristic triggers + Gemini → user_memories |
| Thinking suppressed | 4 layers: thinkingConfig MINIMAL + thought:true filter + ThoughtFilter + strip_reasoning() |
| Output bounds | maxOutputTokens: 8192, max_context_chars: 500000, streaming timeout 300s |
| Clean saved text | strip_reasoning() applied to answer before saving to DB |
| Token tracking | Gemini usageMetadata captured: prompt_tokens, completion_tokens persisted to ChatMessage |
| Cost estimation | Input $0.075/1M + Output $0.30/1M tokens (Gemini 2.5 Flash pricing) |
| Async task tracking | Background memory extraction tracked in _background_tasks set, prevent GC |
| Frontend SSE abort | AbortController cancels stream on unmount or new message |
| Session default | Empty "Chat mới" on page load, sidebar for history |

## Workflow 3: Hard Delete

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
    API->>Redis: enqueue delete_document_task (queue=cleanup)
    API-->>Client: 202 accepted

    Cleanup->>Registry: registry.delete() → status='deleted'
    Cleanup->>Qdrant: delete all vectors for document_id
    Cleanup->>DB: delete sections from document_sections
    Cleanup->>RustFS: delete file object
    Cleanup->>DB: DELETE document row
    Cleanup->>Cleanup: invalidate_doc_ids_cache()
    Cleanup->>Registry: registry.purge()
```

### Delete Invariants

| Rule | Requirement |
|------|-------------|
| Hard delete | 6-step order (see 01_ARCHITECTURE.md for full detail) |
| Registry first | `/status` returns 'deleted' immediately |
| Sections before DB | Referential integrity |
| No recovery | Irreversible — no trash/recycle |

## Workflow 4: Chat Session Auto-Delete

```mermaid
sequenceDiagram
    participant Beat as Celery Beat (cleanup-pipeline)
    participant DB as PostgreSQL
    participant Redis

    Note over Beat: Runs daily (every 86400s)
    Beat->>DB: DELETE chat_sessions WHERE created_at < NOW() - TTL
    DB->>DB: CASCADE DELETE associated chat_messages
    Note over Redis: Redis keys expire via TTL naturally
```

### Session TTL Invariants

| Rule | Detail |
|------|--------|
| TTL | `CHAT_SESSION_TTL_DAYS` (default: 30 days) |
| Cleanup | Celery beat in cleanup-pipeline — hard delete |
| Cascade | Messages deleted automatically with session |
| Persistence | Messages saved to PostgreSQL every turn; Redis is hot cache |
| Ordering | GET /chat/sessions returns updated_at DESC for sidebar |
| Config | `app/core/config.py` → `chat_session_ttl_days` |

## Error Handling Baseline

| Error | Handling |
|-------|----------|
| Parse failure | status=failed, parse_error set, SoftTimeLimitExceeded handled |
| Chunk embed failure | Log error, continue remaining chunks (partial index) |
| Retrieval timeout (5s) | Empty context, answer from LLM without grounding |
| Provider timeout | Graceful error response |
| Proxy socket close | Route Handler retries once; returns 502 JSON |
| Worker crash mid-task | Auto-requeue via task_acks_late=True |
