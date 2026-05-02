"""
LivingTree 统一技能系统
=======================

整合 skill_matcher + skill_clusterer + skill_discovery + skill_updater

Full migration from legacy agent_skills/ + skill_graph.py + skill_discovery.py +
skill_evolution/ core patterns.
"""

import hashlib
import importlib
import json
import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from threading import Lock
from typing import Any, Dict, List, Optional, Set, Tuple


class SkillStatus(Enum):
    REGISTERED = "registered"
    LOADED = "loaded"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    ERROR = "error"


@dataclass
class SkillInfo:
    name: str = ""
    description: str = ""
    category: str = "general"
    tags: List[str] = field(default_factory=list)
    capabilities: List[str] = field(default_factory=list)
    version: str = "1.0.0"
    author: str = ""
    config: Dict[str, Any] = field(default_factory=dict)
    entry_point: str = ""
    dependencies: List[str] = field(default_factory=list)
    status: str = "loaded"
    usage_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    avg_latency_ms: float = 0.0
    loaded_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def fingerprint(self) -> str:
        raw = f"{self.name}:{self.version}:{self.description}"
        return hashlib.md5(raw.encode()).hexdigest()[:8]

    @property
    def success_rate(self) -> float:
        total = self.success_count + self.failure_count
        if total == 0:
            return 1.0
        return self.success_count / total


class SkillRepository:
    """技能仓库 — 支持多维度索引和模糊搜索."""

    def __init__(self):
        self._skills: Dict[str, SkillInfo] = {}
        self._by_category: Dict[str, List[str]] = {}
        self._by_tag: Dict[str, List[str]] = {}
        self._by_capability: Dict[str, List[str]] = {}
        self._lock = Lock()

    def register(self, skill: SkillInfo):
        key = skill.fingerprint()
        with self._lock:
            existing = self._find_by_name(skill.name)
            if existing and existing != key:
                self._remove_index(existing)
            self._skills[key] = skill
            self._add_index(key, skill)

    def _find_by_name(self, name: str) -> Optional[str]:
        for key, sk in self._skills.items():
            if sk.name == name:
                return key
        return None

    def _add_index(self, key: str, skill: SkillInfo):
        cat = skill.category
        self._by_category.setdefault(cat, []).append(key)
        for tag in skill.tags:
            self._by_tag.setdefault(tag, []).append(key)
        for cap in skill.capabilities:
            self._by_capability.setdefault(cap, []).append(key)

    def _remove_index(self, key: str):
        for cat_list in self._by_category.values():
            if key in cat_list:
                cat_list.remove(key)
        for tag_list in self._by_tag.values():
            if key in tag_list:
                tag_list.remove(key)
        for cap_list in self._by_capability.values():
            if key in cap_list:
                cap_list.remove(key)

    def list_all(self) -> List[SkillInfo]:
        return list(self._skills.values())

    def list_by_category(self, category: str) -> List[SkillInfo]:
        keys = self._by_category.get(category, [])
        return [self._skills[k] for k in keys if k in self._skills]

    def list_by_tag(self, tag: str) -> List[SkillInfo]:
        keys = self._by_tag.get(tag, [])
        return [self._skills[k] for k in keys if k in self._skills]

    def list_by_capability(self, capability: str) -> List[SkillInfo]:
        keys = self._by_capability.get(capability, [])
        return [self._skills[k] for k in keys if k in self._skills]

    def get(self, name: str) -> Optional[SkillInfo]:
        for skill in self._skills.values():
            if skill.name == name:
                return skill
        return None

    def search(self, query: str) -> List[SkillInfo]:
        query_lower = query.lower()
        results: List[Tuple[SkillInfo, float]] = []
        for skill in self._skills.values():
            score = 0.0
            if query_lower in skill.name.lower():
                score += 2.0
            if query_lower in skill.description.lower():
                score += 1.0
            for tag in skill.tags:
                if query_lower in tag.lower():
                    score += 0.5
            if score > 0:
                results.append((skill, score))
        results.sort(key=lambda x: -x[1])
        return [s for s, _ in results]

    def count(self) -> int:
        return len(self._skills)

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            categories = {c: len(v) for c, v in self._by_category.items()}
            return {
                "total": len(self._skills),
                "categories": categories,
                "total_tags": len(self._by_tag),
                "total_capabilities": len(self._by_capability),
            }


class ContextQuery:
    def __init__(self, intent: str = "", entities: List[str] = None,
                 keywords: List[str] = None, required_capabilities: List[str] = None):
        self.intent = intent
        self.entities = entities or []
        self.keywords = keywords or []
        self.required_capabilities = required_capabilities or []


