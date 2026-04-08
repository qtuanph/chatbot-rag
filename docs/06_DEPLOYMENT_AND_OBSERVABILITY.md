# 06 — Deployment and Observability

> Status: target production deployment design. The current repository runs a smaller Docker scaffold and does not yet implement the full observability stack described here.

## Deployment Intent

| Intent | Required implementation outcome |
|--------|---------------------------------|
| "I do not want to install a lot of software manually" | The default developer and demo path must be `docker compose up` |
| "Use Google now, on-prem later" | One compose topology must support both modes via configuration/profile selection |
| "Use GPU later" | On-prem mode must include a dedicated `vllm` service ready for GPU-backed inference |
| "Keep it professional" | Healthchecks, persistence, backups, and telemetry are mandatory, not optional extras |

## Docker Compose Service Map

```yaml
version: "3.8"

services:
  api:
    build: ./api
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://user:pass@db:5432/ragbot
      - REDIS_URL=redis://redis:6379/0
      - AI_PROVIDER=${AI_PROVIDER:-google}
      - GOOGLE_API_KEY=${GOOGLE_API_KEY}
      - GOOGLE_MODEL=${GOOGLE_MODEL:-gemini-2.5-flash}
      - VLLM_BASE_URL=${VLLM_BASE_URL:-http://vllm:8000/v1}
      - EMBEDDING_MODEL=BAAI/bge-m3
      - RERANK_MODEL=BAAI/bge-reranker-base
      - JWT_SECRET=${JWT_SECRET}
    volumes:
      - uploads:/app/uploads
    mem_limit: 2g
    cpus: 2.0
    restart: unless-stopped
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=5)\""]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 15s

  worker:
    build: ./worker
    environment:
      - DATABASE_URL=postgresql+asyncpg://user:pass@db:5432/ragbot
      - REDIS_URL=redis://redis:6379/0
      - AI_PROVIDER=${AI_PROVIDER:-google}
      - GOOGLE_API_KEY=${GOOGLE_API_KEY}
      - GOOGLE_MODEL=${GOOGLE_MODEL:-gemini-2.5-flash}
      - VLLM_BASE_URL=${VLLM_BASE_URL:-http://vllm:8000/v1}
      - EMBEDDING_MODEL=BAAI/bge-m3
      - RERANK_MODEL=BAAI/bge-reranker-base
    volumes:
      - uploads:/app/uploads
    mem_limit: 8g
    cpus: 4.0
    restart: unless-stopped
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD-SHELL", "celery -A app.celery_app inspect ping -d celery@$$HOSTNAME"]
      interval: 30s
      timeout: 10s
      retries: 3

  vllm:
    image: vllm/vllm-openai:latest
    command: >
      --model Qwen/Qwen2.5-7B-Instruct-AWQ
      --quantization awq
      --gpu-memory-utilization 0.9
      --max-model-len 8192
      --host 0.0.0.0
      --port 8000
    ports:
      - "8001:8000"
    volumes:
      - hf_cache:/root/.cache/huggingface
    shm_size: "2g"
    mem_limit: 24g
    cpus: 6.0
    restart: unless-stopped
    profiles: ["onprem"]
    healthcheck:
      test: ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=5)\""]
      interval: 30s
      timeout: 10s
      retries: 5

  db:
    image: pgvector/pgvector:pg16
    ports:
      - "5432:5432"
    environment:
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
      - POSTGRES_DB=ragbot
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql
    mem_limit: 4g
    cpus: 2.0
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U user -d ragbot"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redisdata:/data
    mem_limit: 512m
    cpus: 1.0
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  otel-collector:
    image: otel/opentelemetry-collector-contrib:latest
    command: ["--config=/etc/otel-collector-config.yaml"]
    volumes:
      - ./ops/otel-collector-config.yaml:/etc/otel-collector-config.yaml:ro
    ports:
      - "4317:4317"
      - "4318:4318"
    mem_limit: 512m
    cpus: 1.0
    restart: unless-stopped

  langfuse:
    image: langfuse/langfuse:latest
    ports:
      - "3000:3000"
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/langfuse
      - NEXTAUTH_SECRET=${NEXTAUTH_SECRET}
      - SALT=${LANGFUSE_SALT}
    mem_limit: 1g
    cpus: 1.0
    restart: unless-stopped
    depends_on:
      db:
        condition: service_healthy

volumes:
  pgdata:
  redisdata:
  uploads:
    driver: local
  hf_cache:
    driver: local
```

