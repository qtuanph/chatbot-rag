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

# --- Runtime Stage ---
FROM python:3.12-slim AS runtime

LABEL org.opencontainers.image.authors="qtuanph"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/home/qtuanph/.cache/huggingface \
    PYTHONPATH=/app

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    libglib2.0-0 \
    libgl1 \
    libsm6 \
    libxext6 \
    libxrender1 \
    poppler-utils \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 -s /bin/bash qtuanph && \
    mkdir -p /home/qtuanph/.cache/huggingface /home/qtuanph/.rapidocr /app && \
    chown -R qtuanph:qtuanph /home/qtuanph /app

# Copy python packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Fix permissions for RapidOCR
RUN chown -R qtuanph:qtuanph /usr/local/lib/python3.12/site-packages/rapidocr/models/ 2>/dev/null; true

USER qtuanph

# --- Pre-download Models (Heavy Layers - Cached) ---
# These are placed BEFORE the code copy so they are NOT re-run when code changes.

# 1. Embedding model (~2.2 GB)
RUN --mount=type=cache,id=hf-models,target=/tmp/hf-cache,uid=1000,gid=1000 \
    --mount=type=secret,id=hf_token,env=HF_TOKEN \
    HF_HOME=/tmp/hf-cache \
    python -c "from sentence_transformers import SentenceTransformer; \
    SentenceTransformer('AITeamVN/Vietnamese_Embedding_v2'); \
    print('Embedding model cached')" && \
    cp -rn /tmp/hf-cache/* /home/qtuanph/.cache/huggingface/ 2>/dev/null; true

# 2. Reranker model (~500 MB)
RUN --mount=type=cache,id=hf-models,target=/tmp/hf-cache,uid=1000,gid=1000 \
    --mount=type=secret,id=hf_token,env=HF_TOKEN \
    HF_HOME=/tmp/hf-cache \
    python -c "from transformers import AutoModelForSequenceClassification, AutoTokenizer; \
    AutoTokenizer.from_pretrained('AITeamVN/Vietnamese_Reranker'); \
    AutoModelForSequenceClassification.from_pretrained('AITeamVN/Vietnamese_Reranker'); \
    print('Reranker model cached')" && \
    cp -rn /tmp/hf-cache/* /home/qtuanph/.cache/huggingface/ 2>/dev/null; true

# 3. Word segmentation & OCR models
RUN --mount=type=cache,id=hf-models,target=/tmp/hf-cache,uid=1000,gid=1000 \
    --mount=type=cache,id=rapidocr-models,target=/tmp/rapidocr-cache,uid=1000,gid=1000 \
    python -c "from underthesea import word_tokenize; \
    word_tokenize('warmup', format='text'); \
    from rapidocr_onnxruntime import RapidOCR; \
    engine = RapidOCR(); \
    from docling.document_converter import DocumentConverter, PdfFormatOption; \
    from docling.datamodel.pipeline_options import PdfPipelineOptions; \
    from docling.datamodel.base_models import InputFormat; \
    pipeline_options = PdfPipelineOptions(); \
    pipeline_options.do_ocr = True; \
    pipeline_options.do_table_structure = True; \
    converter = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)}); \
    print('Docling and OCR models pre-downloaded')"

# --- Final Application Copy (Lightweight Layer) ---
# Copy application source code. Any code change only invalidates this layer.
COPY --chown=qtuanph:qtuanph . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
