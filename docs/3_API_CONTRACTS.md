# 3 — API Contracts

Tài liệu route-level bám theo backend hiện tại.

## Quy tắc bảo mật quan trọng

### Browser -> backend

Browser **không** gọi FastAPI trực tiếp.

Luồng chuẩn:

```text
Browser -> /api/bep/* -> Next.js route handler -> backend /v1/*
```

### Token rule

- backend bearer token không lộ ra browser
- `/api/auth/*` là route nội bộ NextAuth, không tính là bypass business API

## Prefix

Base API hiện tại:

`/v1`

## Nhóm route chính

### Auth

| Method | Path |
|---|---|
| POST | `/auth/login` |
| POST | `/auth/logout` |
| GET | `/auth/roles` |
| GET | `/auth/me` |
| GET | `/auth/users` |
| POST | `/auth/users` |
| DELETE | `/auth/users/{username}` |

### Documents

| Method | Path |
|---|---|
| POST | `/upload` |
| GET | `/status/{task_id}` |
| GET | `/documents/stream` |
| GET | `/documents` |
| GET | `/documents/{document_id}` |
| GET | `/documents/{document_id}/access` |
| PUT | `/documents/{document_id}/access` |
| DELETE | `/documents/{document_id}` |
| POST | `/documents/{document_id}/retry` |
| POST | `/documents/{document_id}/rechunk` |
| GET | `/tree/{document_id}` |
| GET | `/tree/{document_id}/nodes/{node_id}` |
| GET | `/tree/{document_id}/search` |

### Internal chat

| Method | Path |
|---|---|
| POST | `/chat/feedback` |

### Analytics

| Method | Path |
|---|---|
| GET | `/analytics/stats` |
| DELETE | `/analytics/stats` |
| GET | `/analytics/me/usage` |

### Settings / AI providers

| Method | Path |
|---|---|
| GET | `/settings/templates` |
| GET | `/settings/providers` |
| POST | `/settings/providers` |
| GET | `/settings/providers/{provider_id}` |
| PUT | `/settings/providers/{provider_id}` |
| DELETE | `/settings/providers/{provider_id}` |
| POST | `/settings/providers/{provider_id}/activate` |
| POST | `/settings/providers/{provider_id}/test` |
| GET | `/settings/providers/{provider_id}/keys` |
| POST | `/settings/providers/{provider_id}/keys` |
| DELETE | `/settings/providers/{provider_id}/keys/{key_id}` |
| GET | `/settings/billing` |
| PUT | `/settings/billing` |

### Admin

| Method | Path |
|---|---|
| GET | `/admin/models` |
| GET | `/admin/usage/daily` |
| GET | `/admin/users/usage` |
| GET | `/admin/users/{user_id}/usage` |
| GET | `/admin/tenants/usage` |
| GET | `/admin/conversations` |
| GET | `/admin/conversations/{conversation_id}/messages` |

### Tenant management

| Method | Path |
|---|---|
| GET | `/admin/tenants` |
| POST | `/admin/tenants` |
| GET | `/admin/tenants/{tenant_id}` |
| PATCH | `/admin/tenants/{tenant_id}` |
| GET | `/admin/tenants/{tenant_id}/settings` |
| PUT | `/admin/tenants/{tenant_id}/settings` |
| GET | `/admin/tenants/{tenant_id}/api-keys` |
| POST | `/admin/tenants/{tenant_id}/api-keys` |
| DELETE | `/admin/tenants/{tenant_id}/api-keys/{key_id}` |

### FAQ & Escalation management

| Method | Path |
|---|---|
| GET | `/tenants/{tenant_id}/faqs` |
| POST | `/tenants/{tenant_id}/faqs` |
| DELETE | `/faqs/{faq_id}` |
| GET | `/tenants/{tenant_id}/escalations` |
| POST | `/escalations/{escalation_id}/promote` |

### Tenant self

| Method | Path |
|---|---|
| GET | `/tenants/me` |
| GET | `/tenants/me/settings` |
| PUT | `/tenants/me/settings` |

### System

| Method | Path |
|---|---|
| GET | `/health` |
| GET | `/health/data` |

### Public inference

| Method | Path |
|---|---|
| GET | `/models` |
| POST | `/chat/completions` |

`GET /health` thuộc nhóm System (xem trên) — inference endpoint không định nghĩa thêm health riêng.

Public chat request hỗ trợ các field chính:

- `model`
- `messages`
- `stream`
- `thinking_mode`
- `temperature`
- `max_tokens`
- `conversation_id` (tùy chọn, string UUID do frontend sinh per session để phục vụ Admin Audit Persistence)

## Rate Limit & Quota contract (HTTP 429)

Khi vượt quá giới hạn lượt request (tenant rate limit), daily request quota (nội bộ user), hoặc monthly LLM call/budget hard stop, backend trả về HTTP 429 với cấu trúc:

```json
{
  "detail": {
    "code": "rate_limited_or_quota_exceeded",
    "limit_type": "user_rate_limit | tenant_rate_limit | daily_request | monthly_llm | hard_budget",
    "retry_after": 60,
    "reset_at": "2026-07-25T10:10:00+07:00",
    "message": "Rate limit or quota exceeded"
  }
}
```

*Lưu ý cho Public API (`POST /v1/chat/completions`)*: Public API xác thực qua Tenant API Key (`user_id = None`), do đó hoàn toàn bỏ qua các counter giới hạn cấp User (`rate:user:...` và `quota:user_daily:...`). Toàn bộ request Public API chỉ tuân theo duy nhất giới hạn cấp **Tenant** (`rate_limit_rpm`, `monthly_request_quota`, `monthly_token_quota` trong DB `tenants`) và Platform Hard Budget (SQLite `platform_settings`).

## Error handling

### General

- route layer translate lỗi sang HTTP
- service layer chỉ raise lỗi business kiểu Python

### Common status

| Status | Ý nghĩa |
|---|---|
| `200` | thành công |
| `201` | tạo mới |
| `202` | accepted / queued |
| `400` | request không hợp lệ |
| `401` | chưa auth |
| `403` | không đủ quyền |
| `404` | không tìm thấy |
| `409` | conflict |
| `429` | rate limit / quota |
| `500` | lỗi server |

## Những contract đã bỏ

- `/chat/stream` (xóa hoàn toàn, dùng chung /v1/chat/completions)
- memories CRUD (`/memories`)
- persisted chat session contract
- session analytics contract
