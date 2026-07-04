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

### Admin

| Method | Path |
|---|---|
| GET | `/admin/models` |
| GET | `/admin/usage/daily` |
| GET | `/admin/users/usage` |
| GET | `/admin/users/{user_id}/usage` |
| GET | `/admin/tenants/usage` |

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

Public chat request hiện hỗ trợ các field chính:

- `model`
- `messages`
- `stream`
- `thinking_mode`
- `temperature`
- `max_tokens`

## Quy tắc role

| Role | Ý nghĩa |
|---|---|
| `platform_admin` | quản trị toàn hệ thống |
| `tenant_admin` | chỉ trong tenant của mình |

## Public API rule

Public API dùng:

`Authorization: Bearer <tenant_api_key>`

Backend tự resolve tenant từ key, không tin tenant do client tự truyền.

## Feedback rule

`/chat/feedback` dùng để ghi nhận `like` / `dislike` cho câu trả lời AI:

- không phụ thuộc persisted chat history
- frontend phải gửi lại `query_text`, `assistant_answer`, `citations`
- backend tự gắn `tenant_id`, `user_id`, và runtime stack metadata

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
