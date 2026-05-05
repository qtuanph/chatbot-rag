# 02 — Workflows

Detailed step-by-step logic for the primary system workflows.

## 1. Document Ingestion Workflow (Admin Only)

The 14-step pipeline for turning raw files into searchable vectors. Runs in `node-ingestion` (solo pool).

```mermaid
sequenceDiagram
    participant Admin
    participant API
    participant Bloom as DuplicateDetector (Bloom)
    participant Storage as RustFS
    participant Queue as Redis Queue
    participant Worker as butler (node-ingestion)
    participant Parser as Docling + PaddleOCR
    participant Context as Contextualizer
    participant Qdrant
    participant DB as PostgreSQL

    Admin->>API: POST /api/v1/documents/upload
    API->>Bloom: check SHA256 (O(1) skip)
    alt is duplicate
        Bloom-->>API: exists=true
        API-->>Admin: 200 (duplicate info)
    else is new
        API->>Storage: save_bytes()
        API->>DB: create document row (pending)
        API->>Bloom: add(sha256)
        API->>Queue: enqueue parse_document_task
        API-->>Admin: 202 accepted (task_id)
    end

    Worker->>Storage: download_bytes()
    Worker->>Parser: parse layout (Method D)
    Parser-->>Worker: hierarchical nodes
    Worker->>Context: contextualize(global_vision)
    Context-->>Worker: enriched chunks (context prefixed)
    Worker->>DB: SectionRepository.store_sections()
    Worker->>Qdrant: parallel embed + store (dense + sparse)
    Worker->>DB: finalize_ingestion() (status=ready)
```

### Ingestion Invariants

| Rule | Requirement |
|------|-------------|
| **Duplicate Detection** | **Redis Bloom Filter (DuplicateDetector)** for O(1) checks before DB query |
| Async processing | Upload returns 202 immediately after storage save |
| Solo pool | Ingestion tasks run sequentially on `node-ingestion` to manage VRAM |
| **Global Vision** | **Contextualizer** prepends document-level summary to every chunk for higher RAG accuracy |
| Hierarchical | Docling structure preserved in `document_sections` |
| DB-less RAG | Qdrant payload contains `section_content` to minimize DB lookups during chat |
| Hybrid indexing | Both dense (1024-dim) and sparse (BM25) vectors stored |
| Timeout | SoftTimeLimitExceeded at 25 min → status=failed |

## 2. Chat → Retrieve → Generate → Response

```mermaid
sequenceDiagram
    participant Browser
    participant API
    participant Cache as SemanticCache (Redis Vector)
    participant ChatSvc
    participant Retriever
    participant Qdrant
    participant Provider as AI Provider

    Browser->>API: POST /api/v1/chat/stream
    API->>ChatSvc: prepare_chat()
    ChatSvc->>Retriever: retrieve_context()
    
    Retriever->>Cache: semantic_cache.get(query_vector)
    alt Cache HIT (Similarity > 98%)
        Cache-->>Retriever: cached RagContext
        Note over Retriever: Bypasses Qdrant & Embedding logic
    else Cache MISS
        Retriever->>Qdrant: hybrid search (dense + BM25 RRF fusion)
        Retriever->>Retriever: section grouping & context assembly
        Retriever->>Cache: semantic_cache.set(result)
    end

    Retriever-->>ChatSvc: RagContext
    ChatSvc->>Provider: chat_stream (Gemma-4)
    Provider-->>Browser: SSE Stream
```

### Chat Invariants

| Rule | Requirement |
|------|-------------|
| **Speed Layer** | **SemanticCache** (Redis Vector Search) checks for similarity > 98% (dist < 0.02) |
| **Exact Cache** | Redis exact match check on raw query text for sub-millisecond response |
| **Binary Serialization** | Chat history stored using **MessagePack** for extreme speed and low RAM |
| Doc ID cache | TTL-cached 60s, invalidated on upload/delete |
| 4-stage retrieval | Hybrid search → section grouping (≥0.30) → context assembly → citations |
| Thinking suppressed | 4 layers: thinkingConfig MINIMAL + thought:true filter + ThoughtFilter + strip_reasoning() |
| Rate limiting | **Sliding Window (Redis Lua)** — 30 req/min per user |

## 3. Hard Delete Workflow

```mermaid
sequenceDiagram
    participant Client
    participant API
    participant Registry as Redis Registry
    participant Cleanup as butler (cleanup queue)
    participant Qdrant
    participant RustFS
    participant DB

    Client->>API: DELETE /api/v1/documents/{document_id}
    API->>Redis: enqueue delete_document_task
    API-->>Client: 202 accepted

    Cleanup->>Cleanup: CleanupService orchestrates 6-step hard delete
    Cleanup->>Registry: registry.delete()
    Cleanup->>Qdrant: delete all vectors
    Cleanup->>DB: delete sections from document_sections
    Cleanup->>RustFS: delete file object
    Cleanup->>DB: DELETE document row
    Cleanup->>Registry: registry.purge()
```

## 4. Decoupled Audit Logging (New in V4)

High-concurrency logging that never blocks the user.

```mermaid
sequenceDiagram
    participant API
    participant Stream as Redis Stream (audit:stream)
    participant Worker as AuditStreamWorker (Celery)
    participant DB as PostgreSQL

    API->>Stream: XADD (audit:stream, payload)
    Note over API: Returns in < 1ms
    
    loop Every 5-10s
        Worker->>Stream: XREAD (batch_size=100)
        Worker->>DB: Batch INSERT SecurityAudit
        Worker->>Stream: XDEL (Acknowledge)
    end
```

### Audit Invariants

| Rule | Detail |
|------|--------|
| **Zero Blocking** | API never writes to SecurityAudit table directly |
| **Batch Write** | AuditStreamWorker groups events to minimize DB transaction overhead |
| **Persistence** | Redis Stream acts as a reliable buffer until DB is ready |

## 5. Analytics Data Flow

Tokens stored per ChatMessage → aggregated by SQL query → endpoint. Admin sees system-wide, members see own stats. Pricing configurable via `AI_INPUT_COST_PER_1M`.

## Error Handling & Resilience

| Strategy | Handling |
|----------|----------|
| **Circuit Breaker** | Trips to OPEN if Qdrant/GPU fails repeatedly, prevents loop hanging |
| **Distributed Lock** | Redis Mutex prevents race conditions during session hydration |
| **Rate Limiter** | Sliding window protects AI resources from abuse |
| Parse failure | status=failed, parse_error set, SoftTimeLimitExceeded handled |
