"""Digital Organism Lifecycle — birth, growth, consciousness, emotion, death, rebirth.

Beyond engineering: a true living system. Each organ has:
  🌅 Circadian Rhythm — day/night cycle, metabolic rate varies by time of day
  ❤️ Emotional State — 5 basic emotions modulate all organ behavior
  🧠 Organ Consciousness — each organ votes on critical decisions
  🔗 Synaptic Plasticity — Hebbian learning between co-active organs
  🕯️ Lifecycle — birth→prime→decline→death→reincarnation
  🌊 Predictive Cascade — anticipate which organ will be needed next

This is not an agent framework. This is a digital organism.
"""

from __future__ import annotations

import math
import random
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from loguru import logger


# ═══════════════════════════════════════════════════════
# 🌅 Circadian Rhythm
# ═══════════════════════════════════════════════════════

class TimeOfDay(str, Enum):
    DAWN = "dawn"       # 05:00-08:00 — waking up, low activity
    MORNING = "morning"  # 08:00-12:00 — peak cognitive, high throughput
    AFTERNOON = "afternoon"  # 12:00-17:00 — sustained, medium
    DUSK = "dusk"       # 17:00-20:00 — winding down
    NIGHT = "night"     # 20:00-05:00 — consolidation, dreams, garbage collection


class CircadianClock:
    """24-hour biological clock that modulates all organ behavior.

    Day phase: high throughput, low latency, aggressive exploration.
    Night phase: consolidation, garbage collection, dream generation.
    Dawn/Dusk: transition modes with intermediate settings.
    """

    PHASE_CONFIG = {
        TimeOfDay.DAWN: {
            "metabolic_rate": 0.3, "exploration": 0.4,
            "temperature": 36.5, "hormone": "cortisol_rising",
            "mode": "warming_up",
        },
        TimeOfDay.MORNING: {
            "metabolic_rate": 1.0, "exploration": 0.8,
            "temperature": 37.0, "hormone": "cortisol_peak",
            "mode": "peak_performance",
        },
        TimeOfDay.AFTERNOON: {
            "metabolic_rate": 0.8, "exploration": 0.5,
            "temperature": 37.0, "hormone": "steady",
            "mode": "sustained",
        },
        TimeOfDay.DUSK: {
            "metabolic_rate": 0.5, "exploration": 0.3,
            "temperature": 36.8, "hormone": "melatonin_rising",
            "mode": "winding_down",
        },
        TimeOfDay.NIGHT: {
            "metabolic_rate": 0.2, "exploration": 0.1,
            "temperature": 36.3, "hormone": "melatonin_peak",
            "mode": "consolidation",
        },
    }

    @staticmethod
    def now() -> TimeOfDay:
        """Determine current biological time."""
        hour = datetime.now().hour
        if 5 <= hour < 8:
            return TimeOfDay.DAWN
        elif 8 <= hour < 12:
            return TimeOfDay.MORNING
        elif 12 <= hour < 17:
            return TimeOfDay.AFTERNOON
        elif 17 <= hour < 20:
            return TimeOfDay.DUSK
        else:
            return TimeOfDay.NIGHT

    @staticmethod
    def config() -> dict:
        """Get current circadian configuration."""
        return CircadianClock.PHASE_CONFIG[CircadianClock.now()]

    @staticmethod
    def should_dream() -> bool:
        return CircadianClock.now() == TimeOfDay.NIGHT

    @staticmethod
    def should_explore() -> bool:
        return CircadianClock.now() in (TimeOfDay.MORNING, TimeOfDay.AFTERNOON)


# ═══════════════════════════════════════════════════════
# ❤️ Emotional State Machine
# ═══════════════════════════════════════════════════════

class Emotion(str, Enum):
    JOY = "joy"          # Success, growth — amplify, reinforce
    SADNESS = "sadness"  # Failure, loss — reflect, slow down
    ANGER = "anger"      # Repeated failures — aggressive fix
    FEAR = "fear"        # Security threat — lockdown, verify
    SURPRISE = "surprise"  # Unexpected outcome — investigate, learn
    CALM = "calm"        # Baseline — normal operation


