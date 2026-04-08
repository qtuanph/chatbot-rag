# 02 — Database and Project

> Status: **Single-project, self-hosted** deployment for one internal project. 
> All users share the same document library with role-based access control (admin / member).
> No customer-isolation layer; this deployment uses one shared project dataset.

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

- **Single Project**: One project, self-hosted on your infrastructure.
- **Shared Documents**: All authenticated users access the same document library.
- **Role-Based Access Control**: 
  - Admin: Full permissions (upload, delete, configure data sources)
  - Member: Chat and document search only
- **App-Level Authorization**: Access control is enforced in the application layer (JWT + role checks).
- **No Data Partition Layer**: Access control is user-role-based, not per-customer data partitioning.

## Document Flow

1. Upload file to MinIO.
2. Create `documents` row.
3. Worker extracts text or OCR.
4. Worker writes `doc_nodes` tree.
5. Document becomes `ready`.
