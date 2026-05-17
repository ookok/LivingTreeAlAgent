"""IdleConsolidator — background memory consolidation during idle time.

    Like human hippocampal replay during sleep:
    1. Detects system idle (>60s no user input)
    2. Scans today's conversations for key decisions/insights
    3. LLM distills into structured knowledge entries
    4. Writes to IntelligentKB + StructMem for future recall
    5. Tags: date, topic, importance, action_items

    Usage:
        ic = get_idle_consolidator()
        await ic.start(hub, idle_threshold=60)  # triggered by LifeDaemon
"""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

CONSOLIDATE_DIR = Path(".livingtree/consolidated")


@dataclass
class ConsolidateEntry:
    timestamp: float
    topic: str
    summary: str
    decisions: list[str] = field(default_factory=list)
    action_items: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    source: str = "idle_consolidation"


class IdleConsolidator:
    """Background knowledge consolidation engine."""

    def __init__(self):
        CONSOLIDATE_DIR.mkdir(parents=True, exist_ok=True)
        self._last_input_time = time.time()
        self._running = False
        self._consolidations: list[ConsolidateEntry] = []
        self._loaded = False

    def touch(self):
        """Mark user activity — reset idle timer."""
        self._last_input_time = time.time()

    @property
    def idle_seconds(self) -> float:
        return time.time() - self._last_input_time

    async def start(self, hub=None, idle_threshold: int = 60):
        """Periodic consolidation task. Run as background daemon."""
        self._running = True
        self._load()

        while self._running:
            try:
                if self.idle_seconds >= idle_threshold and hub and hub.world:
                    await self._consolidate_pass(hub)
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"Consolidation tick: {e}")
                await asyncio.sleep(30)

    def stop(self):
        self._running = False

    async def _consolidate_pass(self, hub):
        """One pass of consolidation."""
        # Gather raw material
        conversations = self._gather_conversations()

        # ── Pre-warm KV cache for active providers ──
        self._pre_warm_cache(hub)

        # ── Adaptive practice: self-study weakest skill ──
        try:
            from .adaptive_practice import get_adaptive_practice
            ap = get_adaptive_practice()
            await ap.practice_weakest(hub)
        except Exception:
            pass

        # ── ErrorReplay: self-heal from recorded errors ──
        try:
            # debug_pro migrated to bridge get_error_replay  # TODO(bridge): via bridge.LLMProtocol
            await get_error_replay().auto_heal_cycle(hub)
        except Exception:
            pass

        if not conversations:
            return

        # ── Pre-warm KV cache for active providers ──
        self._pre_warm_cache(hub)

        try:
            result = await llm.chat(
                messages=[{"role": "user", "content": (
                    "You are consolidating knowledge from a conversation history. "
                    "Extract the KEY decisions, insights, and action items.\n\n"
                    "CONVERSATION:\n" + conversations[-6000:] + "\n\n"
                    "Output JSON:\n"
                    '{"topic": "1-line topic of this conversation", '
                    '"summary": "2-3 sentence summary of what was accomplished", '
                    '"decisions": ["decision 1", "decision 2"], '
                    '"action_items": ["item 1", "item 2"], '
                    '"tags": ["tag1", "tag2", "tag3"]}'
                )}],
                provider=getattr(llm, '_elected', ''),
                temperature=0.2, max_tokens=500, timeout=20,
            )
            if result and result.text:
                import re
                m = re.search(r'\{[\s\S]*\}', result.text)
                if m:
                    data = json.loads(m.group())
                    entry = ConsolidateEntry(
                        timestamp=time.time(),
                        topic=data.get("topic", ""),
                        summary=data.get("summary", ""),
                        decisions=data.get("decisions", []),
                        action_items=data.get("action_items", []),
                        tags=data.get("tags", []),
                    )
                    self._consolidations.append(entry)
                    self._save(entry)
                    self._index_to_kb(entry, hub)

                    tags_str = ", ".join(entry.tags[:5]) if entry.tags else ""
                    logger.debug(f"🧠 Consolidated: {entry.topic[:60]} [{tags_str}]")
        except Exception as e:
            logger.debug(f"Consolidation LLM: {e}")

    def _gather_conversations(self) -> str:
        """Gather recent conversation history."""
        parts = []
        try:
            from ..knowledge.session_search import get_search
            search = get_search()
            # Get recent sessions
            sessions = getattr(search, '_sessions', {})
            for sid, turns in list(sessions.items())[-3:]:
                for turn in turns[-5:]:
                    role = getattr(turn, 'role', '?') if hasattr(turn, 'role') else str(turn)[:100]
                    content = getattr(turn, 'content', str(turn))[:300]
                    parts.append(f"{role}: {content}")
        except Exception:
            pass
        # Fallback: simple log
        if not parts and CONSOLIDATE_DIR.exists():
            for f in sorted(CONSOLIDATE_DIR.glob("*.json"))[-3:]:
                try:
                    d = json.loads(f.read_text(encoding="utf-8"))
                    parts.append(d.get("summary", "")[:200])
                except Exception:
                    pass
        return "\n".join(parts[-30:])

    def _save(self, entry: ConsolidateEntry):
        fpath = CONSOLIDATE_DIR / f"{int(entry.timestamp)}.json"
        fpath.write_text(json.dumps({
            "timestamp": entry.timestamp,
            "topic": entry.topic,
            "summary": entry.summary,
            "decisions": entry.decisions,
            "action_items": entry.action_items,
            "tags": entry.tags,
            "source": entry.source,
        }, indent=2, ensure_ascii=False), encoding="utf-8")

    def _load(self):
        if self._loaded:
            return
        if CONSOLIDATE_DIR.exists():
            for f in sorted(CONSOLIDATE_DIR.glob("*.json")):
                try:
                    d = json.loads(f.read_text(encoding="utf-8"))
                    self._consolidations.append(ConsolidateEntry(**{
                        k: d.get(k, "") for k in ConsolidateEntry.__dataclass_fields__
                    }))
                except Exception:
                    pass
        self._loaded = True

    def _index_to_kb(self, entry: ConsolidateEntry, hub):
        """Push consolidated knowledge to KB stores."""
        try:
            content = f"## {entry.topic}\n\n{entry.summary}\n\n"
            if entry.decisions:
                content += "**决策:**\n" + "\n".join(f"- {d}" for d in entry.decisions) + "\n\n"
            if entry.action_items:
                content += "**行动项:**\n" + "\n".join(f"- [ ] {a}" for a in entry.action_items)

            from ..core.unified_registry import get_registry
            reg = get_registry()
            for kb_name, kb_obj in getattr(reg, '_kbs', {}).items():
                try:
                    kb_obj.add(
                        id=f"consolidated:{entry.topic[:30]}:{int(entry.timestamp)}",
                        title=entry.topic,
                        content=content,
                        source="idle_consolidation",
                        tags=entry.tags,
                    )
                except Exception:
                    pass
        except Exception:
            pass

    def _pre_warm_cache(self, hub):
        """Pre-warm KV cache for providers during idle time.

        Sends a lightweight 'ping with context' to cache the system prompt
        on providers that support prefix caching. This means the next real
        user request gets cached tokens immediately.
        """
        try:
            from ..bridge.registry import get_tool_registry
            director = get_tool_registry().get('cache_director')

            llm = hub.world.consciousness._llm
            for name in llm.provider_names:
                if not director.supports_cache(name):
                    continue
                # Only pre-warm if we have cache stats showing benefit
                s = director.provider_stats(name)
                if s and s["hit_rate_pct"] < 10 and s["total_turns"] > 5:
                    continue  # Not getting enough hits to be worth warming

                try:
                    # Send a lightweight system prompt warm-up
                    provider = llm.get_provider(name)
                    if provider:
                        cap = director.get_capability(name)
                        director.pre_warm(
                            [{"role": "user", "content": "ping"}],
                            name, hub
                        )
                except Exception:
                    pass
        except Exception:
            pass

    def recent_consolidations(self, n: int = 5) -> list[ConsolidateEntry]:
        return self._consolidations[-n:]


_ic: IdleConsolidator | None = None


def get_idle_consolidator() -> IdleConsolidator:
    global _ic
    if _ic is None:
        _ic = IdleConsolidator()
    return _ic
