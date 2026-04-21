#!/bin/bash
# Entrypoint for Celery upload-pipeline worker
# Uses HardwareProfile singleton for autoscale settings.
# GPU mode: solo pool (CUDA incompatible with prefork fork).
# CPU mode: prefork pool with autoscale.

set -e

echo "🔍 Detecting hardware for Celery worker..."

HAS_GPU=$(python -c "
try:
    import torch
    print('true' if torch.cuda.is_available() else 'false')
except Exception:
    print('false')
" 2>/dev/null || echo "false")

if [ "$HAS_GPU" = "true" ]; then
    echo "🎮 GPU detected — using solo pool (CUDA incompatible with prefork)"
    echo ""
    exec celery -A app.core.celery_app.celery_app worker \
        --loglevel=INFO \
        --queues=ingestion,default \
        --pool=solo \
        --max-tasks-per-child=50
else
    HW=$(python -c "from app.core.hardware import hardware; print(f'{hardware.celery_concurrency} {hardware.celery_autoscale_max}')" 2>/dev/null || echo "2 4")

    CONCURRENCY=$(echo "$HW" | awk '{print $1}')
    AUTOSCALE_MAX=$(echo "$HW" | awk '{print $2}')

    echo "🚀 Starting Celery worker: concurrency=$CONCURRENCY autoscale=$CONCURRENCY-$AUTOSCALE_MAX"
    echo ""

    exec celery -A app.core.celery_app.celery_app worker \
        --loglevel=INFO \
        --queues=ingestion,default \
        --max-tasks-per-child=50 \
        --concurrency="$CONCURRENCY" \
        --autoscale="$AUTOSCALE_MAX",$((CONCURRENCY > 1 ? CONCURRENCY / 2 : 1))
fi
