# 02 — Database and Project

> Status: project-only database design for one internal deployment. No SaaS tenancy, no tenant routing.

## Core Tables

| Table | Purpose |
|------|---------|
| `roles` | DB-backed account roles (`admin`, `member`) |
| `users` | Login accounts stored in DB |
| `documents` | Uploaded files and processing state |
| `doc_nodes` | Hierarchical document tree for RAG |
| `chat_sessions` | Chat sessions for the project |
| `chat_messages` | Chat messages and citations |
| `data_sources` | Future connector registry |
| `data_source_schema_cache` | Future schema cache |
| `data_source_query_audit` | Future query audit |

## Project Model

- This repository is for one internal project deployment.
- There is no customer tenancy layer.
- Authentication is DB-backed.
- Authorization is role-backed (`admin` and `member`).

## RLS

- Not used in this project-only model.
- Access control is handled by JWT auth and role checks.

## Document Flow

1. Upload file to MinIO.
2. Create `documents` row.
3. Worker extracts text or OCR.
4. Worker writes `doc_nodes` tree.
5. Document becomes `ready`.
