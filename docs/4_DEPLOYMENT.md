# 4 — Deployment

Tài liệu deployment bám theo `docker-compose.yml` hiện tại.

> **Lưu ý**: Webapp Next.js chạy độc lập ngoài Docker, deploy trên Cloudflare Pages tại `sse.qtuanph.dev`. Docker stack chỉ gồm backend services.

## Topology hiện tại

| Service | Vai trò |
|---|---|
| `api` | FastAPI backend |
| `workers` | Celery workers |
| `ai-proxy` | 9Router |
| `db` | PostgreSQL |
| `redis` | queue + cache |
| `rustfs` | object storage |
| `qdrant` | vector DB |
| `traefik` | reverse proxy |

## Runtime decisions

- `qdrant` pin ở `qdrant/qdrant:v1.18.2`
- `redis` pin ở `redis:8.8.0-trixie`
- `traefik` pin ở `traefik:v3.7.5`
- embedding mặc định: Docker Model Runner
- reranker mặc định: NVIDIA NIM
- local reranker chỉ là fallback

## Ports và routing

| Thành phần | Ghi chú |
|---|---|
| `traefik` | public entry (`Host('api.qtuanph.dev')` → API) |
| `/api/bep/*` | proxy từ Next.js (Cloudflare Pages) sang backend |
| `ai-proxy:2908` | 9Router nội bộ |

## Volume chính

| Volume | Mục đích |
|---|---|
| `pgdata` | PostgreSQL data |
| `redisdata` | Redis data |
| `rustfsdata` | file storage |
| `qdrantdata` | vector data |
| `hf-cache` | cache model/runtime |
| `9router-data` | dữ liệu 9Router |
| `settings-data` | `settings.db` của project |

## Env quan trọng

## Hugging Face / FastEmbed cache

- `HF_TOKEN` được nạp từ Docker secret `hf_token`
- container export thêm `HUGGING_FACE_HUB_TOKEN` để tương thích với các lib HF
- `FASTEMBED_CACHE_PATH` được trỏ vào volume `hf-cache`, không dùng `/tmp`
- worker startup prewarm `Qdrant/bm25` để giảm cold-start ingestion

### API / proxy

- `NEXT_PUBLIC_API_URL=/api/bep`
- `API_INTERNAL_URL=https://api.qtuanph.dev/v1`

### AI

- `AI_PROXY_URL=http://ai-proxy:2908`
- `AI_PROXY_DEFAULT_MODEL`
- `AI_EMBEDDING_URL=http://model-runner.docker.internal:12434/engines/v1`
- `AI_RERANKER_URL=http://model-runner.docker.internal:12434`
- `RERANKER_BACKEND=nvidia`

### Embedding defaults

- `EMBEDDING_API_BASE=http://model-runner.docker.internal:12434/engines/v1`
- `EMBEDDING_HF_MODEL=ai/qwen3-embedding:0.6B-F16`
- `EMBEDDING_VECTOR_SIZE=2048`

### Qdrant

- `QDRANT_URL`
- `QDRANT_API_KEY`
- `QDRANT_SECTION_COLLECTION=documents_sections`
- `QDRANT_CHUNK_COLLECTION=documents_chunks`

### Retrieval / ingestion

- `RETRIEVAL_HIERARCHICAL_CHUNK_SIZES`
- `RETRIEVAL_SENTENCE_WINDOW_SIZE`
- `RETRIEVAL_SECTION_TOP_K`
- `RETRIEVAL_RECURSIVE_TOP_K`
- `RETRIEVAL_CHUNK_TOP_K`
- `RETRIEVAL_AUTO_MERGE_RATIO_THRESHOLD`
- `RETRIEVAL_ROUTE_SECTION_MAX_CHARS`
- `RETRIEVAL_ROUTE_SECTION_MAX_TERMS`
- `RETRIEVAL_SECTION_HYDRATION_ENABLED`
- `RETRIEVAL_SECTION_HYDRATION_TOP_K`
- `RETRIEVAL_RERANK_SKIP_ENABLED`
- `RETRIEVAL_RERANK_SKIP_QUERY_MAX_CHARS`
- `RETRIEVAL_RERANK_SKIP_QUERY_MAX_TERMS`
- `RETRIEVAL_RERANK_SKIP_DOMINANCE_RATIO`
- `QDRANT_SEARCH_INDEXED_ONLY`
- `INGESTION_PIPELINE_BATCH_SIZE`

## Worker model

`workers` phụ trách:

- document ingestion
- usage logging
- background cleanup

Pipeline ingest:

- parse -> canonical sections
- build section index
- build chunk index
- phát progress qua SSE path của backend

## Health probes

| Probe | Ý nghĩa |
|---|---|
| `/v1/health` | health backend & public inference |

## Realtime guidance

### Chat

- tiếp tục dùng SSE

### Ingestion progress

- dùng SSE với auto-reconnect
- không quay về polling ở flow chính
