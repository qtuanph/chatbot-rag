#!/bin/bash
# Entrypoint for API service (FastAPI + uvicorn)
# Uses HardwareProfile singleton for optimal worker count.

set -e

echo "🔍 Detecting hardware for API service..."

WORKERS=$(python -c "from app.core.hardware import hardware; print(hardware.uvicorn_workers)" 2>/dev/null || echo "4")

echo "🚀 Starting uvicorn with $WORKERS workers"
echo ""

exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers "$WORKERS" \
    --loop uvloop \
    --http httptools
