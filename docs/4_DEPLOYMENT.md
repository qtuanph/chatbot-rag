# 4 — Deployment

Tài liệu deployment bám theo `docker-compose.yml` hiện tại.

## Topology hiện tại

| Service | Vai trò |
|---|---|
| `api` | FastAPI backend |
| `workers` | Celery workers |
| `webapp` | Next.js frontend |
| `ai-proxy` | 9Router |
| `db` | PostgreSQL |
| `redis` | queue + cache |
| `rustfs` | object storage |
| `qdrant` | vector DB |
| `traefik` | reverse proxy |

## Runtime decisions

- `qdrant` giữ `latest` theo quyết định runtime hiện tại
- embedding mặc định: Docker Model Runner
- reranker mặc định: NVIDIA NIM
- local reranker chỉ là fallback

Project không còn lấy TEI local làm default runtime chính.

## Cổng và routing

| Thành phần | Ghi chú |
|---|---|
| `traefik` | public entry |
| `webapp` | nhận browser traffic |
| `/api/bep/*` | proxy từ Next.js sang backend |
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

## `settings.db`

`settings.db` là SQLite riêng của project, dùng cho:

- provider settings
- active embedding / reranker / llm metadata
- key pool của provider nếu cần

Không nhầm với dữ liệu riêng của 9Router.

## Env quan trọng

### API / proxy

- `NEXT_PUBLIC_API_URL=/api/bep`
- `API_INTERNAL_URL=http://api:8000/api/v1`

### AI

- `AI_PROXY_URL=http://ai-proxy:2908`
- `AI_PROXY_DEFAULT_MODEL`
- `AI_EMBEDDING_URL=http://model-runner.docker.internal:12434/engines/v1`
- `AI_RERANKER_URL=http://model-runner.docker.internal:12434`

### Embedding defaults

- `EMBEDDING_API_BASE=http://model-runner.docker.internal:12434/engines/v1`
- `EMBEDDING_HF_MODEL=ai/qwen3-embedding:0.6B-F16`
- `EMBEDDING_VECTOR_SIZE=1024`

### Retrieval / ingestion

- `RETRIEVAL_HISTORY_QUERY_COUNT`
- `RETRIEVAL_SECTION_HYDRATION_ENABLED`
- `RETRIEVAL_SECTION_HYDRATION_TOP_K`
- `QDRANT_SEARCH_INDEXED_ONLY`
- `INGESTION_PIPELINE_BATCH_SIZE`

## Worker model

`workers` hiện phụ trách:

- document ingestion
- usage logging
- background cleanup

Pipeline ingest:

- chạy batch theo config
- tự ensure Qdrant payload indexes
- phát progress qua SSE path của backend

## Health probes

| Probe | Ý nghĩa |
|---|---|
| `/api/v1/health` | health backend |
| `/api/v1/public/v1/health` | health public inference |

## Scale guidance

Nếu mục tiêu lên cỡ `200 CCU`, nên ưu tiên:

1. scale riêng `api`, `workers`, `ai-proxy`
2. giữ document progress trên SSE
3. tối ưu ingestion batch / concurrency
4. tách rõ chat online và ingestion background
5. benchmark lại local model runtime trước khi giữ lâu dài

## Realtime guidance

### Chat

- tiếp tục dùng SSE là hợp lý

### Ingestion progress

- hiện dùng SSE với auto-reconnect
- không quay về polling ở flow chính
