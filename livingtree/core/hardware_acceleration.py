"""HardwareAcceleration — GPU-aware acceleration for compute-heavy operations.

LivingTree's compute-intensive modules (FAISS, OCR, embedding, chunking)
can benefit from hardware acceleration on supported devices.

自检测 + 自适应:
  CUDA GPU → FAISS GPU index, torch CUDA embeddings, PaddleOCR GPU
  Apple MPS → torch MPS embeddings
  CPU only → NumPy optimized path, multiprocessing chunking

Does NOT rewrite existing modules — provides configuration and utilities
that existing code can optionally use for acceleration.

Usage:
    accel = get_hardware_accelerator()
    accel.report()  # → "GPU: NVIDIA RTX 3060, 12GB VRAM | Ready"

    # FAISS GPU
    index = accel.create_faiss_index(dimension=768, use_gpu=True)
    # → GPUIndex if CUDA available, CPU Flat index otherwise

    # Batch embedding
    embeddings = accel.batch_embed(texts, model, batch_size=32)
    # → GPU-batched if CUDA, sequential otherwise
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

import torch
import faiss
from paddleocr import PaddleOCR
# ═══════════════════════════════════════════════════════════════════
# GPU Detection
# ═══════════════════════════════════════════════════════════════════

@dataclass
class GPUInfo:
    """GPU 设备信息."""
    available: bool = False
    backend: str = "cpu"           # cuda / mps / cpu
    device_name: str = "CPU"
    device_count: int = 0
    memory_mb: int = 0
    compute_capability: str = ""

    @property
    def can_accelerate_faiss(self) -> bool:
        return self.available and self.backend == "cuda"

    @property
    def can_accelerate_torch(self) -> bool:
        return self.available and self.backend in ("cuda", "mps")

    @property
    def can_accelerate_ocr(self) -> bool:
        return self.available and self.backend == "cuda"


class HardwareAccelerator:
    """GPU 感知硬件加速层.

    提供:
      - GPU 检测与能力报告
      - FAISS GPU index 创建
      - 批量嵌入计算
      - 并行文档分块
      - 加速开关（允许强制 CPU 模式）
    """

    def __init__(self, force_cpu: bool = False):
        self._force_cpu = force_cpu
        self._gpu = self._detect_gpu()
        if self._gpu.available:
            logger.info(f"HardwareAccelerator: {self._gpu.device_name} ({self._gpu.memory_mb}MB)")
        else:
            logger.info("HardwareAccelerator: CPU only")

    def _detect_gpu(self) -> GPUInfo:
        if self._force_cpu:
            return GPUInfo()

        # 1. Try CUDA
        if torch.cuda.is_available():
            info = GPUInfo(
                available=True, backend="cuda",
                device_name=torch.cuda.get_device_name(0),
                device_count=torch.cuda.device_count(),
            )
            try:
                info.memory_mb = int(
                    torch.cuda.get_device_properties(0).total_memory / 1024**2)
            except Exception:
                pass
            try:
                cap = torch.cuda.get_device_capability(0)
                info.compute_capability = f"{cap[0]}.{cap[1]}"
            except Exception:
                pass
            return info

        # 2. Try MPS (Apple Silicon)
        if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            return GPUInfo(
                available=True, backend="mps",
                device_name="Apple MPS", device_count=1,
            )

        # 3. Try nvidia-smi (even without torch)
        import asyncio
        try:
            try:
                from ..treellm.unified_exec import run
                result = asyncio.run(run("nvidia-smi --query-gpu=name,memory.total --format=csv,noheader", timeout=5))
                stdout = result.stdout
                exit_code = result.exit_code
            except ImportError:
                import subprocess
                result = subprocess.run(
                    ["nvidia-smi", "--query-gpu=name,memory.total",
                     "--format=csv,noheader"],
                    capture_output=True, text=True, timeout=5)
                stdout = result.stdout
                exit_code = result.returncode
            if exit_code == 0 and stdout.strip():
                line = result.stdout.strip().split("\n")[0]
                parts = line.split(",")
                name = parts[0].strip() if parts else "NVIDIA GPU"
                mem_str = parts[1].strip().replace(" MiB", "") if len(parts) > 1 else "0"
                return GPUInfo(
                    available=True, backend="cuda",
                    device_name=name,
                    device_count=len(stdout.strip().split("\n")),
                    memory_mb=int(mem_str) if mem_str.isdigit() else 0,
                )
        except Exception:
            pass

        return GPUInfo()

    @property
    def gpu(self) -> GPUInfo:
        return self._gpu

    def report(self) -> str:
        if self._gpu.available:
            return (
                f"GPU: {self._gpu.device_name}, "
                f"{self._gpu.memory_mb}MB VRAM | "
                f"FAISS GPU: {'✓' if self._gpu.can_accelerate_faiss else '✗'} | "
                f"Torch GPU: {'✓' if self._gpu.can_accelerate_torch else '✗'} | "
                f"OCR GPU: {'✓' if self._gpu.can_accelerate_ocr else '✗'}"
            )
        return "CPU only — no GPU detected"

    # ═══ FAISS GPU ═══

    def create_faiss_index(self, dimension: int = 768,
                           use_gpu: bool = True) -> Any:
        """创建 FAISS 索引（自动选择 GPU/CPU）."""
        if use_gpu and self._gpu.can_accelerate_faiss:
            # GPU index: IVF + Flat
            nlist = min(4096, max(128, dimension // 4))
            quantizer = faiss.IndexFlatL2(dimension)
            index = faiss.IndexIVFFlat(quantizer, dimension, nlist)
            gpu_index = faiss.index_cpu_to_all_gpus(index)
            logger.info(f"FAISS GPU index: dim={dimension}, nlist={nlist}")
            return gpu_index

        # CPU index (flat for small, IVF for large)
        cpu_index = faiss.IndexFlatL2(dimension)
        logger.info(f"FAISS CPU index: dim={dimension}")
        return cpu_index

    def ensure_faiss_gpu(self, index: Any) -> Any:
        """If GPU available, move existing FAISS index to GPU."""
        if not self._gpu.can_accelerate_faiss:
            return index
        try:
            import faiss
            return faiss.index_cpu_to_all_gpus(index)
        except Exception:
            return index

    # ═══ Batch Embedding ═══

    def get_torch_device(self) -> str:
        """获取最优 torch 设备."""
        if self._force_cpu:
            return "cpu"
        if self._gpu.backend == "cuda":
            return "cuda"
        if self._gpu.backend == "mps":
            return "mps"
        return "cpu"

    def batch_embed(
        self, texts: list[str], model: Any = None,
        batch_size: int = 32, device: str = "",
    ) -> list[list[float]]:
        """批量计算嵌入向量（GPU 加速）.

        Args:
            texts: 文本列表
            model: embedding 模型（需支持 encode() 方法）
            batch_size: 批大小
            device: 设备（auto / cuda / cpu）

        Returns:
            嵌入向量列表
        """
        if not model:
            return [[0.0] * 768 for _ in texts]

        device = device or self.get_torch_device()
        embeddings: list[list[float]] = []

        try:
            import numpy as np
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                if hasattr(model, 'encode'):
                    vecs = model.encode(batch, device=device, show_progress_bar=False)
                elif hasattr(model, '__call__'):
                    vecs = model(batch)
                else:
                    vecs = np.zeros((len(batch), 768))
                if hasattr(vecs, 'tolist'):
                    embeddings.extend(vecs.tolist())
                else:
                    embeddings.extend([[float(v) for v in vec] for vec in vecs])
        except Exception as e:
            logger.debug(f"Batch embed fallback: {e}")
            # Fallback: single-threaded
            for text in texts:
                try:
                    vec = model.encode([text])[0]
                    embeddings.append(vec.tolist() if hasattr(vec, 'tolist') else list(vec))
                except Exception:
                    embeddings.append([0.0] * 768)

        return embeddings

    # ═══ Parallel Chunking ═══

    def parallel_chunk(
        self, documents: list[str], chunk_size: int = 1000,
        workers: int = 0,
    ) -> list[list[str]]:
        """并行文档分块（多进程加速大文档处理）.

        Args:
            documents: 文档文本列表
            chunk_size: 分块大小
            workers: 并行进程数（0=auto）

        Returns:
            每个文档的分块列表
        """
        if len(documents) <= 1:
            return [self._chunk_single(d, chunk_size) for d in documents]

        try:
            from concurrent.futures import ProcessPoolExecutor
            import multiprocessing

            if workers <= 0:
                workers = min(len(documents), multiprocessing.cpu_count() or 4)

            with ProcessPoolExecutor(max_workers=workers) as executor:
                futures = [
                    executor.submit(self._chunk_single, doc, chunk_size)
                    for doc in documents
                ]
                return [f.result() for f in futures]
        except Exception as e:
            logger.debug(f"Parallel chunk fallback: {e}")
            return [self._chunk_single(d, chunk_size) for d in documents]

    @staticmethod
    def _chunk_single(text: str, chunk_size: int) -> list[str]:
        chunks = []
        for i in range(0, len(text), chunk_size - 100):  # 100 char overlap
            chunk = text[i:i + chunk_size].strip()
            if chunk:
                chunks.append(chunk)
        return chunks

    # ═══ OCR GPU ═══

    def create_ocr(self, use_gpu: bool = True) -> Any | None:
        """创建 GPU 加速 OCR 实例."""
        if not use_gpu or not self._gpu.can_accelerate_ocr:
            return None

        try:
            ocr = PaddleOCR(
                use_angle_cls=True, lang='ch',
                use_gpu=True, show_log=False,
            )
            logger.info("PaddleOCR GPU initialized")
            return ocr
        except Exception as e:
            logger.debug(f"PaddleOCR GPU: {e}")
        return None

    # ═══ Stats ═══

    def stats(self) -> dict[str, Any]:
        return {
            "backend": self._gpu.backend,
            "device": self._gpu.device_name,
            "memory_mb": self._gpu.memory_mb,
            "faiss_gpu": self._gpu.can_accelerate_faiss,
            "torch_gpu": self._gpu.can_accelerate_torch,
            "ocr_gpu": self._gpu.can_accelerate_ocr,
            "force_cpu": self._force_cpu,
        }


# ── Singleton ──────────────────────────────────────────────────────

_hardware_accelerator: HardwareAccelerator | None = None


def get_hardware_accelerator(force_cpu: bool = False) -> HardwareAccelerator:
    global _hardware_accelerator
    if _hardware_accelerator is None or force_cpu:
        _hardware_accelerator = HardwareAccelerator(force_cpu=force_cpu)
    return _hardware_accelerator


get_accelerator = get_hardware_accelerator
