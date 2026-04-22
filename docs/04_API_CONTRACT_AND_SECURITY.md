# 04 — API Contract and Security

Status: stable API and security baseline — updated to reflect Next.js 16 frontend and new endpoints.

## Contract Stability Rules

| Rule | Requirement |
|------|-------------|
| Endpoint stability | Keep public routes stable while internals evolve |
| Provider abstraction | Do not expose provider-specific payloads in public API |
| Grounding | Document route is default; return citations for grounded answers |
| Authorization | RBAC is mandatory; role values come from the `roles` table |



## Upload Contract

Request: multipart form with file payload.

Response on accepted task:

```json
{
  "task_id": "task-uuid",
  "status": "queued",
  "document_id": "doc-uuid"
}
```

## Task Status Contract

Typical lifecycle:

uploaded -> queued -> download -> parse -> persist -> ready

or

uploaded -> queued -> enqueue_failed|download|parse|persist -> failed

Response shape:

```json
{
  "task_id": "task-uuid",
  "status": "processing",
  "stage": "parse",
  "document_id": "doc-uuid",
  "status_message": "Parsing document with Docling.",
  "progress": {
    "step": "parse",
    "percent": 40
  }
}
```

## Chat Contract (JSON)

Request body:

```json
{
  "query": "question text",
  "session_id": "optional-session-id"
}
```

Response shape:

```json
{
  "session_id": "session-id",
  "answer": "grounded answer text",
  "citations": []
}
```

## Error Response Envelope

All JSON error responses follow a unified envelope:

```json
{
  "error": {
    "code": "bad_request",
    "message": "Query cannot be empty",
    "status": 400,
    "path": "/api/v1/chat"
  },
  "detail": "Query cannot be empty"
}
```

Notes:
- `detail` is retained for backward compatibility with existing clients.
- Validation errors (`422`) include `error.details` with FastAPI validation entries.

## Security Baseline

| Concern | Policy |
|---------|--------|
| Authentication | JWT bearer token |
| Authorization | role checks at route boundary |
| Rate limiting | enforce per sensitive endpoint |
| Input validation | schema validation and size limits |
| Audit logging | log privileged actions and failures |
| Soft-delete safety | deletion excludes docs from new retrieval, preserves history |
| Token hiding | Browser never sends/receives Bearer token — all calls via API gateway proxy |
| Server-side auth | Layout files enforce authentication at server component level |
| Security headers | X-Frame-Options, HSTS, nosniff, Referrer-Policy applied via Next.js |

### API Gateway Proxy

Browser communicates with backend exclusively through the Next.js API gateway proxy:

- **Browser path**: `/api/bep/v1/...` (set via `NEXT_PUBLIC_API_URL`)
- **Server path**: `http://api:8000/api/v1/...` (set via `API_INTERNAL_URL`)
- **Token flow**: Route Handler reads `accessToken` from encrypted HttpOnly JWT cookie via `getToken()` → attaches `Authorization: Bearer` header to backend request
- **SSE support**: Stream forwarded as `ReadableStream` with `X-Accel-Buffering: no` header
- **File upload**: `multipart/form-data` forwarded with `duplex: 'half'` for streaming request body

### Rate Limiting Reference

| Endpoint | Limit | Throttle Key |
|----------|-------|--------------|
| `POST /auth/login` | 50/min per IP+user | `throttle:login:{ip}:{username}` |
| `POST /auth/users` | 5/min per admin | `throttle:user:create:{admin_id}` |
| `DELETE /auth/users/{username}` | 5/min per admin | `throttle:user:delete:{admin_id}` |
| `POST /memories` | 20/min per user | `throttle:memory:create:{user_id}` |
| `PATCH /memories/{id}` | 20/min per user | `throttle:memory:update:{user_id}` |
| `DELETE /memories/{id}` | 20/min per user | `throttle:memory:delete:{user_id}` |
| `POST /chat/stream` | 30/min per user | existing chat throttle |

### Rate-Limit Notes

- Non-production environments can relax limits via `RATE_LIMIT_RELAXED_MODE` + `RATE_LIMIT_RELAXED_FLOOR`.
- When throttled, endpoints return `429 Too Many Requests` with a clear `detail` message.
- Production includes a coarse global fallback middleware rate limit (in addition to endpoint-level throttles).

### HTTP Status Code Policy

- `HTTPException` must use FastAPI constants (`status.HTTP_*`) instead of raw numeric literals.
- Policy is enforced by CI workflow: `.github/workflows/status-code-guardrail.yml`.
- API layer (`app/api/routes/*`, `app/api/deps.py`) must raise route-level HTTP errors via `app/core/http_errors.py` helpers.
- Direct `raise HTTPException(...)` in API layer is forbidden by guardrail script.

## Routing Guardrails

