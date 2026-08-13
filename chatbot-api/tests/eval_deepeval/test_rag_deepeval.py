"""
DeepEval Pytest Test Suite
Run via: deepeval test run tests/eval_deepeval/test_rag_deepeval.py
"""

import pytest
from deepeval import assert_test
from deepeval.metrics import (
    FaithfulnessMetric,
    AnswerRelevancyMetric,
    ContextualRecallMetric,
    ContextualPrecisionMetric,
)
from tests.eval_deepeval.custom_model import CustomRAGJudgeLLM
from tests.eval_deepeval.run_deepeval import build_deepeval_test_cases

# Load first 5 sample test cases for standard test run
test_cases = build_deepeval_test_cases(limit=5)
judge_model = CustomRAGJudgeLLM(model="deepeval")


@pytest.mark.parametrize("test_case", test_cases)
def test_rag_faithfulness(test_case):
    metric = FaithfulnessMetric(threshold=0.7, model=judge_model)
    assert_test(test_case, [metric])


@pytest.mark.parametrize("test_case", test_cases)
def test_rag_answer_relevancy(test_case):
    metric = AnswerRelevancyMetric(threshold=0.7, model=judge_model)
    assert_test(test_case, [metric])


@pytest.mark.parametrize("test_case", test_cases)
def test_rag_contextual_recall(test_case):
    metric = ContextualRecallMetric(threshold=0.7, model=judge_model)
    assert_test(test_case, [metric])


@pytest.mark.parametrize("test_case", test_cases)
def test_rag_contextual_precision(test_case):
    metric = ContextualPrecisionMetric(threshold=0.7, model=judge_model)
    assert_test(test_case, [metric])
