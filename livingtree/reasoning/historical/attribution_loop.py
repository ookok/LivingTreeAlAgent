"""Historical Logic — Attribution Iterative Loop (归因迭代律).

历史逻辑第一规律：因果追溯、反复修正。

核心机制：
  1. 任务执行失败 → 自动归因到根因模块
  2. 归因候选排序 → 按置信度 + 历史频率
  3. 修复后验证 → 反馈更新归因模型
  4. 迭代收敛 → 归因精度随时间递增

与现有模块集成：
  - `agent_eval.py`: 任务评估结果入归因
  - `error_replay.py`: 错误重放验证归因
  - `disco_gc.py`: GC 决策归因 (discard vs compact)
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger


@dataclass
class Attribution:
    """一次归因记录。"""
    id: str
    incident: str           # 事件描述
    root_cause: str          # 根因模块名
    confidence: float = 0.0  # 归因置信度
    evidence: list[str] = field(default_factory=list)
    fix_applied: str = ""
    fix_successful: Optional[bool] = None  # 修复是否有效
    timestamp: float = field(default_factory=time.time)
    iteration: int = 0      # 本事件第几次归因迭代


class AttributionLoop:
    """归因迭代环 — 从失败到修复的因果闭环。

    Usage:
        loop = AttributionLoop()
        loop.record_incident("RAG检索遗漏", module="document_kb", confidence=0.7)
        loop.record_fix("RAG检索遗漏", "升级 hierarchical_ingest", success=True)
        # 后续同类问题直接指向 document_kb（归因收敛）
    """

    def __init__(self, name: str = "default"):
        self.name = name
        self._attributions: dict[str, list[Attribution]] = defaultdict(list)
        self._module_failure_counts: dict[str, int] = defaultdict(int)
        self._module_fix_success_rate: dict[str, tuple[int, int]] = defaultdict(lambda: (0, 0))
        self._lock = threading.Lock()
        self._next_id = 0

    def record_incident(
        self,
        incident: str,
        root_cause: str,
        confidence: float = 0.5,
        evidence: list[str] = None,
    ) -> Attribution:
        """记录一个事件及其归因。"""
        with self._lock:
            self._next_id += 1
            iteration = 1
            existing = self._attributions.get(incident, [])
            if existing:
                iteration = existing[-1].iteration + 1

            attr = Attribution(
                id=f"attr_{self._next_id}",
                incident=incident,
                root_cause=root_cause,
                confidence=confidence,
                evidence=evidence or [],
                iteration=iteration,
            )
            self._attributions[incident].append(attr)
            self._module_failure_counts[root_cause] += 1

            logger.debug(
                "AttributionLoop[%s]: '%s' → %s (conf=%.2f, iter=%d)",
                self.name, incident, root_cause, confidence, iteration,
            )
            return attr

    def record_fix(
        self, incident: str, fix_description: str, success: bool,
    ) -> None:
        """记录修复尝试和结果。"""
        with self._lock:
            attrs = self._attributions.get(incident, [])
            if not attrs:
                return

            latest = attrs[-1]
            latest.fix_applied = fix_description
            latest.fix_successful = success

            total, succeed = self._module_fix_success_rate[latest.root_cause]
            if success:
                succeed += 1
            self._module_fix_success_rate[latest.root_cause] = (total + 1, succeed)

            logger.info(
                "AttributionLoop[%s]: fix '%s' for '%s' → %s",
                self.name, fix_description, incident, "OK" if success else "FAIL",
            )

    def find_root_cause(self, incident: str) -> list[tuple[str, float]]:
        """给定事件，推断最可能的根因（排序）。

        策略：本事件历史归因 + 同类事件归因频率。
        """
        with self._lock:
            candidates = []

            # 本事件的历史归因
            if incident in self._attributions:
                for attr in self._attributions[incident]:
                    bonus = 1.2 if attr.fix_successful else 0.5 if attr.fix_successful is False else 0.8
                    candidates.append((attr.root_cause, attr.confidence * bonus))

            # 全局模块失败频率
            total_failures = sum(self._module_failure_counts.values()) or 1
            for module, count in self._module_failure_counts.items():
                freq_score = count / total_failures
                total, succeed = self._module_fix_success_rate[module]
                fix_rate = succeed / max(total, 1)
                score = freq_score * 0.3 + fix_rate * 0.7
                candidates.append((module, score))

            # 去重合并（取最高分）
            merged: dict[str, float] = {}
            for module, score in candidates:
                if module not in merged or score > merged[module]:
                    merged[module] = score

            return sorted(merged.items(), key=lambda x: -x[1])

    def get_top_problem_modules(self, top_n: int = 5) -> list[tuple[str, int, float]]:
        """获取最需关注的模块（失败多且修复成功率低）。"""
        with self._lock:
            scored = []
            for module, count in self._module_failure_counts.items():
                total, succeed = self._module_fix_success_rate[module]
                fix_rate = succeed / max(total, 1)
                urgency = count * (1 - fix_rate)
                scored.append((module, count, fix_rate, urgency))

            scored.sort(key=lambda x: -x[3])
            return [(m, c, r) for m, c, r, _ in scored[:top_n]]

    def get_convergence(self) -> float:
        """归因收敛度：最近归因是否趋于稳定（不再频繁变动）。"""
        with self._lock:
            if not self._attributions:
                return 0.0
            total = sum(len(v) for v in self._attributions.values())
            fixed = sum(1 for v in self._attributions.values() if v and v[-1].fix_successful)
            return fixed / max(total, 1)

    def get_stats(self) -> dict:
        with self._lock:
            return {
                "name": self.name,
                "incidents": len(self._attributions),
                "total_attributions": sum(len(v) for v in self._attributions.values()),
                "modules_tracked": len(self._module_failure_counts),
                "convergence": round(self.get_convergence(), 3),
                "top_problems": self.get_top_problem_modules(3),
            }
