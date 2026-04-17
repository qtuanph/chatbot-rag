# On Load Hook - Docs-First Checklist

Run this checklist at the start of any coding task.

## Step 1 - Discover

1. Confirm `CLAUDE.md` exists at repository root.
2. Confirm `docs/` exists and contains core architecture/workflow docs.
3. Confirm `.claude/MEMORY.md` exists for condensed context.

## Step 2 - Load (Mandatory Read Order)

1. `CLAUDE.md`
2. `docs/01_SYSTEM_ARCHITECTURE.md`
3. `docs/03_CORE_WORKFLOWS.md`
4. `docs/07_INGESTION_AND_RETRIEVAL_STRATEGY.md`
5. Task-specific docs:
   - API/Security: `docs/04_API_CONTRACT_AND_SECURITY.md`
   - DB/Schema: `docs/02_DATABASE_AND_PROJECT.md` + `ops/init.sql`
   - Deploy/Monitoring: `docs/06_DEPLOYMENT_AND_OBSERVABILITY.md`
   - Performance: `docs/05_RESOURCE_OPTIMIZATION_AND_EDGE_CASES.md`

## Step 3 - Verify Before Coding

The agent must be able to answer:

1. What retrieval strategy is used?
2. Where are sections stored?
3. Where are chunks stored?
4. Current embedding model and dimension?
5. Hard-delete ordering and rationale?

If any answer is unclear, stop and re-read docs before editing code.

## Step 4 - Update After Changes

When architecture/workflow/contracts change:

1. Update `CLAUDE.md` first.
2. Update `.claude` memory files that reference changed behavior.
3. Keep memory consistent with `CLAUDE.md` (no contradictions).
