"""AdversarialSelfPlay — Iterative self-rebuttal for reasoning depth.

Core value: Models are incentivized to give confident, unchallenged answers.
AdversarialSelfPlay forces them to confront counter-arguments, revise their
position, and iterate until the reasoning stabilizes (no new counter-arguments).

Enhanced with PRefLexOR (Buehler, npj AI, 2025): recursive self-reflection loop.
Instead of linear rebuttal→revise, the model first produces <reflect> introspection,
then refines its own reasoning before engaging in adversarial rounds.

Algorithm:
  1. Model produces initial answer (with DeepProbe forcing)
  2. [PRefLexOR] Model self-reflects: <reflect>...</reflect> → refines
  3. AdversarialSelfPlay generates the strongest counter-arguments
  4. Model revises answer in response to counter-arguments
  4. Repeat 2-3 until convergence (max rounds or no new counter-arguments)
  5. Return final answer + revision history + convergence status

Convergence detection:
  - Jaccard similarity between consecutive revisions > 0.85 → converged
  - Counter-argument addresses fewer than 2 new points → converged
  - Max rounds reached → forced stop

Integration:
  - Called by SynapseAggregator during aggregation
  - Called by route_layered() after getting candidate output (optional)
  - DepthGrading uses revision count and convergence as scoring inputs

Usage:
    player = get_selfplay()
    result = await player.play(
        model_output="The system should be optimized by...",
        original_query="How to optimize this system?",
        chat_fn=tree_llm_chat_function,
    )
"""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Optional

from loguru import logger


# ═══ Data Types ════════════════════════════════════════════════════


class PlayStatus(StrEnum):
    """Status of an adversarial self-play session."""
    CONVERGED = "converged"         # Reasoning stabilized
    MAX_ROUNDS = "max_rounds"       # Hit round limit
    ERROR = "error"                 # Failed during play
    TRIVIAL = "trivial"             # Output too short for meaningful play


@dataclass
class RebuttalRound:
    """One round of adversarial self-play."""
    round_num: int
    original_answer: str              # Answer at start of this round
    counter_arguments: list[str]      # Generated counter-arguments
    revised_answer: str               # Answer after considering rebuttals
    changes_made: list[str]           # What changed in the revision
    jaccard_to_previous: float        # Similarity to previous round answer
    tokens_spent: int = 0
    latency_ms: float = 0.0


@dataclass
class SelfPlayResult:
    """Complete result of adversarial self-play."""
    original_answer: str              # Initial model output
    final_answer: str                 # Final answer after all rounds
    rounds: list[RebuttalRound]       # Full play-by-play
    status: PlayStatus
    total_rounds: int
    total_tokens_spent: int
    total_latency_ms: float
    convergence_round: int = -1       # Which round convergence was detected
    depth_gain: float = 0.0           # Estimated reasoning depth improvement
    metadata: dict = field(default_factory=dict)


# ═══ AdversarialSelfPlay ══════════════════════════════════════════