| Scenario | Required behavior |
|----------|-------------------|
| Question answerable from docs | Use document RAG |
| Explicit live business data request | SQL connector path only if approved/configured |
| No connector configured | Return explicit limitation, do not run ad hoc SQL |

## Compatibility Promise

The API contract remains stable across provider mode changes:

| Area | Demo mode | Production mode |
|------|-----------|-----------------|
| `AI_PROVIDER` | `google` | `vllm` |
| Chat provider | Google AI Studio | On-prem `vLLM` |
| Application endpoints | Unchanged | Unchanged |
| Auth model | Project-only auth model | Project-only auth model |
| Retrieval pipeline | Unchanged | Unchanged |

The provider abstraction layer normalizes provider-specific request and response formats so `/chat` remains unchanged across both phases.

## Contract Invariants

| Area | Requirement |
|------|-------------|
| Endpoint naming | MUST keep documented route names stable; do not rename routes during provider migration |
| Response contract | MUST preserve `session_id`, `answer`, `citations` fields exactly |
| Auth | MUST reject missing/invalid JWT; admin routes MUST reject non-admin roles |
| Citations | Assistant responses MUST include citations or an explicit no-grounding response |
| Version resolution | Default retrieval MUST prefer latest non-deleted version unless caller narrows scope |
| Data-source routing | `/chat` MUST preserve one public contract even when internally routing to document or SQL workflows |

## AI Coding Guardrails

| Do | Do not |
|----|--------|
| Generate request/response models matching these examples | Silently change field names or response shapes |
| Keep `/chat` provider-agnostic | Expose provider-specific payloads to clients |
| Return grounded failure messages | Hallucinate answers when citations are missing |
| Route SQL questions through a connector policy layer | Open a raw SQL connection directly from route handlers |

## Future SQL Connector Rules

| Rule | Requirement |
|------|-------------|
| Connection ownership | Admin configures SQL Server connections; the application stores encrypted config only |
| Access policy | Only approved schemas/tables may be queried |
| SQL verbs | Only `SELECT` is allowed |
| Query limits | Apply row limit, timeout, and redaction before returning results |
| Answer behavior | If the request is not clearly data-centric, prefer document answering first |

### Version Conflict Resolution

```
User re-uploads "policy.md" (same filename, different content)
-> SHA-256 differs -> not a duplicate
-> Create new version (version + 1)
-> Previous version stays accessible but marked as superseded
-> Router prioritizes latest version by default
-> User can query specific version via document_ids filter
```

---

## Route Reference (Implemented)

> Base prefix: `/api/v1` (configurable via `API_V1_PREFIX` env var)

### Auth

| Method | Path | Auth | Body / Notes |
|--------|------|------|--------------|
| `POST` | `/api/v1/auth/login` | ❌ Public | `{username, password}` → `{access_token, token_type, role}` |
| `POST` | `/api/v1/auth/logout` | ✅ Bearer | Vô hiệu hoá token hiện tại |
| `GET` | `/api/v1/auth/roles` | 🔒 Admin | Danh sách role lấy từ bảng `roles` |
| `POST` | `/api/v1/auth/users` | 🔒 Admin | `{username, password, role}` → tạo user mới |
| `GET` | `/api/v1/auth/me` | ✅ Bearer | Trả về thông tin user hiện tại |
| `GET` | `/api/v1/auth/users` | 🔒 Admin | Danh sách tất cả users |
| `DELETE` | `/api/v1/auth/users/{username}` | 🔒 Admin | Xóa user (không thể tự xóa) |

Auth request validation:
- `username`: 3-64 ký tự, được normalize lowercase + trim.
- `create user password`: 8-256 ký tự.
- `role`: phải khớp với `name` của một dòng trong bảng `roles`.

### Documents & Ingestion

| Method | Path | Auth | Notes |
|--------|------|------|-------|
| `POST` | `/api/v1/upload` | 🔒 Admin | `multipart/form-data` field `file` → `{task_id, document_id}` **202** |
| `GET` | `/api/v1/status/{task_id}` | ✅ Bearer | Poll trạng thái xử lý pipeline |
| `GET` | `/api/v1/documents` | 🔒 Admin | Danh sách tài liệu (không bao gồm soft-deleted) |
| `GET` | `/api/v1/documents/{document_id}` | 🔒 Admin | Chi tiết 1 document |
| `DELETE` | `/api/v1/documents/{document_id}` | 🔒 Admin | Kích hoạt worker xóa: DB + S3 + Qdrant |

### Chat

| Method | Path | Auth | Notes |
|--------|------|------|-------|
| `POST` | `/api/v1/chat` | ✅ Bearer | `{query, session_id?}` → `{answer, citations, session_id}` (non-streaming, `strip_reasoning()` applied) |
| `POST` | `/api/v1/chat/stream` | ✅ Bearer | `{query, session_id?}` → SSE stream với chunks real-time, `thinkingConfig: {thinkingBudget: 0}` |
| `GET` | `/api/v1/chat/sessions` | ✅ Bearer | Danh sách chat sessions của user hiện tại |

