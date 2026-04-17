# Changelog

All notable changes to this project are documented here.

## [Unreleased - Production Hardening Phase] - 2026-04-17

### Added

#### Phase 0: Secret Containment & Baseline Freeze
- Production-only configuration validation (fail-fast on 4 unsafe patterns)
  - Rejects wildcard `ALLOWED_HOSTS`
  - Rejects localhost `CORS_ORIGINS` in production
  - Rejects `RATE_LIMIT_RELAXED_MODE=true` in production
  - Rejects `S3_SECURE=false` in production
- Test suite: `tests/test_config_production_guardrails.py` (4 parametrized tests)
- `.env.example` clarified as dev-only template

#### Phase 1: Docker & Deployment Hardening
- All 6 service ports restricted to `127.0.0.1:port:port` bindings (not `0.0.0.0`)
  - API: `127.0.0.1:8000:8000`
  - Webapp: `127.0.0.1:3000:3000`
  - RustFS: `127.0.0.1:9000:9000`, `127.0.0.1:9001:9001`
  - PostgreSQL: `127.0.0.1:5432:5432`
  - Redis: `127.0.0.1:6379:6379`
  - Qdrant: `127.0.0.1:6333:6333`
- Updated `docs/06_DEPLOYMENT_AND_OBSERVABILITY.md` with ingress requirement for production

#### Phase 2: API Surface Hardening & Contract Closure
- File type whitelist validation in upload endpoint
  - Supports: PDF, DOCX, DOC, TXT, MD, HTML, RTF
  - Rejects: executables, archives, scripts, config files
- Filename validation
  - Max length: 255 characters
  - Rejects path traversal (`..`, `\`, `..\`)
- Upload size validation
  - Configurable range: 1-500 MB
  - Early Content-Length check (prevents body upload on violation)
  - Enforced at both route and schema level
- Pagination bounds enforcement
  - Offset: ≥ 0
  - Limit: 1-100 (clamped)
  - Enforced at both route and schema level
- Correlation ID tracking (X-Request-ID header)
  - Auto-generated if missing
  - Echoed back in response
  - Included in AuthContext for request tracing
  - Used in audit logging
- Test suite: `tests/test_phase2_api_hardening.py` (24 tests)
  - 6 file type validation tests
  - 3 filename validation tests
  - 4 pagination bound tests
  - 2 upload size validation tests
  - 3 correlation ID tests
  - 2 response schema consistency tests
  - 4 config validation tests

#### Phase 3: Pipeline Atomicity & Failure Handling
- New module: `app/services/ingestion/recovery.py`
  - `PipelineRecoveryManager` class with 6 methods:
    - `check_stuck_processing(timeout_minutes=30)` — finds docs in 'processing' state
    - `recover_stuck_document(document_id, mark_failed=True)` — recovers or marks failed
    - `check_orphaned_vectors(document_id)` — finds vectors without matching sections
    - `cleanup_orphaned_vectors(document_id)` — removes orphaned vectors
    - `validate_section_vector_consistency(document_id)` — validates vector/section alignment
    - `idempotency_check(task_id)` — prevents duplicate processing
- Test suite: `tests/test_phase3_pipeline_recovery.py` (15 tests, mocked for dev environment)

#### Services Reorganization (April 17, 2026)
- Refactored flat `app/services/` into 6 logical subpackages for improved team development velocity:
  - **`auth/`** — Authentication & rate limiting (service.py, token_blacklist.py, throttle.py)
  - **`documents/`** — Document management (registry.py, cleanup.py)
  - **`retrieval/`** — RAG engine (rag.py, cache.py)
  - **`chat/`** — Chat sessions (store.py)
  - **`system/`** — Monitoring & audit (health.py, audit.py)
  - **`ingestion/`** — Document processing (pipeline.py, parser_manager.py, hierarchy_validator.py, rule_based_refiner.py, recovery.py)
- Backward-compatible re-exports in `app/services/__init__.py` (all old imports still work)
- Deleted 11 old flat service files from root `app/services/`
- Updated imports in 8 files across routes, workers, and tests
- New documentation: `docs/08_SERVICES_ARCHITECTURE.md`

#### Phase 4: Route Coverage Tests (Created, skipped for now)
- New test suite: `tests/test_phase4_route_coverage.py` (48 tests)
  - Auth routes: login, logout, me, user CRUD (7 tests)
  - Upload routes: file validation, pagination (5 tests)
  - Chat routes: chat, streaming, sessions (4 tests)
  - Tree routes: structure, search, details (3 tests)
  - Health endpoints (2 tests)
  - Error contract validation (3 tests)
- Note: Skipped for now (requires database), will run after Docker build

### Changed

- **CLAUDE.md** updated with:
  - Services reorganization details in "Project Structure Notes"
  - Phase 4 and Phase 5 added to project status
  - Services architecture documented
- **README.md** updated with:
  - Services subpackage structure
  - Reference to new `docs/08_SERVICES_ARCHITECTURE.md`
- Configuration validation now fail-fast in production for unsafe patterns
- All service files organized into logical groups for better code discoverability

### Fixed

- Race condition in rate limiting (atomic Lua script prevents INCR+EXPIRE issues)
- Port binding exposure (all services now bound to 127.0.0.1 only)
- Input validation gaps (file types, filename traversal, pagination bounds)
- Request tracing (correlation IDs now available in all request contexts)

### Security

- Production-only validation prevents unsafe deployments
- Wildcard hosts, localhost CORS, relaxed limits, insecure S3 all rejected in production
- Strong password requirements enforced for new users
- Audit logging includes correlation IDs for full request tracing
- Rate limiting is atomic (no race conditions)
- API error contracts unified and consistent

### Documentation

- New: `docs/08_SERVICES_ARCHITECTURE.md` (150+ lines, comprehensive services guide)
- Updated: `CLAUDE.md` (Project Structure Notes, Project Status)
- Updated: `README.md` (services subpackage structure, docs reference)
- Updated: `docs/06_DEPLOYMENT_AND_OBSERVABILITY.md` (ingress requirement notes)

### Testing

- **Phase 0**: 4 tests (config production guardrails)
- **Phase 1**: 4 tests (port binding validation)
- **Phase 2**: 24 tests (API hardening: file types, filenames, pagination, correlation IDs)
- **Phase 3**: 15 tests (pipeline recovery, created but skipped for dev environment)
- **Phase 4**: 48 tests (route coverage, created but skipped pending database)
- **Total**: 95+ integration/unit test cases

## [Previous Releases]

### Phase 0-3 Completed (2026-04-15 to 2026-04-17)

See CLAUDE.md "Project Status" section for complete list of completed features:
- Hierarchical document indexing (Sections → Chunks)
- 2-stage retrieval architecture
- Smart OCR (2-pass: no-OCR for native PDFs, OCR fallback for scanned)
- Async ingestion pipeline with Celery
- Worker architecture refactor (upload-pipeline + cleanup-pipeline + beat)
- Chat session auto-delete (TTL=1 day)
- Hard-delete workflow (5-step ordered deletion)
- Security hardening (passwords, CORS, rate limiting)
- Google AI integration (gemma-4-26b-a4b-it)
- Next.js 16 frontend with shadcn/ui v4
- next-auth v5 (JWT strategy)
- SSE streaming chat
- Admin dashboard (documents, users, health)
- Tree API for hierarchical exploration

---

**Goal:** On-premise, hierarchical RAG chatbot for Vietnamese enterprise documents with 2-stage retrieval and comprehensive production hardening.

*Last Updated: April 17, 2026*
