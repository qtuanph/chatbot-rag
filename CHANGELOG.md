# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- Continue hardening ingestion/rechunk stability and analytics consistency.
- Improve answer style for end users while keeping anti-hallucination safeguards.

## [v0.1.2] - 2026-05-25

### Fixed
- Stabilized ingestion/rechunk pipeline in Celery daemon workers by preventing child-process spawning conflicts.
- Fixed chat retrieval crash with Qdrant async client (`Unknown arguments: ['timeout']`) in hybrid retrieval path.
- Improved chat answer reliability by tightening prompt rules to avoid fabricated section/chapter/page references.
- Updated Traefik image pin to `v3.7.1` to match valid published tag.
- Synced environment and runtime settings notes for embedding parallelism safe mode (`EMBED_PARALLELISM=0`).

### Changed
- Created patch release `v0.1.2` and published GitHub Release.

## [v0.1.1] - 2026-05-10

### Fixed
- HF_TOKEN pass-through for Docker build.
- Redis Alpine image pinning updates for runtime stability.

### Changed
- Documentation structure refactored into parent-child workflow docs.

## [v0.1.0] - 2026-05-09

### Added
- Core RAG pipeline with document management and retrieval services.
- Initial ingestion flow with health-aware service orchestration.
- FastAPI-based backend for embedding/reranking integration.

### Changed
- Module structure refactoring.
- Cache base abstraction cleanup.
