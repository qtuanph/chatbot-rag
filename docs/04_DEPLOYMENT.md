# 04 — Deployment and Observability

Docker topology, nginx configuration, environment, and health. Architecture in `01_ARCHITECTURE.md`.

## Deployment Topology

Docker Compose with these services:

| Service | Role | Access |
|---------|------|--------|
| nginx | Reverse proxy — **port 80 (public entry)** | Public |
| api | FastAPI backend | Internal via nginx |
| webapp | Next.js 16 frontend | Internal via nginx |
| butler | Celery multi worker — node-ingestion (solo, GPU) + node-default (prefork, CPU, beat) | Internal |
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
| REDIS_URL | Redis connection (DB 2 for app cache) |
| CELERY_BROKER_URL | Redis DB 0 (Celery broker) |
| CELERY_RESULT_BACKEND | Redis DB 1 (task results) |
| S3_* | Object storage configuration |
| QDRANT_URL | Qdrant endpoint |
| QDRANT_COLLECTION | Vector collection name |
| QDRANT_SEGMENT_NUMBER | Auto-set from `hnsw_m // 4` — segments processed in parallel |
| EMBEDDING_MODEL | Embedding model selection |
| EMBEDDING_VECTOR_SIZE | Qdrant dimension (default 1024) |
| AI_PROVIDER | Chat generation backend |
| AI_INPUT_COST_PER_1M | Input token cost per 1M tokens (default 0.0) |
| AI_OUTPUT_COST_PER_1M | Output token cost per 1M tokens (default 0.0) |
| NEXTAUTH_URL | Public webapp base URL |
| NEXTAUTH_SECRET | next-auth signing secret |
| NEXT_PUBLIC_API_URL | Browser API URL (`/api/bep`) |
| API_INTERNAL_URL | Server-side API URL (`http://api:8000/api/v1`) |
| REDIS_MAXMEMORY | Redis maxmemory (default 512mb) |
| CELERY_TASK_TIME_LIMIT | Task hard kill in seconds (default 1800) |
| CELERY_TASK_SOFT_TIME_LIMIT | Task soft kill in seconds (default 1500) |
| CELERY_WORKER_MAX_MEMORY_KB | Worker memory limit (default 1500000) |
| CELERY_MAX_TASKS_PER_CHILD | Recycle after N tasks (default 50) |
| AI_TEMPERATURE | Generation temperature (default 0.3) |
| AI_MAX_OUTPUT_TOKENS | Max output tokens (default 8192) |
| AI_MAX_HISTORY_MESSAGES | Multi-turn context window (default 20) |
| AI_STREAM_TIMEOUT | HTTP timeout for AI streaming (default 300s) |
| AI_HTTP_MAX_CONNECTIONS | httpx connection pool (default 50) |
| RATE_LIMIT_GLOBAL_RPM | Global rate limit, production only (default 300) |
| RATE_LIMIT_RELAXED_MODE | Bypass rate limiting when true (default false) |
| RATE_LIMIT_RELAXED_FLOOR | Minimum RPM even in relaxed mode (default 1000) |
| CHAT_HISTORY_LIMIT | Redis messagepack history cap (default 20) |
| CHAT_SESSION_TTL_DAYS | Session hard-delete TTL in days (default 30) |
| AUDIT_STREAM_ENABLED | Enable Redis Stream audit logging (default true) |
| AUDIT_STREAM_MAXLEN | Max entries retained in audit stream (default 50000) |
| AUDIT_STREAM_NAME | Redis Stream key for audit events (default `audit:stream`) |
| RETRIEVAL_SEMANTIC_CACHE_THRESHOLD | Cosine distance threshold for semantic cache hit (default 0.05) |
| RETRIEVAL_SEMANTIC_CACHE_TTL | Semantic cache entry TTL in seconds (default 86400) |
| MEMORY_CACHE_TTL | User memory Redis cache TTL in seconds (default 300) |
| EMBEDDING_QUERY_PREFIX | Prefix added to query text before embedding (optional) |
| EMBEDDING_PASSAGE_PREFIX | Prefix added to passage text before embedding (optional) |

