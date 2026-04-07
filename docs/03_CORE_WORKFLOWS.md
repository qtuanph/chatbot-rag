# 03 — Core Workflows

> Status: target production workflows. Upload, storage, async task tracking, and delete are implemented; chat is still a placeholder.

## Workflow 1: Upload → Parse → Hierarchical Tree Index → Ready

```mermaid
sequenceDiagram
    participant C as Client
    participant API as API Gateway
    participant DB as PostgreSQL
    participant Redis as Redis Queue
    participant Worker as Celery Worker
    participant Parser as Document Parser
    participant Tree as Tree Builder
    participant Embed as Embedding Service

    C->>API: POST /upload (file, metadata)
    API->>API: Validate JWT, extract tenant_id
    API->>DB: INSERT document (status='pending')
    API->>Redis: Enqueue parse_task(doc_id, file_path)
    API->>C: 202 {task_id, status: "queued"}
    C->>API: GET /status/{task_id}
    API->>C: {status, progress, document_id}

    Redis->>Worker: Dequeue task
    Worker->>Parser: Parse file (PDF/DOCX/XLSX/Images)
    Parser-->>Worker: Native text + OCR fallback + structure

    Worker->>Tree: Build document tree
    Tree->>Tree: Document root -> page nodes -> section nodes
    Tree-->>Worker: Tree nodes with parent_id and level

    Worker->>DB: INSERT doc_nodes (batch)
    Worker->>DB: UPDATE document status='ready'
```

### Checkpointing & Retry

| Checkpoint | What's Saved | Recovery |
|------------|-------------|----------|
| Upload complete | Document row + file stored | Resume from parse |
| Parse complete | Raw text extracted | Resume from tree building |
| Tree built | Hierarchical nodes in memory | Resume from embedding |
| Embedding done | Vectors computed | Resume from DB insert |
| Final | Document status='ready' | Complete |

**Retry Strategy:** Max 3 attempts, exponential backoff (30s → 2m → 8m). After 3 failures → status='failed', notify user.

## Workflow 2: Query → Router → Retrieve → Generate → SSE

```mermaid
sequenceDiagram
    participant C as Client
    participant API as API Gateway
    participant DB as PostgreSQL
    participant Router as Query Router
    participant Filter as Metadata Filter
    participant Retriever as Hierarchical Retriever
    participant AI as AI Provider
    participant Rerank as BGE Reranker

    C->>API: POST /chat {query, session_id?}
    API->>API: Validate JWT, extract tenant_id
    API->>DB: Load chat history (if session_id)
    
    API->>Router: Route query with tenant context
    Router->>Router: Classify: on-topic / out-of-scope
    
    alt Out of scope
        Router->>C: SSE: "I can only answer based on uploaded documents."
    else On topic
        Router->>Filter: Apply tenant_id and router filters
        Note over Filter: Enforce deleted_at IS NULL,
        Note over Filter: optional document_ids/metadata,
        Note over Filter: latest version only by default
        Filter->>Retriever: Candidate documents
        Retriever->>Retriever: Navigate tree with query
        
        Retriever->>DB: Search heading embeddings (HNSW)
        DB-->>Retriever: Top-K matching headings
        
        Retriever->>Retriever: Expand to full sections
        Retriever->>Retriever: Include parent context
        
        Retriever->>Rerank: Rerank sections by relevance
        Rerank-->>Retriever: Ranked sections with scores
        
        Retriever->>AI: Build prompt with sections + history

        alt Generation succeeds
            AI->>API: SSE stream (token by token)
            API->>C: Forward SSE chunks
            AI-->>API: Generation complete
            API->>DB: Save message + citations + metrics
        else Provider timeout / transient error
            AI-->>API: Timeout or 5xx
            API->>AI: Retry once with reduced context
            alt Retry succeeds
                AI->>API: SSE stream (token by token)
                API->>C: Forward SSE chunks
                API->>DB: Save message + citations + metrics
            else Retry fails
                API->>C: SSE error event + partial answer warning
                API->>DB: Save failed attempt metadata
            end
        end
    end
```

### Context Budgeting Rule

