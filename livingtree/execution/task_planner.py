"""TaskPlanner — Intelligent task decomposition with chain-of-thought planning.

Decomposes complex goals into executable sub-tasks with dependencies,
resource estimates, and domain-aware splitting strategies.

LDR-inspired Research Strategy Taxonomy: matches task intent to optimal
strategy (quick fact, detailed research, report generation, etc.).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from loguru import logger
from pydantic import BaseModel, Field


class SubTask(BaseModel):
    """A single executable sub-task in a plan."""
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    name: str
    description: str = ""
    action: str = "execute"
    agent_roles: list[str] = Field(default_factory=lambda: ["general"])
    dependencies: list[str] = Field(default_factory=list)
    estimated_duration: float = 60.0
    retry_count: int = 0
    max_retries: int = 3
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    status: str = "pending"
    result: Any = None
    needs_approval: bool = False
    approval_question: str = ""
    needs_deep_reasoning: bool = False

    def mark_completed(self, result: Any = None) -> None:
        self.status = "completed"
        self.result = result

    def mark_failed(self, error: str = "") -> None:
        self.status = "failed"
        self.result = {"error": error}

    def mark_running(self) -> None:
        self.status = "running"


class TaskSpec(BaseModel):
    """Full task specification with decomposed plan."""
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    goal: str
    domain: str = "general"
    sub_tasks: list[SubTask] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)
    total_estimated_duration: float = 0.0
    progress: float = 0.0
    status: str = "pending"

    def get_ready_tasks(self) -> list[SubTask]:
        """Get tasks whose dependencies are all completed."""
        completed = {t.id for t in self.sub_tasks if t.status == "completed"}
        return [
            t for t in self.sub_tasks
            if t.status == "pending"
            and all(dep in completed for dep in t.dependencies)
        ]

    def update_progress(self) -> None:
        total = len(self.sub_tasks)
        if total == 0:
            self.progress = 1.0
            return
        completed = sum(1 for t in self.sub_tasks if t.status == "completed")
        failed = sum(1 for t in self.sub_tasks if t.status == "failed")
        self.progress = (completed + failed) / total
        if self.progress >= 1.0:
            self.status = "completed" if failed == 0 else "partial"


# ═══ LDR-inspired Research Strategy Taxonomy ═══


class ResearchStrategy(str, Enum):
    """LDR-inspired: 20+ research strategies mapped to LivingTree domains.

    Each strategy specifies: search depth, parallelism, source priority,
    and expected output format. Matched to task intent via keyword analysis.
    """
    QUICK_FACT = "quick_fact"
    LOOKUP_STANDARD = "lookup_standard"
    DETAILED_RESEARCH = "detailed_research"
    REPORT_GENERATION = "report_generation"
    CODE_ANALYSIS = "code_analysis"
    DATA_ANALYSIS = "data_analysis"
    COMPLIANCE_CHECK = "compliance_check"
    COMPARATIVE = "comparative"
    LITERATURE_REVIEW = "literature_review"
    EXPLORATORY = "exploratory"


@dataclass
class StrategyConfig:
    strategy: ResearchStrategy
    search_depth: int
    parallel_search: bool
    max_sources: int
    source_priority: list[str]
    needs_knowledge_base: bool
    needs_web_search: bool
    expected_duration: float
    output_format: str


STRATEGY_CONFIGS: dict[ResearchStrategy, StrategyConfig] = {
    ResearchStrategy.QUICK_FACT: StrategyConfig(
        strategy=ResearchStrategy.QUICK_FACT,
        search_depth=1, parallel_search=False, max_sources=3,
        source_priority=["engram", "fts5"], needs_knowledge_base=True,
        needs_web_search=False, expected_duration=5.0,
        output_format="简短答案+来源引用",
    ),
    ResearchStrategy.LOOKUP_STANDARD: StrategyConfig(
        strategy=ResearchStrategy.LOOKUP_STANDARD,
        search_depth=1, parallel_search=False, max_sources=2,
        source_priority=["engram"], needs_knowledge_base=True,
        needs_web_search=False, expected_duration=3.0,
        output_format="标准+数值",
    ),
    ResearchStrategy.DETAILED_RESEARCH: StrategyConfig(
        strategy=ResearchStrategy.DETAILED_RESEARCH,
        search_depth=3, parallel_search=True, max_sources=15,
        source_priority=["engram", "fts5", "vector", "web"],
        needs_knowledge_base=True, needs_web_search=True,
        expected_duration=120.0,
        output_format="结构化分析+多源引证",
    ),
    ResearchStrategy.REPORT_GENERATION: StrategyConfig(
        strategy=ResearchStrategy.REPORT_GENERATION,
        search_depth=4, parallel_search=True, max_sources=20,
        source_priority=["engram", "fts5", "vector", "web", "graph"],
        needs_knowledge_base=True, needs_web_search=True,
        expected_duration=300.0,
        output_format="完整报告+目录+参考文献",
    ),
    ResearchStrategy.CODE_ANALYSIS: StrategyConfig(
        strategy=ResearchStrategy.CODE_ANALYSIS,
        search_depth=2, parallel_search=False, max_sources=5,
        source_priority=["fts5", "graph"], needs_knowledge_base=True,
        needs_web_search=False, expected_duration=60.0,
        output_format="代码审查+建议",
    ),
    ResearchStrategy.DATA_ANALYSIS: StrategyConfig(
        strategy=ResearchStrategy.DATA_ANALYSIS,
        search_depth=2, parallel_search=False, max_sources=8,
        source_priority=["engram", "fts5"], needs_knowledge_base=True,
        needs_web_search=False, expected_duration=90.0,
        output_format="数据表格+统计+结论",
    ),
    ResearchStrategy.COMPLIANCE_CHECK: StrategyConfig(
        strategy=ResearchStrategy.COMPLIANCE_CHECK,
        search_depth=2, parallel_search=False, max_sources=5,
        source_priority=["engram"], needs_knowledge_base=True,
        needs_web_search=False, expected_duration=45.0,
        output_format="合规判定+超标清单+整改建议",
    ),
    ResearchStrategy.COMPARATIVE: StrategyConfig(
        strategy=ResearchStrategy.COMPARATIVE,
        search_depth=3, parallel_search=True, max_sources=12,
        source_priority=["engram", "vector", "web"],
        needs_knowledge_base=True, needs_web_search=True,
        expected_duration=150.0,
        output_format="对比表+差异分析+推荐",
    ),
    ResearchStrategy.LITERATURE_REVIEW: StrategyConfig(
        strategy=ResearchStrategy.LITERATURE_REVIEW,
        search_depth=4, parallel_search=True, max_sources=25,
        source_priority=["web", "vector", "fts5"],
        needs_knowledge_base=False, needs_web_search=True,
        expected_duration=180.0,
        output_format="综述+分类+趋势分析",
    ),
    ResearchStrategy.EXPLORATORY: StrategyConfig(
        strategy=ResearchStrategy.EXPLORATORY,
        search_depth=2, parallel_search=True, max_sources=10,
        source_priority=["web", "vector"],
        needs_knowledge_base=False, needs_web_search=True,
        expected_duration=90.0,
        output_format="探索摘要+方向建议",
    ),
}


INTENT_TO_STRATEGY = {
    "查询": ResearchStrategy.QUICK_FACT,
    "什么是": ResearchStrategy.QUICK_FACT,
    "定义": ResearchStrategy.QUICK_FACT,
    "标准": ResearchStrategy.LOOKUP_STANDARD,
    "限值": ResearchStrategy.LOOKUP_STANDARD,
    "GB": ResearchStrategy.LOOKUP_STANDARD,
    "HJ": ResearchStrategy.LOOKUP_STANDARD,
    "研究": ResearchStrategy.DETAILED_RESEARCH,
    "分析": ResearchStrategy.DETAILED_RESEARCH,
    "评估": ResearchStrategy.DETAILED_RESEARCH,
    "报告": ResearchStrategy.REPORT_GENERATION,
    "环评": ResearchStrategy.REPORT_GENERATION,
    "编制": ResearchStrategy.REPORT_GENERATION,
    "代码": ResearchStrategy.CODE_ANALYSIS,
    "审查": ResearchStrategy.CODE_ANALYSIS,
    "bug": ResearchStrategy.CODE_ANALYSIS,
    "数据": ResearchStrategy.DATA_ANALYSIS,
    "统计": ResearchStrategy.DATA_ANALYSIS,
    "监测": ResearchStrategy.DATA_ANALYSIS,
    "合规": ResearchStrategy.COMPLIANCE_CHECK,
    "达标": ResearchStrategy.COMPLIANCE_CHECK,
    "审核": ResearchStrategy.COMPLIANCE_CHECK,
    "对比": ResearchStrategy.COMPARATIVE,
    "比较": ResearchStrategy.COMPARATIVE,
    "方案比选": ResearchStrategy.COMPARATIVE,
    "综述": ResearchStrategy.LITERATURE_REVIEW,
    "文献": ResearchStrategy.LITERATURE_REVIEW,
    "研究进展": ResearchStrategy.LITERATURE_REVIEW,
    "探索": ResearchStrategy.EXPLORATORY,
    "调研": ResearchStrategy.EXPLORATORY,
    "初步": ResearchStrategy.EXPLORATORY,
}


def classify_strategy(goal: str, domain: str = "general") -> tuple[ResearchStrategy, StrategyConfig]:
    """LDR-inspired: classify task intent to optimal research strategy.

    Matches goal keywords to strategy types. Domain-specific overrides
    applied for EIA/Code contexts.
    """
    goal_lower = goal.lower()

    if domain in ("环评", "EIA", "环境影响评价"):
        if any(kw in goal for kw in ["报告", "编制", "环评"]):
            return (ResearchStrategy.REPORT_GENERATION,
                    STRATEGY_CONFIGS[ResearchStrategy.REPORT_GENERATION])
        if any(kw in goal for kw in ["标准", "GB", "HJ", "限值"]):
            return (ResearchStrategy.LOOKUP_STANDARD,
                    STRATEGY_CONFIGS[ResearchStrategy.LOOKUP_STANDARD])
        if any(kw in goal for kw in ["合规", "达标", "审核"]):
            return (ResearchStrategy.COMPLIANCE_CHECK,
                    STRATEGY_CONFIGS[ResearchStrategy.COMPLIANCE_CHECK])

    if domain in ("代码", "code", "软件"):
        return (ResearchStrategy.CODE_ANALYSIS,
                STRATEGY_CONFIGS[ResearchStrategy.CODE_ANALYSIS])

    for keyword, strategy in INTENT_TO_STRATEGY.items():
        if keyword in goal_lower:
            return strategy, STRATEGY_CONFIGS[strategy]

    return (ResearchStrategy.EXPLORATORY,
            STRATEGY_CONFIGS[ResearchStrategy.EXPLORATORY])


def get_strategy_config(strategy: ResearchStrategy) -> StrategyConfig:
    return STRATEGY_CONFIGS.get(strategy, STRATEGY_CONFIGS[ResearchStrategy.EXPLORATORY])


class TaskPlanner:
    """Task planner with dynamic template learning.

    No hardcoded domain templates. Templates are learned from:
    1. KnowledgeBase (previously learned)
    2. Distillation (expert model)
    3. FormatDiscovery (document analysis)

    Usage:
        planner = TaskPlanner(kb=world.knowledge_base)
        steps = await planner.decompose_task(goal, domain="环评报告")
    """

    def __init__(self, max_depth: int = 10, kb: Any = None,
                 distillation: Any = None, expert_config: Any = None,
                 format_discovery: Any = None):
        self.max_depth = max_depth
        self.kb = kb
        self.distillation = distillation
        self.expert_config = expert_config
        self.format_discovery = format_discovery
        self._learner: Any = None

    async def decompose_task(self, goal: str, context: dict[str, Any] | None = None,
                             domain: str = "general", depth: int = 0) -> list[dict[str, Any]]:
        """Dynamically learn or retrieve a task template."""
        if self._learner is None:
            from ..knowledge.learning_engine import TemplateLearner
            self._learner = TemplateLearner(
                kb=self.kb, distillation=self.distillation, expert_config=self.expert_config,
            )

        return await self._learner.get_template(domain, goal)

    async def record_result(self, domain: str, success_rate: float) -> None:
        if self._learner:
            self._learner.record_success(domain, success_rate)

    async def estimate_complexity(self, goal: str) -> dict[str, Any]:
        return {"complexity": "medium", "estimated_steps": 5, "parallel_possible": True}