Docker Compose: keep webapp variables in root `.env` for single source of truth. Butler worker routing configured in `ops/entrypoint-worker.sh` (no env vars needed).

Compose defaults bind to 127.0.0.1. Production: front with ingress/reverse proxy + network policy.

## Nginx Configuration

Config: `ops/nginx/nginx.conf` | Image: `nginx:stable-alpine`

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
| Proxy failover | `proxy_next_upstream error timeout http_502 http_503` with `proxy_next_upstream_non_idempotent off` so POST/PUT/PATCH/DELETE are not replayed by nginx |
| WebSocket/HMR | `map $http_upgrade $connection_upgrade` for Next.js hot reload |
| Upload size | `client_max_body_size 50m` (matches MAX_UPLOAD_SIZE_MB) |
| Long timeout | `proxy_read_timeout 86400s` for SSE and HMR |
| Version hidden | `server_tokens off` |

## Health and Readiness

| Service | Probe |
|---------|-------|
| nginx | No container healthcheck (reverse proxy layer) |
| API | `/api/v1/health` (via nginx and container healthcheck, 30s interval, 30s start_period) |
| Butler | celery inspect ping (30s interval, 60s start_period) |
| Workers | celery inspect ping (included in API health payload) |
| PostgreSQL | pg_isready (3s interval) |
| Redis | redis-cli ping (3s interval) |
| Qdrant | TCP port 6333 check (3s interval) |

Healthcheck cadence varies by service: 3s for infrastructure (DB, Redis, Qdrant), 30s for application services (API, Butler).

## Connection Pool Sizing

| Service | Pool | Overflow | Notes |
|---------|------|----------|-------|
| PostgreSQL (api) | `hardware.db_pool_size` | `hardware.db_max_overflow` | Auto-scales: `max(20, min(100, 250/workers))` |
| PostgreSQL (celery) | — | — | ~4 |
| httpx (Gemini) | `AI_HTTP_MAX_CONNECTIONS` (default 50) | `AI_HTTP_KEEPALIVE_CONNECTIONS` (default 10) | Shared singleton |
| Redis | per-instance | — | ~7 instances |

PostgreSQL: pool auto-calculated as `max(10, uvicorn_workers * 5)`. SQLAlchemy engine in `app/db/session.py` reads from `app/core/hardware.py`.

AI provider: singleton via `@lru_cache(maxsize=1)` in `app/adapters/ai/__init__.py`. httpx pool configurable via `AI_HTTP_MAX_CONNECTIONS` / `AI_HTTP_KEEPALIVE_CONNECTIONS`.

## Resource Limits

| Service | CPUs | Memory | Notes |
|---------|------|--------|-------|
| api | 4.0 | 6G | Docker deploy limits — increase for production |
| redis | — | `REDIS_MAXMEMORY` env var (default 512mb) | allkeys-lru eviction |
| butler | — | — | GPU device reserved |

## Hardware Auto-Detection

`app/core/hardware.py` — HardwareProfile singleton detected once at module load. **3-tier VRAM-aware scaling.**

