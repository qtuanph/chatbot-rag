# syntax=docker/dockerfile:1
FROM python:3.12-slim

LABEL org.opencontainers.image.authors="qtuanph"

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=off
# HuggingFace cache dir (persistent across builds via BuildKit cache mount)
ENV HF_HOME=/root/.cache/huggingface

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
	curl \
	gcc \
	build-essential \
	libgl1 \
	libglib2.0-0 \
	libgomp1 \
	libsm6 \
	libxext6 \
	libxrender1 \
	poppler-utils \
	&& rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./

# BuildKit cache mount: pip packages cached between builds — no re-download on code-only changes.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip setuptools wheel && pip install -r requirements.txt

# Pre-download EasyOCR models (vi + en) at build time.
# BuildKit cache keeps models between builds — not baked into image layer.
RUN --mount=type=cache,target=/root/.EasyOCR \
    python -c "import easyocr; easyocr.Reader(['vi', 'en'], gpu=False, verbose=False)" \
    || echo "EasyOCR pre-download skipped"

# Pre-download BAAI/bge-m3 embedding model at build time.
# ~570MB — BuildKit cache avoids re-download on subsequent builds.
# gpu=False here is intentional: build environment has no GPU, runtime will use GPU.
RUN --mount=type=cache,target=/root/.cache/huggingface \
    python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-m3'); print('BAAI/bge-m3 ready')" \
    || echo "BAAI/bge-m3 pre-download skipped (no network)"

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
