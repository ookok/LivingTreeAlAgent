"""
AI能力检测与算力注册中心 (AI Capability Detector & Registry)
==============================================================

为 DeCommerce 去中心化电商系统提供本地 AI 算力检测、匹配和注册功能。

核心功能:
- 本地硬件自动检测 (CPU/RAM/GPU)
- AI模型兼容性评估
- 算力服务注册与发现
- 为卖家提供硬件背书报告
- 为买家提供决策辅助

使用方法:
    from core.ai_capability_detector import (
        AICapabilityRegistry,
        get_ai_capability_registry,
        get_local_capability,
        can_run_model,
    )

作者: Hermes Desktop Team
"""

from core.logger import get_logger
logger = get_logger('ai_capability_detector')

import json
import sqlite3
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass, asdict, field
from enum import Enum
import asyncio
import aiohttp

try:
    from core.config.unified_config import get_config as _get_unified_config
    _uconfig_ai = _get_unified_config()
except Exception:
    _uconfig_ai = None

def _ai_get(key: str, default):
    return _uconfig_ai.get(key, default) if _uconfig_ai else default

# =============================================================================
# 数据模型
# =============================================================================

class ModelType(Enum):
    """AI模型类型"""
    TEXT_LLM = "text_llm"
    EMBEDDING = "embedding"
    VISION = "vision"
    MULTIMODAL = "multimodal"
    TTS = "tts"
    STT = "stt"
    API_ONLY = "api_only"  # 仅API调用,不本地运行


class ModelCompatibility(Enum):
    """模型兼容性等级"""
    EXCELLENT = "excellent"   # 完全支持,流畅运行
    GOOD = "good"           # 支持,可能有轻微延迟
    MODERATE = "moderate"   # 可运行,但较慢
    SLOW = "slow"           # CPU降级运行,很慢
    API_ONLY = "api_only"   # 只能通过API调用
    UNSUPPORTED = "unsupported"  # 无法运行


@dataclass
class ModelSpec:
    """AI模型规格"""
    name: str
    provider: str
    params: str  # 参数量, 如 "7B", "13B", "1.5T"
    vram_required_gb: float  # 最低VRAM需求
    ram_required_gb: float   # 最低系统内存需求
    model_type: ModelType
    compatibility: ModelCompatibility = ModelCompatibility.UNSUPPORTED
    estimated_speed: int = 0  # tokens/sec 预估
    recommended: bool = False
    quantization_options: List[str] = field(default_factory=lambda: ["FP16", "INT8", "INT4"])
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "provider": self.provider,
            "params": self.params,
            "vram_required_gb": self.vram_required_gb,
            "ram_required_gb": self.ram_required_gb,
            "model_type": self.model_type.value,
            "compatibility": self.compatibility.value,
            "estimated_speed": self.estimated_speed,
            "recommended": self.recommended,
            "quantization_options": self.quantization_options,
            "notes": self.notes
        }


@dataclass
class HardwareSpec:
    """硬件规格"""
    cpu_cores: int = 0
    cpu_threads: int = 0
    cpu_model: str = "Unknown"
    cpu_arch: str = "x64"
    ram_total_gb: float = 0.0
    ram_available_gb: float = 0.0
    ram_type: str = "Unknown"
    gpu_renderer: str = "Unknown"
    gpu_vram_gb: float = 0.0
    gpu_vendor: str = "Unknown"
    has_webgl: bool = False
    has_gpu: bool = False
    os_platform: str = "Windows"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HardwareSpec":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def get_profile_hash(self) -> str:
        """生成硬件配置哈希"""
        key = f"{self.cpu_model}:{self.ram_total_gb}:{self.gpu_renderer}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]


