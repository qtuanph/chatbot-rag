# chatbot-rag

**Docker-first, single-tenant hierarchical RAG chatbot** for Vietnamese enterprise documents.

> Deployment: Pure Docker. Self-hosted on your infrastructure. One project, shared document library, role-based access (admin / member).

## What Exists

- FastAPI backend with async ingestion pipeline
- Celery worker for document parsing and OCR
- PostgreSQL + Redis + MinIO (object storage) via docker-compose
- S3-compatible object storage (MinIO) for uploaded files
- Optional `vllm` service (onprem profile) for local LLM inference
- Multi-format ingestion: PDF, scanned PDF, images, DOCX, XLSX, Markdown, plain text
- Automatic OCR fallback for image-only pages and scanned documents
- Hierarchical document indexing: document → chapters → sections → subsections
- Weighted retrieval with parent context injection

## Database Initialization

Database schema and seed data are initialized automatically at container startup:

- **Location**: [ops/init.sql](ops/init.sql) (comprehensive single-file initialization)
- **Mounted by docker-compose**: `./ops/init.sql:/docker-entrypoint-initdb.d/init.sql:ro`
- **Execution**: PostgreSQL automatically runs SQL files in `/docker-entrypoint-initdb.d/` on first startup
- **What it creates**:
  - Vector extension for embeddings (`pgvector`)
  - UUID extension (`pgcrypto`, `uuid-ossp`)
  - 10 core tables: roles, users, documents, doc_nodes, chat_sessions, chat_messages, data_sources, data_source_schema_cache, data_source_query_audit
  - Indexes on document/node/session lookups
  - Automatic `updated_at` triggers
  - Seed users: admin/member (password: `password123`)

No Alembic migrations needed. Database is idempotent and initialized from a single `.sql` file.

## Project Structure

```text
chatbot-rag/
├── AGENTS.md                    # Build guide and project objectives
├── README.md                    # This file
├── Dockerfile                   # Application container (FastAPI + Celery worker)
├── docker-compose.yml           # Complete local stack (PostgreSQL, Redis, MinIO, app, worker)
├── requirements.txt             # Python dependencies
├── .env.example                 # Environment variables template
├── .gitignore
├── .dockerignore
│
├── app/                         # Application code
│   ├── main.py                  # FastAPI app entry point
│   ├── worker.py                # Celery task definitions
│   ├── adapters/
│   │   └── ai/                  # Provider adapters (Google AI, vLLM, etc.)
│   ├── api/
│   │   ├── deps.py              # Dependency injection (auth, DB session)
│   │   └── routes/
│   │       ├── auth.py          # Login/token endpoints
│   │       ├── chat.py          # /chat endpoint with SSE streaming
│   │       ├── documents.py     # /upload, /documents endpoints
│   │       └── health.py        # /health endpoint
│   ├── core/
│   │   ├── config.py            # Settings from .env
│   │   └── celery_app.py        # Celery configuration
│   ├── db/
│   │   ├── session.py           # SQLAlchemy session factory
│   │   ├── base.py              # Declarative base for models
│   │   └── types.py             # Custom column types (Vector)
│   ├── models/
│   │   ├── core.py              # DocNode, Document, User, ChatMessage ORM models
│   │   └── chat.py              # Chat-related models
│   ├── schemas/
│   │   ├── auth.py              # Login/token request/response schemas
│   │   ├── chat.py              # Chat request/response schemas
│   │   └── documents.py         # Document upload/metadata schemas
│   └── services/
│       ├── ingestion.py         # Document parsing (PDF, DOCX, images, etc.)
│       ├── ocr.py               # PaddleOCR integration
│       ├── rag.py               # RAG retrieval with hierarchical context injection
│       ├── chat_store.py        # Chat persistence
│       ├── auth.py              # JWT and password hashing
│       ├── storage.py           # MinIO S3 client wrapper
│       ├── audit.py             # Security audit logging
│       ├── health.py            # Service health checks
│       └── registry.py          # AI provider registry
│
├── docs/                        # Architecture and design
│   ├── 01_SYSTEM_ARCHITECTURE.md
│   ├── 02_DATABASE_AND_PROJECT.md
│   ├── 03_CORE_WORKFLOWS.md
│   ├── 04_API_CONTRACT_AND_SECURITY.md
│   ├── 05_RESOURCE_OPTIMIZATION_AND_EDGE_CASES.md
│   └── 06_DEPLOYMENT_AND_OBSERVABILITY.md
│
├── ops/                         # Deployment and database
│   └── init.sql                 # Single comprehensive database initialization
│
└── FILEUPLOADTEST/              # Manual testing folder (upload examples)
```

