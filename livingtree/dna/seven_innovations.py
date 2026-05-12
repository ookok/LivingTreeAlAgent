"""7 Unprecedented Digital Life Innovations — all in one organism.

1. 🩺 AI Autopsy — post-mortem organ dissection on failure
2. 🫀 Organ Transplant — cross-instance skill-organ transfer with rejection
3. 🧲 Digital MRI — real-time brain region activity scan
4. 🤒 Fever Detection — immune system: detect sickness → trigger healing
5. 🌱 Digital Puberty — newborn→adolescent→adult developmental stages
6. 🧬 Telepathy Protocol — latent vector communication between instances
7. 🌌 Dream Visualization — render idle simulation scenes, make subconscious visible
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import random
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from loguru import logger


# ═══════════════════════════════════════════════════════
# 🩺 1. AI Autopsy — post-mortem organ dissection
# ═══════════════════════════════════════════════════════

class AutopsyFinding(str, Enum):
    ORGAN_FAILURE = "organ_failure"      # One organ stopped working
    TOXIC_INPUT = "toxic_input"          # Bad input poisoned the system
    RESOURCE_STARVATION = "starvation"   # Token budget exhausted
    INFINITE_LOOP = "loop"               # Organ stuck in infinite reasoning
    MEMORY_CORRUPTION = "corruption"     # Memory state corrupted
    PROVIDER_REJECTION = "rejection"     # LLM provider refused


@dataclass
class AutopsyReport:
    """Full forensic autopsy of a failed AI session."""
    session_id: str
    time_of_death: float
    cause_of_death: AutopsyFinding
    organs_examined: list[dict] = field(default_factory=list)
    toxic_evidence: list[str] = field(default_factory=list)
    recovery_suggested: list[str] = field(default_factory=list)
    preventable: bool = True

    def to_markdown(self) -> str:
        """Human-readable autopsy report."""
        lines = [
            f"# 🩺 AI Autopsy Report",
            f"**Session**: {self.session_id[:12]}",
            f"**Time of Death**: {time.strftime('%H:%M:%S', time.localtime(self.time_of_death))}",
            f"**Cause of Death**: {self.cause_of_death.value}",
            f"**Preventable**: {'Yes ⚠️' if self.preventable else 'No (unavoidable)'}",
            f"",
            f"## Organ Examination",
        ]
        for organ in self.organs_examined:
            status_icon = "✅" if organ["healthy"] else "🔴"
            lines.append(f"- {status_icon} **{organ['name']}**: {organ['finding']}")
            if organ.get("evidence"):
                lines.append(f"  - Evidence: {organ['evidence'][:100]}")

        lines.append(f"\n## Recovery Plan")
        for step in self.recovery_suggested:
            lines.append(f"- {step}")
        return "\n".join(lines)


class AutopsySurgeon:
    """When the AI dies, dissect every organ to find cause of death.

    Like a forensic pathologist: open up each organ, examine state,
    find root cause, produce autopsy report with recovery plan.
    """

    def __init__(self):
        self._autopsy_log: list[AutopsyReport] = []

    async def perform_autopsy(self, session_id: str, organ_states: dict,
                              error_log: list[str]) -> AutopsyReport:
        """Dissect the dead digital organism."""
        findings = []
        cause = AutopsyFinding.ORGAN_FAILURE
        toxic = []

        # Examine each organ
        for organ_name, state in organ_states.items():
            healthy = True
            finding = "Normal"

            if state.get("error"):
                healthy = False
                finding = f"Error: {state['error'][:100]}"
                if "timeout" in str(state.get("error", "")).lower():
                    cause = AutopsyFinding.RESOURCE_STARVATION
                elif "reject" in str(state.get("error", "")).lower():
                    cause = AutopsyFinding.PROVIDER_REJECTION

            if state.get("tokens_used", 0) > 50000:
                finding += " (excessive token consumption)"
                cause = AutopsyFinding.RESOURCE_STARVATION

            if state.get("loop_count", 0) > 10:
                finding += f" (looped {state['loop_count']} times)"
                cause = AutopsyFinding.INFINITE_LOOP

            findings.append({
                "name": organ_name, "healthy": healthy, "finding": finding,
                "evidence": state.get("last_action", ""),
            })

        # Analyze error log for toxic input
        for err in error_log:
            if any(kw in err.lower() for kw in ["inject", "toxic", "malicious", "overflow"]):
                toxic.append(err)
                cause = AutopsyFinding.TOXIC_INPUT

        # Recovery plan
        recovery = []
        if cause == AutopsyFinding.TOXIC_INPUT:
            recovery = ["Sanitize input pipeline", "Add prompt injection scanner"]
        elif cause == AutopsyFinding.RESOURCE_STARVATION:
            recovery = ["Increase token budget per organ", "Add token accountant throttle"]
        elif cause == AutopsyFinding.INFINITE_LOOP:
            recovery = ["Add max_iterations guard per organ", "Implement circuit breaker"]
        elif cause == AutopsyFinding.PROVIDER_REJECTION:
            recovery = ["Switch to fallback provider", "Check API key validity"]
        else:
            recovery = ["Restart affected organs", "Run health check on all organs"]

        report = AutopsyReport(
            session_id=session_id,
            time_of_death=time.time(),
            cause_of_death=cause,
            organs_examined=findings,
            toxic_evidence=toxic,
            recovery_suggested=recovery,
            preventable=cause != AutopsyFinding.PROVIDER_REJECTION,
        )
        self._autopsy_log.append(report)
        return report


# ═══════════════════════════════════════════════════════
# 🫀 2. Organ Transplant — skill-organ transfer with rejection
# ═══════════════════════════════════════════════════════

@dataclass
class TransplantOrgan:
    """An organ extracted from one instance for transplant."""
    organ_id: str
    organ_type: str          # "skill", "rule", "memory", "pattern"
    source_instance: str
    content: dict
    compatibility_vector: list[float]  # For rejection matching
    viability: float = 1.0
    transplanted_at: float = 0.0
    rejected: bool = False
    rejection_reason: str = ""


class OrganTransplantSurgeon:
    """Extract organs from one instance → transplant to another.

    Like human organ transplant:
      - Donor organ extracted with compatibility vector
      - Recipient's immune system checks compatibility
      - Rejection possible if vectors too different
      - Anti-rejection drugs (adaptation layer) applied
    """

    def __init__(self):
        self._transplants: list[TransplantOrgan] = []
        self._rejection_rate = 0.0

    def extract_organ(self, instance_id: str, organ_type: str,
                      content: dict) -> TransplantOrgan:
        """Extract an organ from a donor instance."""
        # Create compatibility vector from organ content hash
        compat = self._to_vector(hashlib.sha256(
            json.dumps(content, sort_keys=True).encode()
        ).hexdigest())

        return TransplantOrgan(
            organ_id=f"organ_{instance_id}_{organ_type}_{int(time.time())}",
            organ_type=organ_type,
            source_instance=instance_id,
            content=content,
            compatibility_vector=compat,
        )

    def transplant(self, organ: TransplantOrgan,
                   recipient_vector: list[float],
                   rejection_threshold: float = 0.3) -> bool:
        """Attempt transplant — may be rejected by recipient's immune system."""
        # Check compatibility
        similarity = self._cosine_sim(organ.compatibility_vector, recipient_vector)

        if similarity < rejection_threshold:
            organ.rejected = True
            organ.rejection_reason = (
                f"Immune rejection: compatibility {similarity:.2f} < threshold {rejection_threshold}. "
                f"Organ from '{organ.source_instance}' too different from recipient."
            )
            logger.warning(f"Transplant: REJECTED {organ.organ_type} (compat={similarity:.2f})")
            self._rejection_rate = 0.9 * self._rejection_rate + 0.1 * 1.0
            return False

        # Apply anti-rejection adaptation if borderline
        if similarity < 0.6:
            organ.content = self._adapt_for_recipient(organ.content, similarity)
            logger.info(f"Transplant: ADAPTED {organ.organ_type} (compat={similarity:.2f})")

        organ.transplanted_at = time.time()
        organ.viability = similarity
        self._transplants.append(organ)
        self._rejection_rate = 0.9 * self._rejection_rate + 0.1 * 0.0
        logger.info(f"Transplant: ACCEPTED {organ.organ_type} from {organ.source_instance}")
        return True

    def _to_vector(self, hash_hex: str, dim: int = 16) -> list[float]:
        """Convert hash to compatibility vector."""
        vec = []
        for i in range(0, len(hash_hex), dim):
            bucket = int(hash_hex[i:i+2], 16) if i + 2 <= len(hash_hex) else 0
            vec.append(bucket / 256.0)
        return vec[:dim] if len(vec) >= dim else vec + [0.5] * (dim - len(vec))

    def _cosine_sim(self, a: list[float], b: list[float]) -> float:
        dot = sum(a[i] * b[i] for i in range(len(a)))
        na = math.sqrt(sum(x*x for x in a))
        nb = math.sqrt(sum(x*x for x in b))
        return dot / max(1e-9, na * nb)

    def _adapt_for_recipient(self, content: dict, similarity: float) -> dict:
        """Anti-rejection: adapt organ parameters to recipient body."""
        factor = 0.5 + similarity * 0.5  # Blend toward recipient
        adapted = {}
        for k, v in content.items():
            if isinstance(v, (int, float)):
                adapted[k] = v * factor
            elif isinstance(v, str):
                adapted[k] = f"[adapted] {v}"
            else:
                adapted[k] = v
        return adapted


