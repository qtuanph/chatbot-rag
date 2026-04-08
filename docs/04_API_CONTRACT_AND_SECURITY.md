# 04 — API Contract and Security

> Status: target public API contract. The current scaffold implements only a subset and does not yet provide JWT auth, SSE chat, or persistence-backed workflows.

## What The AI Must Preserve

| Requirement | Why it exists |
|-------------|---------------|
| Docker-friendly app boundaries | User wants the system to run with containers, not manual host setup |
| Stable API surface | Provider changes must not force frontend or client rewrites |
| Provider-agnostic `/chat` | Demo uses Google now; production uses `vLLM` later |
| Security before convenience | Role-based access is mandatory, not optional |
| Grounded answers only | User wants a useful enterprise chatbot, not generic LLM chat |
| Data access routing | Uploaded documents are the default source. SQL connector is used only when the request clearly asks for live business data and the connector is configured. |

## REST Endpoints

### Health Check

```
GET /health
```

**Response 200:**
```json
{
  "status": "healthy",
  "services": {
    "database": "connected",
    "redis": "connected",
    "ai_provider": "google"
  },
  "timestamp": "2026-04-07T10:00:00Z"
}
```

### Authentication

```
POST /auth/login
```

**Request:**
```json
{
  "username": "user1",
  "password": "securepassword"
}
```

