# 06 — Deployment and Observability

Status: deployment and operations baseline — updated to reflect worker architecture refactor.

## Deployment Topology

Primary runtime uses Docker Compose with the following services:

- api (FastAPI) — published on localhost only
- webapp (Next.js 16) — published on localhost only
- upload-pipeline (Celery GPU worker) — queues: ingestion, default
- cleanup-pipeline (Celery lightweight worker + beat) — queues: cleanup, default
- db (PostgreSQL 18) — published on localhost only
- redis (broker/result/cache) — published on localhost only
- rustfs (object storage) — published on localhost only
- qdrant (vector retrieval store) — published on localhost only
- vllm (optional on-prem profile)

## Storage Responsibilities

| Component | Role |
|-----------|------|
| PostgreSQL | system database: auth, roles, sessions, documents metadata, status, audit |
| Qdrant | retrieval database: node vectors and retrieval payload |
| RustFS | raw upload and artifact object storage |
| Redis | queue and lightweight runtime cache |

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
| API | /api/v1/health |
| Webapp | http://localhost:3000 |
| upload-pipeline | celery inspect ping |
| cleanup-pipeline | celery inspect ping |
| PostgreSQL | pg_isready |
| Redis | redis-cli ping |
| Qdrant | /health |
| vLLM (optional) | /health |

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
