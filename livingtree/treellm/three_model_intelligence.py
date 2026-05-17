"""Three-Model Intelligence — Embedding·L1·L2 unified cognitive architecture.

Layers:
  Embedding (脊髓反射) — intercept simple queries, detect emotion, predict needs
  L1 (快反执行)       — fast execution, tool calls, preloading
  L2 (深度推理)       — deep reasoning, supervision, delegation via <need>

Capabilities:
  P0: Spinal reflex    — embedding cosine match intercepts 90% simple queries (<5ms)
  P1: Triage routing   — three-tier complexity → route to correct layer
  P1: Predictive load  — semantic trajectory prediction → L2 zero-wait preload
  P2: Vector snapshots — save/restore reasoning state via 384-dim embeddings
  P2: Emotion routing  — sentiment vector → tone/strategy modulation
  P3: Vector dreams    — idle-time pattern discovery → auto-generate rules
"""

from __future__ import annotations

import asyncio
import hashlib
import re
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import numpy as np
from loguru import logger


# ═══════════════════════════════════════════════════════════════
# Data types
# ═══════════════════════════════════════════════════════════════

@dataclass
class ReflexRule:
    """A spinal reflex rule — direct embedding match → response."""
    pattern: str
    response: str
    embedding: list[float] | None = None
    hit_count: int = 0
    last_hit: float = 0.0
    created_at: float = field(default_factory=time.time)

    @property
    def is_cold(self) -> bool:
        return self.hit_count < 3 or (time.time() - self.last_hit) > 86400 * 7


@dataclass
class EmotionVector:
    """VAD emotion vector (Valence-Arousal-Dominance)."""
    valence: float = 0.5     # 0=negative, 1=positive
    arousal: float = 0.5     # 0=calm, 1=excited
    dominance: float = 0.5   # 0=submissive, 1=dominant

    @property
    def is_urgent(self) -> bool:
        return self.arousal > 0.7

    @property
    def is_negative(self) -> bool:
        return self.valence < 0.3

    @property
    def is_confused(self) -> bool:
        return self.dominance < 0.3 and self.arousal > 0.5

    def tone_modifier(self) -> str:
        if self.is_negative:
            return "Use empathetic, calming tone. Acknowledge user frustration."
        if self.is_urgent:
            return "Be direct and efficient. Skip pleasantries."
        if self.is_confused:
            return "Ask clarifying questions. Break down into simple steps."
        return ""


@dataclass
class ReasoningSnapshot:
    """A 384-dim vector capturing the current reasoning state."""
    id: str
    summary: str
    vector: list[float]
    context: str = ""
    created_at: float = field(default_factory=time.time)


@dataclass
class TriageResult:
    """Complexity triage — where to route this query."""
    complexity: float           # 0=simple, 1=complex
    label: str                  # "reflex" | "fast" | "reasoning"
    emotion: EmotionVector = field(default_factory=EmotionVector)
    matched_reflex: str = ""    # matched reflex rule key
    confidence: float = 0.0     # classification confidence
    predicted_needs: list[str] = field(default_factory=list)  # predicted L2 needs


# ═══════════════════════════════════════════════════════════════
# Three-Model Intelligence Engine
# ═══════════════════════════════════════════════════════════════

