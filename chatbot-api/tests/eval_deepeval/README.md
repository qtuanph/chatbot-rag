# DeepEval RAG Evaluation Suite

Hệ thống đánh giá chất lượng RAG tự động dựa trên framework **DeepEval** (by Confident AI), kết nối độc lập với LLM Judge 9Router tại `http://localhost:20128/v1` (model: `deepeval`).

---

## 🌟 1. Các chỉ số được đo lường (RAG Triad)

| Metric | Mô tả | Ngưỡng đạt chuẩn (Threshold) |
|---|---|:---:|
| **Faithfulness** | Mức độ trung thực của câu trả lời so với các đoạn dữ liệu trích xuất (chống ảo giác / hallucination). | $\ge 0.70$ |
| **Answer Relevancy** | Mức độ bám sát câu hỏi người dùng của câu trả lời. | $\ge 0.70$ |
| **Contextual Recall** | Tỷ lệ ngữ cảnh trích xuất bao quát được thông tin cần thiết trong câu trả lời mẫu. | $\ge 0.70$ |
| **Contextual Precision** | Mức độ ưu tiên xếp hạng đoạn dữ liệu quan trọng nhất lên đầu (Rank #1). | $\ge 0.70$ |

---

## 🚀 2. Cách chạy kiểm thử

Chỉ cần chạy lệnh duy nhất (đã tự động cấu hình sẵn endpoint model `deepeval` ở `http://localhost:20128/v1`):

```bash
cd chatbot-api
.venv\Scripts\python.exe tests/eval_deepeval/run_deepeval.py --limit 5
```
*(Tham số `--limit 5` để chạy mẫu 5 câu, hoặc `--limit 0` để chạy toàn bộ 35 câu).*

---

## 📊 3. Báo cáo đầu ra
Sau khi chạy xong, kết quả được xuất tự động tại:
- `tests/eval_deepeval/DEEPEVAL_REPORT.md` (Báo cáo Markdown chi tiết).
- `tests/eval_deepeval/deepeval_results.json` (Dữ liệu JSON định lượng).
