# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [v0.1.2] - 2026-05-11

### Added
- AMD GPU support with `amdsmi` library for ROCm GPUs
- Multi-vendor hardware detection (NVIDIA → AMD → torch.cuda fallback)

### Fixed
- HF_TOKEN Setup: Use Machine-level environment variable for Docker build
- Line endings normalized to LF for all source files
- CI guardrail reliability improvements
- Worker count validation in entry script

### Changed
- Updated `nvidia-ml-py==13.595.45` (replaces deprecated pynvml)
- Updated dependencies: docling, psycopg, boto3, underthesea

## [v0.1.1] - 2026-05-10

### Fixed
- HF_TOKEN pass-through for Docker build
- Redis Alpine version to stable (8-alpine)

### Changed
- Documentation restructure with parent-child workflow docs

## [v0.1.0] - 2026-05-09

### Added
- Robust document ingestion pipeline with service health checks
- Core RAG pipeline with document management and retrieval services
- FastAPI inference server for embedding and reranking models

### Changed
- Module subdirectory structure refactoring
- Cache base class consolidation

## [v0.0.9] - 2026-05-08

### Added
- Initial implementation milestones

## [v0.0.1] - 2026-05-01

### Added
- Foundation: Initial commit, license, workflows documentation