@dataclass
class CapabilityProfile:
    """算力能力画像"""
    hardware: HardwareSpec
    compatible_models: List[ModelSpec]
    best_model: Optional[ModelSpec] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    profile_hash: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hardware": self.hardware.to_dict(),
            "compatible_models": [m.to_dict() for m in self.compatible_models],
            "best_model": self.best_model.to_dict() if self.best_model else None,
            "timestamp": self.timestamp,
            "profile_hash": self.profile_hash
        }

    def generate_report(self) -> str:
        """生成硬件认证报告"""
        hw = self.hardware
        best = self.best_model

        report_lines = [
            "=" * 50,
            "AI算力认证报告",
            "=" * 50,
            f"检测时间: {self.timestamp}",
            "",
            "【硬件配置】",
            f"  CPU: {hw.cpu_model} ({hw.cpu_cores}核/{hw.cpu_threads}线程)",
            f"  内存: {hw.ram_total_gb}GB {hw.ram_type}",
            f"  GPU: {hw.gpu_renderer}",
            f"  VRAM: {hw.gpu_vram_gb}GB",
            f"  平台: {hw.os_platform}",
            "",
            "【推荐模型】",
        ]

        if best:
            report_lines.extend([
                f"  模型: {best.name}",
                f"  参数量: {best.params}",
                f"  预估速度: {best.estimated_speed} tokens/sec",
                f"  VRAM需求: {best.vram_required_gb}GB",
                f"  推荐量化: {', '.join(best.quantization_options[:2])}",
            ])
        else:
            report_lines.append("  暂无本地运行推荐,请使用API模式")

        report_lines.extend([
            "",
            "【兼容模型列表】",
        ])

        # 按速度排序显示前10个
        sorted_models = sorted(
            [m for m in self.compatible_models if m.compatibility != ModelCompatibility.API_ONLY],
            key=lambda x: x.estimated_speed,
            reverse=True
        )[:10]

        for i, model in enumerate(sorted_models, 1):
            compat_emoji = {
                ModelCompatibility.EXCELLENT: "[推荐]",
                ModelCompatibility.GOOD: "[良好]",
                ModelCompatibility.MODERATE: "[一般]",
                ModelCompatibility.SLOW: "[较慢]",
            }.get(model.compatibility, "")
            report_lines.append(
                f"  {i}. {model.name} {compat_emoji} "
                f"({model.estimated_speed} tok/s, {model.vram_required_gb}GB VRAM)"
            )

        report_lines.extend([
            "",
            "=" * 50,
            "认证指纹: " + self.profile_hash,
            "=" * 50,
        ])

        return "\n".join(report_lines)


# =============================================================================
# AI模型数据库
# =============================================================================

