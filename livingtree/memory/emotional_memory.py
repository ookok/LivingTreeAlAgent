"""Emotional Memory — weights knowledge retrieval by emotional significance.

Simulates human "flashbulb memory": highly emotional events are remembered
more vividly and recalled more easily. Integrates with anime_persona.py for
emotional tone and user_model.py for preference recall.

Core concepts:
  - Plutchik's wheel: 8 basic emotions as a continuous vector space
  - Flashbulb memory: high-intensity events decay slower (Ebbinghaus curve)
  - Emotional retrieval: semantic similarity × 0.6 + emotional intensity × 0.4
  - LTP/LTD plasticity: reinforce/weaken emotional associations over time
  - Primary dyads: joy+trust=love, sadness+disgust=remorse, etc.

Reference:
  Plutchik, R. (2001). The Nature of Emotions. American Scientist.
  Ebbinghaus, H. (1885). Über das Gedächtnis.
"""

from __future__ import annotations

import bisect
import json
import math
import os
import re
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from loguru import logger

# ═══ Persistence ═══

EMOTIONAL_MEMORY_FILE = Path(".livingtree/emotional_memory.json")
EMOTIONAL_MEMORY_DIR = Path(".livingtree")


# ═══ Plutchik's Wheel: 8 Basic Emotions ═══

class EmotionType(str, Enum):
    JOY = "joy"                   # 快乐
    SURPRISE = "surprise"         # 惊讶
    SADNESS = "sadness"           # 悲伤
    FEAR = "fear"                 # 恐惧
    ANGER = "anger"               # 愤怒
    DISGUST = "disgust"           # 厌恶
    TRUST = "trust"               # 信任
    ANTICIPATION = "anticipation" # 期待


# Emotion ordering consistent with Plutchik's wheel (adjacent = similar)
EMOTION_ORDER: list[EmotionType] = [
    EmotionType.JOY,
    EmotionType.TRUST,
    EmotionType.FEAR,
    EmotionType.SURPRISE,
    EmotionType.SADNESS,
    EmotionType.DISGUST,
    EmotionType.ANGER,
    EmotionType.ANTICIPATION,
]

# Positive / negative valence mapping
_POSITIVE_EMOTIONS = {EmotionType.JOY, EmotionType.TRUST, EmotionType.ANTICIPATION}
_NEGATIVE_EMOTIONS = {EmotionType.SADNESS, EmotionType.FEAR, EmotionType.ANGER, EmotionType.DISGUST}
_NEUTRAL_EMOTIONS = {EmotionType.SURPRISE}

# Plutchik's wheel angle for each emotion (radians, for vector ops)
_EMOTION_ANGLE: dict[EmotionType, float] = {
    EmotionType.JOY:          0.0,
    EmotionType.TRUST:        math.pi / 4,
    EmotionType.FEAR:         math.pi / 2,
    EmotionType.SURPRISE:     3 * math.pi / 4,
    EmotionType.SADNESS:      math.pi,
    EmotionType.DISGUST:      5 * math.pi / 4,
    EmotionType.ANGER:        3 * math.pi / 2,
    EmotionType.ANTICIPATION: 7 * math.pi / 4,
}


# ═══ Emotion Vector ═══

