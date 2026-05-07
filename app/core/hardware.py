"""
Hardware Profile: Production-grade hardware detection and optimal configuration.
Strictly requires psutil and pynvml. Optimized for Docker/K8s high-concurrency (200+ CCU).
"""

import logging
import multiprocessing
import os
import psutil
import pynvml
import torch
from dataclasses import dataclass

logger = logging.getLogger(__name__)


def _get_container_memory_limit() -> float:
    """Detect memory limit in Docker/K8s using cgroups."""
    try:
        # Cgroup v2
        path = "/sys/fs/cgroup/memory.max"
        if os.path.exists(path):
            with open(path, "r") as f:
                val = f.read().strip()
                if val != "max":
                    return round(int(val) / 1024 / 1024 / 1024, 1)

        # Cgroup v1
        path = "/sys/fs/cgroup/memory/memory.limit_in_bytes"
        if os.path.exists(path):
            with open(path, "r") as f:
                val = f.read().strip()
                return round(int(val) / 1024 / 1024 / 1024, 1)
    except Exception:
        pass
    return 0.0


def _detect_ram_gb() -> float:
    """Detect available RAM, prioritizing container limits."""
    container_limit = _get_container_memory_limit()
    if container_limit > 0:
        return container_limit

    return round(psutil.virtual_memory().total / (1024**3), 1)


def _detect_gpu_info() -> tuple[int, float]:
    """Detect GPU count and VRAM using pynvml (professional grade)."""
    try:
        pynvml.nvmlInit()
        count = pynvml.nvmlDeviceGetCount()
        if count > 0:
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            return count, round(info.total / 1024**3, 1)
    except Exception as e:
        if "NVML Shared Library Not Found" in str(e):
            logger.info("No NVIDIA GPU detected (NVML library not found), falling back to CPU/torch logic.")
        else:
            logger.info("NVML detection failed, falling back to torch: %s", e)

        if torch.cuda.is_available():
            return torch.cuda.device_count(), round(torch.cuda.get_device_properties(0).total_memory / 1024**3, 1)
    return 0, 0.0


@dataclass
class HardwareProfile:
    """
    Production-grade Hardware Profile.
    Calculates optimal threading, pooling, and worker settings for 200+ CCU.
    """

    cpu_count: int
    ram_gb: float
    gpu_count: int
    gpu_vram_gb: float

    # Execution Settings
    uvicorn_workers: int
    redis_io_threads: int
    celery_concurrency: int
    celery_autoscale_max: int
    embed_parallelism: int
    inference_concurrency: int

    # Resource Pools (Tuned for 200 CCU Chatbot)
    db_pool_size: int
    db_max_overflow: int
    redis_pool_size: int

    # AI Specifics
    qdrant_hnsw_m: int
    qdrant_hnsw_ef: int
    qdrant_quantization: bool

    @classmethod
    def detect(cls) -> "HardwareProfile":
        cpu = multiprocessing.cpu_count()
        ram = _detect_ram_gb()
        gpu_count, vram = _detect_gpu_info()

        # VRAM-Aware Worker Strategy
        # Reserve 2GB for base overhead, each worker might need its own context if not shared
        vram_headroom = (vram - 2.0) if gpu_count > 0 else 0.0
        tight_gpu = gpu_count > 0 and vram_headroom < 6.0

        if tight_gpu:
            uvicorn_workers = 1  # Avoid VRAM duplication on small GPUs
        elif gpu_count > 0:
            # On powerful GPUs (like 4090/A100), scale by VRAM (approx 4GB per worker context)
            # but also respect CPU/RAM and cap at 8.
            uvicorn_workers = max(1, min(cpu, int(ram // 6), int(vram_headroom // 4), 8))
        else:
            # CPU only mode: scale by RAM (6GB per worker)
            uvicorn_workers = max(1, min(cpu, int(ram // 6), 8))

        # Redis 8/9 Multi-threading: set io-threads (usually cpu/4, min 1)
        redis_io_threads = max(1, cpu // 4)

        # Database Pool: Total CCU 200 distributed across workers
        # Standard: (CCU / workers) + buffer
        db_pool_size = max(20, min(100, (250 // uvicorn_workers)))
        db_max_overflow = 20

        # Redis Pool: High-frequency ops (Semantic Caching, Streams, JSON)
        redis_pool_size = max(100, uvicorn_workers * 30)

        # Qdrant Indexing Settings
        if ram >= 32.0 or vram_headroom >= 12.0:
            qdrant_hnsw_m = 32
            qdrant_hnsw_ef = 256
        else:
            qdrant_hnsw_m = 16
            qdrant_hnsw_ef = 128

        qdrant_quantization = ram < 64.0

        profile = cls(
            cpu_count=cpu,
            ram_gb=ram,
            gpu_count=gpu_count,
            gpu_vram_gb=vram,
            uvicorn_workers=uvicorn_workers,
            redis_io_threads=redis_io_threads,
            celery_concurrency=max(1, min(cpu, int(ram // 2), 8)),
            celery_autoscale_max=max(1, min(cpu * 2, int(ram // 1.5), 16)),
            embed_parallelism=max(1, cpu // 2),
            inference_concurrency=max(1, cpu // 4),
            db_pool_size=db_pool_size,
            db_max_overflow=db_max_overflow,
            redis_pool_size=redis_pool_size,
            qdrant_hnsw_m=qdrant_hnsw_m,
            qdrant_hnsw_ef=qdrant_hnsw_ef,
            qdrant_quantization=qdrant_quantization,
        )

        logger.info(
            "\n"
            "╔══════════════════════════════════════════╗\n"
            "║    PRODUCTION HARDWARE PROFILE DETECTED  ║\n"
            "╠══════════════════════════════════════════╣\n"
            "║ CPU/RAM:     %-2s cores / %-5s GB       ║\n"
            "║ GPU:         %-2sx %-14s         ║\n"
            "║ Workers:     %-26s║\n"
            "║ DB Pool:     %-2s (overflow: %-2s)       ║\n"
            "║ Redis Pool:  %-26s║\n"
            "╚══════════════════════════════════════════╝",
            cpu,
            ram,
            gpu_count,
            f"{vram}GB VRAM" if gpu_count > 0 else "N/A",
            uvicorn_workers,
            db_pool_size,
            db_max_overflow,
            redis_pool_size,
        )
        return profile


# Lazy Singleton
_hardware_instance: HardwareProfile | None = None


def get_hardware() -> HardwareProfile:
    """Lazy initialization of the Hardware Profile."""
    global _hardware_instance
    if _hardware_instance is None:
        _hardware_instance = HardwareProfile.detect()
    return _hardware_instance


# For backwards compatibility with existing imports
hardware = get_hardware()
