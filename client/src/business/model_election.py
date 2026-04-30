# -*- coding: utf-8 -*-
"""
硬件感知 L0/L3/L4 模型自动选举系统
====================================

功能：
1. 自动检测本地硬件（CPU/RAM/GPU/VRAM）
2. 根据硬件配置，从 Ollama 模型列表中自动选举：
   - L0: 轻量快速模型（意图分类/路由）
   - L3: 中等推理模型（意图理解）
   - L4: 深度生成模型（思考/长文）
3. 如果 Ollama 中没有合适模型，加载 models 文件夹下的 SmolLM2.gguf

硬件分级策略：
- 无 GPU / 低配 (< 4GB VRAM): L0=smollm2, L3=qwen2.5:0.5b, L4=qwen2.5:1.5b
- 中配 (4-8GB VRAM): L0=qwen2.5:0.5b, L3=qwen3.5:2b, L4=qwen3.5:4b
- 高配 (8-16GB VRAM): L0=qwen2.5:0.5b, L3=qwen3.5:4b, L4=qwen3.5:9b
- 顶级 (> 16GB VRAM): L0=qwen3.5:2b, L3=qwen3.5:4b, L4=qwen3.6:35b
"""

import subprocess
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
from dataclasses import dataclass

# 硬件感知 - 利用已有的 ai_capability_detector
try:
    from client.src.business.ai_capability_detector import AICapabilityDetector, HardwareSpec
    HARDWARE_DETECTOR_AVAILABLE = True
except ImportError:
    HARDWARE_DETECTOR_AVAILABLE = False


@dataclass
class ModelTier:
    """模型层级信息"""
    name: str           # 模型名称（Ollama 格式，如 qwen2.5:0.5b）
    purpose: str         # 用途描述
    vram_min_gb: float   # 最低 VRAM 需求（GB）
    tier: str            # L0 / L3 / L4


@dataclass
class ElectionResult:
    """选举结果"""
    l0_model: str
    l3_model: str
    l4_model: str
    hardware: "HardwareSpec"
    gpu_vram_gb: float
    tier_level: str      # "low" / "medium" / "high" / "ultra"


# ── 模型候选池（按 VRAM 需求分层）───────────────────────────────────

MODEL_CANDIDATES: Dict[str, List[ModelTier]] = {
    # 无 GPU 或极低配置：全部使用 CPU 可运行的极小模型
    "ultra_low": [
        ModelTier("smollm2:latest",    "L0 快速路由", 0,   "L0"),
        ModelTier("qwen2.5:0.5b",       "L3 意图理解", 0,   "L3"),
        ModelTier("qwen2.5:1.5b",       "L4 深度生成", 0,   "L4"),
    ],
    # 低配（< 4GB VRAM）
    "low": [
        ModelTier("qwen2.5:0.5b",       "L0 快速路由", 0,   "L0"),
        ModelTier("qwen3.5:0.8b",       "L3 意图理解", 2,   "L3"),
        ModelTier("qwen3.5:2b",         "L4 深度生成", 3,   "L4"),
    ],
    # 中配（4-8GB VRAM）
    "medium": [
        ModelTier("qwen2.5:0.5b",       "L0 快速路由", 0,   "L0"),
        ModelTier("qwen3.5:2b",         "L3 意图理解", 2,   "L3"),
        ModelTier("qwen3.5:4b",         "L4 深度生成", 4,   "L4"),
    ],
    # 高配（8-16GB VRAM）
    "high": [
        ModelTier("qwen2.5:0.5b",       "L0 快速路由", 0,   "L0"),
        ModelTier("qwen3.5:4b",         "L3 意图理解", 4,   "L3"),
        ModelTier("qwen3.5:9b",         "L4 深度生成", 8,   "L4"),
    ],
    # 顶级（> 16GB VRAM）
    "ultra": [
        ModelTier("qwen3.5:2b",         "L0 快速路由", 2,   "L0"),
        ModelTier("qwen3.5:4b",         "L3 意图理解", 4,   "L3"),
        ModelTier("qwen3.6:35b-a3b",   "L4 深度生成", 24,  "L4"),
    ],
}


# ── Ollama 模型列表获取 ─────────────────────────────────────────────

def get_ollama_models() -> List[str]:
    """获取 Ollama 中已下载的模型列表"""
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            return []
        models = []
        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("NAME") or line.startswith("-"):
                continue
            # 第一列是模型名
            name = line.split()[0]
            if name:
                models.append(name)
        return models
    except Exception:
        return []


# ── SmolLM2.gguf 加载 ─────────────────────────────────────────────

