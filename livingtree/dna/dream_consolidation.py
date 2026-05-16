"""Dream Consolidation — Human-like memory replay during idle periods.

Implements the cognitive function of sleep/dreaming: replay the day's experiences,
extract salient patterns, discard noise, and reinforce important memories. This is
the mechanism by which humans "sleep on a problem" and wake up with clarity.

Academic grounding:
  - Walker 2004 "Sleep-Dependent Memory Consolidation"
  - Stickgold 2005 "Sleep-Dependent Memory Consolidation and Reconsolidation"
  - Lewis & Durrant 2011 "Overlapping Memory Replay During Sleep"
  - Klinzing et al. 2019 "Mechanisms of Systems Memory Consolidation"

Three-phase architecture (mirrors SWS → REM cycle):
  Phase 1 — REPLAY: Retrieve today's episodic memories from struct_mem
  Phase 2 — PATTERN EXTRACT: Cross-event consolidation → identify recurring themes
  Phase 3 — REINFORCE: Strengthen high-salience memories, discard low-signal ones

Integration surface:
  - Reads from struct_mem for episodic replay (already has consolidate logic)
  - Reads from persona_memory for user fact reinforcement
  - Writes into engram_store for crystallized knowledge
  - Delegates training to dream_pretraining.py (DreamPretrainer) for LoRA fine-tuning
  - Triggered by life_engine during idle or by GreenScheduler (GROWTH mode)

Key insight vs existing dream_pretraining.py:
  dream_pretraining generates synthetic training data for model fine-tuning.
  dream_consolidation replays REAL EXPERIENCES and extracts patterns from them.
  The two are complementary: consolidation feeds real patterns into pretraining.
"""

from __future__ import annotations

import asyncio
import math
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from loguru import logger


@dataclass
class ReplayChunk:
    """A segment of memory being replayed during consolidation."""
    event_id: str
    content: str
    timestamp: str
    emotional_salience: float       # How emotionally engaging this was (0-1)
    cognitive_depth: float          # How much reasoning/decision was involved (0-1)
    novelty_score: float            # How new/unusual this was vs past patterns (0-1)
    user_feedback: float            # User satisfaction signal (0-1, 0.5=neutral)
    replay_count: int = 0           # Times replayed in this dream session


@dataclass
class ExtractPattern:
    """A recurring pattern discovered across multiple memory chunks."""
    pattern_id: str
    theme: str                      # "user_prefers_bullets", "API_changes_cause_bugs"
    supporting_events: list[str]    # Event IDs that show this pattern
    confidence: float               # How consistently this pattern appears
    category: str = "general"       # "user_behavior", "task_pattern", "error_pattern"
    actionable: bool = False        # Can we turn this into a proactive rule?


@dataclass
class ConsolidationSession:
    """A single dream-consolidation cycle's results."""
    session_id: str
    chunks_replayed: int
    patterns: list[ExtractPattern]
    reinforced_memories: list[str]       # Event IDs that got stronger
    discarded_memories: list[str]        # Event IDs judged as noise
    new_engrams: int                     # Knowledge entries crystallized to engram store
    insight: str                         # Human-readable "what I learned" summary
    duration_seconds: float
    status: str = "completed"


