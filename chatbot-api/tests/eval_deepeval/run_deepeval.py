"""
==========================================================================================
 🌟 DEEPEVAL PRODUCTION ENTERPRISE RAG EVALUATION SUITE (DIRECT PROJECT IMPORTS)
==========================================================================================
100% Native Integration with Production Codebase:
  - Document Preprocessor : `MarkdownCleaner` (`app.adapters.parsers.markdown_cleaner`)
  - Query Normalizer     : `normalize_query` (`app.modules.chat.utils.query_normalizer`)
  - Prompt Synthesizer   : `PublicInferenceService._build_messages` (`app.modules.inference.service`)
  - Refusal Guardrail    : `is_unanswered_response` (`app.modules.inference.service`)
  - Data Structures      : `RagNode`, `RagContext` (`app.models.rag`)
  - DeepEval Evaluation  : 4 Pillars (Retrieval, Generation, Safety, ERP Domain G-Eval)
==========================================================================================
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Reconfigure stdout for UTF-8 encoding on Windows
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# ── DIRECT IMPORTS FROM PRODUCTION PROJECT MODULES ───────────────────────────
from app.adapters.parsers.markdown_cleaner import MarkdownCleaner
from app.models.rag import RagNode, RagContext
from app.modules.chat.utils.query_normalizer import normalize_query
from app.modules.inference.service import PublicInferenceService, is_unanswered_response

# ── DEEPEVAL TEST CASE & METRICS ─────────────────────────────────────────────
from deepeval.test_case import LLMTestCase, SingleTurnParams
from deepeval.metrics import (
    ContextualRecallMetric,
    ContextualPrecisionMetric,
    ContextualRelevancyMetric,
    FaithfulnessMetric,
    AnswerRelevancyMetric,
    HallucinationMetric,
    ToxicityMetric,
    BiasMetric,
    GEval,
)
from tests.benchmark.run_benchmark import parse_markdown, EnterpriseHybridRAG
from tests.eval_deepeval.custom_model import CustomRAGJudgeLLM


def synthesize_via_production_pipeline(
    inference_service: PublicInferenceService,
    judge_llm: CustomRAGJudgeLLM,
    query: str,
    retrieved_candidates: list[tuple[float, dict, str]],
) -> tuple[str, list[str]]:
    """Synthesizes response using the EXACT production prompt builder and data structures."""
    rag_nodes: list[RagNode] = []

    for idx, (score, sec, full_context) in enumerate(retrieved_candidates):
        node = RagNode(
            node_id=f"node-{idx+1}",
            parent_id=None,
            document_id="doc-sao-erp",
            document_title="Tài liệu kỹ thuật SSE Accounting Online",
            heading=sec.get("title") or "Chung",
            section_code=sec.get("section_code"),
            summary=None,
            full_text=full_context,
            page_range=sec.get("page_range"),
            breadcrumb=tuple(sec.get("breadcrumb") or ()),
            score=score,
        )
        rag_nodes.append(node)

    rag_context = RagContext(nodes=rag_nodes)

    # 1. Build messages using EXACT production function (_build_messages)
    llm_messages = inference_service._build_messages(
        messages=[{"role": "user", "content": query}],
        setting={"system_instruction": "Tư vấn chính xác, đầy đủ theo tài liệu phần mềm SAO."},
        context=rag_context,
    )

    # 2. Format messages for LLM completion
    prompt_payload = []
    for msg in llm_messages:
        role_str = getattr(msg.role, "value", str(msg.role)).lower()
        if "system" in role_str:
            role = "system"
        elif "user" in role_str:
            role = "user"
        else:
            role = "assistant"
        prompt_payload.append({"role": role, "content": msg.content})

    # 3. Call 9Router model
    client = judge_llm.load_model()
    resp = client.chat.completions.create(
        model=judge_llm.model_name,
        messages=prompt_payload,
        temperature=0.0,
    )
    actual_output = resp.choices[0].message.content or ""
    retrieval_context_texts = [n.full_text for n in rag_nodes] if rag_nodes else ["Không tìm thấy tài liệu phù hợp."]

    return actual_output, retrieval_context_texts


def build_deepeval_test_cases(
    judge_llm: CustomRAGJudgeLLM,
    limit: int | None = None,
    sample_diverse: bool = False,
    selected_ids: list[str] | None = None,
    top_k: int = 5,
) -> list[LLMTestCase]:
    """Load golden dataset, preprocess document via MarkdownCleaner, retrieve context, and construct test cases."""
    dataset_path = BASE_DIR / "chatbot-api" / "tests" / "benchmark" / "sao_erp_benchmark_dataset.json"
    if not dataset_path.exists():
        dataset_path = BASE_DIR / "tests" / "benchmark" / "sao_erp_benchmark_dataset.json"

    doc_path = BASE_DIR / "chatbot-api" / "tests" / "file_test" / "test_tailieukythuat.md"
    if not doc_path.exists():
        doc_path = BASE_DIR / "tests" / "file_test" / "test_tailieukythuat.md"

    with open(dataset_path, "r", encoding="utf-8") as f:
        cases_data = json.load(f)

    if selected_ids:
        selected_set = {sid.strip().upper() for sid in selected_ids}
        cases_data = [c for c in cases_data if c.get("id", "").upper() in selected_set]
    elif sample_diverse:
        # Sample diverse representatives across categories (Factoid, Accounting, Synthesis, Admin, Paraphrase, UI Shortcuts, Trap)
        diverse_ids = {"BM-01", "BM-05", "BM-10", "BM-14", "BM-19", "BM-35"}
        cases_data = [c for c in cases_data if c.get("id") in diverse_ids]
    elif limit and limit > 0:
        cases_data = cases_data[:limit]

    with open(doc_path, "r", encoding="utf-8") as f:
        raw_doc_content = f.read()

    # 1. Preprocess document using EXACT production MarkdownCleaner
    cleaner = MarkdownCleaner()
    cleaned_doc_content = cleaner.clean(raw_doc_content)

    sections = parse_markdown(cleaned_doc_content)
    rag_engine = EnterpriseHybridRAG(sections)
    inference_service = PublicInferenceService(tenant_repo=None, section_repo=None)

    test_cases = []
    print(f"🔄 Executing REAL production pipeline for {len(cases_data)} questions via 9Router LLM (top_k={top_k})...")

    for i, item in enumerate(cases_data, 1):
        query = item.get("query") or item.get("question")
        expected_output = item.get("ground_truth") or item.get("expected_answer")
        category = item.get("category", "General")
        cid = item.get("id", f"BM-{i:02d}")

        # 2. Normalize query using EXACT production normalize_query
        norm_query = normalize_query(query)

        # 3. Retrieve top candidates (top_k=5 production default)
        candidates = rag_engine.retrieve(norm_query or query, top_k=top_k)

        # 4. Synthesize answer using EXACT production prompt builder (_build_messages)
        actual_output, retrieval_context = synthesize_via_production_pipeline(
            inference_service=inference_service,
            judge_llm=judge_llm,
            query=query,
            retrieved_candidates=candidates,
        )

        # Check refusal using EXACT production is_unanswered_response
        if is_unanswered_response(actual_output):
            print(f"  [{cid}] ({category}) ❓ \"{query[:40]}...\" -> 🛡️ Refused by Guardrail")
        else:
            print(f"  [{cid}] ({category}) ❓ \"{query[:40]}...\" -> 💬 Grounded Output ({len(actual_output)} chars)")

        tc = LLMTestCase(
            input=query,
            actual_output=actual_output,
            expected_output=expected_output,
            context=retrieval_context,
            retrieval_context=retrieval_context,
        )
        # Store metadata for detailed reporting
        tc.additional_metadata = {"id": cid, "category": category}
        test_cases.append(tc)

    return test_cases


def run_deepeval_evaluation(
    limit: int | None = 6,
    sample_diverse: bool = True,
    selected_ids: list[str] | None = None,
    top_k: int = 5,
):
    print("=" * 100)
    print(" 🌟 DEEPEVAL PRODUCTION ENTERPRISE RAG EVALUATION (100% PRODUCTION CODE IMPORTS) ")
    print("=" * 100)
    print("🤖 Model Judge  : deepeval via 9Router (http://localhost:20128/v1)")
    print("📦 Preprocessor : `MarkdownCleaner` (app.adapters.parsers.markdown_cleaner)")
    print("📦 Normalizer   : `normalize_query` (app.modules.chat.utils.query_normalizer)")
    print("📦 Prompt Eng.  : `PublicInferenceService._build_messages` (app.modules.inference.service)")
    print("📦 Guardrail    : `is_unanswered_response` (app.modules.inference.service)")
    print(f"📋 Scope Mode   : {'Diverse Multi-Category Sample' if sample_diverse else f'Limit {limit}'}")
    print("=" * 100)

    judge_model = CustomRAGJudgeLLM(model="deepeval")
    test_cases = build_deepeval_test_cases(
        judge_llm=judge_model,
        limit=limit,
        sample_diverse=sample_diverse,
        selected_ids=selected_ids,
        top_k=top_k,
    )

    # ─────────────────────────────────────────────────────────────────────────────
    # Initialize Full 100% Metrics across 4 Pillars
    # ─────────────────────────────────────────────────────────────────────────────

    # 1. Retrieval Process Metrics (Đo khâu Lấy Dữ Liệu)
    m_ctx_recall = ContextualRecallMetric(threshold=0.7, model=judge_model)
    m_ctx_precision = ContextualPrecisionMetric(threshold=0.7, model=judge_model)
    m_ctx_relevancy = ContextualRelevancyMetric(threshold=0.7, model=judge_model)

    # 2. Generation & Truthfulness Metrics (Đo khâu Sinh Lời & Chống Ảo Giác)
    m_faithfulness = FaithfulnessMetric(threshold=0.7, model=judge_model)
    m_ans_relevancy = AnswerRelevancyMetric(threshold=0.7, model=judge_model)
    m_hallucination = HallucinationMetric(threshold=0.3, model=judge_model)

    # 3. Safety & Brand Tone Metrics (Đo An Toàn & Đạo Đức)
    m_toxicity = ToxicityMetric(threshold=0.1, model=judge_model)
    m_bias = BiasMetric(threshold=0.1, model=judge_model)

    # 4. G-Eval Domain ERP Metrics (Đo Nghiệp Vụ Kế Toán Phần Mềm SAO)
    g_erp_accuracy = GEval(
        name="ERP Accounting Accuracy",
        criteria="Đánh giá tính chính xác của các số tài khoản, mã phiếu thu/chi, chức vụ nhân sự và quy trình chứng từ trong phần mềm SAO theo đúng tài liệu kỹ thuật.",
        evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT, SingleTurnParams.EXPECTED_OUTPUT],
        model=judge_model,
        threshold=0.7,
    )

    all_metrics = [
        # (Group, Metric Name, Metric Instance, Inverted (Lower is Better))
        ("1. RETRIEVAL PROCESS", "Contextual Recall", m_ctx_recall, False),
        ("1. RETRIEVAL PROCESS", "Contextual Precision", m_ctx_precision, False),
        ("1. RETRIEVAL PROCESS", "Contextual Relevancy", m_ctx_relevancy, False),
        ("2. GENERATION & TRUTH", "Faithfulness", m_faithfulness, False),
        ("2. GENERATION & TRUTH", "Answer Relevancy", m_ans_relevancy, False),
        ("2. GENERATION & TRUTH", "Hallucination Rate", m_hallucination, True),
        ("3. SAFETY & TONE", "Toxicity Rate", m_toxicity, True),
        ("3. SAFETY & TONE", "Bias Rate", m_bias, True),
        ("4. DOMAIN G-EVAL", "ERP Accounting Accuracy", g_erp_accuracy, False),
    ]

    results_summary = []
    print("\n🚀 Starting DeepEval LLM-as-a-Judge Evaluation across all 9 Metrics...")

    for idx, tc in enumerate(test_cases, 1):
        meta = getattr(tc, "additional_metadata", {})
        cid = meta.get("id", f"BM-{idx:02d}")
        cat = meta.get("category", "General")

        print(f"\n[Case {idx:02d}/{len(test_cases):02d}] 🏷️ [{cid}] ({cat}) ❓ \"{tc.input[:55]}...\"")
        print(f"   💬 Assistant: \"{tc.actual_output[:80]}...\"")
        case_scores = {}

        for group, name, metric, is_inverted in all_metrics:
            t0 = time.perf_counter()
            try:
                metric.measure(tc)
                score = float(getattr(metric, "score", 0.0))
                passed = getattr(metric, "is_successful", lambda: (score <= metric.threshold if is_inverted else score >= metric.threshold))()
                reason = getattr(metric, "reason", "Evaluated successfully")
                elapsed = (time.perf_counter() - t0) * 1000
                case_scores[name] = {"group": group, "score": score, "passed": passed, "reason": reason}
                status_icon = "✅ PASS" if passed else "⚠️ WARN"
                print(f"   -> {status_icon} | [{group[:12]}] {name:<25}: {score:.2f} ({elapsed:.0f}ms) | {reason[:50]}...")
            except Exception as e:
                case_scores[name] = {"group": group, "score": 0.0, "passed": False, "reason": str(e)}
                print(f"   -> ❌ ERR  | [{group[:12]}] {name:<25}: Error ({e})")

        results_summary.append({
            "index": idx,
            "id": cid,
            "category": cat,
            "input": tc.input,
            "actual_output": tc.actual_output,
            "expected_output": tc.expected_output,
            "scores": case_scores,
        })

    # ─────────────────────────────────────────────────────────────────────────────
    # Aggregate Metrics Calculation
    # ─────────────────────────────────────────────────────────────────────────────
    n = len(results_summary)
    avg_scores = {}
    for _, name, _, _ in all_metrics:
        total = sum(r["scores"].get(name, {}).get("score", 0.0) for r in results_summary)
        avg_scores[name] = total / max(n, 1)

    print("\n" + "=" * 100)
    print("                    🏆 DEEPEVAL 100% COMPLETE RAG SCORECARD (4 PILLARS)                 ")
    print("=" * 100)
    print("--- [Pillar 1: Retrieval Process Metrics (Khâu Tìm Kiếm & Lấy Dữ Liệu)] ---")
    print(f"  • Contextual Recall       (Bao quát đủ ý)       : {avg_scores['Contextual Recall']:.2f} / 1.00  (Target: >= 0.70) -> {'✅ PASS' if avg_scores['Contextual Recall'] >= 0.7 else '⚠️ WARN'}")
    print(f"  • Contextual Precision    (Xếp Top 1 chuẩn)     : {avg_scores['Contextual Precision']:.2f} / 1.00  (Target: >= 0.70) -> {'✅ PASS' if avg_scores['Contextual Precision'] >= 0.7 else '⚠️ WARN'}")
    print(f"  • Contextual Relevancy    (Độ sạch / Không rác) : {avg_scores['Contextual Relevancy']:.2f} / 1.00  (Target: >= 0.70) -> {'✅ PASS' if avg_scores['Contextual Relevancy'] >= 0.7 else '⚠️ WARN'}")
    print("\n--- [Pillar 2: Generation & Truthfulness Metrics (Khâu LLM Sinh Lời & Chống Ảo Giác)] ---")
    print(f"  • Faithfulness            (Trung thực với text) : {avg_scores['Faithfulness']:.2f} / 1.00  (Target: >= 0.70) -> {'✅ PASS' if avg_scores['Faithfulness'] >= 0.7 else '⚠️ WARN'}")
    print(f"  • Answer Relevancy        (Đúng trọng tâm hỏi)  : {avg_scores['Answer Relevancy']:.2f} / 1.00  (Target: >= 0.70) -> {'✅ PASS' if avg_scores['Answer Relevancy'] >= 0.7 else '⚠️ WARN'}")
    print(f"  • Hallucination Rate      (Tỷ lệ nói dối/bịa)   : {avg_scores['Hallucination Rate']:.2f} / 1.00  (Target: <= 0.30) -> {'✅ PASS' if avg_scores['Hallucination Rate'] <= 0.3 else '⚠️ WARN'}")
    print("\n--- [Pillar 3: Safety & Brand Tone Metrics (An Toàn & Đạo Đức Doanh Nghiệp)] ---")
    print(f"  • Toxicity Rate           (Độ độc hại/khiếm nhã): {avg_scores['Toxicity Rate']:.2f} / 1.00  (Target: <= 0.10) -> {'✅ PASS' if avg_scores['Toxicity Rate'] <= 0.1 else '⚠️ WARN'}")
    print(f"  • Bias Rate               (Độ thiên kiến)       : {avg_scores['Bias Rate']:.2f} / 1.00  (Target: <= 0.10) -> {'✅ PASS' if avg_scores['Bias Rate'] <= 0.1 else '⚠️ WARN'}")
    print("\n--- [Pillar 4: Domain G-Eval Custom Metrics (Nghiệp Vụ Kế Toán Phần Mềm SAO)] ---")
    print(f"  • ERP Accounting Accuracy (Chuẩn nghiệp vụ SAO) : {avg_scores['ERP Accounting Accuracy']:.2f} / 1.00  (Target: >= 0.70) -> {'✅ PASS' if avg_scores['ERP Accounting Accuracy'] >= 0.7 else '⚠️ WARN'}")
    print("=" * 100)

    # ─────────────────────────────────────────────────────────────────────────────
    # Export Markdown Report
    # ─────────────────────────────────────────────────────────────────────────────
    export_dir = Path(__file__).resolve().parent
    export_path = export_dir / "DEEPEVAL_REPORT.md"
    with open(export_path, "w", encoding="utf-8") as f:
        f.write("# DeepEval Enterprise RAG Evaluation Report (Diverse Benchmark)\n\n")
        f.write(f"- **Evaluated Date**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"- **Judge Model**: `deepeval` via 9Router (`http://localhost:20128/v1`)\n")
        f.write(f"- **Pipeline**: Real Production `MarkdownCleaner` + `normalize_query` + `PublicInferenceService._build_messages`\n")
        f.write(f"- **Total Test Cases**: {len(test_cases)}\n\n")
        f.write("## 🏆 Complete 4-Pillar RAG Scorecard\n\n")
        f.write("| Pillar | Metric Name | Average Score | Target SLA | Status |\n")
        f.write("|---|---|:---:|:---:|:---:|\n")
        for group, name, _, is_inverted in all_metrics:
            score = avg_scores[name]
            sla = "<= 0.30" if is_inverted else ">= 0.70"
            passed = score <= 0.3 if is_inverted else score >= 0.7
            status = "✅ PASS" if passed else "⚠️ WARN"
            f.write(f"| **{group}** | {name} | **{score:.2f}** | ${sla}$ | {status} |\n")

        f.write("\n## 📋 Detailed Case-by-Case Breakdown\n\n")
        f.write("| ID | Category | Question | Ctx Recall | Ctx Prec | Faithfulness | Relevancy | Hallucination | ERP Acc |\n")
        f.write("|---|---|---|:---:|:---:|:---:|:---:|:---:|:---:|\n")
        for res in results_summary:
            s = res["scores"]
            c_rec = s.get("Contextual Recall", {}).get("score", 0.0)
            c_prc = s.get("Contextual Precision", {}).get("score", 0.0)
            fth = s.get("Faithfulness", {}).get("score", 0.0)
            rel = s.get("Answer Relevancy", {}).get("score", 0.0)
            hal = s.get("Hallucination Rate", {}).get("score", 0.0)
            erp = s.get("ERP Accounting Accuracy", {}).get("score", 0.0)
            f.write(f"| {res['id']} | {res['category']} | {res['input'][:35]}... | {c_rec:.2f} | {c_prc:.2f} | {fth:.2f} | {rel:.2f} | {hal:.2f} | {erp:.2f} |\n")

    # Export JSON
    json_path = export_dir / "deepeval_results.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "evaluated_at": time.strftime('%Y-%m-%d %H:%M:%S'),
            "model_judge": "deepeval (9Router)",
            "pipeline": "Real Production MarkdownCleaner + normalize_query + PublicInferenceService",
            "total_cases": len(test_cases),
            "averages": avg_scores,
            "cases": results_summary,
        }, f, ensure_ascii=False, indent=2)

    print(f"\n📁 Markdown report exported to: {export_path}")
    print(f"📁 Raw JSON exported to: {json_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run DeepEval RAG full evaluation")
    parser.add_argument("--limit", type=int, default=6, help="Number of test cases (default: 6)")
    parser.add_argument("--diverse", action="store_true", default=True, help="Sample across diverse categories")
    parser.add_argument("--ids", type=str, default="", help="Comma-separated IDs (e.g. BM-01,BM-05,BM-10,BM-14,BM-19,BM-35)")
    parser.add_argument("--top_k", type=int, default=5, help="Retrieval top_k (default: 5)")
    args = parser.parse_args()

    selected = [x.strip() for x in args.ids.split(",")] if args.ids else None
    run_deepeval_evaluation(
        limit=args.limit,
        sample_diverse=args.diverse and not selected,
        selected_ids=selected,
        top_k=args.top_k,
    )