@dataclass
class EmotionVector:
    """8-dimensional emotion vector (0-1 values for each Plutchik emotion).

    Properties:
        dominant_emotion: highest-intensity emotion
        intensity: L2 magnitude of the vector (0-1)
        valence: positive - negative intensity sum (-1 to +1)
    """
    joy: float = 0.0
    trust: float = 0.0
    fear: float = 0.0
    surprise: float = 0.0
    sadness: float = 0.0
    disgust: float = 0.0
    anger: float = 0.0
    anticipation: float = 0.0

    def as_list(self) -> list[float]:
        return [
            self.joy, self.trust, self.fear, self.surprise,
            self.sadness, self.disgust, self.anger, self.anticipation,
        ]

    def as_dict(self) -> dict[str, float]:
        return {
            "joy": self.joy, "trust": self.trust, "fear": self.fear,
            "surprise": self.surprise, "sadness": self.sadness,
            "disgust": self.disgust, "anger": self.anger,
            "anticipation": self.anticipation,
        }

    @classmethod
    def from_dict(cls, d: dict[str, float]) -> EmotionVector:
        return cls(
            joy=d.get("joy", 0), trust=d.get("trust", 0),
            fear=d.get("fear", 0), surprise=d.get("surprise", 0),
            sadness=d.get("sadness", 0), disgust=d.get("disgust", 0),
            anger=d.get("anger", 0), anticipation=d.get("anticipation", 0),
        )

    @classmethod
    def from_list(cls, values: list[float]) -> EmotionVector:
        padded = (values + [0.0] * 8)[:8]
        return cls(*padded)

    @classmethod
    def zero(cls) -> EmotionVector:
        return cls()

    @property
    def dominant_emotion(self) -> EmotionType:
        values = self.as_list()
        idx = max(range(8), key=lambda i: values[i])
        return EMOTION_ORDER[idx]

    @property
    def intensity(self) -> float:
        return min(1.0, math.sqrt(sum(v * v for v in self.as_list())))

    @property
    def valence(self) -> float:
        pos = self.joy + self.trust + self.anticipation
        neg = self.sadness + self.fear + self.anger + self.disgust
        total = pos + neg + 1e-8
        return (pos - neg) / total

    def dominate(self, emotion: EmotionType, value: float = 1.0) -> EmotionVector:
        """Set one emotion to value and suppress others to 0."""
        d = {e.value: 0.0 for e in EmotionType}
        d[emotion.value] = max(0.0, min(1.0, value))
        return EmotionVector(**d)

    @staticmethod
    def blend(a: EmotionVector, b: EmotionVector, weight_b: float = 0.5) -> EmotionVector:
        """Weighted blend of two emotion vectors."""
        w = max(0.0, min(1.0, weight_b))
        return EmotionVector(
            joy=a.joy * (1 - w) + b.joy * w,
            trust=a.trust * (1 - w) + b.trust * w,
            fear=a.fear * (1 - w) + b.fear * w,
            surprise=a.surprise * (1 - w) + b.surprise * w,
            sadness=a.sadness * (1 - w) + b.sadness * w,
            disgust=a.disgust * (1 - w) + b.disgust * w,
            anger=a.anger * (1 - w) + b.anger * w,
            anticipation=a.anticipation * (1 - w) + b.anticipation * w,
        )


# ═══ Plutchik Primary Dyads (emotion blending rules) ═══

PLUTCHIK_DYADS: dict[tuple[EmotionType, EmotionType], str] = {
    (EmotionType.JOY, EmotionType.TRUST): "love",
    (EmotionType.TRUST, EmotionType.FEAR): "submission",
    (EmotionType.FEAR, EmotionType.SURPRISE): "awe",
    (EmotionType.SURPRISE, EmotionType.SADNESS): "disappointment",
    (EmotionType.SADNESS, EmotionType.DISGUST): "remorse",
    (EmotionType.DISGUST, EmotionType.ANGER): "contempt",
    (EmotionType.ANGER, EmotionType.ANTICIPATION): "aggressiveness",
    (EmotionType.ANTICIPATION, EmotionType.JOY): "optimism",
    # Reverse pairs
    (EmotionType.TRUST, EmotionType.JOY): "love",
    (EmotionType.FEAR, EmotionType.TRUST): "submission",
    (EmotionType.SURPRISE, EmotionType.FEAR): "awe",
    (EmotionType.SADNESS, EmotionType.SURPRISE): "disappointment",
    (EmotionType.DISGUST, EmotionType.SADNESS): "remorse",
    (EmotionType.ANGER, EmotionType.DISGUST): "contempt",
    (EmotionType.ANTICIPATION, EmotionType.ANGER): "aggressiveness",
    (EmotionType.JOY, EmotionType.ANTICIPATION): "optimism",
}


def dyad_name(a: EmotionType, b: EmotionType) -> str:
    """Get Plutchik primary dyad name for two emotions."""
    return PLUTCHIK_DYADS.get((a, b), "complex")


