"""AgentParliament — Multi-agent deliberative parliament with chair, voting, and minority reports.

Builds on existing SynapseAggregator (consensus/debate/stitch), MultiAgentDebate
(parallel agent roles), and SheshaHeads (inter-head messaging).

Protocol:
  1. Chair(LLM) opens session, defines question and agent roles
  2. Round 1: Position — each agent states its position independently
  3. Round 2: Cross-Examination — agents critique each other's positions
  4. Round 3: Revision — agents revise based on critiques
  5. Round 4: Closing — final statements
  6. Vote: weighted by historical accuracy × confidence
  7. Chair delivers majority verdict + formal minority report

Integration:
  parliament = get_agent_parliament()
  verdict = await parliament.deliberate(question, roles=["analyst","critic","synthesizer"])
"""

from __future__ import annotations

import asyncio
import math
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from loguru import logger


# ═══ Data Types ════════════════════════════════════════════════════


@dataclass
class AgentRole:
    name: str
    persona: str
    expertise: str
    weight: float = 1.0           # Voting weight (adjusted by historical accuracy)
    accuracy_history: list[float] = field(default_factory=list)

    @property
    def historical_accuracy(self) -> float:
        if not self.accuracy_history:
            return 0.5
        return sum(self.accuracy_history[-10:]) / len(self.accuracy_history[-10:])


@dataclass
class Position:
    agent: str
    content: str
    confidence: float = 0.5
    citations: list[str] = field(default_factory=list)


@dataclass
class Critique:
    from_agent: str
    target_agent: str
    content: str
    severity: str = "moderate"    # minor|moderate|major|fatal


@dataclass
class Vote:
    agent: str
    preferred_position: str      # Which agent's position they support
    confidence: float = 0.5
    reasoning: str = ""


@dataclass
class Verdict:
    question: str
    majority_position: str = ""   # Winning position
    majority_agents: list[str] = field(default_factory=list)
    minority_report: str = ""     # Dissenting views preserved
    minority_agents: list[str] = field(default_factory=list)
    consensus_score: float = 0.0  # 0.0-1.0
    rounds: int = 0
    duration_ms: float = 0.0


# ═══ AgentParliament ══════════════════════════════════════════════


