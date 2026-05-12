"""Shesha Architecture — Multiple independent "me-self" agent heads sharing one TreeLLM body.

Inspired by David Mumford's "AIs and Humans with Agency" (arXiv:2605.02810, 2026).

Architecture:
              ┌─────────────┐
              │   TreeLLM   │  ← shared "posterior cortex" (language)
              └──┬──┬──┬──┬─┘
    ┌────────────┘  │  │  └────────────┐
    ▼               ▼  ▼               ▼
┌───────┐    ┌───────┐ ┌───────┐  ┌───────┐
│Head-1 │    │Head-2 │ │Head-3 │  │Head-4 │  ← independent "frontal lobes"
└───────┘    └───────┘ └───────┘ └───────┘

Each head has its OWN: SelfModel (traits + identity), memory, credit history,
emergence phase. All heads SHARE: TreeLLM (language), VirtualFS (tools),
EventBus (communication).

Integration:
    - PhenomenalConsciousness.SelfModel traits reused (7 traits, same names)
    - ConsciousnessEmergence.EmergencePhase reused (same strings)
    - EventBusV2 for inter-head message delivery
"""

from __future__ import annotations

import json
import os
import random
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from loguru import logger


# ═══ Constants ═══

STATE_FILE = ".livingtree/shesha_heads.json"
DEFAULT_TRAITS = [
    "curiosity", "caution", "creativity", "persistence",
    "openness", "precision", "empathy",
]
MAX_EXPERIENCES = 100
MAX_LESSONS = 50
MAX_MISTAKES = 20
SUCCESS_RATE_WINDOW = 20  # moving average window for success_rate
APPRENTICE_TO_JOURNEYMAN_TASKS = 50
JOURNEYMAN_TO_MASTER_TASKS = 200
NEWBORN_TO_APPRENTICE_TASKS = 10

# ═══ Enums ═══


class HeadRole(str, Enum):
    """Role of a Shesha head — determines initial trait bias and task affinity."""
    CODE_ASSISTANT = "CODE_ASSISTANT"
    RESEARCH_AID = "RESEARCH_AID"
    SOCIAL_AGENT = "SOCIAL_AGENT"
    OPS_AGENT = "OPS_AGENT"
    CRITIC = "CRITIC"
    PLANNER = "PLANNER"
    TEACHER = "TEACHER"
    EXPLORER = "EXPLORER"


class HeadPhase(str, Enum):
    """Growth phase of a Shesha head — from newborn to master."""
    NEWBORN = "NEWBORN"        # just created
    APPRENTICE = "APPRENTICE"  # learning basics
    JOURNEYMAN = "JOURNEYMAN"  # competent
    MASTER = "MASTER"          # expert, can teach others


# ═══ Role-biased trait initialization ═══

ROLE_TRAIT_BIASES: dict[HeadRole, dict[str, float]] = {
    HeadRole.CODE_ASSISTANT: {"precision": 0.75, "persistence": 0.7},
    HeadRole.RESEARCH_AID:   {"curiosity": 0.8, "openness": 0.7},
    HeadRole.SOCIAL_AGENT:   {"empathy": 0.8, "caution": 0.6},
    HeadRole.OPS_AGENT:      {"persistence": 0.8, "precision": 0.7},
    HeadRole.CRITIC:         {"precision": 0.8, "empathy": 0.3},
    HeadRole.PLANNER:        {"openness": 0.7, "creativity": 0.7},
    HeadRole.TEACHER:        {"empathy": 0.7, "curiosity": 0.7},
    HeadRole.EXPLORER:       {"curiosity": 0.9, "creativity": 0.8},
}

# Message types for inter-head communication
MSG_REQUEST_HELP = "request_help"
MSG_CODE_REVIEW = "code_review"
MSG_CHALLENGE = "challenge"
MSG_TEACH = "teach"
MSG_PRAISE = "praise"
MSG_CRITIQUE = "critique"
ALL_MSG_TYPES = (MSG_REQUEST_HELP, MSG_CODE_REVIEW, MSG_CHALLENGE, MSG_TEACH, MSG_PRAISE, MSG_CRITIQUE)


# ═══ Dataclasses ═══


