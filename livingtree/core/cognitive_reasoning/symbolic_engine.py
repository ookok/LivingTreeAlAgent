"""
符号推理引擎 (Symbolic Engine)

基于形式逻辑的符号推理：
- 命题逻辑推理
- 规则推导 (Forward/Backward Chaining)
- 知识表示 (Frames/Semantic Nets)
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from .reasoning_coordinator import ReasoningResult

logger = logging.getLogger(__name__)


@dataclass
class Rule:
    rule_id: str
    name: str
    conditions: List[str]
    conclusion: str
    priority: int = 0
    description: str = ""


@dataclass
class Fact:
    predicate: str
    subject: str
    obj: str = ""
    confidence: float = 1.0


class SymbolicEngine:

    def __init__(self):
        self._rules: Dict[str, Rule] = {}
        self._facts: List[Fact] = []
        self._inference_log: List[str] = []

    def add_rule(self, rule: Rule):
        self._rules[rule.rule_id] = rule

    def add_fact(self, fact: Fact):
        self._facts.append(fact)

    def reason(self, query: str, context: Dict[str, Any] = None) -> ReasoningResult:
        if not self._rules and not self._facts:
            return ReasoningResult(
                task_id="symbolic_default",
                domain=None,
                engine="symbolic_engine",
                conclusion=f"符号推理知识库为空，无法推理: {query[:100]}",
                reasoning_chain=["知识库为空"],
                confidence=0.0)

        triggered_rules = self._match_rules(query)

        if not triggered_rules:
            return ReasoningResult(
                task_id="symbolic_no_match",
                domain=None,
                engine="symbolic_engine",
                conclusion=f"未找到匹配的推理规则: {query[:100]}",
                reasoning_chain=["无规则匹配"],
                confidence=0.1)

        self._inference_log = []
        conclusions = []
        for rule in triggered_rules[:3]:
            fired, trace = self._try_fire_rule(rule)
            self._inference_log.extend(trace)
            if fired:
                conclusions.append(rule.conclusion)

        chain = self._inference_log[-5:] if self._inference_log else ["无推理步骤"]
        conclusion = "符号推理结果：\n"
        if conclusions:
            for i, c in enumerate(conclusions, 1):
                conclusion += f"结论{i}: {c}\n"
        else:
            conclusion += "无法推导出确定结论"

        return ReasoningResult(
            task_id="symbolic_result",
            domain=None,
            engine="symbolic_engine",
            conclusion=conclusion,
            reasoning_chain=chain,
            confidence=0.8 if conclusions else 0.2,
            metadata={
                "rules_checked": len(triggered_rules),
                "rules_fired": len(conclusions),
                "total_rules": len(self._rules)})

    def _match_rules(self, query: str) -> List[Rule]:
        matched = []
        query_lower = query.lower()
        for rule in self._rules.values():
            score = 0
            for cond in rule.conditions:
                if cond.lower() in query_lower:
                    score += 1
            if score > 0 or rule.name.lower() in query_lower:
                matched.append((score, rule.priority, rule))

        matched.sort(key=lambda x: (-x[0], -x[1]))
        return [m[2] for m in matched]

    def _try_fire_rule(self, rule: Rule) -> Tuple[bool, List[str]]:
        trace = [f"检查规则: {rule.name}"]
        conditions_met = True

        for cond in rule.conditions:
            fact_matched = any(
                cond.lower() in f.predicate.lower()
                or cond.lower() in f.subject.lower()
                or cond.lower() in f.obj.lower()
                for f in self._facts)

            if fact_matched:
                trace.append(f"  条件满足: {cond}")
            else:
                trace.append(f"  条件未满足: {cond}")
                conditions_met = False

        if conditions_met:
            trace.append(f"  规则触发: → {rule.conclusion}")
            return True, trace
        else:
            trace.append(f"  规则未触发")
            return False, trace

    def _check_fact(self, predicate: str, subject: str = "",
                    obj: str = "") -> bool:
        for fact in self._facts:
            if (predicate.lower() in fact.predicate.lower()
                and (not subject or subject.lower() in fact.subject.lower())
                and (not obj or obj.lower() in fact.obj.lower())):
                return True
        return False

    def get_knowledge_summary(self) -> Dict[str, Any]:
        return {
            "facts_count": len(self._facts),
            "rules_count": len(self._rules),
            "rule_names": list(self._rules.keys()),
        }


__all__ = ["Rule", "Fact", "SymbolicEngine"]