Chat features:
- **Multi-turn**: Last 20 messages sent as Gemini `contents` array (role: assistant→model mapping)
- **Memory injection**: Active user memories loaded from Redis cache → injected into `systemInstruction`
- **Memory extraction**: Async post-response — heuristic triggers + Gemini extraction → `user_memories` table
- **Thinking control**: `thinkingConfig: {thinkingBudget: 0}` disables Gemma 4 chain-of-thought; `thought:true` parts filtered; `strip_reasoning()` applied to saved text

### User Memories

| Method | Path | Auth | Notes |
|--------|------|------|-------|
| `GET` | `/api/v1/memories` | ✅ Bearer | Danh sách tất cả memories của user hiện tại |
| `POST` | `/api/v1/memories` | ✅ Bearer | `{memory_type, content}` → tạo memory mới (201) |
| `PATCH` | `/api/v1/memories/{id}` | ✅ Bearer | `{content?, memory_type?, is_active?}` → cập nhật memory |
| `DELETE` | `/api/v1/memories/{id}` | ✅ Bearer | Xóa memory (204) |

Memory types: `preference` | `correction` | `instruction` | `fact`
Content limit: max 1000 characters per memory.
Redis cache (5min TTL) invalidated on create/update/delete.

### Health / Monitoring (JSON)

| Method | Path | Auth | Notes |
|--------|------|------|-------|
| `GET` | `/api/v1/health` | ❌ Public | Health status đơn giản |
| `GET` | `/api/v1/health/data` | ✅ Bearer | JSON snapshot chi tiết với checks chạy song song, cache ngắn, throttled |
| `GET` | `/api/v1/health/nodes` | ✅ Bearer | `?document_id=` → JSON danh sách Qdrant nodes, throttled |
| `GET` | `/api/v1/health/node` | ✅ Bearer | `?document_id=&node_id=` → JSON chi tiết 1 node, throttled |

### Demo UI (app/view/ — có thể xóa khi go-live)

| Method | Path | Notes |
|--------|------|-------|
| `GET` | `/` | SPA Admin/Chat — auth xử lý phía client (JWT localStorage) |
| `GET` | `/view/stats` | JSON tổng hợp dùng cho Dashboard |
| `GET` | `/view/nodes` | HTML danh sách nodes (light theme) |
| `GET` | `/view/node` | HTML chi tiết 1 node (mở tab mới) |

### Tree API

| Method | Path | Auth | Notes |
|--------|------|------|-------|
| `GET` | `/api/v1/tree/{document_id}` | 🔒 Bearer | Trả về cấu trúc phân cấp hoàn chỉnh của tài liệu, throttled |
| `GET` | `/api/v1/tree/{document_id}/nodes/{node_id}` | 🔒 Bearer | Chi tiết một node với đầy đủ nội dung và metadata, throttled |
| `GET` | `/api/v1/tree/{document_id}/search?query=` | 🔒 Bearer | Tìm kiếm node theo tiêu đề hoặc nội dung, throttled, `query` 1-500 ký tự |

Common throttling response:

```json
{
  "detail": "Too many ... requests"
}
```

**Tree API Response Examples**:

`GET /api/v1/tree/{document_id}`
```json
{
  "document_id": "uuid-here",
  "document_title": "Policy.pdf",
  "total_nodes": 45,
  "max_depth": 3,
  "nodes": [
    {
      "node_id": "node-uuid",
      "title": "Chapter 1",
      "level": 1,
      "breadcrumb": "Policy.pdf > Chapter 1",
      "parent_id": null,
      "child_count": 5,
      "text_length": 2500,
      "page_number": "1-3"
    }
  ]
}
```

Tree ordering rules:
- `document_sections.order_index` is the canonical sort key.
- `page_number` in tree responses is a display hint and may be a range string such as `"1-3"`.
- `page_range` is included explicitly to preserve the original page span as evidence for later AI use.
- The tree endpoint returns a paginated slice ordered by `order_index`; page span is preserved for display and evidence only.
- Qdrant is not the ordering source for tree display.

`GET /api/v1/tree/{document_id}/nodes/{node_id}`
```json
{
  "node_id": "node-uuid",
  "title": "Section 1.1",
  "level": 2,
  "breadcrumb": "Policy.pdf > Chapter 1 > Section 1.1",
  "text": "Full text content here...",
  "metadata": {
    "page_number": 5,
    "node_type": "section",
    "order": 1,
    "char_count": 2500,
    "token_count": 500
  }
}
```

`GET /api/v1/tree/{document_id}/search?query=policy`
```json
{
  "results": [
    {
      "node_id": "node-uuid",
      "title": "Matching Section",
      "preview": "...context around match...",
      "highlight": "policy"
    }
  ]
}
```
