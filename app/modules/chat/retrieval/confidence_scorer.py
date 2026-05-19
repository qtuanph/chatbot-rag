"""Retrieval confidence scoring — score-based failure detection."""

from __future__ import annotations

from typing import Any

from app.adapters.base import RetrievedDocument
from app.core.config import settings


class RetrievalConfidence:
    @staticmethod
    def score(results: list[RetrievedDocument]) -> dict[str, Any]:
        """Evaluate retrieval quality based on score distribution.

        Returns:
            dict with keys:
                - confidence: "high" | "medium" | "low" | "no_results"
                - max_score: float
                - avg_score: float
                - status: str
        """
        if not results:
            return {"confidence": "no_results", "max_score": 0.0, "avg_score": 0.0, "status": "no_results"}

        max_score = max(r.score for r in results)
        avg_score = sum(r.score for r in results) / len(results)

        if (
            max_score >= settings.retrieval_confidence_threshold_high
            and avg_score >= settings.retrieval_confidence_avg_high
        ):
            return {"confidence": "high", "max_score": max_score, "avg_score": avg_score, "status": "correct"}
        elif max_score >= settings.retrieval_confidence_threshold_low:
            return {"confidence": "medium", "max_score": max_score, "avg_score": avg_score, "status": "ambiguous"}
        else:
            return {"confidence": "low", "max_score": max_score, "avg_score": avg_score, "status": "incorrect"}