class AgentParliament:
    """Multi-agent deliberative parliament with structured procedure."""

    _instance: Optional["AgentParliament"] = None

    @classmethod
    def instance(cls) -> "AgentParliament":
        if cls._instance is None:
            cls._instance = AgentParliament()
        return cls._instance

    def __init__(self):
        self._default_roles = [
            AgentRole("analyst", "数据驱动的理性分析者", "逻辑分析、数据推理、因果推断"),
            AgentRole("critic", "严格的质量审查者", "找出逻辑漏洞、边界情况、隐含假设"),
            AgentRole("synthesizer", "多方视角的综合者", "整合不同观点、发现共识、构建框架"),
            AgentRole("innovator", "创造性思考者", "跳出框框、提出新思路、挑战常规"),
            AgentRole("pragmatist", "务实的执行者", "关注可行性、成本收益、实施路径"),
        ]
        self._sessions = 0

    # ── Main Protocol ──────────────────────────────────────────────

    async def deliberate(self, question: str,
                         roles: list[str] = None,
                         chat_fn: Callable = None,
                         max_rounds: int = 3) -> Verdict:
        """Run full parliamentary deliberation. Returns verdict."""
        t0 = time.time()
        self._sessions += 1

        # Select agents
        selected = [r for r in self._default_roles
                    if not roles or r.name in roles][:5]
        if len(selected) < 2:
            selected = self._default_roles[:3]

        verdict = Verdict(question=question)

        # 1. Position statements (parallel)
        positions = await self._gather_positions(question, selected, chat_fn)

        # 2-3. Cross-examination + Revision rounds
        for round_num in range(1, max_rounds + 1):
            critiques = await self._cross_examine(positions, selected, chat_fn)
            positions = await self._revise(positions, critiques, selected, chat_fn, question)
            verdict.rounds = round_num

        # 4. Vote
        votes = await self._gather_votes(positions, selected, chat_fn)

        # 5. Tally + minority report
        self._tally(verdict, votes, positions, selected)

        verdict.duration_ms = (time.time() - t0) * 1000
        logger.info(
            f"AgentParliament: verdict reached in {len(selected)} agents, "
            f"{verdict.rounds} rounds, consensus={verdict.consensus_score:.2f}"
        )
        return verdict

    # ── Protocol Steps ─────────────────────────────────────────────

    async def _gather_positions(self, question: str, agents: list[AgentRole],
                                chat_fn: Callable) -> list[Position]:
        """Round 1: Each agent states its position independently."""
        async def _ask(agent):
            prompt = (
                f"你是{agent.name}({agent.expertise})。\n"
                f"问题: {question}\n"
                f"请给出你对这个问题的立场和分析。用100-200字。"
            )
            if chat_fn:
                try:
                    result = await chat_fn([{"role": "user", "content": prompt}],
                                          max_tokens=300, temperature=0.3)
                    text = getattr(result, 'text', '') or str(result)
                    return Position(agent=agent.name, content=text[:500], confidence=0.7)
                except Exception:
                    pass
            return Position(agent=agent.name, content=f"[{agent.name}] 需要更多信息来分析此问题。")

        tasks = [_ask(a) for a in agents]
        return await asyncio.gather(*tasks)

    async def _cross_examine(self, positions: list[Position],
                             agents: list[AgentRole],
                             chat_fn: Callable) -> list[Critique]:
        """Rounds 2-3: Agents critique each other."""
        critiques = []
        async def _critique(critic, target_pos):
            prompt = (
                f"你是{critic.name}({critic.expertise})。"
                f"审查{target_pos.agent}的观点:\n{target_pos.content[:300]}\n"
                f"找出逻辑漏洞、遗漏或错误。用50-100字。"
            )
            if chat_fn:
                try:
                    result = await chat_fn([{"role": "user", "content": prompt}],
                                          max_tokens=200, temperature=0.2)
                    text = getattr(result, 'text', '') or str(result)
                    sev = "major" if any(k in text for k in ["错误","矛盾","遗漏关键"]) else "moderate"
                    return Critique(from_agent=critic.name, target_agent=target_pos.agent,
                                   content=text[:300], severity=sev)
                except Exception:
                    pass
            return None

        tasks = []
        for critic in agents:
            for pos in positions:
                if pos.agent != critic.name:
                    tasks.append(_critique(critic, pos))

        results = await asyncio.gather(*tasks)
        critiques = [r for r in results if r is not None]
        return critiques[:len(agents) * 2]  # Cap critiques

    async def _revise(self, positions: list[Position],
                      critiques: list[Critique], agents: list[AgentRole],
                      chat_fn: Callable, question: str) -> list[Position]:
        """Round 2-3: Agents revise positions based on critiques."""
        async def _revise(agent, original_pos):
            my_critiques = [c for c in critiques if c.target_agent == agent.name]
            if not my_critiques:
                return original_pos

            critique_text = "\n".join(
                f"- [{c.from_agent}] {c.content[:200]}" for c in my_critiques[:3]
            )
            prompt = (
                f"你是{agent.name}。收到以下批评:\n{critique_text}\n\n"
                f"原立场:\n{original_pos.content[:300]}\n\n"
                f"问题: {question}\n"
                f"请修正你的立场,回应批评。如有错误,承认并修正。用100-200字。"
            )
            if chat_fn:
                try:
                    result = await chat_fn([{"role": "user", "content": prompt}],
                                          max_tokens=300, temperature=0.2)
                    text = getattr(result, 'text', '') or str(result)
                    return Position(agent=agent.name, content=text[:500],
                                   confidence=min(1.0, original_pos.confidence + 0.1))
                except Exception:
                    pass
            return original_pos

        tasks = [_revise(a, pos) for a, pos in zip(agents, positions)]
        return await asyncio.gather(*tasks)

    async def _gather_votes(self, positions: list[Position],
                            agents: list[AgentRole],
                            chat_fn: Callable) -> list[Vote]:
        """Agents vote for the position they support."""
        votes = []
        for agent in agents:
            others = [p for p in positions if p.agent != agent.name]
            if not others:
                continue

            pos_text = "\n".join(f"- [{p.agent}]: {p.content[:150]}" for p in others)
            prompt = (
                f"你是{agent.name}。审查以下观点:\n{pos_text}\n"
                f"选择你支持的观点(只回复agent名称),并简述理由(30字):"
            )
            if chat_fn:
                try:
                    result = await chat_fn([{"role": "user", "content": prompt}],
                                          max_tokens=100, temperature=0.1)
                    text = getattr(result, 'text', '') or str(result)
                    preferred = others[0].agent
                    for p in others:
                        if p.agent.lower() in text.lower():
                            preferred = p.agent
                            break
                    votes.append(Vote(agent=agent.name, preferred_position=preferred,
                                     confidence=0.6, reasoning=text[:100]))
                except Exception:
                    pass

        return votes

    def _tally(self, verdict: Verdict, votes: list[Vote],
               positions: list[Position], agents: list[AgentRole]) -> None:
        """Tally votes with weighted voting. Preserve minority report."""
        tally = defaultdict(float)
        for vote in votes:
            agent = next((a for a in agents if a.name == vote.agent), None)
            weight = agent.historical_accuracy if agent else 1.0
            tally[vote.preferred_position] += weight * vote.confidence

        if not tally:
            return

        sorted_tally = sorted(tally.items(), key=lambda x: -x[1])
        winner = sorted_tally[0][0]
        total = sum(tally.values())
        verdict.consensus_score = sorted_tally[0][1] / max(total, 0.01)
        verdict.majority_agents = [v.agent for v in votes if v.preferred_position == winner]

        # Majority position
        for pos in positions:
            if pos.agent == winner:
                verdict.majority_position = pos.content[:1000]
                break

        # Minority report
        if len(sorted_tally) > 1 and sorted_tally[0][1] / max(sorted_tally[1][1], 0.01) < 2.0:
            runner_up = sorted_tally[1][0]
            verdict.minority_agents = [v.agent for v in votes if v.preferred_position == runner_up]
            for pos in positions:
                if pos.agent == runner_up:
                    minority_support = sorted_tally[1][1] / max(total, 0.01)
                    verdict.minority_report = (
                        f"[少数派报告,支持率{minority_support:.0%}] {pos.content[:800]}"
                    )
                    break

    # ── Feedback ───────────────────────────────────────────────────

    def record_accuracy(self, agent_name: str, correct: bool) -> None:
        for role in self._default_roles:
            if role.name == agent_name:
                role.accuracy_history.append(1.0 if correct else 0.0)
                if len(role.accuracy_history) > 50:
                    role.accuracy_history = role.accuracy_history[-50:]
                return

    def stats(self) -> dict:
        return {
            "sessions": self._sessions,
            "agents": {r.name: round(r.historical_accuracy, 3) for r in self._default_roles},
        }


# ═══ Singleton ════════════════════════════════════════════════════

_parliament: Optional[AgentParliament] = None


def get_agent_parliament() -> AgentParliament:
    global _parliament
    if _parliament is None:
        _parliament = AgentParliament()
    return _parliament


__all__ = ["AgentParliament", "Verdict", "AgentRole", "get_agent_parliament"]
