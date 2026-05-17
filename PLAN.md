# PLAN: CLIProxyAPI + LlamaIndex Architecture Overhaul

## Tổng quan

Thay thế Google Gemini (AIProvider) bằng **CLIProxyAPI** — proxy AI model
với OpenAI-compatible endpoint. Tích hợp **LlamaIndex core** cho ingestion
pipeline và LLM abstraction. Giữ nguyên custom OCR (Docling), embedding
(AITeamVN), reranker (AITeamVN), và 5-stage retrieval.

## Kiến trúc mới

```
Browser (Next.js webapp)
  └── /api/bep/* → Next.js Route Handler → FastAPI
        │
  FastAPI Backend
    ├── ChatService → LlamaIndex OpenAI LLM → CLIProxyAPI (ai-proxy:8317/v1)
    ├── IngestionService → LlamaIndex IngestionPipeline + SentenceSplitter
    ├── 5-stage retrieval (GIỮ: hybrid → dedup → rerank → expand → context)
    └── Admin module → quản lý providers qua CLIProxyAPI Management API
        │
  CLIProxyAPI (ai-proxy container)
    ├── /v1/chat/completions (OpenAI-compatible)
    ├── Format translation (OpenAI ↔ Gemini ↔ Claude)
    └── Provider routing (NVIDIA NIM, Groq, OpenAI, Gemini...)
```

## Container thay đổi

| Service | Trạng thái | Details |
|---------|-----------|---------|
| **ai-proxy** | **MỚI** | CLIProxyAPI (eceasy/cli-proxy-api:latest), port 8317 |
| api | SỬA | Thêm dependency ai-proxy + env vars |
| workers | KHÔNG ĐỔI | Celery workers, vẫn dùng ai-engine cho embedding |
| ai-engine | KHÔNG ĐỔI | Serve AITeamVN embedding + reranker |
| webapp | SỬA | Thêm admin/providers pages |

## File thay đổi

### MỚI (10 files)

| File | Purpose |
|------|---------|
| `ops/entrypoint-ai-proxy.sh` | Entrypoint cho ai-proxy container |
| `app/adapters/ai/cliproxy_bridge.py` | Wrap OpenAI LLM → CLIProxyAPI |
| `app/adapters/embeddings/llama_bridge.py` | Wrap AITeamVN → BaseEmbedding |
| `app/adapters/reranker/llama_bridge.py` | Wrap AITeamVN → BaseNodePostprocessor |
| `app/modules/documents/ingestion/llama_pipeline.py` | IngestionPipeline wrapper |
| `app/modules/admin/__init__.py` | Admin module init |
| `app/modules/admin/router.py` | Admin REST API |
| `app/modules/admin/schemas.py` | Admin Pydantic schemas |
| `app/modules/admin/services/__init__.py` | Admin services init |
| `app/modules/admin/services/model_provider_service.py` | Provider management via CLIProxyAPI Mgmt API |

### SỬA (8 files)

| File | Changes |
|------|---------|
| `docker-compose.yml` | Thêm ai-proxy service + volumes |
| `app/core/config.py` | Thêm CLIPROXY settings, bỏ google settings |
| `.env` | Thêm CLIPROXY vars, bỏ GOOGLE vars |
| `app/main.py` | Register admin router |
| `app/modules/documents/ingestion/ingestion_service.py` | Dùng LlamaIndex IngestionPipeline |
| `app/modules/chat/services/service.py` | Dùng OpenAI LLM (→ CLIProxyAPI) |
| `app/api/routes/websocket.py` | Fix imports |
| `requirements.txt` | Thêm llama-index-* packages |

### BỎ (5 files)

| File | Reason |
|------|--------|
| `app/adapters/ai/base.py` | AIProvider ABC → LlamaIndex BaseLLM |
| `app/adapters/ai/google.py` | GoogleAIProvider → CLIProxyAPI |
| `app/adapters/ai/__init__.py` | build_ai_provider() → CLIProxyBridge |
| `app/modules/documents/utils/text_splitter.py` | SentenceSplitter |
| `app/modules/documents/utils/contextualizer.py` | Không cần |

## Execution Plan (8 Phases)

### Phase 0: ✅ CLIProxyAPI Test (done)
- Pull image: `eceasy/cli-proxy-api:latest`
- Test `/v1/chat/completions` + Management API

### Phase 1: Docker + Config
- Add ai-proxy service
- Tạo entrypoint-ai-proxy.sh
- Update config.py + .env

### Phase 2: Dependencies
- Thêm llama-index-* vào requirements.txt

### Phase 3: Adapter Wrappers
- cliproxy_bridge.py (OpenAI LLM → CLIProxyAPI)
- llama_bridge.py (embedding → BaseEmbedding)
- llama_bridge.py (reranker → BaseNodePostprocessor)

### Phase 4: Ingestion Pipeline
- llama_pipeline.py (IngestionPipeline wrapper)
- SỬA ingestion_service.py

### Phase 5: Chat Engine
- SỬA chat service.py (dùng OpenAI LLM)
- SỬA websocket.py (fix imports)

### Phase 6: Admin Module
- router.py + schemas.py + model_provider_service.py

### Phase 7: Cleanup
- Xoá base.py, google.py, __init__.py (ai)
- Xoá text_splitter.py, contextualizer.py
- Update tất cả imports

### Phase 8: Docs + Lint
- Update docs/1_ARCHITECTURE.md, docs/3_API_CONTRACTS.md
- Chạy black + flake8

## Key Design Decisions

1. **CLIProxyAPI > 9Router**: CLIProxyAPI là Go binary nhẹ (~15MB),
   9Router là Next.js (Node). User chọn CLIProxyAPI.

2. **LlamaIndex cho ingestion, custom cho retrieval**: SentenceSplitter
   thay text_splitter.py. 5-stage retrieval giữ nguyên.

3. **OpenAI LLM của LlamaIndex**: Trỏ api_base → CLIProxyAPI.
   Dùng `llama-index-llms-openai`.

4. **AITeamVN models**: Wrap thành BaseEmbedding và BaseNodePostprocessor.

5. **Provider management**: FastAPI gọi CLIProxyAPI Management API
   (PUT /v0/management/config.yaml) để bật/tắt providers.

6. **Mỗi lần 1 provider**: Admin UI toggle → FastAPI disable all, enable 1.
