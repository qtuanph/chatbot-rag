# RAG Improvement Roadmap

> **Mục tiêu**: Tăng độ chính xác câu trả lời mà KHÔNG tăng đáng kể latency.
> Ưu tiên sắp xếp theo: **ROI cao + latency thấp trước**.

---

## Baseline hiện tại (đã có)

```
Query → Semantic Cache → Hybrid Search (Dense+BM25 RRF)
      → Score Filter (≥0.30) → Cross-encoder Reranker
      → Neighbor Expansion "Soi sáng" → LLM
```

**Điểm mạnh**: Tốt hơn LlamaIndex default ở mọi khía cạnh. Semantic cache giúp repeat queries cực nhanh.

---

## 🚀 Priority 1 — High ROI, Latency thấp

### 1.1 Multi-Query Retrieval (Quan trọng nhất)

**Vấn đề**: Câu hỏi của user thường viết tắt, mơ hồ, hoặc dùng từ khác với tài liệu.

**Ví dụ**: User hỏi "quy định nghỉ phép" nhưng tài liệu viết "chính sách nghỉ có lương" → miss!

**Giải pháp**: Dùng LLM nhẹ (Gemini Flash) tạo 2-3 biến thể query song song:
```
"quy định nghỉ phép"
→ "chính sách nghỉ có lương"
→ "số ngày phép hàng năm"
→ "quy trình xin nghỉ phép"
→ Search 3 queries song song (asyncio.gather) → RRF merge
```

**Cải thiện**: +15~30% recall.
**Latency thêm**: ~50-100ms (chạy song song với embedding của query gốc).
**Vị trí implement**: `app/modules/chat/retrieval/retrieval_service.py` — thêm `_expand_queries()` trước Stage 1.

> ⚠️ Chỉ trigger khi query < 5 từ HOẶC confidence score top-1 < 0.50 để tránh tốn token không cần thiết.

---

### 1.2 Query Rewriting (Làm sạch câu hỏi)

**Vấn đề**: User hay hỏi kiểu chat thông thường: "ừ thế còn cái chính sách kia thì sao?", "như tôi hỏi lúc nãy ấy".

**Giải pháp**: Trước khi search, rewrite câu hỏi thành câu độc lập, rõ ràng:
```
Context: [user hỏi về chính sách A]
Query: "còn cái kia thì sao?"
→ Rewritten: "Chính sách B (liên quan đến A) quy định như thế nào?"
```

**Cải thiện**: Đặc biệt hiệu quả cho multi-turn conversation.
**Latency thêm**: ~100-200ms.
**Vị trí implement**: `app/modules/chat/services/service.py` — trước khi gọi `retrieve_context()`.

---

### 1.3 Tối ưu Chunking (Ingestion side)

**Vấn đề hiện tại**: Nếu chunking cắt đứt câu hoặc cắt sai vị trí, retrieval không bao giờ tìm được đúng.

**Giải pháp**: Đảm bảo chunking:
- Cắt theo heading/section, không cắt giữa câu
- Chunk size: 512-1024 tokens (không quá nhỏ gây mất context, không quá lớn gây noise)
- **Sliding window overlap**: Chunk liền kề overlap 10-20% để không mất thông tin ở biên

**Cải thiện**: Nền tảng — nếu chunk tốt thì mọi kỹ thuật khác đều hiệu quả hơn.
**Latency thêm**: 0 (xử lý lúc ingest, không ảnh hưởng query time).
**Vị trí implement**: `app/modules/documents/` — ingestion pipeline.

---

## ⚡ Priority 2 — Trung bình ROI, Cần đánh giá trước khi bật

### 2.1 Contextual Compression

**Vấn đề**: LLM bị "lost in the middle" — khi context dài 2000+ tokens, LLM hay bỏ qua thông tin ở giữa.

**Giải pháp**: Sau khi retrieve, dùng lightweight model lọc bỏ phần không liên quan trong mỗi chunk:
```
Retrieved chunk (500 tokens):
"...phần không liên quan 200 tokens...
 [THÔNG TIN CẦN] 50 tokens
 ...phần rác 250 tokens..."
→ Compressed: "[THÔNG TIN CẦN] 50 tokens"
```

**Cải thiện**: Giảm hallucination, tăng precision ~20%.
**Latency thêm**: +100-300ms (thêm 1 model call).
**Trade-off**: Tốn thêm token, cần model nhỏ (distilbert hoặc dùng reranker hiện có).
**Vị trí implement**: Sau Stage 2.5 (Reranker) trong retrieval_service.py.

---

### 2.2 HyDE (Hypothetical Document Embeddings)

**Vấn đề**: Embedding của câu hỏi ngắn không khớp tốt với embedding của đoạn văn tài liệu dài.

