# 02 — Database and Tenancy

> Status: target production schema and tenancy design. Most tables and RLS policies are not implemented in the current scaffold yet.

## Core Schema

## Project Intent Mapping

| User expectation | Database consequence |
|------------------|----------------------|
| Fast read/write on one server | PostgreSQL is the primary database; do not split metadata across multiple databases |
| Zero tenant leakage | `tenant_id` everywhere + RLS everywhere |
| Docker-first setup | Schema and extensions must boot from containerized init/migrations |
| Future provider switch | Database schema must not depend on Google-only or `vLLM`-only payload shapes |
| Hierarchical retrieval | `doc_nodes` stores an n-ary document tree, not binary-tree pointers |

## Future Connector Registry

### `data_sources`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK, DEFAULT gen_random_uuid() | Data source identifier |
| `tenant_id` | UUID | NOT NULL, FK -> tenants(id) | Owning tenant |
| `type` | VARCHAR(50) | NOT NULL | `file`, `sqlserver`, `api` |
| `name` | VARCHAR(255) | NOT NULL | User-visible source name |
| `config_encrypted` | BYTEA | NOT NULL | Encrypted connection config |
| `capabilities` | JSONB | DEFAULT '{}' | e.g. read_only, schema_sync |
| `is_active` | BOOLEAN | NOT NULL, DEFAULT true | Source enabled flag |
| `created_by` | UUID | NULLABLE, FK -> users(id) ON DELETE SET NULL | Source owner |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Creation timestamp |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Last update timestamp |

