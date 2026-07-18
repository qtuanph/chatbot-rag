"""Unit tests for offline retrieval metrics (stdlib unittest — no app conftest)."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
API_ROOT = EVAL_DIR.parents[1]
sys.path.insert(0, str(EVAL_DIR))

from retrieval_metrics import (  # noqa: E402
    aggregate_results,
    evaluate_query,
    hit_at_k,
    mrr,
    ndcg_at_k,
    recall_at_k,
)


class RetrievalMetricsTests(unittest.TestCase):
    def test_hit_recall_mrr_basic(self):
        ranked = ["a", "b", "c", "d"]
        relevant = {"c"}
        self.assertFalse(hit_at_k(ranked, relevant, 2))
        self.assertTrue(hit_at_k(ranked, relevant, 3))
        self.assertEqual(recall_at_k(ranked, relevant, 3), 1.0)
        self.assertAlmostEqual(mrr(ranked, relevant), 1 / 3)

    def test_recall_multilabel(self):
        ranked = ["a", "b", "c"]
        relevant = {"a", "c", "z"}
        self.assertAlmostEqual(recall_at_k(ranked, relevant, 3), 2 / 3)

    def test_ndcg_perfect(self):
        ranked = ["a", "b", "c"]
        relevant = {"a", "b"}
        self.assertAlmostEqual(ndcg_at_k(ranked, relevant, 2), 1.0)

    def test_evaluate_and_aggregate(self):
        m1 = evaluate_query(ranked_ids=["x", "y"], relevant_ids=["y"], ks=(1, 2))
        m2 = evaluate_query(ranked_ids=["y", "x"], relevant_ids=["y"], ks=(1, 2))
        self.assertFalse(m1["hit"]["1"])
        self.assertTrue(m2["hit"]["1"])
        agg = aggregate_results([{"metrics": m1}, {"metrics": m2}], ks=(1, 2))
        self.assertEqual(agg["n_queries"], 2)
        self.assertAlmostEqual(agg["hit"]["1"], 0.5)
        self.assertAlmostEqual(agg["mrr"], (0.5 + 1.0) / 2)

    def test_cli_sample_fixtures(self):
        golden = API_ROOT / "tests" / "eval_fixtures" / "golden_sample.jsonl"
        preds = API_ROOT / "tests" / "eval_fixtures" / "predictions_sample.jsonl"
        script = EVAL_DIR / "run_retrieval_eval.py"
        out = EVAL_DIR / "_out_test.json"
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
        self.assertEqual(cp.returncode, 0, cp.stderr + cp.stdout)
        report = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(report["aggregates"]["n_queries"], 4)
        self.assertGreater(report["aggregates"]["mrr"], 0)
        out.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
