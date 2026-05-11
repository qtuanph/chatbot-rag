#!/bin/bash
# Entrypoint for Celery workers.
# Runtime lazy load: model download happens here, not in Docker build.
# HF_HOME volume ensures cache persists across restarts.
# Runs 2 worker nodes in 1 container:
#   node-ingestion: solo pool, GPU, ingestion queue only
#   node-default:    prefork pool, CPU, cleanup+default queues, Beat scheduler

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

MAX_TASKS=${CELERY_MAX_TASKS_PER_CHILD:-$(python -c "from app.core.config import settings; print(settings.celery_max_tasks_per_child)" 2>/dev/null || echo "50")}

# 0. Clean up stale PIDs from previous runs
rm -f /tmp/celery-*.pid

echo "Worker starting..."

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

# 2. Start default worker
# Only run Beat (-B) on the first replica to avoid duplicate periodic tasks
# (Assumes K8s StatefulSet or manual scaling where HOSTNAME has index)
BEAT_FLAG=""
if [[ "$HOSTNAME" == *"-0" ]] || [[ -z "$HOSTNAME" ]]; then
    echo "   Beat scheduler: ENABLED on this node ($HOSTNAME)"
    BEAT_FLAG="-B"
else
    echo "   Beat scheduler: DISABLED on this node ($HOSTNAME) to avoid duplicates"
fi

celery -A app.core.celery_app.celery_app worker \
    -n node-default@%h \
    --pool=prefork -c "$CONCURRENCY" \
    -Q cleanup,default \
    $BEAT_FLAG \
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