### `data_source_schema_cache`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK, DEFAULT gen_random_uuid() | Cache row identifier |
| `tenant_id` | UUID | NOT NULL, FK -> tenants(id) | Owning tenant |
| `data_source_id` | UUID | NOT NULL, FK -> data_sources(id) ON DELETE CASCADE | Parent source |
| `schema_name` | VARCHAR(255) | NOT NULL | DB schema |
| `table_name` | VARCHAR(255) | NOT NULL | Table name |
| `column_metadata` | JSONB | NOT NULL | Columns, types, keys, sensitivity flags |
| `table_description` | TEXT | NULLABLE | Human-curated business meaning |
| `join_hints` | JSONB | DEFAULT '[]' | Known join paths |
| `synced_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Last schema sync time |

### `data_source_query_audit`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK, DEFAULT gen_random_uuid() | Audit identifier |
| `tenant_id` | UUID | NOT NULL, FK -> tenants(id) | Owning tenant |
| `data_source_id` | UUID | NOT NULL, FK -> data_sources(id) ON DELETE CASCADE | Target source |
| `user_id` | UUID | NULLABLE, FK -> users(id) ON DELETE SET NULL | Initiating user |
| `session_id` | UUID | NULLABLE, FK -> chat_sessions(id) ON DELETE SET NULL | Chat linkage |
| `sql_text_redacted` | TEXT | NOT NULL | Executed SQL with secrets removed |
| `row_count` | INTEGER | NULLABLE | Returned rows |
| `duration_ms` | INTEGER | NULLABLE | Query latency |
| `status` | VARCHAR(50) | NOT NULL | success / denied / failed / timeout |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Audit timestamp |

### `tenants`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK, DEFAULT gen_random_uuid() | Tenant identifier |
| `name` | VARCHAR(255) | NOT NULL | Display name |
| `api_key` | VARCHAR(255) | UNIQUE, NULLABLE | Optional API key |
| `settings` | JSONB | DEFAULT '{}' | Per-tenant config (model, thresholds) |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Creation timestamp |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Last update timestamp |

### `users`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK, DEFAULT gen_random_uuid() | User identifier |
| `tenant_id` | UUID | NOT NULL, FK → tenants(id) | Owning tenant |
| `email` | VARCHAR(255) | NOT NULL | Login email |
| `password_hash` | VARCHAR(255) | NOT NULL | Argon2id hash |
| `role` | VARCHAR(50) | NOT NULL, DEFAULT 'member' | admin / member |
| `is_active` | BOOLEAN | NOT NULL, DEFAULT true | Account status |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | — |

### `documents`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK, DEFAULT gen_random_uuid() | Document identifier |
| `tenant_id` | UUID | NOT NULL, FK → tenants(id) | Owning tenant |
| `title` | VARCHAR(500) | NOT NULL | Document title |
| `file_name` | VARCHAR(500) | NOT NULL | Original filename |
| `file_path` | VARCHAR(1000) | NOT NULL | Storage path |
| `sha256` | CHAR(64) | NOT NULL | Content fingerprint for dedup |
| `file_type` | VARCHAR(50) | NOT NULL | md, pdf, docx, txt |
| `file_size` | BIGINT | NOT NULL | Bytes |
| `version` | INTEGER | NOT NULL, DEFAULT 1 | Auto-increment on re-upload |
| `status` | VARCHAR(50) | NOT NULL, DEFAULT 'pending' | pending / parsing / ready / failed / superseded |
| `parse_error` | TEXT | NULLABLE | Error message if failed |
| `metadata` | JSONB | DEFAULT '{}' | Extra metadata (author, tags) |
| `deleted_at` | TIMESTAMPTZ | NULLABLE | Soft delete timestamp |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | — |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | — |

### `doc_nodes`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK, DEFAULT gen_random_uuid() | Node identifier |
| `tenant_id` | UUID | NOT NULL, FK → tenants(id) | Owning tenant |
| `document_id` | UUID | NOT NULL, FK → documents(id) ON DELETE CASCADE | Parent document |
| `parent_id` | UUID | NULLABLE, FK → doc_nodes(id) ON DELETE SET NULL | Parent node (NULL = root) |
| `level` | INTEGER | NOT NULL, DEFAULT 0 | Tree depth (0 = root) |
| `heading` | TEXT | NOT NULL | Section heading / title |
| `summary` | TEXT | NULLABLE | LLM-generated section summary |
| `full_text` | TEXT | NOT NULL | Complete section content |
| `page_range` | VARCHAR(50) | NULLABLE | e.g. "5-12" (for PDF/DOCX) |
| `heading_embedding` | vector(1024) | NULLABLE | BGE-M3 embedding of heading |
| `is_duplicate` | BOOLEAN | NOT NULL, DEFAULT false | Node-level dedup flag |
| `duplicate_of` | UUID | NULLABLE, FK → doc_nodes(id) ON DELETE SET NULL | Original node if duplicate |
| `order_index` | INTEGER | NOT NULL, DEFAULT 0 | Sibling ordering |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | — |

### `chat_sessions`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK, DEFAULT gen_random_uuid() | Session identifier |
| `tenant_id` | UUID | NOT NULL, FK → tenants(id) | Owning tenant |
| `user_id` | UUID | NULLABLE, FK → users(id) ON DELETE SET NULL | Optional user link |
| `title` | VARCHAR(500) | NULLABLE | Auto-generated or manual |
| `deleted_at` | TIMESTAMPTZ | NULLABLE | Soft delete |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | — |

### `chat_messages`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK, DEFAULT gen_random_uuid() | Message identifier |
| `tenant_id` | UUID | NOT NULL, FK → tenants(id) | Owning tenant |
| `session_id` | UUID | NOT NULL, FK → chat_sessions(id) ON DELETE CASCADE | Parent session |
| `role` | VARCHAR(20) | NOT NULL | user / assistant / system |
| `content` | TEXT | NOT NULL | Message body |
| `citations` | JSONB | DEFAULT '[]' | [{node_id, document_id, heading, score}] |
| `model_used` | VARCHAR(100) | NULLABLE | Which model generated this |
| `tokens_in` | INTEGER | NULLABLE | Prompt tokens |
| `tokens_out` | INTEGER | NULLABLE | Completion tokens |
| `latency_ms` | INTEGER | NULLABLE | Generation latency |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | — |

## Row-Level Security (RLS)

### Enable RLS on all tenant-scoped tables

```sql
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents FORCE ROW LEVEL SECURITY;
ALTER TABLE doc_nodes ENABLE ROW LEVEL SECURITY;
ALTER TABLE doc_nodes FORCE ROW LEVEL SECURITY;
ALTER TABLE chat_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_sessions FORCE ROW LEVEL SECURITY;
ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_messages FORCE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE users FORCE ROW LEVEL SECURITY;
```

### RLS Policy Template

```sql
-- Documents: tenant can only see their own
-- USING: controls SELECT, UPDATE, DELETE visibility
-- WITH CHECK: controls INSERT, UPDATE allowed values
CREATE POLICY tenant_isolation_documents ON documents
    USING (
        current_setting('app.tenant_id', true) IS NOT NULL
        AND tenant_id = current_setting('app.tenant_id', true)::uuid
    )
    WITH CHECK (
        current_setting('app.tenant_id', true) IS NOT NULL
        AND tenant_id = current_setting('app.tenant_id', true)::uuid
    );

-- Doc nodes: same pattern
CREATE POLICY tenant_isolation_nodes ON doc_nodes
    USING (
        current_setting('app.tenant_id', true) IS NOT NULL
        AND tenant_id = current_setting('app.tenant_id', true)::uuid
    )
    WITH CHECK (
        current_setting('app.tenant_id', true) IS NOT NULL
        AND tenant_id = current_setting('app.tenant_id', true)::uuid
    );

-- Chat sessions
CREATE POLICY tenant_isolation_sessions ON chat_sessions
    USING (
        current_setting('app.tenant_id', true) IS NOT NULL
        AND tenant_id = current_setting('app.tenant_id', true)::uuid
    )
    WITH CHECK (
        current_setting('app.tenant_id', true) IS NOT NULL
        AND tenant_id = current_setting('app.tenant_id', true)::uuid
    );

