# chatbot-rag

**Docker-first, single-project hierarchical RAG chatbot** for Vietnamese enterprise documents.

> Deployment: Pure Docker. Self-hosted on your infrastructure. One project, shared document library, role-based access (admin / member).

## What Exists

- FastAPI backend with async ingestion pipeline
- Celery worker for asynchronous document parsing
- PostgreSQL + Redis + RustFS + Qdrant via docker-compose
- S3-compatible object storage (RustFS) for uploaded files
- Optional `vllm` service (onprem profile) for local LLM inference
- Multi-format ingestion: PDF, scanned PDF, images, DOCX, XLSX, Markdown, plain text
- Docling-first document extraction with deterministic fallback path
- Hierarchical document indexing: document → chapters → sections → subsections
- Weighted retrieval with parent context injection

## Database Initialization

Database schema and seed data are initialized automatically at container startup:

- **Location**: [ops/init.sql](ops/init.sql) (comprehensive single-file initialization)
- **Mounted by docker-compose**: `./ops/init.sql:/docker-entrypoint-initdb.d/init.sql:ro`
- **Execution**: PostgreSQL automatically runs SQL files in `/docker-entrypoint-initdb.d/` on first startup
- **What it creates**:
  - UUID extension (`pgcrypto`, `uuid-ossp`)
   - 9 core tables: roles, users, documents, chat_sessions, chat_messages, data_sources, data_source_schema_cache, data_source_query_audit, security_audit
   - Indexes on document/session/audit lookups
  - Automatic `updated_at` triggers
   - Seed users: admin/member (password: `abc123`)

No Alembic migrations needed. Database is idempotent and initialized from a single `.sql` file.

## Project Structure

```text
chatbot-rag/
├── AGENTS.md
├── README.md
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── app/
│   ├── main.py
│   ├── worker.py
│   ├── adapters/
│   │   ├── base.py                        # Shared adapter contracts
│   │   ├── ai/                            # LLM provider adapters
│   │   ├── parsers/                       # Docling + Classic parser adapters
│   │   ├── embeddings/                    # Gemini embedding adapter (online)
│   │   └── vector_stores/                 # Qdrant vector store adapter
│   ├── api/
│   │   ├── deps.py
│   │   └── routes/
│   ├── core/
│   │   ├── config.py
│   │   ├── celery_app.py
│   │   └── exceptions.py
│   ├── db/
│   ├── models/
│   ├── schemas/
│   └── services/
│       ├── ingestion/
│       │   ├── parser_manager.py
│       │   ├── hierarchy_validator.py
│       │   └── pipeline.py
│       ├── storage/
│       │   ├── __init__.py
│       │   └── document_store.py
│       ├── rag.py
│       ├── chat_store.py
│       ├── auth.py
│       ├── audit.py
│       ├── health.py
│       ├── registry.py
│       ├── throttle.py
│       └── token_blacklist.py
├── docs/
├── ops/
│   └── init.sql
└── tests/
```

## Storage Choice

- Uploaded files are stored in `RustFS`, not inside the git project and not as a local app folder source-of-truth.
- Reason: closer to production behavior, easier debugging of object-storage flows, cleaner future migration to S3-compatible deployments.
- RustFS API: `http://localhost:9000`
- RustFS console: `http://localhost:9001`

## LLM Configuration

### Current Setup (Production Demo)
- **AI Provider**: Google AI Studio (cloud-based)
- **Model**: Gemini 2.5 Flash
- **Configuration**: `AI_PROVIDER=google` in `.env`
- **Why**: Minimal resource requirements, immediate production-ready demonstration for stakeholders

### Future vLLM On-Premises Upgrade

When you have GPU hardware available, enable local inference:

#### Phase 1: Enable vLLM Service
1. Uncomment the `vllm` service in `docker-compose.yml` (lines ~125-160)
2. Optionally add HuggingFace model cache volume to persist downloaded models:
   ```yaml
   volumes:
     - hf_cache:/root/.cache/huggingface
   
   volumes:
     hf_cache:
   ```
3. Change `.env`: `AI_PROVIDER=vllm` (or keep `google` as fallback)
4. Start with profile: `docker compose --profile onprem up -d`

#### Phase 2: Scale Model Capacity (Optional)
Current default: `Qwen/Qwen2.5-7B-Instruct-AWQ` (7B parameters, lighter)

To upgrade to larger model in future, modify docker-compose.yml vLLM command:
```yaml
command: >
  --model Qwen/Qwen2.5-14B-Instruct-AWQ
  --quantization awq
  --host 0.0.0.0
  --port 8000
```