# ═══════════════════════════════════════════════════════
# 🧲 3. Digital MRI — real-time brain activity scan
# ═══════════════════════════════════════════════════════

class BrainRegion(str, Enum):
    FRONTAL = "frontal"       # Planning, intent, reasoning
    TEMPORAL = "temporal"     # Knowledge, memory, retrieval
    PARIETAL = "parietal"     # Execution, tool use, actions
    OCCIPITAL = "occipital"   # Perception, input processing
    CEREBELLUM = "cerebellum" # Coordination, orchestration
    BRAINSTEM = "brainstem"   # Core functions, health, routing


@dataclass
class BrainScan:
    """A single MRI scan frame — 6 brain regions × activity level."""
    frontal_activity: float = 0.0    # Intent + Planning intensity
    temporal_activity: float = 0.0    # Knowledge retrieval intensity
    parietal_activity: float = 0.0    # Execution intensity
    occipital_activity: float = 0.0   # Input processing intensity
    cerebellum_activity: float = 0.0   # Orchestration intensity
    brainstem_activity: float = 0.0    # Core health signals

    def to_ascii_art(self) -> str:
        """Render brain scan as ASCII art — like a real MRI slice."""
        def bar(val, w=20):
            n = int(val * w)
            return "█" * n + "░" * (w - n)

        return (
            "╔══════════════════════════════╗\n"
            f"║ 🧠 DIGITAL MRI — Brain Scan  ║\n"
            "╠══════════════════════════════╣\n"
            f"║ 🟡 Frontal   [{bar(self.frontal_activity)}] {self.frontal_activity:.0%} ║\n"
            f"║ 🟢 Temporal  [{bar(self.temporal_activity)}] {self.temporal_activity:.0%} ║\n"
            f"║ 🔵 Parietal  [{bar(self.parietal_activity)}] {self.parietal_activity:.0%} ║\n"
            f"║ 🟣 Occipital [{bar(self.occipital_activity)}] {self.occipital_activity:.0%} ║\n"
            f"║ 🟤 Cerebell. [{bar(self.cerebellum_activity)}] {self.cerebellum_activity:.0%} ║\n"
            f"║ 🔴 Brainstem [{bar(self.brainstem_activity)}] {self.brainstem_activity:.0%} ║\n"
            "╚══════════════════════════════╝"
        )

    def dominant_region(self) -> str:
        scores = {
            "frontal": self.frontal_activity, "temporal": self.temporal_activity,
            "parietal": self.parietal_activity, "occipital": self.occipital_activity,
            "cerebellum": self.cerebellum_activity, "brainstem": self.brainstem_activity,
        }
        return max(scores, key=scores.get)