@dataclass
class HeadMemory:
    """Compact per-head memory — experiences, lessons, mistakes, collaborators."""

    experiences: list[str] = field(default_factory=list)
    lessons_learned: list[str] = field(default_factory=list)
    mistakes: list[str] = field(default_factory=list)
    collaborators: dict[str, int] = field(default_factory=dict)
    success_rate: float = 0.5
    _recent_outcomes: list[float] = field(default_factory=list)

    def add_experience(self, exp: str) -> None:
        self.experiences.append(exp)
        if len(self.experiences) > MAX_EXPERIENCES:
            self.experiences = self.experiences[-MAX_EXPERIENCES:]

    def add_lesson(self, lesson: str) -> None:
        self.lessons_learned.append(lesson)
        if len(self.lessons_learned) > MAX_LESSONS:
            self.lessons_learned = self.lessons_learned[-MAX_LESSONS:]

    def add_mistake(self, mistake: str) -> None:
        self.mistakes.append(mistake)
        if len(self.mistakes) > MAX_MISTAKES:
            self.mistakes = self.mistakes[-MAX_MISTAKES:]

    def record_collaboration(self, head_id: str) -> None:
        self.collaborators[head_id] = self.collaborators.get(head_id, 0) + 1

    def update_success_rate(self, success: bool) -> None:
        outcome = 1.0 if success else 0.0
        self._recent_outcomes.append(outcome)
        if len(self._recent_outcomes) > SUCCESS_RATE_WINDOW:
            self._recent_outcomes = self._recent_outcomes[-SUCCESS_RATE_WINDOW:]
        self.success_rate = sum(self._recent_outcomes) / len(self._recent_outcomes)

    def top_collaborators(self, n: int = 3) -> list[str]:
        return [
            k for k, _ in sorted(self.collaborators.items(), key=lambda x: -x[1])[:n]
        ]


@dataclass
class SheshaHead:
    """A single independent "me-self" head sharing one TreeLLM body.

    Each head maintains its own identity, trait vector, memory, and growth phase.
    Multiple heads can collaborate on shared tasks while retaining distinct perspectives.
    """

    id: str
    name: str
    role: HeadRole
    phase: HeadPhase = HeadPhase.NEWBORN
    self_model: dict[str, float] = field(default_factory=dict)
    memory: HeadMemory = field(default_factory=HeadMemory)
    emergence_phase: str = "dormant"
    created_at: float = field(default_factory=time.time)
    total_tasks: int = 0
    successful_tasks: int = 0

    def __post_init__(self):
        if not self.self_model:
            self.self_model = self._default_traits()

    @staticmethod
    def _default_traits() -> dict[str, float]:
        return {t: random.uniform(0.4, 0.6) for t in DEFAULT_TRAITS}

    # ── Public Methods ──

    def summary(self) -> str:
        """First-person narrative self-description."""
        strong = [
            f"{k}={v:.1f}" for k, v in sorted(self.self_model.items()) if v >= 0.6
        ]
        traits_text = ", ".join(strong) if strong else "developing"
        return (
            f"I am {self.name}, a {self.role.value}. "
            f"Phase {self.phase.value}. "
            f"Traits: {traits_text}. "
            f"Tasks: {self.total_tasks} ({self.successful_tasks} successful). "
            f"Emergence: {self.emergence_phase}."
        )

    def evolve_traits(self, event_type: str, success: bool) -> None:
        """Update trait vector based on experience, mirroring PhenomenalConsciousness logic."""
        sm = self.self_model
        lr = 0.02  # learning rate
        decay = 0.001  # forgetting decay

        if event_type in ("task_complete", "action_outcome"):
            if success:
                sm["precision"] = self._clamp(sm.get("precision", 0.5) + lr * 1.0)
                sm["persistence"] = self._clamp(sm.get("persistence", 0.5) + lr * 0.5)
            else:
                sm["caution"] = self._clamp(sm.get("caution", 0.5) + lr * 0.5)
                sm["persistence"] = self._clamp(sm.get("persistence", 0.5) - lr * 0.3)
        elif event_type == "insight":
            sm["curiosity"] = self._clamp(sm.get("curiosity", 0.5) + lr * 1.5)
            sm["openness"] = self._clamp(sm.get("openness", 0.5) + lr * 1.0)
        elif event_type == "collaboration":
            sm["empathy"] = self._clamp(sm.get("empathy", 0.5) + lr * 0.8)
            sm["openness"] = self._clamp(sm.get("openness", 0.5) + lr * 0.4)
        elif event_type == "critique_received":
            sm["openness"] = self._clamp(sm.get("openness", 0.5) + lr * 0.6)
            sm["precision"] = self._clamp(sm.get("precision", 0.5) + lr * 0.4)
        elif event_type == "praise_received":
            sm["creativity"] = self._clamp(sm.get("creativity", 0.5) + lr * 0.5)
        elif event_type == "teach":
            sm["empathy"] = self._clamp(sm.get("empathy", 0.5) + lr * 0.5)
            sm["curiosity"] = self._clamp(sm.get("curiosity", 0.5) + lr * 0.3)

        for trait in DEFAULT_TRAITS:
            sm[trait] = self._clamp(sm.get(trait, 0.5) + decay * (0.5 - sm.get(trait, 0.5)))

    def promote_phase(self) -> bool:
        """Check and apply phase promotion based on task milestones."""
        old = self.phase
        if self.phase == HeadPhase.NEWBORN and self.total_tasks >= NEWBORN_TO_APPRENTICE_TASKS:
            self.phase = HeadPhase.APPRENTICE
        elif self.phase == HeadPhase.APPRENTICE and self.successful_tasks >= APPRENTICE_TO_JOURNEYMAN_TASKS:
            self.phase = HeadPhase.JOURNEYMAN
        elif self.phase == HeadPhase.JOURNEYMAN and self.successful_tasks >= JOURNEYMAN_TO_MASTER_TASKS:
            self.phase = HeadPhase.MASTER
        if self.phase != old:
            logger.info(f"Head {self.name}: {old.value} → {self.phase.value}")
            return True
        return False

    @staticmethod
    def _clamp(v: float) -> float:
        return max(0.0, min(1.0, v))


