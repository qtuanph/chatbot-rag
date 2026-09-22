# Changelog

All notable changes to the **chatbot-rag** platform will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Changed — Annual Maintenance (2026-09-22)
- **Backend dependencies** (`chatbot-api/requirements.txt`): `llama-index-core` 0.14.24 → 0.14.25, `uvicorn` 0.52.4 → 0.53.0, `sqlalchemy` 2.0.52 → 2.0.54, `psycopg` 3.3.5 → 3.3.6, `boto3` 1.43.89 → 1.43.99, `PyJWT` 2.13.0 → 2.14.0, `docling` 2.126.0 → 2.129.0, `qdrant-client` 1.19.0 → 1.19.1; dev: `deepeval` 4.2.1 → 4.2.3. Verified with `black`, `flake8` and `pytest tests/unit` (10 passed).
- **Frontend dependencies** (`chatbot-webapp/package.json`): `next` 16.3.4 → 16.3.5, `react`/`react-dom` 19.2.8 → 19.3.0, `zod` 4.5.4 → 4.6.5, `lucide-react` 1.41.0 → 1.47.0, `tailwind-merge` 3.6.0 → 3.7.0, `react-resizable-panels` 4.12.3 → 4.13.2, `eslint-config-next` 16.3.4 → 16.3.5, `@types/node` 26.4.1 → 26.6.2, `@types/react` 19.2.18 → 19.3.0, `@types/react-dom` 19.2.7 → 19.3.0; root `shadcn` 4.14.0 → 4.21.0. Verified with `tsc --noEmit`, `eslint` and `next build`. `npm audit` reports 0 vulnerabilities in webapp and root.
- **Held back intentionally**: `eslint` stays on v9 (v10 is semver-major, ignored in dependabot config), `typescript` stays on v6.0.3 (v7 breaks `typescript-eslint` v8 peer range `>=4.8.4 <6.1.0`), `next-auth` stays on `5.0.0-beta.32` (no newer beta; `latest` tag still points to v4), Python stays on 3.13 (dependency compatibility).
- **Docker images** (`chatbot-api/docker-compose.yml`): `postgres` 18.4 → 18.6, `redis` 8.10.0 → 8.10.1, `traefik` v3.7.10 → v3.7.11.
- **Dependabot coverage fix** (`.github/dependabot.yml`): added missing `npm` entry for repo root (root `package.json`/`package-lock.json` were unmonitored), `docker` entries for both Dockerfiles, and `docker-compose` entry for `chatbot-api` (GA since Feb 2025, matches `docker-compose.yml`).

## [v1.0.0] - 2026-08-11

### Added & Redesigned
- **Analytics Executive Dashboard**: Redesigned `/analytics` with pure Shadcn UI components, tabbed layout, executive KPI cards, and dynamic model pricing calculator.
- **Streamlined Pricing Form**: Simplified model pricing configuration layout by removing preset buttons for a clean, direct custom price entry interface.
- **Headless Enterprise RAG Platform**: Multi-tenant RAG architecture with Wildcard CORS support and embeddable widget assets.

### Fixed & Optimized
- **RAG Leaf Chunk Hydration**: Preserved leaf chunk `full_text` details in `SafeAutoMergingRetriever` and added Redis cache clearance guard.
- **Qdrant Client Pin**: Pinned `qdrant-client == 1.18.0` in `chatbot-api/requirements.txt` for stable vector database operations.
- **Widget Typography & Tables**: Enhanced `Chatbot.css` with explicit table grid borders, scrollable container constraints, and word-wrap formatting for Vietnamese text.
- **CI Pipeline**: Removed legacy pytest step from GitHub Actions workflow and enforced 100% clean `black` & `flake8` compliance.

## [v0.12.0] - 2026-08-10

### Added
- **Interactive User Guides**: Added comprehensive user guides for system integration, tenant management, document parsing, and AI providers.
- **Architecture Canvas & Specs**: Added interactive architecture canvas and ZaloPay API specification docs.
- **Widget Script Assets**: Production embeddable widget script assets (`Chatbot.js`, `Chatbot.css`, `marked.min.js`).

## [v0.11.0] - 2026-08-10

### Added
- **Dual-Mode Sidebar**: Added collapsible dual-mode sidebar switcher (Compact vs Expanded).
- **Admin Audit Dashboard**: Created conversation audit logging interface to inspect query transcripts and user sessions.

## [v0.10.0] - 2026-08-10

### Added
- **Tenant Management Sheets**: Interactive UI sheets for creating, updating, and disabling tenants.
- **Document Catalog UI**: Upload catalog with real-time parsing status badges and section breakdowns.
- **FAQ Manager UI**: Administrative FAQ catalog manager with instant CRUD operations.

## [v0.9.0] - 2026-08-10

### Added
- **REST API Client SDK**: Structured REST client in `webapp/lib/api-client.ts` with error handling middleware.
- **Zod Runtime Schemas**: Zod validation schemas for all backend API request and response models.
- **NextAuth Integration**: Secure session management and authentication flow.

## [v0.8.0] - 2026-08-10

### Added
- **Next.js 16 Webapp Control Plane**: Built webapp foundation with TailwindCSS design system.
- **Backend Proxy Handler**: `/api/bep/*` proxy handler to keep backend tokens isolated from the browser.
- **Dark Mode System**: Global theme switcher supporting Light, Dark, and System modes.

## [v0.7.0] - 2026-08-10

### Added
- **Traefik v3 Reverse Proxy**: Edge routing with auto SSL/TLS termination.
- **RustFS S3 Storage**: High-performance S3 object storage for raw document binaries and chunks.

## [v0.6.0] - 2026-08-10

### Added
- **9Router LLM AI Proxy**: Gateway for orchestrating LLM inference requests.
- **Reranker & Local Embeddings**: NVIDIA NIM Reranker with Docker Model Runner local embedding fallback.

## [v0.5.0] - 2026-08-10

### Added
- **Streaming Chat Service**: Server-Sent Events (SSE) streaming API for real-time AI responses.
- **Redis O(1) FAQ Cache**: Tier 0 exact match FAQ cache (~20ms latency).

## [v0.4.0] - 2026-08-10

### Added
- **Document Ingestion Pipeline**: Support for PDF, DOCX, TXT, and Markdown parsing.
- **Celery Worker Tasks**: Async background task processing queue for document parsing.

## [v0.3.0] - 2026-08-10

### Added
- **Multi-Tenant Boundary Isolation**: Enforced `tenant_id` filtering across database queries.
- **JWT Auth Engine**: Bearer token authentication and role-based access control (`platform_admin`, `tenant_admin`).

## [v0.2.0] - 2026-08-10

### Added
- **RAG Gateway Core**: Controller-Service-Repository architecture pattern.
- **Qdrant Vector Adapter**: HNSW vector collection initialization and similarity search.

## [v0.1.0] - 2026-08-10

### Added
- **Initial Baseline**: Core platform architecture, database schema (`ops/init.sql`), and documentation suite (`docs/`).
