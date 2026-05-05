# 05 — Ingestion and Retrieval Strategy

Authoritative pipeline details. Architecture in `01_ARCHITECTURE.md`, workflows in `02_WORKFLOWS.md`.

## Primary Principle

Qdrant for retrieval. PostgreSQL for metadata/state. Redis for cache and queue. No full-text PostgreSQL scan as retrieval path.

## Ingestion Pipeline (13 Steps)

1. **Upload**: Client uploads file → API saves to RustFS → inserts `documents` row (status=pending).
2. **Enqueue**: API enqueues `parse_document_task` to Redis queue `ingestion`.
3. **Download**: Worker downloads file bytes from RustFS.
4. **PaddleOCR** (mandatory, single-pass):
   - `force_full_page_ocr=True` — OCR on every page, no scanned detection.
   - Engine: PaddleOCR via RapidOCR ONNX backend (`rapidocr_onnxruntime==1.4.4`).
   - Languages: Vietnamese + English.
   - Images (PNG/JPG): Always OCR pipeline. DOCX: Docling WordFormatOption (structure extraction).
5. **Heading hierarchy fix** (PDF only):
   - `docling-hierarchical-pdf` post-processor corrects flat `level=1` from Docling.
   - 3 strategies: PDF bookmarks (pymupdf) → numbering patterns → font size/style clustering.
   - Vietnamese heading correction: "CHƯƠNG I" / "PHẦN 1" → level 1 override.
   - Noise filtering: empty sections on pages 1-2 (cover), TOC markers removed.
6. **Method D extraction**: Direct from `iterate_items()` — preserves page spans, heading levels, table structures:
   - `SectionHeaderItem` → section boundary, `TitleItem` → document title
   - `TextItem` → content, `TableItem` → markdown table, `ListItem` → bullet text
   - `PictureItem` → skip (future: image captioning)
7. **Section extraction**: Items → sections with exact page spans → breadcrumbs from heading stack.
8. **Chunk splitting**: Each section → ~400 token chunks with ~75 token overlap, linked via `section_id`.
9. **HierarchyValidator** (`app/utils/hierarchy_validator.py`): Checks parent-child consistency.
10. **RuleBasedRefiner** (`app/utils/text_refiner.py`): Fixes OCR errors, detects headers (0GB VRAM, ~1ms per node).
11. **Section storage**: SectionRepository stores in `document_sections` (order_index, parent_section_id, page span).
12. **Embed + store**: Chunks embedded in parallel batches of 32 via ThreadPoolExecutor → upsert to Qdrant with named dense vector + BM25 sparse vector + `section_id`. progress_callback updates percent live.
13. **BM25 rebuild + finalize**: Set status=ready. invalidate_doc_ids_cache(). Dispatch `rebuild_bm25_index_task` (queue=ingestion) — async BM25 vocab rebuild from Qdrant, runs after ingestion completes.

### OCR Backend

| Strategy | When | Config |
|----------|------|--------|
| PaddleOCR (`force_full_page_ocr=True`) | All PDFs + images | `converter` + RapidOcrOptions vi+en |
| Classic parser | DOCX, XLSX, TXT, Markdown | No OCR — native text extraction |

Parser selection and fallback managed by `ParserManager` (`app/adapters/parsers/manager.py`). Single converter initialized in `_initialize_docling()`. PaddleOCR (RapidOCR ONNX) models pre-downloaded during Docker build.
PaddleOCR is MANDATORY — if backend missing, `_require_paddleocr()` raises RuntimeError and worker fails with clear error.

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
4. **Doc scope**: TTL-cached active doc IDs (60s). `DocumentRepository.get_latest_active_document_ids()` — returns set of latest-version ready doc IDs. Invalidated on upload/delete via `invalidate_doc_ids_cache()`.
5. **Multi-query expansion** (opt-in, `RETRIEVAL_QUERY_EXPANSION_ENABLED=True`): Generate N query variants via AI provider. Each variant uses different vocabulary → broader recall.
6. **Hybrid search (Multi-intent)**: For each query, run a 3-way prefetch in parallel:
   - **Sparse (BM25)**: Keyword relevance.
   - **Dense (Semantic)**: Standard query semantic similarity.
   - **Recommendation (Feedback)**: Guiding results towards "Liked" chunks and away from "Disliked" ones using Qdrant's `RecommendQuery` with `strategy="best_score"`.
7. **RRF Fusion**: Combine all 3 intents using Reciprocal Rank Fusion (RRF) via Qdrant Prefetch API. This ensures the search stays grounded in the user's query while respecting historical feedback.
8. **Stage 1 — Section grouping**: Merge results across queries (dedupe by node_id, keep max score). Group by section_id → top 3 sections (score ≥ 0.30). Load section details via `SectionRepository.get_sections_for_rag()`.
9. **Stage 2 — Chunk re-ranking**: Prioritise chunks within top sections first, then remaining. Score filter ≥ 0.35. Dedup overlapping chunks (100-char signature).
10. **Stage 3 — Cross-encoder reranking** (optional, off by default): AITeamVN/Vietnamese_Reranker (`app/adapters/reranker/reranker.py`) scores (query, passage) pairs → top 5 chunks by relevance. Disabled via `RETRIEVAL_RERANK_ENABLED=false` — when sending full section context, LLM self-ranks effectively. Enable via env var if needed.
11. **Stage 4 — Context assembly**: Map chunks → full section content from PostgreSQL. Deduplicate by section_id. Send complete section text (not chunk fragments) to LLM with breadcrumb hierarchy + page ranges. This ensures the LLM sees all content within a section, including details that may span multiple chunks.

