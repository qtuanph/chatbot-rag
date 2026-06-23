#!/bin/bash
# Entrypoint for API service (FastAPI + uvicorn)
# Model runtime is handled by Docker Model Runner / external providers; this container should not assume TEI sidecars.

set -e

export HF_HOME="${HF_HOME:-/home/qtuanph/.cache/huggingface}"
export HUGGINGFACE_HUB_CACHE="${HUGGINGFACE_HUB_CACHE:-$HF_HOME}"
export FASTEMBED_CACHE_PATH="${FASTEMBED_CACHE_PATH:-$HF_HOME/fastembed}"
mkdir -p "$HF_HOME" "$FASTEMBED_CACHE_PATH" /app/data

# Initialize SQLite settings database with provider templates
echo "Initializing settings database..."
python -c "from app.modules.settings.database import init_db; init_db()" 2>/dev/null && echo "Settings DB ready" || echo "Settings DB init skipped (may already exist)"

# Load HF_TOKEN from Docker secret (preferred) or fall back to env var
if [ -f "/run/secrets/hf_token" ]; then
    export HF_TOKEN=$(cat /run/secrets/hf_token | tr -d '\r\n')
    export HUGGING_FACE_HUB_TOKEN="$HF_TOKEN"
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
    --timeout-keep-alive 90 \
    --log-level info
