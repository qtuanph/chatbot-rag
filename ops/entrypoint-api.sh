#!/bin/bash
# Entrypoint for API service (FastAPI + uvicorn)
# Uses HardwareProfile singleton for optimal worker count.

set -e

echo "🔍 Detecting hardware for API service..."

# Capture output and validate it is a positive integer
WORKERS=$(python -c "from app.core.hardware import hardware; print(hardware.uvicorn_workers)" 2>/dev/null) || WORKERS=1

# Validate: must be a positive integer, fallback to 1 if invalid
if ! [[ "$WORKERS" =~ ^[1-9][0-9]*$ ]]; then
    echo "⚠️  Invalid worker count from hardware detection: '$WORKERS', using 1 worker"
    WORKERS=1
fi

echo "🚀 Starting uvicorn with $WORKERS workers"
echo ""

exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers "$WORKERS" \
    --loop uvloop \
    --http httptools \
    --timeout-keep-alive 75 \
    --log-level info
