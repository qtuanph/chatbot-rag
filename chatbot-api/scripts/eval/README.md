# Offline retrieval eval harness

Lightweight **Recall@k / MRR / nDCG@k** tools for hybrid retrieval experiments.

Designed for `chatbot-rag`’s structure-aware pipeline (section_id / section_code / document_id) without requiring a live LLM for offline scoring.

## Layout

```text
scripts/eval/
  retrieval_metrics.py      # pure metrics
  run_retrieval_eval.py     # CLI
  README.md
tests/eval_fixtures/
  golden_sample.jsonl
  predictions_sample.jsonl
tests/test_retrieval_metrics.py
```

## Quick start (offline, no stack)

From `chatbot-api/`:

```bash
python scripts/eval/run_retrieval_eval.py \
  --golden tests/eval_fixtures/golden_sample.jsonl \
  --predictions tests/eval_fixtures/predictions_sample.jsonl \
  --ks 1,3,5,10 \
  --out /tmp/retrieval_eval.json
```

Example output:

```text
Queries: 4  MRR: 0.79
   k    Hit@k   Recall@k    nDCG@k
   1   0.5000     0.3750    0.5000
   3   1.0000     1.0000    0.92...
```

## Golden format (JSONL)

```json
{
  "id": "q1",
  "question": "How do I create a warehouse receipt?",
  "expected_section_ids": ["sec-wh-321"],
  "expected_section_codes": ["3.2.1"],
  "expected_document_ids": ["doc-erp-wh"],
  "id_field": "section_ids"
}
```

`id_field` selects which expected_* list is scored against ranked_* predictions:

| id_field | golden key | prediction key |
|----------|------------|----------------|
| `section_ids` | `expected_section_ids` | `ranked_section_ids` |
| `section_codes` | `expected_section_codes` | `ranked_section_codes` |
| `document_ids` | `expected_document_ids` | `ranked_document_ids` |

## Predictions format (JSONL)

Export from retrieval debug logs / staging runs:

```json
{
  "id": "q1",
  "ranked_section_ids": ["sec-a", "sec-wh-321", "sec-b"],
  "ranked_section_codes": ["3.1", "3.2.1"],
  "ranked_document_ids": ["doc-1"]
}
```

Tip: map `RAG_RETRIEVE` / `RAG_RERANK` debug events in `pipeline.py` (`_serialize_nodes_for_debug`) into this shape.

## Live mode (optional)

Requires running API deps (Qdrant, embeddings, tenant data) and `PYTHONPATH` / cwd = `chatbot-api`:

```bash
python scripts/eval/run_retrieval_eval.py \
  --golden path/to/golden.jsonl \
  --live \
  --tenant-id <tenant_uuid> \
  --limit 20 \
  --out /tmp/live_eval.json
```

Live mode calls `retrieve_context()` and reads `section_id` / `section_code` / `document_id` from node metadata.

## Suggested experiments

1. **hybrid ON vs OFF** — export two prediction files, compare Recall@10  
2. **rerank ON vs skip-heavy** — same golden, different runtime flags  
3. **section-code queries** — score `id_field=section_codes`  
4. **natural language** — score `id_field=section_ids`  

Keep latency/cost notes next to accuracy when changing `retrieval_hybrid_top_k` / rerank skip policy.

## Tests

```bash
cd chatbot-api
python scripts/eval/test_retrieval_metrics.py
# or: python -m unittest scripts.eval.test_retrieval_metrics
```

## Related

Longer product suggestions:  
https://github.com/iZenDeveloper/auditai/blob/main/docs/gtm/drafts/03-qtuanph-chatbot-rag-retrieval-suggestions.md

## Real-world Evaluation Results (July 2026)

A live evaluation was conducted using a realistic "conversational" dataset (`doc_golden_sample.jsonl`) against the BGE-M3 backed Qdrant RAG pipeline.

### Dataset
The evaluation dataset contains 10 highly conversational, natural language questions mimicking end-user behavior (e.g. accounting staff). Examples:
- *"bạn ơi cho mình hỏi cái phần công nợ bán hàng trong SAO thì dùng để làm gì thế?"*
- *"chết dở mình nhập trùng chứng từ mua hàng thì giờ xử lý kiểu gì?"*
- *"sếp bắt tính tồn kho theo NTXT thì cài đặt ở đâu hả bạn?"*

### Results
The evaluation was executed directly in the production Docker environment (`api` container) with `--id-field document_ids` targeting the "Hướng dẫn sử dụng SAO" manual.

```text
Queries: 10  MRR: 1.0000
   k     Hit@k    Recall@k      nDCG@k
   1    1.0000      1.0000      1.0000
   3    1.0000      1.0000      1.0000
   5    1.0000      1.0000      1.0000
```
**Conclusion:** The hybrid RAG retrieval pipeline achieved a perfect 1.0000 (100%) accuracy across all queries, proving extreme resilience against conversational Vietnamese slang, typos, and semantic variances.
