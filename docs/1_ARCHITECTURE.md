# 1 — Architecture

Tài liệu nguồn chuẩn cho kiến trúc hiện tại của project. Nếu code và tài liệu lệch nhau, **code hiện tại là nguồn sự thật**, rồi phải sửa tài liệu theo code.

## Mục tiêu hệ thống

Project hiện tại là một nền tảng **multi-tenant SaaS RAG**:

- `platform_admin` quản trị toàn bộ nền tảng
- `tenant_admin` chỉ thao tác trong tenant của mình
- tài liệu, quota, usage, API key, instruction đều tách theo `tenant_id`
- chat nội bộ và public API đều **stateless**
- transcript chat **không lưu bền** trong database

## Kiến trúc tổng thể

```text
Browser
  -> Next.js webapp
  -> /api/bep/*
  -> FastAPI (/api/v1/*)
  -> Service
  -> Repository
  -> PostgreSQL / Qdrant / Redis / RustFS
  -> AI providers (9Router, Docker Model Runner, NVIDIA NIM, ...)
```

## Tech stack

| Thành phần | Công nghệ hiện tại |
|---|---|
| Frontend | Next.js 16 + shadcn/ui + next-auth |
| Backend | FastAPI async |
| Worker | Celery |
| Database | PostgreSQL |
| Vector DB | Qdrant |
| Cache / Queue | Redis |
| Object storage | RustFS (S3-compatible) |
| LLM | 9Router |
| Embedding mặc định | Docker Model Runner `ai/qwen3-embedding:0.6B-F16` |
| Reranker mặc định | NVIDIA NIM, có local Docker Model Runner fallback |

## Phân tầng bắt buộc

```text
Route -> Service -> Repository
```

### Rule

- Route chỉ xử lý HTTP, auth, parse request, format response
- Service giữ business logic
- Repository giữ truy cập dữ liệu
- Route không được query DB trực tiếp
- Service không được ném `HTTPException` trực tiếp

## Mô hình multi-tenant

### Role

| Role | Phạm vi |
|---|---|
| `platform_admin` | Toàn hệ thống |
| `tenant_admin` | Đúng tenant của mình |

### Tenant-scoped data

Các vùng dữ liệu chính đã/đang đi theo `tenant_id`:

- `tenants`
- `tenant_settings`
- `tenant_api_keys`
- `users.tenant_id`
- `documents.tenant_id`
- `document_sections.tenant_id`
- `ai_model_usage.tenant_id`

## Auth model

### Nội bộ webapp

- JWT qua next-auth
- browser không giữ backend bearer token
- mọi business request từ browser phải đi qua `/api/bep/*`

### Public integration

- dùng `Authorization: Bearer <tenant_api_key>`
- backend resolve `tenant_id` từ API key
- chỉ lưu `hash`, không lưu raw key

## Chat model

Chat hiện tại là **stateless chat**:

- không còn `chat_sessions` / `chat_messages` là luồng sản phẩm chính
- frontend chỉ giữ một cửa sổ message ngắn trong memory
- đóng chat hoặc refresh là mất transcript
- backend chỉ nhận `messages` gần nhất rồi trả kết quả

## Ingestion model

Luồng ingest hiện tại:

1. upload file
2. lưu metadata document
3. enqueue Celery task
4. parse nội dung
5. tách section
6. embed + ghi vector vào Qdrant
7. finalize trạng thái document

### Điểm quan trọng

- worker ingest chạy tuần tự ở `node-ingestion`
- pipeline hiện đang đẩy vào `run_ingestion_pipeline()` với `batch_size = 1`
- điều này làm ingest ổn định hơn nhưng **chậm hơn**

## Dữ liệu và storage

| Store | Vai trò |
|---|---|
| PostgreSQL | metadata, auth, tenant, usage, sections |
| Qdrant | dense vectors + sparse hybrid payload |
| Redis | queue, cache, rate limit, audit stream |
| RustFS | file gốc, artifact OCR/markdown |

## AI provider boundary

Project không cho route gọi provider SDK trực tiếp.

### Quy tắc

- chat nội bộ đi qua `PublicInferenceService`
- public API OpenAI-compatible đi qua `app/modules/inference`
- provider active được quản lý trong `settings.db`

## Provider runtime hiện tại

### Embedding

- mặc định: Docker Model Runner
- endpoint mặc định: `http://model-runner.docker.internal:12434/engines/v1`
- model mặc định: `ai/qwen3-embedding:0.6B-F16`
- vector size mặc định: `1024`

### Reranker

- mặc định: NVIDIA NIM
- local fallback: Docker Model Runner `ai/qwen3-reranker:0.6B`

### LLM

- mặc định: 9Router
- public shape: OpenAI-compatible

## Realtime hiện tại

Project **chưa dùng realtime progress thật** cho ingestion ở webapp.

Hiện trạng:

- backend có cập nhật tiến độ document
- frontend trang tài liệu đang **poll mỗi 4 giây**
- tức là đã “gần realtime”, nhưng **chưa phải SSE/WebSocket progress**

## Hard delete

Thứ tự cứng:

1. đánh dấu delete trong registry
2. xóa vector
3. xóa sections
4. xóa file storage
5. xóa DB row
6. purge registry

Không được đổi thứ tự này.

## Tiền tệ và thời gian

### Tiền tệ

- currency chuẩn hiện tại: `VND`
- tiền được lưu bằng integer: `cost_micros_vnd`
- không lưu tiền bằng float

### Thời gian

- DB lưu UTC
- backend/frontend format sang giờ Việt Nam khi hiển thị

## Những thứ đã bỏ

Không còn coi là core flow:

- persisted chat history
- chat session sidebar kiểu cũ
- analytics theo `chat_sessions`
- ownership chính theo `user_id`

## Ghi chú vận hành

- nếu ingest chậm, nguyên nhân lớn nhất hiện tại thường là:
  - worker ingest chạy `solo`
  - embed batch đang là `1` ở pipeline
  - provider embedding là Docker Model Runner local
- nếu muốn realtime mượt hơn ở webapp, cần nâng từ polling sang push progress thực sự