### Hybrid Search: Dense + BM25

| Component | Details |
|-----------|---------|
| Dense model | AITeamVN/Vietnamese_Embedding_v2 (1024-dim, cosine) |
| Sparse model | Custom VietnameseBM25Encoder (Underthesea tokenization + BM25 scoring) |
| Fusion | Reciprocal Rank Fusion (RRF) via Qdrant Prefetch API |
| Qdrant config | Named vectors: "dense" + "sparse-bm25" (Modifier.IDF) |
| BM25 params | k1=1.5, b=0.75 (standard defaults) |
| BM25 vocab | Built from all Qdrant chunks, persisted to `data/bm25_vocab.json` |
| Vocab rebuild | After every document upload/delete (full rebuild for correct IDF). Dispatched as async Celery task (`rebuild_bm25_index_task`, queue=ingestion) — does not block ingestion completion |
| Vocab cache | TTL-based reload (120s) to pick up changes from Celery worker. Note: Redis 512mb maxmemory with allkeys-lru may evict cache keys under memory pressure |

### Cross-Encoder Reranker

| Parameter | Value |
|-----------|-------|
| Model | AITeamVN/Vietnamese_Reranker |
| Benchmark | MRR@10 = 0.8672 on Legal Zalo (best for Vietnamese) |
| Context | 2304 tokens (256 query + 2048 passage) |
| Device | GPU auto / CPU fallback (~50-100ms for 20 candidates on CPU) |
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
| PaddleOCR (mandatory) | `app/adapters/parsers/docling.py:_convert_with_docling()` |
| Method D item extraction | `app/adapters/parsers/docling.py:_extract_from_docling_items()` |
| Table → markdown | `app/adapters/parsers/docling.py:_table_item_to_markdown()` |
| Page number extraction | `app/adapters/parsers/docling.py:_get_page_number()` |
| Scanned PDF detection | `app/adapters/parsers/docling.py:_is_scanned()` |
| Section + chunk extraction | `app/adapters/parsers/docling.py:_extract_from_docling_items()` |
| Markdown fallback path | `app/adapters/parsers/docling.py:_extract_sections_from_markdown()` |
| Parser selection + fallback | `app/adapters/parsers/manager.py:ParserManager` |
| Ingestion orchestration | `app/services/ingestion/ingestion_service.py:IngestionService` (accepts optional section_repo) |
| Hierarchy checks | `app/utils/hierarchy_validator.py:HierarchyValidator` |
| Section storage (PostgreSQL) | `app/repositories/section_repository.py:SectionRepository` |
| Parallel embedding | `app/adapters/embeddings/sentence_transformer.py:embed_batch()` |
| Vector store adapter | `app/adapters/vector_stores/qdrant.py` — named dense + sparse-bm25, int8 quantized. DocumentService uses build_vector_store() factory |
| BM25 sparse encoder | `app/adapters/sparse_embeddings/vietnamese_bm25.py` — Underthesea tokenization + BM25 scoring |
| BM25 index management | `app/utils/bm25_index.py` — vocab build from Qdrant, persist/rebuild |
| 4-stage retrieval | `app/services/retrieval/retrieval_service.py:retrieve_context()` — uses DocumentRepository + SectionRepository methods |
| Cross-encoder reranker | `app/adapters/reranker/reranker.py` — AITeamVN/Vietnamese_Reranker |
| Multi-query expansion | `app/services/retrieval/query_expand.py` — Gemini query variants (domain logic for RAG) |
| Doc ID TTL cache + invalidation | `app/services/retrieval/retrieval_service.py` |
| Query embedding cache | `app/utils/query_cache.py` |
| Hardware auto-detection | `app/core/hardware.py` |
| Ingestion tasks | `app/workers/upload_pipeline.py` — dispatches rebuild_bm25_index_task after ingestion |
| Cleanup tasks + beat | `app/workers/cleanup_pipeline.py` — uses CleanupService, dispatches rebuild_bm25_index_task after deletion |
| Maintenance tasks | `app/workers/maintenance_tasks.py` — rebuild_bm25_index_task (ingestion queue), cleanup_orphaned_vectors_task (cleanup queue, Beat daily), record_audit_task (default queue) |
| Chat tasks | `app/workers/chat_tasks.py` — compatibility Celery wrapper; SSE path persists assistant messages synchronously before final done:true |
| Memory tasks | `app/workers/memory_tasks.py` — extract_memories_task on default queue (async memory extraction, replaces asyncio.create_task) |
| User memory service | `app/services/chat/user_memory_service.py:UserMemoryService` — receives redis.Redis + MemoryRepository via DI in request paths; worker context may use short-lived repositories |
| Memory service | `app/services/chat/memory_service.py:MemoryService` — receives UserMemoryService via DI |
| AI provider (Google) | `app/adapters/ai/google.py:GoogleAIProvider` — singleton via lru_cache, x-goog-api-key header |
| Provider factory | `app/adapters/ai/__init__.py:build_ai_provider()` — @lru_cache(maxsize=1) singleton |
| Thinking control | `app/adapters/ai/google.py` (strip_reasoning + ThoughtFilter + thinkingConfig) |
| Multi-turn context | `app/adapters/ai/google.py:_build_contents()` |
| Memory CRUD routes | `app/api/routes/memories.py` |
| Chat store | `app/utils/chat_store.py:ChatStore` — Redis pipeline atomic ops, history_exists() check |
| Doc ID cache | `app/services/retrieval/retrieval_service.py` — threading.Lock for thread safety |