## Storage Choice

- Uploaded files are stored in `MinIO`, not inside the git project and not as a local app folder source-of-truth.
- Reason: closer to production behavior, easier debugging of object-storage flows, cleaner future migration to S3-compatible deployments.
- MinIO API: `http://localhost:9000`
- MinIO console: `http://localhost:9001`

## Local Paths And Access

| What | Where / How |
|------|-------------|
| Upload file storage | MinIO bucket `rag-documents` |
| Uploaded object key | `s3://rag-documents/<document_id>/<filename>` |
| PostgreSQL host | `localhost:5432` |
| PostgreSQL DB | `ragbot` |
| PostgreSQL admin user | `db-admin` |
| PostgreSQL admin password | `quoctuan` |
| PostgreSQL app user | `app_rw` |
| PostgreSQL app password | `quoctuan` |
| Redis host | `localhost:6379` |
| MinIO API | `localhost:9000` |
| MinIO Console | `localhost:9001` |
| MinIO access key | `minio-admin` |
| MinIO secret key | `quoctuan` |
## Local Paths and Access

### Connection Details

| What | Value |
|------|-------|
| PostgreSQL host | `localhost:5432` |
| PostgreSQL DB | `ragbot` |
| PostgreSQL admin user | `db-admin` (for schema management) |
| PostgreSQL app user | `app_rw` (app runtime) |
| PostgreSQL password | `quoctuan` (for both) |
| Redis host | `localhost:6379` |
| MinIO API | `localhost:9000` |
| MinIO Console | `localhost:9001` |
| MinIO credentials | `minioadmin` / `minioadmin` |

### Storage

- **Uploaded files**: Stored in MinIO bucket `rag-documents` (not local disk)
- **Object keys**: `s3://rag-documents/<document_id>/<filename>`
- **Local test files**: Use any temp path on your machine, upload via `POST /upload`

## Quick Start

### Prerequisites

- Docker and Docker Compose
- `.env` file (copy from `.env.example`)

### Run the Stack

```bash
# 1. Initialize environment
cp .env.example .env

# 2. Start all services (database, cache, storage, api, worker)
docker compose up --build

# 3. Wait for services to be healthy (30-60 seconds on first run)

# 4. Test API health
curl http://localhost:8000/health
```

### Service Endpoints

| Service | URL |
|---------|-----|
| **API** | `http://localhost:8000` |
| **OpenAPI Docs** | `http://localhost:8000/docs` |
| **MinIO S3 API** | `http://localhost:9000` |
| **MinIO Web Console** | `http://localhost:9001` |
| **Health Check** | `http://localhost:8000/health` |

### Default Login Credentials (Development)

```
Username: admin
Password: password123

Username: member
Password: password123
```

### Optional: Run with Local LLM (vLLM)

To use a locally-hosted LLM instead of Google AI Studio:

```bash
docker compose --profile onprem up --build
```

This starts the `vllm` service with Qwen 2.5 7B (quantized). Set `AI_PROVIDER=vllm` in `.env`.

## Database

The database is **automatically initialized** on first run via PostgreSQL's init hook:

