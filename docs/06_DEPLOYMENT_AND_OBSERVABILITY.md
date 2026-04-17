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
| AI_PROVIDER | chat generation backend selector |

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
- ingestion duration by stage (`uploaded`, `queued`, `download`, `parse`, `persist`, `ready`/`failed`)
- document status field drift (`status`, `status_stage`, `progress_percent`, `status_updated_at`)
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