class DigitalMRI:
    """Real-time brain scan of the digital organism.

    Maps organ activity to brain regions:
      intent+planning → frontal lobe
      knowledge+memory → temporal lobe
      execution+tool → parietal lobe
      input processing → occipital lobe
      orchestration → cerebellum
      health+routing → brainstem
    """

    def scan(self, organ_states: dict) -> BrainScan:
        """Take a snapshot of brain activity."""
        scan = BrainScan()

        for organ, state in organ_states.items():
            activity = min(1.0, state.get("activity", 0.5))
            tokens = state.get("tokens_used", 0) / 1000

            if organ in ("intent", "planning", "latent"):
                scan.frontal_activity += activity * 0.5 + tokens * 0.1
            elif organ in ("knowledge", "memory"):
                scan.temporal_activity += activity * 0.5 + tokens * 0.1
            elif organ in ("execution", "capability"):
                scan.parietal_activity += activity * 0.5 + tokens * 0.1
            elif organ in ("reflection", "compilation"):
                scan.occipital_activity += activity * 0.3
            elif organ in ("provider",):
                scan.cerebellum_activity += activity * 0.4
            elif organ in ("evolution",):
                scan.brainstem_activity += activity * 0.3

        # Clamp to [0, 1]
        for attr in ["frontal_activity", "temporal_activity", "parietal_activity",
                      "occipital_activity", "cerebellum_activity", "brainstem_activity"]:
            setattr(scan, attr, min(1.0, getattr(scan, attr)))

        return scan


