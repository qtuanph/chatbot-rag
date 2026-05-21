# Future Development: BGE-M3 + GTE Reranker

**Created**: 2026-05-21
**Status**: Planned — not yet implemented
**Current stack**: `gte-multilingual-base` (768-dim dense) + `VietnameseBM25Encoder` + `gte-multilingual-reranker-base`

---

## Target Models

| Task | Model | Params | Dim | License |
|------|-------|--------|-----|---------|
| **Embedding** | `BAAI/bge-m3` | 379M (0.568B) | 1024 (dense) | Apache 2.0 |
| **Reranker** | `Alibaba-NLP/gte-multilingual-reranker-base` | 304M | cross-encoder | Apache 2.0 |

---

## BGE-M3: 3-in-1 Output (Single Forward Pass)

BGE-M3 sinh ra **3 loại embedding cùng lúc** trong 1 lần inference:

| Output | Type | Dimension | Purpose |
|--------|------|-----------|---------|
| `dense_vecs` | Dense vector | 1024 | Semantic search (cosine similarity) |
| `lexical_weights` | Sparse vector | 250,002 (vocab size) | BM25-like keyword matching |
| `colbert_vecs` | Multi-vector | [seq_len, 1024] | Fine-grained ColBERT late interaction |

### Advantage over current pipeline

| Current | BGE-M3 |
|---------|--------|
| 2 steps: embed (TEI) + BM25 encode (Underthesea) | 1 step: TEI returns all 3 outputs |
| ~200-300ms total | ~150-200ms total |
| Vietnamese BM25 tokenizer tốt cho tiếng Việt | BGE-M3 sparse tốt cho 100+ languages |

---

## Hardware Requirements (200 CCU)

### Minimum GPU (chạy được cả 2 model cùng lúc)

| Component | Spec | Notes |
|-----------|------|-------|
| **GPU** | RTX 3060 12GB | Minimum for both models at fp16 + batch |
| **VRAM usage** | ~4-6GB total | See breakdown below |
| **RAM** | 32GB | Qdrant + Redis + PostgreSQL + API |
| **CPU** | 6 cores+ | OCR, parsing, BM25 fallback |
| **Storage** | NVMe SSD | Qdrant index I/O |

### VRAM Breakdown (fp16, inference)

| Model | Model Size | Batch Buffer | Total VRAM |
|-------|-----------|--------------|------------|
| BGE-M3 (embedding) | ~1.1 GB | +0.5 GB (batch 32) | ~1.6 GB |
| gte-multilingual-reranker-base | ~0.6 GB | +0.8 GB (batch 16) | ~1.4 GB |
| CUDA context + overhead | — | — | ~1.0 GB |
| **Total** | | | **~4.0 GB** |

→ **GTX 1650 4GB borderline** — có thể chạy được nhưng batch phải nhỏ (8-16), concurrent requests thấp.
→ **RTX 3060 12GB recommended** — thoải mái batch lớn, 200 CCU mượt.

### Recommended GPU Tiers

| Tier | GPU | VRAM | Max Concurrent (embed) | Max Concurrent (rerank) | Est. Cost |
|------|-----|------|------------------------|------------------------|-----------|
| Budget | GTX 1650 | 4GB | 8 | 4 | Đang có |
| Sweet spot | RTX 3060 | 12GB | 64 | 32 | ~$300 |
| Production | RTX 4060 Ti | 16GB | 128 | 64 | ~$450 |
| Enterprise | A6000 / L40 | 48GB | 256+ | 128+ | ~$5000+ |

---

## TEI Configuration (Optimized for 200 CCU)

### ai-embedding (BGE-M3)

```yaml
image: ghcr.io/huggingface/text-embeddings-inference:turing-1.9
command: >
  --model-id BAAI/bge-m3
  --dtype float16
  --auto-truncate true
  --pooling cls
environment:
  MAX_CONCURRENT_REQUESTS: 64
  MAX_BATCH_TOKENS: 32768
  MAX_BATCH_REQUESTS: 32
  MAX_CLIENT_BATCH_SIZE: 32
```

### ai-reranker (gte-multilingual-reranker-base)

```yaml
image: ghcr.io/huggingface/text-embeddings-inference:turing-1.9
command: >
  --model-id Alibaba-NLP/gte-multilingual-reranker-base
  --dtype float16
environment:
  MAX_CONCURRENT_REQUESTS: 32
  MAX_BATCH_TOKENS: 16384
  MAX_BATCH_REQUESTS: 16
```

---

## Estimated Latency (RTX 3060 12GB)

| Stage | Current (GTX 1650) | Target (RTX 3060) |
|-------|-------------------|-------------------|
| Embedding (batch 32) | ~200-500ms | ~50-100ms |
| Reranker (15 docs) | ~2-4s (local) / ~1s (NVIDIA API) | ~200-500ms |
| **Total retrieval** | ~3-5s | **~0.5-1s** |

---

## Migration Steps (Khi implement)

### Phase 1: Embedding swap (BGE-M3 dense only)
1. Đổi `embedding_hf_model` → `BAAI/bge-m3`
2. Đổi `embedding_vector_size` → `1024`
3. Update TEI command: thêm `--pooling cls`
4. **Re-ingest toàn bộ documents** (không cách nào tránh)
5. Flush Redis semantic cache
6. Giữ nguyên VietnameseBM25Encoder (sparse hiện tại)

### Phase 2: BGE-M3 sparse replace BM25
1. Update TEI adapter parse sparse output từ BGE-M3
2. Replace `VietnameseBM25Encoder` với BGE-M3 sparse vectors
3. Update Qdrant sparse vector config
4. Test accuracy so với BM25 hiện tại

### Phase 3: Multi-vector (ColBERT) — optional
1. Add `colbert` named vector to Qdrant collection
2. Update retrieval service: ColBERT late interaction scoring
3. Hybrid score: `w1*dense + w2*sparse + w3*colbert`
4. Only worth it nếu document dài > 500 tokens

---

## Code Changes Required

| File | Change |
|------|--------|
| `app/core/config.py` | `embedding_hf_model`, `embedding_vector_size` |
| `app/adapters/embeddings/tei_embedding.py` | Parse BGE-M3 multi-output response |
| `app/adapters/vector_stores/qdrant.py` | Vector size 768→1024, sparse config |
| `app/utils/cache/semantic_cache.py` | `vector_dim` 768→1024 |
| `app/modules/documents/ingestion/ingestion_service.py` | Embed batch handles 3 outputs |
| `docker-compose.yml` | TEI command + env vars |
| `.env` | Model overrides |

---

## Env Config (Future)

```env
# Embedding
EMBEDDING_HF_MODEL=BAAI/bge-m3
EMBEDDING_VECTOR_SIZE=1024

# Reranker (giữ nguyên)
AI_RERANKER_URL=http://ai-reranker:80
RETRIEVAL_RERANK_MODEL=Alibaba-NLP/gte-multilingual-reranker-base
```

---

## References

- BGE-M3: https://huggingface.co/BAAI/bge-m3
- GTE Reranker: https://huggingface.co/Alibaba-NLP/gte-multilingual-reranker-base
- TEI docs: https://github.com/huggingface/text-embeddings-inference
- BGE-M3 tutorial: https://bge-model.com/tutorial/1_Embedding/1.2.4.html
