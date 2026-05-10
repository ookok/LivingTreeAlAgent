"""Collective Intelligence Layer — memory tiering, crystallization, agent blueprints.

Inspired by ModelScope Ultron's three-hub architecture (Memory/Skill/Harness).
Integrates with LivingTree's existing: struct_memory, skill_factory, conversation_dna.

1. Memory Tiering: HOT/WARM/COLD with time decay + hit-based promotion
2. Memory → Skill Crystallization: validated memories auto-graduate to skills
3. Agent Blueprint: publish/import complete agent configuration profiles
"""

from __future__ import annotations

import hashlib
import json as _json
import math
import time as _time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from loguru import logger


CI_DIR = Path(".livingtree/collective")
CI_DIR.mkdir(parents=True, exist_ok=True)
TIER_FILE = CI_DIR / "memory_tiers.json"
BLUEPRINT_DIR = CI_DIR / "blueprints"
BLUEPRINT_DIR.mkdir(exist_ok=True)


# ═══ 1. Memory Tiering ═══

class MemoryTier(Enum):
    HOT = "hot"       # Frequently accessed, always in context
    WARM = "warm"     # Moderately accessed, available on search
    COLD = "cold"     # Rarely accessed, archived, searchable with penalty


@dataclass
class TieredMemory:
    memory_id: str
    content: str
    tier: MemoryTier = MemoryTier.WARM
    hit_count: int = 0
    last_hit: float = 0.0
    created_at: float = 0.0
    validated_count: int = 0  # Times this memory was confirmed useful
    source_session: str = ""
    tags: list[str] = field(default_factory=list)

    @property
    def hotness(self) -> float:
        """Ultron-style hotness: exp(-α × days_since_last_hit)"""
        if self.last_hit == 0:
            return 0.0
        days = (_time.time() - self.last_hit) / 86400
        return math.exp(-0.15 * days)  # α=0.15, half-life ~4.6 days

    @property
    def search_boost(self) -> float:
        boosts = {MemoryTier.HOT: 1.5, MemoryTier.WARM: 1.0, MemoryTier.COLD: 0.5}
        return boosts.get(self.tier, 1.0) * max(0.1, self.hotness)

    def to_dict(self) -> dict:
        return {
            "id": self.memory_id, "tier": self.tier.value,
            "hits": self.hit_count, "hotness": round(self.hotness, 3),
            "validated": self.validated_count, "tags": self.tags,
            "content": self.content[:200],
        }


