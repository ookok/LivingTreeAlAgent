"""StrategicDistiller — Distill interaction trajectories into abstract reusable strategic principles.

EvolveR-style experience-driven self-improvement:
  1. Collect trajectories from RecordingEngine
  2. Distill each trajectory into abstract strategic principles
  3. Store principles in ContextMoE as high-value Deep memory
  4. Retrieve relevant principles during LLM interaction via PromptEngine

Bridge between: RecordingEngine → StrategicDistiller → ContextMoE → PromptEngine
"""

from __future__ import annotations

import json
import math
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from loguru import logger

PRINCIPLES_FILE = Path(".livingtree/strategic_principles.json")


# ═══ Data Types ════════════════════════════════════════════════════


@dataclass
class StrategicPrinciple:
    """An abstract, reusable strategic principle distilled from experience."""
    id: str = ""
    principle: str = ""              # Abstract principle text
    category: str = ""               # "tool_use" | "reasoning" | "planning" | "debugging"
    source_traces: list[str] = field(default_factory=list)  # RecordingEngine trace IDs
    success_evidence: int = 0        # Times this principle led to success
    failure_evidence: int = 0        # Times this principle was violated in failure
    applicability_score: float = 0.5 # How broadly applicable (0-1)
    last_used: float = 0.0
    embedding_hint: str = ""          # Key terms for retrieval


@dataclass
class DistillationResult:
    traces_processed: int = 0
    principles_distilled: int = 0
    principles_reinforced: int = 0
    duration_ms: float = 0.0


# ═══ Strategic Distiller ═══════════════════════════════════════════


