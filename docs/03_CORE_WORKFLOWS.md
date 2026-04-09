# 03 — Core Workflows

Status: implementation workflow baseline aligned with the new architecture.

## Workflow 1: Upload -> Queue -> Parse -> Index -> Ready

```mermaid
sequenceDiagram
    participant Client
    participant API as FastAPI
    participant RustFS
    participant DB as PostgreSQL
    participant Redis
    participant Worker as Celery Worker
    participant Parser as ParserManager
    participant Pipeline as IngestionPipeline
    participant Qdrant

    Client->>API: POST /api/v1/upload
    API->>API: validate auth and size
    API->>RustFS: store file
    API->>DB: create document(status=pending)
    API->>Redis: enqueue parse task
    API-->>Client: 202 task_id

    Redis->>Worker: parse task
    Worker->>DB: set document status=processing
    Worker->>Parser: parse(filename, bytes)
    Parser->>Pipeline: nodes + parse metadata
    Pipeline->>Pipeline: validate hierarchy
    Pipeline->>Pipeline: embed nodes with BGE-M3
    Pipeline->>Qdrant: upsert vectors
    Worker->>DB: save artifact metadata
    Worker->>DB: set status=ready or failed
```

### Upload Invariants

| Rule | Requirement |
|------|-------------|
| Non-blocking upload | Upload endpoint returns task_id quickly |
| Single ingestion path | Worker uses parser manager + ingestion pipeline only |
| Persistence | Save structured nodes and ingestion artifact |
| Recovery | Mark failed status with parse_error on exception |

## Workflow 2: Chat -> Retrieve -> Generate -> JSON Response

```mermaid
sequenceDiagram
    participant Client
    participant API
    participant Retriever
    participant DB as PostgreSQL
    participant Qdrant
    participant Provider as AI Provider

    Client->>API: POST /api/v1/chat
    API->>API: validate auth and payload
    API->>Retriever: retrieve context
    Retriever->>DB: fetch latest non-deleted metadata scope
    Retriever->>Qdrant: vector similarity search
    Retriever->>DB: fetch parent context and citation fields
    Retriever-->>API: ranked grounded context
    API->>Provider: generate response
    Provider-->>API: answer payload
    API-->>Client: JSON answer + citations
```

### Chat Invariants

| Rule | Requirement |
|------|-------------|
| Grounding first | Build answer from retrieved context |
| Citation required | Return citation payload for grounded answers |
| Retrieval filters | Exclude soft-deleted docs, prefer latest version |
| Provider swap safety | Chat route stays provider-agnostic |

## Workflow 3: Delete -> Exclude -> Retain History

```mermaid
sequenceDiagram
    participant Client
    participant API
    participant DB
    participant Qdrant

    Client->>API: DELETE /api/v1/documents/{document_id}
    API->>DB: soft delete document
    API->>Qdrant: remove vectors for document
    API-->>Client: deleted

    Note over API,DB: New retrieval excludes deleted documents
    Note over API,DB: Historical chat messages remain auditable
```

### Delete Invariants

| Rule | Requirement |
|------|-------------|
| Soft-delete first | Never hard-delete immediately in user path |
| Retrieval exclusion | Deleted docs excluded from new retrieval |
| History integrity | Existing chat history remains available |

## Workflow 4: Optional SQL Connector Route

| Condition | Behavior |
|-----------|----------|
| Question answered by docs | Stay on document RAG route |
| Explicit live business-data request + approved connector | Allow SQL connector route |
| SQL connector unavailable | Return explicit limitation, no ad hoc SQL |

## Error Handling Baseline

| Error | Handling |
|-------|----------|
| parse failure | document status=failed with parse_error |
| hierarchy inconsistency | log warning, safe fallback attachment policy |
| embedding/vector store failure | fail task deterministically, persist reason |
| provider timeout | retry with reduced context then graceful error |