# 内置AI模型列表 (21+ 主流开源模型)
BUILTIN_MODELS: List[ModelSpec] = [
    # Llama系列
    ModelSpec(
        name="Llama-2-7B",
        provider="Meta",
        params="7B",
        vram_required_gb=6,
        ram_required_gb=8,
        model_type=ModelType.TEXT_LLM,
        quantization_options=["FP16", "INT8", "INT4"],
        notes="开源LLaMA 7B基础模型"
    ),
    ModelSpec(
        name="Llama-2-13B",
        provider="Meta",
        params="13B",
        vram_required_gb=12,
        ram_required_gb=16,
        model_type=ModelType.TEXT_LLM,
        quantization_options=["INT8", "INT4"],
        notes="中参数规模,效果较好"
    ),
    ModelSpec(
        name="Llama-2-70B",
        provider="Meta",
        params="70B",
        vram_required_gb=48,
        ram_required_gb=64,
        model_type=ModelType.TEXT_LLM,
        quantization_options=["INT4", "QLoRA"],
        notes="需要多卡或量化"
    ),

    # Mistral系列
    ModelSpec(
        name="Mistral-7B",
        provider="Mistral AI",
        params="7B",
        vram_required_gb=6,
        ram_required_gb=8,
        model_type=ModelType.TEXT_LLM,
        quantization_options=["FP16", "INT8", "INT4"],
        notes="效率与效果兼顾"
    ),
    ModelSpec(
        name="Mixtral-8x7B",
        provider="Mistral AI",
        params="8x7B",
        vram_required_gb=24,
        ram_required_gb=32,
        model_type=ModelType.TEXT_LLM,
        quantization_options=["INT8", "INT4"],
        notes="MoE架构,需多卡"
    ),

    # Qwen系列
    ModelSpec(
        name="Qwen-1.5-7B",
        provider="Alibaba",
        params="7B",
        vram_required_gb=6,
        ram_required_gb=8,
        model_type=ModelType.TEXT_LLM,
        quantization_options=["FP16", "INT8", "INT4"],
        notes="中文优化效果好"
    ),
    ModelSpec(
        name="Qwen-1.5-14B",
        provider="Alibaba",
        params="14B",
        vram_required_gb=14,
        ram_required_gb=16,
        model_type=ModelType.TEXT_LLM,
        quantization_options=["INT8", "INT4"],
        notes="中文能力增强"
    ),
    ModelSpec(
        name="Qwen-1.5-72B",
        provider="Alibaba",
        params="72B",
        vram_required_gb=48,
        ram_required_gb=64,
        model_type=ModelType.TEXT_LLM,
        quantization_options=["INT4", "QLoRA"],
        notes="千亿参数级,中文最强"
    ),
    ModelSpec(
        name="Qwen-2.5-7B",
        provider="Alibaba",
        params="7B",
        vram_required_gb=6,
        ram_required_gb=8,
        model_type=ModelType.TEXT_LLM,
        quantization_options=["FP16", "INT8", "INT4"],
        notes="最新版本,性能提升"
    ),

    # ChatGLM系列
    ModelSpec(
        name="ChatGLM2-6B",
        provider="Zhipu AI",
        params="6B",
        vram_required_gb=5,
        ram_required_gb=8,
        model_type=ModelType.TEXT_LLM,
        quantization_options=["FP16", "INT8", "INT4"],
        notes="中文对话优化"
    ),
    ModelSpec(
        name="ChatGLM3-6B",
        provider="Zhipu AI",
        params="6B",
        vram_required_gb=5,
        ram_required_gb=8,
        model_type=ModelType.TEXT_LLM,
        quantization_options=["FP16", "INT8", "INT4"],
        notes="第三代,工具调用增强"
    ),

    # Baichuan系列
    ModelSpec(
        name="Baichuan2-7B",
        provider="Baichuan AI",
        params="7B",
        vram_required_gb=6,
        ram_required_gb=8,
        model_type=ModelType.TEXT_LLM,
        quantization_options=["FP16", "INT8", "INT4"],
        notes="中英双语优化"
    ),
    ModelSpec(
        name="Baichuan2-13B",
        provider="Baichuan AI",
        params="13B",
        vram_required_gb=12,
        ram_required_gb=16,
        model_type=ModelType.TEXT_LLM,
        quantization_options=["INT8", "INT4"],
        notes="长上下文支持"
    ),

    # Yi系列
    ModelSpec(
        name="Yi-6B",
        provider="01.AI",
        params="6B",
        vram_required_gb=6,
        ram_required_gb=8,
        model_type=ModelType.TEXT_LLM,
        quantization_options=["FP16", "INT8", "INT4"],
        notes="双语训练,长上下文"
    ),
    ModelSpec(
        name="Yi-34B",
        provider="01.AI",
        params="34B",
        vram_required_gb=24,
        ram_required_gb=32,
        model_type=ModelType.TEXT_LLM,
        quantization_options=["INT8", "INT4"],
        notes="开源最强长上下文"
    ),

    # DeepSeek系列
    ModelSpec(
        name="DeepSeek-7B",
        provider="DeepSeek",
        params="7B",
        vram_required_gb=6,
        ram_required_gb=8,
        model_type=ModelType.TEXT_LLM,
        quantization_options=["FP16", "INT8", "INT4"],
        notes="代码能力优化"
    ),
    ModelSpec(
        name="DeepSeek-33B",
        provider="DeepSeek",
        params="33B",
        vram_required_gb=24,
        ram_required_gb=32,
        model_type=ModelType.TEXT_LLM,
        quantization_options=["INT8", "INT4"],
        notes="代码与数学能力突出"
    ),

    # Falcon系列
    ModelSpec(
        name="Falcon-7B",
        provider="TII",
        params="7B",
        vram_required_gb=6,
        ram_required_gb=8,
        model_type=ModelType.TEXT_LLM,
        quantization_options=["FP16", "INT8", "INT4"],
        notes="阿联酋开源最强7B"
    ),
    ModelSpec(
        name="Falcon-40B",
        provider="TII",
        params="40B",
        vram_required_gb=32,
        ram_required_gb=48,
        model_type=ModelType.TEXT_LLM,
        quantization_options=["INT4", "QLoRA"],
        notes="需量化才能单卡运行"
    ),

    # Vicuna系列
    ModelSpec(
        name="Vicuna-7B",
        provider="LMSYS",
        params="7B",
        vram_required_gb=6,
        ram_required_gb=8,
        model_type=ModelType.TEXT_LLM,
        quantization_options=["FP16", "INT8", "INT4"],
        notes="ChatGPT蒸馏,对话流畅"
    ),
    ModelSpec(
        name="Vicuna-13B",
        provider="LMSYS",
        params="13B",
        vram_required_gb=12,
        ram_required_gb=16,
        model_type=ModelType.TEXT_LLM,
        quantization_options=["INT8", "INT4"],
        notes="对话质量更高"
    ),

    # Embedding模型
    ModelSpec(
        name="text-embedding-ada-002",
        provider="OpenAI",
        params="N/A",
        vram_required_gb=0,
        ram_required_gb=4,
        model_type=ModelType.EMBEDDING,
        notes="OpenAI官方Embedding"
    ),
    ModelSpec(
        name="bge-large-zh",
        provider="BAAI",
        params="335M",
        vram_required_gb=1,
        ram_required_gb=4,
        model_type=ModelType.EMBEDDING,
        quantization_options=["FP16", "INT8"],
        notes="中文最优Embedding"
    ),

    # API Only模型
    ModelSpec(
        name="GPT-4",
        provider="OpenAI",
        params="~1T",
        vram_required_gb=0,
        ram_required_gb=0,
        model_type=ModelType.API_ONLY,
        compatibility=ModelCompatibility.API_ONLY,
        notes="需API调用"
    ),
    ModelSpec(
        name="GPT-3.5-Turbo",
        provider="OpenAI",
        params="~20B",
        vram_required_gb=0,
        ram_required_gb=0,
        model_type=ModelType.API_ONLY,
        compatibility=ModelCompatibility.API_ONLY,
        notes="需API调用"
    ),
    ModelSpec(
        name="GPT-4o",
        provider="OpenAI",
        params="~200B",
        vram_required_gb=0,
        ram_required_gb=0,
        model_type=ModelType.MULTIMODAL,
        compatibility=ModelCompatibility.API_ONLY,
        notes="多模态API模型"
    ),
    ModelSpec(
        name="Claude-3.5-Sonnet",
        provider="Anthropic",
        params="N/A",
        vram_required_gb=0,
        ram_required_gb=0,
        model_type=ModelType.API_ONLY,
        compatibility=ModelCompatibility.API_ONLY,
        notes="需API调用"
    ),
]


