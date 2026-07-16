"""Offline retrieval metrics: Recall@k, MRR, nDCG@k.

Pure functions — no Qdrant / LLM dependency.
Used by `run_retrieval_eval.py` and unit tests.
"""

from __future__ import annotations

import math
from typing import Iterable, Sequence


def _norm(value: str | None) -> str:
    return " ".join(str(value or "").strip().lower().split())


def normalize_id_set(values: Iterable[str] | None) -> set[str]:
    return {_norm(v) for v in (values or []) if _norm(v)}


def hit_at_k(ranked_ids: Sequence[str], relevant: set[str], k: int) -> bool:
    if not relevant or k <= 0:
        return False
    top = {_norm(x) for x in ranked_ids[:k]}
    return bool(top & relevant)


def recall_at_k(ranked_ids: Sequence[str], relevant: set[str], k: int) -> float:
    """Fraction of relevant items found in top-k (multi-label)."""
    if not relevant or k <= 0:
        return 0.0
    top = {_norm(x) for x in ranked_ids[:k]}
    return len(top & relevant) / len(relevant)


def mrr(ranked_ids: Sequence[str], relevant: set[str]) -> float:
    """Mean Reciprocal Rank for a single query (0 if no hit)."""
    if not relevant:
        return 0.0
    for i, rid in enumerate(ranked_ids, start=1):
        if _norm(rid) in relevant:
            return 1.0 / i
    return 0.0


def dcg_at_k(relevances: Sequence[float], k: int) -> float:
    total = 0.0
    for i, rel in enumerate(relevances[:k], start=1):
        total += (2**rel - 1) / math.log2(i + 1)
    return total


def ndcg_at_k(ranked_ids: Sequence[str], relevant: set[str], k: int) -> float:
    """Binary relevance nDCG@k."""
    if not relevant or k <= 0:
        return 0.0
    gains = [1.0 if _norm(rid) in relevant else 0.0 for rid in ranked_ids[:k]]
    dcg = dcg_at_k(gains, k)
    ideal = dcg_at_k(sorted(gains, reverse=True), k)
    if ideal <= 0:
        return 0.0
    return dcg / ideal


def first_hit_rank(ranked_ids: Sequence[str], relevant: set[str]) -> int | None:
    for i, rid in enumerate(ranked_ids, start=1):
        if _norm(rid) in relevant:
            return i
    return None


def evaluate_query(
    *,
    ranked_ids: Sequence[str],
    relevant_ids: Sequence[str],
    ks: Sequence[int] = (1, 3, 5, 10, 20),
) -> dict:
    relevant = normalize_id_set(relevant_ids)
    ranked = [_norm(x) for x in ranked_ids if _norm(x)]
    out: dict = {
        "n_ranked": len(ranked),
        "n_relevant": len(relevant),
        "mrr": round(mrr(ranked, relevant), 6),
        "first_hit_rank": first_hit_rank(ranked, relevant),
        "hit": {},
        "recall": {},
        "ndcg": {},
    }
    for k in ks:
        out["hit"][str(k)] = hit_at_k(ranked, relevant, k)
        out["recall"][str(k)] = round(recall_at_k(ranked, relevant, k), 6)
        out["ndcg"][str(k)] = round(ndcg_at_k(ranked, relevant, k), 6)
    return out


def aggregate_results(per_query: list[dict], ks: Sequence[int] = (1, 3, 5, 10, 20)) -> dict:
    if not per_query:
        return {"n_queries": 0}
    n = len(per_query)
    agg: dict = {"n_queries": n, "mrr": 0.0, "hit": {}, "recall": {}, "ndcg": {}}
    for k in ks:
        sk = str(k)
        hits = sum(1 for q in per_query if q.get("metrics", {}).get("hit", {}).get(sk))
        agg["hit"][sk] = round(hits / n, 6)
        agg["recall"][sk] = round(
            sum(q.get("metrics", {}).get("recall", {}).get(sk, 0.0) for q in per_query) / n, 6
        )
        agg["ndcg"][sk] = round(
            sum(q.get("metrics", {}).get("ndcg", {}).get(sk, 0.0) for q in per_query) / n, 6
        )
    agg["mrr"] = round(sum(q.get("metrics", {}).get("mrr", 0.0) for q in per_query) / n, 6)
    return agg
