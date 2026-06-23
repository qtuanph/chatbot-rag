# 8 — Tenant Integration Guide

Tài liệu này dành cho trường hợp muốn gắn chatbot vào phần mềm của từng công ty khách.

## Mục tiêu tích hợp

Mỗi tenant dùng:

- dữ liệu tài liệu riêng
- instruction riêng
- quota/rate limit riêng
- API key riêng

Backend của project này đóng vai trò **cầu nối**:

- tenant gọi vào chatbot này
- chatbot này tự retrieval đúng tài liệu của tenant
- rồi gọi LLM/provider phía sau

## Hiện tại việc kết nối đã đơn giản chưa?

### Câu trả lời ngắn

**Khá đơn giản rồi**, nhưng chưa phải mức “zero-config enterprise polished”.

### Đã đơn giản ở các điểm này

- auth bằng `Bearer API key`
- endpoint public rõ ràng
- payload chat gần kiểu OpenAI
- tenant không cần biết vector DB hay retrieval bên trong

### Chưa đẹp hoàn toàn ở các điểm này

- `GET /public/v1/models` còn đơn giản
- response có `citations` riêng ngoài shape OpenAI gốc
- chưa có bộ SDK / doc tích hợp mẫu đầy đủ trong codebase
- chưa có request id / tenant usage headers thật rõ ở public contract

## Thông tin tenant cần để tích hợp

Mỗi tenant tối thiểu cần:

- `base_url`
- `api_key`
- `model`
- `messages`

### Ví dụ

```text
base_url = https://api.qtuanph.dev
api_key  = <tenant_api_key>
model    = chatbot-rag
```

## Endpoint chính

| Method | Path | Mục đích |
|---|---|---|
| GET | `/v1/health` | kiểm tra sống |
| GET | `/v1/models` | danh sách model logic |
| POST | `/v1/chat/completions` | gửi chat |

## Auth

Header:

```http
Authorization: Bearer <tenant_api_key>
Content-Type: application/json
```

## Request mẫu

```json
{
  "model": "chatbot-rag",
  "messages": [
    { "role": "user", "content": "Cách tạo phiếu nhập kho?" }
  ],
  "thinking_mode": false,
  "stream": false,
  "temperature": 0.2,
  "max_tokens": 1024
}
```

### Các trường cần cho tích hợp

| Field | Required | Ý nghĩa |
|---|---|---|
| `model` | yes | giữ cố định là `chatbot-rag` |
| `messages` | yes | message hiện tại hoặc vài message gần nhất |
| `stream` | no | bật SSE để nhận text dần |
| `thinking_mode` | no | bật marker thinking start/end khi stream |

`temperature` và `max_tokens` hiện backend có nhận, nhưng với hướng tích hợp managed hiện tại, tenant software không bắt buộc phải gửi.

## Python SDK example

Tenant software can call the platform with the OpenAI Python SDK using only:

- `base_url`
- `api_key`
- `model`

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://api.qtuanph.dev/v1",
    api_key="YOUR_TENANT_API_KEY",
)

completion = client.chat.completions.create(
    model="chatbot-rag",
    messages=[
        {"role": "user", "content": "Muốn backup số liệu thì vào mục nào?"}
    ],
    stream=True,
    extra_body={"thinking_mode": True},
)

for chunk in completion:
    data = chunk.model_dump()

    if data.get("thinking") is True:
        print("[thinking:start]")
        continue
    if data.get("thinking") is False:
        print("[thinking:end]")
        continue

    if not chunk.choices:
        continue
    delta = chunk.choices[0].delta
    if delta.content:
        print(delta.content, end="")
```

## Response mẫu

```json
{
  "id": "chatcmpl-...",
  "object": "chat.completion",
  "created": 0,
  "model": "chatbot-rag",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "..."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 123,
    "completion_tokens": 456,
    "total_tokens": 579
  },
  "citations": []
}
```

## Stream mẫu

Nếu `stream=true`, backend trả SSE:

```text
data: {"thinking": true, "done": false}

data: {...chunk...}

data: {...chunk...}

data: {"thinking": false, "done": false}

data: [DONE]
```

`thinking_mode` hiện tại chỉ phát marker trạng thái để UI biết lúc nào chatbot đang ở pha suy luận. Nó không trả full chain-of-thought hay reasoning text riêng.

## Luồng nghiệp vụ đúng

1. `platform_admin` tạo tenant
2. `platform_admin` upload tài liệu cho tenant
3. `platform_admin` tạo API key cho tenant
4. phần mềm bên khách lưu:
   - `base_url`
   - `api_key`
   - `model`
5. phần mềm bên khách gọi `chat/completions`

## Những gì tenant không cần biết

Tenant tích hợp không cần biết:

- Qdrant
- Redis
- embedding provider
- reranker provider
- worker ingest

Đó là phần backend của nền tảng tự lo.

## Gợi ý tích hợp vào phần mềm khách

### Mức tối thiểu

- nút mở chatbot
- input message
- gọi `POST /chat/completions`
- hiển thị output

### Mức tốt hơn

- giữ vài message gần nhất ở memory client
- gửi lại `messages` gần nhất mỗi turn
- dùng streaming để cảm giác phản hồi nhanh hơn

## Realtime nên dùng gì?

### Với chat

Nên giữ **SSE** nếu luồng chỉ là server -> client.

Lý do:

- đơn giản hơn WebSocket
- hợp streaming text
- dễ vận hành hơn qua reverse proxy

### Với progress ingestion

Nếu sau này muốn realtime thật cho tiến độ upload/index:

- ưu tiên **SSE** cho progress một chiều
- chỉ cân nhắc WebSocket nếu cần điều khiển hai chiều phức tạp

## Khuyến nghị cho mục tiêu 200 CCU

### Chat streaming

- SSE là đủ tốt cho 200 CCU nếu chỉ stream một chiều
- không nên dùng polling cho progress/chat ở quy mô đó

### Ingestion progress

Polling 4 giây như hiện tại sẽ không đẹp khi scale lên.

Nên roadmap:

1. giữ polling cho dev
2. nâng ingestion progress sang SSE
3. chỉ dùng WebSocket nếu tương lai có collaborative / hai chiều thật sự

## Kết luận

Hướng sản phẩm hiện tại đã đúng để làm “cầu nối chatbot cho phần mềm tenant”:

- tenant có API key riêng
- dữ liệu tenant tách riêng
- API gần chuẩn OpenAI
- phần mềm khách chỉ cần tích hợp như một chat API

Phần còn nên làm tiếp để đẹp hơn ở production:

- integration doc mẫu theo ngôn ngữ
- request/response examples nhiều hơn
- request id / quota headers
- SSE progress cho ingestion thay vì polling
