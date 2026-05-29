# 3 — API Contracts and Security

Full route reference, security architecture, and error handling. Architecture in `1_ARCHITECTURE.md`, workflows in `2_WORKFLOWS.json`.

## Security Architecture

### API Gateway Proxy (JWT Hiding)

Browser **never** sends or receives Bearer tokens. All browser API calls go through the Next.js API gateway proxy:

```
Browser → /api/bep/v1/... → Next.js Route Handler → getToken() (HttpOnly cookie) → Bearer header → FastAPI
```

| Layer | Mechanism |
|-------|-----------|
| Client | Calls `/api/bep/v1/...` — no token in JS, no token in Network tab |
| Route Handler | `webapp/app/api/bep/[...path]/route.ts` — reads JWT via `getToken()` from encrypted HttpOnly cookie |
| Backend | Receives standard Bearer token — no changes to auth logic |
| Session type | Client Session has `role` + `userId` only — `accessToken` stays server-side |
| SSE | Real-time server-sent events via `POST /chat/stream` |
| Upload | `multipart/form-data` forwarded with `duplex: 'half'` |
| Retry | Route Handler retries once on socket close; returns 502 JSON |

### Server-Side Auth Guards

| Layout | Auth Level | Redirect |
|--------|-----------|----------|
| `webapp/app/(main)/admin/layout.tsx` | `session.role === "admin"` | → /login or /chat |
| `webapp/app/(main)/chat/layout.tsx` | `session exists` | → /login |
| `webapp/app/(main)/settings/layout.tsx` | `session exists` | → /login |

### Security Headers

Applied via `next.config.ts` `headers()` on all routes:

| Header | Value |
|--------|-------|
| X-Frame-Options | DENY |
| X-Content-Type-Options | nosniff |
| Referrer-Policy | strict-origin-when-cross-origin |
| Permissions-Policy | geolocation=(), microphone=(), camera=(), payment=() |
| X-DNS-Prefetch-Control | on |
| Strict-Transport-Security | max-age=31536000; includeSubDomains |

### Rate Limiting

| Endpoint | Limit | Throttle Key |
|----------|-------|--------------|
| `POST /auth/login` | 50/min per IP+user | `throttle:login:{ip}:{username}` |
| `POST /auth/users` | 5/min per admin | `throttle:user:create:{admin_id}` |
| `DELETE /auth/users/{username}` | 5/min per admin | `throttle:user:delete:{admin_id}` |
| `POST /memories` | 20/min per user | `throttle:memory:create:{user_id}` |
| `PATCH /memories/{id}` | 20/min per user | `throttle:memory:update:{user_id}` |
| `DELETE /memories/{id}` | 20/min per user | `throttle:memory:delete:{user_id}` |
| `POST /chat/sessions` | 30/min per user | `throttle:chat:sessions:{user_id}` |
| `POST /chat/stream (SSE)` | 30/min per user | existing chat throttle |
| `POST /chat/messages/{id}/feedback` | 60/min per user | `throttle:feedback:{user_id}` |
| `GET /analytics/stats` | 60/min per user | `throttle:analytics:{user_id}` |
| Admin endpoints | 20/min per admin | `throttle:admin:{admin_id}` |

- Non-production: relax via `RATE_LIMIT_RELAXED_MODE` + `RATE_LIMIT_RELAXED_FLOOR`
- Throttled → 429 with clear detail message
- Production has coarse global fallback middleware rate limit
- WebSocket throttled at 30 req/min per user

## Contract Stability

| Rule | Requirement |
|------|-------------|
| Endpoint stability | Keep public routes stable while internals evolve |
| Provider abstraction | Do not expose provider-specific payloads in public API |
| Grounding | Document route is default; return citations for grounded answers |
| Authorization | RBAC mandatory; role values from `roles` table |
| HTTP status codes | Use `status.HTTP_*` constants, not raw numbers |
| API layer errors | Use `app/core/http_errors.py` helpers, not direct HTTPException |
| Service exceptions | Services raise `ValueError`/`RuntimeError` only — routes catch and translate to `http_errors.*` |
| Route responsibility | Routes handle HTTP concerns only (auth, rate limiting, request parsing, response formatting). ChatService owns chat preparation, provider orchestration, and message persistence. |

## Upload Contract

Request: multipart form with file payload. Response (202):

```json
{ "task_id": "task-uuid", "status": "queued", "document_id": "doc-uuid" }
```

Status lifecycle: pending → parsing → embedding → ready (or failed).

```json
{
  "task_id": "task-uuid", "status": "processing", "stage": "parsing",
  "document_id": "doc-uuid", "status_message": "Parsing document with Docling.",
  "progress": { "step": "parsing", "percent": 40 }
}
```

## Chat Contract

Request:

```json
{ "query": "question text", "session_id": "optional-session-id" }
```

Streaming only: SSE via `POST /chat/stream` with `data: {"chunk":"...","done":false}` events, and a final `done:true` event containing `session_id`, `message_id`, `citations`, and `stats`.

## Error Response Envelope