> **Note:** Langfuse uses a separate database `langfuse` on the same PostgreSQL instance. Create it in `init.sql`:
> ```sql
> CREATE DATABASE langfuse;
> ```

> **Sizing note:** Use `Qwen2.5-7B-Instruct-AWQ` on RTX 4070. Upgrade to `Qwen2.5-14B-AWQ` only on RTX 4090-class GPUs after validating latency and VRAM headroom.

> **CPU-only note:** If no GPU is available, keep the same API and retrieval architecture but replace the `vllm` service with a smaller CPU-capable serving stack and reduce concurrency expectations. This is a safe functional fallback, not a performance-equivalent deployment.

## Deployment Modes

| Mode | When to use | Required services | Provider config |
|------|-------------|------------------|-----------------|
| Demo mode | Current phase, no local GPU inference yet | `api`, `worker`, `db`, `redis`, `langfuse`, `otel-collector` | `AI_PROVIDER=google` + `GOOGLE_API_KEY` |
| On-prem mode | Final production rollout | Demo mode services + `vllm` | `AI_PROVIDER=vllm` + `VLLM_BASE_URL=http://vllm:8000/v1` |

Run on-prem mode with the `onprem` profile so one compose file supports both phases.

## Healthcheck & Readiness Probes

| Service | Endpoint | Check | Interval |
|---------|----------|-------|----------|
| API | `GET /health` | DB + Redis + active AI provider connectivity | 30s |
| Worker | Celery inspect ping | Worker responsiveness | 30s |
| vLLM | `GET /health` | OpenAI-compatible server ready | 30s, on-prem profile only |
| DB | `pg_isready` | PostgreSQL accepting connections | 10s |
| Redis | `redis-cli ping` | Redis responding | 10s |

### Health Response Schema

```json
{
  "status": "healthy",
  "checks": {
    "database": {"status": "up", "latency_ms": 2},
    "redis": {"status": "up", "latency_ms": 1},
    "ai_provider": {"status": "up", "provider": "google", "latency_ms": 150}
  },
  "queue_depth": 3,
  "active_sessions": 12,
  "timestamp": "2026-04-07T10:00:00Z"
}
```

## Observability Stack

### Langfuse Integration

| What to Trace | Why |
|---------------|-----|
| Prompt + response pairs | Debug quality, iterate on prompts |
| Token usage (in/out) | Cost tracking, quota management |
| Latency per generation | Performance monitoring |
| Citation accuracy | Verify retrieval quality |
| User feedback (thumbs up/down) | Quality metrics |

### OpenTelemetry Spans

| Span | Attributes |
|------|-----------|
| `request` | method, path, status_code, duration_ms |
| `db.query` | table, operation, duration_ms, row_count |
| `celery.task` | task_name, doc_id, status, duration_ms |
| `ai.chat` | provider, model, tokens_in, tokens_out, latency_ms |
| `rag.retrieve` | top_k, sections_returned, rerank_scores |
| `auth.login` | user_id, success/failure |

### Key Metrics Dashboard

| Metric | Alert Threshold | Action |
|--------|----------------|--------|
| API p95 latency | > 2s | Check AI provider, DB queries |
| Queue depth | > 20 | Scale workers, check stuck tasks |
| Error rate | > 5% | Check logs, rollback if needed |
| AI provider latency | > 10s | Trigger fallback chain |
| DB connection pool | > 80% used | Increase pool size, check leaks |

## Backup Strategy

| Component | Method | Frequency | Retention |
|-----------|--------|-----------|-----------|
| PostgreSQL | `pg_dump -Fc` + checksum | Nightly (02:00) | 30 days |
| Uploaded files | `rsync uploads/` to backup server | Nightly (03:00) | 30 days |
| Redis (queue) | Not backed up (ephemeral) | N/A | N/A |
| Config/Env | Git + encrypted secrets store | On change | Forever |

### Backup Script

