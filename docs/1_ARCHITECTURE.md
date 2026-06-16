# 1 — Architecture

Tài liệu này mô tả kiến trúc hiện tại của `chatbot-rag` sau đợt rebuild RAG theo hướng structure-aware, multi-tenant, stateless chat.

## Tổng quan

```text
Browser -> Next.js webapp -> /api/bep/* proxy -> FastAPI backend
                                      |
                                      +-> NextAuth session/JWT
```

Backend tuân theo CSR:

```text
Route (HTTP only) -> Service (business logic) -> Repository (data access)
```

## Domain chính

### Tenant model

- `platform_admin` quản trị toàn hệ thống
- `tenant_admin` chỉ thao tác trong tenant của mình
- mọi dữ liệu tenant-scoped phải luôn đi cùng `tenant_id`

### Chat model

Chat hiện tại là **stateless**:

- không còn `chat_sessions` / `chat_messages`
- transcript chỉ sống trong memory của tab frontend
- refresh/đóng tab là mất transcript
- backend chỉ nhận recent `messages`, rồi tự inject instruction + RAG context

### Feedback model

Feedback chat được lưu riêng trong `chat_feedback`:

- `feedback_type`: `like` / `dislike`
- `query_text`
- `assistant_answer`
- `citations`
- `llm_model`, `embedding_model`, `reranker_model`

Feedback không phụ thuộc persisted transcript.

## Storage

| Store | Vai trò |
|---|---|
| PostgreSQL | auth, tenant, documents, canonical sections, usage, feedback |
| Qdrant | dual index cho retrieval |
| Redis | queue, cache, rate limit, audit stream |
| RustFS | file gốc và artifact ingest |
| SQLite `settings.db` | provider settings và runtime selection |

## AI provider boundary

- LLM chính đi qua `9Router`
- Embedding local mặc định đi qua Docker Model Runner
- Reranker mặc định là NVIDIA NIM
- local reranker chỉ là fallback

Route layer không được gọi SDK/provider trực tiếp.

## Canonical section graph

Sau khi parse, tài liệu được normalize thành `document_sections` trong PostgreSQL với các field chính:

- `document_id`
- `section_id`
- `parent_section_id`
- `section_code`
- `title`
- `breadcrumb`
- `breadcrumb_text`
- `level`
- `order_index`
- `content`

Đây là source of truth cho cấu trúc tài liệu.

## Retrieval architecture

Retrieval hiện tại là **dual index + structure-aware**:

1. canonical section graph được lưu trong PostgreSQL
2. build **section index** trong Qdrant cho heading / numbered section retrieval
3. build **chunk index** trong Qdrant cho sentence-window evidence retrieval
4. filter nghiêm ngặt theo `tenant_id`
5. route truy vấn:
   - section route cho numbered / heading-style query
   - semantic route cho free-form query
6. dùng `RecursiveRetriever` để mở rộng section -> chunk theo `section_id`
7. dùng `AutoMergingRetriever` để gộp nhiều chunk về parent section khi đủ tỷ lệ
8. thay sentence hit bằng local window context trước khi synthesis
9. rerank sau khi candidate đã được làm sạch theo cấu trúc
10. hydrate full section từ PostgreSQL cho top node nếu cần

### Qdrant collections

- `documents_sections`
- `documents_chunks`

### Qdrant payload

Payload chuẩn:

- `tenant_id`
- `document_id`
- `section_id`
- `section_code`
- `parent_section_id`
- `document_title`
- `heading`
- `breadcrumb_text`
- `level`
- `order_index`
- `node_kind`

## Ingestion architecture

```text
Upload -> persist document row -> enqueue Celery task
-> parse -> canonical section graph -> dual index Qdrant -> finalize
```

Điểm quan trọng:

- ingest chạy nền qua `workers`
- pipeline tự ensure 2 collection + payload indexes trước khi ghi
- `document_sections` trong PostgreSQL là source of truth
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

1. xóa vectors
2. xóa sections
3. xóa file storage
4. xóa DB row

Không được đảo thứ tự này.

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
