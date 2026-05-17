"""RAGAS Evaluation - Measure RAG quality metrics."""

from __future__ import annotations

import logging
from typing import Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RagasaMetrics:
    """RAGAS evaluation results."""

    faithfulness: float
    answer_relevancy: float
    context_relevancy: float
    answer_similarity: float
    overall_score: float


class RagasEvaluator:
    """
    Evaluate RAG quality using RAGAS metrics.

    Metrics:
    - Faithfulness: Does the answer match the context?
    - Answer Relevancy: Is the answer relevant to the query?
    - Context Relevancy: Is the retrieved context relevant?
    """

    def __init__(self, ai_provider: Any = None) -> None:
        self.ai_provider = ai_provider

    async def evaluate(
        self,
        query: str,
        answer: str,
        contexts: list[str],
        ground_truth: str | None = None,
    ) -> RagasaMetrics:
        """
        Evaluate RAG quality.

        Args:
            query: User query
            answer: Generated answer
            contexts: List of retrieved context strings
            ground_truth: Optional ground truth answer for comparison

        Returns:
            RagasaMetrics with scores (0-1)
        """
        if not answer or not contexts:
            return RagasaMetrics(
                faithfulness=0.0,
                answer_relevancy=0.0,
                context_relevancy=0.0,
                answer_similarity=0.0,
                overall_score=0.0,
            )

        context_combined = "\n\n".join(contexts[:3])

        faithfulness = await self._eval_faithfulness(query, answer, context_combined)
        answer_relevancy = await self._eval_answer_relevancy(query, answer)
        context_relevancy = await self._eval_context_relevancy(query, context_combined)

        answer_similarity = 0.0
        if ground_truth:
            answer_similarity = await self._eval_similarity(answer, ground_truth)

        overall = (faithfulness + answer_relevancy + context_relevancy + answer_similarity) / 4

        return RagasaMetrics(
            faithfulness=faithfulness,
            answer_relevancy=answer_relevancy,
            context_relevancy=context_relevancy,
            answer_similarity=answer_similarity,
            overall_score=overall,
        )

    async def _eval_faithfulness(self, query: str, answer: str, context: str) -> float:
        """Evaluate if answer is faithful to context."""
        prompt = (
            f"Đánh giá độ trung thực của câu trả lời với ngữ cảnh (0-1).\n"
            f"Câu hỏi: {query}\n"
            f"Câu trả lời: {answer}\n"
            f"Ngữ cảnh: {context[:500]}\n"
            f"Chỉ trả lời một số từ 0.0 đến 1.0, ví dụ: 0.85"
        )
        return await self._get_score(prompt)

    async def _eval_answer_relevancy(self, query: str, answer: str) -> float:
        """Evaluate if answer is relevant to query."""
        prompt = (
            f"Đánh giá mức độ liên quan của câu trả lời với câu hỏi (0-1).\n"
            f"Câu hỏi: {query}\n"
            f"Câu trả lời: {answer}\n"
            f"Chỉ trả lời một số từ 0.0 đến 1.0, ví dụ: 0.85"
        )
        return await self._get_score(prompt)

    async def _eval_context_relevancy(self, query: str, context: str) -> float:
        """Evaluate if context is relevant to query."""
        prompt = (
            f"Đánh giá mức độ liên quan của ngữ cảnh với câu hỏi (0-1).\n"
            f"Câu hỏi: {query}\n"
            f"Ngữ cảnh: {context[:500]}\n"
            f"Chỉ trả lời một số từ 0.0 đến 1.0, ví dụ: 0.85"
        )
        return await self._get_score(prompt)

    async def _eval_similarity(self, answer: str, ground_truth: str) -> float:
        """Evaluate similarity between answer and ground truth."""
        prompt = (
            f"Đánh giá độ tương đồng giữa câu trả lời và câu trả lời chuẩn (0-1).\n"
            f"Câu trả lời: {answer}\n"
            f"Câu trả lời chuẩn: {ground_truth}\n"
            f"Chỉ trả lời một số từ 0.0 đến 1.0, ví dụ: 0.85"
        )
        return await self._get_score(prompt)

    async def _get_score(self, prompt: str) -> float:
        """Get numeric score from AI."""
        try:
            provider = self.ai_provider or self._get_default_provider()
            response = await provider.chat(messages=[{"role": "user", "content": prompt}])
            text = response.get("answer", "") if isinstance(response, dict) else str(response)
            import re

            match = re.search(r"0?\.\d+", text)
            return float(match.group()) if match else 0.5
        except Exception as e:
            logger.warning("RAGAS score evaluation failed: %s", e)
            return 0.5

    def _get_default_provider(self):
        from app.adapters.ai.cliproxy_bridge import CLIProxyBridge

        return CLIProxyBridge()
