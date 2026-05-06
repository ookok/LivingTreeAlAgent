"""Dialectical Logic — Phase Transition Monitor.

量变质变律的工程实现：
  量变: 连续值的渐进累积
  质变: 累积达到临界阈值 → 系统状态跃迁

监控指标包括：
  - DisCoGC: stale_ratio 从 0 → threshold → 触发 GC
  - Knowledge: 文档量从少量 → 触发知识图谱重构
  - Model: 错误率从低 → 触发模型切换
  - Skill: 技能积累 → 触发能力跃迁
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Callable

from loguru import logger


class Phase(str, Enum):
    """发展阶段 — 辩证逻辑中的质态。"""
    DORMANT = "dormant"          # 萌芽期
    ACCUMULATING = "accumulating"  # 积累期 (量变)
    TRANSITIONING = "transitioning"  # 过渡期 (量变→质变 临界)
    LEAPING = "leaping"           # 飞跃期 (质变)
    STABILIZING = "stabilizing"   # 稳定期 (新质态)


@dataclass
class PhaseTransition:
    """一次质变事件记录。"""
    metric_name: str
    from_phase: Phase
    to_phase: Phase
    value_at_transition: float
    threshold: float
    timestamp: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)


class PhaseTransitionMonitor:
    """量变质变监控器。

    监控多个连续指标，检测从量变累积到质变飞跃的临界点。

    应用：
      - stale_ratio 持续增长 → 0.3 触发 discard, 0.7 触发 compact
      - 知识库文档数 → 100 触发图重构
      - 用户反馈错误率 → 0.15 触发模型切换
    """

    def __init__(self, name: str = "default"):
        self.name = name
        self._metrics: dict[str, list[float]] = defaultdict(list)
        self._phases: dict[str, Phase] = {}
        self._thresholds: dict[str, dict[str, tuple[float, Phase]]] = {}
        self._transitions: list[PhaseTransition] = []
        self._lock = threading.Lock()
        self._on_transition: dict[str, list[Callable]] = defaultdict(list)

    def register_metric(
        self,
        name: str,
        thresholds: dict[str, tuple[float, Phase]] = None,
        initial_phase: Phase = Phase.DORMANT,
    ) -> None:
        """注册监控指标。

        thresholds: {描述: (阈值, 到达后的新质态), ...}
        示例: {"low": (0.3, Phase.TRANSITIONING), "high": (0.7, Phase.LEAPING)}
        """
        with self._lock:
            self._phases[name] = initial_phase
            if thresholds:
                self._thresholds[name] = thresholds
            logger.debug("PhaseMonitor[%s]: registered metric '%s' (phase=%s)",
                        self.name, name, initial_phase.value)

    def record(self, metric_name: str, value: float) -> Optional[PhaseTransition]:
        """记录一次量变观测，检查是否触发质变。"""
        with self._lock:
            self._metrics[metric_name].append(value)
            if len(self._metrics[metric_name]) > 200:
                self._metrics[metric_name] = self._metrics[metric_name][-100:]

            current_phase = self._phases.get(metric_name, Phase.DORMANT)
            thresholds = self._thresholds.get(metric_name, {})

            for thresh_desc, (threshold, target_phase) in sorted(
                thresholds.items(), key=lambda x: x[1][0],
            ):
                if value >= threshold and target_phase != current_phase:
                    transition = PhaseTransition(
                        metric_name=metric_name,
                        from_phase=current_phase,
                        to_phase=target_phase,
                        value_at_transition=value,
                        threshold=threshold,
                        metadata={"description": thresh_desc},
                    )
                    self._phases[metric_name] = target_phase
                    self._transitions.append(transition)

                    logger.info(
                        "PhaseMonitor[%s]: %s → %s @ %.3f (threshold: %s=%.3f)",
                        self.name, current_phase.value, target_phase.value,
                        value, thresh_desc, threshold,
                    )

                    # 触发回调
                    for cb in self._on_transition.get(metric_name, []):
                        try:
                            cb(transition)
                        except Exception as e:
                            logger.error("PhaseMonitor callback error: %s", e)

                    return transition

            return None

    def get_phase(self, metric_name: str) -> Phase:
        return self._phases.get(metric_name, Phase.DORMANT)

    def get_trend(self, metric_name: str, window: int = 10) -> float:
        """获取量变趋势（正=增长，负=下降）。"""
        values = self._metrics.get(metric_name, [])
        if len(values) < 2:
            return 0.0
        recent = values[-min(window, len(values)):]
        if len(recent) < 2:
            return 0.0
        return sum(recent[i] - recent[i-1] for i in range(1, len(recent))) / (len(recent) - 1)

    def is_approaching_threshold(self, metric_name: str, margin: float = 0.1) -> bool:
        """检查是否接近质变临界点。"""
        values = self._metrics.get(metric_name, [])
        if not values:
            return False
        current = values[-1]
        thresholds = self._thresholds.get(metric_name, {})

        for thresh_val, _ in thresholds.values():
            if abs(current - thresh_val) / max(thresh_val, 0.001) <= margin:
                return True
        return False

    def on_transition(self, metric_name: str, callback: Callable) -> None:
        """注册质变回调。"""
        self._on_transition[metric_name].append(callback)

    def get_transitions_since(self, timestamp: float) -> list[PhaseTransition]:
        return [t for t in self._transitions if t.timestamp >= timestamp]

    def get_summary(self) -> dict:
        with self._lock:
            return {
                metric: {
                    "current_phase": self._phases.get(metric, Phase.DORMANT).value,
                    "current_value": self._metrics[metric][-1] if self._metrics[metric] else None,
                    "trend": self.get_trend(metric),
                    "approaching_threshold": self.is_approaching_threshold(metric),
                }
                for metric in self._metrics
            }

    def get_stats(self) -> dict:
        with self._lock:
            return {
                "name": self.name,
                "metrics": len(self._metrics),
                "transitions": len(self._transitions),
                "active_phases": {
                    metric: phase.value
                    for metric, phase in self._phases.items()
                },
            }
