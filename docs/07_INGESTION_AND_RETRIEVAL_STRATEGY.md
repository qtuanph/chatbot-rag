# 07 — Ingestion and Retrieval Strategy

Status: authoritative strategy — updated to reflect EasyOCR, BAAI/bge-m3 local embedding, query cache, and score filtering.

## Primary Principle

Use Qdrant for retrieval data path. Keep PostgreSQL as system metadata/state database. Redis for cache and queue only. No full-text scan of PostgreSQL as retrieval path.

---

## Ingestion Pipeline (Authoritative)

### Steps

1. Client uploads file → API saves to RustFS → inserts `documents` row (`status=pending`).
2. API enqueues `parse_document_task` to Redis queue `ingestion`.
3. Worker downloads file bytes from RustFS.
4. **Docling** converts file to Markdown. For scanned/image PDFs and image files: **EasyOCR** (`lang=["vi","en"]`) performs OCR — mandatory, not optional.
5. **LlamaIndex MarkdownNodeParser** builds hierarchical nodes (section → subsection → paragraph).
6. **HierarchyValidator** checks parent-child consistency.
7. Sequential chunks of **32 nodes** are embedded using `embed_batch()` which delegates to the local **BAAI/bge-m3** model:
   - GPU-native batching via sentence-transformers (no ThreadPoolExecutor needed — GPU handles parallelism internally)
   - `vector_store.store()` upserts the chunk to Qdrant
   - `progress_callback` updates `documents.progress_percent` in DB
8. Worker persists ingestion artifact to `extra_metadata`. Sets `status=ready`.

### OCR Backend

| Backend | When used | Config |
|---------|-----------|--------|
| EasyOCR | Always (mandatory) | `lang=["vi","en"]`, `use_gpu=hardware.gpu_count > 0` |
| Tesseract | **Not used** | Removed — EasyOCR is the only supported backend |

EasyOCR models are pre-downloaded during Docker build using BuildKit cache mount. No runtime download.

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
| **Scale** | GTX 1650 (4GB): ~1.1GB VRAM · Future 24GB: larger batches, faster |

BAAI/bge-m3 is pre-downloaded during Docker build (`RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-m3')"`) using BuildKit cache mount. No runtime download.

### Why Chunked Processing

- **Progress**: Each chunk fires `progress_callback` → frontend sees `40%→50%→...→90%`.
- **Partial index**: If one chunk fails, the rest continue — partial index is better than total failure.

---

## Retrieval Pipeline (Authoritative)

### Steps

1. **Rate limit check**: Atomic Lua script in Redis — 30 req/min per user.
2. **Query embedding cache**: MD5-keyed lookup in Redis. Cache HIT → skip local model inference (TTL=1h).
3. **Query embedding**: If cache MISS, call `embedding.embed(query, task_type=RETRIEVAL_QUERY)`, cache the result.
4. **Document scope filter**: SQL query to get latest active document IDs (no `deleted_at`, `status=ready`, max version per filename).
5. **Qdrant search**: `top_k = max(limit * 2, 10)` — retrieve extra candidates for score filtering.
6. **Score filter**: Drop nodes with `cosine_similarity < settings.retrieval_min_score` (default: **0.35**).
7. **Return top-5** after filter with full text payload and citation metadata.

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
| Qdrant | node text payload, vectors, retrieval metadata |
| PostgreSQL | document status, file metadata, versions, audit, sessions |
| RustFS | original file bytes |
| Redis | Celery tasks, query embedding cache, rate limit counters |

---

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
| OCR backend selection | `app/adapters/parsers/docling.py:_select_ocr_backend()` |
| Parser selection and fallback | `app/services/ingestion/parser_manager.py` |
| Ingestion orchestration + chunked embed | `app/services/ingestion/pipeline.py` |
| Hierarchy checks | `app/services/ingestion/hierarchy_validator.py` |
| Parallel embedding | `app/adapters/embeddings/gemini.py:embed_batch()` |
| Vector store adapter | `app/adapters/vector_stores/qdrant.py` |
| Retrieval + score filter | `app/services/rag.py:retrieve_context()` |
| Query embedding cache | `app/services/query_cache.py` |
| Hardware auto-detection | `app/core/hardware.py` |
