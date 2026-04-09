# 07 — Ingestion and Retrieval Strategy

Status: implementation strategy for the new ingestion and retrieval direction.

## Primary Principle

Use Qdrant for retrieval data path and keep PostgreSQL as system metadata/state database.

## Ingestion Pipeline (Authoritative)

1. Upload file to RustFS (S3-compatible storage).
2. Queue async worker task.
3. Parse with Docling to Markdown.
4. Build hierarchy with LlamaIndex MarkdownNodeParser.
5. Validate parent-child structure.
6. Generate embeddings with Gemini Embedding API.
7. Store vectors and retrieval payload in Qdrant.
8. Persist system metadata and task state in PostgreSQL.

## Storage Contract

| Store | What belongs there |
|-------|--------------------|
| Qdrant | node text payload, vectors, retrieval metadata |
| PostgreSQL | document status, file metadata, versions, audit, sessions |
| RustFS | original file and ingestion artifacts |

## Retrieval Contract

1. Filter allowed documents from PostgreSQL (latest active, not deleted).
2. Embed user query with Gemini Embedding API.
3. Query Qdrant directly for top-k relevant nodes.
4. Build answer context from Qdrant payload.
5. Generate response and return citations.

Do not scan PostgreSQL full_text fields as the primary retrieval path.

## Version and Deletion Policy

| Policy | Behavior |
|--------|----------|
| Latest version | prefer latest non-deleted version per file |
| Soft delete | exclude deleted documents from new retrieval |
| Historical chats | keep existing history for auditability |

## Fallback Policy

| Failure | Fallback |
|---------|----------|
| Docling parse failure | classic parser fallback |
| Qdrant unavailable | explicit retrieval limitation |
| Generation timeout | reduced-context retry, then explicit error |

## Quality Signals

Persist ingestion artifact summary including:

- parser path used
- node count
- text character count
- warnings
- timing

## Implementation Mapping

| Responsibility | Module |
|----------------|--------|
| Parser selection | app/services/ingestion/parser_manager.py |
| Ingestion orchestration | app/services/ingestion/pipeline.py |
| Hierarchy checks | app/services/ingestion/hierarchy_validator.py |
| Vector adapter | app/adapters/vector_stores/qdrant.py |
| Embedding adapter | app/adapters/embeddings/gemini.py |
| Retrieval service | app/services/rag.py |
