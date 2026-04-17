# Quick Reference - Key Rules & Patterns

**Not a replacement for CLAUDE.md** — Use this as a cheat sheet when you remember WHAT but forget WHERE.

For detailed explanations, see CLAUDE.md.

---

## 🚨 Three Core Invariants (NEVER break these)

1. **Async Ingestion** — Upload returns `task_id` immediately, parsing happens async via Celery
2. **2-Stage Retrieval** — Query → Stage 1 (sections, ≥0.30) → Stage 2 (chunks within sections, ≥0.35)
3. **Hard-Delete Ordering** — registry → vectors → file → DB → purge (ensures fast API response)

---

## 📍 Data Location Map

| Data | Where | Query Layer | Notes |
|------|-------|------------|-------|
| **Sections** | PostgreSQL `document_sections` | `SectionRepository` | Level 1: H1-H6 headings |
| **Chunks** | Qdrant (vectors) | `qdrant.py` adapter | Level 2: ~400 tokens each, section_id metadata |
| **Documents** | PostgreSQL `documents` | `app.models` | Status: pending/processing/ready/deleted |
| **Chat history** | Redis (TTL=24h) | `ChatStore` | Auto-cleanup via beat task |
| **Uploaded files** | RustFS (S3-compat) | `DocumentStore` | Hard-deleted on user request |
| **Embeddings cache** | Redis (MD5-keyed) | `QueryEmbeddingCache` | TTL=1h, skip re-embedding |
| **User sessions** | JWT tokens (60min) + blacklist | `TokenBlacklist` (Redis) | Token revocation on logout |

---

## 🔑 Config Checklist (Environment Variables)

```bash
# AI & Embedding
AI_PROVIDER=google              # or: vllm (on-premise)
GOOGLE_API_KEY=...             # REQUIRED for Google AI
GOOGLE_MODEL=gemma-4-26b-a4b-it
EMBEDDING_HF_MODEL=BAAI/bge-m3 # Must be bge-m3

# Retrieval Thresholds
RETRIEVAL_SECTION_MIN_SCORE=0.30  # Stage 1 threshold
RETRIEVAL_MIN_SCORE=0.35          # Stage 2 threshold
RETRIEVAL_SECTION_TOP_K=3         # Coarse search results
RETRIEVAL_CHUNK_TOP_K=5           # Fine search results

# Ingestion
INGESTION_ENGINE=docling         # or: classic (fallback)
INGESTION_EMBEDDING_CHUNK_SIZE=32 # Parallel batch size

# Production Safety (APP_ENV=production)
ALLOWED_HOSTS=must_be_specific    # Wildcard REJECTED
CORS_ORIGINS=must_be_specific     # localhost REJECTED
S3_SECURE=true                    # false REJECTED in production
RATE_LIMIT_RELAXED_MODE=false     # true REJECTED in production
```

**In production**: Config validation FAILS if unsafe patterns detected. This is intentional.

---

## 🎯 API Endpoints (All under `/api/v1/`)

| Method | Path | Auth | Notes |
|--------|------|------|-------|
| POST | `/auth/login` | — | Returns JWT token |
| POST | `/auth/logout` | JWT | Revokes token |
| GET | `/auth/me` | JWT | Current user info |
| POST | `/auth/users` | Admin | Create user |
| GET | `/auth/users` | Admin | List users |
| POST | `/upload` | Admin | Enqueues Celery task, returns task_id |
| GET | `/status/{task_id}` | — | Poll ingestion progress |
| GET | `/documents` | Member | List all docs (soft-delete excluded) |
| DELETE | `/documents/{id}` | Admin | Hard-delete workflow |
| POST | `/chat` | Member | RAG query (non-streaming) |
| POST | `/chat/stream` | Member | RAG query (SSE streaming) |
| GET | `/chat/sessions` | Member | List user's sessions |
| GET | `/tree/{id}` | Member | Document tree structure |
| GET | `/health` | — | Service status |

---

## 🔐 Security Rules

