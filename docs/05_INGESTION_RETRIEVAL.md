# 05 — Ingestion and Retrieval Strategy

Authoritative pipeline details. Architecture in `01_ARCHITECTURE.md`, workflows in `02_WORKFLOWS.md`.

## Primary Principle

Qdrant for retrieval. PostgreSQL for metadata/state. Redis for cache and queue. No full-text PostgreSQL scan as retrieval path.

## Ingestion Pipeline (12 Steps)

1. **Upload**: Client uploads file → API saves to RustFS → inserts `documents` row (status=pending).
2. **Enqueue**: API enqueues `parse_document_task` to Redis queue `ingestion`.
3. **Download**: Worker downloads file bytes from RustFS.
4. **Smart OCR** (2-pass):
   - Pass 1: Fast extraction `do_ocr=False` → extract embedded text. Works for native PDFs.
   - Scanned detection: If text_density < threshold → likely scanned.
   - Pass 2: Re-convert with `do_ocr=True` + EasyOCR (`vi+en`) → OCR only for scanned PDFs.
   - Images (PNG/JPG): Always OCR pipeline. DOCX: native parsing, no OCR.
5. **Method D extraction**: Direct from `iterate_items()` — preserves page spans, heading levels, table structures:
   - `SectionHeaderItem` → section boundary, `TitleItem` → document title
   - `TextItem` → content, `TableItem` → markdown table, `ListItem` → bullet text
   - `PictureItem` → skip (future: image captioning)
6. **Section extraction**: Items → sections with exact page spans → breadcrumbs from heading stack.
7. **Chunk splitting**: Each section → ~400 token chunks with ~75 token overlap, linked via `section_id`.
8. **HierarchyValidator**: Checks parent-child consistency.
9. **RuleBasedRefiner**: Fixes OCR errors, detects headers (0GB VRAM, ~1ms per node).
10. **Section storage**: SectionRepository stores in `document_sections` (order_index, parent_section_id, page span).
11. **Embed + store**: Chunks embedded in parallel batches of 32 via ThreadPoolExecutor → upsert to Qdrant with named dense vector + BM25 sparse vector + `section_id`. progress_callback updates percent live.
12. **BM25 rebuild**: Full rebuild of BM25 vocab + IDF from all Qdrant chunks. Persisted to `data/bm25_vocab.json`.
13. **Finalize**: Persist ingestion artifact to extra_metadata. Set status=ready. invalidate_doc_ids_cache().

### OCR Backend

| Strategy | When | Config |
|----------|------|--------|
| Fast (`do_ocr=False`) | Native PDFs, DOCX | `converter_fast` |
| OCR fallback (`do_ocr=True`) | Scanned PDFs, images | `converter_ocr` + EasyOCR vi+en |
| Smart detection | After Pass 1: text_density < threshold | Both converters |

Two converters initialized in `_initialize_docling()`. EasyOCR models pre-downloaded during Docker build via BuildKit cache.

### Embedding Model

| Parameter | Value |
|-----------|-------|
| Model | AITeamVN/Vietnamese_Embedding_v2 — BGE-M3 fine-tuned on 1.1M Vietnamese triplets |
| Dimensions | 1024 |
| Max tokens | 8192 |
| Device | GPU fp16 (auto) → CPU ONNX fallback |
| Batch size | 32 (`INGESTION_EMBEDDING_CHUNK_SIZE`) |
| Quantization | Qdrant int8 scalar (4x less RAM, <1% accuracy loss) |
| Accuracy | +16% Accuracy@1 vs BGE-M3 on Vietnamese legal retrieval |
| Inference | Local/offline — no API calls, no rate limits |

Model pre-downloaded during Docker build via BuildKit cache.

## Retrieval Pipeline (4-Stage)

1. **Rate limit**: Atomic Lua script — 30 req/min per user.
2. **Query cache**: MD5-keyed Redis lookup. HIT → skip model inference (TTL=1h).
3. **Query embed**: MISS → local Vietnamese_Embedding_v2 → cache result.
4. **Doc scope**: TTL-cached active doc IDs (60s). PostgreSQL subquery runs once/minute max. Invalidated on upload/delete via `invalidate_doc_ids_cache()`.
5. **Multi-query expansion** (opt-in, `RETRIEVAL_QUERY_EXPANSION_ENABLED=True`): Generate N query variants via AI provider. Each variant uses different vocabulary → broader recall.
6. **Hybrid search**: For each query, run dense + BM25 sparse in parallel → RRF fusion in Qdrant.
7. **Stage 1 — Section grouping**: Merge results across queries (dedupe by node_id, keep max score). Group by section_id → top 3 sections (score ≥ 0.30). Load section details from PostgreSQL.
8. **Stage 2 — Chunk re-ranking**: Prioritise chunks within top sections first, then remaining. Score filter ≥ 0.35. Dedup overlapping chunks (100-char signature).
9. **Stage 3 — Cross-encoder reranking**: AITeamVN/Vietnamese_Reranker scores (query, passage) pairs → top 5 chunks by relevance.
10. **Stage 4 — Context assembly**: Enriched context blocks with breadcrumb hierarchy + page ranges for LLM.

### Hybrid Search: Dense + BM25

| Component | Details |
|-----------|---------|
| Dense model | AITeamVN/Vietnamese_Embedding_v2 (1024-dim, cosine) |
| Sparse model | Custom VietnameseBM25Encoder (Underthesea tokenization + BM25 scoring) |
| Fusion | Reciprocal Rank Fusion (RRF) via Qdrant Prefetch API |
| Qdrant config | Named vectors: "dense" + "sparse-bm25" (Modifier.IDF) |
| BM25 params | k1=1.5, b=0.75 (standard defaults) |
| BM25 vocab | Built from all Qdrant chunks, persisted to `data/bm25_vocab.json` |
| Vocab rebuild | After every document upload/delete (full rebuild for correct IDF) |

