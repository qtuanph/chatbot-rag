# chatbot-rag

Nền tảng RAG chatbot multi-tenant theo hướng SaaS, tự host, đóng vai trò **cầu nối** để tích hợp chatbot vào phần mềm của từng công ty qua API kiểu OpenAI-compatible.

## Mục tiêu hiện tại

- `platform_admin` quản trị toàn bộ tenant
- mỗi `tenant` có:
  - tài liệu riêng
  - quota / usage riêng
  - instruction riêng
  - API key riêng
- chat **stateless**
  - không lưu lịch sử chat lâu dài
  - frontend chỉ giữ context ngắn khi cửa sổ chat còn mở
- public integration đi qua:
  - `POST /api/v1/public/v1/chat/completions`

## Stack chính

- **Frontend**: Next.js + shadcn/ui
- **Backend**: FastAPI + Celery
- **Vector DB**: Qdrant
- **Database**: PostgreSQL
- **Cache / Queue**: Redis
- **Object Storage**: RustFS
- **LLM Gateway**: 9Router
- **Embedding local mặc định**: Docker Model Runner
- **Reranker mặc định**: NVIDIA NIM

## Kiến trúc ngắn gọn

```text
Browser
  → /api/bep/*
  → Next.js route handler
  → FastAPI
  → Service / Repository / Qdrant / Postgres / Redis
  → 9Router / Embedding / Reranker
```

Các nguyên tắc quan trọng:
- browser không cầm backend bearer token
- mọi tenant-scoped data phải filter bằng `tenant_id`
- chat stateless, không quay lại persisted sessions cũ
- route không chứa business logic

## Vai trò người dùng

### `platform_admin`
- tạo tenant
- tạo tenant admin
- tạo / revoke API key cho tenant
- upload / retry / rechunk / xóa tài liệu cho tenant
- chat thử theo tenant
- xem usage / quota toàn hệ thống hoặc theo tenant

### `tenant_admin`
- xem tài liệu của tenant mình
- chat thử nội bộ tenant mình
- xem usage / quota tenant mình
- sửa instruction / welcome / display name tenant mình
- **không** thấy API key
- **không** quản lý ingestion

## API tích hợp cho tenant

Tenant software chỉ cần vài thứ cơ bản:

- `base_url`
- `api_key`
- `model`
- `messages`

Ví dụ:

```http
POST /api/v1/public/v1/chat/completions
Authorization: Bearer <tenant_api_key>
Content-Type: application/json
```

```json
{
  "model": "chatbot-rag",
  "messages": [
    { "role": "user", "content": "Hướng dẫn tạo phiếu nhập kho?" }
  ],
  "stream": true,
  "temperature": 0.2,
  "max_tokens": 1024
}
```

Xem chi tiết tại `docs/8_TENANT_INTEGRATION_GUIDE.md`.

## Quick Start

```bash
cp .env.example .env
DOCKER_BUILDKIT=1 docker compose build
docker compose up -d
```

Truy cập:

- Webapp: `http://localhost`
- API health: `http://localhost/api/v1/health`
- Qdrant: `http://localhost:6333/dashboard`
- 9Router: `http://localhost:2908`

## Tài liệu cần đọc

| Nội dung | File |
|---------|------|
| Guardrails cho agent/dev | `AGENTS.md` |
| Kiến trúc | `docs/1_ARCHITECTURE.md` |
| Workflows | `docs/2_WORKFLOWS.json` |
| API contracts | `docs/3_API_CONTRACTS.md` |
| Deployment | `docs/4_DEPLOYMENT.md` |
| Current settings | `docs/7_CURRENT_SETTINGS.json` |
| Tích hợp tenant | `docs/8_TENANT_INTEGRATION_GUIDE.md` |

## Trạng thái hiện tại

- multi-tenant SaaS backend: **đã có**
- stateless chat: **đã có**
- OpenAI-compatible public chat API: **đã có**
- tenant instruction riêng: **đã có**
- tenant API key management: **đã có**
- Docker Model Runner embedding default: **đã có**
- NVIDIA NIM reranker default: **đã có**

## Ghi chú hiệu năng thực tế

- Chat nhiều người dùng được, nhưng mức chịu tải thực tế còn phụ thuộc:
  - provider LLM
  - tốc độ embedding / reranking
  - Redis / Postgres / Qdrant
  - cấu hình worker
- Ingestion hiện vẫn thiên về ổn định hơn là throughput tối đa
- Nếu mục tiêu khoảng `200 CCU`, nên ưu tiên:
  - SSE cho stream chat
  - SSE cho progress ingestion
  - scale worker / API / proxy tách riêng
  - dùng provider inference đủ mạnh thay vì dồn hết sang local GPU nhỏ

## Contributing

1. Đọc `AGENTS.md`
2. Giữ đúng CSR:
   - Route → Service → Repository
3. Không hardcode để “pass bug”
4. Sync docs cùng lúc với code

## License

`AGPL-3.0`