def dyad_vector(a: EmotionType, b: EmotionType) -> EmotionVector:
    """Create blended emotion vector for two adjacent emotions on the wheel."""
    v = EmotionVector.zero()
    setattr(v, a.value, 0.6)
    setattr(v, b.value, 0.6)
    return v


# ═══ Emotion Detection: Keyword Heuristic ═══

EMOTION_KEYWORDS: dict[EmotionType, list[str]] = {
    EmotionType.JOY: [
        "开心", "高兴", "快乐", "太好了", "哈哈", "嘻嘻", "棒", "赞",
        "喜欢", "爱", "幸福", "满足", "庆祝", "恭喜", "优秀", "厉害",
        "happy", "joy", "love", "great", "awesome", "wonderful", "excellent",
        "amazing", "fantastic", "yay", "woohoo", "glad", "delighted",
        "bright", "beautiful", "lovely", "cheerful", "blessed", "grateful",
    ],
    EmotionType.SURPRISE: [
        "惊讶", "居然", "天哪", "真的吗", "没想到", "意外", "突然",
        "哇", "噢", "什么!", "惊人", "不可思议", "难以置信",
        "wow", "surprise", "unexpected", "whoa", "omg", "incredible",
        "unbelievable", "astonishing", "shocking", "what", "really",
    ],
    EmotionType.SADNESS: [
        "难过", "伤心", "悲伤", "哭泣", "流泪", "失望", "遗憾",
        "痛苦", "孤独", "寂寞", "怀念", "可惜", "唉", "郁闷",
        "sad", "unhappy", "depressed", "cry", "tears", "sorrow",
        "grief", "lonely", "miss", "disappointed", "regret",
    ],
    EmotionType.FEAR: [
        "害怕", "恐惧", "担心", "担忧", "紧张", "焦虑", "不安",
        "惊慌", "恐怖", "吓人", "可怕", "胆怯", "恐慌",
        "fear", "scared", "afraid", "terrified", "anxious", "worried",
        "nervous", "panic", "horror", "dread", "frightened",
    ],
    EmotionType.ANGER: [
        "生气", "愤怒", "恼火", "讨厌", "烦", "可恶", "混蛋",
        "滚", "操", "妈的", "气死", "怒", "火大", "暴躁",
        "angry", "mad", "furious", "annoyed", "irritated", "rage",
        "hate", "frustrated", "pissed", "outraged",
    ],
    EmotionType.DISGUST: [
        "恶心", "厌恶", "讨厌", "反感", "嫌弃", "肮脏", "丑陋",
        "disgust", "gross", "disgusting", "yuck", "eww", "revolting",
        "nasty", "awful", "terrible",
    ],
    EmotionType.TRUST: [
        "相信", "信任", "靠谱", "可靠", "依赖", "放心", "真诚",
        "坦诚", "忠实", "信赖", "信心", "信念",
        "trust", "reliable", "dependable", "honest", "faith", "confident",
        "believe", "confidence", "loyal",
    ],
    EmotionType.ANTICIPATION: [
        "期待", "盼望", "希望", "展望", "即将", "准备", "计划",
        "未来", "憧憬", "向往", "等待", "好奇", "探索",
        "expect", "anticipate", "hope", "looking forward", "curious",
        "excited for", "future", "planning", "soon", "upcoming",
    ],
}


def detect_emotion(text: str) -> EmotionVector:
    """Heuristic emotion detection from text using keyword matching.

    Matches Chinese and English keywords against input text. Returns
    an 8-dim emotion vector with scores proportional to keyword hits.
    """
    text_lower = text.lower()
    values: dict[EmotionType, float] = {e: 0.0 for e in EmotionType}

    for emotion, keywords in EMOTION_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in text_lower)
        if hits > 0:
            values[emotion] = min(1.0, hits * 0.25)

    total = sum(values.values())
    if total > 0:
        for e in EmotionType:
            values[e] /= total

    return EmotionVector(**{e.value: values[e] for e in EmotionType})


# ═══ Emotional Memory Entry ═══

