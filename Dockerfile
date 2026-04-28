# syntax=docker/dockerfile:1
FROM python:3.12-slim AS builder

LABEL org.opencontainers.image.authors="qtuanph"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip setuptools wheel && \
    pip install -r requirements.txt

COPY . .

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/home/qtuanph/.cache/huggingface

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    libglib2.0-0 \
    libgl1 \
    libsm6 \
    libxext6 \
    libxrender1 \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 -s /bin/bash qtuanph

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --chown=qtuanph:qtuanph . .

RUN mkdir -p /home/qtuanph/.cache/huggingface /home/qtuanph/.rapidocr && \
    chown -R qtuanph:qtuanph /home/qtuanph /app && \
    chmod -R 777 /usr/local/lib/python3.12/site-packages/rapidocr/models/ 2>/dev/null; true

USER qtuanph

# Pre-download embedding model (Vietnamese_Embedding_v2 ~2.2 GB)
# Secret mount with env= keeps HF_TOKEN out of image layers (no SecretsUsedInArgOrEnv warning).
# Cache mount: models persist across rebuilds, then copy into image layer.
RUN --mount=type=cache,id=hf-models,target=/tmp/hf-cache,uid=1000,gid=1000 \
    --mount=type=secret,id=hf_token,env=HF_TOKEN \
    HF_HOME=/tmp/hf-cache \
    python -c "from sentence_transformers import SentenceTransformer; \
    SentenceTransformer('AITeamVN/Vietnamese_Embedding_v2'); \
    print('Embedding model cached')" && \
    cp -rn /tmp/hf-cache /home/qtuanph/.cache/huggingface 2>/dev/null; true

# Pre-download reranker model (AITeamVN/Vietnamese_Reranker ~500 MB)
RUN --mount=type=cache,id=hf-models,target=/tmp/hf-cache,uid=1000,gid=1000 \
    --mount=type=secret,id=hf_token,env=HF_TOKEN \
    HF_HOME=/tmp/hf-cache \
    python -c "from transformers import AutoModelForSequenceClassification, AutoTokenizer; \
    AutoTokenizer.from_pretrained('AITeamVN/Vietnamese_Reranker'); \
    AutoModelForSequenceClassification.from_pretrained('AITeamVN/Vietnamese_Reranker'); \
    print('Reranker model cached')" && \
    cp -rn /tmp/hf-cache /home/qtuanph/.cache/huggingface 2>/dev/null; true

# Pre-download underthesea word segmentation data
RUN --mount=type=cache,id=hf-models,target=/tmp/hf-cache,uid=1000,gid=1000 \
    python -c "from underthesea import word_tokenize; \
    word_tokenize('Test tải model underthesea', format='text'); \
    print('Underthesea models pre-downloaded')"

# Pre-download PaddleOCR (RapidOCR ONNX) models for Vietnamese OCR
# On first run, RapidOCR downloads detection + classification + recognition models (~100 MB)
RUN --mount=type=cache,id=rapidocr-models,target=/tmp/rapidocr-cache,uid=1000,gid=1000 \
    python -c "from rapidocr_onnxruntime import RapidOCR; \
    engine = RapidOCR(); \
    print('PaddleOCR (RapidOCR ONNX) models pre-downloaded')"

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