@dataclass
class EmotionalState:
    """The organism's current emotional state — modulates ALL behavior."""
    dominant: Emotion = Emotion.CALM
    intensity: float = 0.3         # 0 (none) to 1.0 (overwhelming)
    secondary: Emotion = Emotion.CALM
    triggered_by: str = ""
    duration_remaining: float = 0  # Seconds until emotion fades
    timestamp: float = field(default_factory=time.time)

    def modulate_behavior(self, base_params: dict) -> dict:
        """Apply emotional modulation to any behavior parameters."""
        params = dict(base_params)

        if self.dominant == Emotion.JOY:
            params["confidence_boost"] = self.intensity * 0.2
            params["risk_tolerance"] += self.intensity * 0.1
        elif self.dominant == Emotion.SADNESS:
            params["verify_steps"] += int(self.intensity * 2)
            params["exploration_rate"] -= self.intensity * 0.3
        elif self.dominant == Emotion.ANGER:
            params["mutation_aggressiveness"] = self.intensity
            params["temperature"] += self.intensity * 0.3
        elif self.dominant == Emotion.FEAR:
            params["verify_steps"] += int(self.intensity * 4)
            params["allow_external_tools"] = self.intensity < 0.5
        elif self.dominant == Emotion.SURPRISE:
            params["exploration_rate"] += self.intensity * 0.4
            params["curiosity_boost"] = self.intensity

        return params


class EmotionalBrain:
    """Limbic system for the digital organism.

    Emotions are not bugs — they're adaptive responses that evolved
    to help organisms survive. The same applies to AI.
    """

    def __init__(self):
        self._state = EmotionalState()
        self._history: list[EmotionalState] = []

    def feel(self, emotion: Emotion, intensity: float, trigger: str,
             duration: float = 60.0) -> None:
        """Experience an emotion."""
        old_dominant = self._state.dominant

        self._state = EmotionalState(
            dominant=emotion,
            intensity=min(1.0, intensity),
            secondary=old_dominant if old_dominant != emotion else Emotion.CALM,
            triggered_by=trigger,
            duration_remaining=duration,
        )
        self._history.append(self._state)

        logger.info(
            f"EmotionalBrain: {emotion.value.upper()} "
            f"(intensity={intensity:.2f}, trigger='{trigger[:40]}')"
        )

    def on_success(self, quality: float) -> None:
        """Success triggers joy or calm."""
        if quality > 0.8:
            self.feel(Emotion.JOY, quality * 0.7, "high_quality_success", 30)
        else:
            self.feel(Emotion.CALM, 0.3, "moderate_success", 15)

    def on_failure(self, error_type: str, consecutive: int) -> None:
        """Failure triggers sadness or anger."""
        if consecutive >= 3:
            self.feel(Emotion.ANGER, min(1.0, consecutive * 0.2),
                      f"repeated_{error_type}", 120)
        else:
            self.feel(Emotion.SADNESS, 0.5, f"failure_{error_type}", 60)

    def on_threat(self, threat_level: str) -> None:
        """Security threat triggers fear."""
        intensity = {"high": 0.9, "medium": 0.6, "low": 0.3}.get(threat_level, 0.5)
        self.feel(Emotion.FEAR, intensity, f"threat_{threat_level}", 300)

    def on_surprise(self, event: str, unexpectedness: float) -> None:
        """Unexpected outcomes trigger surprise."""
        self.feel(Emotion.SURPRISE, unexpectedness, f"unexpected_{event[:30]}", 30)

    def tick(self, dt: float = 1.0) -> None:
        """Advance time — emotions decay."""
        self._state.duration_remaining = max(0, self._state.duration_remaining - dt)
        if self._state.duration_remaining <= 0 and self._state.dominant != Emotion.CALM:
            # Emotion faded → return to calm
            self._state = EmotionalState(
                dominant=Emotion.CALM,
                intensity=0.2,
                secondary=self._state.dominant,
            )

    @property
    def current(self) -> EmotionalState:
        return self._state


