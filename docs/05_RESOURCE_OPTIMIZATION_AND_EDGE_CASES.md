# 05 — Resource Optimization and Edge Cases

> Status: target production operating guidance for later implementation phases.

## Constraint → Solution Matrix

## Intent Clarification For AI Coding

| Common wrong interpretation | Correct behavior |
|-----------------------------|------------------|
| "Need fast search" -> add new specialized DB | Stay with PostgreSQL + pgvector for this scale |
| "Tree-based" -> build binary tree | Build document hierarchy with many children per node |
| "Need easy setup" -> skip containers and run locally | Prefer Docker Compose as the default runtime path |
| "Need fallback" -> return ungrounded answer | Return grounded partial answer or explicit failure |

| Constraint | Impact | Solution |
|------------|--------|----------|
| **VRAM limit (12-24GB)** | Can't load large models + embeddings simultaneously | Quantized models (AWQ/GGUF), unload embeddings during generation, batch size = 1 |
| **GPU bottleneck** | Parse blocks generation, or vice versa | Separate API and Worker processes, Celery queue isolates heavy tasks |
| **Parse blocking** | Large PDFs take minutes to OCR | Async Celery task, progress tracking, user notified when ready |
| **Memory peak** | Loading full document text into memory | Stream parsing, process section by section, gc.collect() after each doc |
| **Repeated queries** | Same query hits LLM repeatedly, wastes tokens | Cache identical queries (TTL 5min), return cached response |
| **LLM timeout** | Google AI Studio or vLLM slow/unavailable | 30s timeout, fallback chain (see below) |
| **Embedding OOM** | Too many headings at once | Batch embed (batch_size=32), checkpoint after each batch |
| **Concurrent uploads** | Multiple users upload simultaneously | Celery concurrency limit = 2, queue the rest |
| **CPU-only deployment** | 20 concurrent users will have degraded latency | Safest fallback: smaller 7B quantized model, lower concurrency, async-first UX, and explicit latency warning |

## Fallback Strategy Chain

```
Phase 1:   Google AI Studio adapter
    |
    v (on-prem migration complete)
Phase 2:   vLLM + quantized Qwen2.5-7B/14B-AWQ
    |
    v (timeout / error)
Fallback 1: Retry once with reduced context (top-3 sections instead of top-5)
    |
    v (still failing)
Fallback 2: BM25 + cosine similarity only (no LLM routing)
    |
    v (still failing)
Fallback 3: Strict prompt with retrieved sections, no chat history
    |
    v (still failing)
Final:     partial answer + warning, or explicit failure if no grounded answer exists
```

### Fallback Implementation

```python
async def chat_with_fallback(query: str, project_id: str) -> AsyncGenerator:
    try:
        async for chunk in primary_provider.chat(query, project_id):
            yield chunk
    except TimeoutError:
        # Fallback 1: reduced context
        async for chunk in primary_provider.chat(query, project_id, top_k=3):
            yield chunk
    except ProviderError:
        # Fallback 2: hybrid retrieval without router dependence
        sections = hybrid_search_bm25_cosine(query, project_id)
        async for chunk in strict_prompt(sections):
            yield chunk
    except Exception:
        sections = hybrid_search_bm25_cosine(query, project_id)
        yield "[Warning] Primary generation is unavailable. Returning a partial grounded answer."
        async for chunk in synthesize_grounded_partial_answer(sections):
            yield chunk
```

> Remote-provider adapters are acceptable for the demo phase. Once on-prem rollout is complete, production fallback should remain grounded in local retrieval so the system still works during provider or network outages.

> **Tradeoff:** `vLLM` is the production path for GPU-backed nodes. On CPU-only hardware, the system remains functional but should not be sold as low-latency for 20 concurrent users; queueing and smaller models are the safest fallback.

## Optimization Invariants

| Rule | Requirement |
|------|-------------|
| Context budget | MUST keep retrieved content within 60% of window |
| Section integrity | MUST trim on section or sentence boundaries; MUST NOT cut arbitrary token spans from the middle of a section |
| Fallback quality | MUST prefer grounded partial answers over confident unsupported answers |
| Duplicate handling | MUST run SHA-256 pre-check before parse and node similarity check after parse |
| Resource safety | MUST batch embeddings and reranking to avoid OOM on 4070-class GPUs |

## AI Coding Guardrails

| Preferred implementation | Avoid |
|--------------------------|-------|
| Config-driven thresholds and batch sizes | Hardcoded magic numbers scattered across modules |
| Hybrid fallback retrieval | Returning empty answers immediately on first provider timeout |
| Latency warnings in degraded mode | Hiding degraded-mode behavior from callers |

## Context Budgeting Rules

| Rule | Description |
|------|-------------|
| Max retrieved content | <= 60% of context window |
| Parent injection | Always include parent heading for context |
| No arbitrary cutting | Never cut mid-sentence; trim at section boundary |
| History truncation | Keep last 5 turns, summarize older if needed |
| System prompt | Fixed, ~10% of window |

### Context Assembly Example

```
[System Prompt ~10%]
You are a helpful assistant. Answer based ONLY on provided documents.
Cite your sources.

[Chat History ~20%]
User: What is the leave policy?
Assistant: The leave policy provides 12 days annually...

[Retrieved Sections ~60%]
=== HR Policy > Leave Policy ===
Full section text here...

=== HR Policy > Public Holidays ===
Full section text here...

[User Query]
How many sick days do I get?
```

## Duplicate & Conflict Handling

### SHA-256 Pre-Check (Document Level)

```python
async def check_duplicate(sha256: str, project_id: str) -> Optional[Document]:
    """Return existing document if exact match found."""
    return await db.query(Document).filter_by(
        sha256=sha256,
        project_id=project_id,
        deleted_at=None
    ).first()
```

### Node-Level Dedup (Within Document)

| Threshold | Action |
|-----------|--------|
| Cosine similarity > 0.95 | Mark as duplicate, link to original |
| Cosine similarity 0.85-0.95 | Flag for review, keep both |
| Cosine similarity < 0.85 | Keep as unique node |

### Version Priority

| Scenario | Behavior |
|----------|----------|
| Same filename, same SHA-256 | Reject as duplicate |
| Same filename, different SHA-256 | New version, old version superseded |
| Different filename, same SHA-256 | Reject as duplicate (content identical) |
| Different filename, different SHA-256 | New document |

### Ambiguity Flagging

```python
# Flag when retrieved sections have conflicting information
if has_conflict(sections):
    response += "\n\n[Note: Multiple documents contain conflicting information on this topic.]"
    ambiguity_flag = True
```

## Resource Limits for ~20 Concurrent Users

| Resource | Limit | Rationale |
|----------|-------|-----------|
| Celery workers | 2 | Enough for async parsing without starving GPU |
| API workers (uvicorn) | 4 | Handle concurrent chat requests |
| Redis memory | 512MB | Queue + caching |
| PostgreSQL connections | 20 | 1 per concurrent user max |
| Upload size limit | 50MB per file | Prevent memory exhaustion |
| Chat timeout | 30s | Fail fast, fallback gracefully |
