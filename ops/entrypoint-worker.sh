#!/bin/bash
# Entrypoint for Celery upload-pipeline worker
# Uses HardwareProfile singleton for autoscale settings.

set -e

echo "🔍 Detecting hardware for Celery worker..."

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