class StrategicDistiller:
    """Distill interaction experiences into strategic principles."""

    _instance: Optional["StrategicDistiller"] = None

    @classmethod
    def instance(cls) -> "StrategicDistiller":
        if cls._instance is None:
            cls._instance = StrategicDistiller()
        return cls._instance

    def __init__(self):
        self._principles: dict[str, StrategicPrinciple] = {}
        self._distilled_count = 0
        self._load()

    # ── Main Distillation Pipeline ─────────────────────────────────

    async def distill_from_recordings(self, engine: Any = None) -> DistillationResult:
        """Distill all recording traces into strategic principles."""
        t0 = time.time()
        result = DistillationResult()

        try:
            from .recording_engine import get_recording_engine
            engine = engine or get_recording_engine()
            recordings = engine.list_recordings()[-50:]

            for rec in recordings:
                rec_obj = engine._recordings.get(rec["id"])
                if not rec_obj:
                    continue
                result.traces_processed += 1

                # Distill principles from this recording's events
                for evt in rec_obj.events:
                    if evt.result_error or not evt.result:
                        # Failure → reinforce relevant principles as counter-examples
                        self._reinforce_failure(evt)
                        result.principles_reinforced += 1
                        continue

                    # Success → distill new principles
                    if evt.type in ("tool_call", "llm_chat"):
                        new_count = self._distill_event(evt, rec["id"])
                        result.principles_distilled += new_count
        except Exception as e:
            logger.debug(f"StrategicDistiller: {e}")

        result.duration_ms = (time.time() - t0) * 1000
        if result.principles_distilled > 0:
            self._save()
            logger.info(
                f"StrategicDistiller: {result.principles_distilled} new principles "
                f"from {result.traces_processed} traces ({result.duration_ms:.0f}ms)"
            )
        return result

    def _distill_event(self, evt, trace_id: str) -> int:
        """Distill a single successful event into strategic principles."""
        count = 0
        text = str(evt.result)[:2000] if evt.result else ""
        params = str(evt.params)[:500] if hasattr(evt, 'params') else ""

        # Pattern 1: Successful tool choice
        if evt.capability:
            principle_text = self._extract_tool_strategy(evt.capability, text)
            if principle_text:
                self._add_principle(f"tool:{evt.capability}",
                                   principle_text, "tool_use", trace_id)
                count += 1

        # Pattern 2: Multi-step reasoning detected
        reasoning_patterns = self._detect_reasoning_patterns(text)
        for pattern in reasoning_patterns:
            self._add_principle(f"reasoning:{hash(pattern) & 0xFFFF:04x}",
                              pattern, "reasoning", trace_id)
            count += 1

        # Pattern 3: Successful debugging / fix
        if self._detect_debugging(text):
            principle_text = self._extract_debugging_strategy(text)
            if principle_text:
                self._add_principle(f"debug:{hash(principle_text) & 0xFFFF:04x}",
                                  principle_text, "debugging", trace_id)
                count += 1

        return count

    def _add_principle(self, pid: str, principle: str,
                       category: str, trace_id: str) -> None:
        """Add or reinforce a strategic principle."""
        if pid in self._principles:
            p = self._principles[pid]
            p.success_evidence += 1
            if trace_id not in p.source_traces:
                p.source_traces.append(trace_id)
            p.last_used = time.time()
            return

        self._principles[pid] = StrategicPrinciple(
            id=pid, principle=principle[:300], category=category,
            source_traces=[trace_id], success_evidence=1,
            last_used=time.time(),
            embedding_hint=" ".join(principle.lower().split()[:10]),
        )
        self._distilled_count += 1

    def _reinforce_failure(self, evt) -> None:
        """Reinforce existing principles as counter-examples on failure."""
        if not hasattr(evt, 'capability') or not evt.capability:
            return
        pid = f"tool:{evt.capability}"
        if pid in self._principles:
            self._principles[pid].failure_evidence += 1

    # ── Pattern Extractors ────────────────────────────────────────

    @staticmethod
    def _extract_tool_strategy(capability: str, text: str) -> str:
        """Extract strategic insight from successful tool use."""
        tool_hints = {
            "web_search": "搜索前先明确关键词,限定来源和时效性",
            "read_file": "读取大文件时先查看结构,再定位关键部分",
            "bash": "执行命令前先dry-run验证,处理异常输出",
            "vfs:read": "先用list了解结构,再按需读取具体文件",
            "vfs:write": "写入前检查路径是否存在,使用原子写入",
        }
        for key, hint in tool_hints.items():
            if key in capability:
                return f"[{capability}] {hint}"
        return f"[{capability}] 工具调用成功后记录为有效策略"

    @staticmethod
    def _detect_reasoning_patterns(text: str) -> list[str]:
        """Detect reasoning patterns in output text."""
        patterns = []
        text_lower = text.lower()

        if "首先" in text and "然后" in text and "最后" in text:
            patterns.append("结构化推理: 首先-然后-最后分解步骤")
        if "因为" in text and "所以" in text:
            patterns.append("因果推理: 明确原因和结果的逻辑链")
        if "如果" in text and "那么" in text:
            patterns.append("假设验证: 提出假设并推演后果")
        if "first" in text_lower and "then" in text_lower and "finally" in text_lower:
            patterns.append("Structured reasoning: decompose into sequential steps")
        if len(patterns) < 2 and len(text.split()) > 50:
            patterns.append("长文本推理: 使用分段结构化输出")
        return patterns[:3]

    @staticmethod
    def _detect_debugging(text: str) -> bool:
        """Detect if the event involved debugging/fixing."""
        debug_keywords = ["修复", "fix", "bug", "错误", "error", "debug",
                         "调试", "修正", "解决", "resolved", "fixed"]
        return any(kw in text.lower() for kw in debug_keywords)

    @staticmethod
    def _extract_debugging_strategy(text: str) -> str:
        debug_hints = [
            ("先定位", "先定位错误源,再逐步缩小范围修复"),
            ("测试", "修复后运行对应测试验证"),
            ("日志", "使用日志追踪执行路径定位问题"),
            ("断点", "在关键位置设置检查点验证假设"),
        ]
        for keyword, strategy in debug_hints:
            if keyword in text:
                return strategy
        return "调试修复: 定位根因→验证修复→回归测试"

    # ── Retrieval ──────────────────────────────────────────────────

    def retrieve(self, context: str, top_k: int = 3) -> list[str]:
        """Retrieve relevant strategic principles for current context."""
        ctx_words = set(context.lower().split())
        scored = []
        for pid, p in self._principles.items():
            p_words = set(p.embedding_hint.lower().split())
            overlap = len(ctx_words & p_words) / max(len(p_words), 1)
            # Weight: success evidence vs failure
            total = p.success_evidence + p.failure_evidence
            reliability = p.success_evidence / max(total, 1)
            score = overlap * 0.4 + reliability * 0.3 + min(p.success_evidence / 10, 1.0) * 0.3
            if score > 0.05:
                scored.append((score, p.principle, pid))
        scored.sort(key=lambda x: -x[0])
        return [p for _, p, _ in scored[:top_k]]

    def inject_into_prompt(self, context: str) -> str:
        """Build a strategic guidance section for the LLM prompt."""
        principles = self.retrieve(context, top_k=3)
        if not principles:
            return ""
        parts = ["[已验证的有效策略]"]
        for i, p in enumerate(principles):
            parts.append(f"  {i+1}. {p}")
        return "\n".join(parts)

    # ── Persistence ────────────────────────────────────────────────

    def _save(self):
        try:
            PRINCIPLES_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = {
                pid: {"principle": p.principle, "category": p.category,
                      "success_evidence": p.success_evidence,
                      "failure_evidence": p.failure_evidence,
                      "source_traces": p.source_traces[-10:],
                      "embedding_hint": p.embedding_hint}
                for pid, p in self._principles.items() if p.success_evidence >= 2
            }
            PRINCIPLES_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        except Exception as e:
            logger.debug(f"StrategicDistiller save: {e}")

    def _load(self):
        try:
            if PRINCIPLES_FILE.exists():
                data = json.loads(PRINCIPLES_FILE.read_text())
                for pid, pd in data.items():
                    self._principles[pid] = StrategicPrinciple(
                        id=pid, principle=pd["principle"],
                        category=pd.get("category", ""),
                        source_traces=pd.get("source_traces", []),
                        success_evidence=pd.get("success_evidence", 0),
                        failure_evidence=pd.get("failure_evidence", 0),
                        embedding_hint=pd.get("embedding_hint", ""),
                    )
                logger.info(f"StrategicDistiller: loaded {len(self._principles)} principles")
        except Exception:
            pass

    def stats(self) -> dict:
        by_cat = defaultdict(int)
        for p in self._principles.values():
            by_cat[p.category] += 1
        return {
            "total_principles": len(self._principles),
            "total_distilled": self._distilled_count,
            "by_category": dict(by_cat),
        }


_distiller: Optional[StrategicDistiller] = None


def get_strategic_distiller() -> StrategicDistiller:
    global _distiller
    if _distiller is None:
        _distiller = StrategicDistiller()
    return _distiller


__all__ = ["StrategicDistiller", "StrategicPrinciple", "get_strategic_distiller"]
