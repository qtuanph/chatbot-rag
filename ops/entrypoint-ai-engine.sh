#!/bin/bash
# Entrypoint for AI Engine service (embedding + reranking inference server).
# Model download handled by sentence_transformers at server startup.
# HF_TOKEN is loaded from Docker secret (/run/secrets/hf_token) at runtime.

set -e

HF_HOME="${HF_HOME:-/home/qtuanph/.cache/huggingface}"
mkdir -p "$HF_HOME"

# Load HF_TOKEN from Docker secret (preferred) or fall back to env var
if [ -f "/run/secrets/hf_token" ]; then
    export HF_TOKEN=$(cat /run/secrets/hf_token | tr -d '\r\n')
    echo "HF_TOKEN loaded from Docker secret"
fi

echo "Starting AI Engine server..."
exec python -m app.modules.inference.server
