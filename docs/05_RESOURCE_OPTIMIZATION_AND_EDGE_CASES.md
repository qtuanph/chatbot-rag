# 05 — Resource Optimization and Edge Cases

Status: operational optimization baseline — updated to reflect rule-based refiner (0GB VRAM).

## Constraint -> Response Matrix

| Constraint | Impact | Recommended response |
|-----------|--------|----------------------|
| Large PDFs and DOCX | long parse duration | keep async queue, track status, avoid request-thread parsing |
| Embedding pressure | memory spikes | embed in batches, configurable batch size |
| Vector write latency | queue slowdown | upsert in bounded chunks, retry idempotently |
| Provider latency | delayed chat | reduced-context retry, then explicit failure |
| Concurrent uploads | worker saturation | cap worker concurrency and queue depth alerts |

## Ingestion Optimization Rules

| Rule | Requirement |
|------|-------------|
| Parser path | Docling-first, deterministic fallback only when needed |
| Hierarchy quality | validate parent links before persistence |
| Artifact quality | persist parse metadata and warnings for audit |
| Duplicate control | run SHA-256 duplicate checks before enqueue |
| Refiner type | **Rule-based only** — 0GB VRAM, ~1ms per node (NO AI in ingestion) |

## Retrieval Optimization Rules

| Rule | Requirement |
|------|-------------|
| Candidate retrieval | vector retrieval from Qdrant + metadata filters |
| Grounding | include parent context for selected nodes |
| Version policy | latest active version preferred |
| Deletion policy | soft-deleted docs excluded from new retrieval |

PostgreSQL should remain a system database for metadata/state, not the primary context-retrieval store or node store.

## Generation Fallback Chain

1. Primary provider generation.
2. Retry with reduced context window.
3. Return explicit grounded limitation if generation still fails.

The system must not return confident ungrounded answers.

## Context Budgeting Guidance

| Component | Budget target |
|-----------|---------------|
| System instructions | 10% |
| Chat history | 20% |
| Retrieved grounded context | 60% |
| Safety margin | 10% |

## Practical Runtime Targets

| Resource | Baseline |
|----------|----------|
| API workers | 2 to 4 |
| Celery workers | 1 to 2 for heavy parsing nodes |
| Upload limit | 50MB per file |
| Chat timeout | 30s default |
