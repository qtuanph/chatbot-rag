#!/bin/bash
# Entrypoint for AI Engine service (embedding + reranking inference server).
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

# Reranker model (optional, only download if RETRIEVAL_RERANK_ENABLED=true at runtime)
# Check if reranker is enabled in config before downloading
RERANK_ENABLED=$(python -c "from app.core.config import settings; print(settings.retrieval_rerank_enabled)" 2>/dev/null || echo "False")
if [ "$RERANK_ENABLED" = "True" ]; then
    RERANKER_MODEL_DIR="$HF_HOME/models--AITeamVN--Vietnamese_Reranker"
    if [ ! -d "$RERANKER_MODEL_DIR" ]; then
        echo "Reranker enabled: downloading reranker model..."
        hf download AITeamVN/Vietnamese_Reranker \
            --local-dir "$RERANKER_MODEL_DIR"
        echo "Reranker model ready"
    else
        echo "Reranker model found in cache: $RERANKER_MODEL_DIR"
    fi
else
    echo "Reranker disabled (RETRIEVAL_RERANK_ENABLED=false) — skipping"
fi

echo "Starting AI Engine server..."
exec python -m app.modules.inference.server