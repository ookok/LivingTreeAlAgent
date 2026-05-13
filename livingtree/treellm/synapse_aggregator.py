"""SynapseAggregator — Multi-model reasoning fusion engine.

Core value: "Stand on the shoulders of all giants" — instead of picking the
single best model, run top-K models in parallel and synthesize their insights.

Three aggregation strategies (auto-selected by consensus level):
  1. consensus (>0.8 agreement): weighted merge — all models agree, blend outputs
  2. debate (0.4–0.8 agreement): LLM judge resolves conflicts, models rebut each other
  3. stitch (<0.4 agreement): extract strongest non-contradictory segments from each

Key capabilities:
  - Cross-validation: detect factual agreements and contradictions across models
  - Consensus detection: semantic + structural similarity scoring
  - Conflict resolution: LLM judge arbitrates disagreements
  - Fragment stitching: extract best parts from each model output
  - Contribution attribution: track which model contributed what insight

Integration:
  - TreeLLM.route_layered() calls aggregate() after getting top-K model outputs
  - CompetitiveEliminator uses contribution scores for Elo updates
  - StrategicOrchestrator uses this for multi-perspective task analysis

Usage:
    aggregator = get_synapse_aggregator()
    result = await aggregator.aggregate(
        outputs=[{provider: "deepseek", text: "...", ...}, ...],
        query="Explain quantum computing",
        task_type="reasoning",
    )
"""

from __future__ import annotations

import asyncio
import math
import re
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger


# ═══ Data Types ════════════════════════════════════════════════════


@dataclass
class ModelOutput:
    """Output from a single model in the aggregation set."""
    provider: str
    text: str
    tokens: int = 0
    latency_ms: float = 0.0
    cost_yuan: float = 0.0
    self_assessment: float = 0.5    # Self-evaluated confidence
    election_score: float = 0.5     # From HolisticElection


@dataclass
class CrossValidation:
    """Pairwise semantic comparison between two model outputs."""
    model_a: str
    model_b: str
    semantic_similarity: float       # Jaccard word-level overlap
    structural_similarity: float     # Sentence count & structure match
    factual_agreement: bool          # LLM judge verdict
    contradiction_points: list[str] = field(default_factory=list)
    shared_insights: list[str] = field(default_factory=list)
    judge_confidence: float = 0.5


@dataclass
class SynapseResult:
    """Final synthesized output from multi-model aggregation."""
    aggregated_text: str
    contributions: dict[str, float]    # provider → contribution weight (0-1)
    consensus_level: float             # 0-1 across all model pairs
    method: str                        # "consensus", "debate", "stitch"
    model_outputs: list[ModelOutput]
    cross_validations: list[CrossValidation]
    conflict_resolutions: list[str]
    grounded_in: list[str]             # Which models were primary sources
    total_tokens_spent: int
    total_cost_yuan: float
    timestamp: float = field(default_factory=time.time)


# ═══ SynapseAggregator ═════════════════════════════════════════════