- **Initialization file**: `ops/init.sql` (comprehens single-file schema)
- **Idempotent**: Safe to re-run; uses `CREATE IF NOT EXISTS` pattern
- **Seed data**: Default admin/member users and roles
- **No migrations needed**: Schema is complete at startup

### Troubleshooting Database Initialization

If the database doesn't initialize properly:

```bash
# 1. Stop all services
docker compose down

# 2. Remove PostgreSQL data volume
docker volume rm chatbot-rag_pgdata

# 3. Restart (will reinitialize from init.sql)
docker compose up --build
```

## Notes

- **Database**: Single `.sql` file initialization (`ops/init.sql`) via PostgreSQL init hook. No Alembic needed.
- **Ingestion**: Production-style multi-format parsing (PDF, DOCX, images, etc.) with OCR fallback and hierarchical indexing.
- **Retrieval**: Weighted scoring with parent context injection for chapter-aware Q&A.
- **Next steps**: SSE-based streaming chat flow, more sophisticated RAG evaluation, production telemetry.
- `/health` performs real dependency checks (PostgreSQL, Redis, MinIO, AI provider). Other business endpoints are currently scaffold implementations.
- `AI_PROVIDER` in `.env` controls LLM backend: `google` or `vllm` (must set `VLLM_BASE_URL` for local inference).

## Implemented Endpoints (Scaffold → Production)

| Endpoint | Method | Status | Notes |
|----------|--------|--------|-------|
| `/health` | GET | ✅ Working | Real dependency checks |
| `/auth/login` | POST | 🟡 Scaffold | Returns JWT + refresh token (not yet persisted) |
| `/upload` | POST | 🟡 Scaffold | Enqueues Celery job; returns task_id |
| `/status/{task_id}` | GET | 🟡 Scaffold | Returns Celery task state |
| `/chat` | POST | ⏳ TODO | SSE streaming (not yet implemented) |
| `/documents` | GET | ⏳ TODO | List user documents |
| `/documents/{id}` | GET | ⏳ TODO | Document details + nodes |
- Worker ingestion now extracts text from PDF, scanned PDF, images, DOCX, and XLSX.
- OCR fallback is used for image-only pages and scanned documents.
- Indexed output is stored as hierarchical nodes for later retrieval.
- `DELETE /documents/{document_id}` removes the uploaded object and marks the document deleted in DB.
- `POST /chat` is still a placeholder.

## Chat Behavior Target

- Keep chat history minimal.
- Use one active chat session at a time for the project.
- Creating a new chat should clear the active session history.
- Retain messages for 24h only if you need temporary debugging/audit.

## Chat Storage Today

- Active chat state is intended to be stored in Redis.
- The current `/chat` route still does not wire that in yet.
- Creating a new chat should call the reset path to remove the current session history.
- This is intentionally lightweight for local development and debugging.

## Database Model

The database keeps three main kinds of data:

- `roles`: stores account permissions in DB
- `documents`: one row per uploaded file, including file path, hash, size, and status
- `doc_nodes`: the extracted document tree used for hierarchical RAG

Simple flow:

```text
Upload file
   |
   v
MinIO object
   |
   v
documents row
   |
   v
worker parse/OCR
   |
   v
doc_nodes tree
   |
   v
ready for RAG
```

1. Upload file to MinIO
2. Create a `documents` row with `status=pending`
3. Worker parses/OCRs the file
4. Worker writes a tree of `doc_nodes`
5. `documents.status` becomes `ready`

For deletes:

- `documents.deleted_at` is set
- related `doc_nodes` are removed
- the file is deleted from MinIO

The rest of the tables support auth, chat history, and future data connectors.

## Auth And Roles

- No public self-signup.
- Admin users manage account creation.
- Admin and member accounts are stored in the database.
- Roles:
  - `admin`: can create users and upload files
  - `member`: can only chat with AI

Protected routes:

- `POST /upload` requires `admin`
- `POST /auth/users` requires `admin`
- `POST /chat` requires a valid JWT

Login uses the DB-backed project accounts plus username/password.
