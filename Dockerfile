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

RUN mkdir -p /home/qtuanph/.cache/huggingface /home/qtuanph/.EasyOCR && \
    chown -R qtuanph:qtuanph /home/qtuanph /app && \
    chmod -R 777 /usr/local/lib/python3.12/site-packages/rapidocr/models/

# Pre-download embedding model into image (Vietnamese_Embedding_v2 ~2.2 GB)
# Must run as qtuanph so HF cache is in the correct home directory
USER qtuanph
RUN for i in 1 2 3; do \
        python -c "from sentence_transformers import SentenceTransformer; \
        SentenceTransformer('AITeamVN/Vietnamese_Embedding_v2'); \
        print('Embedding model pre-downloaded successfully')" && break || \
        (echo "Retry $i/3 — embedding download failed, waiting 10s..." && sleep 10); \
    done

# Pre-download reranker model (AITeamVN/Vietnamese_Reranker ~500 MB)
RUN for i in 1 2 3; do \
        python -c "from sentence_transformers import CrossEncoder; \
        CrossEncoder('AITeamVN/Vietnamese_Reranker', device='cpu', max_length=2304); \
        print('Reranker model pre-downloaded successfully')" && break || \
        (echo "Retry $i/3 — reranker download failed, waiting 10s..." && sleep 10); \
    done

# Pre-download underthesea word segmentation data
RUN for i in 1 2 3; do \
        python -c "from underthesea import word_tokenize; \
        word_tokenize('Test tải model underthesea', format='text'); \
        print('Underthesea models pre-downloaded successfully')" && break || \
        (echo "Retry $i/3 — underthesea download failed, waiting 10s..." && sleep 10); \
    done

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