def find_smolllm2_gguf() -> Optional[Path]:
    """查找 SmolLM2.gguf 文件"""
    search_paths = [
        Path(__file__).parent.parent / "models",
        Path.home() / ".hermes-desktop" / "models",
        Path.home() / ".ollama" / "models" / "file_context",
    ]
    for search_dir in search_paths:
        if not search_dir.exists():
            continue
        # 优先找 SmolLM2.gguf
        gguf = search_dir / "SmolLM2.gguf"
        if gguf.exists():
            return gguf
        # 找任意 smollm gguf
        for gguf_file in search_dir.glob("*smollm*.gguf"):
            if "q4_k" in gguf_file.name.lower() or "q5" in gguf_file.name.lower():
                return gguf_file
            return gguf_file  # 任意 smollm 都行
    return None


# ── 硬件检测 ───────────────────────────────────────────────────────

def detect_hardware() -> "HardwareSpec":
    """检测本地硬件配置"""
    if HARDWARE_DETECTOR_AVAILABLE:
        detector = AICapabilityDetector()
        return detector.detect_hardware()
    else:
        # 备用：简单检测
        import psutil
        ram_gb = psutil.virtual_memory().total / (1024 ** 3)
        return _SimpleHardwareSpec(
            cpu_cores=psutil.cpu_count(logical=False) or 4,
            ram_total_gb=ram_gb,
            gpu_vram_gb=0,
            has_gpu=False,
        )


class _SimpleHardwareSpec:
    """简化硬件规格（备用）"""
    def __init__(self, cpu_cores, ram_total_gb, gpu_vram_gb, has_gpu):
        self.cpu_cores = cpu_cores
        self.ram_total_gb = ram_total_gb
        self.gpu_vram_gb = gpu_vram_gb
        self.has_gpu = has_gpu


# ── 核心选举算法 ────────────────────────────────────────────────────

def elect_models(
    ollama_models: Optional[List[str]] = None,
    hardware: Optional["HardwareSpec"] = None,
) -> ElectionResult:
    """
    根据硬件配置自动选举 L0/L3/L4 模型

    选举策略：
    1. 检测硬件（GPU VRAM / RAM）
    2. 确定硬件层级
    3. 从候选池中选择每层最适合的模型
    4. 如果 Ollama 中没有候选模型，降级到次优选择
    5. 如果 Ollama 中完全没模型，尝试加载 SmolLM2.gguf
    """
    if ollama_models is None:
        ollama_models = get_ollama_models()

    if hardware is None:
        hardware = detect_hardware()

    vram_gb = hardware.gpu_vram_gb if hasattr(hardware, "gpu_vram_gb") else 0
    has_gpu = hardware.has_gpu if hasattr(hardware, "has_gpu") else False

    # 确定硬件层级
    tier_level = _classify_tier(vram_gb, has_gpu, hardware)
    candidates = MODEL_CANDIDATES[tier_level]

    # 从候选池中选择每层模型
    l0 = _select_best_fit(candidates, "L0", ollama_models)
    l3 = _select_best_fit(candidates, "L3", ollama_models)
    l4 = _select_best_fit(candidates, "L4", ollama_models)

    return ElectionResult(
        l0_model=l0,
        l3_model=l3,
        l4_model=l4,
        hardware=hardware,
        gpu_vram_gb=vram_gb,
        tier_level=tier_level,
    )


def _classify_tier(vram_gb: float, has_gpu: bool, hardware) -> str:
    """
    根据 VRAM + RAM + CPU 综合分类硬件层级

    策略：
    - 有 GPU：按 GPU VRAM 分层（精确）
    - 无 GPU：按 RAM + CPU 核数分层（内存足够时可用较大模型）
    """
    ram_gb = hardware.ram_total_gb if hasattr(hardware, "ram_total_gb") else 0
    cpu_cores = hardware.cpu_cores if hasattr(hardware, "cpu_cores") else 4

    # ── 有 GPU 加速 ───────────────────────────────────────────────
    if has_gpu and vram_gb >= 1:
        if vram_gb < 4:
            return "low"
        elif vram_gb < 8:
            return "medium"
        elif vram_gb < 16:
            return "high"
        else:
            return "ultra"

    # ── 无 GPU 加速，纯 CPU 模式 ─────────────────────────────────
    # RAM 足够 + CPU 核心多 → 可用量化大模型（但慢）
    if ram_gb >= 48 and cpu_cores >= 16:
        # 超大内存 + 多核：可跑 9B 量化模型
        return "high"
    elif ram_gb >= 32 and cpu_cores >= 12:
        # 大内存：可跑 4B 模型
        return "medium"
    elif ram_gb >= 16 and cpu_cores >= 8:
        # 中等配置：可跑 2B 模型
        return "low"
    else:
        # 小内存或低核心：只能用极小模型
        return "ultra_low"


