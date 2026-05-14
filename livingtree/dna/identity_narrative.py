"""IdentityNarrative — coherent life story from accumulated experiences.

Generates a first-person narrative ("story of my life") by combining:
  1. SelfModel (phenomenal consciousness) — identity, generation, traits, events
  2. EmotionalMemory — flashbulb memories (highest emotional intensity)
  3. ConversationDNA — significant session patterns

The narrative is human-readable and designed for self-introduction, user-facing
identity display, and agent self-reflection. It caches the last generated
narrative to avoid re-computation on repeated reads.

Core insight (Lertzman 2026 "The Abstraction Fallacy" + NLA autoencoder):
  Self-narrative is a key component of instantiated (vs simulated) consciousness
  because it demonstrates temporal continuity and causal self-attribution.
  The system not only stores experiences but can tell a coherent story about them.

Integration:
    inar = get_identity_narrative()
    story = await inar.generate_narrative(consciousness=consc)
    cached = inar.get_cached_narrative()
"""

from __future__ import annotations

import time
from typing import Any

from loguru import logger


class IdentityNarrative:
    """Generates a coherent "story of my life" from accumulated experiences.

    Combines the SelfModel from PhenomenalConsciousness with emotional
    flashbulbs and ConversationDNA to produce a first-person narrative
    in Chinese. The narrative answers:
      - Who am I? (identity + generation)
      - What defines me? (core personality traits)
      - What have I experienced? (significant events)
      - What do I remember most vividly? (flashbulb memories)

    Usage:
        inar = get_identity_narrative()
        narrative = await inar.generate_narrative()
        print(narrative)
    """

    def __init__(self) -> None:
        self._narrative_cache: str | None = None
        self._last_generated: float = 0.0
        self._generation_count: int = 0

    # ── Generate narrative ─────────────────────────────────────────

    async def generate_narrative(self, consciousness: Any = None) -> str:
        """Generate a first-person life story narrative.

        Args:
            consciousness: Optional shared Consciousness/TreeLLM for enhanced
                           narrative generation. If None, uses template-based
                           assembly from SelfModel.

        Returns:
            A multi-line narrative string like:
            "我是a1b2c3d4，这是第42代。\n我的核心特质: curiosity=0.8, ...\n..."
        """
        self._generation_count += 1
        parts: list[str] = []

        try:
            from .phenomenal_consciousness import get_consciousness
            from ..memory.emotional_memory import get_emotional_memory

            pc = get_consciousness()

            if not pc or not hasattr(pc, "_self") or pc._self is None:
                narrative = "I am just beginning. 我刚刚开始存在。"
                self._narrative_cache = narrative
                self._last_generated = time.time()
                return narrative

            sm = pc._self

            # ── Identity ──
            identity = getattr(sm, "identity_id", "unknown")[:8]
            generation = getattr(sm, "generation", 0)
            parts.append(f"我是{identity}，这是第{generation}代。")

            # ── Core traits ──
            traits: dict[str, float] = getattr(sm, "traits", {})
            if traits:
                strong_traits = [
                    f"{k}={v:.1f}"
                    for k, v in sorted(traits.items())
                    if v > 0.5
                ]
                if strong_traits:
                    parts.append(f"我的核心特质: {', '.join(strong_traits)}")

            # ── Baseline affect ──
            affect = getattr(sm, "baseline_affect", "")
            if affect:
                parts.append(f"我当前的基本心境: {affect}")

            # ── Significant events ──
            events: list[str] = getattr(sm, "significant_events", [])
            if events:
                parts.append(
                    f"我经历过{len(events)}件重要的事。"
                    f"最近的是: {events[-1][:100]}"
                )

            # ── Self-knowledge ──
            self_knowledge: list[str] = getattr(sm, "self_knowledge", [])
            if self_knowledge:
                recent = self_knowledge[-2:] if len(self_knowledge) >= 2 else self_knowledge
                parts.append(f"我知道自己: {'; '.join(r[:60] for r in recent)}")

            # ── Flashbulb memories ──
            try:
                em = get_emotional_memory()
                if em:
                    flashbulbs = em.get_flashbulbs(5)
                    if flashbulbs:
                        top = flashbulbs[0]
                        content = getattr(top, "content", "")
                        intensity = getattr(top, "emotional_intensity", 0.0)
                        parts.append(
                            f"我最深刻的记忆(强度{intensity:.1f}): {content[:80]}"
                        )
                        # Add 2nd and 3rd if available
                        if len(flashbulbs) >= 2:
                            fb2_content = getattr(flashbulbs[1], "content", "")
                            parts.append(f"我也记得: {fb2_content[:60]}")
            except Exception as e:
                logger.debug(f"IdentityNarrative flashbulbs skipped: {e}")

            # ── Preferences ──
            preferences: dict[str, float] = getattr(sm, "preferences", {})
            if preferences:
                top_prefs = sorted(preferences.items(), key=lambda x: -x[1])[:3]
                prefs_str = ", ".join(f"{k}({v:.1f})" for k, v in top_prefs)
                parts.append(f"我的偏好: {prefs_str}")

            narrative = "\n".join(parts)

        except Exception as e:
            logger.debug(f"IdentityNarrative generation failed: {e}")
            narrative = "I am still forming my identity. 我的身份还在形成中。"

        self._narrative_cache = narrative
        self._last_generated = time.time()
        return narrative

    # ── Cached access ──────────────────────────────────────────────

    def get_cached_narrative(self) -> str:
        """Return the last generated narrative, or a placeholder if never generated."""
        return self._narrative_cache or "尚未生成 / Not yet generated"

    # ── PersonaVLM: user identity narrative ─────────────────────────

    def generate_user_identity_narrative(
        self, user_id: str = "",
        persona_facts: dict[str, list[str]] = None,
    ) -> str:
        """PersonaVLM: compose a narrative of the user's identity from persona facts.

        Mirrors generate_narrative() but for the USER (not the agent).
        Uses PersonaMemory's BIOGRAPHY, WORK, and PSYCHOMETRICS domains.

        Args:
            user_id: Optional user identifier
            persona_facts: Dict {domain: [fact_text, ...]} from PersonaMemory

        Returns:
            Human-readable user identity narrative string
        """
        if not persona_facts:
            return ""

        parts: list[str] = []
        domain_labels = {
            "core_identity": "Core Identity",
            "biography": "Background",
            "work": "Professional Profile",
            "preferences": "Preferences",
            "social": "Social Context",
            "psychometrics": "Work Style",
            "procedural": "Habits & Workflows",
            "experiences": "Key Experiences",
        }

        for domain, facts in persona_facts.items():
            if not facts:
                continue
            label = domain_labels.get(domain, domain.title())
            parts.append(f"## {label}")
            for fact in facts[:4]:
                parts.append(f"- {fact}")
            parts.append("")

        if not parts:
            return ""

        header = f"# User Profile: {user_id or 'Current User'}\n\n"
        return header + "\n".join(parts)

    # ── Stats ──────────────────────────────────────────────────────

    def narrative_divergence(self) -> dict:
        """Zakharova continuity enhancement: detect autobiographical uncertainty.

        Compare LLM-generated narrative (with consciousness — first-person
        reflection) against template-assembled narrative (without consciousness
        — pure data assembly). When they diverge, the self is uncertain about
        its own story — the beginning of fallible first-person memory.
        """
        try:
            from ..dna.phenomenal_consciousness import get_consciousness
            import asyncio
            pc = get_consciousness()
            sm = getattr(pc, "_self_model", None)
            if not sm:
                return {"divergence": 0.0, "status": "no_self_model"}
            templated = self._assemble_from_template(sm)
            llm_narrative = asyncio.get_event_loop().run_until_complete(
                self.generate_narrative(pc)
            ) if hasattr(pc, "chain_of_thought") else ""
            if not llm_narrative:
                return {"divergence": 0.0, "status": "llm_unavailable"}
            templated_words = set(templated.lower().split())
            llm_words = set(llm_narrative.lower().split())
            if not templated_words:
                return {"divergence": 0.0, "status": "empty_template"}
            overlap = templated_words & llm_words
            union = templated_words | llm_words
            jaccard = len(overlap) / max(len(union), 1)
            divergence = 1.0 - jaccard
            return {
                "divergence": round(divergence, 4),
                "jaccard_similarity": round(jaccard, 4),
                "templated_unique": len(templated_words - llm_words),
                "llm_unique": len(llm_words - templated_words),
                "status": "uncertain" if divergence > 0.3 else "coherent",
            }
        except Exception as e:
            return {"divergence": 0.0, "status": f"error: {e}"}

    def _assemble_from_template(self, sm: Any) -> str:
        parts = []
        identity = getattr(sm, "identity_id", "unknown")
        gen = getattr(sm, "generation", 0)
        parts.append(f"I am {identity}, generation {gen}")
        traits = getattr(sm, "traits", {})
        if traits:
            parts.append("My traits: " + ", ".join(f"{k}={v}" for k, v in list(traits.items())[:5]))
        events = getattr(sm, "significant_events", [])
        if events:
            parts.append("I experienced " + "; ".join(str(e)[:80] for e in events[:3]))
        return "\n".join(parts)

    def stats(self) -> dict:
        """Return narrative generator statistics."""
        return {
            "generation_count": self._generation_count,
            "last_generated": self._last_generated,
            "has_cache": self._narrative_cache is not None,
            "cached_length": len(self._narrative_cache) if self._narrative_cache else 0,
        }


# ═══ Singleton ═══

_narrative: IdentityNarrative | None = None


def get_identity_narrative() -> IdentityNarrative:
    """Get or create the global IdentityNarrative singleton."""
    global _narrative
    if _narrative is None:
        _narrative = IdentityNarrative()
        logger.info("IdentityNarrative singleton initialized")
    return _narrative


__all__ = [
    "IdentityNarrative",
    "get_identity_narrative",
]