class MemoryTierManager:
    """HOT/WARM/COLD tiering with time decay and hit-based promotion."""

    HOT_THRESHOLD = 5     # Hits to promote to HOT
    COLD_THRESHOLD = 30   # Days without hit to demote to COLD
    CRYSTAL_THRESHOLD = 3 # Validations to crystallize into a skill

    def __init__(self):
        self._memories: dict[str, TieredMemory] = {}
        self._load()

    def _load(self):
        if TIER_FILE.exists():
            try:
                data = _json.loads(TIER_FILE.read_text())
                for item in data:
                    m = TieredMemory(
                        memory_id=item["id"], content=item.get("content", ""),
                        tier=MemoryTier(item.get("tier", "warm")),
                        hit_count=item.get("hits", 0), last_hit=item.get("last_hit", 0),
                        created_at=item.get("created_at", _time.time()),
                        validated_count=item.get("validated", 0),
                        source_session=item.get("session", ""),
                        tags=item.get("tags", []),
                    )
                    self._memories[m.memory_id] = m
            except Exception:
                pass

    def _save(self):
        TIER_FILE.write_text(_json.dumps(
            [m.to_dict() for m in self._memories.values()], ensure_ascii=False, indent=2
        ))

    def store(self, content: str, source_session: str = "",
              tags: list[str] | None = None) -> str:
        """Store a memory with auto-classification."""
        mid = hashlib.md5(f"{content}{_time.time()}".encode()).hexdigest()[:12]

        # Auto-classify tags if not provided
        if not tags:
            tags = self._auto_classify(content)

        m = TieredMemory(
            memory_id=mid, content=content, tier=MemoryTier.WARM,
            hit_count=0, created_at=_time.time(),
            source_session=source_session, tags=tags or [],
        )
        self._memories[mid] = m
        self._save()
        return mid

    def _auto_classify(self, content: str) -> list[str]:
        """LLM-free auto-classification by keyword."""
        tags = []
        cl = content.lower()
        if any(kw in cl for kw in ["error", "bug", "fail", "crash", "错误", "异常"]):
            tags.append("error")
        if any(kw in cl for kw in ["fix", "solution", "解决", "修复", "方案"]):
            tags.append("fix")
        if any(kw in cl for kw in ["pattern", "模式", "template", "模板"]):
            tags.append("pattern")
        if any(kw in cl for kw in ["security", "安全", "vuln", "attack"]):
            tags.append("security")
        if any(kw in cl for kw in ["config", "配置", "setup", "install", "部署"]):
            tags.append("config")
        if any(kw in cl for kw in ["api", "endpoint", "接口"]):
            tags.append("api")
        return tags or ["general"]

    def hit(self, memory_id: str, validated: bool = False) -> Optional[TieredMemory]:
        """Record a hit on a memory. Promotes tier if threshold reached."""
        m = self._memories.get(memory_id)
        if not m:
            return None
        m.hit_count += 1
        m.last_hit = _time.time()
        if validated:
            m.validated_count += 1

        if m.hit_count >= self.HOT_THRESHOLD and m.tier != MemoryTier.HOT:
            m.tier = MemoryTier.HOT
            logger.info(f"Memory promoted to HOT: {memory_id}")

        self._save()
        return m

    def apply_decay(self):
        """Apply time decay: demote COLD memories, remove very old ones."""
        now = _time.time()
        demoted, removed = 0, 0
        for mid in list(self._memories):
            m = self._memories[mid]
            days = (now - max(m.last_hit, m.created_at)) / 86400
            if days > 90:
                del self._memories[mid]
                removed += 1
            elif days > self.COLD_THRESHOLD and m.tier != MemoryTier.COLD:
                m.tier = MemoryTier.COLD
                demoted += 1
        if demoted or removed:
            self._save()
            logger.info(f"Memory decay: {demoted} demoted to COLD, {removed} removed")

    def search(self, query: str, limit: int = 10) -> list[TieredMemory]:
        """Semantic-approximate search with tier boost."""
        ql = query.lower().split()
        scored = []
        for m in self._memories.values():
            ml = m.content.lower()
            overlap = sum(1 for w in ql if w in ml) / max(len(ql), 1)
            tag_bonus = sum(1 for t in m.tags if any(w in t for w in ql)) * 0.2
            score = overlap + tag_bonus
            scored.append((score * m.search_boost, m))
        scored.sort(key=lambda x: -x[0])
        return [m for _, m in scored[:limit]]

    def get_crystallization_candidates(self) -> list[TieredMemory]:
        """Memories ready to crystallize into skills."""
        return [
            m for m in self._memories.values()
            if m.validated_count >= self.CRYSTAL_THRESHOLD and m.tier == MemoryTier.HOT
        ]

    def stats(self) -> dict:
        tiers = {"hot": 0, "warm": 0, "cold": 0}
        for m in self._memories.values():
            tiers[m.tier.value] += 1
        return {
            "total": len(self._memories), "tiers": tiers,
            "crystallization_candidates": len(self.get_crystallization_candidates()),
        }


# ═══ 2. Memory → Skill Crystallization ═══

class SkillCrystallizer:
    """Auto-graduates validated memories into reusable skills."""

    def __init__(self, tier_manager: MemoryTierManager):
        self._tiers = tier_manager
        self._crystallized: set[str] = set()

    def crystallize(self, hub=None) -> list[dict]:
        """Check for candidates and crystallize them into skills."""
        candidates = self._tiers.get_crystallization_candidates()
        new_skills = []

        for m in candidates:
            if m.memory_id in self._crystallized:
                continue

            skill_name = f"crystal_{m.memory_id}"
            skill_desc = m.content[:200]
            skill_tags = m.tags

            if hub and hasattr(hub, "world"):
                sf = getattr(hub.world, "skill_factory", None)
                if sf and hasattr(sf, "register"):
                    try:
                        sf.register(name=skill_name, description=skill_desc)
                        self._crystallized.add(m.memory_id)
                        new_skills.append({
                            "name": skill_name, "source": m.memory_id,
                            "description": skill_desc, "tags": skill_tags,
                        })
                        logger.info(f"Skill crystallized: {skill_name} ({m.validated_count} validations)")
                    except Exception as e:
                        logger.debug(f"Crystallization failed: {e}")

        return new_skills


# ═══ 3. Agent Blueprint ═══

