# 04 — API Contract and Security

Status: stable API and security baseline.

## Contract Stability Rules

| Rule | Requirement |
|------|-------------|
| Endpoint stability | Keep public routes stable while internals evolve |
| Provider abstraction | Do not expose provider-specific payloads in public API |
| Grounding | Document route is default; return citations for grounded answers |
| Authorization | RBAC is mandatory (admin/member) |



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

## Security Baseline

| Concern | Policy |
|---------|--------|
| Authentication | JWT bearer token |
| Authorization | role checks at route boundary |
| Rate limiting | enforce per sensitive endpoint |
| Input validation | schema validation and size limits |
| Audit logging | log privileged actions and failures |
| Soft-delete safety | deletion excludes docs from new retrieval, preserves history |

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
| `POST` | `/api/v1/auth/users` | 🔒 Admin | `{username, password, role}` → tạo user mới |

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
| `POST` | `/api/v1/chat` | ✅ Bearer | `{query, session_id?}` → `{answer, citations, session_id}` |

### Health / Monitoring (JSON)

| Method | Path | Auth | Notes |
|--------|------|------|-------|
| `GET` | `/api/v1/health` | ❌ Public | Health HTML + JSON snapshot |
| `GET` | `/api/v1/health/data` | ❌ Public | JSON snapshot phục vụ auto-refresh |
| `GET` | `/api/v1/health/nodes` | ❌ Public | `?document_id=` → JSON danh sách Qdrant nodes |
| `GET` | `/api/v1/health/node` | ❌ Public | `?document_id=&node_id=` → JSON chi tiết 1 node |

### Demo UI (app/view/ — có thể xóa khi go-live)

| Method | Path | Notes |
|--------|------|-------|
| `GET` | `/` | SPA Admin/Chat — auth xử lý phía client (JWT localStorage) |
| `GET` | `/view/stats` | JSON tổng hợp dùng cho Dashboard |
| `GET` | `/view/nodes` | HTML danh sách nodes (light theme) |
| `GET` | `/view/node` | HTML chi tiết 1 node (mở tab mới) |

### Tree API (Streamlit Visualizer Support)

| Method | Path | Auth | Notes |
|--------|------|------|-------|
| `GET` | `/api/v1/tree/{document_id}` | 🔒 Bearer | Trả về cấu trúc phân cấp hoàn chỉnh của tài liệu |
| `GET` | `/api/v1/tree/{document_id}/nodes/{node_id}` | 🔒 Bearer | Chi tiết một node với đầy đủ nội dung và metadata |
| `GET` | `/api/v1/tree/{document_id}/search?query=` | 🔒 Bearer | Tìm kiếm node theo tiêu đề hoặc nội dung |

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
      "page_number": 1
    }
  ]
}
```

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
