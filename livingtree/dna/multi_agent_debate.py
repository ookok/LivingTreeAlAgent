"""Multi-Agent Debate — Internal consensus before external response.

Instead of a single LLM answer, multiple internal "agents" (perspectives)
independently analyze the query, debate differences, and reach consensus.
The final answer reflects the synthesis, not a single model's output.

Agents: Analyst, Critic, Synthesizer, FactChecker, CreativeExplorer.
Each runs in parallel (using flash models for speed), then a pro model
synthesizes the consensus.

Usage:
    debate = MultiAgentDebate(consciousness)
    result = await debate.deliberate("Should we refactor the auth module?")
"""

from __future__ import annotations
import asyncio, time
from dataclasses import dataclass, field
from loguru import logger

@dataclass
class AgentView:
    agent: str
    perspective: str
    output: str = ""
    confidence: float = 0.5
    latency_ms: float = 0.0

@dataclass  
class DebateResult:
    query: str
    views: list[AgentView] = field(default_factory=list)
    consensus: str = ""
    confidence: float = 0.5
    dissenting_points: list[str] = field(default_factory=list)
    total_latency_ms: float = 0.0

AGENT_DEFINITIONS = {
    "Analyst": "Analyze the core facts, data, and logic. Be precise and evidence-based. Provide structured analysis.",
    "Critic": "Identify weaknesses, risks, edge cases, and blind spots. Challenge assumptions. Be skeptical.",
    "Synthesizer": "Combine perspectives into a coherent whole. Find patterns across viewpoints. Integrate insights.",
    "FactChecker": "Verify factual claims. Check against what is known. Flag uncertain or unverified statements.",
    "CreativeExplorer": "Think outside the box. Propose novel angles, unconventional solutions, creative alternatives.",
}