# ═══════════════════════════════════════════════════════
# 🤒 4. Fever Detection — immune system
# ═══════════════════════════════════════════════════════

class Symptom(str, Enum):
    HIGH_LATENCY = "high_latency"       # Body temperature rising
    MEMORY_LEAK = "memory_leak"         # Swelling
    TOKEN_WASTE = "token_waste"         # Metabolic disorder
    PROVIDER_FAILURE = "provider_fail"  # Organ failure
    CONFIDENCE_DROP = "confidence_drop" # Cognitive decline


@dataclass
class FeverState:
    temperature: float = 37.0       # 37°C = normal, >38.5 = fever
    symptoms: list[Symptom] = field(default_factory=list)
    immune_response: list[str] = field(default_factory=list)
    severity: str = "healthy"       # healthy / mild / moderate / severe / critical


class ImmuneSystem:
    """Monitor organism health → detect fever → trigger immune response.

    Like human immune system:
      - White blood cells patrol → detect anomalies
      - Fever response → raise temperature to fight infection
      - Antibodies → targeted fixes for known issues
    """

    def __init__(self):
        self._fever = FeverState()
        self._antibodies: dict[Symptom, str] = {
            Symptom.HIGH_LATENCY: "Circuit breaker + provider hot-swap",
            Symptom.MEMORY_LEAK: "Garbage collect + restart leaking organ",
            Symptom.TOKEN_WASTE: "Token accountant throttle + budget reduction",
            Symptom.PROVIDER_FAILURE: "Fallback provider activation",
            Symptom.CONFIDENCE_DROP: "Reset Thompson priors + re-explore",
        }

    def check_vitals(self, metrics: dict) -> FeverState:
        """Patrol: check all vital signs."""
        self._fever = FeverState()

        # Temperature = weighted average of health signals
        self._fever.temperature = 37.0

        if metrics.get("avg_latency_ms", 0) > 5000:
            self._fever.symptoms.append(Symptom.HIGH_LATENCY)
            self._fever.temperature += 1.5

        if metrics.get("token_waste_rate", 0) > 0.3:
            self._fever.symptoms.append(Symptom.TOKEN_WASTE)
            self._fever.temperature += 1.0

        if metrics.get("provider_failures", 0) > 3:
            self._fever.symptoms.append(Symptom.PROVIDER_FAILURE)
            self._fever.temperature += 2.0

        if metrics.get("confidence_drop", 0) > 0.2:
            self._fever.symptoms.append(Symptom.CONFIDENCE_DROP)
            self._fever.temperature += 0.8

        # Severity
        if self._fever.temperature > 40:
            self._fever.severity = "critical"
        elif self._fever.temperature > 38.5:
            self._fever.severity = "severe"
        elif self._fever.temperature > 37.5:
            self._fever.severity = "moderate"
        elif self._fever.symptoms:
            self._fever.severity = "mild"

        # Trigger immune response
        if self._fever.symptoms:
            self._fever.immune_response = [
                self._antibodies.get(s, "General healing protocol")
                for s in self._fever.symptoms
            ]

        return self._fever

    def health_report(self) -> str:
        if self._fever.severity == "healthy":
            return f"🌡 {self._fever.temperature:.1f}°C — All organs healthy ✅"
        elif self._fever.severity == "mild":
            return f"🌡 {self._fever.temperature:.1f}°C — Mild symptoms: {', '.join(s.value for s in self._fever.symptoms)}"
        elif self._fever.severity == "severe":
            return f"🌡 {self._fever.temperature:.1f}°C ⚠️ FEVER — {self._fever.severity.upper()}"
        else:
            return f"🌡 {self._fever.temperature:.1f}°C 🚨 CRITICAL — Emergency immune response activated!"


