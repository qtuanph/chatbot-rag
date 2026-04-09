# 04 — API Contract and Security

Status: stable API and security baseline.

## Contract Stability Rules

| Rule | Requirement |
|------|-------------|
| Endpoint stability | Keep public routes stable while internals evolve |
| Provider abstraction | Do not expose provider-specific payloads in public API |
| Grounding | Document route is default; return citations for grounded answers |
| Authorization | RBAC is mandatory (admin/member) |

## Public API Surface

All routes are served under the configured API prefix.

| Endpoint | Method | Purpose | Access |
|----------|--------|---------|--------|
| /health | GET | service health summary | authenticated or open (deployment policy) |
| /auth/login | POST | obtain access token | public |
| /auth/logout | POST | revoke current token | authenticated |
| /auth/users | POST | create user | admin |
| /upload | POST | enqueue ingestion task | admin |
| /status/{task_id} | GET | task/document processing state | admin |
| /documents | GET | list document metadata | admin |
| /documents/{document_id} | GET | document details | admin |
| /documents/{document_id} | DELETE | soft delete document | admin |
| /chat | POST | grounded answer response | authenticated |

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
