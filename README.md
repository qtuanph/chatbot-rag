<div align="center">

# chatbot-rag

**On-premise hierarchical RAG chatbot for Vietnamese enterprise documents**

Self-hosted. No cloud lock-in. Complete control over your data.

[![Docker](https://img.shields.io/badge/Docker-Compose-blue?logo=docker&logoColor=white)](https://docs.docker.com/compose/)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Next.js](https://img.shields.io/badge/Next.js-16-black?logo=next.js&logoColor=white)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.136-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![LlamaIndex](https://img.shields.io/badge/LlamaIndex-0.14-7B3FE4?logo=llamaindex&logoColor=white)](https://www.llamaindex.ai/)
[![Qdrant](https://img.shields.io/badge/Qdrant-1.18-DC2D5E?logo=qdrant&logoColor=white)](https://qdrant.tech/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-18-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

</div>

---

## Features

| Feature | Description |
|---------|-------------|
| **Hierarchical Indexing** | Docs → Sections (H1–H6) → Chunks via LlamaIndex `IngestionPipeline`. Preserves document structure for accurate context retrieval. |
| **LlamaIndex RAG** | `VectorStoreIndex` with hybrid search (dense + Qdrant native BM25 RRF) + switchable reranker (TEI or NVIDIA NIM). |
| **TEI Inference** | Dedicated TEI containers: `gte-multilingual-base` (embedding, 768-dim) + `gte-multilingual-reranker-base` (reranker). GPU-optimized. |
| **Switchable Reranker** | Managed via SQLite `/admin/providers`: activate `TEI (Local)` or `NVIDIA NIM` at runtime (no redeploy needed). |
| **Smart OCR** | LlamaParse cloud OCR for PDF/DOCX. Local parser for .md/.txt (no API call). |
| **Async Ingestion** | Upload returns `task_id` instantly. Background parsing/indexing via Celery with live progress. |
| **SSE Chat** | Real-time streaming via `OpenAILike.astream_chat()` through 9Router, with citations grouped by document. |
| **User Memory** | Persistent per-user preferences, corrections, and facts injected into AI context. |
| **9Router AI Gateway** | OpenAI-compatible proxy with 3-tier fallback, RTK token saver, and usage tracking. |
| **3-Layer Cache** | LLM Response + Semantic + Query Embedding — fast hit rates, reduced latency. |

## Quick Start

```bash
# 1. Configure
cp .env.example .env
# Edit .env: set JWT_SECRET, DATABASE_URL, S3_SECRET_KEY, HF_TOKEN

# 2. Build & start
DOCKER_BUILDKIT=1 docker compose up -d --build

# 3. Access
open http://localhost
```

**First startup**: Takes 3-5 minutes to download TEI models (~2.7GB total). Subsequent restarts reuse cache.

### Default Credentials

```
Username: admin
Password: abc123
```

### Services

| Service | URL |
|---------|-----|
| Web App | http://localhost |
| API Health | http://localhost/api/v1/health |
| Qdrant Dashboard | http://localhost:6333/dashboard |
| RustFS Console | http://localhost:9001 |
| 9Router Dashboard | http://localhost:2908 |

## Architecture

```
Browser → Traefik (:80) → Next.js (webapp) → FastAPI (api)
                                          ↕
                          Celery Workers · Qdrant · PostgreSQL · Redis · RustFS
                                          ↕
                    ai-embedding (TEI) · ai-reranker (TEI) · ai-proxy (9Router)
                                          ↕
                                LlamaIndex Core
                          Settings.embed_model · Settings.llm
                          VectorStoreIndex · IngestionPipeline
```

### Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 16 + shadcn/ui v4 + next-auth v5 |
| Backend | FastAPI + Celery + SQLAlchemy |
| RAG Framework | **LlamaIndex** (`VectorStoreIndex`, `IngestionPipeline`, `QdrantVectorStore`, `TextEmbeddingsInference`, `OpenAILike`) |
| Database | PostgreSQL 18 |
| Cache / Queue | Redis 8 |
| Vector Search | Qdrant (dense + native BM25 hybrid) |
| Embedding | TEI — `Alibaba-NLP/gte-multilingual-base` (768-dim, 32k ctx) |
| Reranker | TEI — `Alibaba-NLP/gte-multilingual-reranker-base`, or NVIDIA NIM `nvidia/llama-nemotron-rerank-1b-v2` |
| LLM Provider | 9Router (OpenAI-compatible, port 2908) |
| OCR | LlamaParse (cloud) + local MarkdownNodeParser |
| Reverse Proxy | Traefik v3.7 |

### Retrieval Pipeline

```
Query → Cache Check (3 layers)
  → MISS: Embed (TEI) → Hybrid Search (Dense + Native BM25 RRF)
  → Rerank (TEI or NVIDIA) → Dedup → Full Section → LLM (SSE Stream)
```

## API Reference

All endpoints prefixed with `/api/v1`. Auth via JWT Bearer.

### Auth
| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/auth/login` | POST | public | JWT authentication |
| `/auth/logout` | POST | JWT | Revoke token |
| `/auth/me` | GET | JWT | Current user info |
| `/auth/users` | POST/GET | admin | User management |

### Documents
| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/documents/upload` | POST | admin | Upload → returns `task_id` |
| `/documents/status/{task_id}` | GET | JWT | Poll progress |
| `/documents/{id}` | DELETE | admin | Hard-delete |
| `/documents/{id}/rechunk` | POST | admin | Re-index from saved OCR |

### Chat
| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/chat/stream` | POST (SSE) | member | Chat with streaming |
| `/chat/sessions` | POST/GET | member | Session management |
| `/chat/messages` | GET | member | Get messages |

### Other
| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/memories` | CRUD | member | User memory management |
| `/analytics/stats` | GET | member | Usage statistics |
| `/health` | GET | public | Health check |

Full API docs: [`docs/3_API_CONTRACTS.md`](docs/3_API_CONTRACTS.md)

## Configuration

All settings via environment variables. See `app/core/config.py` for defaults.

### Key Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AI_EMBEDDING_URL` | `http://ai-embedding:80` | TEI embedding endpoint |
| `AI_RERANKER_URL` | `http://ai-reranker:80` | TEI reranker endpoint |
| `RERANKER_BACKEND` | `tei` | Legacy fallback only. Runtime reranker selection is managed via SQLite `/admin/providers`. |
| `NVIDIA_API_KEY` | — | Required when `RERANKER_BACKEND=nvidia` |
| `AI_PROXY_URL` | `http://ai-proxy:2908` | 9Router endpoint |
| `EMBEDDING_HF_MODEL` | `Alibaba-NLP/gte-multilingual-base` | Embedding model |
| `AI_MAX_HISTORY_MESSAGES` | `6` | Messages sent to LLM per turn |
| `RETRIEVAL_RERANK_TOP_K` | `10` | Candidates for reranker |

Full config reference: [`docs/7_CURRENT_SETTINGS.json`](docs/7_CURRENT_SETTINGS.json)

## Documentation

| Topic | File |
|-------|------|
| Dev guidelines | [`AGENTS.md`](AGENTS.md) |
| Architecture & data model | [`docs/1_ARCHITECTURE.md`](docs/1_ARCHITECTURE.md) |
| Workflows (ingestion, chat, delete, audit, analytics) | [`docs/2_WORKFLOWS.json`](docs/2_WORKFLOWS.json) |
| API contracts & security | [`docs/3_API_CONTRACTS.md`](docs/3_API_CONTRACTS.md) |
| Deployment & observability | [`docs/4_DEPLOYMENT.md`](docs/4_DEPLOYMENT.md) |
| Current settings (all defaults) | [`docs/7_CURRENT_SETTINGS.json`](docs/7_CURRENT_SETTINGS.json) |
| Known issues | [`docs/6_KNOWN_ISSUES.json`](docs/6_KNOWN_ISSUES.json) |

## Contributing

1. Read [`AGENTS.md`](AGENTS.md) for dev guidelines
2. Create a feature branch (`git checkout -b feat/your-feature`)
3. Commit using [Conventional Commits](https://www.conventionalcommits.org/)
4. Push and open a Pull Request

All changes must pass linting:
```bash
python -m black app --line-length=120
python -m flake8 app --select=F,E1,E2,E4,E9,W --ignore=E203,E501,W293,W292,W391,W503,W504
```

## License

[Apache 2.0](LICENSE)
