# chatbot-rag

Docker-first backend for a single-project hierarchical RAG chatbot.

> Current repo status: Docker-first backend for one internal project with async ingestion, OCR fallback, and hierarchical document tree indexing.

## What Exists

- FastAPI backend scaffold
- Celery worker scaffold
- PostgreSQL + Redis + MinIO via Docker Compose
- S3-compatible object storage for uploaded files
- Optional `vllm` service behind the `onprem` profile
- Multi-format ingestion foundation for PDF, scanned PDF, images, DOCX, and XLSX
- OCR fallback path for image-only pages and scans
- Hierarchical node indexing in PostgreSQL for document → page → section retrieval

## Project Structure

```text
chatbot-rag/
|-- .dockerignore
|-- AGENTS.md
|-- alembic.ini
|-- Dockerfile
|-- .gitignore
|-- README.md
|-- docker-compose.yml
|-- requirements.txt
|-- .env.example
|-- app/
|   |-- __init__.py
|   |-- main.py
|   |-- worker.py
|   |-- adapters/
|   |   |-- __init__.py
|   |   `-- ai/
|   |       |-- __init__.py
|   |       `-- base.py
|   |-- api/
|   |   |-- __init__.py
|   |   `-- routes/
|   |       |-- __init__.py
|   |       |-- chat.py
|   |       |-- documents.py
|   |       `-- health.py
|   |-- core/
|   |   |-- __init__.py
|   |   |-- celery_app.py
|   |   `-- config.py
|   |-- db/
|   |   |-- __init__.py
|   |   `-- base.py
|   |-- models/
|   |   `-- __init__.py
|   |-- schemas/
|   |   |-- __init__.py
|   |   |-- chat.py
|   |   `-- documents.py
|   `-- services/
|       |-- __init__.py
|       `-- storage.py
|-- alembic/
|   |-- README
|   |-- env.py
|   |-- script.py.mako
|   `-- versions/
|       |-- .gitkeep
|       `-- 20260407_000001_baseline_scaffold.py
|-- docs/
|   |-- 01_SYSTEM_ARCHITECTURE.md
|   |-- 02_DATABASE_AND_TENANCY.md
|   |-- 03_CORE_WORKFLOWS.md
|   |-- 04_API_CONTRACT_AND_SECURITY.md
|   |-- 05_RESOURCE_OPTIMIZATION_AND_EDGE_CASES.md
|   `-- 06_DEPLOYMENT_AND_OBSERVABILITY.md
`-- ops/
    `-- init.sql
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
| pgAdmin host | `localhost` |
| pgAdmin port | `5432` |
| pgAdmin database | `ragbot` |
| pgAdmin username | `ragbot` |
| pgAdmin password | `QuocTuanMaiDinh` |

### Local File Location

- There is no local upload directory source-of-truth.
- Uploaded files live in MinIO only.
- If you need a local test file for upload, use any temp path on your machine, then upload it through `POST /upload`.

## Run

1. Copy `.env.example` to `.env`
2. Start backend stack:

```bash
docker compose up --build
```

This also runs the one-shot `migrate` service before `api` and `worker` start.

3. Optional on-prem inference profile:

```bash
docker compose --profile onprem up --build
```

## Migrations

Run migrations with the one-shot migration service:

```bash
docker compose run --rm migrate
```

Create a new revision:

```bash
docker compose exec api python -m alembic revision -m "describe change"
```

If migrations fail during startup, fix the revision/code and rerun `docker compose run --rm migrate` before restarting app services.

## Scope

- This repo currently sets up the backend API and worker only.
- Frontend can be built later as a separate app consuming the backend REST/SSE API.
- Keep this structure section updated whenever files/folders are added, removed, or moved.

## Version Baseline

- Python: `3.12.11-slim`
- PostgreSQL: `17` via `pgvector/pgvector:pg17`
- Redis: `7.4-alpine`
- MinIO: `minio/minio:RELEASE.2025-09-07T16-13-09Z`

## Notes

- This is still an evolving backend, but ingestion now targets production-style document parsing and tree indexing.
- JWT auth, richer retrieval, and SSE chat flow remain the next big steps.
- Alembic is wired and ready; future schema changes should go through migrations instead of `ops/init.sql`.
- `ops/init.sql` remains as an intentionally empty placeholder for non-schema Postgres bootstrap only.
- `/health` now performs real DB, Redis, MinIO, and provider-configuration checks. Other business endpoints are still partial scaffold implementations.

## Implemented Today

- `GET /health` returns real dependency status and timestamp.
- `POST /upload` stores the file in MinIO and enqueues a Celery job.
- `GET /status/{task_id}` reads Celery task state and terminal result metadata.
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

Login uses the single project scope configured for this deployment plus email/password.
