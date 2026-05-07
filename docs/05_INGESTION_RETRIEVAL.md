# 05 — Ingestion and Retrieval Strategy

Authoritative pipeline details. Architecture in `01_ARCHITECTURE.md`, workflows in `02_WORKFLOWS.md`.

## Primary Principle

Qdrant for retrieval. PostgreSQL for metadata/state. Redis for cache and queue. No full-text PostgreSQL scan as retrieval path.

## Ingestion Pipeline (13 Steps)

1. **Upload**: Client uploads file → API saves to RustFS → inserts `documents` row (status=pending).
2. **Enqueue**: API enqueues `parse_document_task` to Redis queue `ingestion`.
3. **Download**: Worker downloads file bytes from RustFS.
4. **PaddleOCR** (mandatory): `force_full_page_ocr=True` — Engine: PaddleOCR via RapidOCR ONNX.
5. **Heading hierarchy fix**: Post-processor corrects flat levels from Docling using PDF bookmarks and numbering patterns.
6. **Method D extraction**: Direct from Docling `iterate_items()` — preserves page spans, heading levels, and table structures.
7. **Contextual Enrichment**: **Contextualizer** prepends document-level summary to every chunk.
8. **Section extraction**: Items → sections with exact page spans → breadcrumbs.
9. **Chunk splitting**: Sections → ~400 token chunks with ~75 token overlap, linked via `section_id`.
10. **HierarchyValidator**: Checks parent-child consistency and structure depth.
11. **RuleBasedRefiner**: Fixes OCR errors and detects noise (0GB VRAM).
12. **Section storage**: SectionRepository stores in `document_sections` (order_index canonical).
13. **Embed & Index**: Parallel embedding → upsert to Qdrant (dense + BM25 sparse) → Set status=ready → async BM25 vocab rebuild.

### OCR Backend

| Strategy | When | Config |
|----------|------|--------|
| PaddleOCR (`force_full_page_ocr=True`) | All PDFs + images | `converter` + RapidOcrOptions vi+en |
| Classic parser | DOCX, XLSX, TXT, Markdown | No OCR — native text extraction |

### Embedding Model

| Parameter | Value |
|-----------|-------|
| Model | AITeamVN/Vietnamese_Embedding_v2 |
| Dimensions | 1024 |
| Batch size | 32 (`INGESTION_EMBEDDING_CHUNK_SIZE`) |

## Retrieval Pipeline (5-Stage)

1. **Rate limit**: Atomic Lua script — 30 req/min per user.
2. **Semantic Cache**: Redis Vector Search matching similarity < 0.02. HIT → return immediately.
3. **Hybrid search**: Parallel Dense (Semantic) + Sparse (BM25 Keyword) + Recommendation (Feedback).
4. **Section grouping**: Merge queries → dedupe → top 3 sections (score ≥ 0.30).
5. **Neighbor Expansion (Soi sáng)**: Fetch +/- N chunks by `order` to ensure narrative flow (configurable expansion window).

### Stage 2.6: "Soi sáng" (Neighboring Node Expansion)
To ensure the LLM receives a coherent narrative, the system performs a "Neighbor Lookup":
1.  For each top hit, the system identifies its `document_id` and `order`.
2.  It fetches $N$ nodes immediately preceding and following that chunk (configurable via `RETRIEVAL_CONTEXT_EXPANSION_WINDOW`).
3.  Nodes are merged, deduped, and sorted linearly by `order`.

### Hybrid Search: Dense + BM25

| Component | Details |
|-----------|---------|
| Dense model | AITeamVN/Vietnamese_Embedding_v2 (1024-dim, cosine) |
| Sparse model | Custom VietnameseBM25Encoder (Underthesea tokenization) |
| BM25 storage | **Redis + RAM Singleton** (BM25Manager) |

## Implementation Mapping

| Responsibility | Module |
|----------------|--------|
| PaddleOCR (mandatory) | `app/modules/documents/ingestion/docling.py` |
| Hierarchy checks | `app/utils/hierarchy_validator.py` |
| Section storage | `app/modules/documents/repository.py` (SectionRepository) |
| Vector store adapter | `app/adapters/vector_stores/qdrant.py` |
| BM25 index management | `app/utils/bm25_index.py` |
| 5-stage retrieval | `app/modules/chat/retrieval/service.py` |
| Multi-query expansion | `app/modules/chat/retrieval/query_expand.py` |
| User memory service | `app/modules/chat/user_memory_service.py` |
| AI provider (Google) | `app/adapters/ai/google.py` |
| Chat store | `app/utils/chat_store.py:ChatStore` — Redis pipeline atomic ops, history_exists() check |
| Doc ID cache | `app/services/retrieval/retrieval_service.py` — threading.Lock for thread safety |
