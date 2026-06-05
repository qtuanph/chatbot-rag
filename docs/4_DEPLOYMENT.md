# 4 — Deployment

Tài liệu deployment ở mức thực dụng, bám `docker-compose.yml` hiện tại.

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

## Điểm khác so với bản cũ

Deployment hiện tại **không còn dựa vào TEI container local như mặc định chính**.

### Mặc định hiện tại

- embedding mặc định: Docker Model Runner qua `model-runner.docker.internal`
- reranker mặc định: NVIDIA NIM
- local reranker Docker Model Runner chỉ là fallback

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

## settings.db

`settings.db` là SQLite riêng của project, dùng cho:

- provider settings
- active embedding / reranker / llm metadata
- key pool của provider nếu cần

Không nhầm với SQLite/data riêng của 9Router.

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

## Worker model

### `workers`

Một container workers hiện chạy theo hướng:

- ingest là đường nặng nhất
- ingestion thực tế vẫn tuần tự/thiên về an toàn
- phần này là một trong các nguyên nhân làm embedding chậm

## Health

| Probe | Ý nghĩa |
|---|---|
| `/api/v1/health` | health backend |
| `/api/v1/public/v1/health` | health public inference |

## Gợi ý scale cho tương lai

Nếu mục tiêu lên khoảng `200 CCU`, cần ưu tiên:

1. scale API / worker / proxy riêng
2. giữ progress document trên SSE
3. tối ưu ingestion batch / concurrency cẩn thận
4. tách rõ đường chat online và ingestion background
5. benchmark lại Docker Model Runner local trước khi giữ lâu dài

## Gợi ý realtime

### Chat

- tiếp tục dùng SSE là hợp lý

### Ingestion progress

- hiện dùng SSE với auto-reconnect
- không quay về polling ở flow chính

### Khi nào mới cần WebSocket

- khi thật sự cần hai chiều
- ví dụ collaborative control, cancel/reprioritize tasks trực tiếp, nhiều tín hiệu song song

Nếu chỉ server -> client để báo tiến độ, **SSE là lựa chọn hợp lý hơn**.