class SynapseAggregator:
    """Multi-model reasoning synthesis engine.

    Design principle (Stand on Shoulders):
      Each model brings a unique perspective. The aggregator identifies areas
      of agreement (high-signal consensus), resolves disagreements (via debate
      or LLM judge), and stitches the strongest insights from each model into
      a single coherent output.

    Three strategies:
      1. Consensus: all models agree → weighted merge of outputs
      2. Debate: partial agreement → models rebut each other, judge decides
      3. Stitch: low agreement → extract non-contradictory fragments
    """

    CONSENSUS_HIGH = 0.80     # Above this → consensus mode
    CONSENSUS_LOW = 0.40      # Below this → stitch mode
    MAX_MODELS_TO_DEBATE = 3  # Debate mode: max models to involve
    JUDGE_TEMPERATURE = 0.1   # Judge should be precise

    def __init__(self, judge_fn: Any = None):
        """Initialize with optional custom LLM judge function.

        judge_fn: async callable(judge_prompt: str) -> str
        If None, uses heuristic consensus/stitch only (no debate mode).
        """
        self._judge_fn = judge_fn
        self._stats: dict[str, dict[str, float]] = {}  # provider → agg stats

    # ── Main Aggregation Pipeline ──────────────────────────────────

    async def aggregate(
        self,
        outputs: list[ModelOutput],
        query: str = "",
        task_type: str = "general",
        enable_debate: bool = True,
        max_debate_rounds: int = 2,
    ) -> SynapseResult:
        """Aggregate multiple model outputs into a single synthesized result.

        Pipeline:
          1. Cross-validate all model pairs
          2. Compute consensus level from pairwise similarities
          3. Select strategy based on consensus level
          4. Execute strategy (consensus / debate / stitch)
          5. Compute contributions and return result

        Args:
            outputs: List of model outputs (2+ models required).
            query: Original user query (for context in debate mode).
            task_type: Task category for strategy weighting.
            enable_debate: If True, use LLM judge for debate resolution.
            max_debate_rounds: Max rounds of rebuttal in debate mode.

        Returns:
            SynapseResult with aggregated text and metadata.
        """
        if len(outputs) < 2:
            # Single model — no aggregation needed, return as-is
            return SynapseResult(
                aggregated_text=outputs[0].text if outputs else "",
                contributions={outputs[0].provider: 1.0} if outputs else {},
                consensus_level=1.0,
                method="single_model",
                model_outputs=outputs,
                cross_validations=[],
                conflict_resolutions=[],
                grounded_in=[outputs[0].provider] if outputs else [],
                total_tokens_spent=sum(o.tokens for o in outputs),
                total_cost_yuan=sum(o.cost_yuan for o in outputs),
            )

        # Step 1: Cross-validate all pairs
        cross_validations = self._cross_validate_all(outputs, query, task_type)
        if enable_debate and self._judge_fn:
            cross_validations = await self._judge_validations(cross_validations, outputs, query)

        # Step 2: Compute consensus level
        consensus_level = self._compute_consensus(cross_validations)

        # Step 3: Select and execute strategy
        if consensus_level >= self.CONSENSUS_HIGH:
            method = "consensus"
            text, resolutions = self._consensus_merge(outputs, cross_validations, query)
        elif consensus_level >= self.CONSENSUS_LOW:
            method = "debate"
            text, resolutions = await self._debate_resolve(
                outputs, cross_validations, query, max_debate_rounds,
            )
        else:
            method = "stitch"
            text, resolutions = self._stitch_fragments(outputs, cross_validations, query)

        # Step 4: Compute contribution weights
        contributions = self._compute_contributions(outputs, cross_validations, consensus_level)

        # Step 5: Identify grounded sources
        grounded_in = self._identify_grounded_sources(contributions)

        logger.info(
            f"SynapseAggregator: {len(outputs)} models aggregated "
            f"via '{method}' (consensus={consensus_level:.2f})"
        )

        return SynapseResult(
            aggregated_text=text,
            contributions=contributions,
            consensus_level=consensus_level,
            method=method,
            model_outputs=outputs,
            cross_validations=cross_validations,
            conflict_resolutions=resolutions,
            grounded_in=grounded_in,
            total_tokens_spent=sum(o.tokens for o in outputs),
            total_cost_yuan=sum(o.cost_yuan for o in outputs),
        )

    # ── Step 1: Cross-Validation ───────────────────────────────────

    def _cross_validate_all(
        self, outputs: list[ModelOutput], query: str, task_type: str,
    ) -> list[CrossValidation]:
        """Compute pairwise semantic and structural similarity for all model pairs."""
        validations: list[CrossValidation] = []
        for i in range(len(outputs)):
            for j in range(i + 1, len(outputs)):
                a, b = outputs[i], outputs[j]
                sem_sim = self._jaccard_similarity(a.text, b.text)
                struct_sim = self._structural_similarity(a.text, b.text)
                validations.append(CrossValidation(
                    model_a=a.provider,
                    model_b=b.provider,
                    semantic_similarity=sem_sim,
                    structural_similarity=struct_sim,
                    factual_agreement=sem_sim > 0.5,  # Placeholder before judge
                ))
        return validations

    async def _judge_validations(
        self,
        validations: list[CrossValidation],
        outputs: list[ModelOutput],
        query: str,
    ) -> list[CrossValidation]:
        """Use LLM judge to assess factual agreement and detect contradictions.

        Only runs judge for pairs near the boundary (0.3-0.7 similarity)
        where the answer isn't obvious from similarity alone.
        """
        output_map = {o.provider: o for o in outputs}
        judge_tasks: list[tuple[int, CrossValidation]] = []

        for idx, cv in enumerate(validations):
            # Only judge borderline pairs — extreme similarity is self-evident
            if 0.30 <= cv.semantic_similarity <= 0.75:
                judge_tasks.append((idx, cv))

        if not judge_tasks or not self._judge_fn:
            # Heuristic fallback: assume agreement if semantic sim > 0.5
            for cv in validations:
                cv.factual_agreement = cv.semantic_similarity >= 0.5
            return validations

        # Run judges in parallel
        async def judge_one(cv: CrossValidation) -> CrossValidation:
            txt_a = output_map.get(cv.model_a, ModelOutput(provider="", text="")).text
            txt_b = output_map.get(cv.model_b, ModelOutput(provider="", text="")).text
            prompt = self._build_judge_prompt(query, cv.model_a, txt_a, cv.model_b, txt_b)
            try:
                verdict = await asyncio.wait_for(
                    self._judge_fn(prompt), timeout=30.0,
                )
                cv.factual_agreement, cv.contradiction_points, cv.shared_insights, cv.judge_confidence = (
                    self._parse_judge_verdict(verdict)
                )
            except Exception as e:
                logger.debug(f"SynapseAggregator judge error: {e}")
                cv.factual_agreement = cv.semantic_similarity >= 0.5
            return cv

        judge_results = await asyncio.gather(
            *(judge_one(cv) for _, cv in judge_tasks), return_exceptions=True,
        )
        for (idx, _), result in zip(judge_tasks, judge_results):
            if isinstance(result, CrossValidation):
                validations[idx] = result
            elif isinstance(result, Exception):
                pass  # Keep heuristic default

        return validations

    # ── Step 2: Consensus Computation ──────────────────────────────

    @staticmethod
    def _compute_consensus(validations: list[CrossValidation]) -> float:
        """Compute overall consensus level (0-1) from pairwise validations."""
        if not validations:
            return 0.0
        # Weighted: 60% semantic + 25% structural + 15% factual agreement
        scores = []
        for cv in validations:
            s = (
                cv.semantic_similarity * 0.60
                + cv.structural_similarity * 0.25
                + (1.0 if cv.factual_agreement else 0.0) * 0.15
            )
            scores.append(s)
        return round(sum(scores) / len(scores), 4)

    # ── Strategy 1: Consensus Merge ────────────────────────────────

    def _consensus_merge(
        self,
        outputs: list[ModelOutput],
        validations: list[CrossValidation],
        query: str,
    ) -> tuple[str, list[str]]:
        """All models agree → weighted merge. The model with highest quality
        score anchors the output, other models' complementary details are added.
        """
        best = max(outputs, key=lambda o: o.election_score)
        resolutions = [f"High consensus ({len(validations)} pairs agree) — "
                       f"anchored on {best.provider}"]

        # Start with the best model's output
        text = best.text

        # Add unique insights from other models (sentences not found in best output)
        best_sentences = self._extract_sentences(best.text)
        for o in outputs:
            if o.provider == best.provider:
                continue
            other_sentences = self._extract_sentences(o.text)
            unique = [s for s in other_sentences
                      if not any(self._sentence_overlap(s, bs) > 0.7 for bs in best_sentences)]
            if unique:
                supplement = f"\n\n[补充 — {o.provider}]: " + " ".join(unique)
                if len(text + supplement) < 8000:
                    text += supplement
                    resolutions.append(f"Added {len(unique)} unique insights from {o.provider}")

        return text, resolutions

    # ── Strategy 2: Debate Resolution ──────────────────────────────

    async def _debate_resolve(
        self,
        outputs: list[ModelOutput],
        validations: list[CrossValidation],
        query: str,
        max_rounds: int,
    ) -> tuple[str, list[str]]:
        """Partial agreement → models debate each other, LLM judge resolves.

        Multi-round: identify disagreement points, let models rebut, judge arbitrates.
        """
        resolutions: list[str] = []

        # Sort outputs by election score, take top N for debate
        debaters = sorted(outputs, key=lambda o: -o.election_score)[:self.MAX_MODELS_TO_DEBATE]

        if not self._judge_fn:
            # No judge available → fallback to weighted best
            return self._consensus_merge(outputs, validations, query)

        # Round 1: Identify disagreement points
        disagreements = self._find_disagreements(debaters, validations)
        if not disagreements:
            return self._consensus_merge(outputs, validations, query)

        resolutions.append(f"Debate mode: {len(disagreements)} disagreement points, "
                          f"{len(debaters)} models debating")

        # Build debate prompt
        debate_prompt = self._build_debate_prompt(query, debaters, disagreements)

        # Round 1+N: Get judge verdict and potentially run rebuttal
        try:
            verdict = await asyncio.wait_for(
                self._judge_fn(debate_prompt), timeout=60.0,
            )
            resolutions.append(f"Judge verdict received ({len(verdict)} chars)")

            for round_num in range(max_rounds):
                rebuttals = await self._run_rebuttal_round(
                    debaters, verdict, disagreements, query, round_num,
                )
                if not rebuttals:
                    break
                # Update: incorporate rebuttals into final synthesis
                resolutions.extend(rebuttals)
        except asyncio.TimeoutError:
            resolutions.append("Debate timed out — falling back to consensus merge")
            return self._consensus_merge(outputs, validations, query)
        except Exception as e:
            logger.debug(f"SynapseAggregator debate error: {e}")
            return self._consensus_merge(outputs, validations, query)

        return verdict, resolutions

    async def _run_rebuttal_round(
        self,
        debaters: list[ModelOutput],
        verdict: str,
        disagreements: list[str],
        query: str,
        round_num: int,
    ) -> list[str]:
        """Let debaters rebut the judge's current verdict."""
        rebuttals: list[str] = []
        rebuttal_prompt = (
            f"Previous judge verdict:\n{verdict[:3000]}\n\n"
            f"Disagreement points:\n" + "\n".join(f"- {d}" for d in disagreements[:3]) +
            f"\n\nYou are a synthesizer. Based on the judge's analysis above, "
            f"produce a refined final answer to the query: '{query[:200]}'.\n"
            f"Resolve any remaining conflicts and produce a single definitive answer."
        )
        try:
            refined = await asyncio.wait_for(
                self._judge_fn(rebuttal_prompt), timeout=30.0,
            )
            if refined and len(refined) > 50:
                rebuttals.append(f"Round {round_num + 1} refinement: {len(refined)} chars")
                # Replace verdict with refined version
                return [refined]  # Signal to update main verdict
        except Exception as e:
            logger.debug(f"SynapseAggregator rebuttal error: {e}")
        return []

    # ── Strategy 3: Fragment Stitching ─────────────────────────────

    def _stitch_fragments(
        self,
        outputs: list[ModelOutput],
        validations: list[CrossValidation],
        query: str,
    ) -> tuple[str, list[str]]:
        """Low agreement → extract strongest non-contradictory fragments.

        For each model, identify its most confident statements (by self-assessment
        or keyword confidence markers). Stitch together non-contradictory fragments
        and flag contradictions explicitly.
        """
        resolutions: list[str] = [
            f"Stitch mode: low consensus across {len(outputs)} models"
        ]

        # Extract high-confidence segments from each model
        fragments: list[tuple[str, str, float]] = []  # (provider, text, confidence)
        for o in outputs:
            segments = self._extract_confident_segments(o.text)
            for seg in segments:
                fragments.append((o.provider, seg, o.election_score))

        # Sort by confidence, then deduplicate
        fragments.sort(key=lambda x: -x[2])
        seen: set[str] = set()
        selected: list[str] = []
        for provider, fragment, conf in fragments:
            frag_hash = self._fragment_hash(fragment)
            if frag_hash not in seen:
                seen.add(frag_hash)
                if len(selected) == 0 or not self._contradicts_any(fragment, selected):
                    selected.append(f"[{provider}]: {fragment}")

        # Flag contradictions
        contradictions = self._detect_contradictions(outputs)
        if contradictions:
            resolutions.append(f"Flagged {len(contradictions)} contradictions — "
                              f"models disagree on: {', '.join(contradictions[:3])}")
            selected.append("\n\n⚠️ 矛盾点 (Models Disagree):\n" +
                           "\n".join(f"- {c}" for c in contradictions))

        text = "\n\n".join(selected)
        return text, resolutions

    # ── Step 4: Contribution Attribution ───────────────────────────

    @staticmethod
    def _compute_contributions(
        outputs: list[ModelOutput],
        validations: list[CrossValidation],
        consensus: float,
    ) -> dict[str, float]:
        """Compute per-model contribution weight based on quality, uniqueness,
        and how well it agreed with consensus.
        """
        contribs: dict[str, float] = {}
        for o in outputs:
            base = o.election_score * 0.4 + o.self_assessment * 0.2

            # Agreement bonus: models that agree with the consensus contribute more
            agree_count = 0
            for cv in validations:
                if cv.model_a == o.provider and cv.factual_agreement:
                    agree_count += 1
                elif cv.model_b == o.provider and cv.factual_agreement:
                    agree_count += 1
            agree_bonus = (agree_count / max(len(validations), 1)) * 0.2

            # Uniqueness bonus: longer, more detailed output contributes more
            length_score = min(1.0, len(o.text) / 2000) * 0.2

            contribs[o.provider] = round(base + agree_bonus + length_score, 4)

        # Normalize to sum ~1.0
        total = sum(contribs.values()) or 1.0
        return {k: round(v / total, 4) for k, v in contribs.items()}

    # ── Step 5: Grounded Sources ────────────────────────────────────

    @staticmethod
    def _identify_grounded_sources(contributions: dict[str, float]) -> list[str]:
        """Identify which models were primary grounded sources (>15% contribution)."""
        return [k for k, v in sorted(contributions.items(), key=lambda x: -x[1])
                if v >= 0.15]

    # ── Helpers: Text Analysis ─────────────────────────────────────

    @staticmethod
    def _jaccard_similarity(text_a: str, text_b: str) -> float:
        """Word-level Jaccard similarity."""
        if not text_a or not text_b:
            return 0.0
        set_a = set(text_a.lower().split())
        set_b = set(text_b.lower().split())
        if not set_a or not set_b:
            return 0.0
        return len(set_a & set_b) / len(set_a | set_b)

    @staticmethod
    def _structural_similarity(text_a: str, text_b: str) -> float:
        """Compare text structure: sentence count ratio and avg sentence length ratio."""
        if not text_a or not text_b:
            return 0.0
        sent_a = len(re.split(r'[.!?。！？\n]+', text_a))
        sent_b = len(re.split(r'[.!?。！？\n]+', text_b))
        count_ratio = min(sent_a, sent_b) / max(sent_a, sent_b, 1)

        avg_len_a = len(text_a) / max(sent_a, 1)
        avg_len_b = len(text_b) / max(sent_b, 1)
        len_ratio = min(avg_len_a, avg_len_b) / max(avg_len_a, avg_len_b, 1)

        return round((count_ratio + len_ratio) / 2, 4)

    @staticmethod
    def _extract_sentences(text: str) -> list[str]:
        """Split text into sentences."""
        return [s.strip() for s in re.split(r'[.!?。！？\n]+', text) if len(s.strip()) > 10]

    @staticmethod
    def _sentence_overlap(s1: str, s2: str) -> float:
        """Word-level sentence overlap for deduplication."""
        w1 = set(s1.lower().split())
        w2 = set(s2.lower().split())
        if not w1 or not w2:
            return 0.0
        return len(w1 & w2) / max(len(w1), len(w2))

    @staticmethod
    def _extract_confident_segments(text: str) -> list[str]:
        """Extract sentences with high-confidence markers."""
        sentences = re.split(r'(?<=[.!?。！？])\s+', text)
        confident = []
        markers = ["definitely", "clearly", "certainly", "关键是", "显然",
                    "important", "critical", "essential", "综上所述",
                    "therefore", "thus", "hence", "因此", "所以"]
        for s in sentences:
            s_lower = s.lower()
            if any(m in s_lower for m in markers):
                confident.append(s.strip())
        # If no confident markers found, take longest sentences as best
        if not confident and sentences:
            confident = [max(sentences, key=len).strip()]
        return confident

    @staticmethod
    def _fragment_hash(text: str) -> str:
        """Simple hash for fragment deduplication."""
        import hashlib
        return hashlib.md5(text[:200].encode()).hexdigest()

    def _contradicts_any(self, fragment: str, existing: list[str]) -> bool:
        """Check if a fragment contradicts any existing selected fragments."""
        f_words = set(fragment.lower().split())
        for ex in existing:
            ex_words = set(ex.lower().split())
            overlap = len(f_words & ex_words) / max(len(f_words), 1)
            # High overlap but with negation → contradiction
            if overlap > 0.6:
                negations = ["not", "no", "never", "don't", "doesn't", "isn't", "aren't",
                            "不", "没有", "不是", "无"]
                f_has_neg = any(n in fragment.lower().split() for n in negations)
                e_has_neg = any(n in ex.lower().split() for n in negations)
                if f_has_neg != e_has_neg:  # One negates, one doesn't → contradiction
                    return True
        return False

    @staticmethod
    def _detect_contradictions(outputs: list[ModelOutput]) -> list[str]:
        """Detect explicit contradictions between model outputs."""
        contradictions = []
        for i in range(len(outputs)):
            for j in range(i + 1, len(outputs)):
                a_words = set(outputs[i].text.lower().split())
                b_words = set(outputs[j].text.lower().split())
                overlap = len(a_words & b_words) / max(len(a_words | b_words), 1)
                if overlap > 0.5:
                    # Check for negation asymmetry
                    negs = {"not", "no", "never", "不", "没有", "不是"}
                    a_has = any(n in a_words for n in negs)
                    b_has = any(n in b_words for n in negs)
                    if a_has != b_has:
                        contradictions.append(
                            f"{outputs[i].provider} vs {outputs[j].provider}"
                        )
        return contradictions[:5]  # Cap at 5

    def _find_disagreements(
        self, debaters: list[ModelOutput], validations: list[CrossValidation],
    ) -> list[str]:
        """Identify specific disagreement points from cross validations."""
        disagreements = []
        for cv in validations:
            if not cv.factual_agreement and cv.semantic_similarity < 0.4:
                disagreements.append(
                    f"{cv.model_a} ↔ {cv.model_b}: "
                    f"semantic_sim={cv.semantic_similarity:.2f}"
                )
        return disagreements[:5]

    # ── Judge Prompt Builders ──────────────────────────────────────

    @staticmethod
    def _build_judge_prompt(
        query: str, model_a: str, text_a: str, model_b: str, text_b: str,
    ) -> str:
        """Build a concise judge prompt for pairwise comparison."""
        return (
            f"Compare two AI model responses to the same query. "
            f"Determine if they FACTUALLY AGREE, and identify any contradictions.\n\n"
            f"Query: {query[:500]}\n\n"
            f"Response from {model_a}:\n{text_a[:2000]}\n\n"
            f"Response from {model_b}:\n{text_b[:2000]}\n\n"
            f"Reply in JSON:\n"
            f'{{"factually_agree": true/false, '
            f'"contradictions": ["point1", ...], '
            f'"shared_insights": ["insight1", ...], '
            f'"confidence": 0.0-1.0}}'
        )

    @staticmethod
    def _build_debate_prompt(
        query: str, debaters: list[ModelOutput], disagreements: list[str],
    ) -> str:
        """Build debate resolution prompt for the LLM judge."""
        model_texts = "\n\n".join(
            f"## {d.provider} (election_score={d.election_score:.2f}):\n{d.text[:2500]}"
            for d in debaters
        )
        return (
            f"You are a debate arbiter. Multiple AI models analyzed the same query "
            f"and produced different answers. Your job is to synthesize a single "
            f"definitive answer, resolving all disagreements.\n\n"
            f"Query: {query[:500]}\n\n"
            f"Model outputs:\n{model_texts}\n\n"
            f"Key disagreements:\n" +
            "\n".join(f"- {d}" for d in disagreements[:5]) +
            f"\n\nProduce a SINGLE definitive answer that:\n"
            f"1. States the agreed-upon facts clearly\n"
            f"2. For each disagreement, explains which side is correct and why\n"
            f"3. Provides a final synthesized conclusion"
        )

    @staticmethod
    def _parse_judge_verdict(
        verdict_text: str,
    ) -> tuple[bool, list[str], list[str], float]:
        """Parse JSON from judge verdict. Returns (agrees, contradictions, insights, confidence)."""
        import json as _json
        try:
            # Find JSON block in text
            start = verdict_text.find("{")
            end = verdict_text.rfind("}") + 1
            if start >= 0 and end > start:
                data = _json.loads(verdict_text[start:end])
                return (
                    data.get("factually_agree", True),
                    data.get("contradictions", []),
                    data.get("shared_insights", []),
                    float(data.get("confidence", 0.5)),
                )
        except Exception:
            pass
        # Heuristic fallback: check keywords
        agrees = "factually_agree" not in verdict_text.lower() or \
                 "true" in verdict_text.lower()
        return agrees, [], [], 0.5

    # ── DR-CoT Voting: Multi-Chain Consensus (DR-CoT, Sci Reports 2025) ─

    @staticmethod
    def voting_aggregate(outputs: list[ModelOutput], query: str = "",
                         vote_threshold: float = 0.5) -> str:
        """DR-CoT voting mechanism: aggregate via independent reasoning chains.

        From DR-CoT (2025): "aggregating outputs from multiple independent
        reasoning chains via a voting mechanism mitigates errors from any
        single chain and converges on a consensus final answer."

        Each model output is treated as an independent reasoning chain.
        The answer that receives majority support (by semantic similarity
        voting) wins. When no clear majority, fall back to highest-quality.

        This is fundamentally different from `aggregate()` which fuses outputs
        — voting preserves the independence of each chain and selects the
        most widely-supported answer.

        Args:
            outputs: List of model outputs (independent reasoning chains).
            query: Original query (for context logging).
            vote_threshold: Minimum fraction of votes to win (default 0.5).

        Returns:
            The winning answer text.
        """
        if not outputs:
            return ""
        if len(outputs) == 1:
            return outputs[0].text

        # Step 1: Extract core answer from each chain
        answers: list[tuple[str, str, float]] = []  # (provider, core_answer, quality)
        for o in outputs:
            core = SynapseAggregator._extract_core_answer(o.text)
            answers.append((o.provider, core, o.election_score))

        # Step 2: Build pairwise vote matrix (semantic agreement)
        n = len(answers)
        votes = [[0.0] * n for _ in range(n)]  # votes[i][j] = chain i votes for chain j

        for i in range(n):
            for j in range(n):
                if i == j:
                    votes[i][j] = 1.0
                else:
                    sim = SynapseAggregator._jaccard_similarity(
                        answers[i][1], answers[j][1]
                    )
                    votes[i][j] = sim

        # Step 3: Count votes per chain
        vote_counts = [sum(votes[i]) for i in range(n)]
        total_votes = sum(vote_counts)

        # Step 4: Determine winner
        best_idx = 0
        best_votes = 0
        for i in range(n):
            vote_share = vote_counts[i] / max(total_votes, 1)
            # Weight by quality
            weighted = vote_share * 0.7 + answers[i][2] * 0.3
            if weighted > best_votes:
                best_votes = weighted
                best_idx = i

        winner = answers[best_idx]
        logger.info(
            f"Synapse DR-CoT vote: {n} chains, winner={winner[0]} "
            f"(vote_share={vote_counts[best_idx]/max(total_votes,1):.2f}, "
            f"quality={winner[2]:.2f})"
        )

        return outputs[best_idx].text

    @staticmethod
    def _extract_core_answer(text: str) -> str:
        """Extract the core answer from a full reasoning output.

        Heuristic: take the last substantial paragraph as the answer,
        since reasoning chains typically end with a conclusion.
        """
        paragraphs = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 30]
        if not paragraphs:
            return text[:500]
        # Take last 2 paragraphs as the core conclusion
        return " ".join(paragraphs[-2:])[:1000]

    # ── Auto-connect to TreeLLM as judge ──────────────────────────

    def _auto_connect_judge(self) -> bool:
        """Auto-connect the LLM judge function to TreeLLM.

        This enables debate mode and judge_validations without manual setup.
        The judge uses a flash model for fast pairwise evaluations.
        """
        try:
            from .core import TreeLLM
            llm = TreeLLM()

            async def _judge_fn(prompt: str) -> str:
                result = await llm.chat(
                    [{"role": "user", "content": prompt}],
                    max_tokens=256, temperature=0.1,
                )
                return getattr(result, 'text', '') or str(result)

            self._judge_fn = _judge_fn
            logger.info("SynapseAggregator: auto-connected judge to TreeLLM")
            return True
        except Exception as e:
            logger.debug(f"SynapseAggregator judge auto_connect: {e}")
            return False

    # ── Statistics ─────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        return {
            "aggregations_run": sum(
                v.get("count", 0) for v in self._stats.values()
            ),
            "methods_used": {
                k: v.get("method", "unknown")
                for k, v in self._stats.items()
            },
        }


# ═══ Singleton ═════════════════════════════════════════════════════

_synapse: Optional[SynapseAggregator] = None


def get_synapse_aggregator() -> SynapseAggregator:
    global _synapse
    if _synapse is None:
        _synapse = SynapseAggregator()
        _synapse._auto_connect_judge()
    return _synapse


def set_synapse_judge(judge_fn) -> None:
    """Set an async LLM judge function for debate resolution.

    judge_fn: async callable(prompt: str) -> str
    Example:
        async def my_judge(prompt):
            return await tree_llm.chat([{"role": "user", "content": prompt}]).text
        set_synapse_judge(my_judge)
    """
    agg = get_synapse_aggregator()
    agg._judge_fn = judge_fn


__all__ = [
    "SynapseAggregator", "SynapseResult", "ModelOutput", "CrossValidation",
    "get_synapse_aggregator", "set_synapse_judge",
]