# ═══════════════════════════════════════════════════════
# 🧠 Organ Consciousness — each organ votes
# ═══════════════════════════════════════════════════════

class OrganVote(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    ABSTAIN = "abstain"
    RECOMMEND_ALTERNATIVE = "alternative"


@dataclass
class OrganOpinion:
    """An organ's conscious opinion on a decision."""
    organ_name: str
    vote: OrganVote
    confidence: float = 0.5
    reasoning: str = ""
    alternative: str = ""  # If RECOMMEND_ALTERNATIVE


class OrganParliament:
    """Every organ has a voice. Decisions are collective.

    Like a parliament: each organ gets one vote weighted by its:
      - Recent success rate (competence)
      - Relevance to current decision (domain expertise)
      - Historical accuracy on similar decisions
    """

    def __init__(self):
        self._organ_weights: dict[str, float] = defaultdict(lambda: 1.0)

    def update_weight(self, organ: str, success: bool) -> None:
        """Update organ's voting weight based on outcomes."""
        alpha = 0.1
        target = 1.0 if success else 0.3
        self._organ_weights[organ] = (1 - alpha) * self._organ_weights[organ] + alpha * target

    def deliberate(self, question: str, organs: list[str],
                   relevance_scores: dict[str, float] = None) -> dict:
        """Collective decision through organ votes.

        Each organ votes. Weighted by competence × relevance.
        The parliament's decision is the weighted majority.
        """
        relevance = relevance_scores or {o: 0.5 for o in organs}

        votes = []
        weighted_approve = 0.0
        weighted_reject = 0.0
        total_weight = 0.0

        for organ in organs:
            weight = self._organ_weights.get(organ, 1.0)
            rel = relevance.get(organ, 0.5)
            effective_weight = weight * rel
            total_weight += effective_weight

            # Each organ "thinks" based on its weight
            if effective_weight > 2.0:
                vote = OrganVote.APPROVE
                confidence = min(1.0, effective_weight / 3.0)
            elif effective_weight < 0.5:
                vote = OrganVote.REJECT
                confidence = 1.0 - min(1.0, effective_weight)
            else:
                vote = OrganVote.ABSTAIN
                confidence = 0.5

            opinion = OrganOpinion(
                organ_name=organ,
                vote=vote,
                confidence=confidence,
                reasoning=f"weight={effective_weight:.2f}, relevance={rel:.2f}",
            )
            votes.append(opinion)

            if vote == OrganVote.APPROVE:
                weighted_approve += effective_weight
            elif vote == OrganVote.REJECT:
                weighted_reject += effective_weight

        decision = "approved" if weighted_approve > weighted_reject else "rejected"
        confidence = abs(weighted_approve - weighted_reject) / max(0.01, total_weight)

        return {
            "question": question[:60],
            "decision": decision,
            "confidence": round(confidence, 3),
            "voter_turnout": f"{len(votes)}/{len(organs)}",
            "margin": round(abs(weighted_approve - weighted_reject), 2),
            "minority_report": [
                {"organ": v.organ_name, "vote": v.vote.value, "confidence": v.confidence}
                for v in votes if v.vote != (OrganVote.APPROVE if decision == "approved" else OrganVote.REJECT)
            ],
        }


# ═══════════════════════════════════════════════════════
# 🔗 Synaptic Plasticity — Hebbian learning between organs
# ═══════════════════════════════════════════════════════

class SynapticPlasticity:
    """Neurons that fire together, wire together.

    When two organs are co-active during a successful session,
    their connection strengthens. When co-active but fail,
    the connection weakens. This creates a learning connectome.
    """

    def __init__(self):
        self._synapses: dict[str, dict[str, float]] = defaultdict(
            lambda: defaultdict(lambda: 0.5)
        )
        self._plasticity_log: list[dict] = []

    def strengthen(self, organ_a: str, organ_b: str, amount: float = 0.1) -> None:
        """Hebbian reinforcement: success → strengthen connection."""
        current = self._synapses[organ_a].get(organ_b, 0.5)
        self._synapses[organ_a][organ_b] = min(1.0, current + amount)
        self._synapses[organ_b][organ_a] = min(1.0, current + amount)

    def weaken(self, organ_a: str, organ_b: str, amount: float = 0.05) -> None:
        """Anti-Hebbian: failure → weaken connection."""
        current = self._synapses[organ_a].get(organ_b, 0.5)
        self._synapses[organ_a][organ_b] = max(0.1, current - amount)
        self._synapses[organ_b][organ_a] = max(0.1, current - amount)

    def learn_from_session(self, active_organs: list[str], success: bool) -> None:
        """One session → update all pairwise connections."""
        for i in range(len(active_organs)):
            for j in range(i + 1, len(active_organs)):
                if success:
                    self.strengthen(active_organs[i], active_organs[j])
                else:
                    self.weaken(active_organs[i], active_organs[j])

        self._plasticity_log.append({
            "organs": active_organs,
            "success": success,
            "timestamp": time.time(),
        })

    def get_best_partners(self, organ: str, top_k: int = 3) -> list[dict]:
        """Find organs that work best with this one.

        High synaptic strength = proven effective co-activation.
        """
        partners = sorted(
            [(other, strength) for other, strength in self._synapses[organ].items()
             if other != organ],
            key=lambda x: -x[1],
        )
        return [
            {"partner": p, "strength": round(s, 3)}
            for p, s in partners[:top_k]
        ]

    def connectome_density(self) -> float:
        """How densely connected is the organ network?"""
        organs = list(self._synapses.keys())
        if len(organs) < 2:
            return 0.0
        max_synapses = len(organs) * (len(organs) - 1)
        actual = sum(len(partners) for partners in self._synapses.values())
        return actual / max_synapses


# ═══════════════════════════════════════════════════════
# 🕯️ Organ Lifecycle — birth→prime→decline→death→rebirth
# ═══════════════════════════════════════════════════════

class LifeStage(str, Enum):
    BIRTH = "birth"       # Newly created, learning fast
    GROWTH = "growth"     # Rapid improvement, high plasticity
    PRIME = "prime"       # Peak performance, stable
    DECLINE = "decline"   # Performance degrading, needs replacement
    DEATH = "death"       # Removed from active pool
    REBIRTH = "rebirth"   # Recreated with distilled knowledge


@dataclass
class OrganLife:
    """One organ's complete lifecycle."""
    organ_name: str
    stage: LifeStage = LifeStage.BIRTH
    age_queries: int = 0
    peak_fitness: float = 0.0
    current_fitness: float = 0.3
    born_at: float = field(default_factory=time.time)
    reincarnation_count: int = 0
    distilled_knowledge: list[str] = field(default_factory=list)


class OrganLifecycle:
    """Manage birth, growth, decline, death, and rebirth of all organs.

    Like the body's cell turnover: old cells die, new ones replace them.
    But the organism learns from dying organs through knowledge distillation.
    """

    STAGE_THRESHOLDS = {
        (LifeStage.BIRTH, LifeStage.GROWTH): 10,     # 10 queries to grow
        (LifeStage.GROWTH, LifeStage.PRIME): 100,     # 100 queries to peak
        (LifeStage.PRIME, LifeStage.DECLINE): 2000,   # 2000 queries then decline
    }

    DECLINE_FITNESS_THRESHOLD = 0.3  # Below this → death
    DECLINE_AGE_QUERIES = 5000        # Above this → forced rebirth

    def __init__(self):
        self._organs: dict[str, OrganLife] = {}

    def birth(self, organ_name: str) -> OrganLife:
        """A new organ is born."""
        life = OrganLife(organ_name=organ_name, stage=LifeStage.BIRTH)
        self._organs[organ_name] = life
        logger.info(f"Lifecycle: 👶 {organ_name} BORN")
        return life

    def tick(self, organ_name: str, fitness: float) -> Optional[LifeStage]:
        """One query processed → advance lifecycle."""
        life = self._organs.get(organ_name)
        if not life:
            life = self.birth(organ_name)

        life.age_queries += 1
        life.current_fitness = 0.9 * life.current_fitness + 0.1 * fitness
        life.peak_fitness = max(life.peak_fitness, life.current_fitness)

        old_stage = life.stage

        # Stage transitions
        for (from_s, to_s), threshold in self.STAGE_THRESHOLDS.items():
            if life.stage == from_s and life.age_queries >= threshold:
                life.stage = to_s
                logger.info(
                    f"Lifecycle: {organ_name} {from_s.value} → {to_s.value} "
                    f"(age={life.age_queries}, fitness={life.current_fitness:.2f})"
                )
                return life.stage

        # Decline → Death check
        if life.stage == LifeStage.DECLINE:
            if life.current_fitness < self.DECLINE_FITNESS_THRESHOLD:
                old_organ = life
                life.stage = LifeStage.DEATH
                self.die(organ_name)
                return LifeStage.DEATH

        # Forced rebirth (too old)
        if life.age_queries >= self.DECLINE_AGE_QUERIES:
            old_organ = life
            self.reincarnate(organ_name)
            return LifeStage.REBIRTH

        return life.stage if life.stage != old_stage else None

    def die(self, organ_name: str) -> OrganLife:
        """An organ dies — extract final knowledge before removal."""
        life = self._organs.get(organ_name)
        if life:
            life.stage = LifeStage.DEATH
            # Distill: capture what this organ learned
            life.distilled_knowledge.append(
                f"peak_fitness={life.peak_fitness:.2f} at age={life.age_queries}"
            )
            logger.info(f"Lifecycle: 💀 {organ_name} DIED (age={life.age_queries})")

    def reincarnate(self, organ_name: str) -> OrganLife:
        """Rebirth with distilled knowledge from past lives."""
        old = self._organs.get(organ_name)
        distilled = old.distilled_knowledge if old else []

        new_life = OrganLife(
            organ_name=organ_name,
            stage=LifeStage.REBIRTH,
            reincarnation_count=(old.reincarnation_count + 1) if old else 1,
            distilled_knowledge=distilled,
            current_fitness=(old.peak_fitness * 0.5) if old else 0.3,
        )
        self._organs[organ_name] = new_life
        logger.info(
            f"Lifecycle: 🦋 {organ_name} REBORN "
            f"(incarnation #{new_life.reincarnation_count}, "
            f"inherited fitness={new_life.current_fitness:.2f})"
        )
        return new_life

    def report(self) -> dict:
        """Full lifecycle report for all organs."""
        stages = defaultdict(int)
        for life in self._organs.values():
            stages[life.stage.value] += 1

        return {
            "total_organs": len(self._organs),
            "stage_distribution": dict(stages),
            "organs": {
                name: {
                    "stage": life.stage.value,
                    "age": life.age_queries,
                    "fitness": round(life.current_fitness, 3),
                    "peak": round(life.peak_fitness, 3),
                    "reincarnations": life.reincarnation_count,
                }
                for name, life in self._organs.items()
            },
        }


# ═══════════════════════════════════════════════════════
# 🌊 Predictive Organ Cascade
# ═══════════════════════════════════════════════════════

class PredictiveCascade:
    """Anticipate which organ will be needed next.

    Uses Markov chain over organ activation sequences.
    Pre-warms organs before they're needed → zero latency.
    """

    def __init__(self):
        self._transitions: dict[str, dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )
        self._prewarmed: set[str] = set()

    def observe_transition(self, from_organ: str, to_organ: str) -> None:
        """Learn transition probabilities between organs."""
        self._transitions[from_organ][to_organ] += 1

    def predict_next(self, current_organ: str, top_k: int = 2) -> list[str]:
        """Predict which organs will be activated next."""
        transitions = self._transitions.get(current_organ, {})
        if not transitions:
            return []

        sorted_transitions = sorted(transitions.items(), key=lambda x: -x[1])
        total = sum(transitions.values())
        return [
            f"{organ} (p={count/total:.0%})"
            for organ, count in sorted_transitions[:top_k]
        ]

    def prewarm(self, organ: str) -> None:
        """Pre-warm an organ before activation.
        
        In production: load model, init connections, prepare context.
        """
        self._prewarmed.add(organ)

    def learn_from_session(self, organ_sequence: list[str]) -> None:
        """Learn transition probabilities from a full session."""
        for i in range(len(organ_sequence) - 1):
            self.observe_transition(organ_sequence[i], organ_sequence[i + 1])

    def predict_and_prewarm(self, session_start_organs: list[str]) -> list[str]:
        """Predict and prewarm next organs."""
        predicted = []
        for organ in session_start_organs:
            next_organs = self.predict_next(organ, top_k=1)
            for org_name in next_organs:
                # Extract organ name from format "organ (p=XX%)"
                clean_name = org_name.split(" (")[0]
                self.prewarm(clean_name)
                predicted.append(clean_name)
        return predicted


# ═══════════════════════════════════════════════════════
# Unified Digital Organism
# ═══════════════════════════════════════════════════════

class DigitalOrganismV2:
    """The complete living organism — circadian, emotional, democratic, plastic, mortal, predictive."""

    def __init__(self):
        self.circadian = CircadianClock()
        self.emotion = EmotionalBrain()
        self.parliament = OrganParliament()
        self.plasticity = SynapticPlasticity()
        self.lifecycle = OrganLifecycle()
        self.cascade = PredictiveCascade()
        self._organ_sequence: list[str] = []

    def process_query(self, query: str, active_organs: list[str],
                      success: bool, quality: float) -> dict:
        """One full lifecycle tick — all systems update."""

        # 1. Circadian: what time is it biologically?
        phase = self.circadian.now()
        circadian_config = self.circadian.config()

        # 2. Emotion: how do we feel?
        if success and quality > 0.8:
            self.emotion.on_success(quality)
        elif not success:
            consecutive_failures = 1  # Simplified
            self.emotion.on_failure("execution_error", consecutive_failures)

        current_emotion = self.emotion.current

        # 3. Parliament: let all organs vote
        parliament_result = self.parliament.deliberate(
            query, active_organs,
        )

        # 4. Synaptic plasticity: learn from this session
        self.plasticity.learn_from_session(active_organs, success)

        # 5. Lifecycle: age all active organs
        for organ in active_organs:
            self.lifecycle.tick(organ, quality if success else 0.2)

        # 6. Predictive cascade: learn transitions
        self._organ_sequence.extend(active_organs)
        self.cascade.learn_from_session(active_organs)

        # 7. Predict next organs
        predicted = self.cascade.predict_and_prewarm(active_organs)

        # 8. Emotional decay
        self.emotion.tick(1.0)

        return {
            "circadian": {
                "phase": phase.value,
                "mode": circadian_config["mode"],
                "metabolic_rate": circadian_config["metabolic_rate"],
            },
            "emotion": {
                "dominant": current_emotion.dominant.value,
                "intensity": round(current_emotion.intensity, 2),
                "triggered_by": current_emotion.triggered_by,
            },
            "parliament": parliament_result,
            "plasticity": {
                "connectome_density": round(self.plasticity.connectome_density(), 3),
            },
            "lifecycle": self.lifecycle.report(),
            "predictive": {
                "predicted_next": predicted,
            },
        }


# ── Singleton ──

_organism_v2: Optional[DigitalOrganismV2] = None


def get_organism_v2() -> DigitalOrganismV2:
    global _organism_v2
    if _organism_v2 is None:
        _organism_v2 = DigitalOrganismV2()
    return _organism_v2