```json
{
  "error": { "code": "bad_request", "message": "Query cannot be empty", "status": 400, "path": "/api/v1/chat" },
  "detail": "Query cannot be empty"
}
```

`detail` retained for backward compatibility. Validation errors (422) include `error.details`.

## Route Reference

> Base prefix: `/api/v1` (configurable via `API_V1_PREFIX`)

### Auth

| Method | Path | Auth | Notes |
|--------|------|------|-------|
| POST | `/auth/login` | Public | `{username, password}` → `{access_token, token_type, role}` |
| POST | `/auth/logout` | JWT | Blacklist current token |
| GET | `/auth/me` | JWT | Current user info |
| GET | `/auth/roles` | Admin | List roles from `roles` table |
| POST | `/auth/users` | Admin | `{username, password, role}` → create user |
| GET | `/auth/users` | Admin | List all users |
| DELETE | `/auth/users/{username}` | Admin | Delete user (cannot self-delete) |

Validation: username 3-64 chars (trim only, case-sensitive), password 6-256 chars, role must match `roles` table.

### Documents & Ingestion

| Method | Path | Auth | Notes |
|--------|------|------|-------|
| POST | `/upload` | Admin | multipart/form-data field `file` → `{task_id, document_id}` 202. Multi-file parallel supported |
| GET | `/status/{task_id}` | Admin | Poll pipeline status |
| GET | `/documents` | Admin | List documents (excludes soft-deleted) |
| GET | `/documents/{document_id}` | Admin | Document detail |
| DELETE | `/documents/{document_id}` | Admin | Trigger hard-delete worker |
| POST | `/documents/{document_id}/retry` | Admin | Re-process failed document → task_id (re-uploads to LlamaParse API) |
| POST | `/documents/{document_id}/rechunk` | Admin | Re-chunk from saved OCR markdown — no LlamaParse API call. Works on any status. → `{task_id, document_id, status}` |

### Chat

| Method | Path | Auth | Notes |
|--------|------|------|-------|
| POST | `/chat/stream` | Member | SSE real-time streaming |
| POST | `/chat/sessions` | Member | Create empty session → `{session_id, title, ...}` |
| GET | `/chat/sessions` | Member | Sessions ordered by `updated_at DESC` |
| GET | `/chat/messages?session_id=...` | Member | Messages ordered by `created_at ASC`, pagination with limit/offset |
| POST | `/chat/messages/{message_id}/feedback` | Member | Record Like/Dislike feedback for a message |

Chat features:
- Session default: empty "Chat mới" on page load, sidebar for history
- Auto-title: first user message truncated to 80 chars
- Multi-turn: last 20 messages as OpenAI messages array
- Memory injection: active memories → systemInstruction
- Memory extraction: Celery extract_memories_task (queue=default) post-response via AIProxyBridge → user_memories — durable, survives API restart
- Token tracking: response usage from LlamaIndex OpenAI → persisted synchronously before final WebSocket completion to ChatMessage + frontend stats bar
- Cost estimation: Configurable pricing via `AI_INPUT_COST_PER_1M` / `AI_OUTPUT_COST_PER_1M` (default 0.0 for free tier)
- Input validation: nh3 HTML sanitization for query input
- Stream abort: Frontend AbortController cancels WebSocket on unmount/new message

### User Memories

| Method | Path | Auth | Notes |
|--------|------|------|-------|
| GET | `/memories` | Member | List all memories for current user |
| POST | `/memories` | Member | `{memory_type, content}` → create (201) |
| PATCH | `/memories/{id}` | Member | `{content?, memory_type?, is_active?}` → update |
| DELETE | `/memories/{id}` | Member | Delete (204) |

Memory types: `preference` | `correction` | `instruction` | `fact`. Max 1000 chars. Redis cache (5min) invalidated on CUD.

### Health & Monitoring

| Method | Path | Auth | Notes |
|--------|------|------|-------|
| GET | `/health` | Public | Liveness probe — `{"status": "up"}` for load balancers |
| GET | `/health/data` | Admin | Service configuration overview (passive — no active probing) |

### Tree API

| Method | Path | Auth | Notes |
|--------|------|------|-------|
| GET | `/tree/{document_id}` | Member | Hierarchical document structure (paginated), throttled. Params: `offset`, `limit` |
| GET | `/tree/{document_id}/nodes/{node_id}` | Member | Full node detail with text and metadata, throttled |
| GET | `/tree/{document_id}/search?query=` | Member | Search nodes by title/content (query 1-500 chars), throttled |

Tree ordering: `document_sections.order_index` is canonical sort key. `page_number` is display hint (may be range string like "1-3").

### Settings — AI Provider Config (Kết nối AI)

Quản lý Embedding, Reranker, và LLM providers. Lưu vào `settings.db` (SQLite riêng của project). Thay đổi có hiệu lực ngay lập tức qua `RuntimeProviderManager.reload()` — không cần restart.