**Giải pháp**: Dùng LLM tạo "tài liệu giả" → embed tài liệu giả để search:
```
Query: "lương hưu tính sao?"
→ LLM generate: "[Hypothetical doc] Lương hưu được tính dựa trên số năm đóng BHXH..."
→ Embed đoạn văn giả → Search với vector đó
```

**Cải thiện**: +10~20% recall đặc biệt cho câu hỏi ngắn/mơ hồ.
**Latency thêm**: +300-800ms (phải gọi LLM thêm 1 lần).
**Khi nào dùng**: Chỉ bật khi query < 4 từ VÀ top retrieval score < 0.45.
**Vị trí implement**: `retrieval_service.py` — optional branch trước Stage 1.

> ⚠️ HyDE tốn nhiều latency nhất. Chỉ bật sau khi đo được baseline chưa đủ tốt cho câu ngắn.

---

### 2.3 Step-Back Prompting

**Vấn đề**: Câu hỏi cụ thể quá → miss context tổng quát liên quan.

**Ví dụ**:
```
Specific: "Ngày 15/3 năm nay nghỉ lễ không?"
Step-back: "Lịch nghỉ lễ trong năm là gì?" → retrieve thêm context tổng quát
→ Kết hợp cả 2 → answer tốt hơn
```

**Cải thiện**: Tốt cho câu hỏi về quy định, chính sách.
**Latency thêm**: +100-200ms (1 LLM call nhỏ).

---

## 📊 Priority 3 — Đánh giá & Monitoring

### 3.1 RAGAS Evaluation Framework

**Mục tiêu**: Đo được thực sự pipeline tốt đến đâu, cải thiện nào có giá trị.

**Metrics cần đo**:
- **Faithfulness**: AI có bịa thêm thông tin không có trong tài liệu không?
- **Answer Relevancy**: Câu trả lời có đúng trọng tâm câu hỏi không?
- **Context Recall**: Tài liệu liên quan có được retrieve về không?
- **Context Precision**: Tài liệu retrieve về có thực sự liên quan không?

**Cách làm**: Tạo bộ ~50-100 cặp (câu hỏi, câu trả lời đúng) từ tài liệu thực → chạy RAGAS định kỳ.

**Tại sao cần**: Không đo → không biết cải thiện nào thực sự có tác dụng.

---

### 3.2 Per-Query Latency Tracking

**Hiện tại**: Có `latency_ms` trong DB nhưng chưa phân tích sâu.

**Nên thêm**:
- TTFT (Time To First Token) — user cảm nhận độ nhanh
- Retrieval latency vs LLM latency — biết bottleneck ở đâu
- Cache hit rate — bao nhiêu % query được serve từ cache

---

## 🎯 Thực tế cho yêu cầu "nhanh" của công ty

**Latency budget khuyến nghị** (tổng < 3 giây):

| Giai đoạn | Budget |
|---|---|
| Semantic Cache check | < 10ms |
| Query embedding | < 50ms (đã warm) |
| Hybrid Search (Qdrant) | < 200ms |
| Reranker | < 300ms |
| Neighbor Expansion | < 100ms |
| LLM generation (streaming) | < 1500ms TTFT |
| **Tổng** | **< 2.2s đến first token** |

**Chiến lược**: KHÔNG thêm Multi-Query/HyDE vào default path. Chỉ bật khi confidence thấp:
```python
if top_score < 0.50 or query_len < 5:
    # bật multi-query / HyDE
else:
    # dùng pipeline hiện tại (đủ nhanh)
```

---

## 🗂️ File cần chỉnh sửa khi implement

| Tính năng | File chính |
|---|---|
| Multi-Query | `app/modules/chat/retrieval/retrieval_service.py` |
| Query Rewriting | `app/modules/chat/services/service.py` |
| Contextual Compression | `app/modules/chat/retrieval/retrieval_service.py` |
| HyDE | `app/modules/chat/retrieval/retrieval_service.py` |
| Evaluation | `tests/` — thêm `test_rag_quality.py` |
| Chunking | `app/modules/documents/` — ingestion pipeline |

---

## 📌 Thứ tự thực hiện đề xuất

```
1. [NOW]    Đảm bảo chunking tốt (kiểm tra ingestion)
2. [SOON]   Query Rewriting cho multi-turn conversation
3. [SOON]   Multi-Query với adaptive trigger (chỉ khi score thấp)
4. [LATER]  RAGAS evaluation — đo baseline trước khi thêm gì nữa
5. [LATER]  Contextual Compression (sau khi đo thấy cần)
6. [LAST]   HyDE (chỉ cho câu ngắn, sau khi có evaluation)
```

---

*Last updated: 2026-05-17*
*Based on: research từ production RAG systems (Redis, Anyscale, Microsoft, Google) + codebase analysis*
