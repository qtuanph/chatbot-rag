# 07 — Ingestion and Retrieval Strategy

Status: authoritative strategy — updated to reflect Method D, Smart OCR Strategy, and worker architecture refactor.

## Primary Principle

Use Qdrant for retrieval data path. Keep PostgreSQL as system metadata/state database. Redis for cache and queue only. No full-text scan of PostgreSQL as retrieval path.

---

## Ingestion Pipeline (Authoritative)

### Steps

1. Client uploads file → API saves to RustFS → inserts `documents` row (`status=pending`).
2. API enqueues `parse_document_task` to Redis queue `ingestion`.
3. Upload-pipeline worker downloads file bytes from RustFS.
4. **Smart OCR Strategy** (2-pass):
   - **Pass 1**: Fast extraction with `do_ocr=False` → extract embedded text directly. Works perfectly for native PDFs.
   - **Scanned detection**: If total text / page count < threshold → likely scanned PDF.
   - **Pass 2 (fallback)**: Re-convert with `do_ocr=True` + EasyOCR (`lang=["vi","en"]`) → OCR only for scanned PDFs.
   - **Images (PNG/JPG)**: Always use OCR pipeline.
   - **DOCX**: Docling native parsing, no OCR needed.
5. **Method D**: Extract directly from `iterate_items()` — preserves page spans, heading levels, table structures with 100% metadata fidelity for extracted text (tree order still comes from PostgreSQL):
   - `SectionHeaderItem` → section boundary (level from `item.level`, page_no from provenance)
   - `TitleItem` → document title (level 0)
   - `TextItem` → content text (page_no from provenance)
   - `TableItem` → convert cells to markdown table (page_no from provenance)
   - `ListItem` → bullet/numbered text
   - `PictureItem` → skip (future: image captioning)
6. **Section extraction**: Items → sections with exact page spans → breadcrumbs from heading stack.
7. **Chunk splitting**: Each section → chunks of ~400 tokens with ~75 token overlap. Each chunk linked to section via `section_id` in metadata.
8. **HierarchyValidator** checks parent-child consistency.
9. **RuleBasedRefiner** fixes OCR errors, detects headers (0GB VRAM, ~1ms per node).
10. **SectionRepository** stores sections in PostgreSQL `document_sections` table as the canonical order source (`order_index`, `parent_section_id`, page span).
11. Sequential chunks of **32 nodes** are embedded using `embed_batch()` which delegates to the local **BAAI/bge-m3** model:
   - GPU-native batching via sentence-transformers
   - `vector_store.store()` upserts chunks to Qdrant with `section_id` in payload
   - `progress_callback` updates `documents.progress_percent` in DB
12. Worker persists ingestion artifact to `extra_metadata`. Sets `status=ready`.

### OCR Backend — Smart OCR Strategy

| Strategy | When used | Config |
|----------|-----------|--------|
| Fast extraction (`do_ocr=False`) | Native PDFs (copy-pasteable text), DOCX | `pipeline_pdf_fast` converter |
| OCR fallback (`do_ocr=True`) | Scanned PDFs, images (PNG/JPG) | `pipeline_pdf_ocr` converter + EasyOCR |
| Smart detection | After Pass 1: text_density < threshold → re-run with OCR | `converter_fast` + `converter_ocr` |

Two converters initialized in `_initialize_docling()`:
- **converter_fast**: PDF pipeline with `do_ocr=False`, `do_table_structure=True`
- **converter_ocr**: PDF pipeline with `do_ocr=True`, EasyOCR (`vi+en`), `do_table_structure=True`

EasyOCR models are pre-downloaded during Docker build using BuildKit cache mount. No runtime download.

### AI Refiner (Rule-Based)

**Important**: The ingestion pipeline does NOT use any AI model for text refinement. All text processing is done via rule-based heuristics.

| Parameter | Value |
|-----------|-------|
| **Type** | Rule-based (regex + pattern matching) |
| **VRAM Usage** | 0GB (no model loaded) |
| **Speed** | ~1ms per node |
| **Purpose** | Fix OCR errors, detect headers, validate hierarchy |
| **Fallback** | N/A — always available |

Rule-based refiner is **500x faster** than AI-based refiner and uses **0GB VRAM**, making ingestion lightweight and scalable.

### Embedding Model

| Parameter | Value |
|-----------|-------|
| **Model** | `BAAI/bge-m3` — state-of-the-art multilingual |
| **Dimensions** | 1024 |
| **Max tokens** | 8192 (fits entire technical document sections) |
| **Device** | GPU (auto-detected) → CPU fallback |
| **Normalization** | L2 normalize (cosine similarity) |
| **Inference** | Local / offline — no API calls, no rate limits |
| **Batch size** | 32 nodes/batch (`INGESTION_EMBEDDING_CHUNK_SIZE`) |
| **Vector size config** | `EMBEDDING_VECTOR_SIZE=1024` (used for Qdrant collection init; avoids loading model on read-only paths) |
| **Scale** | GTX 1650 (4GB): ~1.1GB VRAM · Future 24GB: larger batches, faster |

BAAI/bge-m3 is pre-downloaded during Docker build (`RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-m3')"`) using BuildKit cache mount. No runtime download.