class SkillMatcher:
    """技能匹配器 — 多因子评分匹配."""

    def __init__(self, repo: Optional[SkillRepository] = None):
        self.repo = repo or SkillRepository()
        self._intent_skill_map: Dict[str, List[str]] = {
            "writing": ["writing_assistant", "content_generator", "report_builder",
                        "document_formatter", "style_checker"],
            "code": ["code_assistant", "debug_helper", "refactor_assistant",
                     "code_reviewer", "test_generator"],
            "search": ["web_search", "knowledge_search", "deep_research",
                       "fact_checker", "source_validator"],
            "analysis": ["data_analyzer", "report_analyzer", "insight_extractor",
                         "trend_analyzer", "pattern_recognizer"],
            "automation": ["task_automator", "batch_processor", "scheduler",
                           "workflow_orchestrator", "cron_manager"],
            "chat": ["conversation_assistant", "summarizer", "translator"],
        }
        self._scoring_weights = {
            "intent_match": 3.0,
            "keyword_match": 1.5,
            "tag_match": 1.0,
            "capability_match": 2.0,
            "success_rate": 0.5,
        }

    def match(self, intent: str, query: Optional[ContextQuery] = None) -> List[SkillInfo]:
        candidates = self._intent_skill_map.get(intent, [])
        scored: List[Tuple[SkillInfo, float]] = []

        for skill in self.repo.list_all():
            score = 0.0

            if skill.name in candidates:
                score += self._scoring_weights["intent_match"]

            if query:
                all_keywords = query.keywords + query.entities
                if all_keywords:
                    text_pool = (skill.name + " " + skill.description + " "
                                 + " ".join(skill.tags)).lower()
                    kw_matches = sum(1 for kw in all_keywords
                                     if kw.lower() in text_pool)
                    score += kw_matches * self._scoring_weights["keyword_match"]

                for kw in all_keywords:
                    for tag in skill.tags:
                        if kw.lower() in tag.lower():
                            score += self._scoring_weights["tag_match"]
                            break

                for req_cap in query.required_capabilities:
                    for cap in skill.capabilities:
                        if req_cap.lower() in cap.lower():
                            score += self._scoring_weights["capability_match"]
                            break

            score += skill.success_rate * self._scoring_weights["success_rate"]

            if score > 0:
                scored.append((skill, score))

        scored.sort(key=lambda x: -x[1])

        result = []
        for skill, score in scored:
            skill.config["_match_score"] = score
            result.append(skill)

        return result

    def best_match(self, intent: str,
                   query: Optional[ContextQuery] = None) -> Optional[SkillInfo]:
        matches = self.match(intent, query)
        return matches[0] if matches else None

    def record_result(self, skill_name: str, success: bool,
                      latency_ms: float = 0.0):
        skill = self.repo.get(skill_name)
        if not skill:
            return
        skill.usage_count += 1
        if success:
            skill.success_count += 1
        else:
            skill.failure_count += 1
        if skill.avg_latency_ms == 0:
            skill.avg_latency_ms = latency_ms
        else:
            skill.avg_latency_ms = skill.avg_latency_ms * 0.8 + latency_ms * 0.2

    @property
    def scoring_weights(self) -> Dict[str, float]:
        return dict(self._scoring_weights)

    def set_weight(self, key: str, value: float):
        self._scoring_weights[key] = value


class SkillDependencyGraph:
    """技能依赖图 — 拓扑排序解析."""

    def __init__(self, repo: SkillRepository):
        self.repo = repo
        self._graph: Dict[str, List[str]] = {}
        self._reverse: Dict[str, List[str]] = {}
        self._build()

    def _build(self):
        self._graph.clear()
        self._reverse.clear()
        for skill in self.repo.list_all():
            self._graph.setdefault(skill.name, [])
            for dep in skill.dependencies:
                self._graph.setdefault(skill.name, []).append(dep)
                self._reverse.setdefault(dep, []).append(skill.name)

    def resolve_order(self, skill_names: List[str]) -> List[str]:
        """拓扑排序 — 解析技能加载顺序."""
        in_degree: Dict[str, int] = {}
        all_nodes: Set[str] = set()

        for name in skill_names:
            q = [name]
            visited = set()
            while q:
                node = q.pop()
                if node in visited:
                    continue
                visited.add(node)
                all_nodes.add(node)
                for dep in self._graph.get(node, []):
                    q.append(dep)

        for node in all_nodes:
            in_degree[node] = 0
        for node in all_nodes:
            for dep in self._graph.get(node, []):
                in_degree[node] = in_degree.get(node, 0) + 1

        queue = [n for n, d in in_degree.items() if d == 0]
        result = []

        while queue:
            node = queue.pop(0)
            result.append(node)
            for dependent in self._reverse.get(node, []):
                if dependent in in_degree:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)

        return result

    def missing_dependencies(self, skill_names: List[str]) -> List[str]:
        """检查缺失的依赖."""
        missing = []
        for name in skill_names:
            for dep in self._graph.get(name, []):
                if not self.repo.get(dep):
                    missing.append(dep)
        return missing

    def what_depends_on(self, skill_name: str) -> List[str]:
        return self._reverse.get(skill_name, [])