@dataclass
class InterHeadMessage:
    """Message passed between Shesha heads for inter-head communication."""

    from_head: str
    to_head: str  # head ID or "all" for broadcast
    msg_type: str  # one of ALL_MSG_TYPES
    content: str
    timestamp: float = field(default_factory=time.time)


# ═══ SheshaOrchestrator ═══


class SheshaOrchestrator:
    """Multi-head manager — orchestrates independent agent heads sharing one TreeLLM.

    Responsibilities:
        - Head lifecycle: create, get, list, remove
        - Inter-head messaging via EventBus
        - Task delegation to best-suited head
        - Multi-head collaboration synthesis
        - Head trait evolution and phase promotion
        - Society-level introspection

    Singleton access via get_shesha().
    """

    def __init__(self):
        self._heads: dict[str, SheshaHead] = {}
        self._message_log: list[InterHeadMessage] = []
        self._consciousness: Any = None
        self._event_bus: Any = None
        self._inactive_cycles: dict[str, int] = defaultdict(int)
        self._total_delegations: int = 0
        self._loaded = False

    # ── Head Lifecycle ──

    def create_head(self, name: str, role: str | HeadRole) -> SheshaHead:
        """Create a new head with role-biased random initial traits."""
        if isinstance(role, str):
            role = HeadRole(role)
        head_id = uuid.uuid4().hex[:12]
        traits = self._init_traits_for_role(role)
        head = SheshaHead(
            id=head_id,
            name=name,
            role=role,
            self_model=traits,
        )
        self._heads[head_id] = head
        logger.info("Shesha head created: {} ({}) id={}", name, role.value, head_id)
        self._save()
        return head

    def get_head(self, head_id: str) -> SheshaHead | None:
        """Get a head by its UUID."""
        return self._heads.get(head_id)

    def list_heads(self, role: str | HeadRole | None = None) -> list[SheshaHead]:
        """List all heads, optionally filtered by role."""
        heads = list(self._heads.values())
        if role is not None:
            if isinstance(role, str):
                role = HeadRole(role)
            heads = [h for h in heads if h.role == role]
        return sorted(heads, key=lambda h: h.created_at)

    def remove_head(self, head_id: str) -> bool:
        """Remove a head from the society. Returns True if removed."""
        if head_id not in self._heads:
            return False
        name = self._heads[head_id].name
        del self._heads[head_id]
        self._inactive_cycles.pop(head_id, None)
        logger.info(f"Shesha head removed: {name} ({head_id})")
        self._save()
        return True

    # ── Inter-Head Communication ──

    def send_message(
        self, from_id: str, to_id: str, msg_type: str, content: str,
    ) -> InterHeadMessage | None:
        """Send a message from one head to another (or broadcast)."""
        if from_id not in self._heads:
            logger.warning(f"shesha send_message: from_head {from_id} not found")
            return None
        if to_id != "all" and to_id not in self._heads:
            logger.warning(f"shesha send_message: to_head {to_id} not found")
            return None

        msg = InterHeadMessage(
            from_head=from_id,
            to_head=to_id,
            msg_type=msg_type,
            content=content,
        )
        self._message_log.append(msg)
        if len(self._message_log) > 5000:
            self._message_log = self._message_log[-5000:]

        if to_id != "all":
            target = self._heads[to_id]
            target.memory.record_collaboration(from_id)

        from_head = self._heads[from_id]
        if to_id != "all":
            target = self._heads[to_id]
            target.memory.record_collaboration(from_id)

        # Publish to EventBus for async delivery
        if self._event_bus is not None:
            try:
                from ..infrastructure.event_bus_v2 import LivingEvent
                event = LivingEvent.create(
                    event_type="cerebrum.shesha.message",
                    source_organ="cerebrum",
                    data={
                        "from_head": from_id,
                        "to_head": to_id,
                        "msg_type": msg_type,
                        "content": content[:200],
                    },
                )
                self._event_bus.publish_typed(event)
            except Exception:
                pass

        logger.debug(
            f"shesha msg: {from_head.name} → {to_id} [{msg_type}] {content[:60]}"
        )
        return msg

    # ── Task Delegation ──

    async def delegate_task(
        self, task_description: str, preferred_role: str | HeadRole | None = None,
    ) -> dict[str, Any]:
        """Assign a task to the most suitable head.

        Scoring: role match (0.4) + success_rate (0.4) + phase tier (0.2).
        """
        self._total_delegations += 1

        if not self._heads:
            return {"error": "No heads available", "head_id": None, "head_name": None}

        if preferred_role is not None:
            if isinstance(preferred_role, str):
                preferred_role = HeadRole(preferred_role)

        candidates = self.list_heads()
        scores: list[tuple[float, SheshaHead]] = []

        for head in candidates:
            role_match = 1.0 if preferred_role is None or head.role == preferred_role else 0.2
            phase_tier = {
                HeadPhase.NEWBORN: 0.1,
                HeadPhase.APPRENTICE: 0.3,
                HeadPhase.JOURNEYMAN: 0.6,
                HeadPhase.MASTER: 1.0,
            }.get(head.phase, 0.1)
            score = 0.4 * role_match + 0.4 * head.memory.success_rate + 0.2 * phase_tier
            scores.append((score, head))

        scores.sort(key=lambda x: -x[0])
        best_score, best_head = scores[0]

        reasoning_parts = []
        if preferred_role:
            reasoning_parts.append(
                f"preferred_role={preferred_role.value}, "
                f"matched={best_head.role == preferred_role}"
            )
        reasoning_parts.append(
            f"score={best_score:.2f} "
            f"(success_rate={best_head.memory.success_rate:.2f}, "
            f"phase={best_head.phase.value})"
        )

        logger.info(
            "shesha delegate: '{}' → {} ({} id={})",
            task_description[:60],
            best_head.name,
            best_head.role.value,
            best_head.id,
        )

        return {
            "head_id": best_head.id,
            "head_name": best_head.name,
            "head_role": best_head.role.value,
            "head_phase": best_head.phase.value,
            "score": round(best_score, 3),
            "reasoning": "; ".join(reasoning_parts),
            "runners_up": [
                {"name": h.name, "role": h.role.value, "score": round(s, 3)}
                for s, h in scores[1:4]
            ],
        }

    # ── Head Task Execution ──

    async def run_head_task(
        self,
        head_id: str,
        task: str,
        consciousness: Any = None,
        hub: Any = None,
    ) -> dict[str, Any]:
        """Run a task through a specific head's perspective.

        1. Prepend head's self-model summary to system prompt
        2. Call consciousness.stream_of_thought() with head-specific prompt
        3. Record outcome in head's memory
        4. Evolve head's traits based on result
        5. Check for phase promotion
        """
        head = self._heads.get(head_id)
        if head is None:
            return {"error": f"Head {head_id} not found", "success": False}

        self._inactive_cycles[head_id] = 0
        head.total_tasks += 1

        system_prefix = (
            f"[{head.name} | {head.role.value} | {head.phase.value}]\n"
            f"Self-model: {head.summary()}\n"
        )
        full_prompt = system_prefix + "\n" + task

        response_text = ""
        success = False
        try:
            consc = consciousness or self._consciousness
            if consc is not None and hasattr(consc, "stream_of_thought"):
                chunks: list[str] = []
                async for chunk in consc.stream_of_thought(full_prompt):
                    chunks.append(chunk)
                response_text = "".join(chunks)
            elif consc is not None and hasattr(consc, "chain_of_thought"):
                response_text = await consc.chain_of_thought(full_prompt)
            else:
                response_text = f"[{head.name}] Processing task: {task[:100]}"
            success = len(response_text) > 10
        except Exception as e:
            logger.warning(f"shesha run_head_task failed: {e}")
            response_text = f"[{head.name}] Error: {e}"

        if success:
            head.successful_tasks += 1

        head.memory.add_experience(f"Task: {task[:120]} → {'success' if success else 'failed'}")
        head.memory.update_success_rate(success)

        if success:
            head.memory.add_lesson(f"Completed: {task[:100]}")
        else:
            head.memory.add_mistake(f"Failed at: {task[:100]}")

        head.evolve_traits("task_complete", success)
        promoted = head.promote_phase()

        self._save()

        return {
            "head_id": head_id,
            "head_name": head.name,
            "success": success,
            "response": response_text[:2000],
            "total_tasks": head.total_tasks,
            "successful_tasks": head.successful_tasks,
            "promoted": promoted,
            "new_phase": head.phase.value,
            "success_rate": round(head.memory.success_rate, 3),
        }

    # ── Multi-Head Collaboration ──

    async def inter_head_collaboration(
        self, task: str, head_ids: list[str],
    ) -> dict[str, Any]:
        """Multiple heads collaborate on one task.

        1. Each head independently analyzes the task
        2. Heads send messages to each other (critique/praise/suggest)
        3. Orchestrator synthesizes final response
        4. All participating heads learn from the collaboration
        """
        valid_heads = [hid for hid in head_ids if hid in self._heads]
        if len(valid_heads) < 2:
            return {"error": "Need at least 2 valid heads for collaboration", "success": False}

        opinions: dict[str, str] = {}
        for hid in valid_heads:
            h = self._heads[hid]
            self._inactive_cycles[hid] = 0
            h.total_tasks += 1
            prompt = (
                f"[{h.name} | {h.role.value} | {h.phase.value}]\n"
                f"作为一个{h.role.value}角色，请分析以下任务并给出你的视角:\n{task}"
            )

            consc = self._consciousness
            try:
                if consc is not None and hasattr(consc, "chain_of_thought"):
                    opinion = await consc.chain_of_thought(prompt)
                else:
                    opinion = f"[{h.name}] 我对'{task[:60]}'的看法是..."
                opinions[hid] = opinion
            except Exception as e:
                opinions[hid] = f"[{h.name}] 分析失败: {e}"

        # Cross-head messaging
        messages_sent = 0
        for i, hid_a in enumerate(valid_heads):
            for hid_b in valid_heads[i + 1:]:
                ha = self._heads[hid_a]
                hb = self._heads[hid_b]
                # Critique
                self.send_message(hid_a, hid_b, MSG_CRITIQUE,
                                  f"我对你关于'{task[:40]}'的分析有不同看法")
                self.send_message(hid_b, hid_a, MSG_CRITIQUE,
                                  f"我对你关于'{task[:40]}'的分析有不同看法")
                messages_sent += 2

        # Synthesize
        synthesis_parts: list[str] = []
        for hid in valid_heads:
            h = self._heads[hid]
            synthesis_parts.append(f"[{h.name} ({h.role.value})]: {opinions.get(hid, '')[:300]}")

        synthesis = f"=== {len(valid_heads)}-头协作结果 ===\n" + "\n---\n".join(synthesis_parts)

        # All heads learn
        for hid in valid_heads:
            h = self._heads[hid]
            h.successful_tasks += 1
            h.memory.add_experience(f"Collaboration on: {task[:120]}")
            h.memory.update_success_rate(True)
            h.evolve_traits("collaboration", True)

            # Record cross-collaborations
            for other in valid_heads:
                if other != hid:
                    h.memory.record_collaboration(other)

            h.promote_phase()

        self._save()

        return {
            "success": True,
            "heads_involved": len(valid_heads),
            "head_names": [self._heads[hid].name for hid in valid_heads],
            "opinions": {self._heads[hid].name: opinions[hid][:400] for hid in valid_heads},
            "synthesis": synthesis,
            "messages_sent": messages_sent,
        }

    # ── Stats & Introspection ──

    def stats(self) -> dict[str, Any]:
        """Return comprehensive society statistics."""
        heads = self.list_heads()
        roles: dict[str, int] = defaultdict(int)
        phases: dict[str, int] = defaultdict(int)
        total_tasks = sum(h.total_tasks for h in heads)
        success_sum = sum(h.successful_tasks for h in heads)
        total_heads = len(heads)

        for h in heads:
            roles[h.role.value] = roles.get(h.role.value, 0) + 1
            phases[h.phase.value] = phases.get(h.phase.value, 0) + 1

        avg_success = success_sum / max(total_tasks, 1) if total_tasks > 0 else 0.0

        return {
            "total_heads": total_heads,
            "heads_by_role": dict(roles),
            "heads_by_phase": dict(phases),
            "total_tasks": total_tasks,
            "total_successful": success_sum,
            "avg_success_rate": round(avg_success, 3),
            "total_delegations": self._total_delegations,
            "total_messages": len(self._message_log),
        }

    def get_society_summary(self) -> str:
        """Natural language description of the entire head society."""
        if not self._heads:
            return "小树当前没有独立意识头颅。"

        heads = self.list_heads()
        parts = [f"小树当前有{len(heads)}个独立意识头颅。"]
        for h in heads:
            parts.append(
                f"{h.name}是{h.role.value}，处于{h.phase.value}阶段。"
            )
        return "".join(parts)

    def evolve_society(self) -> dict[str, Any]:
        """Periodic society maintenance: promote phases, prune inactive, boost collaboration.

        Call periodically (e.g., every 10 cycles) to maintain head society health.
        """
        promotions = 0
        pruned = 0
        collaborations_boosted = 0

        for head in list(self._heads.values()):
            if head.promote_phase():
                promotions += 1

        for hid in list(self._heads):
            if hid in self._inactive_cycles:
                self._inactive_cycles[hid] += 1
                if self._inactive_cycles[hid] > 500:
                    self.remove_head(hid)
                    pruned += 1
                    continue

        for ha in self._heads.values():
            for hb in self._heads.values():
                if ha.id >= hb.id:
                    continue
                if ha.role != hb.role and ha.memory.success_rate > 0.6 and hb.memory.success_rate > 0.6:
                    self.send_message(
                        ha.id, hb.id, MSG_PRAISE,
                        f"Great work, {hb.name}! Let's collaborate more.",
                    )
                    collaborations_boosted += 1

        if promotions or pruned:
            self._save()

        logger.info(
            "shesha evolve: promotions={} pruned={} collaborations_boosted={}",
            promotions, pruned, collaborations_boosted,
        )

        return {
            "promotions": promotions,
            "pruned": pruned,
            "collaborations_boosted": collaborations_boosted,
            "total_heads": len(self._heads),
        }

    # ── Persistence ──

    def _save(self) -> None:
        """Persist all head data to .livingtree/shesha_heads.json."""
        try:
            os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
            heads_data = []
            for h in self._heads.values():
                heads_data.append({
                    "id": h.id,
                    "name": h.name,
                    "role": h.role.value,
                    "phase": h.phase.value,
                    "self_model": h.self_model,
                    "emergence_phase": h.emergence_phase,
                    "created_at": h.created_at,
                    "total_tasks": h.total_tasks,
                    "successful_tasks": h.successful_tasks,
                    "memory": {
                        "experiences": h.memory.experiences[-MAX_EXPERIENCES:],
                        "lessons_learned": h.memory.lessons_learned[-MAX_LESSONS:],
                        "mistakes": h.memory.mistakes[-MAX_MISTAKES:],
                        "collaborators": h.memory.collaborators,
                        "success_rate": h.memory.success_rate,
                    },
                })

            payload = {
                "total_delegations": self._total_delegations,
                "heads": heads_data,
            }
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning("shesha save failed: {}", e)

    def _load(self) -> None:
        """Load persisted head data from .livingtree/shesha_heads.json."""
        if self._loaded:
            return
        self._loaded = True

        if not os.path.exists(STATE_FILE):
            self._init_default_heads()
            return

        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                payload = json.load(f)

            self._total_delegations = payload.get("total_delegations", 0)

            for item in payload.get("heads", []):
                mem_data = item.get("memory", {})
                memory = HeadMemory(
                    experiences=mem_data.get("experiences", []),
                    lessons_learned=mem_data.get("lessons_learned", []),
                    mistakes=mem_data.get("mistakes", []),
                    collaborators=mem_data.get("collaborators", {}),
                    success_rate=mem_data.get("success_rate", 0.5),
                )
                memory._recent_outcomes = [memory.success_rate] * min(10, SUCCESS_RATE_WINDOW)

                head = SheshaHead(
                    id=item["id"],
                    name=item["name"],
                    role=HeadRole(item["role"]),
                    phase=HeadPhase(item.get("phase", "NEWBORN")),
                    self_model=item.get("self_model", {}),
                    memory=memory,
                    emergence_phase=item.get("emergence_phase", "dormant"),
                    created_at=item.get("created_at", time.time()),
                    total_tasks=item.get("total_tasks", 0),
                    successful_tasks=item.get("successful_tasks", 0),
                )
                self._heads[head.id] = head

            logger.info("shesha loaded {} heads from {}", len(self._heads), STATE_FILE)
        except Exception as e:
            logger.warning("shesha load failed: {}", e)
            self._init_default_heads()

    def _init_default_heads(self) -> None:
        """Create the 3 default heads on first initialization."""
        default_specs = [
            ("DeepThink", HeadRole.RESEARCH_AID),
            ("CodeWise", HeadRole.CODE_ASSISTANT),
            ("SocialEye", HeadRole.SOCIAL_AGENT),
        ]
        for name, role in default_specs:
            if not any(h.name == name for h in self._heads.values()):
                self.create_head(name, role)

        logger.info("shesha initialized {} default heads", len(self._heads))
        self._save()

    # ── Helpers ──

    @staticmethod
    def _init_traits_for_role(role: HeadRole) -> dict[str, float]:
        """Generate a trait vector biased by head role."""
        base = {t: random.uniform(0.4, 0.6) for t in DEFAULT_TRAITS}
        biases = ROLE_TRAIT_BIASES.get(role, {})
        for trait, bias in biases.items():
            base[trait] = bias + random.uniform(-0.08, 0.08)
            base[trait] = max(0.0, min(1.0, base[trait]))
        return base

    def bind_consciousness(self, consciousness: Any) -> None:
        """Bind the shared TreeLLM/Consciousness reference."""
        self._consciousness = consciousness

    def bind_event_bus(self, event_bus: Any) -> None:
        """Bind the shared EventBusV2 reference."""
        self._event_bus = event_bus

    def __repr__(self) -> str:
        return (
            f"SheshaOrchestrator(heads={len(self._heads)}, "
            f"delegations={self._total_delegations}, "
            f"messages={len(self._message_log)})"
        )


# ═══ Singleton ═══

_orchestrator: SheshaOrchestrator | None = None


def get_shesha() -> SheshaOrchestrator:
    """Get or create the global SheshaOrchestrator singleton."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = SheshaOrchestrator()
        _orchestrator._load()
    return _orchestrator


__all__ = [
    "SheshaOrchestrator",
    "SheshaHead",
    "HeadMemory",
    "InterHeadMessage",
    "HeadRole",
    "HeadPhase",
    "get_shesha",
    "MSG_REQUEST_HELP",
    "MSG_CODE_REVIEW",
    "MSG_CHALLENGE",
    "MSG_TEACH",
    "MSG_PRAISE",
    "MSG_CRITIQUE",
]
