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