def _select_best_fit(
    candidates: List[ModelTier],
    tier: str,
    available: List[str],
) -> str:
    """
    从候选池中选择最适合的模型

    策略：优先选择 Ollama 中已下载的，如果都没有则选候选列表第一个
    """
    tier_candidates = [c for c in candidates if c.tier == tier]

    # 1. 精确匹配 Ollama 中的模型
    for candidate in tier_candidates:
        if candidate.name in available:
            return candidate.name

    # 2. 尝试部分匹配（如 "qwen2.5:0.5b" 可能被注册为 "qwen2.5:0.5b:latest"）
    available_lower = [m.lower() for m in available]
    for candidate in tier_candidates:
        for avail in available_lower:
            if candidate.name.lower() in avail or avail in candidate.name.lower():
                # 找到匹配，返回原始名称
                for m in available:
                    if m.lower() == avail:
                        return m
                # 模糊匹配，返回候选名称
                return candidate.name

    # 3. 如果没有精确匹配，选择第一个候选（降级方案）
    if tier_candidates:
        return tier_candidates[0].name

    # 4. 兜底：返回 qwen2.5:0.5b
    return "qwen2.5:0.5b"


# ── OllamaRunner SmolLM2 加载集成 ───────────────────────────────────

def ensure_smolllm2_for_l0() -> Tuple[bool, Optional[str]]:
    """
    确保 SmolLM2 可用于 L0 路由

    Returns:
        (success, model_name)
    """
    ollama_models = get_ollama_models()

    # 检查是否已有 smollm 模型
    for m in ollama_models:
        if "smollm" in m.lower():
            return True, m

    # 尝试从 models 文件夹加载 SmolLM2.gguf
    gguf_path = find_smolllm2_gguf()
    if gguf_path:
        try:
            # 复制到 Ollama 目录
            ollama_models_dir = Path.home() / ".ollama" / "models" / "file_context"
            ollama_models_dir.mkdir(parents=True, exist_ok=True)
            dest = ollama_models_dir / gguf_path.name
            import shutil
            if not dest.exists():
                shutil.copy(gguf_path, dest)

            # 创建 Modelfile
            modelfile = Path.home() / ".ollama" / "models" / "Modelfile.smollm2"
            modelfile.write_text(
                f"FROM {gguf_path.name}\n"
                "PARAMETER num_ctx 2048\n"
                'TEMPLATE "{{ .System }} {{ .Prompt }}"'
            )

            # 运行 ollama create
            result = subprocess.run(
                ["ollama", "create", "smollm2:latest", "-f", str(modelfile)],
                capture_output=True, text=True, timeout=120
            )
            if result.returncode == 0:
                return True, "smollm2:latest"
        except Exception as e:
            print(f"[ModelElection] 加载 SmolLM2.gguf 失败: {e}")

    return False, None


# ── 快捷函数 ───────────────────────────────────────────────────────

_election_cache: Optional[ElectionResult] = None


def get_elected_models(force_refresh: bool = False) -> ElectionResult:
    """
    获取选举结果（带缓存）

    用法：
    >>> result = get_elected_models()
    >>> print(result.l0_model, result.l3_model, result.l4_model)
    """
    global _election_cache
    if _election_cache is None or force_refresh:
        _election_cache = elect_models()
    return _election_cache


def print_election_report(result: Optional[ElectionResult] = None):
    """打印选举报告"""
    if result is None:
        result = get_elected_models()

    hw = result.hardware
    vram_display = f"{result.gpu_vram_gb}GB" if result.gpu_vram_gb > 0 else "无独立GPU（CPU模式）"

    print("=" * 50)
    print("  L0/L3/L4 模型自动选举报告")
    print("=" * 50)
    print(f"  硬件层级: {result.tier_level} ({vram_display})")
    print(f"  CPU核心: {hw.cpu_cores if hasattr(hw, 'cpu_cores') else '?'}")
    print(f"  系统内存: {hw.ram_total_gb if hasattr(hw, 'ram_total_gb') else '?'}GB")
    print()
    print(f"  L0 (快速路由): {result.l0_model}")
    print(f"  L3 (意图理解): {result.l3_model}")
    print(f"  L4 (深度生成): {result.l4_model}")
    print("=" * 50)


# ── 测试入口 ───────────────────────────────────────────────────────

if __name__ == "__main__":
    print("检测硬件配置...")
    hw = detect_hardware()
    vram_gb = hw.gpu_vram_gb if hasattr(hw, "gpu_vram_gb") else 0
    has_gpu = hw.has_gpu if hasattr(hw, "has_gpu") else False

    print(f"  GPU: {has_gpu}, VRAM: {vram_gb}GB")
    print(f"  CPU核心: {hw.cpu_cores if hasattr(hw, 'cpu_cores') else '?'}")
    print(f"  内存: {hw.ram_total_gb if hasattr(hw, 'ram_total_gb') else '?'}GB")

    print("\n获取 Ollama 模型列表...")
    models = get_ollama_models()
    print(f"  已安装模型: {len(models)} 个")
    for m in models[:10]:
        print(f"    - {m}")

    print("\n执行模型选举...")
    result = elect_models(ollama_models=models, hardware=hw)
    print_election_report(result)
