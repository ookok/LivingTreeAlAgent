"""
推理协调器 (Reasoning Coordinator)

管理多个推理引擎的调度和融合：
- 根据任务类型自动选择合适的推理引擎
- 支持多引擎融合推理
- 推理过程追踪和结果评估
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
import uuid

logger = logging.getLogger(__name__)


class TaskDomain(Enum):
    LOGICAL = "logical"
    CAUSAL = "causal"
    ANALOGICAL = "analogical"
    COUNTERFACTUAL = "counterfactual"
    GENERAL = "general"


class TaskComplexity(Enum):
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"


@dataclass
class ReasoningTask:
    task_id: str
    query: str
    domain: TaskDomain = TaskDomain.GENERAL
    complexity: TaskComplexity = TaskComplexity.MODERATE
    context: Dict[str, Any] = field(default_factory=dict)
    constraints: List[str] = field(default_factory=list)


@dataclass
class ReasoningResult:
    task_id: str
    domain: TaskDomain
    engine: str
    conclusion: str
    reasoning_chain: List[str] = field(default_factory=list)
    confidence: float = 0.0
    fused: bool = False
    contributing_engines: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ReasoningCoordinator:
    """多引擎推理协调器"""

    def __init__(self):
        self._engines: Dict[str, Any] = {}
        self._engine_domains: Dict[TaskDomain, List[str]] = {}
        self._llm_callable: Optional[Callable[[str], str]] = None

    def register_engine(self, name: str, engine: Any, domains: List[TaskDomain]):
        self._engines[name] = engine
        for domain in domains:
            if domain not in self._engine_domains:
                self._engine_domains[domain] = []
            self._engine_domains[domain].append(name)
        logger.info(f"注册推理引擎: {name} (域: {[d.value for d in domains]})")

    def set_llm_callable(self, llm: Callable[[str], str]):
        self._llm_callable = llm

    def classify_task(self, query: str) -> TaskDomain:
        query_lower = query.lower()

        if any(k in query_lower for k in ["为什么", "导致", "原因", "影响", "结果", "后果"]):
            return TaskDomain.CAUSAL
        if any(k in query_lower for k in ["类比", "类似", "像", "比如", "举例"]):
            return TaskDomain.ANALOGICAL
        if any(k in query_lower for k in ["如果", "假设", "要是", "倘若"]):
            return TaskDomain.COUNTERFACTUAL
        if any(k in query_lower for k in ["逻辑", "推理", "演绎", "归纳", "条件"]):
            return TaskDomain.LOGICAL
        return TaskDomain.GENERAL

    def assess_complexity(self, query: str) -> TaskComplexity:
        if len(query) > 500 or query.count("?") > 2:
            return TaskComplexity.COMPLEX
        if len(query) > 200 or "?" in query:
            return TaskComplexity.MODERATE
        return TaskComplexity.SIMPLE

    def reason(self, query: str) -> ReasoningResult:
        domain = self.classify_task(query)
        complexity = self.assess_complexity(query)

        task = ReasoningTask(
            task_id=f"rtask_{uuid.uuid4().hex[:8]}",
            query=query, domain=domain, complexity=complexity)

        if complexity == TaskComplexity.COMPLEX:
            return self._multi_engine_reason(task)

        return self._single_engine_reason(task)

    def _single_engine_reason(self, task: ReasoningTask) -> ReasoningResult:
        engines = self._engine_domains.get(task.domain, [])
        if engines:
            engine_name = engines[0]
            engine = self._engines.get(engine_name)
            if engine:
                return self._run_engine(engine_name, engine, task)
        return self._default_reason(task)

    def _multi_engine_reason(self, task: ReasoningTask) -> ReasoningResult:
        engines = self._engine_domains.get(task.domain, [])
        if not engines:
            return self._default_reason(task)

        results = []
        for eng_name in engines[:3]:
            engine = self._engines.get(eng_name)
            if engine:
                result = self._run_engine(eng_name, engine, task)
                results.append(result)

        if not results:
            return self._default_reason(task)

        fused = self._fuse_results(results)
        fused.fused = True
        fused.contributing_engines = [r.engine for r in results]
        return fused

    def _run_engine(self, name: str, engine: Any, task: ReasoningTask) -> ReasoningResult:
        try:
            return engine.reason(task.query, task.context)
        except Exception as e:
            logger.error(f"引擎 {name} 推理失败: {e}")
            return ReasoningResult(
                task_id=task.task_id,
                domain=task.domain,
                engine=name,
                conclusion=f"[引擎错误: {str(e)}]",
                confidence=0.0)

    def _fuse_results(self, results: List[ReasoningResult]) -> ReasoningResult:
        if len(results) == 1:
            return results[0]

        conclusions = [r.conclusion for r in results]
        best = max(results, key=lambda r: r.confidence)
        avg_confidence = sum(r.confidence for r in results) / len(results)

        fused_conclusion = f"多引擎融合分析：\n\n"
        for i, r in enumerate(results, 1):
            fused_conclusion += f"引擎{i} ({r.engine}): {r.conclusion[:200]}\n\n"
        fused_conclusion += f"综合置信度最高结论: {best.conclusion}"

        return ReasoningResult(
            task_id=results[0].task_id,
            domain=results[0].domain,
            engine="fusion",
            conclusion=fused_conclusion,
            reasoning_chain=["多引擎融合推理"],
            confidence=avg_confidence,
            metadata={"num_engines": len(results)})

    def _default_reason(self, task: ReasoningTask) -> ReasoningResult:
        if self._llm_callable:
            prompt = f"""请对以下问题进行推理分析：

问题: {task.query}

请给出清晰的推理过程和结论。"""
            result_text = self._llm_callable(prompt)
        else:
            result_text = f"对问题 '{task.query[:100]}' 的推理分析需要集成LLM引擎。"

        return ReasoningResult(
            task_id=task.task_id,
            domain=task.domain,
            engine="default",
            conclusion=result_text,
            reasoning_chain=["默认推理"],
            confidence=0.5)

    def get_engine_stats(self) -> Dict[str, Any]:
        return {
            "total_engines": len(self._engines),
            "engine_names": list(self._engines.keys()),
            "domain_coverage": {
                d.value: names for d, names in self._engine_domains.items()},
        }


__all__ = [
    "TaskDomain", "TaskComplexity", "ReasoningTask",
    "ReasoningResult", "ReasoningCoordinator",
]
