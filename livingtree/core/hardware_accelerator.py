"""Hardware accelerator — CPU multithreading fallback (primary)."""

from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class HardwareInfo:
    cpu_count: int = 0
    cpu_name: str = ""
    memory_gb: float = 0.0
    gpu_available: bool = False
    gpu_name: str = ""
    gpu_memory_mb: int = 0


class HardwareAccelerator:
    def __init__(self, force_cpu: bool = False):
        import os
        self._force_cpu = force_cpu
        self._cpu_count = os.cpu_count() or 1

    @property
    def info(self) -> HardwareInfo:
        import psutil
        mem = psutil.virtual_memory()
        return HardwareInfo(
            cpu_count=self._cpu_count,
            cpu_name="CPU",
            memory_gb=mem.total / (1024**3),
            gpu_available=False,
        )

    def accelerate(self, func, *args, **kwargs):
        return func(*args, **kwargs)


_accelerator: Optional[HardwareAccelerator] = None


def get_accelerator(force_cpu: bool = False) -> HardwareAccelerator:
    global _accelerator
    if _accelerator is None:
        _accelerator = HardwareAccelerator(force_cpu=force_cpu)
    return _accelerator