### Cross-Encoder Reranker

| Parameter | Value |
|-----------|-------|
| Model | AITeamVN/Vietnamese_Reranker |
| Benchmark | MRR@10 = 0.8672 on Legal Zalo (best for Vietnamese) |
| Context | 2304 tokens (256 query + 2048 passage) |
| Device | CPU (~50-100ms for 20 candidates) |
| Top-k | 5 (configurable via `RETRIEVAL_RERANK_TOP_K`) |

### Multi-Query Expansion

| Parameter | Value |
|-----------|-------|
| Enabled | Default OFF — opt-in via `RETRIEVAL_QUERY_EXPANSION_ENABLED=True` |
| Variants | 3 (configurable via `RETRIEVAL_QUERY_EXPANSION_VARIANTS`) |
| Provider | Same Gemini model used for chat |
| Timeout | 3s — falls back to original query on timeout |

### Why 4-Stage

- **Hybrid search**: Dense catches semantic similarity, BM25 catches exact keyword matches (e.g., "khoản 3 điều 15"). RRF fusion combines both → higher recall.
- **Cross-encoder**: Bi-encoder similarity is fast but approximate. Cross-encoder scores (query, passage) pairs directly → higher precision for final ranking.
- **Multi-query**: User's wording may not match document phrasing. Variants broaden recall with different vocabulary.
- **Section grouping**: Scales to 300+ page documents via section narrowing.

### Score Thresholds

| Value | Effect |
|-------|--------|
| 0.35 (default) | Good balance for Vietnamese technical docs |
| 0.5+ | Stricter — fewer but more relevant |
| 0.2 | More chunks — risk of noise |
| Override | `RETRIEVAL_MIN_SCORE` env var |

## Tree Ordering Policy

Display order from `document_sections.order_index`, then page span. Qdrant does not define display order.

## Fallback Policy

| Failure | Behavior |
|---------|----------|
| Docling parse failure | ClassicParser fallback (text extraction only) |
| Chunk embed/store failure | Log, skip chunk, continue with rest |
| Qdrant timeout (5s) | Empty context, LLM answers without grounding |
| No documents in scope | "Chưa có tài liệu nào được index" |
| Score eliminates all results | Same as above |

## Implementation Mapping

| Responsibility | Module |
|----------------|--------|
| Smart OCR 2-pass | `app/adapters/parsers/docling.py:_convert_with_docling()` |
| Method D item extraction | `app/adapters/parsers/docling.py:_extract_from_docling_items()` |
| Table → markdown | `app/adapters/parsers/docling.py:_table_item_to_markdown()` |
| Page number extraction | `app/adapters/parsers/docling.py:_get_page_number()` |
| Scanned PDF detection | `app/adapters/parsers/docling.py:_is_scanned()` |
| Section + chunk extraction | `app/adapters/parsers/docling.py:_extract_from_docling_items()` |
| Markdown fallback path | `app/adapters/parsers/docling.py:_extract_sections_from_markdown()` |
| Parser selection + fallback | `app/services/ingestion/parser_manager.py` |
| Ingestion orchestration | `app/services/ingestion/pipeline.py` |
| Hierarchy checks | `app/services/ingestion/hierarchy_validator.py` |
| Section storage (PostgreSQL) | `app/services/storage/document_store.py:SectionRepository` |
| Parallel embedding | `app/adapters/embeddings/sentence_transformer.py:embed_batch()` |
| Vector store adapter | `app/adapters/vector_stores/qdrant.py` — named dense + sparse-bm25, int8 quantized |
| BM25 sparse encoder | `app/adapters/sparse_embeddings/vietnamese_bm25.py` — Underthesea tokenization + BM25 scoring |
| BM25 index management | `app/services/retrieval/bm25_index.py` — vocab build from Qdrant, persist/rebuild |
| 4-stage retrieval | `app/services/retrieval/rag.py:retrieve_context()` |
| Cross-encoder reranker | `app/services/retrieval/reranker.py` — AITeamVN/Vietnamese_Reranker |
| Multi-query expansion | `app/services/retrieval/query_expand.py` — Gemini query variants |
| Doc ID TTL cache + invalidation | `app/services/retrieval/rag.py` |
| Query embedding cache | `app/services/retrieval/cache.py` |
| Hardware auto-detection | `app/core/hardware.py` |
| Ingestion tasks | `app/workers/upload_pipeline.py` — includes BM25 rebuild after ingestion |
| Cleanup tasks + beat | `app/workers/cleanup_pipeline.py` — includes BM25 rebuild after deletion |
| User memory service | `app/services/chat/memory.py:UserMemoryService` |
| AI provider (Google) | `app/adapters/ai/google.py:GoogleAIProvider` — singleton via lru_cache, x-goog-api-key header |
| Provider factory | `app/adapters/ai/__init__.py:build_ai_provider()` — @lru_cache(maxsize=1) singleton |
| Thinking control | `app/adapters/ai/google.py` (strip_reasoning + ThoughtFilter + thinkingConfig) |
| Multi-turn context | `app/adapters/ai/google.py:_build_contents()` |
| Memory CRUD routes | `app/api/routes/memories.py` |
| Chat store | `app/services/chat/store.py:ChatStore` — Redis pipeline atomic ops, history_exists() check |
| Doc ID cache | `app/services/retrieval/rag.py` — threading.Lock for thread safety |