@dataclass
class EmotionalMemory:
    """A single memory entry with emotional tagging and decay tracking.

    Implements Ebbinghaus forgetting curve: intensity decays exponentially
    over time, but high-emotion memories decay slower (flashbulb effect).

    Attributes:
        memory_id: unique identifier
        content: memory text content
        emotion_vector: 8-dim Plutchik emotion vector
        emotional_intensity: raw intensity at creation time (0-1)
        created_at: POSIX timestamp of creation
        last_recalled: POSIX timestamp of last recall
        recall_count: how many times recalled
        decay_lambda: decay rate (lower = slower decay, flashbulb)
    """
    memory_id: str
    content: str
    emotion_vector: EmotionVector = field(default_factory=EmotionVector.zero)
    emotional_intensity: float = 0.0
    created_at: float = field(default_factory=time.time)
    last_recalled: float = 0.0
    recall_count: int = 0
    decay_lambda: float = 0.05

    @property
    def age_hours(self) -> float:
        return (time.time() - self.created_at) / 3600.0

    @property
    def hours_since_recall(self) -> float:
        ref = self.last_recalled or self.created_at
        return max(0.0, (time.time() - ref) / 3600.0)

    @property
    def decayed_intensity(self) -> float:
        """Ebbinghaus forgetting curve: I(t) = I₀ × e^(-λt).

        High-emotion memories have slower λ (flashbulb effect).
        """
        lam = self.decay_lambda
        if self.emotional_intensity > 0.7:
            lam *= 0.3  # Flashbulb: 3x slower decay
        elif self.emotional_intensity > 0.4:
            lam *= 0.6
        return self.emotional_intensity * math.exp(-lam * self.hours_since_recall)

    def mark_recalled(self) -> None:
        self.recall_count += 1
        self.last_recalled = time.time()

    def to_dict(self) -> dict:
        return {
            "memory_id": self.memory_id,
            "content": self.content,
            "emotion_vector": self.emotion_vector.as_dict(),
            "emotional_intensity": self.emotional_intensity,
            "created_at": self.created_at,
            "last_recalled": self.last_recalled,
            "recall_count": self.recall_count,
            "decay_lambda": self.decay_lambda,
        }

    @classmethod
    def from_dict(cls, d: dict) -> EmotionalMemory:
        return cls(
            memory_id=d["memory_id"],
            content=d["content"],
            emotion_vector=EmotionVector.from_dict(d.get("emotion_vector", {})),
            emotional_intensity=d.get("emotional_intensity", 0.0),
            created_at=d.get("created_at", time.time()),
            last_recalled=d.get("last_recalled", 0.0),
            recall_count=d.get("recall_count", 0),
            decay_lambda=d.get("decay_lambda", 0.05),
        )


# ═══ Emotional Memory Store ═══