class DreamConsolidator:
    """Human-like memory consolidation engine.

    Unlike DreamPretrainer (which creates synthetic training data), this replays
    REAL conversation experiences and extracts patterns, discards noise, and
    reinforces the neural trace of important moments.

    Usage:
        consolidator = DreamConsolidator()
        if consolidator.should_consolidate():
            session = await consolidator.consolidate()
            logger.info(f"Dream learned: {session.insight}")
    """

    MIN_IDLE_SECONDS = 300            # 5 min idle before dreaming
    MAX_CHUNKS_PER_DREAM = 50         # Don't replay more than 50 memories per cycle
    MIN_SALIENCE_TO_KEEP = 0.2        # Below this → noise, discard
    HIGH_SALIENCE_BOOST = 0.7         # Above this → reinforce strongly
    REPLAY_PASSES = 2                  # How many times to revisit the replay set
    PATTERN_CONSOLIDATION_THRESHOLD = 3  # Need 3+ events to form a pattern

    def __init__(self):
        self._store_path = Path(".livingtree/dream_consolidation.json")
        self._sessions: list[ConsolidationSession] = []
        self._last_activity = time.time()
        self._total_chunks_replayed = 0
        self._total_patterns = 0
        self._active = False
        self._replay_bank: dict[str, ReplayChunk] = {}
        self._load()

    def notify_activity(self) -> None:
        self._last_activity = time.time()

    def should_consolidate(self) -> bool:
        if self._active:
            return False
        idle_s = time.time() - self._last_activity
        return idle_s >= self.MIN_IDLE_SECONDS

    def _get_struct_mem(self):
        try:
            from ..knowledge.struct_mem import get_struct_memory
            return get_struct_memory()
        except Exception:
            return None

    def _get_persona_mem(self):
        try:
            from ..memory.persona_memory import get_persona_memory
            return get_persona_memory()
        except Exception:
            return None

    def _get_engram_store(self):
        try:
            from ..knowledge.engram_store import get_engram_store
            return get_engram_store()
        except Exception:
            return None

    def _get_dream_pretrainer(self):
        """DEPRECATED: dream_pretraining module removed."""
        return None

    async def _feed_pretrainer(self, chunks: list[ReplayChunk],
                                patterns: list[ExtractPattern]) -> None:
        """DEPRECATED: dream_pretraining module removed."""
        pass

    def _estimate_cognitive_depth(self, content: str) -> float:
        depth_keywords = {
            "决定": 0.15, "选择": 0.10, "分析": 0.08, "推理": 0.12,
            "结论": 0.10, "方案": 0.08, "策略": 0.10, "架构": 0.12,
            "decide": 0.15, "analyze": 0.08, "conclusion": 0.10,
            "solution": 0.10, "strategy": 0.10, "architecture": 0.12,
        }
        score = 0.0
        cl = content.lower()
        for kw, w in depth_keywords.items():
            if kw in cl:
                score += w
        return min(1.0, score + 0.15)

    def _estimate_novelty(self, content: str) -> float:
        novelty_kw = ["新", "第一次", "首次", "new", "first time", "unusual", "novel"]
        return min(1.0, sum(0.2 for kw in novelty_kw if kw in content.lower()) + 0.1)

    def _estimate_user_feedback(self, content: str) -> float:
        positive = sum(1 for kw in ["好", "对", "可以", "谢谢", "good", "correct", "thanks"] if kw in content.lower())
        negative = sum(1 for kw in ["不对", "错误", "不行", "不要", "wrong", "incorrect", "fail", "no"] if kw in content.lower())
        total = positive + negative
        if total == 0:
            return 0.5
        return positive / total

    def _classify_domain(self, content: str) -> str:
        cl = content.lower()
        for domain, kws in {
            "bio": ["我", "我的", "i am", "my", "名字", "name", "工作", "job"],
            "preferences": ["喜欢", "偏好", "不喜欢", "prefer", "like", "don't like"],
            "work": ["项目", "团队", "project", "team", "公司", "company"],
            "tools": ["用", "工具", "use", "tool", "vscode", "git", "docker"],
        }.items():
            if any(kw in cl for kw in kws):
                return domain
        return "general"

    def _map_theme_category(self, theme: str) -> str:
        mapping = {
            "user_correction": "user_behavior",
            "user_preference": "user_behavior",
            "error_handling": "error_pattern",
            "refactoring": "task_pattern",
            "api_operation": "task_pattern",
            "deployment": "task_pattern",
            "performance": "task_pattern",
            "knowledge_query": "user_behavior",
        }
        return mapping.get(theme, "general")

    def _save(self) -> None:
        try:
            import json
            self._store_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "total_chunks_replayed": self._total_chunks_replayed,
                "total_patterns": self._total_patterns,
                "sessions": [{"id": s.session_id, "chunks": s.chunks_replayed,
                              "patterns": len(s.patterns), "duration_s": s.duration_seconds,
                              "status": s.status} for s in self._sessions[-20:]],
            }
            self._store_path.write_text(json.dumps(data, ensure_ascii=False))
        except Exception:
            pass

    def _load(self) -> None:
        try:
            import json
            if self._store_path.exists():
                data = json.loads(self._store_path.read_text())
                self._total_chunks_replayed = data.get("total_chunks_replayed", 0)
                self._total_patterns = data.get("total_patterns", 0)
        except Exception:
            pass


def get_dream_consolidator() -> DreamConsolidator:
    if "_dc" not in _DC_CACHE:
        _DC_CACHE["_dc"] = DreamConsolidator()
    return _DC_CACHE["_dc"]


_DC_CACHE: dict[str, DreamConsolidator] = {}
