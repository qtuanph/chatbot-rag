# 1 — Architecture

Tài liệu này mô tả kiến trúc hiện tại của `chatbot-rag` sau đợt refactor multi-tenant + stateless chat.

## Tổng quan

Project gồm 3 lớp chính:

```text
Browser -> Next.js webapp -> /api/bep/* proxy -> FastAPI backend
                                      |
                                      +-> NextAuth session/JWT
```

Backend đi theo CSR:

```text
Route (HTTP only) -> Service (business logic) -> Repository (data access)
```

## Domain chính

### Tenant model

- `platform_admin` quản trị toàn hệ thống
- `tenant_admin` chỉ thao tác trong tenant của mình
- mọi dữ liệu tenant-scoped phải đi cùng `tenant_id`

### Chat model

Chat hiện tại là **stateless**:

- không còn `chat_sessions` / `chat_messages`
- frontend chỉ giữ transcript trong memory của tab hiện tại
- đóng chat hoặc refresh là mất transcript
- backend chỉ nhận `messages` gần nhất, rồi tự inject instruction + RAG context

### Feedback model

Feedback chat được lưu riêng trong `chat_feedback`:

- `feedback_type`: `like` / `dislike`
- `query_text`
- `assistant_answer`
- `citations`
- runtime metadata (`llm_model`, `embedding_model`, `reranker_model`)

Feedback không phụ thuộc persisted transcript.

## Storage

| Store | Vai trò |
|---|---|
| PostgreSQL | auth, tenant, documents, sections, usage, feedback |
| Qdrant | vector store + hybrid retrieval payload |
| Redis | queue, cache, rate limit, audit stream |
| RustFS | file gốc và artifact ingest |
| SQLite `settings.db` | provider settings và runtime selection |

## AI provider boundary

- LLM chính đi qua `9Router`
- Embedding local mặc định đi qua Docker Model Runner
- Reranker mặc định là NVIDIA NIM
- local reranker chỉ là fallback, không phải happy path mặc định

Route layer không được gọi provider SDK trực tiếp.

## Retrieval architecture

Retrieval hiện tại gồm:

1. chuẩn hóa query từ các user message gần nhất
2. embed query
3. hybrid retrieve trong Qdrant
4. filter nghiêm ngặt theo `tenant_id`
5. hydrate full section từ PostgreSQL cho top node
6. rerank top-k
7. assemble context và gọi LLM

### Qdrant payload

Payload chuẩn hiện tại có:

- `tenant_id`
- `document_id`
- `section_id`

Collection bootstrap và retrieval path đều tự ensure payload index cho các field này.

## Ingestion architecture

Luồng ingest:

```text
Upload -> persist document row -> enqueue Celery task -> parse -> sectionize -> embed -> Qdrant -> finalize
```

Điểm quan trọng:

- ingest chạy nền qua `workers`
- batch ingest là config-driven
- pipeline tự ensure collection + payload indexes trước khi ghi
- progress tài liệu dùng SSE, không dùng polling làm đường chính nữa

## Auth boundary

### Internal webapp

- browser gọi business API qua `/api/bep/*`
- Next.js route handler lấy token từ NextAuth
- backend bearer token không lộ ra browser

### Public API

- dùng `Authorization: Bearer <tenant_api_key>`
- backend tự resolve tenant từ API key
- raw key chỉ hiển thị đúng một lần lúc tạo

## Money và time

### Money

- tiền chuẩn là `VND`
- lưu dưới dạng integer `cost_micros_vnd`
- không dùng float để tính phí

### Time

- DB lưu UTC
- backend/frontend format sang `Asia/Ho_Chi_Minh` khi hiển thị

## Hard delete order

Thứ tự xóa cứng bắt buộc:

1. `registry.delete()`
2. xóa vector
3. xóa sections
4. xóa file storage
5. xóa DB row
6. purge registry

Không được đảo thứ tự này.

## Những gì đã bỏ hẳn

- persisted chat history
- session sidebar kiểu cũ
- analytics dựa trên `chat_sessions`
- `user_memories` và memories CRUD
- boundary ownership kiểu cũ lấy `user_id` làm chính

## Runtime shape hiện tại

- `api` — FastAPI
- `workers` — Celery
- `webapp` — Next.js
- `postgres`
- `redis`
- `qdrant`
- `rustfs`
- `ai-proxy` — 9Router
- `traefik`
