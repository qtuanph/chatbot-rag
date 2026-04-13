---
name: project
description: Core architecture and key decisions for chatbot-rag (condensed)
type: project
---

# Architecture Summary - chatbot-rag

**Status:** 85% Complete, Production Hardening Phase

## Core Technology Stack

### Infrastructure (Docker-First)
- FastAPI (async), Celery + Redis, PostgreSQL, Qdrant, RustFS (S3-compatible)
- Single-project deployment, on-premise focus

### AI/ML Stack (CRITICAL - Read This!)

#### ✅ Local Components (100% Offline)
1. **Embedding**: BAAI/bge-m3 via sentence-transformers
   - Config: `EMBEDDING_MODEL=sentence-transformer`, `EMBEDDING_HF_MODEL=BAAI/bge-m3`
   - 1024-dim vectors, 8192 tokens, multilingual (Vietnamese optimized)
   - GPU/CPU auto-detect, fully offline

2. **AI Refiner**: Rule-based heuristics (NOT AI model)
   - File: `app/services/ingestion/rule_based_refiner.py`
   - Config: `AI_REFINER_TYPE=rule_based`
   - 0GB VRAM, ~1ms per node, 500x faster than Qwen
   - Purpose: OCR error correction, hierarchy validation

3. **OCR**: EasyOCR (vi+en), GPU acceleration

#### ⚠️ External Component (Temporary)
1. **Chat LLM**: Google Gemini API (gemini-2.5-flash)
   - Config: `AI_PROVIDER=google`, `GOOGLE_API_KEY`
   - ONLY used for `/api/v1/chat` responses
   - Future: Migrate to local vLLM for 100% offline

## Key Architectural Decisions

### Why Local Embedding (BAAI/bge-m3)?
- Fully offline, no rate limits, no ongoing costs
- Excellent Vietnamese support
- Data privacy (never leaves infrastructure)

### Why Rule-Based Refiner?
- Zero VRAM (no GPU required)
- 500x faster than AI-based refiner
- Deterministic rules, no model hallucinations
- Accurate pattern matching for OCR errors

### Why Hierarchical Indexing?
Preserves document structure (not flat chunking):
```
Document → Chapters → Sections → Subsections
```
Benefits: Better context, richer citations, tree visualization

### Why Async Ingestion?
- Upload endpoint returns immediately with `task_id`
- Celery provides reliability (acks_late, retries)
- Progress reporting via callbacks

## Current Implementation Status

### ✅ Complete (Working)
- Ingestion pipeline (Docling + EasyOCR → LlamaIndex hierarchy)
- Hierarchical retrieval with BAAI/bge-m3 local embedding
- Rule-based refiner (0GB VRAM, 500x faster)
- Streamlit tree visualizer (full feature set)
- Tree API endpoints (GET /documents/{id}/tree)
- Hard-delete workflow (registry → vectors → file → DB)
- Health checks with dependency monitoring
- Security hardened (strong passwords, CORS configured)

### ⏳ Needs Testing
- Docker image rebuild (code changed, image stale)
- Service health verification
- Test suite execution (68 tests created)

### ❌ Not Implemented (Production Gaps)
- Structured logging
- Monitoring/metrics collection
- Backup procedures automation

## Important Invariants

| Rule | Required Behavior |
|------|-------------------|
| Async ingestion | Upload must return immediately with `task_id` |
| Provider boundary | Route handlers never call provider SDKs directly |
| Hierarchical retrieval | Preserve document structure |
| Hard-delete order | registry → vectors → file → DB → purge |
| Score threshold | Drop chunks with cosine similarity < 0.35 |
| Config location | **All changes in .env, NEVER in .env.example** |

## Configuration Files

| File | Purpose |
|------|---------|
| `.env` | Runtime config (gitignored) |
| `.env.example` | Template only (committed) |
| `CLAUDE.md` | AI agent guide (comprehensive) |
| `docs/01_SYSTEM_ARCHITECTURE.md` | Detailed architecture |
| `docs/04_API_CONTRACT_AND_SECURITY.md` | API endpoints |

## Database Credentials (CRITICAL)

**PostgreSQL Setup (docker-compose.yml):**
- `POSTGRES_USER=db-admin` (PostgreSQL admin account)
- `POSTGRES_PASSWORD` (admin password)
- `app.app_rw_password` (app user password, set via `APP_DB_PASSWORD` in .env)

**App Connection (.env):**
- `DATABASE_URL=postgresql+psycopg://app_rw:APP_DB_PASSWORD@db:5432/ragbot`
- `APP_DB_USER=app_rw`
- `APP_DB_PASSWORD` (must match what was set when database volume was created)

**CRITICAL:** When changing database password in .env:
```bash
docker compose down -v              # Destroy volumes
docker volume prune -f               # Prune unused
docker compose up -d                 # Fresh start
```

## Common Pitfalls (Learned the Hard Way)

1. ❌ Changing .env password without recreating database volume → authentication fails
2. ❌ Calling provider SDKs directly in routes → breaks adapter pattern
3. ❌ Flat chunking instead of hierarchical indexing → loses context
4. ❌ Editing .env.example instead of .env → changes lost on git pull
5. ❌ Forgetting to rebuild Docker after code changes → stale image

## Development Commands

```bash
# Rebuild after code changes
docker compose up --build

# View logs
docker compose logs -f api worker

# Database reset (WARNING: destroys data)
docker compose down
docker volume rm chatbot-rag_pgdata
docker compose up --build

# Check service health
curl http://localhost:8000/api/v1/health
```

## Hardware Requirements

**Minimum (CPU-only):**
- 4+ cores CPU, 8GB RAM
- Embedding: Slow (CPU-based)

**Recommended (GPU):**
- NVIDIA 6GB+ VRAM, 16GB RAM
- Embedding: Fast (GPU-based)
- BAAI/bge-m3: ~2GB VRAM

## Production Readiness Checklist

### Critical (Blocking)
- [ ] Rebuild Docker image with latest code
- [ ] Verify all services running and healthy
- [ ] Test full workflow: upload → parse → tree → visualize
- [ ] Run all tests and verify they pass

### High Priority (Should Have)
- [ ] Implement structured logging
- [ ] Set up monitoring/metrics collection
- [ ] Create backup procedures
- [ ] Load testing (100 concurrent users)

## Documentation Links

- Architecture: `docs/01_SYSTEM_ARCHITECTURE.md`
- Workflows: `docs/03_CORE_WORKFLOWS.md`
- API Contract: `docs/04_API_CONTRACT_AND_SECURITY.md`
- Deployment: `docs/06_DEPLOYMENT_AND_OBSERVABILITY.md`

## Last Updated
- 2026-04-13: Condensed from 3 files (architecture_clarifications + project_context + external_resources)