### Why Chunked Processing

- **Progress**: Each chunk fires `progress_callback` → frontend sees `40%→50%→...→90%`.
- **Partial index**: If one chunk fails, the rest continue — partial index is better than total failure.

---

## Retrieval Pipeline (Authoritative)

### Steps — 2-Stage Retrieval

1. **Rate limit check**: Atomic Lua script in Redis — 30 req/min per user.
2. **Query embedding cache**: MD5-keyed lookup in Redis. Cache HIT → skip local model inference (TTL=1h).
3. **Query embedding**: If cache MISS, call local `BAAI/bge-m3`, cache the result.
4. **Document scope filter**: SQL query to get latest active document IDs (no `deleted_at`, `status=ready`, max version per filename).
5. **Stage 1 — Section search**: Qdrant search (top_k=50) → group results by `section_id` → pick top 3 sections (score ≥ 0.30). Load section details from PostgreSQL `document_sections` table.
6. **Stage 2 — Chunk search**: Qdrant search within top sections → prioritize chunks with matching `section_id` → score filter (≥ 0.35).
7. **Return** top sections + chunks with full text payload and citation metadata.

### Why 2-Stage Retrieval

- **Coarse → Fine**: Section search quickly narrows scope, then chunk search finds precise answers within those sections.
- **Context preservation**: Each chunk carries its section context (title, breadcrumb), giving the LLM better understanding of where information comes from.
- **Scalability**: For large documents (300+ pages), filtering by section first dramatically reduces the search space for Stage 2.

### Query Cache

```
HIT flow:  query_text → MD5 hash → Redis GET → vector (0ms, 0 API cost)
MISS flow: query_text → Gemini API → vector → Redis SET (TTL=1h) → Qdrant
```

Cache is particularly effective during demos and employee training sessions where the same questions are asked repeatedly.

### Score Threshold

| Threshold | Effect |
|-----------|--------|
| 0.35 (default) | Good balance for technical Vietnamese documents |
| Tune up (0.5+) | Stricter — fewer but more relevant chunks |
| Tune down (0.2) | More chunks — risk of noise in LLM context |
| Override via env | `RETRIEVAL_MIN_SCORE=0.35` in `.env` |

### Version and Deletion Policy

| Policy | SQL logic |
|--------|-----------|
| Latest version | `GROUP BY file_name, MAX(version)` subquery |
| Exclude deleted | `Document.deleted_at.is_(None) AND Document.status == 'ready'` |
| After hard-delete | DB row gone → query never returns that document |

---

## Storage Contract

| Store | What belongs there |
|-------|---------------------|
| Qdrant | chunk text payload, vectors, retrieval metadata (including `section_id`) |
| PostgreSQL | document status, file metadata, versions, **sections** (canonical tree order), audit, sessions |
| RustFS | original file bytes |
| Redis | Celery tasks, query embedding cache, rate limit counters |

---

## Tree Ordering Policy

Tree/list display order is derived from PostgreSQL `document_sections.order_index`, then page span. Qdrant does not define display order.

## Fallback Policy

| Failure | Behavior |
|---------|----------|
| Docling parse failure | ClassicParser fallback (text extraction only) |
| Chunk embed/store failure | Log error, skip chunk, continue with rest |
| Qdrant retrieval timeout (5s) | Return empty context, LLM answers without grounding |
| No documents in scope | Return "Chưa có tài liệu nào được index" |
| Score filter eliminates all results | Same as above — LLM answers without grounding |

---

## Implementation Mapping

| Responsibility | Module |
|----------------|--------|
| Smart OCR strategy (2-pass) | `app/adapters/parsers/docling.py:_convert_with_docling()` |
| Method D item extraction | `app/adapters/parsers/docling.py:_extract_from_docling_items()` |
| Table conversion | `app/adapters/parsers/docling.py:_table_item_to_markdown()` |
| Page number extraction | `app/adapters/parsers/docling.py:_get_page_number()` |
| Scanned PDF detection | `app/adapters/parsers/docling.py:_is_scanned()` |
| Section extraction + chunk splitting | `app/adapters/parsers/docling.py:_extract_from_docling_items()` |
| Markdown fallback path | `app/adapters/parsers/docling.py:_extract_sections_from_markdown()` |
| Parser selection and fallback | `app/services/ingestion/parser_manager.py` |
| Ingestion orchestration + section storage | `app/services/ingestion/pipeline.py` |
| Hierarchy checks | `app/services/ingestion/hierarchy_validator.py` |
| Section storage (PostgreSQL) | `app/services/storage/document_store.py:SectionRepository` |
| Parallel embedding | `app/adapters/embeddings/sentence_transformer.py:embed_batch()` |
| Vector store adapter | `app/adapters/vector_stores/qdrant.py` |
| 2-stage retrieval + score filter | `app/services/rag.py:retrieve_context()` |
| Query embedding cache | `app/services/query_cache.py` |
| Hardware auto-detection | `app/core/hardware.py` |
| Ingestion tasks | `app/workers/upload_pipeline.py` |
| Cleanup tasks + beat | `app/workers/cleanup_pipeline.py` |
