#!/usr/bin/env python3
"""Offline retrieval eval harness (Recall@k / MRR / nDCG@k).

Two input modes (no live LLM required for offline mode):

1) **Predictions JSONL** — each line already has ranked retrieval ids:
   {
     "id": "q1",
     "ranked_section_ids": ["sec-a", "sec-b", ...],
     "ranked_section_codes": ["3.2.1", "3.1"],   # optional alt id space
     "ranked_document_ids": ["doc-1", ...]         # optional
   }

2) **Golden JSONL** + **predictions** joined by `id`.

Golden format:
   {
     "id": "q1",
     "question": "...",
     "expected_section_ids": ["sec-a"],
     "expected_section_codes": ["3.2.1"],
     "expected_document_ids": ["doc-1"],
     "id_field": "section_ids"   # optional: section_ids|section_codes|document_ids
   }

Optional live mode (requires running stack + PYTHONPATH=chatbot-api):
   --live --tenant-id <uuid>
   Uses retrieve_context() and extracts section_id / section_code from node metadata.

Examples:
  python scripts/eval/run_retrieval_eval.py \\
    --golden tests/eval_fixtures/golden_sample.jsonl \\
    --predictions tests/eval_fixtures/predictions_sample.jsonl

  python scripts/eval/run_retrieval_eval.py \\
    --golden path/to/golden.jsonl \\
    --predictions path/to/preds.jsonl \\
    --ks 1,3,5,10 --out /tmp/retrieval_eval.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

# Allow `python scripts/eval/run_retrieval_eval.py` from chatbot-api/
_SCRIPT_DIR = Path(__file__).resolve().parent
_API_ROOT = _SCRIPT_DIR.parents[1]
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from retrieval_metrics import aggregate_results, evaluate_query  # noqa: E402


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as e:
            raise SystemExit(f"{path}:{line_no}: invalid JSON: {e}") from e
    return rows


def _index_by_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        qid = str(row.get("id") or "").strip()
        if not qid:
            raise SystemExit(f"row missing id: {row!r}")
        if qid in out:
            raise SystemExit(f"duplicate id: {qid}")
        out[qid] = row
    return out


def _pick_relevant(golden: dict[str, Any], id_field: str | None) -> tuple[list[str], str]:
    field = (id_field or golden.get("id_field") or "section_ids").strip()
    mapping = {
        "section_ids": "expected_section_ids",
        "section_codes": "expected_section_codes",
        "document_ids": "expected_document_ids",
    }
    key = mapping.get(field, field if field.startswith("expected_") else mapping["section_ids"])
    # allow direct expected_* override
    if field in ("expected_section_ids", "expected_section_codes", "expected_document_ids"):
        key = field
        field = {
            "expected_section_ids": "section_ids",
            "expected_section_codes": "section_codes",
            "expected_document_ids": "document_ids",
        }[key]
    vals = golden.get(key) or []
    if not isinstance(vals, list):
        vals = [vals]
    return [str(v) for v in vals if str(v).strip()], field


def _pick_ranked(pred: dict[str, Any], field: str) -> list[str]:
    mapping = {
        "section_ids": "ranked_section_ids",
        "section_codes": "ranked_section_codes",
        "document_ids": "ranked_document_ids",
    }
    key = mapping.get(field, f"ranked_{field}")
    # also accept generic ranked_ids
    vals = pred.get(key) or pred.get("ranked_ids") or []
    if not isinstance(vals, list):
        vals = [vals]
    return [str(v) for v in vals if str(v).strip()]


def _parse_ks(raw: str) -> list[int]:
    ks = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        ks.append(int(part))
    return ks or [1, 3, 5, 10, 20]


async def _live_rank(
    *,
    question: str,
    tenant_id: str | None,
    limit: int,
) -> dict[str, list[str]]:
    """Call production retrieve_context and extract id lists from metadata."""
    from app.modules.chat.retrieval.pipeline import retrieve_context

    ctx = await retrieve_context(
        queries=[question],
        limit=limit,
        tenant_id=tenant_id,
    )
    section_ids: list[str] = []
    section_codes: list[str] = []
    document_ids: list[str] = []
    for node in ctx.nodes or []:
        # RagNode dataclass fields (preferred)
        sid = getattr(node, "section_id", None)
        scode = getattr(node, "section_code", None)
        did = getattr(node, "document_id", None)
        if sid:
            section_ids.append(str(sid))
        if scode:
            section_codes.append(str(scode))
        if did:
            document_ids.append(str(did))
    return {
        "ranked_section_ids": section_ids,
        "ranked_section_codes": section_codes,
        "ranked_document_ids": document_ids,
    }


def _print_table(agg: dict, ks: list[int]) -> None:
    print(f"\nQueries: {agg.get('n_queries', 0)}  MRR: {agg.get('mrr', 0):.4f}")
    print(f"{'k':>4}  {'Hit@k':>8}  {'Recall@k':>10}  {'nDCG@k':>10}")
    for k in ks:
        sk = str(k)
        print(
            f"{k:>4}  {agg.get('hit', {}).get(sk, 0):>8.4f}  "
            f"{agg.get('recall', {}).get(sk, 0):>10.4f}  "
            f"{agg.get('ndcg', {}).get(sk, 0):>10.4f}"
        )


def main() -> int:
    ap = argparse.ArgumentParser(description="Offline retrieval Recall@k / MRR / nDCG harness")
    ap.add_argument("--golden", type=Path, required=True, help="Golden JSONL path")
    ap.add_argument(
        "--predictions",
        type=Path,
        default=None,
        help="Predictions JSONL (required unless --live)",
    )
    ap.add_argument("--ks", default="1,3,5,10,20", help="Comma-separated k values")
    ap.add_argument("--out", type=Path, default=None, help="Write full JSON report")
    ap.add_argument(
        "--id-field",
        default=None,
        choices=["section_ids", "section_codes", "document_ids"],
        help="Override id space (default: per-row or section_ids)",
    )
    ap.add_argument("--live", action="store_true", help="Call retrieve_context for each golden query")
    ap.add_argument("--tenant-id", default=None, help="Tenant id for --live")
    ap.add_argument("--limit", type=int, default=20, help="Retrieval limit for --live")
    args = ap.parse_args()

    ks = _parse_ks(args.ks)
    golden_rows = _load_jsonl(args.golden)
    golden = _index_by_id(golden_rows)

    predictions: dict[str, dict[str, Any]] = {}
    if args.live:
        if not args.tenant_id:
            print("WARN: --live without --tenant-id may return empty (tenant filters).", file=sys.stderr)

        async def _run_all() -> dict[str, dict[str, Any]]:
            out: dict[str, dict[str, Any]] = {}
            for qid, g in golden.items():
                q = str(g.get("question") or "").strip()
                if not q:
                    raise SystemExit(f"golden {qid}: missing question for --live")
                ranked = await _live_rank(question=q, tenant_id=args.tenant_id, limit=args.limit)
                out[qid] = {"id": qid, **ranked}
            return out

        predictions = asyncio.run(_run_all())
    else:
        if not args.predictions:
            raise SystemExit("--predictions is required unless --live")
        predictions = _index_by_id(_load_jsonl(args.predictions))

    per_query: list[dict] = []
    missing = 0
    for qid, g in golden.items():
        pred = predictions.get(qid)
        if not pred:
            missing += 1
            per_query.append(
                {
                    "id": qid,
                    "question": g.get("question"),
                    "error": "missing_prediction",
                    "metrics": evaluate_query(ranked_ids=[], relevant_ids=[], ks=ks),
                }
            )
            continue
        relevant, field = _pick_relevant(g, args.id_field)
        ranked = _pick_ranked(pred, field)
        metrics = evaluate_query(ranked_ids=ranked, relevant_ids=relevant, ks=ks)
        per_query.append(
            {
                "id": qid,
                "question": g.get("question"),
                "id_field": field,
                "relevant": relevant,
                "ranked": ranked[: max(ks) if ks else 20],
                "metrics": metrics,
            }
        )

    agg = aggregate_results(per_query, ks=ks)
    agg["missing_predictions"] = missing

    _print_table(agg, ks)
    if missing:
        print(f"\nWARN: {missing} golden rows without predictions", file=sys.stderr)

    report = {"aggregates": agg, "ks": ks, "results": per_query}
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"\nWrote {args.out}")

    # exit 0 always for offline harness (CI can threshold later)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
