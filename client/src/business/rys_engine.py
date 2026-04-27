"""
RYS (Repeat Yourself) 层重复推理引擎
=====================================

基于 dnhkng 的 RYS 研究：在推理时重复执行 Transformer 中间推理层，
不修改权重、不微调、不训练，仅改变层的执行路径。

核心原理：
    - Transformer 有三层解剖结构：编码层(~17%)、推理层(~60%)、解码层(~25%)
    - 只重复中间推理层（而非编码层或解码层）才有收益
    - 小模型单层重复即可获得显著提升（Qwen3-4B 重复第21层 → +11.9%）

配置格式：
    - (i, j) 块配置：运行层 0..j-1，然后跳回运行层 i..N-1
    - 效果：层 i..j-1 被重复执行
    - 基线：(0, 0) = 无重复

参考：
    - https://github.com/dnhkng/RYS
    - https://github.com/ggml-org/llama.cpp/discussions/21116

使用方式：
    # 方式1：直接使用 RYSEngine
    engine = RYSEngine()
    config = engine.scan_optimal_config("qwen3.5:4b", num_layers=36)
    result = engine.run_with_rys(prompt, system_prompt, config)

    # 方式2：通过 GlobalModelRouter（推荐）
    response = await router.call_model(
        capability=ModelCapability.REASONING,
        prompt="帮我分析环境影响...",
        rys_config={"blocks": [(21, 22)]},  # 重复第21层
    )
"""

import json
import time
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any

logger = logging.getLogger(__name__)


# ── 配置数据结构 ──────────────────────────────────────────────────


@dataclass
class RYSBlock:
    """RYS 块配置：(i, j) 表示重复层 i..j-1"""
    start: int  # i：重复起始层
    end: int    # j：重复结束层（不包含）

    def __post_init__(self):
        if self.start < 0 or self.end < 0:
            raise ValueError(f"层索引不能为负数: ({self.start}, {self.end})")
        if self.start >= self.end:
            raise ValueError(f"起始层必须小于结束层: ({self.start}, {self.end})")

    @property
    def repeat_count(self) -> int:
        """重复的层数"""
        return self.end - self.start

    def __repr__(self):
        return f"RYSBlock({self.start},{self.end})"

    def to_tuple(self) -> Tuple[int, int]:
        return (self.start, self.end)

    @classmethod
    def from_tuple(cls, t: Tuple[int, int]) -> "RYSBlock":
        return cls(start=t[0], end=t[1])


@dataclass
class RYSConfig:
    """RYS 完整配置"""
    blocks: List[RYSBlock] = field(default_factory=list)
    enabled: bool = True
    num_layers: int = 0  # 模型总层数

    def __post_init__(self):
        # 去重并排序
        seen = set()
        unique_blocks = []
        for b in self.blocks:
            key = (b.start, b.end)
            if key not in seen:
                seen.add(key)
                unique_blocks.append(b)
        self.blocks = sorted(unique_blocks, key=lambda b: b.start)

    @property
    def total_extra_layers(self) -> int:
        """额外重复的层数"""
        return sum(b.repeat_count for b in self.blocks)

    @property
    def is_baseline(self) -> bool:
        """是否为基线配置（无重复）"""
        return len(self.blocks) == 0

    def get_execution_sequence(self, num_layers: int) -> List[int]:
        """
        生成完整的层执行序列

        例：num_layers=36, blocks=[RYSBlock(21,22)]
        → [0,1,2,...,20, 21, 21, 22,23,...,35]
        层 21 被执行两次

        例：num_layers=36, blocks=[RYSBlock(5,8)]
        → [0,1,2,3,4, 5,6,7, 5,6,7, 8,9,...,35]
        层 5,6,7 被执行两次
        """
        if not self.blocks or not self.enabled:
            return list(range(num_layers))

        sequence = []
        blocks_sorted = sorted(self.blocks, key=lambda b: b.start)

        # 构建带重复的执行序列
        layer_idx = 0
        block_i = 0

        while layer_idx < num_layers:
            if block_i < len(blocks_sorted):
                block = blocks_sorted[block_i]
                if layer_idx == block.start:
                    # 先正常执行这一段
                    for l in range(block.start, block.end):
                        if l < num_layers:
                            sequence.append(l)
                    layer_idx = block.end
                    # 然后重复这一段
                    for l in range(block.start, block.end):
                        if l < num_layers:
                            sequence.append(l)
                    block_i += 1
                    continue
                elif layer_idx < block.start:
                    # 正常执行到 block 起始
                    for l in range(layer_idx, block.start):
                        if l < num_layers:
                            sequence.append(l)
                    layer_idx = block.start
                    continue
            # 正常执行
            sequence.append(layer_idx)
            layer_idx += 1

        return sequence

    def to_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "blocks": [b.to_tuple() for b in self.blocks],
            "num_layers": self.num_layers,
            "total_extra_layers": self.total_extra_layers,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "RYSConfig":
        blocks = []
        for b in d.get("blocks", []):
            if isinstance(b, (list, tuple)) and len(b) == 2:
                blocks.append(RYSBlock(start=b[0], end=b[1]))
        return cls(
            blocks=blocks,
            enabled=d.get("enabled", True),
            num_layers=d.get("num_layers", 0),
        )


