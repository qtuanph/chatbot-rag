"""
Hardware Profile: Auto-detect server resources at startup.

Singleton — detect 1 lần khi module load, dùng mọi nơi.
Tự động tính toán optimal settings cho uvicorn, Celery, embedding.
"""

import logging
import multiprocessing
import torch
from dataclasses import dataclass

logger = logging.getLogger(__name__)


def _detect_ram_gb() -> float:
    """Detect total system RAM in GB."""
    try:
        with open("/proc/meminfo", "r") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    kb = int(line.split()[1])
                    return round(kb / 1024 / 1024, 1)
    except (FileNotFoundError, ValueError, IndexError):
        pass
    return 8.0  # safe default


def _detect_gpu_vram_gb() -> float:
    """Detect total GPU VRAM in GB (first GPU only)."""
    if torch.cuda.is_available():
        props = torch.cuda.get_device_properties(0)
        return round(props.total_memory / 1024**3, 1)
    return 0.0


@dataclass
class HardwareProfile:
    """
    Detected server hardware resources and derived optimal settings.

    Attributes:
        cpu_count:              Logical CPU cores available
        ram_gb:                 Total system RAM in GB
        gpu_count:              Number of CUDA-capable GPUs
        gpu_vram_gb:            GPU VRAM in GB (first GPU)
        uvicorn_workers:        Recommended uvicorn worker processes
        celery_concurrency:     Celery worker child processes
        celery_autoscale_max:   Celery autoscale upper bound
        embed_parallelism:      Parallel embedding API calls
        db_pool_size:           SQLAlchemy pool_size (per worker)
        db_max_overflow:        SQLAlchemy max_overflow
        qdrant_hnsw_m:          HNSW connectivity (higher = better recall, more RAM)
        qdrant_hnsw_ef:         HNSW accuracy during search
        qdrant_quantization:    Whether to enable Scalar Quantization
        redis_pool_size:        Optimal Redis connection pool size
    """

    cpu_count: int
    ram_gb: float
    gpu_count: int
    gpu_vram_gb: float
    uvicorn_workers: int
    celery_concurrency: int
    celery_autoscale_max: int
    embed_parallelism: int
    db_pool_size: int
    db_max_overflow: int
    qdrant_hnsw_m: int
    qdrant_hnsw_ef: int
    qdrant_quantization: bool
    redis_pool_size: int

    @classmethod
    def detect(cls) -> "HardwareProfile":
        """
        Detect hardware and compute optimal settings.

        VRAM-aware scaling:
          - vram_headroom = vram - 2.0 (2GB for embedding + reranker)
          - Tight GPU (< 8GB headroom): 1 worker, solo pool — prevent OOM
          - Comfortable GPU (>= 8GB headroom): multi-worker — server-grade
          - CPU only: fallback to multi-worker for throughput

        Formulas:
          - uvicorn_workers: 1 if tight GPU, else min(cpu, ram//2, 8)
          - celery_concurrency: min(cpu, 4) if GPU tight, min(cpu, 8) if CPU
          - embed_parallelism: min(cpu * 2, 16) — I/O-bound
          - db_pool_size: max(10, workers * 5) — scale with workers
        """
        cpu = multiprocessing.cpu_count()
        ram = _detect_ram_gb()
        gpu = torch.cuda.device_count()
        vram = _detect_gpu_vram_gb() if gpu > 0 else 0.0

        # VRAM headroom: total VRAM minus what embedding + reranker need (~2GB)
        vram_headroom = (vram - 2.0) if gpu > 0 else 0.0
        tight_gpu = gpu > 0 and vram_headroom < 6.0

        if tight_gpu:
            # Tight GPU (e.g. GTX 1650 4GB): 1 worker, no VRAM duplication
            uvicorn_workers = 1
            celery_concurrency = min(cpu, 4)
            celery_autoscale_max = min(cpu * 2, 8)
        elif gpu > 0:
            # Comfortable GPU (e.g. RTX 4090 24GB): multi-worker safe
            uvicorn_workers = max(1, min(cpu, int(ram // 2), 8))
            celery_concurrency = min(cpu, 8)
            celery_autoscale_max = min(cpu * 2, 16)
        else:
            # CPU only: full multi-worker
            uvicorn_workers = max(1, min(cpu, int(ram // 2), 8))
            celery_concurrency = min(cpu, 8)
            celery_autoscale_max = cpu

        embed_parallelism = min(cpu * 2, 16)

        # DB pool scales with workers — each worker needs its own connections
        db_pool_size = max(10, uvicorn_workers * 5)
        db_max_overflow = db_pool_size

        # Qdrant Optimization (RAM & GPU aware)
        # High-end: m=32, ef=256, quantization=True (accurate & fast)
        # Low-end:  m=16, ef=128, quantization=True (memory efficient)
        if ram >= 32.0 or vram_headroom >= 12.0:
            qdrant_hnsw_m = 32
            qdrant_hnsw_ef = 256
        else:
            qdrant_hnsw_m = 16
            qdrant_hnsw_ef = 128
        
        qdrant_quantization = ram < 64.0  # Always use SQ unless we have massive RAM

        # Redis pool: shared across async tasks in a worker
        redis_pool_size = max(20, uvicorn_workers * 10)

        profile = cls(
            cpu_count=cpu,
            ram_gb=ram,
            gpu_count=gpu,
            gpu_vram_gb=vram,
            uvicorn_workers=uvicorn_workers,
            celery_concurrency=celery_concurrency,
            celery_autoscale_max=celery_autoscale_max,
            embed_parallelism=embed_parallelism,
            db_pool_size=db_pool_size,
            db_max_overflow=db_max_overflow,
            qdrant_hnsw_m=qdrant_hnsw_m,
            qdrant_hnsw_ef=qdrant_hnsw_ef,
            qdrant_quantization=qdrant_quantization,
            redis_pool_size=redis_pool_size,
        )

        # Print diagnostic banner
        mode_label = "TIGHT GPU" if tight_gpu else ("GPU" if gpu > 0 else "CPU")
        logger.info(
            "\n╔══════════════════════════════════════════╗\n"
            "║        HARDWARE PROFILE DETECTED         ║\n"
            "╠══════════════════════════════════════════╣\n"
            "║ CPU cores:   %-28s║\n"
            "║ RAM:         %-28s║\n"
            "║ GPU:         %-28s║\n"
            "║ GPU VRAM:    %-28s║\n"
            "║ Mode:        %-28s║\n"
            "╠══════════════════════════════════════════╣\n"
            "║ uvicorn workers:    %-22s║\n"
            "║ celery concurrency: %-22s║\n"
            "║ celery autoscale:   %-22s║\n"
            "║ embed parallelism:  %-22s║\n"
            "║ db pool size:       %-22s║\n"
            "╚══════════════════════════════════════════╝",
            f"{cpu} cores",
            f"{ram} GB",
            f"{gpu}x" + (f" ({vram} GB VRAM)" if gpu > 0 else ""),
            f"{vram} GB" if gpu > 0 else "N/A",
            mode_label,
            uvicorn_workers,
            celery_concurrency,
            f"{celery_concurrency}-{celery_autoscale_max}",
            embed_parallelism,
            f"{db_pool_size}+{db_max_overflow} (Redis: {redis_pool_size})",
        )
        return profile


# Singleton — import anywhere, detect only once at startup.
hardware = HardwareProfile.detect()