class SkillUpdater:
    """技能更新器 — 版本检查和热更新."""

    def __init__(self, repo: Optional[SkillRepository] = None):
        self.repo = repo or SkillRepository()
        self._update_log: List[Dict[str, Any]] = []

    def check_updates(self, remote_versions: Dict[str, str]) -> List[Tuple[SkillInfo, str]]:
        """检查是否有可用更新."""
        updates = []
        for name, remote_version in remote_versions.items():
            skill = self.repo.get(name)
            if skill and skill.version != remote_version:
                updates.append((skill, remote_version))
        return updates

    def update_skill(self, skill_name: str, updates: Dict[str, Any]):
        skill = self.repo.get(skill_name)
        if not skill:
            return
        for key, value in updates.items():
            if hasattr(skill, key):
                setattr(skill, key, value)
        skill.updated_at = datetime.now()
        self._update_log.append({
            "skill": skill_name, "updates": updates,
            "timestamp": datetime.now().isoformat(),
        })

    def deprecate(self, skill_name: str, replacement: str = ""):
        skill = self.repo.get(skill_name)
        if skill:
            skill.status = "deprecated"
            skill.config["deprecation_replacement"] = replacement

    def get_update_log(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self._update_log[-limit:]


class SkillLoader:
    """技能加载器 — 支持从 dict/json 加载."""

    def __init__(self, repo: Optional[SkillRepository] = None):
        self.repo = repo or SkillRepository()

    def load_from_dict(self, data: Dict[str, Any]) -> SkillInfo:
        skill = SkillInfo(
            name=data.get("name", "unknown"),
            description=data.get("description", ""),
            category=data.get("category", "general"),
            tags=data.get("tags", []),
            capabilities=data.get("capabilities", []),
            version=data.get("version", "1.0.0"),
            author=data.get("author", ""),
            config=data.get("config", {}),
            entry_point=data.get("entry_point", ""),
            dependencies=data.get("dependencies", []),
        )
        self.repo.register(skill)
        return skill

    def load_from_json(self, path: str) -> SkillInfo:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return self.load_from_dict(data)

    def load_default_skills(self):
        defaults = [
            SkillInfo(name="writing_assistant", category="writing",
                      description="帮助撰写各类文档和报告",
                      tags=["writing", "document", "report"],
                      capabilities=["generate_text", "format_document", "proofread"]),
            SkillInfo(name="code_assistant", category="code",
                      description="帮助编写和调试代码",
                      tags=["code", "debug", "refactor"],
                      capabilities=["generate_code", "debug_code", "review_code"]),
            SkillInfo(name="web_search", category="search",
                      description="网络搜索和信息检索",
                      tags=["search", "web", "knowledge"],
                      capabilities=["search_web", "summarize_results", "cite_sources"]),
            SkillInfo(name="data_analyzer", category="analysis",
                      description="数据分析和报告生成",
                      tags=["analysis", "data", "report"],
                      capabilities=["analyze_data", "generate_charts", "find_insights"]),
            SkillInfo(name="task_automator", category="automation",
                      description="任务自动化和批量处理",
                      tags=["automation", "batch", "scheduler"],
                      capabilities=["execute_task", "schedule_job", "monitor_progress"]),
            SkillInfo(name="conversation_assistant", category="chat",
                      description="通用对话助手",
                      tags=["chat", "conversation", "assistant"],
                      capabilities=["chat", "answer_question", "engage_user"]),
        ]
        for skill in defaults:
            self.repo.register(skill)


__all__ = [
    "SkillInfo",
    "SkillRepository",
    "SkillMatcher",
    "SkillLoader",
    "SkillDependencyGraph",
    "SkillUpdater",
    "ContextQuery",
    "SkillStatus",
]
