#!/bin/bash
# Entrypoint for Celery upload-pipeline worker
# Uses HardwareProfile singleton for autoscale settings.
# VRAM-aware: tight GPU → solo pool, comfortable GPU → prefork with concurrency.

set -e

echo "🔍 Detecting hardware for Celery worker..."

HW_INFO=$(python -c "
from app.core.hardware import hardware
print(f'{hardware.gpu_count} {hardware.gpu_vram_gb} {hardware.celery_concurrency} {hardware.celery_autoscale_max}')
" 2>/dev/null || echo "0 0 2 4")

GPU_COUNT=$(echo "$HW_INFO" | awk '{print $1}')
GPU_VRAM=$(echo "$HW_INFO" | awk '{print $2}')
CONCURRENCY=$(echo "$HW_INFO" | awk '{print $3}')
AUTOSCALE_MAX=$(echo "$HW_INFO" | awk '{print $4}')

# Configurable via env var, fallback to settings default
MAX_TASKS=${CELERY_MAX_TASKS_PER_CHILD:-$(python -c "from app.core.config import settings; print(settings.celery_max_tasks_per_child)" 2>/dev/null || echo "50")}

# VRAM headroom: total VRAM minus embedding (~1.1GB) + reranker (~0.5GB) = ~2GB
VRAM_HEADROOM=$(python -c "print(max(0, ${GPU_VRAM} - 2.0))" 2>/dev/null || echo "0")

if [ "$GPU_COUNT" -gt 0 ] && [ "$(echo "$VRAM_HEADROOM < 6.0" | bc -l 2>/dev/null || echo "1")" = "1" ]; then
    echo "🎮 Tight GPU (${GPU_VRAM}GB VRAM, ${VRAM_HEADROOM}GB headroom) — using solo pool"
    echo ""
    exec celery -A app.core.celery_app.celery_app worker \
        --loglevel=INFO \
        --queues=ingestion \
        --pool=solo \
        --max-tasks-per-child="$MAX_TASKS"
elif [ "$GPU_COUNT" -gt 0 ]; then
    echo "🚀 Comfortable GPU (${GPU_VRAM}GB VRAM, ${VRAM_HEADROOM}GB headroom) — prefork pool"
    echo "   concurrency=$CONCURRENCY autoscale=$CONCURRENCY-$AUTOSCALE_MAX"
    echo ""
    exec celery -A app.core.celery_app.celery_app worker \
        --loglevel=INFO \
        --queues=ingestion,default \
        --pool=prefork \
        --max-tasks-per-child="$MAX_TASKS" \
        --concurrency="$CONCURRENCY" \
        --autoscale="$AUTOSCALE_MAX",$((CONCURRENCY > 1 ? CONCURRENCY / 2 : 1))
else
    echo "💻 CPU mode — prefork pool"
    echo "   concurrency=$CONCURRENCY autoscale=$CONCURRENCY-$AUTOSCALE_MAX"
    echo ""
    exec celery -A app.core.celery_app.celery_app worker \
        --loglevel=INFO \
        --queues=ingestion,default \
        --max-tasks-per-child="$MAX_TASKS" \
        --concurrency="$CONCURRENCY" \
        --autoscale="$AUTOSCALE_MAX",$((CONCURRENCY > 1 ? CONCURRENCY / 2 : 1))
fi