| Method | Path | Auth | Notes |
|--------|------|------|-------|
| GET | `/settings/templates` | Admin | Danh sách provider templates (tei, openai, openrouter, nvidia, gemini, cohere, 9router) |
| GET | `/settings/providers?service_type=` | Admin | List providers, filter by `embedding`/`reranker`/`llm` |
| POST | `/settings/providers` | Admin | Tạo provider mới (không được tạo LLM thủ công — chỉ built-in) |
| GET | `/settings/providers/{id}` | Admin | Chi tiết provider |
| PUT | `/settings/providers/{id}` | Admin | Sửa url, model, api_key, priority. Trigger `RuntimeProviderManager.reload()` |
| DELETE | `/settings/providers/{id}` | Admin | Xóa provider (không xóa được `is_builtin=1`) |
| POST | `/settings/providers/{id}/activate` | Admin | **Set active** cho service_type — deactivate tất cả provider cùng loại, activate cái này. Trigger reload() ngay |
| POST | `/settings/providers/{id}/test` | Admin | Test kết nối: embed/rerank/chat test call thực tế → `{success, message}` |
| GET | `/settings/providers/{id}/keys` | Admin | Danh sách API keys của provider |
| POST | `/settings/providers/{id}/keys` | Admin | Thêm API key (round-robin pool) |
| DELETE | `/settings/providers/{id}/keys/{key_id}` | Admin | Xóa API key |

**Seeded providers** (first-boot, nếu `ai_providers` trống):

| service_type | provider_name | Default active |
|---|---|---|
| embedding | tei (TEI Local, built-in) | ✅ |
| embedding | openai, openrouter, nvidia, gemini, cohere | ❌ |
| reranker | tei (TEI Local, built-in) | ✅ |
| reranker | nvidia, cohere | ❌ |
| llm | 9router (built-in) | ✅ |

### Admin — Model Listing

| Method | Path | Auth | Notes |
|--------|------|------|-------|
| GET | `/admin/models` | Admin | List available models from 9Router's connected providers |
| GET | `/admin/usage/daily?days=30` | Admin | Daily usage breakdown for the whole system |
| GET | `/admin/users/usage` | Admin | Per-user summary in last 30 days (token in/out = LLM only, cost = all 3 model types) |
| GET | `/admin/users/{user_id}/usage` | Admin | Per-user detail for last 30 days, includes breakdown `llm/embedding/reranker` |

Rate limit: 20/min per admin. Proxies to 9Router `/v1/models`. Provider management (9Router-side) via 9Router Dashboard tại port 2908 (SQLite riêng của 9Router, khác `settings.db` của project).

### Analytics

| Method | Path | Auth | Notes |
|--------|------|------|-------|
| GET | `/analytics/stats` | JWT | Token usage analytics. Admin: system-wide. Member: own sessions only. |

| GET | `/analytics/me/usage` | JWT | Current user windows 1/7/30 ngày, gồm LLM/Embedding/Reranker |
Response:
```json
{
  "total_messages": 150, "total_sessions": 12, "total_tokens_in": 50000,
  "total_tokens_out": 120000, "total_tokens": 170000, "avg_latency_ms": 2500,
  "estimated_cost_usd": 0.0, "model_used": "model-from-ai-proxy-config",
  "daily": [{"date": "2026-04-28", "messages": 10, "tokens_in": 3000, "tokens_out": 8000, "avg_latency_ms": 2200, "cost_usd": 0.0}],
  "pricing": {"input_per_1m": 0.0, "output_per_1m": 0.0, "model": "from-AI_PROXY_DEFAULT_MODEL", "note": "Free tier"}
}
```

Frontend routes:
- Admin: `/admin/analytics`
- Member: `/analytics` (cùng layout thống kê, dữ liệu chỉ của user hiện tại)

Rate limit: 60/min per user. Throttle key: `throttle:analytics:{user_id}`.

## Routing Guardrails

| Scenario | Behavior |
|----------|----------|
| Question answerable from docs | Use document RAG |
| Explicit live business data request | SQL connector only if approved/configured |
| No connector configured | Return explicit limitation, do not run ad hoc SQL |

## HTTP Status Code Policy

- `HTTPException` must use FastAPI `status.HTTP_*` constants
- API layer (`app/api/routes/*`, `app/api/deps.py`) must use `app/core/http_errors.py` helpers
- Direct `raise HTTPException(...)` in API layer is forbidden
- Enforced by CI: `.github/workflows/status-code-guardrail.yml`

## Compatibility Promise

| Area | Current | Planned |
|------|---------|---------|
| AI_PROVIDER | 9Router (OpenAI-compatible) | vllm (not implemented) |
| Application endpoints | Unchanged | Unchanged |
| Auth model | Unchanged | Unchanged |
| Retrieval pipeline | Unchanged | Unchanged |

Provider abstraction via LlamaIndex OpenAI normalizes request/response so `POST /chat/stream` contract stays stable across provider changes.

## Version Conflict Resolution

```
User re-uploads "policy.md" (same filename, different content)
→ SHA-256 differs → not a duplicate
→ Create new version (version + 1)
→ Previous version marked as superseded
→ Router prioritizes latest version by default
→ User can query specific version via document_ids filter
```
