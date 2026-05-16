"""SwiftDrillTrainer — MS-SWIFT automated training pipeline for LivingTree cells.

Integrates Alibaba ModelScope (魔搭社区) SWIFT framework for:
- LoRA / QLoRA / DoRA / full-parameter fine-tuning
- Knowledge distillation (teacher → student)
- GRPO reinforcement learning alignment
- DPO preference optimization
- Model evaluation via EvalScope (100+ benchmarks)
- Model quantization (AWQ, GPTQ, FP8) and export
- One-click model deployment (vLLM/SGLang)

Usage:
    from livingtree.cell.swift_trainer import SwiftDrillTrainer, DrillConfig
    trainer = SwiftDrillTrainer()
    result = await trainer.train_lora(cell, dataset, config)
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Optional

from loguru import logger
from pydantic import BaseModel, Field

import modelscope
import psutil
import pynvml


@dataclass
class DrillConfig:
    """MS-SWIFT training configuration for cell training."""
    model_name: str = "Qwen/Qwen3.5-4B"
    dataset_name: str = ""
    dataset_path: str = ""
    output_dir: str = "./data/cells/output"
    training_type: str = "lora"

    # Training hyperparams
    epochs: int = 3
    batch_size: int = 8
    learning_rate: float = 2e-5
    warmup_ratio: float = 0.05
    weight_decay: float = 0.01
    max_seq_length: int = 2048
    gradient_accumulation_steps: int = 4
    gradient_checkpointing: bool = True

    # LoRA params
    lora_rank: int = 8
    lora_alpha: int = 16
    lora_dropout: float = 0.05
    lora_target_modules: str = "all-linear"
    use_qlora: bool = False
    use_dora: bool = False

    # Distillation params
    teacher_model: str = ""
    distill_temperature: float = 3.0
    distill_alpha: float = 0.5

    # RL params (GRPO)
    rl_enabled: bool = False
    rl_reward_model: str = ""
    rl_num_generations: int = 8

    # Hardware
    device: str = "auto"
    fp16: bool = True
    deepspeed: str = ""
    num_gpus: int = 1

    # Logging & saving
    logging_steps: int = 10
    save_steps: int = 500
    eval_steps: int = 500
    save_total_limit: int = 3

    # Advanced
    use_flash_attn: bool = True
    packing: bool = False
    neftune_noise_alpha: float = 0.0

    def to_cli_args(self) -> list[str]:
        """Build CLI arguments for `swift sft`."""
        args = ["swift", "sft"]

        args += ["--model", self.model_name]

        if self.dataset_path:
            args += ["--dataset", self.dataset_path]
        elif self.dataset_name:
            args += ["--dataset", self.dataset_name]

        args += ["--output-dir", self.output_dir]

        if self.training_type == "lora":
            args += ["--lora"]
            args += ["--lora-r", str(self.lora_rank)]
            args += ["--lora-alpha", str(self.lora_alpha)]
            if self.lora_target_modules:
                args += ["--lora-target-modules", self.lora_target_modules]
            if self.use_qlora:
                args.append("--quantization-bits 4")
            if self.use_dora:
                args.append("--use-dora")
        elif self.training_type == "full":
            args.append("--full-finetune")
        elif self.training_type == "distill":
            args += ["--distill", "--teacher-model", self.teacher_model or "Qwen/Qwen3.5-14B"]

        if self.rl_enabled:
            args += ["--rlhf-type", "grpo"]
            if self.rl_reward_model:
                args += ["--reward-model", self.rl_reward_model]
            args += ["--num-generations", str(self.rl_num_generations)]

        args += ["--num-epochs", str(self.epochs)]
        args += ["--batch-size", str(self.batch_size)]
        args += ["--learning-rate", str(self.learning_rate)]
        args += ["--max-seq-length", str(self.max_seq_length)]
        args += ["--gradient-accumulation-steps", str(self.gradient_accumulation_steps)]
        args += ["--logging-steps", str(self.logging_steps)]
        args += ["--save-steps", str(self.save_steps)]
        args += ["--eval-steps", str(self.eval_steps)]
        args += ["--save-total-limit", str(self.save_total_limit)]

        if self.warmup_ratio > 0:
            args += ["--warmup-ratio", str(self.warmup_ratio)]
        if self.weight_decay > 0:
            args += ["--weight-decay", str(self.weight_decay)]
        if self.gradient_checkpointing:
            args.append("--gradient-checkpointing")
        if self.fp16:
            args.append("--fp16")
        if self.deepspeed:
            args += ["--deepspeed", self.deepspeed]
        if self.use_flash_attn:
            args.append("--use-flash-attn")
        if self.packing:
            args.append("--packing")
        if self.neftune_noise_alpha > 0:
            args += ["--neftune-noise-alpha", str(self.neftune_noise_alpha)]
        if self.device != "auto":
            args += ["--device", self.device]

        return args


@dataclass
class DrillResult:
    """Training result from SWIFT drill pipeline."""
    success: bool
    model_path: Optional[str] = None
    training_time_seconds: Optional[float] = None
    loss: Optional[float] = None
    eval_loss: Optional[float] = None
    perplexity: Optional[float] = None
    accuracy: Optional[float] = None
    error: Optional[str] = None
    metrics: dict[str, Any] = field(default_factory=dict)
    output_dir: str = ""


class SwiftDrillTrainer:
    """MS-SWIFT automated training pipeline integrated with LivingTree cells.

    Features:
    - CLI-based training (supports all SWIFT features)
    - Python SDK fallback for environments without CLI
    - Automatic dataset preparation from cell training data
    - Model evaluation with EvalScope
    - Model quantization and export
    - Background training scheduler
    - GPU/CPU detection and optimization
    """

    SUPPORTED_MODELS: list[str] = [
        "Qwen/Qwen3.6-35B", "Qwen/Qwen3.6-14B", "Qwen/Qwen3.6-8B",
        "Qwen/Qwen3.5-72B", "Qwen/Qwen3.5-32B", "Qwen/Qwen3.5-14B",
        "Qwen/Qwen3.5-7B", "Qwen/Qwen3.5-4B", "Qwen/Qwen3.5-2B",
        "Qwen/Qwen2.5-7B", "Qwen/Qwen2.5-14B", "Qwen/Qwen2.5-32B",
        "Qwen/Qwen2.5-72B", "Qwen/Qwen2.5-1.5B", "Qwen/Qwen2.5-0.5B",
        "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B",
        "deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B",
    ]

    TRAINING_TYPES: dict[str, str] = {
        "lora": "LoRA fine-tuning",
        "full": "Full-parameter fine-tuning",
        "distill": "Knowledge distillation",
        "sft": "Supervised fine-tuning",
        "dpo": "Direct Preference Optimization",
        "grpo": "Group Relative Policy Optimization",
    }

    def __init__(self, modelscope_token: str = ""):
        self._swift_available = False
        self._modelscope_available = False
        self._checked = False
        self._token = modelscope_token or os.environ.get("MODELSCOPE_TOKEN", "")
        self._progress_callback: Optional[Callable] = None
        self._pending_jobs: list[DrillConfig] = []
        self._is_training = False
        self._system_info: dict[str, Any] = {}

    def _check_environment(self) -> None:
        """Check available training hardware and frameworks."""
        if self._checked:
            return
        self._checked = True

        try:
            result = subprocess.run(["swift", "--version"], capture_output=True, text=True, timeout=10)
            self._swift_available = result.returncode == 0
            if self._swift_available:
                logger.info(f"MS-SWIFT available: {result.stdout.strip()}")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            self._swift_available = False

        self._modelscope_available = True
        logger.info(f"ModelScope SDK available: {modelscope.__version__}")

        self._system_info = self._detect_system()

    def _detect_system(self) -> dict[str, Any]:
        """Detect system hardware for optimal training config."""
        info = {"cpu_count": os.cpu_count() or 1, "gpu_count": 0, "gpu_vram_gb": 0, "ram_gb": 0}
        info["ram_gb"] = round(psutil.virtual_memory().total / (1024**3), 1)

        pynvml.nvmlInit()
        info["gpu_count"] = pynvml.nvmlDeviceGetCount()
        if info["gpu_count"] > 0:
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            info["gpu_vram_gb"] = round(mem.total / (1024**3), 1)
        pynvml.nvmlShutdown()

        logger.info(f"System: {info['cpu_count']} CPUs, {info['gpu_count']} GPUs, {info['ram_gb']}GB RAM, {info['gpu_vram_gb']}GB VRAM")
        return info

    def is_available(self) -> bool:
        self._check_environment()
        return self._swift_available

    def install_swift(self) -> bool:
        """Install MS-SWIFT via pip (using pkg_manager)."""
        try:
            logger.info("Installing MS-SWIFT...")
            from ..integration.pkg_manager import install as pkg_install
            result = pkg_install("ms-swift", providers=["pip"])
            if result.installed:
                logger.info("MS-SWIFT installed successfully")
                self._swift_available = True
                self._checked = True
                return True
            logger.error(f"SWIFT install failed: {result.stderr[:500]}")
            return False
        except subprocess.TimeoutExpired:
            logger.error("SWIFT installation timed out")
            return False

    def on_progress(self, callback: Callable) -> None:
        """Register progress callback(phase, progress_pct, metadata)."""
        self._progress_callback = callback

    async def train_lora(self, cell: Any, dataset: list[dict] | str,
                         config: DrillConfig | None = None) -> DrillResult:
        """LoRA fine-tune a cell with a dataset.

        Args:
            cell: CellAI instance to train
            dataset: List of training samples, or path to dataset file
            config: DrillConfig (auto-generated from cell if None)
        """
        if config is None:
            config = self._auto_config_for_cell(cell, "lora")

        if isinstance(dataset, list):
            dataset_path = self._prepare_dataset(dataset, config.dataset_name or "cell_data")
            config.dataset_path = dataset_path

        return await self._run_drill(config)

    async def train_full(self, cell: Any, dataset: list[dict] | str,
                         config: DrillConfig | None = None) -> DrillResult:
        """Full-parameter fine-tune a cell."""
        if config is None:
            config = self._auto_config_for_cell(cell, "full")
        if isinstance(dataset, list):
            config.dataset_path = self._prepare_dataset(dataset, config.dataset_name or "cell_data")
        return await self._run_drill(config)

    async def distill(self, student_cell: Any, teacher_model: str,
                      dataset: list[dict] | str,
                      config: DrillConfig | None = None) -> DrillResult:
        """Knowledge distillation from teacher to student cell.

        Args:
            student_cell: Target CellAI
            teacher_model: Expert model name (e.g. "Qwen/Qwen3.5-14B")
            dataset: Training dataset or path
        """
        if config is None:
            config = self._auto_config_for_cell(student_cell, "distill")
        config.training_type = "distill"
        config.teacher_model = teacher_model

        if isinstance(dataset, list):
            config.dataset_path = self._prepare_dataset(dataset, config.dataset_name or "distill_data")

        return await self._run_drill(config)

    async def train_grpo(self, cell: Any, dataset: list[dict] | str,
                         reward_model: str = "",
                         config: DrillConfig | None = None) -> DrillResult:
        """GRPO reinforcement learning alignment training."""
        if config is None:
            config = self._auto_config_for_cell(cell, "lora")
        config.rl_enabled = True
        if reward_model:
            config.rl_reward_model = reward_model

        if isinstance(dataset, list):
            config.dataset_path = self._prepare_dataset(dataset, config.dataset_name or "rl_data")

        return await self._run_drill(config)

    async def evaluate(self, model_path: str,
                       benchmarks: list[str] | None = None) -> dict[str, Any]:
        """Evaluate a trained model using EvalScope benchmarks.

        Args:
            model_path: Path to trained model
            benchmarks: List of benchmark names (default: ["ceval", "mmlu"])

        Returns:
            Evaluation metrics dictionary
        """
        self._check_environment()
        if not self._swift_available:
            return {"error": "MS-SWIFT not available"}

        benchmarks = benchmarks or ["ceval", "mmlu"]
        cmd = ["swift", "eval", "--model", model_path, "--eval-dataset"] + benchmarks

        try:
            result = await asyncio.to_thread(subprocess.run, cmd, capture_output=True, text=True, timeout=3600)
            if result.returncode == 0:
                return self._parse_eval_results(result.stdout)
            return {"error": result.stderr[:500]}
        except subprocess.TimeoutExpired:
            return {"error": "Evaluation timed out"}
        except Exception as e:
            return {"error": str(e)}

    async def quantize(self, model_path: str, method: str = "awq",
                       output_dir: str = "") -> DrillResult:
        """Quantize a trained model for deployment.

        Args:
            model_path: Path to trained model
            method: "awq", "gptq", "bnb"
            output_dir: Output directory
        """
        self._check_environment()
        if not self._swift_available:
            return DrillResult(success=False, error="MS-SWIFT not available")

        output = output_dir or f"{model_path}-{method}"
        cmd = ["swift", "export", "--model", model_path, "--output-dir", output,
               "--quant-method", method]

        try:
            result = await asyncio.to_thread(subprocess.run, cmd, capture_output=True, text=True, timeout=3600)
            if result.returncode == 0:
                return DrillResult(success=True, model_path=output, output_dir=output)
            return DrillResult(success=False, error=result.stderr[:500])
        except Exception as e:
            return DrillResult(success=False, error=str(e))

    async def deploy(self, model_path: str, port: int = 8000,
                     engine: str = "vllm") -> dict[str, Any]:
        """Deploy trained model as OpenAI-compatible API server.

        Args:
            model_path: Path to model
            port: API port
            engine: "vllm", "sglang", "lmdeploy"
        """
        self._check_environment()
        if not self._swift_available:
            return {"error": "MS-SWIFT not available"}

        cmd = ["swift", "deploy", "--model", model_path, "--port", str(port)]
        if engine != "vllm":
            cmd += ["--infer-backend", engine]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            return {"status": "deploying", "port": port, "pid": process.pid, "engine": engine}
        except Exception as e:
            return {"error": str(e)}

    def schedule_training(self, config: DrillConfig) -> bool:
        """Queue a training job for idle-time execution."""
        self._check_environment()
        if not self._swift_available:
            logger.warning("MS-SWIFT not available, training queued")
            self._pending_jobs.append(config)
            return True

        if not self._is_system_idle():
            logger.info("System busy, queuing training job")
            self._pending_jobs.append(config)
            return True

        asyncio.create_task(self._execute_scheduled(config))
        return True

    def get_queue(self) -> list[DrillConfig]:
        return list(self._pending_jobs)

    def is_training(self) -> bool:
        return self._is_training

    async def download_model(self, model_id: str, destination: str = "") -> str:
        """Download a model from ModelScope hub."""
        self._check_environment()
        dest = destination or f"./data/models/{model_id.replace('/', '_')}"

        if self._modelscope_available:
            try:
                from modelscope.hub.api import HubApi
                api = HubApi()
                path = await asyncio.to_thread(api.download, model_id=model_id)
                logger.info(f"Downloaded {model_id} to {path}")
                return str(path)
            except Exception as e:
                logger.warning(f"ModelScope SDK download failed: {e}")

        # Fallback: use swift CLI
        if self._swift_available:
            try:
                cmd = ["swift", "download", "--model", model_id, "--output-dir", dest]
                await asyncio.to_thread(subprocess.run, cmd, capture_output=True, text=True, timeout=600)
                return dest
            except Exception as e:
                logger.error(f"SWIFT download failed: {e}")

        return ""

    # ── Internal ──

    async def _run_drill(self, config: DrillConfig) -> DrillResult:
        """Execute a SWIFT training drill."""
        self._check_environment()
        if not self._swift_available:
            return DrillResult(success=False, error="MS-SWIFT not installed. Run: pip install ms-swift -U")

        Path(config.output_dir).mkdir(parents=True, exist_ok=True)
        cmd = config.to_cli_args()

        logger.info(f"SWIFT drill start: {config.model_name} ({config.training_type})")
        logger.info(f"Command: {' '.join(cmd[:10])}...")

        t0 = time.time()
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout_lines: list[str] = []
            async for line in process.stdout:
                text = line.decode("utf-8", errors="replace").strip()
                if text:
                    stdout_lines.append(text)
                    self._parse_progress(text, config)

            await process.wait()
            stdout = "\n".join(stdout_lines)
            stderr = (await process.stderr.read()).decode("utf-8", errors="replace")

            elapsed = time.time() - t0

            if process.returncode == 0:
                result = self._parse_drill_result(stdout, config.output_dir)
                result.training_time_seconds = elapsed
                result.success = True
                logger.info(f"SWIFT drill complete: {elapsed:.0f}s, loss={result.loss}")
                return result

            return DrillResult(success=False, error=stderr[:1000], output_dir=config.output_dir)

        except asyncio.CancelledError:
            logger.warning("Training was cancelled")
            return DrillResult(success=False, error="Cancelled", output_dir=config.output_dir)
        except Exception as e:
            logger.error(f"SWIFT drill exception: {e}")
            return DrillResult(success=False, error=str(e), output_dir=config.output_dir)

    async def _execute_scheduled(self, config: DrillConfig) -> None:
        """Execute a queued training job."""
        self._is_training = True
        try:
            logger.info(f"Starting scheduled training: {config.model_name}")
            result = await self._run_drill(config)
            if result.success:
                logger.info(f"Scheduled training complete: {result.model_path}")
            else:
                logger.error(f"Scheduled training failed: {result.error}")
        finally:
            self._is_training = False
            if self._pending_jobs:
                next_job = self._pending_jobs.pop(0)
                asyncio.create_task(self._execute_scheduled(next_job))

    def _prepare_dataset(self, data: list[dict], name: str) -> str:
        """Convert training data to SWIFT-compatible JSONL format."""
        tmp_dir = Path(tempfile.gettempdir()) / "livingtree_datasets"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        path = tmp_dir / f"{name}_{int(time.time())}.jsonl"

        with open(path, "w", encoding="utf-8") as f:
            for item in data:
                if "instruction" in item and "output" in item:
                    entry = {"query": item["instruction"], "response": item["output"]}
                elif "input" in item and "output" in item:
                    entry = {"query": item["input"], "response": item["output"]}
                elif "prompt" in item and "completion" in item:
                    entry = {"query": item["prompt"], "response": item["completion"]}
                elif "text" in item:
                    entry = {"query": item["text"][:200], "response": item["text"]}
                else:
                    entry = {"query": json.dumps(item, ensure_ascii=False), "response": "acknowledged"}
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        logger.info(f"Prepared dataset: {path} ({len(data)} samples)")
        return str(path)

    def _auto_config_for_cell(self, cell: Any, training_type: str) -> DrillConfig:
        """Generate optimal DrillConfig based on cell and system."""
        info = self._system_info
        config = DrillConfig(
            model_name=getattr(cell, "model_name", "Qwen/Qwen3.5-4B"),
            output_dir=str(getattr(cell, "checkpoint_dir", Path("./data/cells/output"))),
            training_type=training_type,
        )

        # Auto-optimize based on hardware
        if info.get("gpu_vram_gb", 0) >= 24:
            config.batch_size = 16
            config.lora_rank = 16
            config.use_flash_attn = True
        elif info.get("gpu_vram_gb", 0) >= 8:
            config.batch_size = 8
            config.use_qlora = True
        else:
            config.batch_size = 4
            config.use_qlora = True
            config.max_seq_length = 1024

        if info.get("gpu_count", 0) >= 2:
            config.deepspeed = "zero2"

        return config

    def _parse_progress(self, line: str, config: DrillConfig) -> None:
        """Parse progress from SWIFT output and notify callback."""
        if not self._progress_callback:
            return

        # Parse step/epoch from training logs
        step_match = re.search(r"step.*?(\d+)/(\d+)", line)
        loss_match = re.search(r"loss[=:]\s*([\d.]+)", line)

        progress = 0.0
        metadata: dict[str, Any] = {}

        if step_match:
            progress = float(step_match.group(1)) / max(float(step_match.group(2)), 1) * 100
        if loss_match:
            metadata["loss"] = float(loss_match.group(1))

        try:
            self._progress_callback("training", progress, metadata)
        except Exception:
            pass

    def _parse_drill_result(self, output: str, output_dir: str) -> DrillResult:
        """Parse training results from SWIFT output."""
        result = DrillResult(success=True, output_dir=output_dir)

        # Find checkpoint dir
        checkpoint_dirs = sorted(Path(output_dir).glob("checkpoint-*"), key=lambda p: int(p.name.split("-")[1]) if p.name.split("-")[1].isdigit() else 0)
        if checkpoint_dirs:
            result.model_path = str(checkpoint_dirs[-1])
        else:
            result.model_path = output_dir

        # Parse metrics
        for pattern_name, pattern in [
            ("loss", r"loss[=:]\s*([\d.]+)"),
            ("eval_loss", r"eval.*?loss[=:]\s*([\d.]+)"),
            ("perplexity", r"ppl[=:]\s*([\d.]+)"),
            ("accuracy", r"acc(?:uracy)?[=:]\s*([\d.]+)"),
            ("f1", r"f1[=:]\s*([\d.]+)"),
        ]:
            match = re.findall(pattern, output, re.IGNORECASE)
            if match:
                val = float(match[-1])
                result.metrics[pattern_name] = val
                if pattern_name == "loss":
                    result.loss = val
                elif pattern_name == "eval_loss":
                    result.eval_loss = val
                elif pattern_name == "perplexity":
                    result.perplexity = val
                elif pattern_name == "accuracy":
                    result.accuracy = val

        return result

    def _parse_eval_results(self, output: str) -> dict[str, Any]:
        """Parse evaluation results from EvalScope output."""
        results: dict[str, Any] = {}
        for line in output.splitlines():
            for metric in ["accuracy", "f1", "bleu", "rouge", "pass@1"]:
                match = re.search(rf"{metric}.*?:\s*([\d.]+)", line, re.IGNORECASE)
                if match:
                    results.setdefault(metric, []).append(float(match.group(1)))
        return {k: sum(v) / len(v) for k, v in results.items()} if results else {"raw": output[:500]}

    def _is_system_idle(self) -> bool:
        """Check if system resources are free enough for training."""
        if psutil.cpu_percent() > 30:
            return False
        if psutil.virtual_memory().percent > 50:
            return False

        pynvml.nvmlInit()
        for i in range(pynvml.nvmlDeviceGetCount()):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            if (mem.used / mem.total) > 0.2:
                pynvml.nvmlShutdown()
                return False
        pynvml.nvmlShutdown()
        return True

    @staticmethod
    def neftune_annealing_schedule(step: int, max_steps: int = 100,
                                   alpha_max: float = 5.0,
                                   t_init: float = 1.0) -> dict:
        import math as _math
        progress = step / max(max_steps, 1)
        T = t_init / _math.log(_math.e + step)
        alpha = alpha_max * max(0.01, 1.0 - progress) * (T + 0.1)
        return {"alpha": alpha, "temperature": T, "progress": progress,
                "step": step, "cooling_phase": "early" if progress < 0.3 else ("mid" if progress < 0.7 else "late")}

    def convergence_tracker(self, losses: list[float], patience: int = 5,
                            epsilon: float = 1e-4) -> dict:
        if len(losses) < patience + 1:
            return {"converged": False, "reason": "insufficient_data", "loss_std": 0.0}
        recent = losses[-patience:]
        loss_std = sum((l - sum(recent)/len(recent))**2 for l in recent) / len(recent)
        converged = loss_std < epsilon
        trend = "decreasing" if len(losses) >= 2 and losses[-1] < losses[-2] else "flat_or_increasing"
        return {"converged": converged, "loss_std": loss_std, "trend": trend,
                "status": "convergent" if converged else "still_optimizing"}
