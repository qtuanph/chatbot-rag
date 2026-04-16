# 06 — Deployment and Observability

Status: deployment and operations baseline — updated to reflect Next.js 16 frontend.

## Deployment Topology

Primary runtime uses Docker Compose with the following services:

- api (FastAPI) — port 8000
- webapp (Next.js 16) — port 3000
- worker (Celery)
- db (PostgreSQL 18)
- redis (broker/result/cache)
- rustfs (object storage)
- qdrant (vector retrieval store)
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

## Health and Readiness

| Service | Probe |
|---------|-------|
| API | /api/v1/health |
| Webapp | http://localhost:3000 |
| Worker | celery inspect ping |
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
