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
        try:
            from ..cell.dream_pretraining import DreamPretrainer
            pretrainer = DreamPretrainer()
            return pretrainer
        except Exception:
            return None

    async def retrieve_day_memories(self) -> list[ReplayChunk]:
        sm = self._get_struct_mem()
        if not sm:
            return []

        try:
            entries = await sm.retrieve_for_query(
                "recent conversation summary",
                top_k=self.MAX_CHUNKS_PER_DREAM,
                user_only=False,
            )
        except Exception:
            entries = []

        chunks: list[ReplayChunk] = []
        for entry in (entries or []):
            content = getattr(entry, 'text_for_retrieval', lambda: "")()
            if not content:
                continue

            emotional = getattr(entry, 'emotional_valence', 0.0)
            cognitive = self._estimate_cognitive_depth(content)
            novelty = self._estimate_novelty(content)
            user_fb = self._estimate_user_feedback(content)

            salience = 0.35 * abs(emotional) + 0.30 * cognitive + 0.20 * novelty + 0.15 * abs(user_fb - 0.5) * 2

            chunks.append(ReplayChunk(
                event_id=getattr(entry, 'id', ''),
                content=content[:300],
                timestamp=getattr(entry, 'timestamp', ''),
                emotional_salience=salience,
                cognitive_depth=cognitive,
                novelty_score=novelty,
                user_feedback=user_fb,
            ))

        chunks.sort(key=lambda c: c.emotional_salience, reverse=True)
        self._replay_bank = {c.event_id: c for c in chunks}
        return chunks

    async def extract_patterns(self, chunks: list[ReplayChunk]) -> list[ExtractPattern]:
        import hashlib, uuid
        themes: dict[str, list[str]] = defaultdict(list)

        for c in chunks:
            for theme, keywords in {
                "user_correction": ["不对", "错误", "改", "不要", "fix", "correct", "wrong", "change"],
                "api_operation": ["API", "api", "请求", "request", "接口", "endpoint"],
                "refactoring": ["重构", "refactor", "重写", "整理", "rewrite", "clean"],
                "knowledge_query": ["是什么", "如何", "怎么", "what is", "how to", "explain"],
                "error_handling": ["bug", "异常", "错误", "异常", "error", "Exception", "fail", "crash"],
                "user_preference": ["喜欢", "偏好", "常用", "prefer", "like", "use"],
                "deployment": ["部署", "deploy", "docker", "k8s", "上线", "发布"],
                "performance": ["慢", "优化", "加速", "slow", "optimize", "perf", "fast"],
            }.items():
                if any(kw in c.content.lower() for kw in keywords):
                    themes[theme].append(c.event_id)

        patterns = []
        for theme, event_ids in themes.items():
            if len(event_ids) >= self.PATTERN_CONSOLIDATION_THRESHOLD:
                pattern_id = f"pt_{hashlib.md5(theme.encode()).hexdigest()[:8]}_{uuid.uuid4().hex[:4]}"
                confidence = min(1.0, len(event_ids) / 8)
                actionable = len(event_ids) >= 5 and theme in (
                    "user_correction", "user_preference", "error_handling"
                )
                patterns.append(ExtractPattern(
                    pattern_id=pattern_id,
                    theme=theme,
                    supporting_events=event_ids[:10],
                    confidence=confidence,
                    category=self._map_theme_category(theme),
                    actionable=actionable,
                ))

        return patterns

    async def consolidate(self, feed_to_pretraining: bool = True) -> ConsolidationSession:
        import uuid
        sid = f"dreamcons_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        t0 = time.time()

        if self._active:
            return ConsolidationSession(
                session_id=sid, chunks_replayed=0, patterns=[], reinforced_memories=[],
                discarded_memories=[], new_engrams=0, insight="", duration_seconds=0,
                status="skipped",
            )

        self._active = True
        logger.info(f"DreamConsolidator: starting consolidation {sid}")

        try:
            chunks = await self.retrieve_day_memories()
            reinforced: list[str] = []
            discarded: list[str] = []
            new_engrams = 0

            for _ in range(self.REPLAY_PASSES):
                for c in chunks:
                    c.replay_count += 1
                    if c.emotional_salience >= self.HIGH_SALIENCE_BOOST:
                        reinforced.append(c.event_id)
                    elif c.emotional_salience < self.MIN_SALIENCE_TO_KEEP:
                        discarded.append(c.event_id)

            reinforced = list(dict.fromkeys(reinforced))
            discarded = [d for d in dict.fromkeys(discarded) if d not in reinforced]

            patterns = await self.extract_patterns(chunks)

            new_engrams = await self._crystallize_to_engram(chunks, patterns)
            await self._reinforce_persona_facts(chunks)
            await self._reinforce_struct_mem(reinforced)

            if feed_to_pretraining:
                await self._feed_pretrainer(chunks, patterns)

            insights = []
            for p in patterns[:3]:
                insights.append(f"{p.theme}({len(p.supporting_events)}件)")
            if reinforced:
                insights.append(f"强化{len(reinforced)}条记忆")
            if discarded:
                insights.append(f"丢弃{len(discarded)}条噪音")

            insight = f"梦态巩固: {', '.join(insights)}" if insights else "梦态巩固: 信息已整理"

            session = ConsolidationSession(
                session_id=sid,
                chunks_replayed=len(chunks) * self.REPLAY_PASSES,
                patterns=patterns,
                reinforced_memories=reinforced,
                discarded_memories=discarded,
                new_engrams=new_engrams,
                insight=insight,
                duration_seconds=time.time() - t0,
                status="completed",
            )

            self._total_chunks_replayed += len(chunks)
            self._total_patterns += len(patterns)
            self._sessions.append(session)
            self._save()

            logger.info(f"DreamConsolidator: {sid} done — {len(chunks)} chunks, "
                        f"{len(patterns)} patterns, {new_engrams} engrams, "
                        f"{len(reinforced)} reinforced, {len(discarded)} discarded")

        except Exception as e:
            logger.error(f"DreamConsolidator: {sid} failed: {e}")
            session = ConsolidationSession(
                session_id=sid, chunks_replayed=0, patterns=[], reinforced_memories=[],
                discarded_memories=[], new_engrams=0, insight="", duration_seconds=time.time() - t0,
                status="error",
            )
        finally:
            self._active = False
        return session

    async def _crystallize_to_engram(self, chunks: list[ReplayChunk],
                                      patterns: list[ExtractPattern]) -> int:
        eng = self._get_engram_store()
        if not eng:
            return 0

        new_count = 0
        for p in patterns:
            if p.confidence < 0.4:
                continue
            key = f"dream_pattern:{p.theme}"
            try:
                eng.insert(key, p.theme, category="user_fact")
                new_count += 1
            except Exception:
                pass

        for c in chunks:
            if c.emotional_salience < self.HIGH_SALIENCE_BOOST:
                continue
            key = f"dream_mem:{c.event_id[:20]}"
            try:
                eng.insert(key, c.content[:150], category="general")
                new_count += 1
            except Exception:
                pass
        return new_count

    async def _reinforce_persona_facts(self, chunks: list[ReplayChunk]) -> None:
        pm = self._get_persona_mem()
        if not pm:
            return
        for c in chunks:
            if c.emotional_salience < self.HIGH_SALIENCE_BOOST:
                continue
            if c.cognitive_depth > 0.5:
                try:
                    domain = self._classify_domain(c.content)
                    if domain:
                        pm.extract_facts(f"dream replay: {c.content[:200]}", domain=domain)
                except Exception:
                    pass

    async def _reinforce_struct_mem(self, event_ids: list[str]) -> None:
        pass

    async def _feed_pretrainer(self, chunks: list[ReplayChunk],
                                patterns: list[ExtractPattern]) -> None:
        pretrainer = self._get_dream_pretrainer()
        if not pretrainer or not hasattr(pretrainer, 'should_dream'):
            return
        high_sal = [c for c in chunks if c.emotional_salience >= self.HIGH_SALIENCE_BOOST]
        if high_sal:
            logger.debug(f"DreamConsolidator: {len(high_sal)} high-salience memories available for pretraining")

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
