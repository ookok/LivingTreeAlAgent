"""
反事实推理引擎 (Counterfactual Engine)

"What-If" 假设推理：
- 反事实条件生成
- 替代场景模拟
- 因果关系验证（如果X没发生，Y会怎样？）
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .reasoning_coordinator import ReasoningResult

logger = logging.getLogger(__name__)


@dataclass
class Counterfactual:
    fact_id: str
    scenario: str
    actual_outcome: str
    counterfactual_outcome: str = ""
    conditions: List[str] = field(default_factory=list)
    confidence: float = 0.0


@dataclass
class SimulationResult:
    scenario: str
    outcomes: List[Dict[str, Any]] = field(default_factory=list)
    most_likely: str = ""
    probability: float = 0.0


class CounterfactualEngine:

    def __init__(self):
        self._cases: Dict[str, Counterfactual] = {}
        self._init_example_cases()

    def _init_example_cases(self):
        cases = [
            Counterfactual(
                fact_id="cf_01",
                scenario="如果微服务没有拆分数据库",
                actual_outcome="系统性能和可维护性下降",
                counterfactual_outcome="数据库成为单点瓶颈",
                conditions=["共享数据库", "高并发访问"],
                confidence=0.8),
            Counterfactual(
                fact_id="cf_02",
                scenario="如果架构设计忽略了可扩展性",
                actual_outcome="后期重构成本高昂",
                counterfactual_outcome="需要大规模系统迁移",
                conditions=["业务快速增长", "用户量激增"],
                confidence=0.85),
        ]
        for case in cases:
            self._cases[case.fact_id] = case

    def add_case(self, case: Counterfactual):
        self._cases[case.fact_id] = case

    def reason(self, query: str, context: Dict[str, Any] = None) -> ReasoningResult:
        if "如果" in query or "假设" in query or "要是" in query:
            return self._counterfactual_reason(query)
        return self._general_reason(query)

    def _counterfactual_reason(self, query: str) -> ReasoningResult:
        relevant_cases = self._find_relevant_cases(query)

        conclusion = "反事实推理分析：\n"
        chain = ["识别反事实假设"]

        if relevant_cases:
            for case in relevant_cases[:2]:
                conclusion += f"\n假设: {case.scenario}\n"
                conclusion += f"  实际结果: {case.actual_outcome}\n"
                conclusion += f"  反事实结果: {case.counterfactual_outcome}\n"
                conclusion += f"  置信度: {case.confidence:.2f}\n"
                chain.append(f"引用案例: {case.fact_id}")
        else:
            conclusion += f"\n针对假设'{query[:100]}'，反事实推理需要更多上下文信息。"
            chain.append("无匹配案例")

        return ReasoningResult(
            task_id="cf_result",
            domain=None,
            engine="counterfactual_engine",
            conclusion=conclusion,
            reasoning_chain=chain,
            confidence=0.6 if relevant_cases else 0.3,
            metadata={"cases_found": len(relevant_cases)})

    def _general_reason(self, query: str) -> ReasoningResult:
        return ReasoningResult(
            task_id="cf_general",
            domain=None,
            engine="counterfactual_engine",
            conclusion=f"问题不包含反事实假设，请使用'如果...会怎样'的格式来触发反事实推理。\n原始问题: {query[:200]}",
            reasoning_chain=["非反事实推理"],
            confidence=0.0)

    def _find_relevant_cases(self, query: str) -> List[Counterfactual]:
        relevant = []
        query_lower = query.lower()
        for case in self._cases.values():
            scenario_words = set(case.scenario.lower().split())
            query_words = set(query_lower.split())
            overlap = scenario_words & query_words
            if overlap or any(c.lower() in query_lower
                            for c in case.conditions):
                relevant.append(case)

        relevant.sort(key=lambda c: -c.confidence)
        return relevant[:3]

    def simulate(self, scenario: str, variables: Dict[str, Any] = None
                 ) -> SimulationResult:
        outcomes = [{
            "description": f"模拟结果：在'{scenario}'场景下，系统可能表现出与现有案例类似的模式",
            "probability": 0.7}]

        return SimulationResult(
            scenario=scenario,
            outcomes=outcomes,
            most_likely=outcomes[0]["description"] if outcomes else "",
            probability=0.7)


__all__ = ["Counterfactual", "SimulationResult", "CounterfactualEngine"]