# =============================================================================
# 核心检测器
# =============================================================================

class AICapabilityDetector:
    """AI能力检测器"""

    def __init__(self):
        self._models = BUILTIN_MODELS.copy()
        self._current_profile: Optional[CapabilityProfile] = None

    def detect_hardware(self, override_specs: Optional[Dict[str, Any]] = None) -> HardwareSpec:
        """
        检测本地硬件配置

        Args:
            override_specs: 可选的硬件规格覆盖值

        Returns:
            HardwareSpec: 硬件规格对象
        """
        import platform
        import psutil

        # 基础检测
        cpu_count = psutil.cpu_count(logical=True) or 4
        cpu_cores = psutil.cpu_count(logical=False) or cpu_count // 2
        ram_total = psutil.virtual_memory().total / (1024**3)  # GB
        ram_available = psutil.virtual_memory().available / (1024**3)

        hw = HardwareSpec(
            cpu_cores=cpu_cores,
            cpu_threads=cpu_count,
            cpu_model=self._detect_cpu_model(),
            cpu_arch=platform.machine(),
            ram_total_gb=round(ram_total, 1),
            ram_available_gb=round(ram_available, 1),
            ram_type=self._detect_ram_type(),
            os_platform=platform.system()
        )

        # GPU检测 (简化版,需要pygpu或pynvml)
        gpu_info = self._detect_gpu()
        hw.gpu_renderer = gpu_info.get("renderer", "Unknown")
        hw.gpu_vram_gb = gpu_info.get("vram_gb", 0)
        hw.gpu_vendor = gpu_info.get("vendor", "Unknown")
        hw.has_gpu = gpu_info.get("has_gpu", False)

        # 应用覆盖值
        if override_specs:
            for key, value in override_specs.items():
                if hasattr(hw, key) and value is not None:
                    setattr(hw, key, value)

        return hw

    def _detect_cpu_model(self) -> str:
        """检测CPU型号"""
        try:
            import subprocess
            if platform.system() == "Windows":
                result = subprocess.run(
                    ["wmic", "cpu", "get", "name"],
                    capture_output=True,
                    text=True,
                    timeout=_ai_get("timeouts.quick", 5)
                )
                lines = result.stdout.strip().split("\n")
                if len(lines) > 1:
                    return lines[1].strip()
            elif platform.system() == "Linux":
                with open("/proc/cpuinfo", "r") as f:
                    for line in f:
                        if line.startswith("model name"):
                            return line.split(":")[1].strip()
        except Exception:
            pass
        return f"CPU ({platform.processor() or 'Unknown'})"

    def _detect_ram_type(self) -> str:
        """检测内存类型"""
        try:
            import subprocess
            if platform.system() == "Windows":
                result = subprocess.run(
                    ["wmic", "memorychip", "get", "SMBIOSMemoryType"],
                    capture_output=True,
                    text=True,
                    timeout=_ai_get("timeouts.quick", 5)
                )
                lines = result.stdout.strip().split("\n")
                if len(lines) > 1:
                    mem_type = int(lines[1].strip()) if lines[1].strip().isdigit() else 0
                    type_map = {20: "DDR", 21: "DDR2", 24: "DDR3", 26: "DDR4", 34: "DDR5"}
                    return type_map.get(mem_type, "DDR4")
        except Exception:
            pass
        return "DDR4"  # 默认值

    def _detect_gpu(self) -> Dict[str, Any]:
        """检测GPU信息"""
        result = {
            "renderer": "Unknown",
            "vram_gb": 0,
            "vendor": "Unknown",
            "has_gpu": False
        }

        try:
            # 尝试使用pygpu
            import pygpu
            result["renderer"] = pygpu.renderer.get_renderer()
            result["vram_gb"] = pygpu.device.get_memory() / (1024**3)
            result["has_gpu"] = True
        except ImportError:
            # 尝试pynvml (NVIDIA)
            try:
                import pynvml

                pynvml.nvmlInit()
                handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                name = pynvml.nvmlDeviceGetName(handle)
                mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                result["renderer"] = name or "NVIDIA GPU"
                result["vram_gb"] = round(mem_info.total / (1024**3), 1)
                result["vendor"] = "NVIDIA"
                result["has_gpu"] = True
                pynvml.nvmlShutdown()
            except ImportError:
                # 降级: 基于系统信息估算
                pass

        return result

    def match_models(
        self,
        hardware: HardwareSpec,
        min_compatibility: ModelCompatibility = ModelCompatibility.SLOW
    ) -> List[ModelSpec]:
        """
        匹配兼容的AI模型

        Args:
            hardware: 硬件规格
            min_compatibility: 最低兼容性要求

        Returns:
            排序后的兼容模型列表
        """
        matched = []

        for model in self._models:
            compat, speed = self._evaluate_compatibility(hardware, model)
            model.compatibility = compat
            model.estimated_speed = speed

            # 只添加达到最低要求的模型
            if self._compatibility_rank(compat) >= self._compatibility_rank(min_compatibility):
                matched.append(model)

        # 按兼容性和速度排序
        matched.sort(
            key=lambda m: (self._compatibility_rank(m.compatibility), m.estimated_speed),
            reverse=True
        )

        # 标记推荐模型
        if matched:
            # 找第一个非API的
            for m in matched:
                if m.compatibility != ModelCompatibility.API_ONLY and m.estimated_speed > 0:
                    m.recommended = True
                    break

        return matched

    def _evaluate_compatibility(
        self,
        hardware: HardwareSpec,
        model: ModelSpec
    ) -> Tuple[ModelCompatibility, int]:
        """评估模型在给定硬件上的兼容性"""
        # API Only模型
        if model.model_type == ModelType.API_ONLY:
            return ModelCompatibility.API_ONLY, 999

        # 检查内存
        if hardware.ram_total_gb < model.ram_required_gb:
            return ModelCompatibility.UNSUPPORTED, 0

        # 检查VRAM
        if model.vram_required_gb > 0:
            if not hardware.has_gpu:
                # 无GPU,只能CPU运行小模型
                if model.vram_required_gb <= 6:
                    # CPU估算速度
                    speed = hardware.cpu_cores * 2
                    if speed < 5:
                        return ModelCompatibility.SLOW, speed
                    return ModelCompatibility.MODERATE, speed
                return ModelCompatibility.UNSUPPORTED, 0

            if hardware.gpu_vram_gb < model.vram_required_gb:
                # VRAM不足
                if hardware.cpu_cores >= 8 and model.vram_required_gb <= 6:
                    return ModelCompatibility.SLOW, 3
                return ModelCompatibility.UNSUPPORTED, 0

        # GPU加速运行
        base_speed = self._estimate_gpu_speed(hardware, model)

        # 确定兼容性等级
        if base_speed >= 35:
            return ModelCompatibility.EXCELLENT, base_speed
        elif base_speed >= 20:
            return ModelCompatibility.GOOD, base_speed
        elif base_speed >= 10:
            return ModelCompatibility.MODERATE, base_speed
        else:
            return ModelCompatibility.SLOW, base_speed

    def _estimate_gpu_speed(self, hardware: HardwareSpec, model: ModelSpec) -> int:
        """估算GPU运行速度"""
        vram = hardware.gpu_vram_gb
        vram_req = model.vram_required_gb

        if model.vram_required_gb <= 0:
            return 50  # 无VRAM需求

        if vram < vram_req:
            return 2  # VRAM不足

        # 基础速度 (假设RTX 3080 10GB = 45 tok/s)
        if vram_req <= 6:
            base = 45
            # 根据VRAM调整
            extra_vram = max(0, vram - vram_req)
            return base + int(extra_vram * 3)
        elif vram_req <= 12:
            base = 35
            extra_vram = max(0, vram - vram_req)
            return base + int(extra_vram * 2)
        elif vram_req <= 24:
            base = 25
            extra_vram = max(0, vram - vram_req)
            return base + int(extra_vram * 1)
        else:
            base = 15
            extra_vram = max(0, vram - vram_req)
            return base + extra_vram

    def _compatibility_rank(self, compat: ModelCompatibility) -> int:
        """兼容性等级排序值"""
        ranks = {
            ModelCompatibility.EXCELLENT: 5,
            ModelCompatibility.GOOD: 4,
            ModelCompatibility.MODERATE: 3,
            ModelCompatibility.SLOW: 2,
            ModelCompatibility.API_ONLY: 1,
            ModelCompatibility.UNSUPPORTED: 0,
        }
        return ranks.get(compat, 0)

    def create_profile(
        self,
        hardware: Optional[HardwareSpec] = None,
        override_specs: Optional[Dict[str, Any]] = None
    ) -> CapabilityProfile:
        """
        创建完整的算力能力画像

        Args:
            hardware: 可选的硬件规格(若不提供则自动检测)
            override_specs: 可选的覆盖值

        Returns:
            CapabilityProfile: 完整的能力画像
        """
        if hardware is None:
            hardware = self.detect_hardware(override_specs)
        else:
            # 应用覆盖值
            if override_specs:
                for key, value in override_specs.items():
                    if hasattr(hardware, key) and value is not None:
                        setattr(hardware, key, value)

        # 匹配模型
        compatible_models = self.match_models(hardware)
        best_model = next((m for m in compatible_models if m.recommended), None)

        # 创建画像
        profile = CapabilityProfile(
            hardware=hardware,
            compatible_models=compatible_models,
            best_model=best_model,
            profile_hash=hardware.get_profile_hash()
        )

        self._current_profile = profile
        return profile

    def can_run(self, model_name: str, profile: Optional[CapabilityProfile] = None) -> bool:
        """检查当前硬件是否能运行指定模型"""
        if profile is None:
            profile = self._current_profile
        if profile is None:
            profile = self.create_profile()

        for model in profile.compatible_models:
            if model.name == model_name:
                return model.compatibility != ModelCompatibility.UNSUPPORTED
        return False

    def get_model_info(self, model_name: str) -> Optional[ModelSpec]:
        """获取模型信息"""
        for model in self._models:
            if model.name == model_name:
                return model
        return None

    def list_models(
        self,
        model_type: Optional[ModelType] = None,
        has_local: bool = True
    ) -> List[ModelSpec]:
        """列出模型"""
        result = self._models

        if model_type:
            result = [m for m in result if m.model_type == model_type]

        if has_local:
            result = [m for m in result if m.model_type != ModelType.API_ONLY]

        return result