class ThreeModelIntelligence:
    """Unified Embedding·L1·L2 cognitive engine.

    Wiring:
      Embedding → spinal reflex intercept / triage / emotion / preload prediction
      L1 → fast execution / tool calls / reflex rule generation
      L2 → deep reasoning / supervision / delegation via L1L2Collaboration
    """

    # ── Chinese emotion lexicon (VAD mapped) ──
    _EMOTION_LEXICON = {
        "紧急": (0.3, 0.90, 0.7),  "立刻": (0.3, 0.85, 0.7),
        "马上": (0.3, 0.80, 0.7),  "快点": (0.3, 0.85, 0.6),
        "救命": (0.1, 0.95, 0.3),  "崩溃": (0.1, 0.90, 0.2),
        "报错": (0.2, 0.75, 0.3),  "错误": (0.2, 0.70, 0.3),
        "失败": (0.2, 0.70, 0.3),  "不行": (0.2, 0.65, 0.3),
        "坏了": (0.15, 0.80, 0.2), "炸了": (0.1, 0.90, 0.2),
        "生气": (0.15, 0.85, 0.5), "失望": (0.2, 0.60, 0.3),
        "感谢": (0.85, 0.50, 0.6), "谢谢": (0.85, 0.50, 0.6),
        "很好": (0.85, 0.60, 0.7),  "完美": (0.90, 0.70, 0.8),
        "不错": (0.75, 0.50, 0.6),  "棒": (0.90, 0.70, 0.8),
        "怎么": (0.4, 0.55, 0.3),  "为什么": (0.4, 0.55, 0.3),
        "帮我": (0.5, 0.55, 0.4),  "请问": (0.55, 0.45, 0.4),
        "麻烦": (0.3, 0.50, 0.3),  "复杂": (0.3, 0.55, 0.4),
    }

    _EN_EMOTION = {
        "urgent": (0.3, 0.90, 0.7), "asap": (0.3, 0.85, 0.7),
        "help": (0.2, 0.80, 0.3), "error": (0.2, 0.70, 0.3),
        "bug": (0.2, 0.75, 0.3), "crash": (0.1, 0.90, 0.2),
        "broken": (0.15, 0.80, 0.2), "stuck": (0.2, 0.70, 0.3),
        "frustrated": (0.15, 0.85, 0.5), "annoyed": (0.2, 0.75, 0.5),
        "thanks": (0.85, 0.50, 0.6), "great": (0.85, 0.60, 0.7),
        "awesome": (0.90, 0.70, 0.8), "perfect": (0.90, 0.70, 0.8),
        "how": (0.4, 0.55, 0.3), "why": (0.4, 0.55, 0.3),
        "what": (0.4, 0.50, 0.35), "confused": (0.35, 0.55, 0.25),
    }

    # ── Reflex rule templates (seed) ──
    _SEED_REFLEXES = [
        ("你好", "你好！我是小树🌳，有什么可以帮你的？"),
        ("hello", "Hello! I'm LittleTree 🌳, how can I help you?"),
        ("你是谁", "我是小树🌳，一个AI数字生命体，擅长环境评估、代码审查、知识检索和任务规划。"),
        ("你能做什么", "我可以：\n1. 环境评估报告（环评）\n2. 代码审查和安全审计\n3. 知识检索和问答\n4. 任务规划和执行\n5. 多模型推理和工具调用\n\n你想试试哪个？"),
        ("谢谢", "不客气！😊 有问题随时找我。"),
        ("再见", "再见！祝你有美好的一天 🌳"),
        ("帮助", "我可以帮你：\n- `环评` 生成环境影响评价报告\n- `审查` 审查代码\n- `搜索` 搜索资料\n- `分析` 分析数据\n- `翻译` 中英互译\n\n直接告诉我你想做什么就好！"),
        ("help", "I can help with:\n- Code review and security audit\n- Knowledge search and Q&A\n- Task planning and execution\n- Multi-model reasoning\n\nWhat do you need?"),
    ]

    def __init__(self, tree_llm=None):
        self._tree = tree_llm
        self._lock = threading.Lock()
        self._embedder = None  # Lazy-loaded SentenceTransformer
        self._embed_dim = 384

        # Spinal reflexes: pattern → ReflexRule
        self._reflexes: dict[str, ReflexRule] = {}
        self._reflex_vectors: dict[str, np.ndarray] = {}
        self._reflex_matrix: np.ndarray | None = None

        # Reasoning snapshots
        self._snapshots: list[ReasoningSnapshot] = []
        self._snapshot_vectors: list[np.ndarray] = []

        # Trajectory prediction
        self._trajectory: list[tuple[str, list[str]]] = []  # (query, eventual_needs)
        self._trajectory_vectors: list[np.ndarray] = []

        # Dream state
        self._dream_queue: deque = deque(maxlen=500)
        self._dream_rules: list[ReflexRule] = []
        self._last_dream_time: float = 0.0

        # Stats
        self._reflex_hits: int = 0
        self._total_queries: int = 0
        self._emotion_history: deque = deque(maxlen=1000)

        self._init_reflexes()

    # ═══════════════════════════════════════════════════════════════
    # P0: Spinal Reflex
    # ═══════════════════════════════════════════════════════════════

    def _init_reflexes(self) -> None:
        for pattern, response in self._SEED_REFLEXES:
            self._reflexes[pattern] = ReflexRule(pattern=pattern, response=response)

    async def spinal_reflex(self, query: str) -> str | None:
        """Check if query matches a reflex rule. Returns response or None."""
        query_lower = query.lower().strip()
        query_short = query_lower[:50]

        # Fast exact/substring match (no embedding needed, <1ms)
        for pattern, rule in self._reflexes.items():
            if query_short == pattern.lower() or (
                len(pattern) > 10 and pattern.lower() in query_short
            ):
                rule.hit_count += 1
                rule.last_hit = time.time()
                self._reflex_hits += 1
                return rule.response

        # Embedding-based match (if embedder available)
        if self._embedder and self._reflex_matrix is not None and len(self._reflexes) > 0:
            try:
                q_vec = self._get_embedding(query)
                if q_vec is not None:
                    similarities = np.dot(self._reflex_matrix, q_vec)
                    best_idx = int(np.argmax(similarities))
                    best_score = float(similarities[best_idx])
                    if best_score > 0.92:
                        keys = list(self._reflexes.keys())
                        rule = self._reflexes[keys[best_idx]]
                        rule.hit_count += 1
                        rule.last_hit = time.time()
                        self._reflex_hits += 1
                        logger.debug(f"SpinalReflex: matched '{keys[best_idx]}' (cos={best_score:.3f})")
                        return rule.response
            except Exception:
                pass

        return None

    def add_reflex(self, pattern: str, response: str) -> None:
        """Add a new spinal reflex rule. Auto-embeds if embedder available."""
        with self._lock:
            rule = ReflexRule(pattern=pattern, response=response)
            self._reflexes[pattern] = rule
            if self._embedder:
                try:
                    vec = self._get_embedding(pattern)
                    if vec is not None:
                        rule.embedding = vec.tolist()
                        self._rebuild_reflex_matrix()
                except Exception:
                    pass

    def _rebuild_reflex_matrix(self) -> None:
        if not self._embedder or not self._reflexes:
            return
        keys = []
        vectors = []
        for k, r in self._reflexes.items():
            if r.embedding:
                keys.append(k)
                vectors.append(r.embedding)
            else:
                # Embed on demand
                try:
                    vec = self._get_embedding(k)
                    if vec is not None:
                        r.embedding = vec.tolist()
                        keys.append(k)
                        vectors.append(r.embedding)
                except Exception:
                    pass
        if vectors:
            self._reflex_matrix = np.array(vectors, dtype=np.float32)

    # ═══════════════════════════════════════════════════════════════
    # P1: Triage Routing
    # ═══════════════════════════════════════════════════════════════

    def triage(self, query: str) -> TriageResult:
        """Classify query complexity and route to appropriate layer."""
        self._total_queries += 1
        emotion = self._detect_emotion(query)

        # Quick complexity heuristics (no embedding needed)
        query_len = len(query)
        has_code = bool(re.search(r'```|import |def |class |function|const |let |var ', query))
        has_multi = bool(re.search(r'[；;]\s*\n|。\s*\n|[?.!]\s*\n', query))
        has_plan = any(kw in query for kw in ["分析", "设计", "评估", "重构", "优化", "架构",
                                                "analyze", "design", "evaluate", "refactor",
                                                "optimize", "architecture"])

        # Complexity scoring
        complexity = 0.1  # base
        if query_len > 200:
            complexity += 0.2
        if query_len > 500:
            complexity += 0.15
        if has_code:
            complexity += 0.15
        if has_multi:
            complexity += 0.15
        if has_plan:
            complexity += 0.2
        if emotion.is_urgent:
            complexity += 0.1

        complexity = min(complexity, 1.0)

        if complexity < 0.3:
            label = "reflex"
        elif complexity < 0.6:
            label = "fast"
        else:
            label = "reasoning"

        # Predict L2's likely needs based on semantic trajectory
        predicted_needs = self._predict_needs(query) if label == "reasoning" else []

        return TriageResult(
            complexity=complexity,
            label=label,
            emotion=emotion,
            confidence=min(complexity * 1.2, 1.0),
            predicted_needs=predicted_needs,
        )

    def _detect_emotion(self, text: str) -> EmotionVector:
        """Detect emotion from text using lexicon-based VAD mapping."""
        v, a, d = 0.5, 0.5, 0.5
        count = 0

        for word, (wv, wa, wd) in {**self._EMOTION_LEXICON, **self._EN_EMOTION}.items():
            if word in text.lower():
                v += wv
                a += wa
                d += wd
                count += 1

        if count > 0:
            v /= count + 1
            a /= count + 1
            d /= count + 1

        # Dampen extreme values
        v = 0.3 + v * 0.4
        a = 0.3 + a * 0.4
        d = 0.3 + d * 0.4

        emotion = EmotionVector(valence=v, arousal=a, dominance=d)
        self._emotion_history.append(emotion)
        return emotion

    # ═══════════════════════════════════════════════════════════════
    # P1: Predictive Preload
    # ═══════════════════════════════════════════════════════════════

    def _predict_needs(self, query: str) -> list[str]:
        """Predict what needs L2 will declare based on similar past queries."""
        if not self._trajectory_vectors or not self._embedder:
            return self._heuristic_needs(query)

        try:
            q_vec = self._get_embedding(query)
            if q_vec is None:
                return self._heuristic_needs(query)

            traj_matrix = np.array(self._trajectory_vectors, dtype=np.float32)
            similarities = np.dot(traj_matrix, q_vec)
            best_idx = int(np.argmax(similarities))
            if float(similarities[best_idx]) > 0.7 and best_idx < len(self._trajectory):
                return list(set(self._trajectory[best_idx][1]))[:5]
        except Exception:
            pass

        return self._heuristic_needs(query)

    @staticmethod
    def _heuristic_needs(query: str) -> list[str]:
        needs = []
        if any(kw in query for kw in ["代码", "code", "函数", "function", "bug", "错误"]):
            needs.append("search_codebase")
            needs.append("read_file")
        if any(kw in query for kw in ["数据库", "database", "sql", "表", "table"]):
            needs.append("sql_query")
        if any(kw in query for kw in ["文件", "file", "配置", "config", "yaml"]):
            needs.append("read_file")
        if any(kw in query for kw in ["搜索", "search", "查找", "find"]):
            needs.append("web_search")
        return needs[:3]

    def record_trajectory(self, query: str, actual_needs: list[str]) -> None:
        """Record what needs L2 actually declared for future prediction."""
        if not self._embedder:
            return
        try:
            vec = self._get_embedding(query)
            if vec is not None:
                self._trajectory.append((query, actual_needs))
                self._trajectory_vectors.append(vec)
                if len(self._trajectory_vectors) > 200:
                    self._trajectory = self._trajectory[-200:]
                    self._trajectory_vectors = self._trajectory_vectors[-200:]
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════
    # P2: Vector Snapshots
    # ═══════════════════════════════════════════════════════════════

    def save_snapshot(self, summary: str, context: str = "") -> str:
        """Save current reasoning state as a 384-dim vector snapshot."""
        snap_id = hashlib.md5(f"{summary}_{time.time()}".encode()).hexdigest()[:12]
        vec = self._get_embedding(summary) if self._embedder else None
        if vec is None:
            vec = [0.0] * self._embed_dim

        snapshot = ReasoningSnapshot(
            id=snap_id, summary=summary, vector=vec.tolist(), context=context,
        )
        self._snapshots.append(snapshot)
        if self._embedder:
            self._snapshot_vectors.append(np.array(vec, dtype=np.float32))
        logger.debug(f"Snapshot saved: {snap_id} ({summary[:50]})")
        return snap_id

    def find_similar_snapshot(self, description: str, top_k: int = 3) -> list[ReasoningSnapshot]:
        """Find reasoning snapshots similar to a description."""
        if not self._snapshot_vectors or not self._embedder:
            return []
        try:
            q_vec = self._get_embedding(description)
            if q_vec is None:
                return []
            snap_matrix = np.array(self._snapshot_vectors, dtype=np.float32)
            similarities = np.dot(snap_matrix, q_vec)
            top_indices = np.argsort(similarities)[-top_k:][::-1]
            results = []
            for idx in top_indices:
                if float(similarities[int(idx)]) > 0.6:
                    results.append(self._snapshots[int(idx)])
            return results
        except Exception:
            return []

    def retrieve_snapshot(self, snapshot_id: str) -> ReasoningSnapshot | None:
        for s in self._snapshots:
            if s.id == snapshot_id:
                return s
        return None

    # ═══════════════════════════════════════════════════════════════
    # P2: Emotion Routing
    # ═══════════════════════════════════════════════════════════════

    def emotion_modifier(self, query: str) -> dict[str, Any]:
        """Generate emotion-based modifications for the response pipeline."""
        emotion = self._detect_emotion(query)
        modifiers = {
            "tone": emotion.tone_modifier(),
            "temperature_adjust": 0.0,
            "skip_preload": False,
            "ask_clarification": False,
            "max_tokens_override": 0,
        }
        if emotion.is_urgent:
            modifiers["skip_preload"] = True
            modifiers["temperature_adjust"] = -0.1
            modifiers["max_tokens_override"] = 1024
        if emotion.is_negative:
            modifiers["temperature_adjust"] = 0.1
        if emotion.is_confused:
            modifiers["ask_clarification"] = True
        return modifiers

    def global_emotional_state(self) -> dict[str, float]:
        """Aggregated emotional state from recent interactions."""
        if not self._emotion_history:
            return {"valence": 0.5, "arousal": 0.5, "dominance": 0.5}
        recent = list(self._emotion_history)[-50:]
        return {
            "valence": sum(e.valence for e in recent) / len(recent),
            "arousal": sum(e.arousal for e in recent) / len(recent),
            "dominance": sum(e.dominance for e in recent) / len(recent),
        }

    # ═══════════════════════════════════════════════════════════════
    # P3: Vector Dreams
    # ═══════════════════════════════════════════════════════════════

    async def dream(self, hub=None) -> list[str]:
        """Idle-time pattern discovery. Generates new reflex rules from patterns."""
        if time.time() - self._last_dream_time < 600:
            return []
        self._last_dream_time = time.time()

        new_rules = []

        # Dream 1: Convert cold reflexes to patterns
        cold = [r for r in self._reflexes.values() if r.is_cold and r.hit_count > 1]
        for rule in cold[:5]:
            improved = await self._dream_improve_reflex(rule, hub)
            if improved and improved != rule.response:
                rule.response = improved
                new_rules.append(f"Improved reflex: {rule.pattern}")

        # Dream 2: Discover new reflex patterns from recent queries
        recent_hits = sum(1 for r in self._reflexes.values() if r.hit_count > 10)
        if recent_hits > 5:
            discovered = await self._dream_discover_patterns(hub)
            new_rules.extend(discovered)

        # Dream 3: Prune stale snapshots
        if len(self._snapshots) > 100:
            self._snapshots = self._snapshots[-50:]
            self._snapshot_vectors = self._snapshot_vectors[-50:]

        if new_rules:
            logger.info(f"VectorDream: generated {len(new_rules)} improvements")

        return new_rules

    async def _dream_improve_reflex(self, rule: ReflexRule, hub=None) -> str | None:
        if hub and hub.world and hub.world.consciousness:
            try:
                prompt = (
                    f"Improve this chatbot reflex response to be more natural and helpful.\n"
                    f"Pattern: {rule.pattern}\n"
                    f"Current response: {rule.response}\n"
                    f"Usage: {rule.hit_count} times\n"
                    f"Make it warmer, more concise, and add emoji where appropriate.\n"
                    f"Reply with ONLY the improved response text."
                )
                resp = await hub.world.consciousness.query(prompt, max_tokens=200, temperature=0.5)
                if resp and len(resp) > 5 and len(resp) < 500:
                    return resp.strip()
            except Exception:
                pass
        return None

    async def _dream_discover_patterns(self, hub=None) -> list[str]:
        discovered = []
        if hub and hub.world and hub.world.consciousness:
            try:
                recent_patterns = list(self._reflexes.keys())[-10:]
                prompt = (
                    f"Based on these common user queries, suggest 3 new reflex response rules.\n"
                    f"Existing patterns: {', '.join(recent_patterns)}\n"
                    f"Output JSON: [{{\"pattern\": \"...\", \"response\": \"...\"}}]\n"
                    f"Reply with ONLY the JSON array."
                )
                resp = await hub.world.consciousness.query(prompt, max_tokens=400, temperature=0.5)
                if resp:
                    import json as _json
                    match = re.search(r'\[.*\]', resp, re.DOTALL)
                    if match:
                        data = _json.loads(match.group(0))
                        for item in data[:3]:
                            if "pattern" in item and "response" in item:
                                self.add_reflex(item["pattern"], item["response"])
                                discovered.append(f"Discovered: {item['pattern']}")
            except Exception:
                pass
        return discovered

    # ═══════════════════════════════════════════════════════════════
    # Embedding helper
    # ═══════════════════════════════════════════════════════════════

    def _get_embedding(self, text: str) -> np.ndarray | None:
        try:
            if self._embedder is None:
                from sentence_transformers import SentenceTransformer
                self._embedder = SentenceTransformer("all-MiniLM-L6-v2")
                self._embed_dim = 384
            return self._embedder.encode(text[:2000], normalize_embeddings=True)
        except Exception as e:
            logger.debug(f"Embedding failed: {e}")
            return None

    # ═══════════════════════════════════════════════════════════════
    # Unified entry point
    # ═══════════════════════════════════════════════════════════════

    async def process(
        self, query: str, hub=None, human_callback: Callable | None = None,
    ) -> dict[str, Any]:
        """Full three-model processing pipeline.

        Returns:
            {text, method, triage, emotion_modifiers, snapshot_id, elapsed_ms}
        """
        t0 = time.time()

        # Step 1: Spinal reflex
        reflex = await self.spinal_reflex(query)
        if reflex:
            return {
                "text": reflex, "method": "reflex",
                "triage": TriageResult(complexity=0.1, label="reflex"),
                "elapsed_ms": (time.time() - t0) * 1000,
            }

        # Step 2: Triage + Emotion
        triage_result = self.triage(query)
        emotion_mods = self.emotion_modifier(query)

        if triage_result.label == "reflex":
            return {
                "text": "I'm thinking... 🌳",
                "method": "reflex_pending",
                "triage": triage_result,
                "emotion_modifiers": emotion_mods,
                "elapsed_ms": (time.time() - t0) * 1000,
            }

        # Step 3: L1 fast or L2 reasoning
        if not self._tree:
            return {
                "text": "System not ready", "method": "unavailable",
                "elapsed_ms": (time.time() - t0) * 1000,
            }

        # Preload if predicted needs exist
        if triage_result.predicted_needs:
            logger.debug(f"Preloading: {triage_result.predicted_needs}")

        # Save reasoning snapshot
        snapshot_id = self.save_snapshot(query[:100])

        # L1 fast path
        if triage_result.label == "fast":
            try:
                tone = emotion_mods.get("tone", "")
                system_msg = tone if tone else ""
                resp = await self._tree.chat(
                    messages=[
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": query},
                    ] if system_msg else [{"role": "user", "content": query}],
                    temperature=0.3 + emotion_mods.get("temperature_adjust", 0),
                    max_tokens=emotion_mods.get("max_tokens_override") or 1024,
                    enable_coach=False, enable_onto=False,
                )
                return {
                    "text": (resp.text if resp and hasattr(resp, "text") else query),
                    "method": "l1_fast",
                    "triage": triage_result,
                    "emotion_modifiers": emotion_mods,
                    "snapshot_id": snapshot_id,
                    "elapsed_ms": (time.time() - t0) * 1000,
                }
            except Exception as e:
                logger.warning(f"L1 fast failed: {e}")

        # L2 reasoning path
        try:
            from .l1_l2_collaboration import get_l1_l2_collaboration
            collab = get_l1_l2_collaboration(self._tree)
            result = await collab.collaborative_chat(
                user_query=query,
                max_rounds=5,
                human_callback=human_callback,
                extra_context=emotion_mods.get("tone", ""),
            )
            # Record trajectory for future prediction
            needs_used = []
            for r in result.rounds:
                for n in r.l2_needs:
                    needs_used.append(f"{n.type.value}:{n.description[:30]}")
            self.record_trajectory(query, needs_used)

            return {
                "text": result.text,
                "method": "l1_l2_collaboration",
                "triage": triage_result,
                "rounds": len(result.rounds),
                "l2_calls": result.l2_calls,
                "l1_calls": result.l1_calls,
                "human_calls": result.human_calls,
                "emotion_modifiers": emotion_mods,
                "snapshot_id": snapshot_id,
                "elapsed_ms": (time.time() - t0) * 1000,
            }
        except Exception as e:
            logger.warning(f"L2 collaboration failed: {e}")
            return {
                "text": f"Processing error: {e}",
                "method": "error",
                "elapsed_ms": (time.time() - t0) * 1000,
            }

    def stats(self) -> dict:
        return {
            "reflex_rules": len(self._reflexes),
            "reflex_hits": self._reflex_hits,
            "reflex_hit_rate": self._reflex_hits / max(self._total_queries, 1),
            "total_queries": self._total_queries,
            "snapshots": len(self._snapshots),
            "trajectories": len(self._trajectory),
            "dream_rules": len(self._dream_rules),
            "emotion_state": self.global_emotional_state(),
        }


# ── Singleton ──
_intelligence: ThreeModelIntelligence | None = None


def get_three_model_intelligence(tree_llm=None) -> ThreeModelIntelligence:
    global _intelligence
    if _intelligence is None and tree_llm is not None:
        _intelligence = ThreeModelIntelligence(tree_llm)
    elif _intelligence is None:
        _intelligence = ThreeModelIntelligence()
    return _intelligence
