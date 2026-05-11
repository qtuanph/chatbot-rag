#!/bin/bash
# Entrypoint for API service (FastAPI + uvicorn)
# Runtime lazy load: model download happens here, not in Docker build.
# HF_HOME volume ensures cache persists across restarts.

set -e

HF_HOME="${HF_HOME:-/home/qtuanph/.cache/huggingface}"
mkdir -p "$HF_HOME"

echo "Checking HuggingFace cache..."

# Lazy load embedding model (only downloads if not cached)
EMBEDDING_MODEL_DIR="$HF_HOME/models--AITeamVN--Vietnamese_Embedding_v2"
if [ ! -d "$EMBEDDING_MODEL_DIR" ]; then
    echo "First start: downloading embedding model (this may take a few minutes)..."
    hf download AITeamVN/Vietnamese_Embedding_v2 \
        --local-dir "$EMBEDDING_MODEL_DIR"
    echo "Embedding model ready"
else
    echo "Embedding model found in cache: $EMBEDDING_MODEL_DIR"
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