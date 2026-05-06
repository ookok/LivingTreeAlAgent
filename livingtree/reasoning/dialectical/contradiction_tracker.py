"""Dialectical Logic — Contradiction Tracking.

黑格尔/马克思辩证逻辑的工程实现：
  对立统一律: 任何事物内部都包含矛盾双方，矛盾推动发展
  量变质变律: 量的积累达到临界点触发质的飞跃
  否定之否定律: 发展呈现螺旋上升（正→反→合）

ContradictionTracker 追踪系统中的核心矛盾：
  - 精度 vs 速度 (precision vs throughput)
  - 丢弃 vs 压实 (discard vs compaction)
  - 本地 vs 云端 (local vs cloud)
  - 探索 vs 利用 (exploration vs exploitation)
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from loguru import logger


class ContradictionState(str, Enum):
    """矛盾状态 — 辩证逻辑核心概念。"""
    UNITY = "unity"              # 统一：矛盾双方共存
    STRUGGLE = "struggle"        # 斗争：矛盾激化
    RESOLUTION = "resolution"    # 解决：矛盾暂时化解（推向更高层次）
    NEGATION = "negation"        # 否定之否定：螺旋上升


@dataclass
class ContradictionPole:
    """矛盾一极（对立面的一方）。"""
    name: str
    value: float = 0.5          # 当前强度 (0.0-1.0)
    trend: list[float] = field(default_factory=list)  # 历史变化趋势
    metadata: dict = field(default_factory=dict)

    def record(self) -> None:
        self.trend.append(self.value)
        if len(self.trend) > 100:
            self.trend = self.trend[-50:]

    @property
    def momentum(self) -> float:
        """变化趋势：正=增强，负=减弱。"""
        if len(self.trend) < 3:
            return 0.0
        recent = self.trend[-5:]
        if len(recent) < 2:
            return 0.0
        return sum(recent[i] - recent[i-1] for i in range(1, len(recent))) / (len(recent) - 1)


@dataclass
class Contradiction:
    """一个对立统一矛盾体。

    核心属性:
      - thesis/antithesis: 对立两极
      - intensity: 矛盾强度 (0=完全统一, 1=不可调和)
      - balance: 力量对比 (-1=thesis主导, 0=平衡, +1=antithesis主导)
    """
    name: str
    thesis: ContradictionPole
    antithesis: ContradictionPole
    state: ContradictionState = ContradictionState.UNITY
    resolution_count: int = 0

    @property
    def intensity(self) -> float:
        """矛盾强度：双方同时强时矛盾最激烈。"""
        return self.thesis.value * self.antithesis.value

    @property
    def balance(self) -> float:
        """力量对比：正=thesis强，负=antithesis强。"""
        return self.thesis.value - self.antithesis.value

    @property
    def is_escalating(self) -> bool:
        """矛盾是否在激化（双方都在增强）。"""
        return self.thesis.momentum > 0 and self.antithesis.momentum > 0

    @property
    def is_resolving(self) -> bool:
        """矛盾是否在缓和（双方都在减弱）。"""
        return self.thesis.momentum < 0 and self.antithesis.momentum < 0


class ContradictionTracker:
    """矛盾追踪器 — 辩证逻辑核心引擎。

    追踪系统运行中的核心矛盾，监控对立统一关系的变化，
    在量变积累到质变临界点时发出预警。

    Usage:
        tracker = ContradictionTracker()
        tracker.register("precision_vs_speed", "precision", "speed")
        tracker.update("precision_vs_speed", precision=0.85, speed=0.40)
        alert = tracker.check_phase_transition("precision_vs_speed")
    """

    def __init__(self, name: str = "default"):
        self.name = name
        self._contradictions: dict[str, Contradiction] = {}
        self._history: list[dict] = []
        self._lock = threading.Lock()

    def register(self, name: str, thesis_name: str, antithesis_name: str,
                 thesis_value: float = 0.5, antithesis_value: float = 0.5) -> Contradiction:
        """注册一个矛盾对。"""
        with self._lock:
            c = Contradiction(
                name=name,
                thesis=ContradictionPole(name=thesis_name, value=thesis_value),
                antithesis=ContradictionPole(name=antithesis_name, value=antithesis_value),
            )
            c.thesis.record()
            c.antithesis.record()
            self._contradictions[name] = c
            logger.info("Contradiction[%s]: registered '%s' (%s ↔ %s)",
                       self.name, name, thesis_name, antithesis_name)
            return c

    def update(self, name: str, **poles: float) -> Contradiction:
        """更新矛盾双方的值。"""
        with self._lock:
            c = self._contradictions.get(name)
            if not c:
                raise KeyError(f"Unknown contradiction: {name}")

            if c.thesis.name in poles:
                c.thesis.value = max(0.0, min(1.0, poles[c.thesis.name]))
            if c.antithesis.name in poles:
                c.antithesis.value = max(0.0, min(1.0, poles[c.antithesis.name]))

            c.thesis.record()
            c.antithesis.record()

            self._history.append({
                "ts": time.time(),
                "name": name,
                c.thesis.name: c.thesis.value,
                c.antithesis.name: c.antithesis.value,
                "intensity": c.intensity,
                "balance": c.balance,
                "state": c.state.value,
            })

            if len(self._history) > 1000:
                self._history = self._history[-500:]

            return c

    def check_phase_transition(self, name: str, intensity_threshold: float = 0.8) -> Optional[str]:
        """检查是否到达量变→质变临界点。

        返回: None (未到临界点) 或 质变描述字符串。
        """
        with self._lock:
            c = self._contradictions.get(name)
            if not c:
                return None

            if c.intensity >= intensity_threshold and c.is_escalating:
                old_state = c.state
                c.state = ContradictionState.STRUGGLE
                c.resolution_count += 1
                desc = (
                    f"PHASE TRANSITION [{name}]: {c.thesis.name}({c.thesis.value:.2f}) "
                    f"↔ {c.antithesis.name}({c.antithesis.value:.2f}) | "
                    f"intensity={c.intensity:.2f}, "
                    f"old_state={old_state.value} → struggle, "
                    f"resolutions={c.resolution_count}"
                )
                logger.warning("Contradiction[%s]: %s", self.name, desc)
                return desc

            if c.state == ContradictionState.STRUGGLE and c.intensity < 0.3:
                c.state = ContradictionState.RESOLUTION
                desc = (
                    f"NEGATION OF NEGATION [{name}]: resolved at higher level, "
                    f"resolution #{c.resolution_count}"
                )
                logger.info("Contradiction[%s]: %s", self.name, desc)
                return desc

            return None

    def get_dominant_pole(self, name: str) -> tuple[str, float]:
        """获取当前矛盾的主导方。"""
        c = self._contradictions.get(name)
        if not c:
            return ("none", 0.0)
        if c.balance > 0:
            return (c.thesis.name, abs(c.balance))
        elif c.balance < 0:
            return (c.antithesis.name, abs(c.balance))
        return ("balanced", 0.0)

    def get_all_states(self) -> dict[str, dict]:
        """获取所有矛盾的当前状态快照。"""
        with self._lock:
            return {
                name: {
                    "thesis": c.thesis.name,
                    "thesis_value": c.thesis.value,
                    "thesis_momentum": c.thesis.momentum,
                    "antithesis": c.antithesis.name,
                    "antithesis_value": c.antithesis.value,
                    "antithesis_momentum": c.antithesis.momentum,
                    "intensity": c.intensity,
                    "balance": c.balance,
                    "state": c.state.value,
                    "escalating": c.is_escalating,
                    "dominant": self.get_dominant_pole(name)[0],
                    "resolutions": c.resolution_count,
                }
                for name, c in self._contradictions.items()
            }

    def get_stats(self) -> dict:
        with self._lock:
            return {
                "name": self.name,
                "contradictions": len(self._contradictions),
                "history_entries": len(self._history),
                "active_struggles": sum(
                    1 for c in self._contradictions.values()
                    if c.state == ContradictionState.STRUGGLE
                ),
                "total_resolutions": sum(
                    c.resolution_count for c in self._contradictions.values()
                ),
            }