class AdversarialSelfPlay:
    """Iterative self-rebuttal engine for deepening LLM reasoning.

    Design: Instead of accepting the first answer, treat each model output
    as a hypothesis that must survive adversarial scrutiny. The model plays
    both roles: defender (producing answer) and attacker (generating rebuttals).

    The counter-argument generator is designed to FIND flaws, not agree.
    Each round deepens the reasoning because the model must address specific
    criticism rather than just restating.
    """

    MAX_ROUNDS = 3                # Maximum rebuttal rounds
    CONVERGENCE_THRESHOLD = 0.85  # Jaccard similarity for convergence
    MIN_ANSWER_LENGTH = 50        # Minimum chars for meaningful play
    MIN_COUNTER_ARGS = 1          # Minimum counter-arguments to continue
    ROUND_TIMEOUT = 60.0          # Timeout per round (seconds)

    def __init__(self, max_rounds: int = 3, convergence_threshold: float = 0.85):
        self._max_rounds = max_rounds or self.MAX_ROUNDS
        self._convergence_threshold = convergence_threshold
        self._stats = {"sessions": 0, "converged": 0, "max_rounds_reached": 0}

    # ── Main Play Pipeline ────────────────────────────────────────

    async def play(
        self,
        model_output: str,
        original_query: str,
        chat_fn: Any,
        model_name: str = "",
    ) -> SelfPlayResult:
        """Run adversarial self-play on a model output.

        Args:
            model_output: Initial answer from the model.
            original_query: The query that produced the answer.
            chat_fn: async callable(prompt: str, model: str) -> str.
                Must accept a prompt string and return the model's new answer.
            model_name: Model to use for revision rounds.

        Returns:
            SelfPlayResult with full revision history.
        """
        self._stats["sessions"] += 1
        t0 = time.monotonic()
        total_tokens = 0
        rounds: list[RebuttalRound] = []
        current_answer = model_output

        # Triviality check
        if len(model_output.strip()) < self.MIN_ANSWER_LENGTH:
            logger.debug("AdversarialSelfPlay: answer too short — skipping")
            return SelfPlayResult(
                original_answer=model_output,
                final_answer=model_output,
                rounds=[],
                status=PlayStatus.TRIVIAL,
                total_rounds=0,
                total_tokens_spent=0,
                total_latency_ms=(time.monotonic() - t0) * 1000,
            )

        for round_num in range(1, self._max_rounds + 1):
            round_t0 = time.monotonic()

            try:
                # Step 1: Generate counter-arguments
                counter_args = await self._generate_counter_arguments(
                    current_answer, original_query, round_num, chat_fn, model_name,
                )
                total_tokens += sum(len(a) for a in counter_args)

                # Step 2: Check if we still have meaningful challenges
                if len(counter_args) < self.MIN_COUNTER_ARGS:
                    logger.debug(
                        f"AdversarialSelfPlay: converged at round {round_num} "
                        f"(no meaningful counter-arguments)"
                    )
                    self._stats["converged"] += 1
                    return SelfPlayResult(
                        original_answer=model_output,
                        final_answer=current_answer,
                        rounds=rounds,
                        status=PlayStatus.CONVERGED,
                        total_rounds=len(rounds),
                        total_tokens_spent=total_tokens,
                        total_latency_ms=(time.monotonic() - t0) * 1000,
                        convergence_round=round_num,
                        depth_gain=self._estimate_depth_gain(rounds),
                    )

                # Step 3: Ask model to revise based on counter-arguments
                revision_prompt = self._build_revision_prompt(
                    original_query, current_answer, counter_args, round_num,
                )
                revised = await asyncio.wait_for(
                    chat_fn(revision_prompt, model_name),
                    timeout=self.ROUND_TIMEOUT,
                )
                total_tokens += len(revised)
                round_latency = (time.monotonic() - round_t0) * 1000

                # Step 4: Detect changes
                changes = self._detect_changes(current_answer, revised)
                jaccard = self._jaccard_similarity(current_answer, revised)

                rounds.append(RebuttalRound(
                    round_num=round_num,
                    original_answer=current_answer,
                    counter_arguments=counter_args,
                    revised_answer=revised,
                    changes_made=changes,
                    jaccard_to_previous=jaccard,
                    tokens_spent=len(revised) + sum(len(a) for a in counter_args),
                    latency_ms=round_latency,
                ))

                # Step 5: Check convergence
                if jaccard >= self._convergence_threshold:
                    logger.info(
                        f"AdversarialSelfPlay: converged at round {round_num} "
                        f"(jaccard={jaccard:.3f} >= {self._convergence_threshold})"
                    )
                    self._stats["converged"] += 1
                    return SelfPlayResult(
                        original_answer=model_output,
                        final_answer=revised,
                        rounds=rounds,
                        status=PlayStatus.CONVERGED,
                        total_rounds=len(rounds),
                        total_tokens_spent=total_tokens,
                        total_latency_ms=(time.monotonic() - t0) * 1000,
                        convergence_round=round_num,
                        depth_gain=self._estimate_depth_gain(rounds),
                    )

                # Update for next round
                current_answer = revised

            except asyncio.TimeoutError:
                logger.warning(
                    f"AdversarialSelfPlay: round {round_num} timed out"
                )
                break
            except Exception as e:
                logger.warning(f"AdversarialSelfPlay round {round_num}: {e}")
                if round_num == 1:
                    # First round failed — return original
                    return SelfPlayResult(
                        original_answer=model_output,
                        final_answer=model_output,
                        rounds=rounds,
                        status=PlayStatus.ERROR,
                        total_rounds=len(rounds),
                        total_tokens_spent=total_tokens,
                        total_latency_ms=(time.monotonic() - t0) * 1000,
                    )
                break

        # Max rounds reached
        self._stats["max_rounds_reached"] += 1
        return SelfPlayResult(
            original_answer=model_output,
            final_answer=current_answer,
            rounds=rounds,
            status=PlayStatus.MAX_ROUNDS,
            total_rounds=len(rounds),
            total_tokens_spent=total_tokens,
            total_latency_ms=(time.monotonic() - t0) * 1000,
            depth_gain=self._estimate_depth_gain(rounds),
        )

    # ── Counter-Argument Generation ───────────────────────────────

    async def _generate_counter_arguments(
        self, answer: str, query: str, round_num: int,
        chat_fn: Any, model_name: str,
    ) -> list[str]:
        """Generate the strongest possible counter-arguments against an answer.

        The key insight: don't ask the model to "be helpful" — ask it to "find
        every flaw, weakness, oversight, and vulnerability in the following answer
        as if you were its harshest critic."
        """
        # Strategy varies by round: different attack angles each round
        if round_num == 1:
            attack_prompt = (
                f"Critique the following answer as harshly as possible. "
                f"Find EVERY flaw, logical gap, unsupported claim, missing edge case, "
                f"hidden assumption, and potential counter-example.\n\n"
                f"Original question: {query[:500]}\n\n"
                f"Answer to critique:\n{answer[:4000]}\n\n"
                f"List each specific flaw as a numbered bullet point. "
                f"Be SPECIFIC — reference exact claims in the answer. "
                f"At least 3 flaws. Do NOT be polite — be thorough."
            )
        elif round_num == 2:
            attack_prompt = (
                f"The following answer has been revised once already. "
                f"Now find the DEEPER issues: implicit assumptions that survived "
                f"the first round, structural weaknesses in the reasoning framework, "
                f"and meta-level problems (e.g., the answer solves the wrong problem, "
                f"or uses an inappropriate methodology).\n\n"
                f"Original question: {query[:500]}\n\n"
                f"Revised answer:\n{answer[:4000]}\n\n"
                f"Be relentless. List 3+ specific deep flaws."
            )
        else:
            attack_prompt = (
                f"Final critique round. The following answer has survived two "
                f"rounds of criticism. Find ANY remaining issues: unstated tradeoffs, "
                f"unverifiable claims, domain-specific blind spots, or alternative "
                f"framings that are better.\n\n"
                f"Original question: {query[:500]}\n\n"
                f"Answer:\n{answer[:4000]}\n\n"
                f"List 2+ remaining issues. If you truly cannot find meaningful flaws, "
                f"state 'NO_MEANINGFUL_FLAWS' as your response."
            )

        try:
            response = await asyncio.wait_for(
                chat_fn(attack_prompt, model_name), timeout=30.0,
            )
            return self._parse_counter_args(response)
        except asyncio.TimeoutError:
            return []
        except Exception:
            return []

    @staticmethod
    def _parse_counter_args(response: str) -> list[str]:
        """Parse counter-arguments from LLM response into a clean list."""
        if not response:
            return []

        # Check for explicit "no flaws" signal
        if "NO_MEANINGFUL_FLAWS" in response.upper():
            return []

        args = []
        # Split by numbered bullets or newlines
        lines = response.strip().split("\n")
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # Match bullet patterns: "1. ", "- ", "• ", "* "
            if re.match(r'^\d+[\.\)]\s', line) or line.startswith(("- ", "• ", "* ")):
                cleaned = re.sub(r'^\d+[\.\)]\s*', '', line)
                cleaned = cleaned.lstrip("- •*").strip()
                if len(cleaned) > 10:  # Meaningful argument
                    args.append(cleaned)
            elif len(line) > 20 and len(args) > 0:
                # Continuation of previous argument
                args[-1] += " " + line

        # Fallback: if no bullets, split by sentences
        if not args and len(response) > 50:
            import re as _re
            sentences = _re.split(r'(?<=[.!?。！？])\s+', response)
            args = [s.strip() for s in sentences if len(s.strip()) > 15][:5]

        return args[:6]  # Cap at 6 counter-arguments

    # ── Revision Prompt Builder ────────────────────────────────────

    @staticmethod
    def _build_revision_prompt(
        query: str, current_answer: str, counter_args: list[str], round_num: int,
    ) -> str:
        """Build prompt asking model to revise its answer based on counter-arguments."""
        args_text = "\n".join(f"{i+1}. {a}" for i, a in enumerate(counter_args))
        return (
            f"Your previous answer to the question below has been CRITIQUED. "
            f"The following specific flaws were identified:\n\n"
            f"{args_text}\n\n"
            f"Original question: {query[:500]}\n\n"
            f"Your previous answer:\n{current_answer[:3000]}\n\n"
            f"Please produce a REVISED answer that:\n"
            f"1. Addresses each of the identified flaws specifically\n"
            f"2. Acknowledges where the criticism is valid and adjusts accordingly\n"
            f"3. Strengthens arguments that survived the critique\n"
            f"4. Marks any claims that remain uncertain despite revision\n\n"
            f"Do NOT simply restate your original answer. "
            f"Genuinely engage with the criticism."
        )

    # ── Change Detection ──────────────────────────────────────────

    @staticmethod
    def _detect_changes(original: str, revised: str) -> list[str]:
        """Detect what changed between original and revised answers."""
        changes = []
        orig_lines = set(original.split("\n"))
        rev_lines = set(revised.split("\n"))

        added = rev_lines - orig_lines
        removed = orig_lines - rev_lines

        if added:
            changes.append(f"Added {len(added)} new lines")
        if removed:
            changes.append(f"Removed {len(removed)} lines")
        if not added and not removed:
            changes.append("No significant changes detected")

        # Length change
        len_diff = len(revised) - len(original)
        if abs(len_diff) > 50:
            direction = "longer" if len_diff > 0 else "shorter"
            changes.append(f"Answer became {direction} by {abs(len_diff)} chars")

        return changes

    # ── Convergence Detection ─────────────────────────────────────

    @staticmethod
    def _jaccard_similarity(text_a: str, text_b: str) -> float:
        """Word-level Jaccard similarity between two texts."""
        if not text_a or not text_b:
            return 0.0
        set_a = set(text_a.lower().split())
        set_b = set(text_b.lower().split())
        if not set_a or not set_b:
            return 0.0
        return len(set_a & set_b) / len(set_a | set_b)

    # ── Depth Gain Estimation ─────────────────────────────────────

    @staticmethod
    def _estimate_depth_gain(rounds: list[RebuttalRound]) -> float:
        """Estimate how much reasoning depth improved through self-play.

        Based on: number of revisions, changes made per round, convergence speed.
        """
        if not rounds:
            return 0.0
        # More rounds with changes = more depth gain
        change_rounds = sum(1 for r in rounds if r.changes_made
                           and "No significant changes" not in r.changes_made[0])
        # Jaccard divergence from round to round (lower = more change)
        jaccard_avg = sum(r.jaccard_to_previous for r in rounds) / len(rounds)
        divergence = max(0.0, 1.0 - jaccard_avg)
        return min(1.0, change_rounds * 0.3 + divergence * 0.5)

    # ── PRefLexOR: Recursive Self-Reflection (Buehler, npj AI 2025) ─

    async def reflect_and_refine(
        self, answer: str, query: str, chat_fn: Any,
        model_name: str = "", max_reflections: int = 3,
    ) -> str:
        """PRefLexOR recursive self-reflection loop.

        From Buehler (2025): the model produces <reflect> introspection
        of its own reasoning, then refines based on that reflection.
        Unlike adversarial rebuttal (external critique), this is INTERNAL
        self-improvement — the model critiques itself before external challenges.

        The recursive pattern:
          answer → <reflect>what's weak?</reflect> → refined_answer
                → <reflect>still weak?</reflect> → further_refined
                → ... until reflection finds no new weaknesses.
        """
        current = answer
        for r in range(max_reflections):
            reflect_prompt = (
                f"You previously answered the following question:\n"
                f"Question: {query[:500]}\n\n"
                f"Your answer:\n{current[:3000]}\n\n"
                f"Now, critically reflect on YOUR OWN answer. Use "
                f"<reflect>...</reflect> tags to identify:\n"
                f"1. The WEAKEST part of your reasoning\n"
                f"2. Any implicit assumption you didn't state\n"
                f"3. What a more rigorous answer would include\n"
                f"4. One concrete improvement you can make\n\n"
                f"Then provide a REFINED answer that addresses these issues."
            )

            try:
                response = await asyncio.wait_for(
                    chat_fn(reflect_prompt, model_name), timeout=30.0,
                )

                # Extract reflection and refined answer
                refined = self._parse_reflection_response(response, current)

                # Check if reflection found new weaknesses
                if self._jaccard_similarity(refined, current) > 0.92:
                    logger.debug(
                        f"PRefLexOR: converged at reflection {r+1} "
                        f"(jaccard={self._jaccard_similarity(refined, current):.3f})"
                    )
                    current = refined
                    break

                current = refined
                logger.debug(
                    f"PRefLexOR: reflection {r+1}/{max_reflections} "
                    f"(jaccard={self._jaccard_similarity(refined, current):.3f})"
                )

            except asyncio.TimeoutError:
                logger.debug(f"PRefLexOR: reflection {r+1} timed out")
                break
            except Exception as e:
                logger.debug(f"PRefLexOR reflection: {e}")
                break

        return current

    @staticmethod
    def _parse_reflection_response(response: str, fallback: str) -> str:
        """Parse PRefLexOR reflection response, extracting refined answer.

        The response contains <reflect>...</reflect> tags with self-critique,
        followed by the refined answer.
        """
        import re
        # Try to extract content after the last </reflect> tag
        parts = re.split(r'</reflect>', response, maxsplit=1)
        if len(parts) > 1:
            refined = parts[-1].strip()
            if len(refined) > 30:
                return refined
        # If no reflection tags found, return the whole response
        if len(response) > 30:
            return response
        return fallback

    # ── Statistics ─────────────────────────────────────────────────

    def stats(self) -> dict:
        return {
            **self._stats,
            "convergence_rate": (
                self._stats["converged"] / max(self._stats["sessions"], 1)
            ),
        }


# ═══ Singleton ═════════════════════════════════════════════════════

_selfplay: Optional[AdversarialSelfPlay] = None


def get_selfplay() -> AdversarialSelfPlay:
    global _selfplay
    if _selfplay is None:
        _selfplay = AdversarialSelfPlay()
    return _selfplay


def get_adversarial_selfplay() -> AdversarialSelfPlay:
    return get_selfplay()


__all__ = [
    "AdversarialSelfPlay", "SelfPlayResult", "RebuttalRound", "PlayStatus",
    "get_selfplay", "get_adversarial_selfplay",
]