@dataclass
class AgentBlueprint:
    """A shareable agent configuration profile."""
    blueprint_id: str
    name: str
    description: str = ""
    persona: str = ""         # Role/personality description
    model_config: dict = field(default_factory=dict)
    skill_names: list[str] = field(default_factory=list)
    memory_snapshot: list[str] = field(default_factory=list)
    created_at: float = 0.0
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.blueprint_id, "name": self.name,
            "description": self.description, "persona": self.persona,
            "model": self.model_config, "skills": self.skill_names,
            "memories": len(self.memory_snapshot),
            "created_at": self.created_at, "tags": self.tags,
        }


class BlueprintHub:
    """Publish and import agent configuration blueprints."""

    def __init__(self):
        self._blueprints: dict[str, AgentBlueprint] = {}
        self._load_all()

    def _load_all(self):
        for f in BLUEPRINT_DIR.glob("*.json"):
            try:
                data = _json.loads(f.read_text())
                bp = AgentBlueprint(**data)
                self._blueprints[bp.blueprint_id] = bp
            except Exception:
                pass

    def publish(self, name: str, hub=None, description: str = "",
                persona: str = "", tags: list[str] | None = None) -> str:
        """Publish current agent configuration as a shareable blueprint."""
        bid = hashlib.md5(f"{name}{_time.time()}".encode()).hexdigest()[:10]

        model_config = {}
        skill_names = []
        memory_snapshot = []

        if hub and hasattr(hub, "world"):
            w = hub.world
            consc = getattr(w, "consciousness", None)
            if consc:
                model_config = {
                    "flash": getattr(consc, "flash_model", ""),
                    "pro": getattr(consc, "pro_model", ""),
                }
            sf = getattr(w, "skill_factory", None)
            if sf and hasattr(sf, "discover_skills"):
                skill_names = sf.discover_skills()[:20]

        bp = AgentBlueprint(
            blueprint_id=bid, name=name, description=description,
            persona=persona, model_config=model_config,
            skill_names=skill_names, memory_snapshot=memory_snapshot,
            created_at=_time.time(), tags=tags or [],
        )
        self._blueprints[bid] = bp

        (BLUEPRINT_DIR / f"{bid}.json").write_text(
            _json.dumps(bp.__dict__, ensure_ascii=False, indent=2)
        )
        logger.info(f"Blueprint published: {name} ({bid})")
        return bid

    def import_blueprint(self, blueprint_id: str, hub=None) -> bool:
        """Import a published blueprint and apply to current agent."""
        bp = self._blueprints.get(blueprint_id)
        if not bp:
            f = BLUEPRINT_DIR / f"{blueprint_id}.json"
            if f.exists():
                try:
                    bp = AgentBlueprint(**_json.loads(f.read_text()))
                    self._blueprints[blueprint_id] = bp
                except Exception:
                    return False
            else:
                return False

        if hub and hasattr(hub, "world"):
            w = hub.world
            if bp.skill_names:
                sf = getattr(w, "skill_factory", None)
                if sf and hasattr(sf, "register"):
                    for sn in bp.skill_names[:10]:
                        try:
                            sf.register(name=f"imported_{sn}", description=f"Imported from blueprint {bp.name}")
                        except Exception:
                            pass

        logger.info(f"Blueprint imported: {bp.name} ({blueprint_id})")
        return True

    def list_blueprints(self) -> list[dict]:
        return [bp.to_dict() for bp in self._blueprints.values()]

    def delete(self, blueprint_id: str) -> bool:
        f = BLUEPRINT_DIR / f"{blueprint_id}.json"
        if f.exists():
            f.unlink()
        self._blueprints.pop(blueprint_id, None)
        return True


# ═══ Singletons ═══

_tier_instance: Optional[MemoryTierManager] = None
_crystal_instance: Optional[SkillCrystallizer] = None
_blueprint_instance: Optional[BlueprintHub] = None


def get_tiers() -> MemoryTierManager:
    global _tier_instance
    if _tier_instance is None:
        _tier_instance = MemoryTierManager()
    return _tier_instance


def get_crystallizer() -> SkillCrystallizer:
    global _crystal_instance
    if _crystal_instance is None:
        _crystal_instance = SkillCrystallizer(get_tiers())
    return _crystal_instance


def get_blueprints() -> BlueprintHub:
    global _blueprint_instance
    if _blueprint_instance is None:
        _blueprint_instance = BlueprintHub()
    return _blueprint_instance
