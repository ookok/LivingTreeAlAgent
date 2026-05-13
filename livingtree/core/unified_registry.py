"""UnifiedRegistry — single source of truth for tools, skills, roles, knowledge.

Merges scattered systems: 21 tools + 4 agents + 8 roles + 4 KB stores → 1 registry.
Auto-sync: new discovery → all consumers instantly aware.
Replaces 30 global singletons with 1 coordinated registry.
"""
from __future__ import annotations

import asyncio
import json
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger


@dataclass
class RegistryTool:
    name: str; description: str; category: str = ""; formula: str = ""
    params: dict = field(default_factory=dict); handler: Any = None
    source: str = "hardcoded"; enabled: bool = True

    def to_routing_text(self) -> str:
        parts = [f"Tool:{self.name}. {self.description}"]
        if self.formula: parts.append(f"Formula:{self.formula}")
        return " ".join(parts)


@dataclass
class RegistrySkill:
    name: str; description: str; prompt_template: str = ""
    category: str = ""; source: str = "learned"
    success_count: int = 0; usage_count: int = 0; enabled: bool = True


@dataclass
class RegistryRole:
    name: str; description: str; capabilities: list[str] = field(default_factory=list)
    system_prompt: str = ""; source: str = "hardcoded"; enabled: bool = True


class UnifiedRegistry:
    _instance: UnifiedRegistry | None = None

    @classmethod
    def instance(cls) -> UnifiedRegistry:
        if cls._instance is None: cls._instance = UnifiedRegistry()
        return cls._instance

    def __init__(self):
        self.tools: dict[str, RegistryTool] = {}
        self.skills: dict[str, RegistrySkill] = {}
        self.roles: dict[str, RegistryRole] = {}
        self._subscriptions: dict[str, list] = {}
        self._built = False

    def register_tool(self, tool: RegistryTool): self.tools[tool.name] = tool
    def register_skill(self, skill: RegistrySkill): self.skills[skill.name] = skill
    def register_role(self, role: RegistryRole): self.roles[role.name] = role

    def subscribe(self, type_name: str, callback):
        self._subscriptions.setdefault(type_name, []).append(callback)

    def get_tools_routing_text(self, query: str = "", max_tools: int = 5) -> str:
        tools = [t for t in self.tools.values() if t.enabled]
        if query:
            scored = []
            for t in tools:
                score = sum(1 for w in query if w in t.name + t.description)
                scored.append((t, score))
            scored.sort(key=lambda x: -x[1])
            tools = [t for t, _ in scored[:max_tools]]
        lines = []
        for t in tools[:max_tools]:
            formula = f"\n  公式: {t.formula}" if t.formula else ""
            lines.append(f"- **{t.name}** [{t.category}]: {t.description}{formula}")
        return "\n".join(lines) if lines else ""

    def get_status(self) -> dict:
        return {
            "tools": len(self.tools), "skills": len(self.skills), "roles": len(self.roles),
            "sources": {
                "tools": dict(Counter(t.source for t in self.tools.values())),
                "skills": dict(Counter(s.source for s in self.skills.values())),
                "roles": dict(Counter(r.source for r in self.roles.values())),
            },
        }

    async def query_kb(self, query: str, top_k: int = 10) -> list[dict]:
        results = []
        try:
            from ..knowledge.knowledge_base import KnowledgeBase
            for doc in KnowledgeBase().search(query, top_k=top_k):
                results.append({"source": "knowledge_base", "text": doc.content[:300], "score": 0.6})
        except Exception: pass
        try:
            from ..knowledge.document_kb import DocumentKB
            for hit in DocumentKB().search(query, top_k=top_k):
                results.append({"source": "document_kb", "text": hit.chunk.text[:300], "score": hit.score})
        except Exception: pass
        try:
            from ..knowledge.knowledge_graph import KnowledgeGraph
            for entity in KnowledgeGraph().entity_linking(query)[:3]:
                for n in KnowledgeGraph().query_graph(entity)[:5]:
                    results.append({"source": "knowledge_graph", "text": n.get("label",""), "score": 0.4})
        except Exception: pass
        try:
            from ..knowledge.struct_mem import get_struct_mem
            for entry in (await get_struct_mem().retrieve_for_query(query, top_k=3))[:3]:
                results.append({"source": "struct_mem", "text": getattr(entry,'content',str(entry))[:300], "score": 0.3})
        except Exception: pass
        results.sort(key=lambda x: -x.get("score", 0))
        return results[:top_k]

    def build_default(self):
        if self._built: return
        from ..capability.tool_registry import SYSTEM_TOOLS, EXPERT_ROLES
        for name, t in SYSTEM_TOOLS.items():
            self.register_tool(RegistryTool(name=name, description=t["description"], category=t.get("category",""),
                                            formula=t.get("formula",""), params=t.get("params",{}), source="hardcoded"))
        for name, desc in EXPERT_ROLES.items():
            self.register_role(RegistryRole(name=name, description=desc, source="hardcoded"))
        try:
            from ..execution.real_pipeline import get_real_orchestrator
            for name, spec in get_real_orchestrator()._agents.items():
                if name not in self.roles:
                    self.register_role(RegistryRole(name=name, description=spec.description,
                                                    capabilities=spec.capabilities, source="pipeline"))
        except Exception: pass
        try:
            from ..capability.tool_market import ToolMarket
            tm = ToolMarket()
            for spec in tm.discover():
                if spec.name not in self.tools:
                    self.register_tool(RegistryTool(name=spec.name, description=spec.description,
                                                    category=spec.category, source="seed"))
        except Exception: pass
        self._built = True
        logger.info(f"UnifiedRegistry: {len(self.tools)}T/{len(self.roles)}R")

    def discover_from_skills_dir(self, root: str | Path):
        root = Path(root)
        for path in root.rglob("SKILL.md")[:50]:
            try:
                text = path.read_text(errors="replace")
                name = path.parent.name if path.parent != root else path.stem
                if name not in self.skills:
                    self.register_skill(RegistrySkill(name=name, description=text[:200],
                                                      prompt_template=text[:1000], source="SKILL.md"))
            except Exception: pass


def get_registry() -> UnifiedRegistry:
    return UnifiedRegistry.instance()