#### Hardware Requirements
- **Minimum**: NVIDIA GPU with 12GB VRAM
- **Recommended**: NVIDIA GPU with 16GB+ VRAM
- **Disk**: 8GB+ for model cache (persistent with volume)
- **Startup**: 5-15 minutes first run (model download), ~30 seconds with cached volume

#### Fallback Strategy
- Configure both providers in `.env`: `AI_PROVIDER=google` (fallback)
- App automatically routes to working provider if one fails
- Healthcheck includes vLLM when service is active

## Local Paths and Access

### Connection Details

| What | Value |
|------|-------|
| PostgreSQL host | `localhost:5432` |
| PostgreSQL DB | `ragbot` |
| PostgreSQL admin user | `db-admin` (for schema management) |
| PostgreSQL app user | `app_rw` (app runtime) |
| PostgreSQL password | set `POSTGRES_PASSWORD` / `APP_DB_PASSWORD` in `.env` |
| RedisHost | `localhost:6379` |
| RustFS API | `localhost:9000` |
| RustFS Console | `localhost:9001` |
| RustFS credentials | `rustfs` / set `S3_SECRET_KEY` in `.env` |

### Storage

- **Uploaded files**: Stored in RustFS bucket `rag-documents` (not local disk)
- **Object keys**: `s3://rag-documents/<document_id>/<filename>`
- **Local test files**: Use any temp path on your machine, upload via `POST /api/v1/upload`

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
curl http://localhost:8000/api/v1/health
```

### Service Endpoints

| Service | URL |
|---------|-----|
| **API** | `http://localhost:8000` |
| **OpenAPI Docs** | `http://localhost:8000/docs` |
| **RustFS S3 API** | `http://localhost:9000` |
| **RustFS Web Console** | `http://localhost:9001` |
| **Health Check** | `http://localhost:8000/api/v1/health` |

### Default Login Credentials (Development)