class MultiAgentDebate:
    """Internal multi-agent deliberation before response generation."""

    MAX_PARALLEL = 5

    def __init__(self, consciousness=None):
        self._consciousness = consciousness

    async def deliberate(self, query: str, agents: list[str] | None = None,
                         min_agents: int = 3) -> DebateResult:
        t0 = time.monotonic()
        agent_names = agents or list(AGENT_DEFINITIONS.keys())[:min_agents]
        agent_names = agent_names[:self.MAX_PARALLEL]

        if len(agent_names) < min_agents:
            agent_names = list(AGENT_DEFINITIONS.keys())[:min_agents]

        tasks = []
        for name in agent_names:
            definition = AGENT_DEFINITIONS.get(name, name)
            tasks.append(self._run_agent(name, definition, query))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        views = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                views.append(AgentView(agent=agent_names[i], perspective="error", output=str(r)))
            else:
                views.append(r)

        consensus_text = await self._synthesize(query, views)
        consensus_result = DebateResult(
            query=query,
            views=views,
            consensus=consensus_text,
            confidence=sum(v.confidence for v in views) / max(len(views), 1),
            dissenting_points=self._extract_dissent(views, consensus_text),
            total_latency_ms=(time.monotonic() - t0) * 1000,
        )

        return consensus_result

    async def _run_agent(self, name: str, definition: str, query: str) -> AgentView:
        t0 = time.monotonic()
        try:
            prompt = (
                f"You are the {name}. {definition}\n\n"
                f"Analyze the following query from your perspective:\n{query}\n\n"
                f"Output your analysis (3-5 sentences max). Be direct."
            )
            if self._consciousness:
                result = await self._consciousness.chain_of_thought(prompt, steps=1, max_tokens=512)
                confidence = 0.7 if len(result) > 50 else 0.4
            else:
                result = f"[{name}] No consciousness available for: {query[:50]}"
                confidence = 0.1
        except Exception as e:
            result = f"[{name}] Error: {e}"
            confidence = 0.0

        return AgentView(
            agent=name,
            perspective=definition[:50],
            output=result,
            confidence=confidence,
            latency_ms=(time.monotonic() - t0) * 1000,
        )

    async def _synthesize(self, query: str, views: list[AgentView]) -> str:
        if not views or not self._consciousness:
            return ""

        perspectives = "\n\n".join(
            f"[{v.agent}]: {v.output[:300]}" for v in views
        )

        prompt = (
            f"Synthesize these {len(views)} expert perspectives into a unified response.\n\n"
            f"Query: {query}\n\n"
            f"Perspectives:\n{perspectives}\n\n"
            f"Synthesize: identify agreements, resolve disagreements, produce final answer."
        )
        try:
            return await self._consciousness.chain_of_thought(prompt, steps=2, max_tokens=1024)
        except Exception:
            return perspectives

    @staticmethod
    def _extract_dissent(views: list[AgentView], consensus: str) -> list[str]:
        if not consensus:
            return []
        dissent = []
        for v in views:
            if v.output and v.confidence < 0.5:
                dissent.append(f"{v.agent}: {v.output[:100]}")
        return dissent[:3]

    # ═══ SSDataBench: View Diversity Analysis ═══

    def analyze_diversity(self, recent_debates: list[DebateResult] = None) -> dict:
        """SSDataBench-style variance analysis of agent view diversity.

        From paper: LLMs "compress real-world heterogeneity into simplified
        typological structures." Checks if 5 predefined agent roles exhibit
        sufficient diversity — or fall into the typological collapse pattern.

        Returns:
            dict with:
            - view_length_variance: variance of output lengths across agents
            - confidence_dispersion: standard deviation of confidence scores
            - semantic_overlap: estimated pairwise output similarity
            - typological_compression_risk: True if diversity is too low
        """
        import numpy as np
        import hashlib

        if not recent_debates:
            return {
                "status": "no_data",
                "message": "No recent debates available for diversity analysis.",
            }

        all_views: list[AgentView] = []
        for d in recent_debates:
            all_views.extend(d.views)

        if len(all_views) < 10:
            return {
                "status": "insufficient_data",
                "message": "Need ≥10 agent views for meaningful analysis (have {}).".format(len(all_views)),
                "view_count": len(all_views),
            }

        # 1. Output length variance
        lengths = [len(v.output) for v in all_views if v.output]
        length_var = float(np.var(lengths)) if lengths else 0.0
        length_cv = float(np.std(lengths) / max(np.mean(lengths), 1)) if lengths else 0.0

        # 2. Confidence dispersion
        confidences = [v.confidence for v in all_views]
        conf_std = float(np.std(confidences)) if confidences else 0.0

        # 3. Semantic overlap: estimated via n-gram hash similarity
        def _ngram_hash(text: str, n: int = 2) -> set:
            text = text.lower()[:500]
            return {hashlib.md5(text[i:i+n].encode()).hexdigest()[:8]
                    for i in range(len(text) - n + 1)}

        groups: dict[str, list[AgentView]] = {}
        for v in all_views:
            groups.setdefault(v.agent, []).append(v)

        pairwise_similarities = []
        agent_names = list(groups.keys())
        for i in range(len(agent_names)):
            for j in range(i + 1, len(agent_names)):
                set_a = set()
                set_b = set()
                for v in groups[agent_names[i]]:
                    set_a.update(_ngram_hash(v.output))
                for v in groups[agent_names[j]]:
                    set_b.update(_ngram_hash(v.output))
                intersection = len(set_a & set_b)
                union = len(set_a | set_b)
                if union > 0:
                    pairwise_similarities.append(intersection / union)

        avg_similarity = float(np.mean(pairwise_similarities)) if pairwise_similarities else 0.0

        # 4. Typological compression check
        # Paper finding: LLM outputs often collapse to a few templates
        typological_compression_risk = (
            length_cv < 0.15 and  # Too little length variation
            conf_std < 0.08 and   # Too little confidence variation
            avg_similarity > 0.65  # Too much overlap between roles
        )

        recommendations = []
        if typological_compression_risk:
            recommendations.append(
                "CRITICAL: Typological compression detected. "
                "5 predefined roles may not produce sufficient diversity. "
                "Consider: (1) adding role-specific temperature variation, "
                "(2) introducing randomized persona traits per debate, "
                "(3) increasing the distinctiveness of role definitions."
            )
        elif avg_similarity > 0.5:
            recommendations.append(
                "Moderate overlap between agent views. "
                "Consider adding more contrasting role definitions or "
                "randomizing agent prompt prefixes."
            )

        return {
            "status": "analyzed",
            "view_count": len(all_views),
            "agent_count": len(groups),
            "length_variance": round(length_var, 1),
            "length_cv": round(length_cv, 3),
            "confidence_std": round(conf_std, 3),
            "avg_pairwise_similarity": round(avg_similarity, 4),
            "typological_compression_risk": typological_compression_risk,
            "recommendations": recommendations,
        }
