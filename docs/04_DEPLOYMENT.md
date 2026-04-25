# 04 — Deployment and Observability

Docker topology, nginx configuration, environment, and health. Architecture in `01_ARCHITECTURE.md`.

## Deployment Topology

Docker Compose with these services:

| Service | Role | Access |
|---------|------|--------|
| nginx | Reverse proxy — **port 80 (public entry)** | Public |
| api | FastAPI backend | Internal via nginx |
| webapp | Next.js 16 frontend | Internal via nginx |
| upload-pipeline | Celery GPU worker — queues: ingestion, default | Internal |
| cleanup-pipeline | Celery lightweight worker + beat — queues: cleanup | Internal |
| db | PostgreSQL 18 | Internal |
| redis | Broker/result/cache | Internal |
| rustfs | Object storage | Internal |
| qdrant | Vector retrieval | Internal |
| vllm | Planned on-prem profile (adapter not enabled) | — |

All traffic through nginx on port 80. No direct port access.

## Container Runtime Users

| Image | User |
|-------|------|
| api | `qtuanph` (non-root) |
| webapp | `nextapp` (non-root) |

No hardcoded passwords in Dockerfiles. Debug passwords via runtime env/secrets.

## Required Environment Variables

| Variable | Purpose |
|----------|---------|
| DATABASE_URL | PostgreSQL connection |
| REDIS_URL | Redis connection |
| S3_* | Object storage configuration |
| QDRANT_URL | Qdrant endpoint |
| QDRANT_COLLECTION | Vector collection name |
| EMBEDDING_MODEL | Embedding model selection |
| EMBEDDING_VECTOR_SIZE | Qdrant dimension (default 1024) |
| AI_PROVIDER | Chat generation backend |
| NEXTAUTH_URL | Public webapp base URL |
| NEXTAUTH_SECRET | next-auth signing secret |
| NEXT_PUBLIC_API_URL | Browser API URL (`/api/bep`) |
| API_INTERNAL_URL | Server-side API URL (`http://api:8000/api/v1`) |

Docker Compose: keep webapp variables in root `.env` for single source of truth.

Compose defaults bind to 127.0.0.1. Production: front with ingress/reverse proxy + network policy.

## Nginx Configuration

Config: `ops/nginx/nginx.conf` | Image: `nginx:stable-alpine3.23-perl`

### Location Block Order (Critical)

```
1. /api/auth/         → webapp (NextAuth routes — MUST be before /api/)
2. /api/bep/          → webapp (API gateway proxy — browser calls, SSE, upload)
3. /api/v1/chat/stream → api_backend (SSE — unbuffered)
4. /api/               → api_backend (general API — rate limited)
5. /view/              → api_backend (demo UI)
6. /                   → webapp (Next.js app)
7. /_next/static/      → webapp (aggressive caching 365d)
```

### Key Features

| Feature | Config |
|---------|--------|
| SSE streaming | `proxy_buffering off; gzip off; chunked_transfer_encoding off` |
| API gateway | `/api/bep/` → webapp — browser never calls backend directly |
| Connection pooling | `keepalive 64` on both upstreams |
| Rate limiting | `api_limit` 100r/s burst=100, `upload_limit` 2r/s |
| SSE rate limit | `limit_req zone=api_limit burst=20 nodelay` on SSE endpoint |
| Proxy failover | `proxy_next_upstream error timeout http_502 http_503` |
| WebSocket/HMR | `map $http_upgrade $connection_upgrade` for Next.js hot reload |
| Upload size | `client_max_body_size 50m` (matches MAX_UPLOAD_SIZE_MB) |
| Long timeout | `proxy_read_timeout 86400s` for SSE and HMR |
| Version hidden | `server_tokens off` |

## Health and Readiness

| Service | Probe |
|---------|-------|
| nginx | `/nginx_status` (127.0.0.1 only) |
| API | `/api/v1/health` (via nginx) |
| Workers | celery inspect ping (included in API health payload) |
| PostgreSQL | pg_isready |
| Redis | redis-cli ping |
| Qdrant | /health |

Healthcheck cadence: 3s interval, 5s start_period. Startup ~25s.

## Connection Pool Sizing

| Service | Pool | Overflow | Per-Worker | Total (4 workers) |
|---------|------|----------|------------|-------------------|
| PostgreSQL (api) | 10 | 10 | 20 | 80 max |
| PostgreSQL (celery) | — | — | — | ~4 |
| httpx (Gemini) | 50 max conn | 10 keepalive | 50 | 50 (shared singleton) |
| Redis | per-instance | — | — | ~7 instances |

PostgreSQL: `pool_size=10, max_overflow=10, pool_timeout=30, pool_recycle=3600`. SQLAlchemy engine in `app/db/session.py`.

AI provider: singleton via `@lru_cache(maxsize=1)` in `app/adapters/ai/__init__.py`. One httpx.AsyncClient with `max_connections=50, keepalive_expiry=30`.

## Observability Baseline

Track: request latency, error rate, queue depth, task failures, ingestion duration by stage, retrieval latency, provider generation latency.

## Backup and Recovery

| Data | Strategy |
|------|----------|
| PostgreSQL | Periodic dump with retention |
| RustFS | Object sync backup |
| Qdrant | Volume snapshot (rebuildable from raw docs + pipeline) |

Recovery priority: PostgreSQL → RustFS → Qdrant (rebuildable).