| Component | Budget | Rationale |
|-----------|--------|-----------|
| System prompt | ~10% | Instructions, guardrails |
| Chat history | ~20% | Recent turns (last 5-10) |
| Retrieved sections | ≤60% | Full sections, not chunks |
| Safety margin | ~10% | Buffer for response generation |

**Never exceed 60% of context window for retrieved content.** If sections are too large, truncate from the end, never cut mid-sentence.

## Workflow 2B: Query -> SQL Connector (Future, Conditional)

```mermaid
sequenceDiagram
    participant C as Client
    participant API as API Gateway
    participant Router as Query Router
    participant Policy as Query Policy
    participant Catalog as Schema Catalog
    participant SQL as Safe SQL Executor
    participant DS as SQLServerDataSource
    participant AI as AI Provider

    C->>API: POST /chat {query}
    API->>Router: Route query
    Router->>Router: Classify as document or data question

    alt Not a data question
        Router-->>API: Use document workflow
    else Data question
        Router->>Policy: Check connector configured + tenant authorized
        alt Not configured or denied
            Policy-->>API: Return explicit limitation
        else Allowed
            Policy->>Catalog: Load table descriptions + join hints
            Catalog-->>SQL: Provide safe planning context
            SQL->>SQL: Generate read-only SQL plan
            SQL->>DS: Execute validated SELECT
            DS-->>SQL: Rows + metadata
            SQL-->>AI: Structured result context
            AI-->>API: Grounded answer + data citations
        end
    end
```

### SQL Routing Invariants

| Rule | Requirement |
|------|-------------|
| Default route | Document RAG remains the default answer path |
| SQL trigger | SQL path is used only for clearly data-centric questions |
| Access mode | SQL execution MUST be read-only and policy-checked |
| Planning context | SQL generation MUST use schema metadata, table descriptions, and join hints |
| Audit | Every executed SQL statement MUST be logged |

## Workflow 3: Delete → Soft Flag → Exclusion → Cleanup

```mermaid
sequenceDiagram
    participant C as Client
    participant API as API Gateway
    participant DB as PostgreSQL
    participant Router as Query Router
    participant Cleanup as Async Cleanup

    C->>API: DELETE /documents/{id}
    API->>API: Validate JWT, extract tenant_id
    API->>DB: UPDATE documents SET deleted_at=now()
    API->>C: 200 {status: "deleted"}
    
    Note over Router: Next query automatically excludes<br/>deleted documents via RLS + WHERE clause
    
    alt Chat message cites deleted doc
        Router->>C: Show citation with [Đã xóa] tag
    end
    
    Note over Cleanup: Nightly Celery beat task
    Cleanup->>DB: Find docs where deleted_at < now() - 30 days
    Cleanup->>DB: DELETE doc_nodes WHERE document_id IN (...)
    Cleanup->>DB: DELETE documents WHERE deleted_at < threshold
    Cleanup->>Cleanup: Remove files from storage
```

### Error States & Handling

| Error | Trigger | Response |
|-------|---------|----------|
| `tenant_id mismatch` | JWT tenant ≠ document tenant | 403 Forbidden |
| `document not found` | ID doesn't exist or deleted | 404 Not Found |
| `parse timeout` | Large file, OCR taking too long | Retry with warning |
| `embedding OOM` | Too many nodes at once | Batch reduce size |
| `LLM timeout` | AI provider slow | Fallback to BM25 + warning |
| `SSE disconnect` | Client drops connection | Graceful stop, save partial |

## Workflow Invariants

| Workflow | Requirement |
|----------|-------------|
| Upload | MUST return quickly with `task_id`; MUST NOT parse inline in the request thread |
| Parse | MUST checkpoint by stage so retries do not restart from zero unnecessarily |
| Query | MUST apply tenant filter, soft-delete exclusion, and version preference before retrieval |
| Generation | MUST stream via SSE and persist final citations/metrics |
| Delete | MUST soft delete first and MUST exclude deleted docs from new retrieval immediately |

## AI Coding Guardrails

| If implementing | Required behavior |
|----------------|-------------------|
| Upload route | Return `202` for accepted async processing |
| Task polling | Read status from persisted task/document state, not in-memory globals |
| Chat route | Preserve SSE event names and payload shapes exactly as documented |
| Cleanup worker | Delete files only after hard-delete retention threshold is met |
