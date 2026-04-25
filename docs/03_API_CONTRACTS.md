# 03 — API Contracts and Security

Full route reference, security architecture, and error handling. Architecture in `01_ARCHITECTURE.md`, workflows in `02_WORKFLOWS.md`.

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
| SSE | Stream forwarded as `ReadableStream` with `X-Accel-Buffering: no` |
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
| `POST /chat/stream` | 30/min per user | existing chat throttle |
| SSE endpoint | nginx rate limit 100r/s burst=20 | nginx limit_req zone |

- Non-production: relax via `RATE_LIMIT_RELAXED_MODE` + `RATE_LIMIT_RELAXED_FLOOR`
- Throttled → 429 with clear detail message
- Production has coarse global fallback middleware rate limit

## Contract Stability

| Rule | Requirement |
|------|-------------|
| Endpoint stability | Keep public routes stable while internals evolve |
| Provider abstraction | Do not expose provider-specific payloads in public API |
| Grounding | Document route is default; return citations for grounded answers |
| Authorization | RBAC mandatory; role values from `roles` table |
| HTTP status codes | Use `status.HTTP_*` constants, not raw numbers |
| API layer errors | Use `app/core/http_errors.py` helpers, not direct HTTPException |

## Upload Contract

Request: multipart form with file payload. Response (202):

```json
{ "task_id": "task-uuid", "status": "queued", "document_id": "doc-uuid" }
```

Status lifecycle: uploaded → queued → download → parse → persist → ready (or failed).

```json
{
  "task_id": "task-uuid", "status": "processing", "stage": "parse",
  "document_id": "doc-uuid", "status_message": "Parsing document with Docling.",
  "progress": { "step": "parse", "percent": 40 }
}
```

## Chat Contract

Request:

```json
{ "query": "question text", "session_id": "optional-session-id" }
```

Non-streaming response:

```json
{ "session_id": "session-id", "answer": "grounded answer text", "citations": [] }
```

Streaming: SSE with `{"chunk": "...", "done": false}` chunks, final `{"done": true, "session_id": "...", "citations": [...], "stats": {"total_ms", "ttft_ms", "chunks", "chars", "prompt_tokens", "completion_tokens", "total_tokens", "estimated_cost_usd"}}`.

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

Validation: username 3-64 chars (normalized lowercase + trim), password 8-256 chars, role must match `roles` table.

### Documents & Ingestion

| Method | Path | Auth | Notes |
|--------|------|------|-------|
| POST | `/upload` | Admin | multipart/form-data field `file` → `{task_id, document_id}` 202. Multi-file parallel supported |
| GET | `/status/{task_id}` | JWT | Poll pipeline status |
| GET | `/documents` | Member | List documents (excludes soft-deleted) |
| GET | `/documents/{document_id}` | Admin | Document detail |
| DELETE | `/documents/{document_id}` | Admin | Trigger hard-delete worker |
| POST | `/documents/{document_id}/retry` | Admin | Re-process failed document → task_id |

### Chat

| Method | Path | Auth | Notes |
|--------|------|------|-------|
| POST | `/chat` | Member | Non-streaming, strip_reasoning() applied |
| POST | `/chat/stream` | Member | SSE stream, thinkingConfig MINIMAL |
| POST | `/chat/sessions` | Member | Create empty session → `{session_id, title, ...}` |
| GET | `/chat/sessions` | Member | Sessions ordered by `updated_at DESC` |
| GET | `/chat/messages?session_id=...` | Member | Messages ordered by `created_at ASC`, pagination with limit/offset |

Chat features:
- Session default: empty "Chat mới" on page load, sidebar for history
- Auto-title: first user message truncated to 80 chars
- Multi-turn: last 20 messages as Gemini contents array
- Memory injection: active memories → systemInstruction
- Memory extraction: async post-response via provider singleton → user_memories
- Token tracking: usageMetadata from Gemini → persisted to ChatMessage + frontend stats bar
- Cost estimation: Gemini 2.5 Flash pricing ($0.075/1M input, $0.30/1M output)
- Input validation: nh3 HTML sanitization for query input
- SSE abort: Frontend AbortController cancels stream on unmount/new message
- Thinking suppressed: 4 layers (see 01_ARCHITECTURE.md)

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
| GET | `/health` | Public | Simple health status |
| GET | `/health/data` | JWT | Detailed snapshot with parallel checks, cache, throttled |
| GET | `/health/nodes` | JWT | `?document_id=` → Qdrant nodes list, throttled |
| GET | `/health/node` | JWT | `?document_id=&node_id=` → single node detail, throttled |

### Tree API

| Method | Path | Auth | Notes |
|--------|------|------|-------|
| GET | `/tree/{document_id}` | JWT | Hierarchical document structure, throttled |
| GET | `/tree/{document_id}/nodes/{node_id}` | JWT | Full node detail with text and metadata, throttled |
| GET | `/tree/{document_id}/search?query=` | JWT | Search nodes by title/content (query 1-500 chars), throttled |

Tree ordering: `document_sections.order_index` is canonical sort key. `page_number` is display hint (may be range string like "1-3").

### Demo UI (app/view/ — removable at go-live)

| Method | Path | Notes |
|--------|------|-------|
| GET | `/` | SPA Admin/Chat (client-side JWT auth) |
| GET | `/view/stats` | JSON dashboard summary |
| GET | `/view/nodes` | HTML node list |
| GET | `/view/node` | HTML node detail |

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
| AI_PROVIDER | google | vllm (not implemented) |
| Application endpoints | Unchanged | Unchanged |
| Auth model | Unchanged | Unchanged |
| Retrieval pipeline | Unchanged | Unchanged |

Provider abstraction normalizes request/response so `/chat` stays unchanged across phases.

## Version Conflict Resolution

```
User re-uploads "policy.md" (same filename, different content)
→ SHA-256 differs → not a duplicate
→ Create new version (version + 1)
→ Previous version marked as superseded
→ Router prioritizes latest version by default
→ User can query specific version via document_ids filter
```