-- Chat messages
CREATE POLICY tenant_isolation_messages ON chat_messages
    USING (
        current_setting('app.tenant_id', true) IS NOT NULL
        AND tenant_id = current_setting('app.tenant_id', true)::uuid
    )
    WITH CHECK (
        current_setting('app.tenant_id', true) IS NOT NULL
        AND tenant_id = current_setting('app.tenant_id', true)::uuid
    );

CREATE POLICY tenant_isolation_users ON users
    USING (
        current_setting('app.tenant_id', true) IS NOT NULL
        AND tenant_id = current_setting('app.tenant_id', true)::uuid
    )
    WITH CHECK (
        current_setting('app.tenant_id', true) IS NOT NULL
        AND tenant_id = current_setting('app.tenant_id', true)::uuid
    );
```

> **CRITICAL:** `WITH CHECK` prevents a malicious client from INSERTing/UPDATEing rows belonging to another tenant. Without it, RLS only protects reads.

### Tenant Context Injection (Python)

```python
from sqlalchemy import text

async def set_tenant_context(db: AsyncSession, tenant_id: str):
    """Inject tenant_id into the current transaction for RLS enforcement."""
    import uuid

    uuid.UUID(tenant_id)  # Raises ValueError if invalid
    await db.execute(
        text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
        {"tenant_id": tenant_id},
    )
```

This is called at the start of every request after JWT validation. **All subsequent queries automatically filter by tenant_id** — no application-level filtering needed.

## Index Strategy

| Index | Type | Column(s) | Purpose |
|-------|------|-----------|---------|
| `idx_documents_tenant` | B-tree | `tenant_id` | Fast tenant filtering |
| `idx_documents_tenant_sha256` | B-tree | `tenant_id, sha256` | Dedup pre-check within tenant |
| `idx_documents_tenant_status` | B-tree | `tenant_id, status` | Filter by status per tenant |
| `uq_documents_tenant_version` | Unique B-tree | `tenant_id, file_name, version` | Prevent duplicate version numbers |
| `idx_documents_deleted_at` | B-tree (partial) | `deleted_at` WHERE `deleted_at IS NOT NULL` | Soft delete queries |
| `idx_nodes_tenant_doc` | B-tree | `tenant_id, document_id` | Nodes per document |
| `idx_nodes_parent` | B-tree | `parent_id` | Tree traversal |
| `idx_nodes_heading_embedding` | HNSW | `heading_embedding` | Semantic heading search |
| `idx_messages_session` | B-tree | `session_id` | Chat history retrieval |
| `idx_messages_tenant_created` | B-tree | `tenant_id, created_at` | Time-range queries |

### HNSW Index Configuration

```sql
CREATE INDEX idx_nodes_heading_embedding ON doc_nodes
    USING hnsw (heading_embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
```

## Soft Delete vs Hard Delete Lifecycle

| Phase | Action | Timing |
|-------|--------|--------|
| **Soft Delete** | `deleted_at = now()` | Immediate on user request |
| **Router Exclusion** | `WHERE deleted_at IS NULL` in all queries | Immediate |
| **Citation Display** | Show `[Đã xóa]` for cited deleted docs | Immediate |
| **Hard Delete** | `DELETE FROM ... WHERE deleted_at < now() - 30 days` | Async Celery task, nightly |
| **Cascade** | doc_nodes → chat_messages (orphan cleanup) | With hard delete |

### Soft Delete Query Pattern

```python
# Always exclude soft-deleted documents
query = select(Document).where(
    Document.tenant_id == tenant_id,
    Document.deleted_at.is_(None)
)
```

## init.sql (Database Bootstrap)

```sql
-- `ragbot` already exists because POSTGRES_DB=ragbot
CREATE DATABASE langfuse;

-- Connect to ragbot
\c ragbot

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create tables (see schema above)
-- ...

-- Enable RLS
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE doc_nodes ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

-- Create policies (see RLS section above)
-- ...

-- Create indexes (see Index Strategy above)
-- ...
```

> Application connections must **not** use a role with `BYPASSRLS`. Reserve elevated roles for offline migration or break-glass administration only.

## Implementation Invariants

| Rule | Requirement |
|------|-------------|
| `tenant_id` | MUST exist on every tenant-scoped table and MUST be indexed for primary access paths |
| RLS | MUST be enabled and forced on every tenant-scoped table before production use |
| Soft delete | MUST use `deleted_at`; application code MUST NOT physically delete user-facing rows synchronously |
| Versioning | MUST create a new document version for changed content; MUST NOT overwrite prior content in place |
| Dedup | MUST check SHA-256 before parse; MUST support node-level duplicate marking after parse |
| FK behavior | MUST prefer `ON DELETE CASCADE` or `ON DELETE SET NULL` explicitly; MUST NOT rely on implicit database defaults |

## AI Coding Guardrails

| Do | Do not |
|----|--------|
| Reuse existing table names and columns exactly as documented | Invent new tenant-scoped tables without `tenant_id` |
| Use transaction-scoped tenant context | Filter only in application code and skip RLS |
| Add migrations that preserve existing data | Replace schema wholesale for minor changes |
