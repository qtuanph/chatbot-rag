# syntax=docker/dockerfile:1
ARG HF_TOKEN
FROM python:3.12-slim AS builder

LABEL org.opencontainers.image.authors="qtuanph"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# ── System deps: cached via BuildKit mount, only re-runs if this RUN changes ──
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ make \
    && rm -rf /var/lib/apt/lists/*

# ── Requirements: pip cache mount persists across rebuilds ──
COPY requirements.txt .

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip setuptools wheel && \
    pip install -r requirements.txt && \
    # Purge build toolchain from builder image — reduces 300MB, faster COPY to runtime
    apt-get purge -y gcc g++ make && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# ── Runtime Stage ─────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

LABEL org.opencontainers.image.authors="qtuanph"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/home/qtuanph/.cache/huggingface \
    PYTHONPATH=/app \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# ── System deps: cached mount, only re-runs if this RUN changes ──
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 libglib2.0-0 libgl1 libsm6 libxext6 libxrender1 poppler-utils curl \
    && rm -rf /var/lib/apt/lists/*

# ── Non-root user + dirs ──
RUN useradd -m -u 1000 -s /bin/bash qtuanph && \
    mkdir -p /home/qtuanph/.cache/huggingface /home/qtuanph/.rapidocr /app && \
    chown -R qtuanph:qtuanph /home/qtuanph /app

# ── Copy python packages from builder ──
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Fix permissions for RapidOCR
RUN chown -R qtuanph:qtuanph /usr/local/lib/python3.12/site-packages/rapidocr/models/ 2>/dev/null; true

USER qtuanph

# ── Pre-download Models: cached mount, only re-runs if this RUN changes ──
# HF_TOKEN: from build ARG (set via Windows env var or docker compose build --build-arg)
RUN --mount=type=cache,id=hf-models,target=/tmp/hf-cache,uid=1000,gid=1000 \
    --mount=type=cache,id=rapidocr-models,target=/tmp/rapidocr-cache,uid=1000,gid=1000 \
    HF_HOME=/tmp/hf-cache \
    python -c "\
import os; \
hf_token = os.environ.get('HF_TOKEN', ''); \
print(f'Using HF_TOKEN: {hf_token[:8]}...' if hf_token else 'No HF_TOKEN'); \
from sentence_transformers import SentenceTransformer; \
SentenceTransformer('AITeamVN/Vietnamese_Embedding_v2', token=hf_token if hf_token else None); \
print('Embedding model cached'); \
from transformers import AutoModelForSequenceClassification, AutoTokenizer; \
AutoTokenizer.from_pretrained('AITeamVN/Vietnamese_Reranker', token=hf_token if hf_token else None); \
AutoModelForSequenceClassification.from_pretrained('AITeamVN/Vietnamese_Reranker', token=hf_token if hf_token else None); \
print('Reranker model cached'); \
from underthesea import word_tokenize; \
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
print('Docling and OCR models pre-downloaded'); \
" && \
cp -rn /tmp/hf-cache/* /home/qtuanph/.cache/huggingface/ 2>/dev/null; true && \
cp -rn /tmp/rapidocr-cache/* /home/qtuanph/.rapidocr/ 2>/dev/null; true

# ── Application code: LAST layer, only invalidates on code change ──
COPY --chown=qtuanph:qtuanph . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]