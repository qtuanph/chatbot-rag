# Changelog

## [Unreleased] - 2026-04-16

### Added
- Added throttling for authenticated health endpoints: `/api/v1/health/data`, `/api/v1/health/nodes`, `/api/v1/health/node`
- Added throttling for Tree API endpoints: `/api/v1/tree/{document_id}`, `/api/v1/tree/{document_id}/nodes/{node_id}`, `/api/v1/tree/{document_id}/search`
- Added Tree search query validation bounds (`query` min 1, max 500 chars)
- Standardized Tree API hardcoded status codes to FastAPI `status.*` constants for consistent API error handling
- **Page number extraction**: Direct from Docling provenance (`prov[0].page_no`) — no more heuristic guessing
- **Scanned PDF detection**: Automatic detection after fast pass → OCR fallback
- Smart OCR: `do_ocr=False` first → detect scanned → `do_ocr=True` fallback (instead of always-OCR)
- Removed `_build_page_map()` and `_find_page_for_section()` — no longer needed with Method D
- Added production fallback global rate-limit middleware (coarse safety net)
- Tightened auth schema validation: normalized username, bounded password length, strict role enum
- Frontend API client synced for tree query params and typed search results

### Removed
- `app/worker.py` — split into `app/workers/upload_pipeline.py` and `app/workers/cleanup_pipeline.py`
- `app/workflows/` directory — was empty, removed
- `_build_page_map()` — page info now from Docling provenance directly
- `_find_page_for_section()` — heuristic no longer needed
- `app/adapters/embeddings/gemini.py` — dead embedding adapter (unused after local BAAI/bge-m3 standardization)

### Changed
- Standardized status code constants across chat/documents routes (`status.HTTP_*`) for consistency.
- Auth dependency now checks preflight by actual request method (`Request.method`) instead of custom header.

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
