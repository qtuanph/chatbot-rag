"""
Hardware Profile: Auto-detect server CPU/GPU resources at startup.

Tính toán optimal settings cho Celery workers và embedding parallelism.
Được import như singleton — gọi 1 lần khi module load, dùng mọi nơi.
"""

import logging
import multiprocessing
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class HardwareProfile:
    """
    Detected server hardware resources and derived optimal settings.

    Attributes:
        cpu_count:              Physical/logical CPU cores available
        gpu_count:              Number of CUDA-capable GPUs (0 if none/not installed)
        celery_concurrency:     Recommended Celery worker concurrency (CPU-heavy tasks)
        embed_parallelism:      Recommended parallel embedding API calls (I/O-bound)
    """

    cpu_count: int
    gpu_count: int
    celery_concurrency: int
    embed_parallelism: int

    @classmethod
    def detect(cls) -> "HardwareProfile":
        """
        Detect hardware and compute optimal settings.

        Concurrency formulas:
          - celery_concurrency = min(cpu_count, 4)
            Docling + EasyOCR are CPU-heavy; diminishing returns above 4 workers.
          - embed_parallelism = min(cpu_count * 2, 16)
            Embedding API calls are I/O-bound (network wait), so 2x CPU is safe.
            Cap at 16 to avoid Gemini rate-limit bursts.
        """
        cpu = multiprocessing.cpu_count()

        gpu = 0
        try:
            import torch  # type: ignore
            gpu = torch.cuda.device_count()
        except ImportError:
            pass  # PyTorch not installed → no GPU acceleration → fine

        profile = cls(
            cpu_count=cpu,
            gpu_count=gpu,
            celery_concurrency=min(cpu, 4),
            embed_parallelism=min(cpu * 2, 16),
        )

        logger.info(
            "Hardware profile detected: cpu=%d gpu=%d "
            "→ celery_concurrency=%d embed_parallelism=%d",
            cpu,
            gpu,
            profile.celery_concurrency,
            profile.embed_parallelism,
        )
        return profile


# Singleton — import từ bất kỳ module nào, chỉ detect 1 lần khi startup.
hardware = HardwareProfile.detect()