```
Username: admin
Password: abc123

Username: member
Password: abc123
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
- **Ingestion**: Docling-first on-prem parsing to Markdown, then LlamaIndex hierarchical node building, with the classic parser kept only as fallback.
- **Docling extraction**: Upload parsing is Docling-first and provider-agnostic.
- **Ingestion engine**: `INGESTION_ENGINE=docling|classic` (`docling` default) controls the upload pipeline.
- **Retrieval**: Weighted scoring with parent context injection, latest-version preference, and chapter-aware Q&A.
- **Next steps**: chat response latency, more sophisticated RAG evaluation, production telemetry.
- `/health` performs real dependency checks (PostgreSQL, Redis, RustFS, AI provider). Other business endpoints are currently scaffold implementations.
- `AI_PROVIDER` in `.env` controls LLM backend: `vllm` (on-prem default) or `google` (temporary demo mode).
- `API_V1_PREFIX` in `.env` controls the production namespace (default `/api/v1`).
- For temporary online testing, set `AI_PROVIDER=google` and provide `GOOGLE_API_KEY`.
- Optional key rotation/fallback: set `GOOGLE_API_KEYS` as comma-separated keys (keeps API contract unchanged while testing).

## Implemented Endpoints (Scaffold → Production)

| Endpoint | Method | Status | Notes |
|----------|--------|--------|-------|
| `/api/v1/health` | GET | ✅ Working | Real dependency checks |
| `/api/v1/auth/login` | POST | ✅ Working | Returns bearer access token |
| `/api/v1/auth/logout` | POST | ✅ Working | Revokes active token |
| `/api/v1/auth/users` | POST | ✅ Working | Creates a user (admin only) |
| `/api/v1/upload` | POST | ✅ Working | Enqueues Celery job; returns task_id |
| `/api/v1/status/{task_id}` | GET | ✅ Working | Returns normalized task/document progress |
| `/api/v1/chat` | POST | ✅ Working | Provider-driven chat (`vllm` on-prem default, `google` demo mode) |
| `/api/v1/documents` | GET | ✅ Working | Lists documents and current pipeline status |
| `/api/v1/documents/{id}` | GET | ✅ Working | Returns full document metadata/status |
- `DELETE /api/v1/documents/{document_id}` soft-deletes a document and removes the source object from storage.
- Worker ingestion now extracts text from PDF, scanned PDF, images, DOCX, and XLSX.
- Parsing uses the Docling-first pipeline with classic parser fallback.
- Indexed output is stored as hierarchical nodes for later retrieval.
- `POST /api/v1/chat` uses adapter-based provider selection from `AI_PROVIDER`.
- Public API contract is served under `/api/v1/*`.

## Upload Processing Workflow

When an admin uploads a file via `POST /api/v1/upload`, the system runs this pipeline:

1. **Guardrails at API layer**
   - Enforce admin role and upload rate limit.
   - Validate filename and max size (`MAX_UPLOAD_SIZE_MB`).

2. **Deduplication and versioning**
   - Compute SHA-256 for uploaded bytes.
   - Reject active duplicates (`409 duplicate`) when hash matches an existing non-deleted document.
   - Compute next version for same filename.

3. **Persist source file + document row**
   - Save original file to RustFS as `s3://<bucket>/<document_id>/<filename>`.
   - Insert `documents` row with `status=pending`, `status_stage=uploaded`, `progress_percent=1`.
   - Write upload audit log.

4. **Queue asynchronous ingestion**
   - Register `document_id <-> task_id` in Redis.
   - Enqueue Celery task `app.worker.parse_document_task`.
   - Update `documents` progress to `status_stage=queued`, `progress_percent=5`.
   - Return `202 Accepted` immediately with `task_id`, `document_id`, `status=queued`.

5. **Worker parsing and indexing**
   - Download file from RustFS (`status_stage=download`, `progress_percent=10`).
   - Convert the file locally with Docling into Markdown (`status_stage=parse`, `progress_percent=40`).
   - Use LlamaIndex `MarkdownNodeParser` to turn the Markdown into hierarchical nodes.
   - Build hierarchical retrieval nodes for Qdrant (root + parent/child relationships).
   - If Docling or LlamaIndex fails, fall back to the classic parser so upload still completes when possible.
   - Validate extraction quality thresholds (`INGESTION_MIN_NON_EMPTY_NODES`, `INGESTION_MIN_TOTAL_TEXT_CHARS`).
   - Save ingestion artifact into `documents.metadata.ingestion_artifact`.
   - Persist metadata (`status_stage=persist`, `progress_percent=75`).
   - Mark document `ready` on success (`progress_percent=100`) or `failed` + `parse_error` on failure.

6. **Client polling**
   - Use `GET /api/v1/status/{task_id}` until status is `ready` or `failed`.

### Document Status Lifecycle

- `status` (coarse): `pending | processing | ready | failed | deleted`
- `status_stage` (detailed): `uploaded | queued | enqueue_failed | download | parse | persist | ready | failed | deleted`
- `progress_percent`: `0..100`

7. **Retrieval behavior after ready**
   - Chat retrieval excludes soft-deleted documents.
   - Retrieval prefers latest document version per filename.

## Text Extraction And AI Usage

Short answer: **yes, extraction uses local AI/ML processing**, but **does not call the chat LLM provider during upload**.

1. **During upload ingestion**
   - Docling is the primary local parser for upload.
   - LlamaIndex turns the Docling Markdown output into hierarchical nodes.
   - The classic parser path is fallback only.
   - No call to `AI_PROVIDER` (`google`/`vllm`) in the upload pipeline.

2. **During chat answering**
   - `AI_PROVIDER` is used in `POST /api/v1/chat` to generate final answer from retrieved context.
   - Citations come from indexed hierarchical nodes stored in Qdrant.

## Chat Behavior Target

- Keep chat history minimal.
- Use one active chat session at a time for the project.
- Creating a new chat should clear the active session history.
- Retain messages for 24h only if you need temporary debugging/audit.

## Chat Storage Today

- Active chat state is stored in Redis with per-user key scoping.
- Session ownership is checked against `chat_sessions.user_id` to prevent cross-user access.
- Messages are kept with short TTL in Redis for runtime context and persisted to DB as assistant replies.
- This remains lightweight for local development and debugging.

## Database Model

The database keeps three main kinds of data:

- `roles`: stores account permissions in DB
- `documents`: one row per uploaded file, including file path, hash, size, and status
- Qdrant: the extracted document tree and retrieval payload used for hierarchical RAG

Simple flow:

```text
Upload file
   |
   v
RustFS object
   |
   v
documents row
   |
   v
worker parse
   |
   v
hierarchical nodes in Qdrant
   |
   v
ready for RAG
```

1. Upload file to RustFS
2. Create a `documents` row with `status=pending`
3. Worker parses the file
4. Worker writes hierarchical nodes to Qdrant
5. `documents.status` becomes `ready`

For deletes:

- `documents.deleted_at` is set
- related retrieval nodes remain in Qdrant for historical reference but are excluded from new retrieval via document soft-delete filters
- the file is deleted from RustFS

The rest of the tables support auth, chat history, and future data connectors.

## Auth And Roles

- No public self-signup.
- Admin users manage account creation.
- Admin and member accounts are stored in the database.
- Roles:
  - `admin`: can create users and upload files
  - `member`: can only chat with AI

Protected routes:

- `POST /api/v1/upload` requires `admin`
- `POST /api/v1/auth/users` requires `admin`
- `POST /api/v1/chat` requires a valid JWT

Login uses the DB-backed project accounts plus username/password.
