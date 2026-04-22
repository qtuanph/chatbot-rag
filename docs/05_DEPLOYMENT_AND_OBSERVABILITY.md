# 05 — Deployment and Observability

Status: deployment and operations baseline — updated to reflect worker architecture refactor.

## Deployment Topology

Primary runtime uses Docker Compose with the following services:

- nginx (reverse proxy) — **port 80 (public entry point)**
- api (FastAPI) — internal only (accessed via nginx)
- webapp (Next.js 16) — internal only (accessed via nginx)
- upload-pipeline (Celery GPU worker) — queues: ingestion, default
- cleanup-pipeline (Celery lightweight worker + beat) — queues: cleanup, default
- db (PostgreSQL 18) — internal only
- redis (broker/result/cache) — internal only
- rustfs (object storage) — internal only
- qdrant (vector retrieval store) — internal only
- vllm (optional on-prem profile)

All services are accessed through nginx on port 80. Direct port access is no longer the default.

## Storage Responsibilities

| Component | Role |
|-----------|------|
| PostgreSQL | system database: auth, roles, sessions, documents metadata, status, audit, **user memories** |
| Qdrant | retrieval database: node vectors and retrieval payload |
| RustFS | raw upload and artifact object storage |
| Redis | queue, lightweight runtime cache, **user memory cache (5min TTL)** |

PostgreSQL is not the primary retrieval context store in the new direction.

## Required Environment Baseline

| Variable | Purpose |
|----------|---------|
| DATABASE_URL | PostgreSQL connection |
| REDIS_URL | Redis connection |
| S3_* | object storage configuration |
| QDRANT_URL | qdrant endpoint |
| QDRANT_COLLECTION | vector collection |
| EMBEDDING_MODEL | embedding model selection |
| EMBEDDING_VECTOR_SIZE | Qdrant vector dimension (default 1024 for BAAI/bge-m3) |
| AI_PROVIDER | chat generation backend selector |
| NEXTAUTH_URL | public webapp base URL |
| NEXTAUTH_SECRET | next-auth signing secret |
| NEXT_PUBLIC_API_URL | browser-facing API base URL |
| API_INTERNAL_URL | server-side API URL inside docker network |

For Docker Compose deployments, keep webapp variables in root `.env` so backend and webapp share one env source of truth.

## Container Runtime Users

Both app images run as non-root users by default:

- `api` image: `qtuanph`
- `webapp` image: `nextapp`

Runtime users are created without hardcoded passwords in Dockerfiles. If interactive shell password auth is ever required for debugging, pass it via runtime env or secret injection, not image build layers.

Tree/detail views should reuse the existing Qdrant collection and read from payload only. They must not instantiate the embedding model just to derive vector size.

Tree overview endpoints must use PostgreSQL as the ordering source of truth. Qdrant should be used for retrieval payload and detail lookup only, not to determine page order.

## Deployment Modes

| Mode | Provider |
|------|----------|
| Demo mode | google adapter |
| On-prem mode | vllm profile |

Provider changes must not require API contract changes.

Compose defaults bind published ports to 127.0.0.1 so local dev works without exposing services to the wider network. Production deployments should still front services with an ingress/reverse proxy and explicit network policy.

## Health and Readiness

| Service | Probe |
|---------|-------|
| Nginx | `/nginx_status` (internal only, 127.0.0.1) |
| API | `/api/v1/health` (via nginx) — no Docker healthcheck (health checked on-demand via dashboard) |
| Webapp | proxied through nginx `/` |
| upload-pipeline | celery inspect ping |
| cleanup-pipeline | celery inspect ping |
| Workers dashboard | API health payload includes combined Celery worker status |
| PostgreSQL | pg_isready |
| Redis | redis-cli ping |
| Qdrant | /health |
| vLLM (optional) | /health |

Compose healthcheck cadence is 3 seconds interval with 5 second start_period — optimised for fast startup (~25s total).

## Observability Baseline

Track at least:

- request latency and error rate
- queue depth and task failures
- ingestion duration by stage (`uploaded`, `queued`, `download`, `parse`, `sections`, `persist`, `ready`/`failed`)
- document status drift (`status`, `status_stage`, `progress_percent`, `status_updated_at`)
- retrieval latency and hit count
- provider generation latency

## Backup and Recovery

| Data | Strategy |
|------|----------|
| PostgreSQL | periodic dump with retention |
| RustFS buckets | object sync backup |
| Qdrant storage volume | volume snapshot or backup policy |

Recovery priority:
1. PostgreSQL system state
2. RustFS raw uploads/artifacts
3. Qdrant vectors (rebuildable if raw docs + ingestion pipeline are intact)

## Nginx Reverse Proxy Configuration

Config: `ops/nginx/nginx.conf` | Image: `nginx:stable-alpine3.23-perl`

### Location Block Order (Critical)

```
1. /api/auth/         → webapp_frontend (NextAuth routes — MUST be before /api/)
2. /api/bep/          → webapp_frontend (API gateway proxy — browser calls, SSE, file upload)
3. /api/v1/chat/stream → api_backend (SSE streaming — unbuffered)
4. /api/               → api_backend (general API — rate limited)
5. /view/              → api_backend (demo UI)
6. /                   → webapp_frontend (Next.js app)
7. /_next/static/      → webapp_frontend (aggressive caching 365d)
```

### Key Features

| Feature | Config |
|---------|--------|
| SSE streaming | `proxy_buffering off; proxy_cache off; gzip off; chunked_transfer_encoding off` |
| API gateway proxy | `/api/bep/` → webapp_frontend — browser never calls backend directly |
| Connection pooling | `keepalive 32` on both upstreams |
| Rate limiting | `api_limit` 30r/s, `upload_limit` 2r/s |
| WebSocket/HMR | `map $http_upgrade $connection_upgrade` for Next.js hot reload |
| Security headers | `proxy_hide_header` prevents duplicate headers from backend |
| Security headers (Next.js) | X-Frame-Options DENY, HSTS, nosniff, Referrer-Policy via `next.config.ts` |
| Upload size | `client_max_body_size 50m` (matches MAX_UPLOAD_SIZE_MB) |
| Long timeout | `proxy_read_timeout 86400s` for SSE and HMR |
| Version hidden | `server_tokens off` |
