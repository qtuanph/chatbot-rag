"""Unit tests for offline retrieval metrics (no Qdrant)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

API_ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = API_ROOT / "scripts" / "eval"
sys.path.insert(0, str(EVAL_DIR))

from retrieval_metrics import (  # noqa: E402
    aggregate_results,
    evaluate_query,
    hit_at_k,
    mrr,
    ndcg_at_k,
    recall_at_k,
)


def test_hit_recall_mrr_basic():
    ranked = ["a", "b", "c", "d"]
    relevant = {"c"}
    assert hit_at_k(ranked, relevant, 2) is False
    assert hit_at_k(ranked, relevant, 3) is True
    assert recall_at_k(ranked, relevant, 3) == 1.0
    assert mrr(ranked, relevant) == pytest.approx(1 / 3)


def test_recall_multilabel():
    ranked = ["a", "b", "c"]
    relevant = {"a", "c", "z"}
    assert recall_at_k(ranked, relevant, 3) == pytest.approx(2 / 3)


def test_ndcg_perfect():
    ranked = ["a", "b", "c"]
    relevant = {"a", "b"}
    assert ndcg_at_k(ranked, relevant, 2) == pytest.approx(1.0)


def test_evaluate_and_aggregate():
    m1 = evaluate_query(ranked_ids=["x", "y"], relevant_ids=["y"], ks=(1, 2))
    m2 = evaluate_query(ranked_ids=["y", "x"], relevant_ids=["y"], ks=(1, 2))
    assert m1["hit"]["1"] is False
    assert m2["hit"]["1"] is True
    rows = [{"metrics": m1}, {"metrics": m2}]
    agg = aggregate_results(rows, ks=(1, 2))
    assert agg["n_queries"] == 2
    assert agg["hit"]["1"] == pytest.approx(0.5)
    assert agg["mrr"] == pytest.approx((0.5 + 1.0) / 2)


def test_cli_sample_fixtures():
    golden = API_ROOT / "tests" / "eval_fixtures" / "golden_sample.jsonl"
    preds = API_ROOT / "tests" / "eval_fixtures" / "predictions_sample.jsonl"
    script = EVAL_DIR / "run_retrieval_eval.py"
    out = API_ROOT / "tests" / "eval_fixtures" / "_out_test.json"
    cp = subprocess.run(
        [
            sys.executable,
            str(script),
            "--golden",
            str(golden),
            "--predictions",
            str(preds),
            "--ks",
            "1,3,5",
            "--out",
            str(out),
        ],
        cwd=str(API_ROOT),
        capture_output=True,
        text=True,
    )
    assert cp.returncode == 0, cp.stderr + cp.stdout
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["aggregates"]["n_queries"] == 4
    assert report["aggregates"]["mrr"] > 0
    out.unlink(missing_ok=True)