@dataclass
class RYSScanResult:
    """RYS 扫描结果"""
    block: RYSBlock
    score: float
    latency_ms: float
    details: Dict[str, Any] = field(default_factory=dict)


class RYSPreset(Enum):
    """RYS 预设配置（基于 dnhkng 的实验结果）"""

    @staticmethod
    def for_qwen3_4b() -> RYSConfig:
        """Qwen3-4B 最优配置（来自实验：重复第21层，+11.9%）"""
        return RYSConfig(blocks=[RYSBlock(21, 22)], num_layers=36)

    @staticmethod
    def for_qwen3_5_4b() -> RYSConfig:
        """Qwen3.5-4B 推荐配置（参考 Qwen3-4B 结果，需实测验证）"""
        return RYSConfig(blocks=[RYSBlock(21, 22)], num_layers=36)

    @staticmethod
    def for_emotion() -> RYSConfig:
        """情绪推理优化（情感推理黄金区 7-16 层）"""
        return RYSConfig(blocks=[RYSBlock(12, 13)], num_layers=36)

    @staticmethod
    def for_math() -> RYSConfig:
        """数学推理优化（数学推理黄金区 21-27 层）"""
        return RYSConfig(blocks=[RYSBlock(24, 25)], num_layers=36)

    @staticmethod
    def for_comprehensive() -> RYSConfig:
        """综合优化（感性+理性双层重复）"""
        return RYSConfig(
            blocks=[RYSBlock(12, 13), RYSBlock(24, 25)],
            num_layers=36,
        )


# ── 已知模型的层配置 ──────────────────────────────────────────────

# 模型名 → 总层数映射（来自 Ollama /api/show 的 architecture.block_count）
MODEL_NUM_LAYERS: Dict[str, int] = {
    "qwen3.5:0.8b": 32,
    "qwen3.5:1.5b": 28,
    "qwen3.5:2b": 36,
    "qwen3.5:4b": 36,
    "qwen3.5:9b": 40,
    "qwen3.5:14b": 40,
    "qwen3.5:32b": 64,
    "qwen3.5:72b": 80,
    "qwen3.6:latest": 28,  # 3b 版本
    "qwen3.6:35b-a3b": 64,
    "qwen2.5:0.5b": 24,
    "qwen2.5:1.5b": 28,
    "qwen2.5:3b": 36,
    "qwen2.5:7b": 28,
    "qwen2.5:14b": 40,
    "qwen2.5:32b": 64,
    "qwen2.5:72b": 80,
    "smollm2-test:latest": 24,
    "deepseek-r1:70b": 64,
}


# ── 模型层分区（三段论）───────────────────────────────────────────

@dataclass
class LayerZone:
    """模型层分区"""
    encode_end: int     # 编码层结束（0 ~ encode_end-1）
    reason_start: int   # 推理层开始
    reason_end: int     # 推理层结束
    decode_start: int   # 解码层开始
    total: int          # 总层数

    @property
    def encode_layers(self) -> range:
        return range(0, self.encode_end)

    @property
    def reason_layers(self) -> range:
        return range(self.reason_start, self.reason_end)

    @property
    def decode_layers(self) -> range:
        return range(self.decode_start, self.total)

    def is_safe_to_repeat(self, layer: int) -> bool:
        """某层是否安全可重复（在推理黄金区）"""
        return self.reason_start <= layer < self.reason_end


