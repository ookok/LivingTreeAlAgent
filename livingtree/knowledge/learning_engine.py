"""LearningEngine — Meta-learning for self-evolving systems.

Replaces hardcoded templates with learned knowledge:
- TemplateLearner: dynamically generates task templates from KB + Distillation
- SkillDiscoverer: auto-discovers tools from codebase via Phage AST
- RoleGenerator: generates agent roles from task descriptions
- PatternExtractor: extracts reusable patterns from successful executions

All knowledge is stored in KnowledgeBase for future recall.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from loguru import logger


@dataclass
class LearnedTemplate:
    """A task template learned from experience or Distillation."""
    domain: str
    sections: list[str]
    source: str  # "distillation", "execution", "format_discovery", "kb_merge"
    learned_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    success_rate: float = 0.0
    use_count: int = 0

    def to_plan_steps(self) -> list[dict[str, Any]]:
        return [
            {"name": section, "action": "execute", "roles": ["analyst"],
             "description": f"Learned from {self.source}"}
            for section in self.sections
        ]


class TemplateLearner:
    """Learns task templates through Distillation + KB + successful executions.

    No hardcoded templates. Every template is either:
    1. Distilled from expert model on first use
    2. Extracted from existing documents via FormatDiscovery
    3. Merged from similar previously-learned templates in KB
    4. Cached after learning for fast recall
    """

    def __init__(self, kb: Any = None, distillation: Any = None, expert_config: Any = None):
        self.kb = kb
        self.distillation = distillation
        self.expert_config = expert_config
        self._cache: dict[str, LearnedTemplate] = {}
        self._load_cache()

    async def get_template(self, domain: str, goal: str = "") -> list[dict[str, Any]]:
        """Get or learn a task template for a domain.

        Priority:
        1. Cached (already learned)
        2. From KnowledgeBase (previously stored)
        3. From Distillation (ask expert model)
        4. From FormatDiscovery (scan documents)
        5. Merge similar domains
        6. Minimal fallback
        """
        # 1. Cache hit
        if domain in self._cache:
            tpl = self._cache[domain]
            tpl.use_count += 1
            return tpl.to_plan_steps()

        # 2. KB lookup
        if self.kb:
            try:
                kb_results = self.kb.search(f"template {domain} sections", top_k=3)
                for doc in kb_results:
                    if "sections" in doc.metadata:
                        tpl = LearnedTemplate(
                            domain=domain, sections=doc.metadata["sections"],
                            source="kb_retrieval",
                        )
                        self._cache[domain] = tpl
                        return tpl.to_plan_steps()
            except Exception:
                pass

        # 3. Distillation
        tpl = await self._learn_from_expert(domain, goal)
        if tpl and tpl.sections:
            self._cache[domain] = tpl
            self._save(tpl)
            return tpl.to_plan_steps()

        # 4. FormatDiscovery scan
        if self.kb:
            tpl = await self._learn_from_documents(domain)
            if tpl and tpl.sections:
                self._cache[domain] = tpl
                self._save(tpl)
                return tpl.to_plan_steps()

        # 5. Merge similar
        tpl = self._merge_similar(domain)
        if tpl and tpl.sections:
            self._cache[domain] = tpl
            return tpl.to_plan_steps()

        # 6. Minimal
        return [{"name": f"Execute: {goal or domain}", "action": "execute",
                 "description": f"Handle {domain} task"}]

    async def _learn_from_expert(self, domain: str, goal: str) -> Optional[LearnedTemplate]:
        if not self.distillation or not self.expert_config:
            return None
        try:
            prompt = (
                f"For a '{domain}' task{f' ({goal})' if goal else ''}, "
                f"what are the standard steps and sections?\n"
                f"Return exactly: a JSON array of step names, one per line.\n"
                f'Example: ["总论","工程分析","环境现状","结论"]'
            )
            response = await self.distillation.query_expert(prompt, self.expert_config)
            import json, re
            match = re.search(r'\[.*?\]', response, re.DOTALL)
            if match:
                sections = json.loads(match.group())
                return LearnedTemplate(domain=domain, sections=sections, source="distillation")
        except Exception as e:
            logger.debug(f"Template distillation failed: {e}")
        return None

    async def _learn_from_documents(self, domain: str) -> Optional[LearnedTemplate]:
        if not self.kb:
            return None
        try:
            docs = self.kb.search(domain, top_k=10, as_of=datetime.utcnow())
            headings: set[str] = set()
            for doc in docs:
                for line in doc.content.split("\n"):
                    line = line.strip()
                    if line.startswith("#") or (line and line[0].isdigit() and len(line) > 3):
                        headings.add(line.lstrip("#0123456789. ").strip()[:80])
            if len(headings) >= 3:
                return LearnedTemplate(
                    domain=domain, sections=sorted(headings)[:20],
                    source="format_discovery",
                )
        except Exception:
            pass
        return None

    def _merge_similar(self, domain: str) -> Optional[LearnedTemplate]:
        """Merge sections from similar domains in cache."""
        merged: list[str] = []
        for key, tpl in self._cache.items():
            if any(word in key for word in domain.split()) or any(word in domain for word in key.split()):
                for s in tpl.sections:
                    if s not in merged:
                        merged.append(s)
        if len(merged) >= 3:
            return LearnedTemplate(domain=domain, sections=merged, source="merge")
        return None

    def record_success(self, domain: str, success_rate: float) -> None:
        """Update template success rate after execution."""
        if domain in self._cache:
            self._cache[domain].success_rate = success_rate

    def _save(self, tpl: LearnedTemplate) -> None:
        if self.kb:
            try:
                from ..knowledge.knowledge_base import Document
                doc = Document(
                    title=f"template:{tpl.domain}",
                    content="\n".join(tpl.sections),
                    domain=tpl.domain,
                    metadata={"sections": tpl.sections, "source": tpl.source},
                    source="template_learner",
                )
                self.kb.add_knowledge(doc)
            except Exception:
                pass

    def _load_cache(self) -> None:
        if not self.kb:
            return
        try:
            for doc in self.kb.search("template:", top_k=50):
                if "sections" in doc.metadata:
                    domain = doc.metadata.get("domain", doc.domain)
                    if domain:
                        self._cache[domain] = LearnedTemplate(
                            domain=domain,
                            sections=doc.metadata["sections"],
                            source="kb_load",
                        )
        except Exception:
            pass


class SkillDiscoverer:
    """Auto-discovers tools from codebase and skills.

    No hardcoded tool list. Tools are discovered:
    1. From Phage AST scan of the codebase
    2. From SkillFactory registered skills
    3. From KnowledgeBase (previously discovered)
    """

    def __init__(self, phage: Any = None, skill_factory: Any = None, ast_parser: Any = None, kb: Any = None):
        self.phage = phage
        self.skill_factory = skill_factory
        self.ast_parser = ast_parser
        self.kb = kb
        self._discovered: dict[str, Any] = {}

    async def discover(self, codebase_path: str = ".") -> dict[str, Any]:
        """Discover all available tools from all sources."""
        tools: dict[str, Any] = {}

        # From SkillFactory
        if self.skill_factory:
            for name in self.skill_factory.discover_skills():
                tools[name] = {"name": name, "type": "skill", "source": "skill_factory"}

        # From Phage AST scan
        if self.phage and self.ast_parser:
            try:
                scan = await self.phage.scan_directory(codebase_path)
                for func_name in scan.get("top_functions", [])[:20]:
                    name = func_name.get("name", "")
                    if name and name not in tools:
                        tools[name] = {
                            "name": name, "type": "function",
                            "source": "phage_scan",
                            "file": func_name.get("file", ""),
                            "connections": func_name.get("connections", 0),
                        }
            except Exception:
                pass

        # From KB
        if self.kb:
            try:
                kb_tools = self.kb.search("tool:function", top_k=50)
                for doc in kb_tools:
                    name = doc.metadata.get("name", doc.title)
                    if name and name not in tools:
                        tools[name] = {
                            "name": name, "type": "kb_learned",
                            "source": "knowledge_base",
                        }
            except Exception:
                pass

        self._discovered = tools
        return tools

    def get_tool(self, name: str) -> Optional[dict]:
        return self._discovered.get(name)


class RoleGenerator:
    """Generates agent roles dynamically from task descriptions.

    No hardcoded role list. Roles are:
    1. Generated via Distillation for the domain
    2. Merged from similar domains
    3. Cached for reuse
    """

    def __init__(self, distillation: Any = None, expert_config: Any = None, kb: Any = None):
        self.distillation = distillation
        self.expert_config = expert_config
        self.kb = kb
        self._cache: dict[str, list[dict]] = {}

    async def generate_roles(self, domain: str, task_description: str = "") -> list[dict[str, Any]]:
        """Generate appropriate agent roles for a domain task."""
        if domain in self._cache:
            return self._cache[domain]

        if self.distillation and self.expert_config:
            try:
                prompt = (
                    f"For a '{domain}' task, what specialized agent roles are needed?\n"
                    'Return JSON array: [{"name":"role_name","capabilities":["cap1","cap2"]},...]\n'
                    "Use brief English role names."
                )
                response = await self.distillation.query_expert(prompt, self.expert_config)
                import json, re
                match = re.search(r'\[.*?\]', response, re.DOTALL)
                if match:
                    roles = json.loads(match.group())
                    self._cache[domain] = roles
                    return roles
            except Exception:
                pass

        # Generic fallback
        roles = [
            {"name": "analyst", "capabilities": ["analysis", "reasoning"]},
            {"name": "executor", "capabilities": ["execution", "tool_use"]},
        ]
        self._cache[domain] = roles
        return roles
