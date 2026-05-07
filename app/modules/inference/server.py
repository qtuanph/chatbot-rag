"""
AI-Engine Inference Server — Lightweight FastAPI server for model inference.
Decouples heavy model loading from the main API and workers.
"""

import logging
import time
from contextlib import asynccontextmanager
from typing import List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel

from app.core.config import settings
from app.core.hardware import hardware

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ai-engine")

# --- Models ---


class EmbedRequest(BaseModel):
    texts: List[str]
    batch_size: Optional[int] = 32
    normalize: Optional[bool] = True
    task_type: Optional[str] = "query"  # query or passage


class EmbedResponse(BaseModel):
    embeddings: List[List[float]]
    dimension: int
    latency_ms: float


class RerankPair(BaseModel):
    query: str
    text: str


class RerankRequest(BaseModel):
    pairs: List[RerankPair]
    top_k: Optional[int] = None


class RerankResult(BaseModel):
    index: int
    score: float


class RerankResponse(BaseModel):
    results: List[RerankResult]
    latency_ms: float


# --- Global State ---


class InferenceEngine:
    def __init__(self):
        self.embedding_model = None
        self.reranker_model = None
        self.reranker_tokenizer = None
        self.device = "cuda" if hardware.gpu_count > 0 else "cpu"

    def load_models(self):
        # Load Embedding Model
        try:
            from sentence_transformers import SentenceTransformer

            model_name = settings.embedding_hf_model
            logger.info(f"Loading embedding model: {model_name} on {self.device}...")

            if self.device == "cuda":
                self.embedding_model = SentenceTransformer(model_name, device="cuda")
                self.embedding_model = self.embedding_model.half()
            else:
                self.embedding_model = SentenceTransformer(model_name, backend="onnx")

            logger.info("Embedding model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")

        # Load Reranker Model
        try:
            from transformers import AutoModelForSequenceClassification, AutoTokenizer

            model_name = settings.retrieval_rerank_model
            logger.info(f"Loading reranker model: {model_name} on {self.device}...")

            self.reranker_tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
            self.reranker_model = AutoModelForSequenceClassification.from_pretrained(model_name, trust_remote_code=True)
            self.reranker_model.to(self.device)
            self.reranker_model.eval()

            logger.info("Reranker model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load reranker model: {e}")

    def get_embedding_dimension(self) -> int:
        if self.embedding_model:
            return self.embedding_model.get_embedding_dimension()
        return 0


engine = InferenceEngine()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Load models
    engine.load_models()
    yield
    # Shutdown: Clean up (optional)
    logger.info("Shutting down AI-Engine...")


app = FastAPI(title="Chatbot RAG AI-Engine", lifespan=lifespan)

# --- Routes ---


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "device": engine.device,
        "embedding_loaded": engine.embedding_model is not None,
        "reranker_loaded": engine.reranker_model is not None,
    }


@app.post("/embed", response_model=EmbedResponse)
async def embed(request: EmbedRequest):
    if not engine.embedding_model:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Embedding model not loaded")

    start_time = time.perf_counter()

    # Apply prefixes if configured in settings (simplified for now)
    # In a real scenario, we might want to pass these from the request
    texts = request.texts

    embeddings = engine.embedding_model.encode(
        texts, batch_size=request.batch_size, normalize_embeddings=request.normalize, show_progress_bar=False
    )

    latency = (time.perf_counter() - start_time) * 1000

    return EmbedResponse(embeddings=embeddings.tolist(), dimension=engine.get_embedding_dimension(), latency_ms=latency)


@app.post("/rerank", response_model=RerankResponse)
async def rerank(request: RerankRequest):
    if not engine.reranker_model or not engine.reranker_tokenizer:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Reranker model not loaded")

    import torch

    start_time = time.perf_counter()

    pairs = [[p.query, p.text] for p in request.pairs]

    with torch.no_grad():
        inputs = engine.reranker_tokenizer(
            pairs,
            padding=True,
            truncation=True,
            return_tensors="pt",
            max_length=2304,  # Match reranker.py
        ).to(engine.device)

        scores = engine.reranker_model(**inputs, return_dict=True).logits.view(-1).float()
        scores_list = scores.tolist()

    # Create results with original indices
    results = [RerankResult(index=i, score=score) for i, score in enumerate(scores_list)]

    # Sort by score descending
    results.sort(key=lambda x: x.score, reverse=True)

    # Truncate to top_k if specified
    if request.top_k:
        results = results[: request.top_k]

    latency = (time.perf_counter() - start_time) * 1000

    return RerankResponse(results=results, latency_ms=latency)


if __name__ == "__main__":
    # Dynamically determine workers based on hardware profile and GPU presence
    # Note: On GPU systems, we usually want fewer workers but larger batches to avoid VRAM fragmentation
    if hardware.gpu_count > 0:
        # High-performance GPU mode: 2 workers per GPU is usually a sweet spot for throughput
        # This allows parallel inference while sharing VRAM efficiently
        workers = max(1, hardware.gpu_count * 2)
        logger.info(f"GPU detected. Starting server with {workers} hardware-optimized workers.")
    else:
        # CPU mode: Use logical cores but cap to avoid overhead
        workers = min(hardware.cpu_count, 4) if hardware.cpu_count > 1 else 1
        logger.info(f"CPU mode. Starting server with {workers} workers based on {hardware.cpu_count} cores.")

    uvicorn.run(
        "app.modules.inference.server:app",
        host="0.0.0.0",
        port=8000,
        workers=workers,
        loop="auto",
        http="h11",
        timeout_keep_alive=settings.api_timeout_keep_alive,
    )
