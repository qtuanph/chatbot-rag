#!/bin/bash
# Entrypoint for Butler Celery worker.
# Runs 2 worker nodes in 1 container:
#   node-ingestion: solo pool, GPU, ingestion queue only
#   node-default:    prefork pool, CPU, cleanup+default queues, Beat scheduler

set -e

MAX_TASKS=${CELERY_MAX_TASKS_PER_CHILD:-$(python -c "from app.core.config import settings; print(settings.celery_max_tasks_per_child)" 2>/dev/null || echo "50")}

echo "🎩 Butler worker starting..."

# Detect hardware for prefork concurrency
HW_INFO=$(python -c "
from app.core.hardware import hardware
print(f'{hardware.celery_concurrency} {hardware.celery_autoscale_max}')
" 2>/dev/null || echo "2 4")

CONCURRENCY=$(echo "$HW_INFO" | awk '{print $1}')
AUTOSCALE_MAX=$(echo "$HW_INFO" | awk '{print $2}')

echo "   node-ingestion: pool=solo,   queues=ingestion"
echo "   node-default:    pool=prefork, queues=cleanup,default, concurrency=$CONCURRENCY (autoscale: $CONCURRENCY-$AUTOSCALE_MAX)"
echo "   Beat scheduler: node-default"
echo ""

# Start ingestion worker in background
celery -A app.core.celery_app.celery_app worker \
    -n node-ingestion@%h \
    --pool=solo -c 1 \
    -Q ingestion \
    --loglevel=INFO \
    --max-tasks-per-child="$MAX_TASKS" \
    --pidfile=/tmp/celery-ingestion.pid &

# Start default worker with Beat in background
celery -A app.core.celery_app.celery_app worker \
    -n node-default@%h \
    --pool=prefork -c "$CONCURRENCY" \
    -Q cleanup,default \
    -B \
    --loglevel=INFO \
    --max-tasks-per-child="$MAX_TASKS" \
    --pidfile=/tmp/celery-default.pid &

echo "Both workers started. PID 1 waiting for children..."

# Graceful shutdown handler — forward signals to background workers
_shutdown_requested=false

shutdown() {
    echo "Received $1 — shutting down gracefully..."
    _shutdown_requested=true
    kill -TERM $(cat /tmp/celery-ingestion.pid 2>/dev/null) 2>/dev/null
    kill -TERM $(cat /tmp/celery-default.pid 2>/dev/null) 2>/dev/null
}

trap 'shutdown SIGTERM' SIGTERM
trap 'shutdown SIGINT' SIGINT

# Keep PID 1 alive — wait for any child to exit
wait -n

if [ "$_shutdown_requested" = false ]; then
    echo "A worker exited unexpectedly. Shutting down..."
    shutdown "WORKER_EXIT"
fi

wait
