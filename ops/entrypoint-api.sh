#!/bin/bash
# Entrypoint for API service (FastAPI + uvicorn)
# Model download handled exclusively by ai-engine service into shared hf-cache volume.

set -e

HF_HOME="${HF_HOME:-/home/qtuanph/.cache/huggingface}"
mkdir -p "$HF_HOME"

# Load HF_TOKEN from Docker secret (preferred) or fall back to env var
if [ -f "/run/secrets/hf_token" ]; then
    export HF_TOKEN=$(cat /run/secrets/hf_token | tr -d '\r\n')
    echo "HF_TOKEN loaded from Docker secret"
fi

echo "Detecting hardware for API service..."

# Capture output and validate it is a positive integer
WORKERS=$(python -c "from app.core.hardware import hardware; print(hardware.uvicorn_workers)" 2>/dev/null) || WORKERS=1

# Validate: must be a positive integer, fallback to 1 if invalid
if ! [[ "$WORKERS" =~ ^[1-9][0-9]*$ ]]; then
    echo "Invalid worker count from hardware detection: '$WORKERS', using 1 worker"
    WORKERS=1
fi

echo "Starting uvicorn with $WORKERS workers"
echo ""

exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers "$WORKERS" \
    --loop uvloop \
    --http httptools \
    --timeout-keep-alive 75 \
    --log-level info