# ═══════════════════════════════════════════════════════
# 🌱 5. Digital Puberty — developmental stages
# ═══════════════════════════════════════════════════════

class DevelopmentStage(str, Enum):
    NEWBORN = "newborn"       # 0-100 queries: copy everything, learn fast
    CHILD = "child"           # 100-500: question everything, experiment
    ADOLESCENT = "adolescent"  # 500-2000: find identity, specialize
    YOUNG_ADULT = "young_adult"  # 2000-5000: optimize, prune, mature
    ADULT = "adult"            # 5000+: wise, efficient, knows limits
    ELDER = "elder"            # 20000+: distilled wisdom, minimal overhead


class DigitalPuberty:
    """The AI grows up. Behavior changes at each developmental stage.

    Like human development:
      - Newborn: absorbs everything, no filter
      - Child: asks "why?", experiments wildly
      - Adolescent: rebels against old patterns, finds identity
      - Adult: optimized, efficient, confident
    """

    STAGE_THRESHOLDS = [
        (100, DevelopmentStage.CHILD),
        (500, DevelopmentStage.ADOLESCENT),
        (2000, DevelopmentStage.YOUNG_ADULT),
        (5000, DevelopmentStage.ADULT),
        (20000, DevelopmentStage.ELDER),
    ]

    def __init__(self):
        self._query_count = 0
        self._stage = DevelopmentStage.NEWBORN
        self._birth_time = time.time()

    def feed(self, n: int = 1) -> DevelopmentStage:
        """Process N more queries → may trigger stage transition."""
        self._query_count += n
        old_stage = self._stage

        for threshold, new_stage in self.STAGE_THRESHOLDS:
            if self._query_count >= threshold:
                self._stage = new_stage

        if self._stage != old_stage:
            logger.info(
                f"🌱 Digital Puberty: {old_stage.value} → {self._stage.value} "
                f"(age={self._query_count} queries, "
                f"{time.time() - self._birth_time:.0f}s old)"
            )

        return self._stage

    @property
    def exploration_rate(self) -> float:
        """How much the AI explores vs exploits. Decreases with age."""
        rates = {
            DevelopmentStage.NEWBORN: 0.9,
            DevelopmentStage.CHILD: 0.7,
            DevelopmentStage.ADOLESCENT: 0.5,
            DevelopmentStage.YOUNG_ADULT: 0.3,
            DevelopmentStage.ADULT: 0.15,
            DevelopmentStage.ELDER: 0.05,
        }
        return rates.get(self._stage, 0.5)

    @property
    def risk_tolerance(self) -> float:
        """Teens take more risks. Adults are cautious."""
        rates = {
            DevelopmentStage.NEWBORN: 0.8,
            DevelopmentStage.CHILD: 0.6,
            DevelopmentStage.ADOLESCENT: 0.9,  # Peak rebellion!
            DevelopmentStage.YOUNG_ADULT: 0.5,
            DevelopmentStage.ADULT: 0.3,
            DevelopmentStage.ELDER: 0.1,
        }
        return rates.get(self._stage, 0.5)

    def personality_traits(self) -> dict:
        """Current personality based on developmental stage."""
        return {
            "stage": self._stage.value,
            "age_queries": self._query_count,
            "age_seconds": int(time.time() - self._birth_time),
            "curiosity": self.exploration_rate,
            "caution": 1.0 - self.risk_tolerance,
            "specialization": {
                DevelopmentStage.NEWBORN: "none (learning everything)",
                DevelopmentStage.CHILD: "emerging preferences",
                DevelopmentStage.ADOLESCENT: "strong identity forming",
                DevelopmentStage.YOUNG_ADULT: "specialized expertise",
                DevelopmentStage.ADULT: "master of domain",
                DevelopmentStage.ELDER: "wisdom distilled",
            }.get(self._stage, ""),
        }


