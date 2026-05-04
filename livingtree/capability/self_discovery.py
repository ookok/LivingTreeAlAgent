"""Self-Discovering Tools — Auto-detect repeated task patterns and create reusable tools.

Monitors session history for repeated task patterns. When a user performs the
same type of operation N times, the system proposes creating a reusable tool
with a shortcut command and optimized configuration.

Usage:
    discoverer = SelfDiscovery(lookback_sessions=20, trigger_threshold=5)
    
    # Auto-called after each session:
    await discoverer.observe(session_gene)
    
    # If threshold reached:
    proposals = discoverer.get_proposals()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from loguru import logger


@dataclass
class ToolProposal:
    name: str
    category: str
    command: str
    description: str
    pattern: str
    pipeline_config: dict
    occurrence_count: int
    avg_success_rate: float
    auto_created: bool = False

    def format_display(self) -> str:
        return (
            f"Tool: [bold #58a6ff]/{self.name}[/bold #58a6ff] — {self.description}\n"
            f"  Used {self.occurrence_count}x (avg success {self.avg_success_rate:.0%})\n"
            f"  Pipeline: {self.pattern}"
        )


@dataclass
class ToolPattern:
    signature: str
    domain: str
    pipeline_steps: list[str]
    count: int = 0
    success_rates: list[float] = field(default_factory=list)
    sample_queries: list[str] = field(default_factory=list)

    def avg_success(self) -> float:
        return sum(self.success_rates) / max(len(self.success_rates), 1)

    def is_ready(self, threshold: int = 5) -> bool:
        return self.count >= threshold and self.avg_success() >= 0.6


class SelfDiscovery:

    TRIGGER_THRESHOLD = 5
    LOOKBACK_SESSIONS = 30

    def __init__(self, lookback_sessions: int = 30, trigger_threshold: int = 5):
        self._threshold = trigger_threshold
        self._lookback = lookback_sessions
        self._patterns: dict[str, ToolPattern] = {}
        self._proposals: dict[str, ToolProposal] = {}
        self._notified: set[str] = set()

    async def observe(self, session_gene: Any) -> ToolProposal | None:
        steps = getattr(session_gene, 'pipeline_steps', []) or []
        domain = getattr(session_gene, 'domain', 'general')
        success = getattr(session_gene, 'success_rate', 1.0)
        intent = getattr(session_gene, 'intent', '')

        if not steps:
            return None

        sig = self._make_signature(domain, steps)
        if sig not in self._patterns:
            self._patterns[sig] = ToolPattern(
                signature=sig,
                domain=domain,
                pipeline_steps=steps,
            )

        pat = self._patterns[sig]
        pat.count += 1
        pat.success_rates.append(success)
        if intent and len(pat.sample_queries) < 3:
            pat.sample_queries.append(intent[:100])

        if pat.is_ready(self._threshold) and sig not in self._proposals:
            proposal = self._create_proposal(pat)
            self._proposals[sig] = proposal
            logger.info(f"SelfDiscovery: new tool proposal /{proposal.name} ({pat.count}x)")
            return proposal

        return None

    def get_proposals(self) -> list[ToolProposal]:
        return list(self._proposals.values())

    def get_new_proposals(self) -> list[ToolProposal]:
        new = [p for sig, p in self._proposals.items() if sig not in self._notified]
        return new

    def mark_notified(self, name: str) -> None:
        for sig, p in self._proposals.items():
            if p.name == name:
                self._notified.add(sig)

    def mark_created(self, name: str) -> None:
        for sig, p in self._proposals.items():
            if p.name == name:
                p.auto_created = True

    def get_stats(self) -> dict:
        return {
            "patterns_tracked": len(self._patterns),
            "proposals_generated": len(self._proposals),
            "auto_created": sum(1 for p in self._proposals.values() if p.auto_created),
            "trigger_threshold": self._threshold,
        }

    def _create_proposal(self, pat: ToolPattern) -> ToolProposal:
        steps = pat.pipeline_steps
        pattern = "→".join(steps[:4])
        name = self._generate_name(pat.domain, steps)
        cmd = f"/{name}"

        return ToolProposal(
            name=name,
            category=pat.domain,
            command=cmd,
            description=f"Auto-generated {pat.domain} tool ({pat.count} occurrences)",
            pattern=pattern,
            pipeline_config={
                "domain": pat.domain,
                "steps": [{"op": s} for s in steps],
            },
            occurrence_count=pat.count,
            avg_success_rate=pat.avg_success(),
        )

    @staticmethod
    def _make_signature(domain: str, steps: list[str]) -> str:
        return f"{domain}:" + "+".join(steps[:5])

    @staticmethod
    def _generate_name(domain: str, steps: list[str]) -> str:
        op_keywords = {"extract": "extract", "map": "process", "filter": "filter",
                       "resolve": "dedup", "reduce": "summary", "sort": "sort",
                       "glean": "refine"}
        parts = [domain[:6]]
        for s in steps[:3]:
            short = op_keywords.get(s, s[:4])
            if short not in parts:
                parts.append(short)
        return "_".join(parts[:3])