**Response 200:**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 3600,
  "role": "admin"
}
```

```
POST /auth/refresh
```

**Request:**
```json
{
  "refresh_token": "eyJ..."
}
```

**Response 200:**
```json
{
  "access_token": "eyJ...",
  "expires_in": 3600
}
```

### Document Upload

```
POST /upload
Content-Type: multipart/form-data
Authorization: Bearer <token>
```

**Form Data:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | File | Yes | Document file (.md, .pdf, .docx, .txt) |
| `title` | String | No | Override filename as title |
| `metadata` | JSON | No | Custom metadata |

**Response 202:**
```json
{
  "task_id": "celery-task-uuid",
  "status": "queued",
  "document_id": "doc-uuid"
}
```

**Response 200 (duplicate):**
```json
{
  "status": "duplicate",
  "message": "Document already exists",
  "existing_document_id": "doc-uuid",
  "existing_version": 2
}
```

### Task Status

```
GET /status/{task_id}
Authorization: Bearer <token>
```

**Access Control:** Admin-only. Task progress belongs to admin upload workflow.

**Response 200:**
```json
{
  "task_id": "celery-task-uuid",
  "status": "parsing",
  "progress": {
    "step": "tree_building",
    "percent": 65
  },
  "document_id": "doc-uuid"
}
```

**Status values:** `queued` -> `parsing` -> `ready` | `failed`

### List Documents

```
GET /documents?page=1&page_size=20&status=ready
Authorization: Bearer <token>
```

**Response 200:**
```json
{
  "items": [
    {
      "id": "doc-uuid",
      "title": "Company Policy",
      "file_name": "policy.md",
      "file_type": "md",
      "file_size": 15234,
      "version": 1,
      "status": "ready",
      "node_count": 12,
      "created_at": "2026-04-07T10:00:00Z",
      "updated_at": "2026-04-07T10:01:30Z"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20
}
```

### Delete Document (Soft Delete)

```
DELETE /documents/{document_id}
Authorization: Bearer <token>
```

**Response 200:**
```json
{
  "status": "deleted",
  "document_id": "doc-uuid",
  "hard_delete_at": "2026-05-07T10:00:00Z"
}
```

### Chat (SSE)

```
POST /chat
Authorization: Bearer <token>
Accept: text/event-stream
```

**Request:**
```json
{
  "query": "What is the vacation policy?",
  "session_id": "optional-session-uuid",
  "document_ids": ["optional-filter"],
  "stream": true
}
```

**SSE Success Stream:**
```
event: token
data: {"content": "The", "session_id": "uuid", "message_id": "msg-uuid"}

event: token
data: {"content": " vacation", "session_id": "uuid", "message_id": "msg-uuid"}

event: citations
data: {
  "citations": [
    {
      "node_id": "node-uuid",
      "document_id": "doc-uuid",
      "document_title": "HR Policy",
      "heading": "Leave Policy",
      "score": 0.92,
      "deleted": false
    }
  ]
}

event: done
data: {"session_id": "uuid", "message_id": "msg-uuid", "model": "gemini-2.5-flash"}
```

**SSE Error Stream:**
```
event: error
data: {"error": "Unable to process request. Please try again.", "code": "PROVIDER_TIMEOUT"}
```

### Chat History

```
GET /chat/sessions/{session_id}/messages?page=1&page_size=50
Authorization: Bearer <token>
```

**Access Control:** A session is owned by exactly one authenticated user. Requests for another user's session must be rejected.

**Response 200:**
```json
{
  "items": [
    {
      "id": "msg-uuid",
      "role": "user",
      "content": "What is the vacation policy?",
      "created_at": "2026-04-07T10:00:00Z"
    },
    {
      "id": "msg-uuid-2",
      "role": "assistant",
      "content": "The vacation policy states...",
      "citations": [
        {
          "document_title": "HR Policy",
          "heading": "Leave Policy",
          "deleted": false
        }
      ],
      "model_used": "gemini-2.5-flash",
      "created_at": "2026-04-07T10:00:05Z"
    }
  ],
  "total": 2
}
```

## Auth Flow

```
1. Client -> POST /auth/login -> JWT {sub, role, exp}
2. Client includes Authorization: Bearer <jwt> in every request
3. API validates JWT signature + expiry
4. Resolve user role from DB
5. Admin routes enforce role checks
```

### JWT Payload

```json
{
  "sub": "user-uuid",
  "role": "admin",
  "username": "user1",
  "iat": 1712484000,
  "exp": 1712487600
}
```

## Guardrails

| Guardrail | Implementation | Response |
|-----------|---------------|----------|
| Out-of-scope rejection | Router classifies query relevance | "I can only answer based on your uploaded documents." |
| Citation mandatory | Every assistant response must include citations | If no citations found -> "No relevant documents found." |
| Role isolation | JWT role checks + DB-backed accounts | 403 if role mismatch |
| Version conflict | On re-upload, increment version, mark old as superseded | Return new version info |
| Rate limiting | Token bucket per endpoint | 429 Too Many Requests |
| Input validation | Pydantic schemas, max query length 2000 chars | 422 Unprocessable Entity |
| Security headers | X-Content-Type-Options, X-Frame-Options, CSP | Applied on all responses |
| CORS | Whitelist allowed origins only | 403 on mismatch |

## Transport Requirements

| Concern | Requirement |
|---------|-------------|
| TLS | Terminate TLS at reverse proxy; reject plain HTTP outside trusted internal network |
| SSE buffering | Set `Cache-Control: no-cache` and `X-Accel-Buffering: no` |
| Auth header | `Authorization: Bearer <jwt>` on all protected routes |
| Request ID | Generate `X-Request-ID` per request for tracing |
| Audit trail | Log user_id, endpoint, status_code, latency |

## Provider Compatibility

| Concern | Demo Phase | Production Phase |
|---------|------------|------------------|
| `AI_PROVIDER` | `google` | `vllm` |
| Chat provider | Google AI Studio | On-prem `vLLM` |
| Application endpoints | Unchanged | Unchanged |
| Auth model | Project-only auth model |
| Retrieval pipeline | Unchanged | Unchanged |

The provider abstraction layer normalizes provider-specific request and response formats so `/chat` remains unchanged across both phases.

## Contract Invariants

| Area | Requirement |
|------|-------------|
| Endpoint naming | MUST keep documented route names stable; do not rename routes during provider migration |
| SSE contract | MUST preserve `token`, `citations`, `done`, `error` events exactly |
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
