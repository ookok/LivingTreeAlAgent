"""TaskPlanner — Intelligent task decomposition with chain-of-thought planning.

Decomposes complex goals into executable sub-tasks with dependencies,
resource estimates, and domain-aware splitting strategies.
"""

from __future__ import annotations

import uuid
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


class TaskPlanner:
    """
    Intelligent task planner with domain-specific decomposition strategies.

    Supports:
    - Chain-of-thought task decomposition
    - Dependency graph construction
    - Domain-specific templates (EIA reports, code, documents)
    - Parallel execution optimization
    """

    DOMAIN_TEMPLATES: dict[str, list[dict[str, Any]]] = {
        "环评报告": [
            {"name": "收集项目资料", "action": "collect_materials", "roles": ["collector", "environmental"]},
            {"name": "分析工程内容", "action": "analyze_engineering", "roles": ["analyst", "environmental"]},
            {"name": "调查环境现状", "action": "survey_environment", "roles": ["researcher", "environmental"]},
            {"name": "预测环境影响", "action": "predict_impact", "roles": ["modeler", "environmental"]},
            {"name": "制定环保措施", "action": "plan_mitigation", "roles": ["planner", "environmental"]},
            {"name": "风险评价", "action": "risk_assessment", "roles": ["analyst", "safety"]},
            {"name": "经济损益分析", "action": "economic_analysis", "roles": ["analyst", "economic"]},
            {"name": "编制报告文档", "action": "generate_report", "roles": ["writer", "environmental"]},
            {"name": "审核校核", "action": "review", "roles": ["reviewer", "environmental"]},
        ],
        "应急预案": [
            {"name": "风险识别", "action": "identify_risks", "roles": ["analyst", "safety"]},
            {"name": "应急资源调查", "action": "survey_resources", "roles": ["researcher", "safety"]},
            {"name": "编制应急组织", "action": "plan_organization", "roles": ["planner", "safety"]},
            {"name": "制定响应流程", "action": "plan_response", "roles": ["planner", "safety"]},
            {"name": "编制预案文档", "action": "generate_report", "roles": ["writer", "safety"]},
        ],
        "验收报告": [
            {"name": "工程调查", "action": "survey_engineering", "roles": ["researcher", "environmental"]},
            {"name": "环境监测数据分析", "action": "analyze_monitoring", "roles": ["analyst", "environmental"]},
            {"name": "环境影响调查", "action": "survey_impact", "roles": ["researcher", "environmental"]},
            {"name": "公众意见收集", "action": "collect_opinions", "roles": ["collector"]},
            {"name": "编制验收报告", "action": "generate_report", "roles": ["writer", "environmental"]},
        ],
        "可行性研究报告": [
            {"name": "市场调研", "action": "market_research", "roles": ["researcher", "economic"]},
            {"name": "技术方案设计", "action": "design_technical", "roles": ["engineer"]},
            {"name": "投资估算", "action": "estimate_investment", "roles": ["analyst", "economic"]},
            {"name": "经济评价", "action": "economic_evaluation", "roles": ["analyst", "economic"]},
            {"name": "编制可研报告", "action": "generate_report", "roles": ["writer", "economic"]},
        ],
        "code_development": [
            {"name": "需求分析", "action": "analyze_requirements", "roles": ["analyst"]},
            {"name": "架构设计", "action": "design_architecture", "roles": ["architect"]},
            {"name": "编码实现", "action": "implement_code", "roles": ["developer"]},
            {"name": "单元测试", "action": "unit_test", "roles": ["tester"]},
            {"name": "代码审查", "action": "code_review", "roles": ["reviewer"]},
            {"name": "集成部署", "action": "deploy", "roles": ["devops"]},
        ],
    }

    def __init__(self, max_depth: int = 10):
        self.max_depth = max_depth

    async def decompose_task(self, goal: str, context: dict[str, Any] | None = None,
                             domain: str = "general", depth: int = 0) -> list[dict[str, Any]]:
        """
        Decompose a high-level goal into executable sub-tasks.

        Args:
            goal: The user's goal description
            context: Additional context for planning
            domain: Target domain for template matching
            depth: Current recursion depth

        Returns:
            List of sub-task dictionaries
        """
        logger.info(f"Decomposing task: {goal[:100]} (domain={domain})")

        # Try domain-specific template
        template = self._match_template(goal, domain)
        if template:
            logger.info(f"Using domain template: {len(template)} steps")
            return template

        # General decomposition
        sub_tasks = self._general_decompose(goal, context or {}, depth)
        return sub_tasks

    def create_task_spec(self, goal: str, sub_tasks: list[dict[str, Any]],
                         context: dict[str, Any] | None = None,
                         domain: str = "general") -> TaskSpec:
        """Create a TaskSpec from decomposed sub-tasks."""
        task_objects = []
        prev_id = None
        for i, st in enumerate(sub_tasks):
            deps = [prev_id] if prev_id else []
            subtask = SubTask(
                name=st.get("name", f"step_{i}"),
                description=st.get("description", ""),
                action=st.get("action", "execute"),
                agent_roles=st.get("roles", ["general"]),
                dependencies=deps,
                estimated_duration=st.get("estimated_duration", 60.0),
                input_schema=st.get("input", {}),
            )
            task_objects.append(subtask)
            prev_id = subtask.id

        spec = TaskSpec(
            goal=goal,
            domain=domain,
            sub_tasks=task_objects,
            context=context or {},
            total_estimated_duration=sum(t.estimated_duration for t in task_objects),
        )
        return spec

    def _match_template(self, goal: str, domain: str) -> list[dict[str, Any]] | None:
        """Try to match a domain-specific template."""
        # Direct domain match
        if domain in self.DOMAIN_TEMPLATES:
            return self.DOMAIN_TEMPLATES[domain]

        # Keyword matching
        keywords_map = {
            "环评": "环评报告", "环境评价": "环评报告", "EIA": "环评报告",
            "应急预案": "应急预案", "应急": "应急预案",
            "验收": "验收报告", "竣工": "验收报告",
            "可研": "可行性研究报告", "可行性": "可行性研究报告",
            "开发": "code_development", "编程": "code_development", "代码": "code_development",
            "code": "code_development", "软件": "code_development",
        }
        goal_lower = goal.lower()
        for keyword, template_key in keywords_map.items():
            if keyword.lower() in goal_lower:
                return self.DOMAIN_TEMPLATES.get(template_key)
        return None

    def _general_decompose(self, goal: str, context: dict[str, Any],
                           depth: int) -> list[dict[str, Any]]:
        """General purpose task decomposition."""
        return [
            {"name": "理解需求", "action": "understand", "roles": ["analyst"],
             "description": f"分析需求: {goal[:80]}"},
            {"name": "收集资料", "action": "collect_materials", "roles": ["collector"],
             "description": "从网络、文件和用户输入中收集相关资料"},
            {"name": "分析处理", "action": "analyze", "roles": ["analyst"],
             "description": "对收集到的资料进行分析和处理"},
            {"name": "执行任务", "action": "execute", "roles": ["worker"],
             "description": "执行核心任务"},
            {"name": "生成结果", "action": "generate_output", "roles": ["writer"],
             "description": "生成最终输出结果"},
        ]

    async def estimate_complexity(self, goal: str) -> dict[str, Any]:
        """Estimate task complexity for resource allocation."""
        char_count = len(goal)
        keywords = goal.lower()
        complexity = "low"

        # Industry-specific keywords increase complexity
        industry_terms = ["环评", "应急预案", "验收", "可研", "报告", "开发", "系统"]
        matched = sum(1 for t in industry_terms if t in keywords)

        if char_count > 200 or matched >= 3:
            complexity = "high"
        elif char_count > 100 or matched >= 1:
            complexity = "medium"

        return {
            "complexity": complexity,
            "estimated_steps": {"low": 3, "medium": 5, "high": 9}.get(complexity, 5),
            "parallel_possible": complexity != "low",
        }
