# 02 — Database and Project

Status: single-project data model with role-based authorization.

## Storage Split (Source of Truth)

| Layer | Technology | Responsibility |
|-------|------------|----------------|
| Relational metadata | PostgreSQL | users, roles, documents, sessions, audit, connector metadata |
| Vector index | Qdrant | node vectors + retrieval payload |
| Object storage | RustFS | raw uploads + ingestion artifacts |
| Queue/cache | Redis | Celery broker/backend, lightweight runtime mappings |

## Core PostgreSQL Tables

| Table | Purpose |
|------|---------|
| roles | role definitions (admin, member) |
| users | authenticated accounts |
| documents | uploaded file metadata, status, version, soft-delete |
| chat_sessions | conversation sessions |
| chat_messages | message history and citations payload |
| security_audit | audit trail for sensitive actions |
| data_sources | approved connector registry |
| data_source_schema_cache | connector schema metadata cache |
| data_source_query_audit | SQL connector query audit log |

## Project Scope Model

| Topic | Rule |
|-------|------|
| Project mode | One shared project dataset |
| Access model | JWT auth + role checks |
| Admin rights | upload, delete, manage connectors |
| Member rights | chat and retrieval only |
| Isolation model | role-based authorization, not tenant partitioning |

## Versioning and Soft Delete Policy

| Policy | Required behavior |
|--------|-------------------|
| Versioning | same filename with new content creates next version |
| Latest preference | retrieval should prioritize latest active version |
| Soft delete | set deleted marker; exclude from new retrieval |
| Historical integrity | prior chat history keeps old citations for audit |

## Ingestion Persistence Flow

1. Save upload to RustFS.
2. Insert documents row with pending status.
3. Worker parses with Docling and LlamaIndex.
4. Persist vectors and node payload in Qdrant.
5. Save ingestion artifact metadata in the document row.
6. Mark document ready or failed.
