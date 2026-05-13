"""LearningSourceRegistry — User-configurable learning source management.

Provides a unified registry for all external knowledge sources that LivingTree
learns from. Users can add/remove sources and specify research directions through
a simple configuration file or programmatic API.

Architecture:
  LearningSourceRegistry (central manager)
    ├── Built-in sources: arxiv, github, nature
    ├── User-added sources (via config file or API)
    ├── Research directions (topic filtering per source)
    └── Source adapters (normalize different APIs to common Paper/Repo types)

Configuration (~/.livingtree/learning_sources.yaml):
  sources:
    - name: arxiv
      enabled: true
      categories: [cs.AI, cs.CL, cs.MA, cs.LG]
      queries: ["multi-agent LLM orchestration", "model routing optimization"]
    - name: nature
      enabled: true
      journals: [nature, natmachintell, srep, npjai]
      queries: ["collective intelligence", "multi-agent", "LLM reasoning"]
    - name: github
      enabled: true
      queries: ["LLM agent framework", "multi-agent orchestration"]
  directions:
    - name: "Multi-LLM orchestration"
      keywords: [routing, ensemble, model selection, orchestration]
    - name: "Reasoning depth"
      keywords: [chain-of-thought, reflection, self-improvement]

Usage:
    registry = get_learning_sources()
    registry.add_source("nature", journals=["nature", "natmachintell"])
    registry.add_direction("AI safety", keywords=["alignment", "guardrails"])
    papers = await registry.search("Multi-LLM orchestration", max_results=20)
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from loguru import logger

CONFIG_DIR = Path(".livingtree")
SOURCES_CONFIG = CONFIG_DIR / "learning_sources.json"


# ═══ Data Types ════════════════════════════════════════════════════


@dataclass
class ResearchDirection:
    """A user-defined research direction for focused learning."""
    name: str
    keywords: list[str] = field(default_factory=list)
    description: str = ""
    priority: int = 0
    created_at: float = field(default_factory=time.time)


@dataclass
class LearningSource:
    """Configuration for an external learning source."""
    name: str
    source_type: str            # "arxiv", "nature", "github", "custom"
    enabled: bool = True
    base_url: str = ""
    categories: list[str] = field(default_factory=list)
    journals: list[str] = field(default_factory=list)  # for nature
    queries: list[str] = field(default_factory=list)
    max_results: int = 50
    refresh_hours: int = 24
    last_refreshed: float = 0.0
    paper_count: int = 0
    pattern_count: int = 0
    created_at: float = field(default_factory=time.time)


# ═══ Built-in Source Presets ═══════════════════════════════════════

BUILTIN_SOURCES: dict[str, dict[str, Any]] = {
    "arxiv": {
        "source_type": "arxiv",
        "base_url": "https://export.arxiv.org/api/query",
        "categories": ["cs.AI", "cs.CL", "cs.MA", "cs.LG", "cs.DC"],
        "queries": [
            "multi-agent LLM orchestration autonomous",
            "LLM routing model selection optimization",
            "retrieval augmented generation knowledge graph",
            "autonomous skill discovery self-improving agent",
            "context window optimization prompt compression",
            "chain of thought reasoning planning verification",
            "hierarchical memory episodic semantic agent",
            "collective intelligence swarm coordination",
        ],
    },
    "nature": {
        "source_type": "nature",
        "base_url": "https://www.nature.com",
        "journals": [
            "nature", "natmachintell", "srep", "npjai",
            "ncomms", "commschem", "npjdigitalmed",
        ],
        "queries": [
            "multi-agent LLM orchestration collective intelligence",
            "large language model reasoning chain-of-thought",
            "stigmergy swarm intelligence coordination",
            "heterogeneous computing resource allocation scheduling",
            "autonomous agent self-improving learning",
        ],
    },
    "github": {
        "source_type": "github",
        "base_url": "https://api.github.com",
        "queries": [
            "LLM agent framework Python autonomous",
            "multi-agent orchestration tool-calling",
            "knowledge graph RAG retrieval vector",
            "LLM router model selection cost optimization",
            "self-improving AI autonomous evolution",
        ],
    },
}

DEFAULT_DIRECTIONS = [
    ResearchDirection(
        name="Multi-LLM orchestration",
        keywords=["routing", "ensemble", "model selection", "orchestration",
                   "multi-model", "provider", "election", "scheduling"],
        description="How to optimally route and coordinate multiple LLMs",
        priority=10,
    ),
    ResearchDirection(
        name="Reasoning depth",
        keywords=["chain-of-thought", "reflection", "self-improvement",
                   "reasoning", "thinking", "planning", "verification"],
        description="Techniques for deeper and more reliable LLM reasoning",
        priority=9,
    ),
    ResearchDirection(
        name="Collective intelligence",
        keywords=["swarm", "collective", "stigmergy", "emergence",
                   "coordination", "consensus", "decentralized"],
        description="How groups of agents achieve intelligence beyond individuals",
        priority=8,
    ),
]


# ═══ LearningSourceRegistry ═══════════════════════════════════════


class LearningSourceRegistry:
    """Central registry for all external learning sources.

    Users can:
      - Enable/disable built-in sources (arxiv, nature, github)
      - Add custom sources with their own queries
      - Define research directions for focused learning
      - Query across all enabled sources with direction filtering

    Sources are persisted to .livingtree/learning_sources.json.
    """

    def __init__(self):
        self._sources: dict[str, LearningSource] = {}
        self._directions: list[ResearchDirection] = list(DEFAULT_DIRECTIONS)
        self._loaded = False
        self._load()

    # ── Source Management ─────────────────────────────────────────

    def add_source(self, name: str, source_type: str = "custom",
                   **kwargs) -> LearningSource:
        """Add or update a learning source.

        Args:
            name: Unique source name (e.g. "nature", "my-custom-api").
            source_type: "arxiv", "nature", "github", or "custom".
            **kwargs: Any LearningSource field overrides.

        Returns:
            The created/updated LearningSource.
        """
        # Start from built-in preset if available
        preset = BUILTIN_SOURCES.get(name, {})
        config = {
            "name": name,
            "source_type": source_type,
            **preset,
            **kwargs,
        }
        source = LearningSource(**{k: v for k, v in config.items()
                                    if k in LearningSource.__dataclass_fields__})
        self._sources[name] = source
        self._save()
        logger.info(f"LearningSourceRegistry: added source '{name}' ({source_type})")
        return source

    def remove_source(self, name: str) -> bool:
        if name in self._sources:
            del self._sources[name]
            self._save()
            return True
        return False

    def enable_source(self, name: str) -> bool:
        source = self._sources.get(name)
        if source:
            source.enabled = True
            self._save()
            return True
        return False

    def disable_source(self, name: str) -> bool:
        source = self._sources.get(name)
        if source:
            source.enabled = False
            self._save()
            return True
        return False

    def get_source(self, name: str) -> LearningSource | None:
        return self._sources.get(name)

    def list_sources(self) -> list[LearningSource]:
        return list(self._sources.values())

    def list_enabled_sources(self) -> list[LearningSource]:
        return [s for s in self._sources.values() if s.enabled]

    # ── Direction Management ──────────────────────────────────────

    def add_direction(self, name: str, keywords: list[str] | None = None,
                      description: str = "", priority: int = 0) -> ResearchDirection:
        direction = ResearchDirection(
            name=name, keywords=keywords or [],
            description=description, priority=priority,
        )
        # Replace if exists
        for i, d in enumerate(self._directions):
            if d.name == name:
                self._directions[i] = direction
                self._save()
                return direction
        self._directions.append(direction)
        self._directions.sort(key=lambda d: -d.priority)
        self._save()
        return direction

    def remove_direction(self, name: str) -> bool:
        for i, d in enumerate(self._directions):
            if d.name == name:
                self._directions.pop(i)
                self._save()
                return True
        return False

    def list_directions(self) -> list[ResearchDirection]:
        return list(self._directions)

    def get_direction(self, name: str) -> ResearchDirection | None:
        for d in self._directions:
            if d.name == name:
                return d
        return None

    # ── Unified Search ────────────────────────────────────────────

    def get_search_queries(self, direction: str = "",
                           source_filter: list[str] | None = None) -> dict[str, list[str]]:
        """Get search queries for enabled sources, filtered by direction.

        Args:
            direction: Research direction name to filter by (keyword matching).
            source_filter: Only return queries for these source names.

        Returns:
            {source_name: [query_strings]} for all matching enabled sources.
        """
        result: dict[str, list[str]] = {}

        # Get direction keywords
        dir_keywords: list[str] = []
        if direction:
            d = self.get_direction(direction)
            if d:
                dir_keywords = d.keywords

        for source in self.list_enabled_sources():
            if source_filter and source.name not in source_filter:
                continue
            if not source.queries:
                continue
            result[source.name] = list(source.queries)
        return result

    def search_summary(self, direction: str = "") -> str:
        """Human-readable summary of what will be searched."""
        queries = self.get_search_queries(direction)
        if not queries:
            return "No enabled sources configured. Use add_source() to add sources."

        lines = ["## Active Learning Sources\n"]
        for source_name, qs in queries.items():
            source = self._sources.get(source_name)
            if source:
                lines.append(f"### {source_name} ({source.source_type})")
                lines.append(f"- URL: {source.base_url}")
                lines.append(f"- Queries: {len(qs)}")
                lines.append(f"- Refresh: every {source.refresh_hours}h")
                if source.journals:
                    lines.append(f"- Journals: {', '.join(source.journals[:5])}")
                lines.append("")
        if direction:
            d = self.get_direction(direction)
            if d:
                lines.append(f"### Direction: {d.name}")
                lines.append(f"Keywords: {', '.join(d.keywords)}")
        return "\n".join(lines)

    # ── Quick Setup ───────────────────────────────────────────────

    def setup_defaults(self) -> list[LearningSource]:
        """Initialize all built-in sources with defaults."""
        added = []
        for name in BUILTIN_SOURCES:
            if name not in self._sources:
                source = self.add_source(name)
                added.append(source)
        return added

    def setup_nature(self) -> LearningSource:
        """Quick setup for Nature.com learning source."""
        return self.add_source("nature")

    # ── Persistence ────────────────────────────────────────────────

    def _save(self) -> None:
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            data = {
                "sources": {
                    name: {
                        k: v for k, v in s.__dict__.items()
                        if not k.startswith("_")
                    }
                    for name, s in self._sources.items()
                },
                "directions": [
                    {
                        "name": d.name, "keywords": d.keywords,
                        "description": d.description, "priority": d.priority,
                    }
                    for d in self._directions
                ],
                "updated_at": time.time(),
            }
            SOURCES_CONFIG.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        except Exception as e:
            logger.debug(f"LearningSourceRegistry save: {e}")

    def _load(self) -> None:
        if self._loaded:
            return
        try:
            if SOURCES_CONFIG.exists():
                data = json.loads(SOURCES_CONFIG.read_text())
                for name, sd in data.get("sources", {}).items():
                    self._sources[name] = LearningSource(**sd)
                for dd in data.get("directions", []):
                    self._directions.append(ResearchDirection(**dd))
                # Merge with defaults (keep user-added directions)
                for dd in DEFAULT_DIRECTIONS:
                    if not any(d.name == dd.name for d in self._directions):
                        self._directions.append(dd)
                self._directions.sort(key=lambda d: -d.priority)
                logger.info(
                    f"LearningSourceRegistry: loaded {len(self._sources)} sources, "
                    f"{len(self._directions)} directions"
                )
        except Exception as e:
            logger.debug(f"LearningSourceRegistry load: {e}")
        self._loaded = True

    def save(self) -> None:
        self._save()

    def stats(self) -> dict[str, Any]:
        return {
            "total_sources": len(self._sources),
            "enabled_sources": len(self.list_enabled_sources()),
            "total_directions": len(self._directions),
            "sources": [
                {"name": s.name, "type": s.source_type, "enabled": s.enabled,
                 "queries": len(s.queries), "papers": s.paper_count}
                for s in self._sources.values()
            ],
            "directions": [
                {"name": d.name, "priority": d.priority, "keywords": len(d.keywords)}
                for d in self._directions
            ],
        }


# ═══ Singleton ═════════════════════════════════════════════════════

_registry: Optional[LearningSourceRegistry] = None


def get_learning_sources() -> LearningSourceRegistry:
    global _registry
    if _registry is None:
        _registry = LearningSourceRegistry()
    return _registry


__all__ = [
    "LearningSourceRegistry", "LearningSource", "ResearchDirection",
    "get_learning_sources",
]