| Rule | Implementation |
|------|-----------------|
| Rate limiting | Atomic Lua script in Redis (prevents INCR+EXPIRE race) |
| Password policy | Min 8 chars, 1 upper + 1 lower + 1 digit + 1 special |
| JWT tokens | HS256, 60-min expiry, JTI tracked in blacklist |
| Soft-delete | Excluded from retrieval but preserved in chat history |
| Hard-delete | 5-step atomic workflow (registry → vectors → file → DB → purge) |
| File upload | MIME type whitelist (PDF, DOCX, DOC, TXT, MD, HTML, RTF) |
| Filenames | Max 255 chars, reject path traversal (`../`, `..\\`) |
| Correlation ID | X-Request-ID header echoed back, tracked in logs |
| Audit logging | Security events logged to PostgreSQL with correlation_id |

---

## 🏗️ Service Structure (6 Subpackages)

```
app/services/
├── auth/              # JWT, passwords, rate limiting
├── documents/         # Registry, hard-delete
├── retrieval/         # 2-stage RAG, query cache
├── chat/              # Chat sessions
├── system/            # Health checks, audit
└── ingestion/         # Pipeline, parsers, recovery
```

**Note**: Root `__init__.py` re-exports all for backward compatibility.

---

## 🔄 Ingestion Pipeline Flow

1. User uploads file → API saves to RustFS → enqueues Celery task
2. Worker: download → parse (Docling Method D) → validate hierarchy
3. Worker: refine (rule-based) → extract sections → embed chunks
4. Worker: store sections (PostgreSQL) → store vectors (Qdrant with section_id)
5. Worker: verify → unload embedding model
6. API: `/status/{task_id}` returns progress in real-time

**Parsing**: Docling preferred (preserves page#, heading level, table structure)
**OCR**: 2-pass (fast no-OCR for native PDFs, OCR fallback for scanned)
**Refinement**: Rule-based only (0GB VRAM, ~1ms per node)

---

## 📊 2-Stage Retrieval

**Stage 1** (Coarse-grained):
```
Query → Embed (BAAI/bge-m3) → Qdrant search (top 3, ≥0.30)
→ Group by section_id → Pick unique sections
```

**Stage 2** (Fine-grained):
```
For each top section → Qdrant search (top 5, ≥0.35)
→ Detailed chunks with context
```

**Fallback**:
```
If no sections found → Flat vector retrieval
```

---

## ❌ Don't Ever Do This

| Anti-pattern | Why | Do This Instead |
|--------------|-----|-----------------|
| Flat chunking | Loses document structure | Use hierarchical indexing |
| Direct DB calls | Bypasses service layer | Use repositories + services |
| Provider SDK in routes | Hard to test/swap | Use adapter pattern |
| Numeric HTTP codes | CI guardrail fails | Use `status.HTTP_*` constants |
| `raise HTTPException` in routes | CI guardrail fails | Use `app/core/http_errors.py` helpers |
| Hallucinate answers | User trust lost | Say "not found in documents" |
| Naive pagination | Bounds not enforced | Validate offset≥0, limit 1-100 |

---

## 🧪 Testing

- **Phase 0**: Config production guardrails (4 tests)
- **Phase 1**: Port binding validation (4 tests)
- **Phase 2**: API hardening (24 tests: file types, filenames, pagination, correlation IDs)
- **Phase 3**: Pipeline recovery (15 tests, skipped pending database)
- **Phase 4**: Route coverage (48 tests, skipped pending database)

**To run**: 
```bash
pytest tests/test_phase2_api_hardening.py -v  # Runs locally
pytest tests/test_phase4_route_coverage.py -v # Needs database (Docker)
```

---

## 🚀 Quick Commands

```bash
# Build + run
docker compose up --build

# Access services
API: localhost:8000
Webapp: localhost:3000
Qdrant: localhost:6333/dashboard
RustFS: localhost:9001
Database: localhost:5432 (db: ragbot, user: db-admin)

# Service logs
docker compose logs -f api
docker compose logs -f upload-pipeline

# Health check
curl http://localhost:8000/api/v1/health

# Access DB
docker exec -it chatbot-rag-db-1 psql -U db-admin -d ragbot
```

---

**Last Updated**: 2026-04-17 | **For detailed explanations**: See CLAUDE.md
