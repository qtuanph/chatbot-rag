#!/bin/bash
# Entrypoint for Celery workers.
# Model runtime is handled by Docker Model Runner / external providers.
# Runs 2 worker nodes in 1 container:
#   node-ingestion: solo pool, GPU, ingestion queue only
#   node-default:    prefork pool, CPU, cleanup+default queues, Beat scheduler

set -e

export HF_HOME="${HF_HOME:-/home/qtuanph/.cache/huggingface}"
export HUGGINGFACE_HUB_CACHE="${HUGGINGFACE_HUB_CACHE:-$HF_HOME}"
export FASTEMBED_CACHE_PATH="${FASTEMBED_CACHE_PATH:-$HF_HOME/fastembed}"
mkdir -p "$HF_HOME" "$FASTEMBED_CACHE_PATH" /app/data
chown -R 1000:1000 "$HF_HOME" "$FASTEMBED_CACHE_PATH" 2>/dev/null || true

# Initialize SQLite settings database with provider templates
python -c "from app.modules.settings.database import init_db; init_db()" 2>/dev/null && echo "Settings DB ready" || echo "Settings DB init skipped (may already exist)"

# Load HF_TOKEN from Docker secret (preferred) or fall back to env var
if [ -f "/run/secrets/hf_token" ]; then
    export HF_TOKEN=$(cat /run/secrets/hf_token | tr -d '\r\n')
    export HUGGING_FACE_HUB_TOKEN="$HF_TOKEN"
    echo "HF_TOKEN loaded from Docker secret"
fi

echo "Prewarming FastEmbed sparse model cache..."
python - <<'PY'
from fastembed.sparse.sparse_text_embedding import SparseTextEmbedding

SparseTextEmbedding(model_name="Qdrant/bm25")
print("FastEmbed sparse model cache ready")
PY

MAX_TASKS=${CELERY_MAX_TASKS_PER_CHILD:-$(python -c "from app.core.config import settings; print(settings.celery_max_tasks_per_child)" 2>/dev/null | tail -n 1 || echo "50")}

# 0. Clean up stale PIDs from previous runs
rm -f /tmp/celery-*.pid

echo "Worker starting..."

# Detect hardware for prefork concurrency.
# IMPORTANT: stderr redirected + tail -n 1 to avoid stdout pollution from GPU libs
# (e.g., AMD ROCm amdsmi prints "/opt/rocm/lib/libamd_smi.so: Unable..." to stdout)
# which would corrupt CONCURRENCY and crash Celery with an invalid -c value.
HW_INFO=$(python -c "
from app.core.hardware import hardware
print(f'{hardware.celery_concurrency} {hardware.celery_autoscale_max}')
" 2>/dev/null | tail -n 1 || echo "2 4")

CONCURRENCY=$(echo "$HW_INFO" | awk '{print $1}')
AUTOSCALE_MAX=$(echo "$HW_INFO" | awk '{print $2}')

# Validate: must be positive integers — final guard against any residual pollution
if ! [[ "$CONCURRENCY" =~ ^[1-9][0-9]*$ ]]; then
    echo "Invalid CONCURRENCY from hardware detection: '$CONCURRENCY', falling back to 2"
    CONCURRENCY=2
fi
if ! [[ "$AUTOSCALE_MAX" =~ ^[1-9][0-9]*$ ]]; then
    echo "Invalid AUTOSCALE_MAX from hardware detection: '$AUTOSCALE_MAX', falling back to 4"
    AUTOSCALE_MAX=4
fi

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