# =============================================================================
# 单例访问器
# =============================================================================

_instance: Optional["AICapabilityRegistry"] = None


class AICapabilityRegistry:
    """
    AI能力注册中心 (单例)

    协调硬件检测、模型匹配、能力存储和共享
    """

    def __init__(self):
        self._detector = AICapabilityDetector()
        self._current_profile: Optional[CapabilityProfile] = None
        self._db_path = Path(__file__).parent.parent / "database" / "hermes.db"
        self._ensure_db()

    def _ensure_db(self) -> None:
        """确保数据库存在"""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(str(self._db_path))
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ai_capability_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_hash TEXT UNIQUE NOT NULL,
                cpu_model TEXT,
                cpu_cores INTEGER,
                ram_total_gb REAL,
                gpu_renderer TEXT,
                gpu_vram_gb REAL,
                best_model TEXT,
                best_speed INTEGER,
                profile_data TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ai_capability_shares (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_hash TEXT NOT NULL,
                shared_with_peer TEXT,
                share_method TEXT,
                shared_at TEXT,
                note TEXT
            )
        """)

        conn.commit()
        conn.close()

    def detect(self, override_specs: Optional[Dict[str, Any]] = None) -> CapabilityProfile:
        """
        执行硬件检测并创建能力画像

        Args:
            override_specs: 可选的硬件覆盖值

        Returns:
            CapabilityProfile: 能力画像
        """
        self._current_profile = self._detector.create_profile(override_specs=override_specs)
        self._save_profile(self._current_profile)
        return self._current_profile

    def get_current_profile(self) -> Optional[CapabilityProfile]:
        """获取当前能力画像"""
        return self._current_profile

    def load_profile(self, profile_hash: str) -> Optional[CapabilityProfile]:
        """从数据库加载能力画像"""
        try:
            conn = sqlite3.connect(str(self._db_path))
            cursor = conn.cursor()

            cursor.execute(
                "SELECT profile_data FROM ai_capability_profiles WHERE profile_hash = ?",
                (profile_hash,)
            )
            row = cursor.fetchone()
            conn.close()

            if row:
                data = json.loads(row[0])
                self._current_profile = self._profile_from_dict(data)
                return self._current_profile

        except Exception as e:
            logger.info(f"加载画像失败: {e}")

        return None

    def _save_profile(self, profile: CapabilityProfile) -> None:
        """保存能力画像到数据库"""
        try:
            conn = sqlite3.connect(str(self._db_path))
            cursor = conn.cursor()

            best = profile.best_model
            hw = profile.hardware

            cursor.execute("""
                INSERT OR REPLACE INTO ai_capability_profiles
                (profile_hash, cpu_model, cpu_cores, ram_total_gb, gpu_renderer,
                 gpu_vram_gb, best_model, best_speed, profile_data, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                profile.profile_hash,
                hw.cpu_model,
                hw.cpu_cores,
                hw.ram_total_gb,
                hw.gpu_renderer,
                hw.gpu_vram_gb,
                best.name if best else None,
                best.estimated_speed if best else 0,
                json.dumps(profile.to_dict(), ensure_ascii=False),
                profile.timestamp,
                datetime.now().isoformat()
            ))

            conn.commit()
            conn.close()

        except Exception as e:
            logger.info(f"保存画像失败: {e}")

    def _profile_from_dict(self, data: Dict[str, Any]) -> CapabilityProfile:
        """从字典创建CapabilityProfile"""
        hardware = HardwareSpec.from_dict(data["hardware"])
        models = [ModelSpec(**m) for m in data.get("compatible_models", [])]
        best_data = data.get("best_model")
        best = ModelSpec(**best_data) if best_data else None

        return CapabilityProfile(
            hardware=hardware,
            compatible_models=models,
            best_model=best,
            timestamp=data.get("timestamp", datetime.now().isoformat()),
            profile_hash=data.get("profile_hash", "")
        )

    def can_run_model(self, model_name: str) -> Tuple[bool, ModelCompatibility, int]:
        """
        检查是否能运行指定模型

        Returns:
            (can_run, compatibility, estimated_speed)
        """
        if self._current_profile is None:
            self.detect()

        for model in self._current_profile.compatible_models:
            if model.name == model_name:
                return (
                    model.compatibility != ModelCompatibility.UNSUPPORTED,
                    model.compatibility,
                    model.estimated_speed
                )

        return False, ModelCompatibility.UNSUPPORTED, 0

    def get_capability_summary(self) -> Dict[str, Any]:
        """获取能力摘要"""
        if self._current_profile is None:
            self.detect()

        profile = self._current_profile
        hw = profile.hardware
        best = profile.best_model

        return {
            "profile_hash": profile.profile_hash,
            "cpu": f"{hw.cpu_model} ({hw.cpu_cores}核)",
            "ram": f"{hw.ram_total_gb}GB {hw.ram_type}",
            "gpu": hw.gpu_renderer if hw.has_gpu else "无独立GPU",
            "vram": f"{hw.gpu_vram_gb}GB" if hw.has_gpu else "N/A",
            "best_model": best.name if best else "N/A",
            "best_speed": f"{best.estimated_speed} tok/s" if best else "N/A",
            "model_count": len(profile.compatible_models),
            "local_capable": len([m for m in profile.compatible_models
                                 if m.compatibility != ModelCompatibility.API_ONLY]),
            "timestamp": profile.timestamp
        }

    def generate_service_description(
        self,
        service_name: str,
        price_per_hour: float
    ) -> str:
        """
        生成AI服务的硬件认证描述

        用于DeCommerce商品发布
        """
        if self._current_profile is None:
            self.detect()

        summary = self.get_capability_summary()

        return f"""
{service_name}
【硬件认证】
CPU: {summary['cpu']}
内存: {summary['ram']}
GPU: {summary['gpu']} ({summary['vram']})
推荐模型: {summary['best_model']}
预估速度: {summary['best_speed']}
━━━━━━━━━━━━━━━━━━━━
价格: ¥{price_per_hour}/小时
交付: P2P安全通道
认证指纹: {summary['profile_hash'][:16]}
"""

    def register_service_in_decommerce(
        self,
        service_name: str,
        service_type: str,
        price_per_hour: float,
        broadcast_callback=None
    ) -> Dict[str, Any]:
        """
        注册AI算力服务到DeCommerce系统

        Args:
            service_name: 服务名称
            service_type: 服务类型 (gpt问答/代码检查/等)
            price_per_hour: 每小时价格
            broadcast_callback: 可选的广播回调函数

        Returns:
            发布结果
        """
        if self._current_profile is None:
            self.detect()

        profile = self._current_profile
        best = profile.best_model

        # 构建服务列表
        listing = {
            "id": f"ai_service_{profile.profile_hash[:8]}",
            "type": "ai_capability",
            "name": service_name,
            "service_type": service_type,
            "hardware_certified": {
                "cpu": profile.hardware.cpu_model,
                "ram_gb": profile.hardware.ram_total_gb,
                "gpu": profile.hardware.gpu_renderer,
                "vram_gb": profile.hardware.gpu_vram_gb,
            },
            "recommended_model": best.name if best else None,
            "estimated_speed": best.estimated_speed if best else 0,
            "price_per_hour": price_per_hour,
            "profile_hash": profile.profile_hash,
            "timestamp": datetime.now().isoformat()
        }

        # 如果有广播回调,则广播
        if broadcast_callback:
            asyncio.create_task(broadcast_callback(listing))

        return listing


def get_ai_capability_registry() -> AICapabilityRegistry:
    """获取AI能力注册中心单例"""
    global _instance
    if _instance is None:
        _instance = AICapabilityRegistry()
    return _instance


def get_local_capability(
    override_specs: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """快捷函数: 获取本地AI算力能力"""
    registry = get_ai_capability_registry()
    if override_specs:
        registry.detect(override_specs)
    else:
        registry.detect()
    return registry.get_capability_summary()


def can_run_model(model_name: str) -> Tuple[bool, str, int]:
    """快捷函数: 检查是否能运行模型"""
    registry = get_ai_capability_registry()
    can_run, compat, speed = registry.can_run_model(model_name)
    return can_run, compat.value, speed