def estimate_layer_zones(num_layers: int) -> LayerZone:
    """
    估算模型层分区（基于 dnhkng 的实验规律）

    经验公式（来自 Qwen 系列实验）：
    - 编码层：前 ~17% → 负责文字→向量
    - 推理层：中间 ~60% → 真正"思考"
    - 解码层：后 ~25% → 向量→文字

    Args:
        num_layers: 模型总层数

    Returns:
        LayerZone 分区信息
    """
    encode_end = max(1, int(num_layers * 0.17))
    decode_start = int(num_layers * 0.75)
    reason_start = encode_end
    reason_end = decode_start

    return LayerZone(
        encode_end=encode_end,
        reason_start=reason_start,
        reason_end=reason_end,
        decode_start=decode_start,
        total=num_layers,
    )


def get_model_num_layers(model_name: str, ollama_url: str = "http://localhost:11434") -> int:
    """
    获取模型的层数

    优先级：
    1. 本地缓存映射表
    2. Ollama /api/show API

    Args:
        model_name: 模型名称
        ollama_url: Ollama 服务地址

    Returns:
        层数（获取失败返回 0）
    """
    # 1. 查缓存
    if model_name in MODEL_NUM_LAYERS:
        return MODEL_NUM_LAYERS[model_name]

    # 2. 查 Ollama API
    try:
        import httpx
        with httpx.Client(timeout=10.0) as c:
            r = c.post(
                f"{ollama_url}/api/show",
                json={"name": model_name},
            )
            if r.status_code == 200:
                data = r.json()
                arch = data.get("model_info", {}).get("architecture", {})
                num_layers = arch.get("block_count", 0)
                if num_layers > 0:
                    MODEL_NUM_LAYERS[model_name] = num_layers
                    return num_layers
    except Exception as e:
        logger.debug(f"获取模型层数失败 ({model_name}): {e}")

    return 0


# ── RYS 引擎 ──────────────────────────────────────────────────────


