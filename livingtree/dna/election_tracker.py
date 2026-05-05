"""ElectionTracker — captures which model served each layer per message.

L0: free models (longcat/zhipu/spark/siliconflow/mofang)
L1: paid models (xiaomi/aliyun/dmxapi/deepseek) 
L2: opencode (bridge-discovered providers)
L3: opencode-serve (local relay)

Tracks per-message election and generates a compact display badge.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from loguru import logger


@dataclass
class LayerElection:
    layer: int
    provider: str = ""
    model: str = ""
    latency_ms: float = 0.0

    @property
    def label(self) -> str:
        if not self.provider:
            return ""
        return f"{self.provider}"


@dataclass
class MessageElection:
    """Election snapshot for a single message turn."""
    l0: LayerElection = field(default_factory=lambda: LayerElection(0))
    l1: LayerElection = field(default_factory=lambda: LayerElection(1))
    l2: LayerElection = field(default_factory=lambda: LayerElection(2))
    l3: LayerElection = field(default_factory=lambda: LayerElection(3))

    @property
    def all_same(self) -> bool:
        """Whether all layers used the same provider."""
        providers = {self.l0.provider, self.l1.provider, self.l2.provider, self.l3.provider}
        providers.discard("")
        return len(providers) <= 1

    @property
    def merged_label(self) -> str:
        """Single merged label when all layers agree."""
        for l in [self.l0, self.l3, self.l2, self.l1]:
            if l.provider:
                return l.provider
        return "none"

    def format_badge(self) -> str:
        """Generate a compact election badge for display."""
        if self.all_same:
            merged = self.merged_label
            if not merged or merged == "none":
                return ""
            return f"[dim #8b949e]⚡{merged}[/dim #8b949e]"

        parts = []
        for l in [self.l0, self.l1, self.l2, self.l3]:
            if l.provider:
                parts.append(f"L{l.layer}:{l.provider}")
        return f"[dim #8b949e]{' · '.join(parts)}[/dim #8b949e]"


class ElectionTracker:
    """Tracks per-message election and provides display formatting."""

    def __init__(self):
        self._history: list[MessageElection] = []
        self._current: MessageElection | None = None

    def start_turn(self):
        self._current = MessageElection()

    def record_layer(self, layer: int, provider: str, model: str = "", latency_ms: float = 0.0):
        if self._current is None:
            self.start_turn()
        election = LayerElection(layer=layer, provider=provider, model=model, latency_ms=latency_ms)
        if layer == 0:
            self._current.l0 = election
        elif layer == 1:
            self._current.l1 = election
        elif layer == 2:
            self._current.l2 = election
        elif layer == 3:
            self._current.l3 = election

    def snapshot(self, hub=None) -> MessageElection:
        """Capture current election state from hub consciousness."""
        if self._current is None:
            self.start_turn()

        if hub and hub.world:
            try:
                consciousness = hub.world.consciousness
                elected = getattr(consciousness._llm, '_elected', '')
                llm = consciousness._llm

                # Determine which layer the elected provider belongs to
                free_models = getattr(consciousness, '_free_models', [])
                paid_models = getattr(consciousness, '_paid_models', [])
                oc_cache = getattr(consciousness, '_opencode_cache', [])

                oc_providers = {f"oc-{p.get('name', '')}" for p in oc_cache}

                if elected == "opencode-serve":
                    self.record_layer(3, "opencode-serve", "")
                elif elected in oc_providers or elected.startswith("oc-"):
                    self.record_layer(2, elected, "")
                elif elected in free_models:
                    self.record_layer(0, elected, "")
                elif elected in paid_models:
                    self.record_layer(1, elected, "")
                elif elected:
                    self.record_layer(0, elected, "")
            except Exception as e:
                logger.debug(f"Election snapshot: {e}")

        result = self._current
        self._history.append(result)
        return result

    def get_badge_text(self, hub=None) -> str:
        """Get election badge text for the current message."""
        election = self.snapshot(hub)
        return election.format_badge()

    def get_status(self) -> dict:
        total = len(self._history)
        if total == 0:
            return {"total_turns": 0}
        merged = sum(1 for e in self._history if e.all_same)
        providers = {}
        for e in self._history:
            for l in [e.l0, e.l1, e.l2, e.l3]:
                if l.provider:
                    providers[l.provider] = providers.get(l.provider, 0) + 1
        return {
            "total_turns": total,
            "merged_turns": merged,
            "merge_rate": merged / total,
            "top_providers": dict(sorted(providers.items(), key=lambda x: -x[1])[:5]),
        }


# ═══ Global singleton ═══

_tracker: ElectionTracker | None = None


def get_tracker() -> ElectionTracker:
    global _tracker
    if _tracker is None:
        _tracker = ElectionTracker()
    return _tracker
