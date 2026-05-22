# syntax=docker/dockerfile:1
FROM python:3.12-slim AS builder

LABEL org.opencontainers.image.authors="qtuanph"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DEFAULT_TIMEOUT=300 \
    PIP_RETRIES=5 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# ── System deps: cached via BuildKit mount, only re-runs if this RUN changes ──
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ make \
    && rm -rf /var/lib/apt/lists/*

# ── Requirements: persistent pip cache for fast rebuilds ──
COPY requirements.txt .

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade setuptools wheel && \
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
    apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 libglib2.0-0 libgl1 libsm6 libxext6 libxrender1 poppler-utils curl \
    libreoffice-writer-nogui \
    && rm -rf /var/lib/apt/lists/*

# ── Non-root user + dirs ──
RUN useradd -m -u 1000 -s /bin/bash qtuanph && \
    mkdir -p /home/qtuanph/.cache/huggingface /app/data /app && \
    chown -R qtuanph:qtuanph /home/qtuanph /app

# ── Copy python packages from builder ──
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Fix permissions for RapidOCR
RUN chown -R qtuanph:qtuanph /usr/local/lib/python3.12/site-packages/rapidocr/models/ 2>/dev/null; true

USER qtuanph

# ── Application code: LAST layer, only invalidates on code change ──
COPY --chown=qtuanph:qtuanph . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]