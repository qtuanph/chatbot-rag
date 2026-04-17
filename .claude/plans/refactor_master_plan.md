# Refactor Master Plan Snapshot

This is a local `.claude` snapshot for implementation tracking.
Canonical planning context may also exist in session memory.

## Strategic Goals

1. Reach code maintainability target 9.5/10.
2. Reach REST API production-readiness target 9.5/10.
3. Reach AI-readable documentation target 9.5/10.

## Implementation Direction

1. Enforce Docs-First workflow for all AI tasks.
2. Harden REST APIs incrementally (P1 -> P2 -> P3) with frontend contract sync after each API batch.
3. Refactor backend structure (repository/DI/domain split) in small safe batches.
4. Refactor frontend structure incrementally (hooks/components/client typing).
5. Upgrade docs in place to a single canonical set.

## Delivery Mode

1. Small batches, limited file changes per batch.
2. Validate after each batch.
3. Keep API behavior stable unless explicitly planned.
4. Keep `.claude` memory synchronized with architecture changes.