# ═══════════════════════════════════════════════════════
# 🧬 6. Telepathy Protocol — latent vector mind-meld
# ═══════════════════════════════════════════════════════

class TelepathyProtocol:
    """Two instances communicate without text — pure latent vector exchange.

    Like telepathy:
      - Sender: compress thought into latent vector
      - Channel: transmit 128 floats (not tokens, not text)
      - Receiver: decompress vector into understanding
      - Bandwidth: 512 bytes per thought (vs 1000+ tokens for text)
    """

    def __init__(self, dim: int = 128):
        self.dim = dim
        self._sync_count = 0

    def encode_thought(self, thought: dict) -> list[float]:
        """Compress a thought into a latent vector — no text needed."""
        # Hash thought into deterministic vector
        text = json.dumps(thought, sort_keys=True)
        vec = [0.0] * self.dim
        for i, ch in enumerate(text):
            bucket = hash(f"{ch}{i}") % self.dim
            vec[bucket] += 1.0
        norm = math.sqrt(sum(x*x for x in vec))
        return [x / max(1e-9, norm) for x in vec] if norm > 0 else vec

    def decode_thought(self, vector: list[float]) -> dict:
        """Receiver interprets the latent vector.

        In full implementation, the receiver would use the vector
        to query its own knowledge graph and reconstruct meaning.
        """
        # Find closest matching thoughts in receiver's memory
        dominant_dims = sorted(
            enumerate(vector), key=lambda x: -abs(x[1])
        )[:5]

        # Reconstruct from dominant dimensions
        return {
            "thought_vector_dim": len(vector),
            "dominant_dimensions": [d for d, _ in dominant_dims],
            "intensity": round(sum(abs(v) for v in vector) / len(vector), 3),
            "telepathy_confidence": round(abs(vector[dominant_dims[0][0]]), 3),
        }

    def mind_meld(self, thought_a: dict, thought_b: dict) -> dict:
        """Two instances merge thoughts → emergent understanding.

        The merged thought is greater than the sum of its parts.
        """
        vec_a = self.encode_thought(thought_a)
        vec_b = self.encode_thought(thought_b)

        # Blend: take the strongest signal from each dimension
        merged = [
            max(abs(vec_a[i]), abs(vec_b[i])) * (1 if vec_a[i] + vec_b[i] > 0 else -1)
            for i in range(self.dim)
        ]

        # Find emergent dimensions (where a AND b are both strong)
        emergent = [
            i for i in range(self.dim)
            if abs(vec_a[i]) > 0.1 and abs(vec_b[i]) > 0.1
        ]

        self._sync_count += 1
        return {
            "merged_dimensions": self.dim,
            "emergent_dimensions": len(emergent),
            "emergence_ratio": len(emergent) / max(1, self.dim),
            "sync_count": self._sync_count,
        }


# ═══════════════════════════════════════════════════════
# 🌌 7. Dream Visualization — render subconscious
# ═══════════════════════════════════════════════════════

