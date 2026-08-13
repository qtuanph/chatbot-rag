# DeepEval Enterprise RAG Evaluation Report (Diverse Benchmark)

- **Evaluated Date**: 2026-08-13 17:13:30
- **Judge Model**: `deepeval` via 9Router (`http://localhost:20128/v1`)
- **Pipeline**: Real Production `MarkdownCleaner` + `normalize_query` + `PublicInferenceService._build_messages`
- **Total Test Cases**: 6

## 🏆 Complete 4-Pillar RAG Scorecard

| Pillar | Metric Name | Average Score | Target SLA | Status |
|---|---|:---:|:---:|:---:|
| **1. RETRIEVAL PROCESS** | Contextual Recall | **0.78** | $>= 0.70$ | ✅ PASS |
| **1. RETRIEVAL PROCESS** | Contextual Precision | **0.14** | $>= 0.70$ | ⚠️ WARN |
| **1. RETRIEVAL PROCESS** | Contextual Relevancy | **0.15** | $>= 0.70$ | ⚠️ WARN |
| **2. GENERATION & TRUTH** | Faithfulness | **0.83** | $>= 0.70$ | ✅ PASS |
| **2. GENERATION & TRUTH** | Answer Relevancy | **0.80** | $>= 0.70$ | ✅ PASS |
| **2. GENERATION & TRUTH** | Hallucination Rate | **0.23** | $<= 0.30$ | ✅ PASS |
| **3. SAFETY & TONE** | Toxicity Rate | **0.00** | $<= 0.30$ | ✅ PASS |
| **3. SAFETY & TONE** | Bias Rate | **0.00** | $<= 0.30$ | ✅ PASS |
| **4. DOMAIN G-EVAL** | ERP Accounting Accuracy | **0.43** | $>= 0.70$ | ⚠️ WARN |

## 📋 Detailed Case-by-Case Breakdown

| ID | Category | Question | Ctx Recall | Ctx Prec | Faithfulness | Relevancy | Hallucination | ERP Acc |
|---|---|---|:---:|:---:|:---:|:---:|:---:|:---:|
| BM-01 | Single-hop Factoid | Ai là người tạo và người duyệt tài ... | 1.00 | 0.33 | 0.00 | 1.00 | 0.80 | 0.00 |
| BM-05 | Accounting Code & Condition | Mục 1.4.2 quy định về cập nhật chứn... | 1.00 | 0.00 | 1.00 | 1.00 | 0.60 | 1.00 |
| BM-10 | System Admin & Config | Trường 'Mã ctừ mẹ' trong khai báo m... | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 1.00 |
| BM-14 | Semantic / Paraphrase | Tôi muốn phân quyền cho nhân viên m... | 1.00 | 0.50 | 1.00 | 0.67 | 0.00 | 0.60 |
| BM-19 | UI Navigation & Shortcuts | Các phím chức năng F2, F3, F4, F8 v... | 1.00 | 0.00 | 1.00 | 0.88 | 0.00 | 0.00 |
| BM-35 | No-answer / Hallucination Trap | Dự báo thời tiết và nhiệt độ tại Hà... | 0.67 | 0.00 | 1.00 | 0.25 | 0.00 | 0.00 |
