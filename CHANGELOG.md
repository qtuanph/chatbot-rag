# Changelog

All notable changes to the **chatbot-rag** platform will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

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
