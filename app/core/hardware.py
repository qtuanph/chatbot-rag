"""
Hardware Profile: Auto-detect server resources at startup.

Singleton — detect 1 lần khi module load, dùng mọi nơi.
Tự động tính toán optimal settings cho uvicorn, Celery, embedding.
"""

import logging
import multiprocessing
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
    try:
        import torch

        if torch.cuda.is_available():
            props = torch.cuda.get_device_properties(0)
            return round(props.total_memory / 1024**3, 1)
    except (ImportError, RuntimeError):
        pass
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
    """

    cpu_count: int
    ram_gb: float
    gpu_count: int
    gpu_vram_gb: float
    uvicorn_workers: int
    celery_concurrency: int
    celery_autoscale_max: int
    embed_parallelism: int

    @classmethod
    def detect(cls) -> "HardwareProfile":
        """
        Detect hardware and compute optimal settings.

        Formulas:
          - uvicorn_workers: min(cpu_count, ram_gb // 2, 8)
            FastAPI is async — few workers handle many connections.
            Each worker ~50-100MB RAM.
          - celery_concurrency: min(cpu_count, 4) when GPU, else min(cpu_count, 8)
            GPU embedding is the bottleneck; more processes compete for GPU.
          - celery_autoscale_max: min(cpu_count * 2, 8) when GPU, else cpu_count
            Scale up when queue is busy, scale down when idle.
          - embed_parallelism: min(cpu_count * 2, 16)
            I/O-bound calls, 2x CPU is safe.
        """
        cpu = multiprocessing.cpu_count()
        ram = _detect_ram_gb()
        gpu = 0
        vram = 0.0
        try:
            import torch

            gpu = torch.cuda.device_count()
            if gpu > 0:
                vram = _detect_gpu_vram_gb()
        except ImportError:
            pass

        has_gpu = gpu > 0

        uvicorn_workers = max(1, min(cpu, int(ram // 2), 8))
        celery_concurrency = min(cpu, 4) if has_gpu else min(cpu, 8)
        celery_autoscale_max = min(cpu * 2, 8) if has_gpu else cpu
        embed_parallelism = min(cpu * 2, 16)

        profile = cls(
            cpu_count=cpu,
            ram_gb=ram,
            gpu_count=gpu,
            gpu_vram_gb=vram,
            uvicorn_workers=uvicorn_workers,
            celery_concurrency=celery_concurrency,
            celery_autoscale_max=celery_autoscale_max,
            embed_parallelism=embed_parallelism,
        )

        # Print diagnostic banner
        logger.info(
            "\n╔══════════════════════════════════════════╗\n"
            "║        HARDWARE PROFILE DETECTED         ║\n"
            "╠══════════════════════════════════════════╣\n"
            "║ CPU cores:   %-28s║\n"
            "║ RAM:         %-28s║\n"
            "║ GPU:         %-28s║\n"
            "║ GPU VRAM:    %-28s║\n"
            "╠══════════════════════════════════════════╣\n"
            "║ uvicorn workers:    %-22s║\n"
            "║ celery concurrency: %-22s║\n"
            "║ celery autoscale:   %-22s║\n"
            "║ embed parallelism:  %-22s║\n"
            "╚══════════════════════════════════════════╝",
            f"{cpu} cores",
            f"{ram} GB",
            f"{gpu}x" + (f" ({vram} GB VRAM)" if gpu > 0 else ""),
            f"{vram} GB" if gpu > 0 else "N/A",
            uvicorn_workers,
            celery_concurrency,
            f"{celery_concurrency}-{celery_autoscale_max}",
            embed_parallelism,
        )
        return profile


# Singleton — import anywhere, detect only once at startup.
hardware = HardwareProfile.detect()