class EmotionalMemoryStore:
    """Stores and retrieves memories weighted by emotional significance.

    Key mechanisms:
      1. Flashbulb effect: high-intensity events decay slower
      2. Emotional retrieval: semantic_similarity × 0.6 + emotional_intensity × 0.4
      3. LTP/LTD plasticity: reinforce/weaken emotional associations
      4. Plutchik dyad blending: merge adjacent emotions into complex feelings
      5. Emotional context: aggregated emotional state from recent interactions

    Integration:
      - anime_persona.py: emotional tone for avatar expression
      - user_model.py: preference recall weighted by emotional significance
    """

    MAX_MEMORIES = 2000
    DEFAULT_DECAY_LAMBDA = 0.05
    EMOTIONAL_CTX_WINDOW_HOURS = 2.0

    def __init__(self):
        self._memories: dict[str, EmotionalMemory] = {}
        self._next_id: int = 0
        self._lock = threading.RLock()
        self._load()

    # ── Storage ──

    def store(self, content: str, emotion_vector: EmotionVector = None) -> str:
        """Store a memory with emotional tagging.

        Args:
            content: the memory text
            emotion_vector: 8-dim Plutchik emotion vector (auto-detected if None)

        Returns:
            memory_id of the stored memory
        """
        with self._lock:
            if emotion_vector is None:
                emotion_vector = detect_emotion(content)

            intensity = emotion_vector.intensity
            decay_lambda = self.DEFAULT_DECAY_LAMBDA

            self._next_id += 1
            mem_id = f"em_{self._next_id:06d}"

            memory = EmotionalMemory(
                memory_id=mem_id,
                content=content,
                emotion_vector=emotion_vector,
                emotional_intensity=intensity,
                decay_lambda=decay_lambda,
            )
            self._memories[mem_id] = memory

            # Enforce max capacity: remove lowest decayed-intensity
            if len(self._memories) > self.MAX_MEMORIES:
                sorted_ids = sorted(
                    self._memories.keys(),
                    key=lambda mid: self._memories[mid].decayed_intensity,
                )
                for mid in sorted_ids[:len(self._memories) - self.MAX_MEMORIES]:
                    del self._memories[mid]

            logger.debug(
                "EmotionalMemory: stored %s (intensity=%.2f, dominant=%s)",
                mem_id, intensity, emotion_vector.dominant_emotion.value,
            )
            self._save()
            return mem_id

    # ── Recall ──

    def recall(self, query: str, top_k: int = 10) -> list[EmotionalMemory]:
        """Retrieve memories weighted by emotional significance.

        Score = semantic_similarity × 0.6 + emotional_intensity × 0.4

        Args:
            query: search query
            top_k: number of results to return

        Returns:
            List of EmotionalMemory sorted by combined relevance score
        """
        with self._lock:
            if not self._memories:
                return []

            query_emotion = detect_emotion(query)
            query_chars = set(query.lower().replace(" ", ""))
            results: list[tuple[float, EmotionalMemory]] = []

            for memory in self._memories.values():
                # Semantic similarity via character trigram Jaccard
                sem_sim = self._semantic_similarity(query, memory.content)

                # Emotional similarity via cosine of emotion vectors
                emo_sim = self._emotion_similarity(query_emotion, memory.emotion_vector)

                # Decayed intensity as recency/importance boost
                dec_int = memory.decayed_intensity

                # Combined score
                score = sem_sim * 0.6 + (emo_sim * 0.5 + dec_int * 0.5) * 0.4

                if score > 0.01:
                    results.append((score, memory))

            results.sort(key=lambda x: -x[0])
            top = [mem for _, mem in results[:top_k]]

            for mem in top:
                mem.mark_recalled()

            logger.debug(
                "EmotionalMemory: recall '%s' → %d results (top_score=%.3f)",
                query[:40], len(top), results[0][0] if results else 0,
            )
            return top

    # ── Plasticity: LTP / LTD ──

    def reinforce(self, memory_id: str, emotion_delta: float) -> bool:
        """Strengthen (LTP) or weaken (LTD) emotional association.

        Positive delta → LTP (long-term potentiation): intensity increases.
        Negative delta → LTD (long-term depression): intensity decreases.
        """
        with self._lock:
            memory = self._memories.get(memory_id)
            if not memory:
                return False

            old_intensity = memory.emotional_intensity
            memory.emotional_intensity = max(0.0, min(1.0, old_intensity + emotion_delta))
            memory.decay_lambda = max(0.01, min(0.2, memory.decay_lambda - emotion_delta * 0.01))

            logger.debug(
                "EmotionalMemory: reinforce %s intensity %.3f→%.3f (Δ=%.3f)",
                memory_id, old_intensity, memory.emotional_intensity, emotion_delta,
            )
            self._save()
            return True

    # ── Flashbulb ──

    def get_flashbulbs(self, limit: int = 5) -> list[EmotionalMemory]:
        """Return the highest emotional intensity memories (flashbulbs)."""
        with self._lock:
            sorted_mems = sorted(
                self._memories.values(),
                key=lambda m: -m.emotional_intensity,
            )
            return sorted_mems[:limit]

    # ── Decay ──

    def decay_all(self) -> dict[str, float]:
        """Apply Ebbinghaus forgetting curve to all memories.

        Removes memories that have decayed below threshold (intensity < 0.01).
        High-emotion memories decay slower (flashbulb preservation).

        Returns stats dict.
        """
        with self._lock:
            removed = []
            remaining_intensities = []

            for mem_id in list(self._memories.keys()):
                memory = self._memories[mem_id]
                decayed = memory.decayed_intensity
                if decayed < 0.01:
                    removed.append(mem_id)
                    del self._memories[mem_id]
                else:
                    remaining_intensities.append(decayed)

            if removed:
                self._save()

            stats = {
                "total": len(self._memories) + len(removed),
                "remaining": len(self._memories),
                "removed": len(removed),
                "avg_decayed_intensity": (
                    sum(remaining_intensities) / max(len(remaining_intensities), 1)
                ),
            }
            logger.debug(
                "EmotionalMemory: decay → removed=%d, remaining=%d, avg_int=%.3f",
                stats["removed"], stats["remaining"], stats["avg_decayed_intensity"],
            )
            return stats

    # ── Emotional Context ──

    def emotional_context(self) -> EmotionVector:
        """Aggregate current emotional state from recent interactions.

        Weights recent memories (within EMOTIONAL_CTX_WINDOW_HOURS) by
        their decayed intensity to produce a composite emotional context.
        """
        with self._lock:
            now = time.time()
            window = self.EMOTIONAL_CTX_WINDOW_HOURS * 3600
            recent = [
                m for m in self._memories.values()
                if (now - m.created_at) < window
            ]

            if not recent:
                return EmotionVector.zero()

            # Weight by decayed intensity
            total_weight = sum(m.decayed_intensity for m in recent) + 1e-8

            ctx = EmotionVector.zero()
            for m in recent:
                w = m.decayed_intensity / total_weight
                ctx = EmotionVector.blend(ctx, m.emotion_vector, w)

            return ctx

    # ── Emotion Blending: Plutchik Dyads ──

    def merge_emotion(self, memory_id: str, new_emotion: EmotionVector) -> bool:
        """Blend a new emotion into an existing memory.

        If the memory's dominant emotion and the new dominant emotion are
        adjacent on Plutchik's wheel, the result is the primary dyad
        (e.g., joy + trust = love).

        Args:
            memory_id: target memory
            new_emotion: incoming emotion vector to blend in

        Returns:
            True if successfully merged, False if memory not found
        """
        with self._lock:
            memory = self._memories.get(memory_id)
            if not memory:
                return False

            old_dom = memory.emotion_vector.dominant_emotion
            new_dom = new_emotion.dominant_emotion

            # Blend vectors (weighted toward existing memory)
            blended = EmotionVector.blend(memory.emotion_vector, new_emotion, 0.35)

            # Check Plutchik adjacency for dyad naming
            dyad = dyad_name(old_dom, new_dom)
            if dyad != "complex":
                # Apply dyad vector as additional blending component
                dyad_vec = dyad_vector(old_dom, new_dom)
                blended = EmotionVector.blend(blended, dyad_vec, 0.3)
                logger.debug(
                    "EmotionalMemory: merge %s → dyad '%s' (%s + %s)",
                    memory_id, dyad, old_dom.value, new_dom.value,
                )

            memory.emotion_vector = blended
            memory.emotional_intensity = max(
                memory.emotional_intensity,
                blended.intensity,
            )
            memory.last_recalled = time.time()
            self._save()
            return True

    # ── Stats ──

    def stats(self) -> dict[str, Any]:
        """Return statistics about the emotional memory store."""
        with self._lock:
            mems = self._memories
            total = len(mems)
            if total == 0:
                return {
                    "total_memories": 0,
                    "avg_intensity": 0.0,
                    "dominant_emotion": "none",
                    "flashbulb_count": 0,
                    "avg_recall_count": 0.0,
                    "valence_distribution": {},
                }

            intensities = [m.emotional_intensity for m in mems.values()]
            avg_intensity = sum(intensities) / total
            flashbulbs = sum(1 for i in intensities if i > 0.7)

            # Dominant emotion across all memories
            emotion_counts: dict[str, int] = {}
            for m in mems.values():
                dom = m.emotion_vector.dominant_emotion.value
                emotion_counts[dom] = emotion_counts.get(dom, 0) + 1
            dominant = max(emotion_counts, key=emotion_counts.get)

            avg_recall = sum(m.recall_count for m in mems.values()) / total

            # Valence distribution
            valence_dist: dict[str, int] = {"positive": 0, "negative": 0, "neutral": 0}
            for m in mems.values():
                v = m.emotion_vector.valence
                if v > 0.2:
                    valence_dist["positive"] += 1
                elif v < -0.2:
                    valence_dist["negative"] += 1
                else:
                    valence_dist["neutral"] += 1

            decayed = [m.decayed_intensity for m in mems.values()]
            avg_decayed = sum(decayed) / total if decayed else 0.0

            return {
                "total_memories": total,
                "avg_intensity": round(avg_intensity, 3),
                "avg_decayed_intensity": round(avg_decayed, 3),
                "dominant_emotion": dominant,
                "flashbulb_count": flashbulbs,
                "avg_recall_count": round(avg_recall, 1),
                "valence_distribution": valence_dist,
                "emotion_counts": emotion_counts,
            }

    # ── Persistence ──

    def _save(self) -> None:
        try:
            EMOTIONAL_MEMORY_DIR.mkdir(parents=True, exist_ok=True)
            data = {
                "next_id": self._next_id,
                "memories": [m.to_dict() for m in self._memories.values()],
            }
            EMOTIONAL_MEMORY_FILE.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as e:
            logger.debug(f"EmotionalMemory save: {e}")

    def _load(self) -> None:
        try:
            if EMOTIONAL_MEMORY_FILE.exists():
                data = json.loads(EMOTIONAL_MEMORY_FILE.read_text(encoding="utf-8"))
                self._next_id = data.get("next_id", 0)
                self._memories = {
                    m["memory_id"]: EmotionalMemory.from_dict(m)
                    for m in data.get("memories", [])
                }
                logger.info(
                    "EmotionalMemory: loaded %d memories (next_id=%d)",
                    len(self._memories), self._next_id,
                )
            else:
                logger.info("EmotionalMemory: no existing data, starting fresh")
        except Exception as e:
            logger.warning(f"EmotionalMemory load failed: {e}")
            self._memories = {}
            self._next_id = 0

    # ── Helpers ──

    @staticmethod
    def _semantic_similarity(a: str, b: str) -> float:
        """Character trigram Jaccard similarity for Chinese + English text."""
        a_clean = a.lower().replace(" ", "")
        b_clean = b.lower().replace(" ", "")

        def trigrams(s: str) -> set[str]:
            return {s[i:i + 3] for i in range(max(0, len(s) - 2))}

        ta = trigrams(a_clean)
        tb = trigrams(b_clean)

        if not ta or not tb:
            # Fallback: character overlap
            sa = set(a_clean)
            sb = set(b_clean)
            overlap = len(sa & sb)
            union = len(sa | sb)
            return overlap / max(union, 1) if union > 0 else 0.0

        overlap = len(ta & tb)
        union = len(ta | tb)
        return overlap / max(union, 1)

    @staticmethod
    def _emotion_similarity(a: EmotionVector, b: EmotionVector) -> float:
        """Cosine similarity between two emotion vectors."""
        va = a.as_list()
        vb = b.as_list()
        dot = sum(x * y for x, y in zip(va, vb))
        na = math.sqrt(sum(x * x for x in va))
        nb = math.sqrt(sum(y * y for y in vb))
        denom = na * nb
        return dot / denom if denom > 0 else 0.0


# ═══ Singleton ═══

_emotional_memory: Optional[EmotionalMemoryStore] = None
_emotional_memory_lock = threading.Lock()


def get_emotional_memory() -> EmotionalMemoryStore:
    """Get or create the global EmotionalMemoryStore singleton.

    Thread-safe double-checked locking. Called by:
      - anime_persona.py: for emotional tone in avatar expression
      - user_model.py: for emotionally-weighted preference recall
    """
    global _emotional_memory
    if _emotional_memory is None:
        with _emotional_memory_lock:
            if _emotional_memory is None:
                _emotional_memory = EmotionalMemoryStore()
                logger.info("EmotionalMemory: singleton initialized")
    return _emotional_memory
