"""Historical Logic — Layering Tracker (层累演进律).

历史逻辑第二规律：层层积累、逐渐高级。

核心机制：
  1. Layer 架构: 每一层是对前一层的抽象与超越
  2. Evolution tracking: 记录每一层的诞生时间和累积贡献
  3. Emergent capability: 检测层次跃迁产生涌现能力

LivingTree 映射:
  Layer 0: 原始功能 (工具调用)
  Layer 1: 主动学习 (EvolutionEngine)
  Layer 2: 结构化记忆 (StructMemory)
  Layer 3: 多文档融合 (MultiDocFusion)
  Layer 4: 逻辑推理 (本 reasoning 层)
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger


@dataclass
class Layer:
    """一个进化层。

    每一层包含一组相关能力，层与层之间有明确的依赖和超越关系。
    """
    name: str
    level: int
    description: str = ""
    capabilities: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)     # 依赖的低层
    transcends: list[str] = field(default_factory=list)     # 超越的低层
    created_at: float = field(default_factory=time.time)
    stability: float = 1.0  # 成熟度 (0=实验, 1=稳定)
    usage_count: int = 0


@dataclass
class EmergentCapability:
    """涌现能力 — 层累叠加后产生的高阶能力。

    涌现特征：无法从单独任一层预测，是多层协同的产物。
    """
    name: str
    description: str
    emerged_at_level: int
    required_layers: list[str]  # 需要哪些层同时存在
    detected_at: float = field(default_factory=time.time)
    confidence: float = 0.0


class LayeringTracker:
    """层累演进追踪器。

    记录系统能力的层层积累，监控涌现现象。

    Usage:
        tracker = LayeringTracker()
        tracker.register_layer("基础工具层", 0, ["tool_executor", "file_parser"])
        tracker.register_layer("主动学习层", 1, ["evolution_engine"], depends_on=["基础工具层"])
        emergent = tracker.check_emergence()
    """

    def __init__(self, name: str = "default"):
        self.name = name
        self._layers: dict[str, Layer] = {}
        self._emergents: list[EmergentCapability] = []
        self._lock = threading.RLock()

    def register_layer(
        self,
        name: str,
        level: int,
        capabilities: list[str],
        description: str = "",
        depends_on: list[str] = None,
        transcends: list[str] = None,
    ) -> Layer:
        """注册一个进化层。"""
        with self._lock:
            layer = Layer(
                name=name,
                level=level,
                description=description,
                capabilities=capabilities,
                depends_on=depends_on or [],
                transcends=transcends or [],
            )
            self._layers[name] = layer
            logger.info(
                "Layering[%s]: Layer %d — '%s' (%d capabilities, depends on %s)",
                self.name, level, name, len(capabilities), layer.depends_on,
            )
            return layer

    def mark_usage(self, layer_name: str) -> None:
        """标记某层被使用（帮助衡量稳定性）。"""
        with self._lock:
            layer = self._layers.get(layer_name)
            if layer:
                layer.usage_count += 1
                layer.stability = min(1.0, layer.stability + 0.001)

    def check_emergence(self) -> list[EmergentCapability]:
        """检测是否有涌现能力产生。

        涌现条件：
          1. 某个能力在多个高层同时存在
          2. 这些层依赖同一组低层
          3. 该能力无法归因于单独任一层
        """
        with self._lock:
            new_emergents = []
            capability_to_layers: dict[str, list[str]] = {}

            for name, layer in self._layers.items():
                for cap in layer.capabilities:
                    if cap not in capability_to_layers:
                        capability_to_layers[cap] = []
                    capability_to_layers[cap].append(name)

            for cap, layer_names in capability_to_layers.items():
                if len(layer_names) >= 2:
                    layers = [self._layers[n] for n in layer_names if n in self._layers]
                    max_level = max(l.level for l in layers)
                    min_level = min(l.level for l in layers)

                    if max_level - min_level >= 2:  # 跨越了至少两层
                        existing = [e for e in self._emergents if e.name == cap]
                        if not existing:
                            emergent = EmergentCapability(
                                name=cap,
                                description=f"Emergent ability spanning Layers {min_level}-{max_level}",
                                emerged_at_level=max_level,
                                required_layers=layer_names,
                                confidence=min(1.0, 0.5 + 0.1 * (max_level - min_level)),
                            )
                            self._emergents.append(emergent)
                            new_emergents.append(emergent)
                            logger.info(
                                "Layering[%s]: EMERGENCE detected — '%s' at Layer %d "
                                "(spans layers %d-%d)",
                                self.name, cap, max_level, min_level, max_level,
                            )

            return new_emergents

    def get_layer_stack(self) -> list[dict]:
        """获取完整的层堆栈（从低到高）。"""
        with self._lock:
            sorted_layers = sorted(self._layers.values(), key=lambda l: l.level)
            return [
                {
                    "level": l.level,
                    "name": l.name,
                    "capabilities": l.capabilities,
                    "depends_on": l.depends_on,
                    "transcends": l.transcends,
                    "stability": l.stability,
                    "usage_count": l.usage_count,
                    "age_hours": (time.time() - l.created_at) / 3600,
                }
                for l in sorted_layers
            ]

    def get_layers_between(self, from_level: int, to_level: int) -> list[Layer]:
        return [
            l for l in self._layers.values()
            if from_level <= l.level <= to_level
        ]

    def get_total_capabilities(self) -> int:
        with self._lock:
            all_caps = set()
            for layer in self._layers.values():
                all_caps.update(layer.capabilities)
            return len(all_caps)

    def get_stats(self) -> dict:
        with self._lock:
            return {
                "name": self.name,
                "layers": len(self._layers),
                "max_level": max((l.level for l in self._layers.values()), default=0),
                "total_capabilities": self.get_total_capabilities(),
                "emergents": len(self._emergents),
                "stable_layers": sum(1 for l in self._layers.values() if l.stability >= 0.9),
            }
