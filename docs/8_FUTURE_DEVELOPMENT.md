# Future Development: BGE-M3 Upgrade

**Created**: 2026-05-21
**Updated**: 2026-05-22
**Status**: Planned — not yet implemented
**Current stack**: `gte-multilingual-base` (768-dim dense) + Qdrant native BM25 + TEI reranker

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
| 2 services: ai-embedding + Qdrant native BM25 | 1 service: TEI returns all 3 outputs |
| BM25 is Qdrant-managed, limited control | BGE-M3 sparse works for 100+ languages |
| ~150-300ms total | ~150-200ms total |

---

## TEI Configuration (Target)

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

### ai-reranker (gte-multilingual-reranker-base, giữ nguyên)

```yaml
image: ghcr.io/huggingface/text-embeddings-inference:turing-1.9
command: >
  --model-id Alibaba-NLP/gte-multilingual-reranker-base
  --dtype float16
```

---

## Migration Steps (Khi implement)

### Phase 1: Embedding swap (BGE-M3 dense only)
1. Đổi `EMBEDDING_HF_MODEL` → `BAAI/bge-m3`
2. Đổi `EMBEDDING_VECTOR_SIZE` → `1024`
3. Update TEI command: thêm `--pooling cls`
4. **Re-ingest toàn bộ documents**
5. Flush Redis semantic cache
6. Update `TextEmbeddingsInference` trong `app/core/llama_index.py` nếu cần

### Phase 2: BGE-M3 sparse replace Qdrant native BM25
1. Cấu hình Qdrant collection thêm sparse vector config
2. Update `IngestionPipeline` để parse và lưu BGE-M3 sparse vectors
3. Update `VectorStoreIndex` để dùng hybrid search với sparse vectors mới
4. So sánh accuracy với Qdrant native BM25 hiện tại

### Phase 3: Multi-vector (ColBERT) — optional
1. Add `colbert` named vector to Qdrant collection
2. Custom reranking với ColBERT late interaction scoring
3. Chỉ worth it nếu document dài > 500 tokens

---

## Hardware Requirements (200 CCU)

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| **GPU** | RTX 3060 12GB | RTX 4060 Ti 16GB |
| **VRAM usage** | ~4-6GB | ~8-10GB |
| **RAM** | 32GB | 64GB |
| **CPU** | 6 cores+ | 8 cores+ |

---

## References

- BGE-M3: https://huggingface.co/BAAI/bge-m3
- GTE Reranker: https://huggingface.co/Alibaba-NLP/gte-multilingual-reranker-base
- TEI docs: https://github.com/huggingface/text-embeddings-inference