| Mode | Condition | uvicorn workers | node-ingestion | node-default | Reason |
|------|-----------|-----------------|----------------|-------------|--------|
| TIGHT GPU | CUDA + VRAM headroom < 6GB | 1 | solo (1 task) | prefork min(cpu, 4) | Prevent VRAM duplication |
| COMFORTABLE GPU | CUDA + VRAM headroom ≥ 6GB | min(cpu, ram//2, 8) | solo (1 task) | prefork min(cpu, 8) | GPU safety + CPU parallelism |
| CPU only | No CUDA | min(cpu, ram//2, 8) | solo (1 task) | prefork min(cpu, 8) | Full throughput |

VRAM headroom = total VRAM − 2GB (embedding + reranker). GTX 1650 4GB → TIGHT. RTX 4090 24GB → COMFORTABLE.

Worker: `ops/entrypoint-worker.sh` runs `celery multi` with 2 nodes:
- **node-ingestion**: `pool=solo`, queues=ingestion, GPU. Embedding model load/unload per task → always sequential.
- **node-default**: `pool=prefork`, queues=cleanup,default, Beat scheduler. CPU-only tasks (chat, audit, memory) run in parallel.

## Redis Configuration

```
redis-server --maxmemory ${REDIS_MAXMEMORY:-512mb} --maxmemory-policy allkeys-lru --save 60 1000 --appendonly yes
```

| DB | Purpose |
|----|---------|
| 0 | Celery broker (task messages) |
| 1 | Celery result backend (task results) |
| 2 | App cache (query embedding cache, rate limits, chat history) |

Separation prevents `allkeys-lru` eviction from deleting broker task messages.

## Celery Worker Configuration

All values configurable via env vars. Defaults designed for dev laptop.

| Setting | Env Var | Default | Purpose |
|---------|---------|---------|---------|
| task_time_limit | CELERY_TASK_TIME_LIMIT | 1800s | Hard kill |
| task_soft_time_limit | CELERY_TASK_SOFT_TIME_LIMIT | 1500s | Graceful SoftTimeLimitExceeded |
| worker_max_memory_per_child | CELERY_WORKER_MAX_MEMORY_KB | 1,500,000 (1.5GB) | Kill child if RSS exceeded |
| visibility_timeout | CELERY_VISIBILITY_TIMEOUT | 7200s (2h) | Prevent Redis re-delivery |
| result_expires | CELERY_RESULT_EXPIRES | 86400s (24h) | Task result TTL |
| max_tasks_per_child | CELERY_MAX_TASKS_PER_CHILD | 50 | Recycle child after N tasks |
| retry_backoff (upload) | CELERY_RETRY_BACKOFF | 30s | Exponential backoff base |
| retry_backoff_max | CELERY_RETRY_BACKOFF_MAX | 600s | Max backoff |
| max_retries | CELERY_MAX_RETRIES | 3 | Transient failure recovery |
| broker_connection_retry_on_startup | — | true | Don't crash if Redis unavailable |
| worker_disable_rate_limits | — | true | Rate limit at API level |
| worker_prefetch_multiplier | — | 1 | Fair distribution |
| task_acks_late | — | true | ACK after completion |
| Queue routing | entrypoint script | ingestion,cleanup,default | `celery multi` with 2 nodes — node-ingestion (solo), node-default (prefork+Beat) |

### Beat Schedule (Periodic Tasks)

| Task | Schedule | Queue | Purpose |
|------|----------|-------|---------|
| `cleanup_old_chat_sessions_task` | Every 24h | cleanup | Hard-delete sessions older than `CHAT_SESSION_TTL_DAYS` (default 30) |
| `cleanup_orphaned_vectors_task` | Every 24h | cleanup | Remove Qdrant vectors without matching DB sections |
| `process_audit_stream` | Every 10s | default | Batch persist Redis Stream audit events to PostgreSQL (XREADGROUP consumer group) |
| `refresh_mv_daily_stats` | Every 5min | default | Refresh `mv_daily_stats` materialized view for analytics |

## Observability Baseline

Track: request latency, error rate, queue depth, task failures, ingestion duration by stage, retrieval latency, provider generation latency.

## Backup and Recovery

| Data | Strategy |
|------|----------|
| PostgreSQL | Periodic dump with retention |
| RustFS | Object sync backup |
| Qdrant | Volume snapshot (rebuildable from raw docs + pipeline) |

Recovery priority: PostgreSQL → RustFS → Qdrant (rebuildable).
