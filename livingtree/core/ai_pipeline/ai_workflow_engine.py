"""
AI 工作流引擎 (AI Workflow Engine)

多阶段工作流调度系统：
1. Analyze → 分析任务
2. Plan → 制定方案
3. Generate → 生成内容/代码
4. Verify → 验证结果
5. Refine → 迭代优化
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class WorkflowStage(Enum):
    ANALYZE = "analyze"
    PLAN = "plan"
    GENERATE = "generate"
    VERIFY = "verify"
    REFINE = "refine"
    COMPLETE = "complete"


@dataclass
class WorkflowContext:
    session_id: str
    task: str
    current_stage: WorkflowStage = WorkflowStage.ANALYZE
    history: List[Dict[str, Any]] = field(default_factory=list)
    artifacts: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


class AIWorkflowEngine:

    def __init__(self):
        self._stage_handlers: Dict[WorkflowStage, Callable] = {
            WorkflowStage.ANALYZE: self._handle_analyze,
            WorkflowStage.PLAN: self._handle_plan,
            WorkflowStage.GENERATE: self._handle_generate,
            WorkflowStage.VERIFY: self._handle_verify,
            WorkflowStage.REFINE: self._handle_refine,
        }
        self._llm_callable: Optional[Callable[[str], str]] = None

    def set_llm(self, llm: Callable[[str], str]):
        self._llm_callable = llm

    def start_session(self, task: str,
                      metadata: Dict[str, Any] = None) -> WorkflowContext:
        session_id = f"wf_{uuid.uuid4().hex[:8]}"
        context = WorkflowContext(
            session_id=session_id, task=task,
            metadata=metadata or {})
        context.history.append({
            "stage": "START", "timestamp": datetime.now().isoformat(),
            "task": task[:200]})
        return context

    def execute_stage(self, context: WorkflowContext) -> WorkflowContext:
        handler = self._stage_handlers.get(context.current_stage)
        if handler:
            context = handler(context)
            context.history.append({
                "stage": context.current_stage.value,
                "timestamp": datetime.now().isoformat(),
                "artifacts_keys": list(context.artifacts.keys())[-3:]})

        context.current_stage = self._next_stage(context.current_stage)
        return context

    def execute_full(self, task: str,
                     max_iterations: int = 10) -> WorkflowContext:
        context = self.start_session(task)
        iterations = 0

        while context.current_stage != WorkflowStage.COMPLETE and iterations < max_iterations:
            context = self.execute_stage(context)
            iterations += 1

        return context

    def _next_stage(self, current: WorkflowStage) -> WorkflowStage:
        transitions = {
            WorkflowStage.ANALYZE: WorkflowStage.PLAN,
            WorkflowStage.PLAN: WorkflowStage.GENERATE,
            WorkflowStage.GENERATE: WorkflowStage.VERIFY,
            WorkflowStage.VERIFY: WorkflowStage.REFINE,
            WorkflowStage.REFINE: WorkflowStage.COMPLETE,
        }
        return transitions.get(current, WorkflowStage.COMPLETE)

    def _handle_analyze(self, context: WorkflowContext) -> WorkflowContext:
        task_type = self._classify_task(context.task)
        complexity = "simple" if len(context.task) < 200 else "moderate" if len(context.task) < 500 else "complex"

        context.artifacts["analysis"] = {
            "task_type": task_type,
            "complexity": complexity,
            "summary": context.task[:500]}

        if self._llm_callable:
            prompt = f"分析以下任务:\n{context.task}\n\n给出任务类型、复杂度和关键要素。"
            context.artifacts["deep_analysis"] = self._llm_callable(prompt)

        return context

    def _handle_plan(self, context: WorkflowContext) -> WorkflowContext:
        analysis = context.artifacts.get("analysis", {})
        complexity = analysis.get("complexity", "simple")

        plan = {
            "phases": [
                {"name": "准备", "steps": ["确认需求", "收集信息"]},
                {"name": "执行", "steps": ["核心实现", "测试验证"]},
                {"name": "交付", "steps": ["检查结果", "生成报告"]},
            ],
            "estimated_phases": 3 if complexity != "complex" else 5}
        context.artifacts["plan"] = plan
        return context

    def _handle_generate(self, context: WorkflowContext) -> WorkflowContext:
        plan = context.artifacts.get("plan", {})

        if self._llm_callable:
            prompt = f"基于分析结果和计划，执行任务:\n{context.task}\n\n计划: {plan.get('phases', [])}"
            result = self._llm_callable(prompt)
        else:
            result = f"任务生成结果（未启用LLM）: {context.task[:200]}"

        context.artifacts["generation"] = {"result": result,
                                           "format": "text"}
        return context

    def _handle_verify(self, context: WorkflowContext) -> WorkflowContext:
        generation = context.artifacts.get("generation", {})
        result = generation.get("result", "")

        checks = {
            "has_content": bool(result),
            "length": len(result),
            "status": "passed" if len(result) > 10 else "needs_refine",
        }
        context.artifacts["verification"] = checks
        return context

    def _handle_refine(self, context: WorkflowContext) -> WorkflowContext:
        verification = context.artifacts.get("verification", {})

        if verification.get("status") == "needs_refine":
            generation = context.artifacts.get("generation", {})
            if self._llm_callable and generation.get("result"):
                refined = self._llm_callable(
                    f"请改进以下结果:\n{generation['result']}")
                generation["refined_result"] = refined

        context.artifacts["refined"] = True
        return context

    def _classify_task(self, task: str) -> str:
        task_lower = task.lower()
        if any(k in task_lower for k in ["代码", "编程", "实现", "函数"]):
            return "coding"
        if any(k in task_lower for k in ["分析", "评估"]):
            return "analysis"
        if any(k in task_lower for k in ["设计", "架构"]):
            return "design"
        return "general"


__all__ = ["WorkflowStage", "WorkflowContext", "AIWorkflowEngine"]