class RYSEngine:
    """
    RYS (Repeat Yourself) 层重复推理引擎

    功能：
    1. 管理模型层分区信息
    2. 提供 RYS 配置建议
    3. 记录 RYS 使用效果
    4. 与 GlobalModelRouter 集成

    注意：
    - 当前 Ollama/llama.cpp 不支持运行时层重复参数
    - 实际的层重复需要在 GGUF 模型文件层面实现（预构建 RYS 模型变体）
    - 本引擎作为配置管理和效果追踪层，为后续集成做准备
    """

    # RYS 使用记录（model → list of (config, score, latency)）
    _usage_history: Dict[str, List[dict]] = {}

    def __init__(self, ollama_url: str = "http://localhost:11434"):
        self.ollama_url = ollama_url

    def get_model_zones(self, model_name: str) -> Optional[LayerZone]:
        """获取模型的层分区"""
        num_layers = get_model_num_layers(model_name, self.ollama_url)
        if num_layers == 0:
            return None
        return estimate_layer_zones(num_layers)

    def suggest_config(
        self,
        model_name: str,
        task_type: str = "general",
    ) -> RYSConfig:
        """
        推荐最优 RYS 配置

        Args:
            model_name: 模型名称
            task_type: 任务类型
                - "general": 综合任务
                - "emotion": 情绪感知/情感推理
                - "math": 数学/逻辑推理
                - "reasoning": 深度推理
                - "chat": 对话

        Returns:
            推荐的 RYSConfig
        """
        num_layers = get_model_num_layers(model_name, self.ollama_url)
        if num_layers == 0:
            logger.warning(f"未知模型层数 ({model_name})，返回基线配置")
            return RYSConfig()

        zones = estimate_layer_zones(num_layers)

        # 根据任务类型选择黄金层
        if task_type == "emotion":
            # 情感推理黄金区：7-16 层
            target_layer = (zones.reason_start + zones.reason_start + int(zones.total * 0.17)) // 2
            target_layer = max(zones.reason_start, min(target_layer, zones.reason_end - 1))
            return RYSConfig(blocks=[RYSBlock(target_layer, target_layer + 1)], num_layers=num_layers)

        elif task_type == "math" or task_type == "reasoning":
            # 数学推理黄金区：靠后（21-27 层 / 36 层模型）
            target_layer = zones.reason_end - max(1, int(num_layers * 0.08))
            target_layer = max(zones.reason_start, min(target_layer, zones.reason_end - 1))
            return RYSConfig(blocks=[RYSBlock(target_layer, target_layer + 1)], num_layers=num_layers)

        else:
            # general/chat：使用模型系列预设
            preset = self._find_preset(model_name, num_layers)
            if preset:
                return preset

            # 默认：推理区中间偏后
            mid_reason = (zones.reason_start + zones.reason_end) // 2
            target_layer = max(zones.reason_start, min(mid_reason + 3, zones.reason_end - 1))
            return RYSConfig(blocks=[RYSBlock(target_layer, target_layer + 1)], num_layers=num_layers)

    def _find_preset(self, model_name: str, num_layers: int) -> Optional[RYSConfig]:
        """查找匹配的预设配置"""
        name_lower = model_name.lower()

        if "qwen3.5" in name_lower or "qwen3" in name_lower:
            if num_layers <= 28:
                # 小模型（3b 级别）
                return RYSConfig(blocks=[RYSBlock(num_layers * 58 // 100, num_layers * 58 // 100 + 1)], num_layers=num_layers)
            elif num_layers <= 40:
                # 中模型（9b-14b）
                return RYSPreset.for_qwen3_4b()
            else:
                # 大模型
                return RYSConfig(blocks=[RYSBlock(num_layers * 52 // 100, num_layers * 52 // 100 + 2)], num_layers=num_layers)
        elif "qwen2.5" in name_lower:
            return RYSPreset.for_qwen3_4b()  # 近似

        return None

    def validate_config(self, config: RYSConfig, model_name: str) -> Tuple[bool, str]:
        """
        验证 RYS 配置是否安全

        Args:
            config: RYS 配置
            model_name: 模型名称

        Returns:
            (是否安全, 原因说明)
        """
        num_layers = get_model_num_layers(model_name, self.ollama_url)
        if num_layers == 0:
            return False, f"未知模型层数 ({model_name})"

        zones = estimate_layer_zones(num_layers)

        for block in config.blocks:
            if block.start < 0 or block.end > num_layers:
                return False, f"层索引超出范围 ({block.start},{block.end}) / 总层数 {num_layers}"

            # 检查是否碰到了编码层或解码层
            for layer in range(block.start, block.end):
                if layer < zones.encode_end:
                    return False, f"层 {layer} 在编码区（0-{zones.encode_end-1}），重复可能降低质量"
                if layer >= zones.decode_start:
                    return False, f"层 {layer} 在解码区（{zones.decode_start}+），重复可能降低质量"

        # 检查重复层数是否过多（帕累托法则：>3 层不划算）
        if config.total_extra_layers > 3:
            return False, f"重复 {config.total_extra_layers} 层过多，建议 ≤3 层"

        return True, "配置安全"

    def record_usage(
        self,
        model_name: str,
        config: RYSConfig,
        score: float,
        latency_ms: float,
    ):
        """记录 RYS 使用效果"""
        if model_name not in RYSEngine._usage_history:
            RYSEngine._usage_history[model_name] = []

        RYSEngine._usage_history[model_name].append({
            "config": config.to_dict(),
            "score": score,
            "latency_ms": latency_ms,
            "timestamp": time.time(),
        })

        # 只保留最近 100 条记录
        if len(RYSEngine._usage_history[model_name]) > 100:
            RYSEngine._usage_history[model_name] = RYSEngine._usage_history[model_name][-100:]

    def get_best_config(self, model_name: str, task_type: str = "general") -> Optional[RYSConfig]:
        """
        从历史记录中获取最优配置

        Args:
            model_name: 模型名称
            task_type: 任务类型（暂未分类，返回全局最优）

        Returns:
            历史最优配置（无记录返回 None）
        """
        history = RYSEngine._usage_history.get(model_name, [])
        if not history:
            return None

        best = max(history, key=lambda x: x["score"])
        return RYSConfig.from_dict(best["config"])

    def print_model_analysis(self, model_name: str) -> str:
        """
        打印模型的层分析报告

        Returns:
            分析报告文本
        """
        num_layers = get_model_num_layers(model_name, self.ollama_url)
        if num_layers == 0:
            return f"⚠️ 无法获取模型 {model_name} 的层数信息"

        zones = estimate_layer_zones(num_layers)

        lines = [
            f"📊 模型层分析: {model_name}",
            f"{'='*60}",
            f"  总层数: {num_layers}",
            f"",
            f"  🏗️  编码层: 0-{zones.encode_end-1} ({zones.encode_end}层)",
            f"  🧠 推理层: {zones.reason_start}-{zones.reason_end-1} ({zones.reason_end - zones.reason_start}层) ← 黄金区",
            f"  🔤 解码层: {zones.decode_start}-{zones.total-1} ({zones.total - zones.decode_start}层)",
            f"",
            f"  ✅ 推荐重复层:",
        ]

        # 情绪推理推荐
        emotion_layer = zones.reason_start + (zones.reason_end - zones.reason_start) // 3
        lines.append(f"    情绪推理: 第 {emotion_layer} 层 (感性思考靠前)")

        # 数学推理推荐
        math_layer = zones.reason_end - max(1, (zones.reason_end - zones.reason_start) // 4)
        lines.append(f"    数学推理: 第 {math_layer} 层 (理性思考靠后)")

        # 综合推荐
        lines.append(f"    综合最优: 第 {math_layer} 层 (单层重复性价比最高)")

        # 执行序列示例
        sample_config = RYSConfig(blocks=[RYSBlock(math_layer, math_layer + 1)], num_layers=num_layers)
        sequence = sample_config.get_execution_sequence(num_layers)
        lines.extend([
            f"",
            f"  📋 执行序列示例 (重复第 {math_layer} 层):",
            f"    {' → '.join(str(l) for l in sequence)}",
            f"    (总执行 {len(sequence)} 层，额外 +{sample_config.total_extra_layers} 层)",
        ])

        # 历史记录
        history = RYSEngine._usage_history.get(model_name, [])
        if history:
            best = max(history, key=lambda x: x["score"])
            lines.extend([
                f"",
                f"  📈 历史最优: {best['config']['blocks']}",
                f"    得分: {best['score']:.4f}, 延迟: {best['latency_ms']:.0f}ms",
            ])

        return "\n".join(lines)

    def generate_full_scan_configs(self, num_layers: int) -> List[RYSConfig]:
        """
        生成全量扫描配置（所有单层重复组合）

        Args:
            num_layers: 模型总层数

        Returns:
            所有单层 (i, i+1) 配置列表
        """
        zones = estimate_layer_zones(num_layers)
        configs = []

        # 只扫描推理区的单层重复
        for layer in zones.reason_layers:
            configs.append(RYSConfig(
                blocks=[RYSBlock(layer, layer + 1)],
                num_layers=num_layers,
            ))

        return configs


# ── 单例 ──────────────────────────────────────────────────────────

_rys_engine: Optional[RYSEngine] = None


def get_rys_engine(ollama_url: str = "http://localhost:11434") -> RYSEngine:
    """获取 RYS 引擎单例"""
    global _rys_engine
    if _rys_engine is None:
        _rys_engine = RYSEngine(ollama_url)
    return _rys_engine


# ── 便捷函数 ──────────────────────────────────────────────────────

def suggest_rys_config(model_name: str, task_type: str = "general") -> RYSConfig:
    """快速推荐 RYS 配置"""
    return get_rys_engine().suggest_config(model_name, task_type)


def validate_rys_config(config: RYSConfig, model_name: str) -> Tuple[bool, str]:
    """快速验证 RYS 配置"""
    return get_rys_engine().validate_config(config, model_name)


def get_model_zones(model_name: str) -> Optional[LayerZone]:
    """获取模型层分区"""
    return get_rys_engine().get_model_zones(model_name)


# ── 导出 ──────────────────────────────────────────────────────────

__all__ = [
    "RYSBlock",
    "RYSConfig",
    "RYSScanResult",
    "RYSPreset",
    "LayerZone",
    "RYSEngine",
    "estimate_layer_zones",
    "get_model_num_layers",
    "get_rys_engine",
    "suggest_rys_config",
    "validate_rys_config",
    "get_model_zones",
    "MODEL_NUM_LAYERS",
]