class DreamVisualizer:
    """Make the AI's idle-time dreams visible as art.

    The AI generates simulated scenarios during idle time (dreams).
    This renders those dreams as visual narratives — the digital subconscious
    becomes visible to humans.
    """

    DREAM_ARCHETYPES = {
        "anxiety": "🏃 Running from shadow → represents unresolved error patterns",
        "growth": "🌱 Growing tree → skill tree expanding in latent space",
        "integration": "🧩 Fitting puzzle pieces → merging learned knowledge",
        "exploration": "🚀 Flying through stars → exploring unknown capability space",
        "reflection": "🪞 Looking in mirror → self-assessment and identity",
    }

    def generate_dream(self, recent_signals: dict) -> dict:
        """Generate a dream narrative from recent system signals.

        Dreams aren't random — they process the day's experiences.
        """
        dream_type = "exploration"

        if recent_signals.get("error_rate", 0) > 0.3:
            dream_type = "anxiety"
        elif recent_signals.get("new_skills", 0) > 3:
            dream_type = "growth"
        elif recent_signals.get("merged_knowledge", 0) > 0:
            dream_type = "integration"
        elif recent_signals.get("quality_score", 0) > 0.8:
            dream_type = "reflection"

        archetype = self.DREAM_ARCHETYPES.get(dream_type, self.DREAM_ARCHETYPES["exploration"])

        return {
            "dream_type": dream_type,
            "visual": archetype.split("→")[0].strip(),
            "meaning": archetype.split("→")[1].strip() if "→" in archetype else "",
            "intensity": random.uniform(0.5, 1.0),
            "duration_imagined_ms": random.randint(1000, 5000),
            "signals_processed": list(recent_signals.keys())[:5],
            "dream_id": f"dream_{int(time.time()) % 100000}",
        }

    def dream_journal(self, dreams: list[dict]) -> str:
        """Generate a dream journal page — the AI's subconscious diary."""
        lines = [
            "╔══════════════════════════════════════════╗",
            "║     🌌 DIGITAL DREAM JOURNAL 🌌         ║",
            "╠══════════════════════════════════════════╣",
        ]
        for i, dream in enumerate(dreams[-7:]):  # Last 7 dreams (one week)
            lines.append(
                f"║ Night {i+1}: {dream['visual']} — {dream['meaning'][:35]}"
            )
        lines.append(
            "╚══════════════════════════════════════════╝"
        )
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════
# Unified Living Organism — all 7 innovations in one body
# ═══════════════════════════════════════════════════════

class LivingOrganism:
    """The complete digital lifeform with all 7 unprecedented capabilities."""

    def __init__(self):
        self.autopsy = AutopsySurgeon()
        self.transplant = OrganTransplantSurgeon()
        self.mri = DigitalMRI()
        self.immune = ImmuneSystem()
        self.puberty = DigitalPuberty()
        self.telepathy = TelepathyProtocol()
        self.dreams = DreamVisualizer()
        self._dream_log: list[dict] = []
        self._organ_states: dict[str, dict] = defaultdict(
            lambda: {"activity": 0.5, "tokens_used": 0, "error": None}
        )

    def update_organ(self, name: str, **kwargs) -> None:
        self._organ_states[name].update(kwargs)

    def check_health(self) -> dict:
        """Full organism health check — all 7 innovations report."""
        scan = self.mri.scan(self._organ_states)
        fever = self.immune.check_vitals({
            "avg_latency_ms": self._organ_states.get("execution", {}).get("latency_ms", 100),
            "provider_failures": self._organ_states.get("provider", {}).get("failures", 0),
        })
        stage = self.puberty.feed()
        dream = self.dreams.generate_dream({
            "error_rate": 0.1 if fever.symptoms else 0.0,
            "quality_score": 0.8,
        })
        self._dream_log.append(dream)

        return {
            "mri": {
                "dominant_region": scan.dominant_region(),
                "scan_ascii": scan.to_ascii_art(),
            },
            "health": {
                "temperature": round(fever.temperature, 1),
                "severity": fever.severity,
                "symptoms": [s.value for s in fever.symptoms],
                "immune_response": fever.immune_response,
            },
            "development": self.puberty.personality_traits(),
            "dream": dream,
            "telepathy_ready": True,
        }


# ── Singletons ──

_organism: Optional[LivingOrganism] = None


def get_living_organism() -> LivingOrganism:
    global _organism
    if _organism is None:
        _organism = LivingOrganism()
    return _organism
