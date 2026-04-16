# Changelog

## [Unreleased] - 2026-04-16

### Added
- **Method D**: Docling `iterate_items()` for direct item extraction — preserves page numbers, heading levels, table structures with 100% metadata fidelity
- **Smart OCR Strategy**: 2-pass approach — fast no-OCR first (native PDFs), OCR fallback only for scanned PDFs
- **Worker architecture refactor**: `app/worker.py` → `app/workers/upload_pipeline.py` + `app/workers/cleanup_pipeline.py`
- **Chat session auto-delete**: TTL=1 day via Celery beat daily cleanup task in `cleanup-pipeline`
- **Table extraction**: `TableItem` → markdown table conversion with cell grid structure
- **Page number extraction**: Direct from Docling provenance (`prov[0].page_no`) — no more heuristic guessing
- **Scanned PDF detection**: Automatic detection after fast pass → OCR fallback

### Changed
- Worker services renamed: `worker` → `upload-pipeline` (GPU) + `cleanup-pipeline` (lightweight + beat)
- Task names updated: `app.worker.*` → `app.workers.upload_pipeline.*` / `app.workers.cleanup_pipeline.*`
- Docling parser: `_convert_with_docling()` now returns `ConversionResult` instead of markdown string
- Smart OCR: `do_ocr=False` first → detect scanned → `do_ocr=True` fallback (instead of always-OCR)
- Removed `_build_page_map()` and `_find_page_for_section()` — no longer needed with Method D

### Removed
- `app/worker.py` — split into `app/workers/upload_pipeline.py` and `app/workers/cleanup_pipeline.py`
- `app/workflows/` directory — was empty, removed
- `_build_page_map()` — page info now from Docling provenance directly
- `_find_page_for_section()` — heuristic no longer needed

## [0.1.0] - 2026-04-15

### Added
- **Next.js 16 frontend** with shadcn/ui v4 components
- **next-auth v5** with JWT strategy and Credentials provider
- **SSE streaming chat** endpoint (`POST /api/v1/chat/stream`)
- **Admin dashboard** with health monitoring
- **Document management** with upload, list, and detail views
- **User management** with CRUD operations (admin only)
- **Role-based routing** (admin vs member access)
- **Document tree visualization** with react-flow
- **Tree API endpoints** (GET /tree, /nodes, /search)
- **New auth endpoints**: GET /auth/me, GET /auth/users, DELETE /auth/users/{username}
- **New health endpoints**: GET /health/data, GET /health/nodes, GET /health/node
- **Chat sessions endpoint**: GET /chat/sessions
- 2-stage retrieval pipeline (Sections → Chunks)
- `document_sections` table in PostgreSQL for section-level storage
- `SectionRepository` for managing sections in PostgreSQL
- Section extraction from Markdown via heading-based splitting
- Rule-based text refiner (0GB VRAM, ~1ms per node) — **restored as default**
- Comprehensive test suite (68 tests)

### Changed
- **Rule-based refiner restored** — AI-based refiner removed from ingestion pipeline
- Ingestion no longer uses any AI model (0GB VRAM for text refinement)
- AI is now ONLY used for /chat endpoint
- Retrieval uses 2-stage: coarse section search (≥ 0.30) → fine chunk search (≥ 0.35)
- Removed Nuxt.js and Streamlit frontends — replaced with Next.js 16
- Updated documentation to reflect BGE-m3 local embedding
- Strengthened security (strong passwords, secrets, JWT entropy)
- Updated CORS origins to include Next.js port 3000
- Docker compose now includes webapp service on port 3000

### Fixed
- Thread safety in tree.py vector store initialization
- Removed dead code (old refiner.py)
- Fixed incorrect architecture documentation
