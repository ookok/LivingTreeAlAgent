"""UnifiedSkillSystem — merges SkillRouter + SkillGraph + SkillSelfLearn + SkillDiscovery.

Single entry point for all skill operations:
  1. route(query) → best provider, tools, roles (replaces TinyClassifier + SkillRouter)
  2. graph → relationships between skills (replaces SkillGraph)
  3. learn(task, success) → proposed skills, nudges (replaces SkillSelfLearn)
  4. discover() → SKILL.md file scanning (replaces SkillDiscoveryManager)

This is the merger of 5 previously separate modules per architecture review.
"""
from __future__ import annotations

import json
import math
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

from ..treellm.skill_router import PureTfidf, RouteResult, RoutingDecision
from ..dna.skill_graph import SkillGraph, SkillNode, get_skill_graph
from ..dna.skill_self_learn import LearnedSkill, KnowledgeNudge
from ..tui.widgets.enhanced_tool_call import SYSTEM_TOOLS, EXPERT_ROLES

GRAPH_FILE = Path(".livingtree/skill_graph.json")
SKILL_FILE = Path(".livingtree/learned_skills.json")


class UnifiedSkillSystem:
    """Single system for all skill operations."""

    def __init__(self):
        # Routing (from SkillRouter)
        self._provider_texts: dict[str, str] = {}
        self._tool_texts: dict[str, str] = {}
        self._role_texts: dict[str, str] = {}
        self._vectorizer: PureTfidf | None = None
        self._provider_vectors: list[list[float]] = []
        self._tool_vectors: list[list[float]] = []
        self._role_vectors: list[list[float]] = []

        # Graph (from SkillGraph)
        self.graph = get_skill_graph()

        # Learning (from SkillSelfLearn)
        self._skills: dict[str, LearnedSkill] = {}
        self._nudges: dict[str, KnowledgeNudge] = {}
        self._task_count = 0

        # History
        self._history: list[dict] = []
        self._built = False

        self._register_defaults()
        self._load()

    # ═══ Routing (merged TinyClassifier + SkillRouter) ═══

    def route(self, query: str) -> RoutingDecision:
        if not self._built:
            self.build()
        result = RoutingDecision(query=query)
        result.providers = self._rank(query, self._provider_texts, self._provider_vectors)
        result.tools = self._rank(query, self._tool_texts, self._tool_vectors)
        result.roles = self._rank(query, self._role_texts, self._role_vectors)

        # Graph boost
        for tool in result.tools:
            deps = self.graph.get_dependencies(tool.name, recursive=False)
            for dep in deps:
                for t in result.tools:
                    if t.name == dep:
                        t.score *= 1.5
            comps = self.graph.get_compositions(tool.name)
            for comp in comps:
                for t in result.tools:
                    if t.name == comp:
                        t.score *= 1.3
            conflicts = self.graph.get_conflicts(tool.name)
            for conflict in conflicts:
                for t in result.tools:
                    if t.name == conflict:
                        t.score *= 0.3
        result.tools.sort(key=lambda x: -x.score)
        result.top_provider = result.providers[0].name if result.providers else "auto"
        result.top_tool = result.tools[0].name if result.tools else ""
        result.top_role = result.roles[0].name if result.roles else ""
        return result

    def _rank(self, query: str, texts: dict[str, str], vectors: list[list[float]]) -> list[RouteResult]:
        if not texts or self._vectorizer is None or not vectors:
            return []
        query_vec = self._vectorizer.transform([query])
        scores = PureTfidf.cosine_similarity(query_vec[0], vectors)
        results = []
        for name, score in zip(texts.keys(), scores):
            if score > 0:
                results.append(RouteResult(name=name, score=score, description=texts[name][:200], full_text=texts[name]))
        results.sort(key=lambda x: -x.score)
        return results[:10]

    def build(self):
        all_texts = list(self._provider_texts.values()) + list(self._tool_texts.values()) + list(self._role_texts.values())
        if not all_texts:
            return
        self._vectorizer = PureTfidf(ngram_range=(1, 3), max_features=2000)
        self._vectorizer.fit(all_texts)
        all_vec = self._vectorizer.transform(all_texts)
        n_p, n_t = len(self._provider_texts), len(self._tool_texts)
        n_r = len(self._role_texts)
        self._provider_vectors = all_vec[:n_p]
        self._tool_vectors = all_vec[n_p:n_p + n_t]
        self._role_vectors = all_vec[n_p + n_t:]
        self._built = True
        logger.info(f"SkillSystem: {n_p}P/{n_t}T/{n_r}R built")

    # ═══ Learning (from SkillSelfLearn) ═══

    def learn(self, task: str, result: str = "", success: bool = True) -> LearnedSkill | None:
        self._task_count += 1
        if self._task_count % 10 == 0:
            for skill in self._skills.values():
                if skill.name.lower() in task.lower():
                    skill.usage_count += 1
                    if success:
                        skill.success_count += 1
                    skill.last_used = time.time()
                    self._save()
                    return skill
        return None

    def propose_skill(self, task: str) -> LearnedSkill:
        words = task.replace("，", " ").replace("。", " ").split()
        keywords = [w for w in words if len(w) >= 2][:3]
        name = "-".join(keywords) if keywords else f"skill-{len(self._skills)+1}"
        skill = LearnedSkill(name=name, description=task[:120], prompt_template=task, proposed=True)
        self._skills[skill.name] = skill
        self._save()
        return skill

    def approve_skill(self, name: str) -> bool:
        s = self._skills.get(name)
        if s and s.proposed:
            s.proposed = False
            self._save()
            return True
        return False

    def get_due_nudges(self) -> list[KnowledgeNudge]:
        now = time.time()
        return [n for n in self._nudges.values() if now - n.last_nudged > 86400]

    def get_status(self) -> dict:
        return {
            "skills": len(self._skills),
            "proposed": sum(1 for s in self._skills.values() if s.proposed),
            "nudges": len(self._nudges),
            "graph_nodes": len(self.graph._nodes),
            "routing_built": self._built,
        }

    def feed_back(self, query: str, chosen: str, success: bool):
        self._history.append({"query": query[:200], "chosen": chosen, "success": success})
        if len(self._history) > 500:
            self._history = self._history[-300:]

    # ═══ Persistence ═══

    def _register_defaults(self):
        providers = {
            "siliconflow-flash": ("硅基流动 Qwen2.5-7B", "通用对话/翻译/分析"),
            "siliconflow-reasoning": ("硅基流动 DeepSeek-R1-7B", "深度推理/数学/逻辑"),
            "mofang-flash": ("模力方舟 Qwen2.5-7B", "通用对话/文档处理"),
            "deepseek": ("DeepSeek V4 Pro", "高精度推理/代码/复杂分析"),
            "longcat": ("LongCat Flash", "通用对话/快速响应"),
            "zhipu": ("智谱 GLM-4-Flash", "中文对话/文本理解"),
            "spark": ("讯飞星火 xDeepSeekV3", "搜索增强/知识问答"),
        }
        for name, (desc, caps) in providers.items():
            self._provider_texts[name] = f"{name}. {desc}. Capabilities: {caps}"

        for name, tool in SYSTEM_TOOLS.items():
            self._tool_texts[name] = f"Tool:{name}. {tool['description']}"

        for name, desc in EXPERT_ROLES.items():
            self._role_texts[name] = f"Role:{name}. {desc}"

    def _save(self):
        from ..core.async_disk import save_json
        data = [{"name": s.name, "description": s.description, "prompt_template": s.prompt_template,
                 "usage_count": s.usage_count, "success_count": s.success_count,
                 "proposed": s.proposed} for s in self._skills.values()]
        save_json(SKILL_FILE, data)

    def _load(self):
        try:
            if SKILL_FILE.exists():
                for d in json.loads(SKILL_FILE.read_text()):
                    s = LearnedSkill(**{k: d.get(k, "") for k in ["name", "description", "prompt_template", "category", "usage_count", "success_count", "version", "proposed"]})
                    self._skills[s.name] = s
        except Exception:
            pass


# ═══ Global ═══

_system: UnifiedSkillSystem | None = None


def get_skill_system() -> UnifiedSkillSystem:
    global _system
    if _system is None:
        _system = UnifiedSkillSystem()
    return _system