```bash
#!/bin/bash
# backup.sh - Run nightly via cron

BACKUP_DIR="/backups/$(date +%Y-%m-%d)"
mkdir -p "$BACKUP_DIR"

# Database dump
pg_dump -h db -U user -Fc ragbot > "$BACKUP_DIR/db.dump"
sha256sum "$BACKUP_DIR/db.dump" > "$BACKUP_DIR/db.dump.sha256"

# File storage sync
rsync -a /app/uploads/ "$BACKUP_DIR/uploads/"
tar -C "$BACKUP_DIR" -czf "$BACKUP_DIR/uploads.tar.gz" uploads
rm -rf "$BACKUP_DIR/uploads"

# Encrypt at rest (AES-256)
for f in "$BACKUP_DIR"/*.dump "$BACKUP_DIR"/*.sha256 "$BACKUP_DIR"/*.tar.gz; do
    openssl enc -aes-256-cbc -salt -pbkdf2 -in "$f" -out "${f}.enc" -pass env:BACKUP_KEY
    rm "$f"
done

# Cleanup old backups
find /backups -mindepth 1 -maxdepth 1 -type d -mtime +30 -exec rm -rf {} \;
```

## Future-Proofing

### BaseDataSource Interface

```python
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator

class BaseDataSource(ABC):
    """Connector interface for future data sources."""

    @abstractmethod
    async def connect(self, config: dict) -> None:
        """Initialize connection to data source."""
        pass

    @abstractmethod
    async def fetch_documents(self) -> AsyncIterator[dict]:
        """Yield documents from source."""
        pass

    @abstractmethod
    async def describe_capabilities(self) -> dict[str, Any]:
        """Describe supported operations such as document sync or SQL querying."""
        pass

    @abstractmethod
    async def watch_changes(self) -> AsyncIterator[dict]:
        """Stream real-time changes (if supported)."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Cleanup connection."""
        pass
```

### SQLServerDataSource Responsibilities

| Responsibility | Required behavior |
|----------------|-------------------|
| Connection management | Use project-provided encrypted config |
| Schema sync | Cache schemas, tables, columns, PK/FK metadata, and admin-written descriptions |
| Query execution | Validate read-only SQL and enforce timeout + row limit |
| Audit | Emit query audit log for every execution |
| Isolation | Respect project-owned connector configuration and policy scope |

### SQL Connector Rollout Policy

| Stage | Scope |
|-------|-------|
| Stage 1 | Documents only |
| Stage 2 | Add connector registry + schema sync |
| Stage 3 | Enable read-only SQL Server Q&A for approved project tables |
| Stage 4 | Add richer business glossary, join hints, and guarded analytics flows |

### Future Source Implementations

| Source | Implementation | Use Case |
|--------|---------------|----------|
| `FileDataSource` | Local/Network files | Current (default) |
| `SQLDataSource` | Database tables | Query existing DBs |
| `APIDataSource` | REST/GraphQL APIs | External systems |
| `ConfluenceSource` | Confluence API | Wiki integration |
| `SharePointSource` | SharePoint API | Enterprise docs |
| `MCPSource` | Model Context Protocol | Future MCP servers |

### MCP Adapter Readiness Checklist

- [ ] `BaseDataSource` interface implemented
- [ ] Async iterator pattern for document streaming
- [ ] Config schema per source type
- [ ] Error handling + retry per source
- [ ] Access control for source connectors (admin-only configuration)
- [ ] MCP client library integrated
- [ ] Source registry in database
- [ ] UI for managing sources

### Provider Switch Checklist (Google AI Studio -> vLLM)

- [ ] Set `AI_PROVIDER=vllm` in `.env`
- [ ] Set `VLLM_BASE_URL=http://localhost:8001/v1`
- [ ] Deploy `vllm` container with quantized Qwen2.5 model
- [ ] Verify prompt, embedding, and reranker compatibility
- [ ] Run retrieval + generation integration tests
- [ ] Monitor latency, GPU memory, and citation quality for 24h
- [ ] Remove `GOOGLE_API_KEY` if fully migrated

Zero core code changes required; only configuration and infrastructure change.

## Deployment Invariants

| Rule | Requirement |
|------|-------------|
| Single source of truth | MUST drive provider selection from environment/config, not code edits |
| Persistence | MUST persist PostgreSQL data and uploaded files across restarts |
| Healthchecks | MUST gate dependent services on health where possible |
| Observability | MUST emit request, retrieval, provider, and queue telemetry with project tags |
| Backups | MUST back up database and file storage separately and verify backup integrity |

## AI Coding Guardrails

| Do | Do not |
|----|--------|
| Keep one compose topology supporting demo and on-prem modes | Fork two unrelated deployment stacks unnecessarily |
| Trace queue depth, provider latency, and citation metadata | Log only HTTP latency and ignore retrieval internals |
| Treat secrets as env vars or secret stores | Hardcode API keys or JWT secrets in source |
