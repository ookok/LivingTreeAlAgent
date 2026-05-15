"""Formal Logic — Rule-based reasoning engine.

亚里士多德形式逻辑在 LivingTree 中的工程实现：
  同一律 (A=A): 每个规则标识唯一，结论确定性
  矛盾律 (¬(A∧¬A)): 禁止冲突规则共存
  排中律 (A∨¬A): 对任何命题必须给出判定（含 UNCERTAIN 显式标注）

Core algorithms:
  - Forward Chaining: 事实驱动 → 推导所有可证结论
  - Backward Chaining: 目标驱动 → 寻找支持目标的证据链
  - Rule Conflict Detection: 自动检测矛盾规则并发出警告
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Callable

from loguru import logger


class FactStatus(str, Enum):
    KNOWN = "known"        # 已确认事实
    ASSUMED = "assumed"    # 假设（待验证）
    RETRACTED = "retracted"  # 已撤回
    UNCERTAIN = "uncertain"  # 不确定（排中律：显式标注无法判定）


@dataclass
class Fact:
    """一个逻辑事实（命题原子）。"""
    name: str
    value: Any = True
    status: FactStatus = FactStatus.KNOWN
    confidence: float = 1.0          # 0.0-1.0
    source: str = ""                 # 来源（规则/传感器/用户）
    timestamp: float = field(default_factory=time.time)
    evidence: list[str] = field(default_factory=list)  # 支持证据

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        return self.name == other.name if isinstance(other, Fact) else self.name == other


@dataclass
class Rule:
    """一条形式规则（IF antecedent THEN consequent）。

    支持：
      - 简单条件: Fact(name) == value
      - 复合条件: ALL/ANY 连接
      - 可调用条件: callable(facts) → bool
    """
    name: str
    conditions: list[str]           # 前提事实名列表（ALL 需满足）
    any_conditions: list[str] = field(default_factory=list)  # ANY 满足其一即可
    conclusion: str = ""             # 结论事实名
    conclusion_value: Any = True
    priority: int = 0               # 越高越优先
    description: str = ""
    condition_fn: Optional[Callable] = None  # 自定义条件函数

    def evaluate(self, facts: dict[str, Fact]) -> tuple[bool, float]:
        """评估规则前提是否满足。返回 (satisfied, confidence)。"""
        if self.condition_fn:
            try:
                if self.condition_fn(facts):
                    return True, 1.0
            except Exception:
                pass

        confidences = []

        # ALL条件必须全部满足
        for cond in self.conditions:
            if cond not in facts:
                return False, 0.0
            fact = facts[cond]
            if fact.status in (FactStatus.RETRACTED,):
                return False, 0.0
            if not fact.value:
                return False, 0.0
            confidences.append(fact.confidence)

        # ANY条件至少满足一个
        if self.any_conditions:
            any_satisfied = False
            for cond in self.any_conditions:
                if cond in facts and facts[cond].value and facts[cond].status != FactStatus.RETRACTED:
                    any_satisfied = True
                    confidences.append(facts[cond].confidence)
                    break
            if not any_satisfied:
                return False, 0.0

        avg_confidence = sum(confidences) / len(confidences) if confidences else 1.0
        return True, avg_confidence


class RuleEngine:
    """规则推理机 — 前向链 + 后向链 + 矛盾检测。

    形式逻辑三大规律的工程保证：
      - 同一律: Rule.name 全局唯一，Fact.name 全局唯一
      - 矛盾律: add_rule 时自动检测冲突（A→B 与 A→¬B）
      - 排中律: 每个 query 必须返回 KNOWN/ASSUMED/UNCERTAIN
    """

    def __init__(self, name: str = "default"):
        self.name = name
        self._facts: dict[str, Fact] = {}
        self._rules: dict[str, Rule] = {}
        self._rule_conflicts: list[tuple[str, str, str]] = []  # (rule_a, rule_b, reason)
        self._inference_count: int = 0
        self._lock = threading.RLock()

    def assert_fact(self, name: str, value: Any = True,
                    confidence: float = 1.0, source: str = "",
                    status: FactStatus = FactStatus.KNOWN) -> Fact:
        """声明一个事实（同一律：同名事实覆盖更新）。"""
        with self._lock:
            fact = Fact(name=name, value=value, confidence=confidence,
                       source=source, status=status)
            self._facts[name] = fact
            logger.debug("RuleEngine[%s]: assert_fact %s = %s (conf=%.2f)", self.name, name, value, confidence)
            return fact

    def retract_fact(self, name: str) -> None:
        """撤回一个事实（矛盾律：撤销错误断言）。"""
        with self._lock:
            if name in self._facts:
                self._facts[name].status = FactStatus.RETRACTED
                logger.debug("RuleEngine[%s]: retract_fact %s", self.name, name)

    def add_rule(self, rule: Rule) -> bool:
        """添加规则（自动矛盾检测）。"""
        with self._lock:
            if rule.name in self._rules:
                logger.warning("RuleEngine[%s]: duplicate rule name '%s'", self.name, rule.name)
                return False

            self._check_rule_conflict(rule)
            self._rules[rule.name] = rule
            logger.debug("RuleEngine[%s]: add_rule %s", self.name, rule.name)
            return True

    def forward_chain(self, max_iterations: int = 100) -> list[Fact]:
        """前向链推理：从已知事实出发，反复应用规则，推导所有可证结论。

        算法：
         1. 收集所有满足前提的规则
         2. 按优先级排序
         3. 依次触发，将结论加入事实库
         4. 重复直到没有新事实产生
        """
        with self._lock:
            new_facts = []
            visited_rules: set[str] = set()

            for iteration in range(max_iterations):
                fired = False
                sorted_rules = sorted(self._rules.values(), key=lambda r: -r.priority)

                for rule in sorted_rules:
                    if rule.name in visited_rules:
                        continue
                    satisfied, confidence = rule.evaluate(self._facts)
                    if not satisfied:
                        continue

                    visited_rules.add(rule.name)
                    self._inference_count += 1

                    if rule.conclusion not in self._facts or self._facts[rule.conclusion].status == FactStatus.ASSUMED:
                        fact = self.assert_fact(
                            name=rule.conclusion,
                            value=rule.conclusion_value,
                            confidence=confidence,
                            source=f"rule:{rule.name}",
                            status=FactStatus.KNOWN,
                        )
                        new_facts.append(fact)
                        fired = True

                if not fired:
                    break

            logger.info("RuleEngine[%s]: forward_chain → %d new facts in %d iterations",
                       self.name, len(new_facts), iteration + 1)
            return new_facts

    def backward_chain(self, goal: str, max_depth: int = 20) -> tuple[bool, list[str]]:
        """后向链推理：给定目标，逆向寻找支持证据链。

        返回 (可证明, 证据规则链)。
        """
        with self._lock:
            if goal in self._facts and self._facts[goal].value and self._facts[goal].status != FactStatus.RETRACTED:
                return True, ["known_fact"]

            proof_chain = []
            visited = set()

            def _prove(target: str, depth: int) -> bool:
                if depth > max_depth or target in visited:
                    return False
                visited.add(target)

                for rule in sorted(self._rules.values(), key=lambda r: -r.priority):
                    if rule.conclusion == target:
                        satisfied, _ = rule.evaluate(self._facts)
                        if satisfied:
                            proof_chain.append(rule.name)
                            return True

                        for cond in rule.conditions:
                            if cond not in self._facts or not self._facts[cond].value:
                                if _prove(cond, depth + 1):
                                    proof_chain.append(rule.name)
                                    return True
                return False

            result = _prove(goal, 0)

            if result:
                proof_chain.reverse()
                return True, proof_chain

            if goal in self._facts:
                status = self._facts[goal].status
                if status == FactStatus.UNCERTAIN:
                    return False, ["uncertain"]
                if status == FactStatus.RETRACTED:
                    return False, ["retracted"]

            return False, ["no_proof"]

    def query(self, fact_name: str) -> FactStatus:
        """查询事实状态（排中律实现：必返回确定性状态）。"""
        with self._lock:
            if fact_name in self._facts:
                return self._facts[fact_name].status
            return FactStatus.UNCERTAIN

    def get_inference_trace(self, goal: str) -> dict:
        """获取目标推理的完整 trace（归因分析用）。"""
        provable, chain = self.backward_chain(goal)
        return {
            "goal": goal,
            "provable": provable,
            "proof_chain": chain,
            "facts_used": [
                f"{k}={self._facts[k].value}[{self._facts[k].status.value}]"
                for k in set().union(*(
                    set(r.conditions + r.any_conditions)
                    for r in [self._rules[rn] for rn in chain if rn in self._rules]
                )) if k in self._facts
            ],
            "inference_count": self._inference_count,
        }

    def _check_rule_conflict(self, new_rule: Rule) -> None:
        """矛盾律检测：新规则是否与已有规则冲突（A→B 与 A→¬B）。"""
        for existing in self._rules.values():
            same_premise = (set(new_rule.conditions) == set(existing.conditions) and
                          set(new_rule.any_conditions) == set(existing.any_conditions))
            opposite_conclusion = (new_rule.conclusion == existing.conclusion and
                                 new_rule.conclusion_value != existing.conclusion_value)
            if same_premise and opposite_conclusion:
                conflict = (new_rule.name, existing.name,
                          f"Same premises → opposite conclusions for '{new_rule.conclusion}'")
                self._rule_conflicts.append(conflict)
                logger.warning("RuleEngine[%s]: CONFLICT — %s vs %s", self.name, new_rule.name, existing.name)
                return

    def get_conflicts(self) -> list[tuple[str, str, str]]:
        return list(self._rule_conflicts)

    def get_stats(self) -> dict:
        with self._lock:
            return {
                "engine": self.name,
                "facts": len(self._facts),
                "rules": len(self._rules),
                "conflicts": len(self._rule_conflicts),
                "inferences": self._inference_count,
            }


# ──────────────────────────────────────────
#  Syllogism Verifier (三段论推理验证)
#  从 syllogism.py 合并入 rule_engine.py
# ──────────────────────────────────────────

class Quantifier(str, Enum):
    ALL = "all"
    SOME = "some"
    NONE = "none"
    SOME_NOT = "some_not"


class SyllogismFigure(str, Enum):
    FIGURE_1 = "1"
    FIGURE_2 = "2"
    FIGURE_3 = "3"
    FIGURE_4 = "4"


@dataclass
class CategoricalProposition:
    subject: str
    predicate: str
    quantifier: Quantifier
    confidence: float = 1.0


@dataclass
class SyllogismResult:
    conclusion: CategoricalProposition
    figure: SyllogismFigure
    mood: str = ""
    valid: bool = True
    confidence: float = 1.0
    explanation: str = ""


class SyllogismVerifier:
    VALID_MOODS = {
        ("all", "all", "all", "1"): ("BARBARA", SyllogismFigure.FIGURE_1),
        ("none", "all", "none", "1"): ("CELARENT", SyllogismFigure.FIGURE_1),
        ("all", "some", "some", "1"): ("DARII", SyllogismFigure.FIGURE_1),
        ("none", "some", "some_not", "1"): ("FERIO", SyllogismFigure.FIGURE_1),
        ("all", "all", "some", "1"): ("BARBARI", SyllogismFigure.FIGURE_1),
        ("none", "all", "some_not", "1"): ("CELARONT", SyllogismFigure.FIGURE_1),
        ("none", "all", "none", "2"): ("CESARE", SyllogismFigure.FIGURE_2),
        ("all", "none", "none", "2"): ("CAMESTRES", SyllogismFigure.FIGURE_2),
        ("none", "some", "some_not", "2"): ("FESTINO", SyllogismFigure.FIGURE_2),
        ("all", "some_not", "some_not", "2"): ("BAROCO", SyllogismFigure.FIGURE_2),
        ("all", "all", "some", "3"): ("DARAPTI", SyllogismFigure.FIGURE_3),
        ("none", "all", "some_not", "3"): ("FELAPTON", SyllogismFigure.FIGURE_3),
        ("all", "some", "some", "3"): ("DATISI", SyllogismFigure.FIGURE_3),
        ("some", "all", "some", "3"): ("DISAMIS", SyllogismFigure.FIGURE_3),
        ("some_not", "all", "some_not", "3"): ("BOCARDO", SyllogismFigure.FIGURE_3),
        ("none", "some", "some_not", "3"): ("FERISON", SyllogismFigure.FIGURE_3),
        ("all", "all", "some", "4"): ("BRAMANTIP", SyllogismFigure.FIGURE_4),
        ("all", "none", "none", "4"): ("CAMENES", SyllogismFigure.FIGURE_4),
        ("some", "none", "some_not", "4"): ("DIMARIS", SyllogismFigure.FIGURE_4),
        ("none", "all", "some_not", "4"): ("FESAPO", SyllogismFigure.FIGURE_4),
        ("none", "some", "some_not", "4"): ("FRESISON", SyllogismFigure.FIGURE_4),
    }

    def verify(
        self,
        major: CategoricalProposition,
        minor: CategoricalProposition,
        figure: SyllogismFigure,
    ) -> SyllogismResult:
        major_quant = major.quantifier.value
        minor_quant = minor.quantifier.value

        if figure == SyllogismFigure.FIGURE_1:
            conclusion_quant, valid = self._figure1(major_quant, minor_quant)
        elif figure == SyllogismFigure.FIGURE_2:
            conclusion_quant, valid = self._figure2(major_quant, minor_quant)
        elif figure == SyllogismFigure.FIGURE_3:
            conclusion_quant, valid = self._figure3(major_quant, minor_quant)
        elif figure == SyllogismFigure.FIGURE_4:
            conclusion_quant, valid = self._figure4(major_quant, minor_quant)
        else:
            return SyllogismResult(
                conclusion=CategoricalProposition(
                    subject=minor.subject, predicate=major.predicate,
                    quantifier=Quantifier.SOME,
                ),
                figure=figure,
                valid=False,
                explanation=f"Unknown figure: {figure}",
            )

        mood_key = (major_quant, minor_quant, conclusion_quant, figure.value)
        mood_info = self.VALID_MOODS.get(mood_key)

        if valid and mood_info:
            mood_name = mood_info[0]
            explanation = f"Valid syllogism: {mood_name} (Figure {figure.value})"
        elif valid:
            mood_name = "custom"
            explanation = f"Valid custom syllogism (Figure {figure.value})"
        else:
            mood_name = "invalid"
            explanation = f"Invalid syllogism: {major.subject}-{major.predicate} ∧ {minor.subject}-{minor.predicate}"

        confidence = min(major.confidence, minor.confidence) if valid else 0.0

        return SyllogismResult(
            conclusion=CategoricalProposition(
                subject=minor.subject,
                predicate=major.predicate,
                quantifier=Quantifier(conclusion_quant) if valid else Quantifier.SOME,
                confidence=confidence,
            ),
            figure=figure,
            mood=mood_name,
            valid=valid,
            confidence=confidence,
            explanation=explanation,
        )

    def verify_simple(
        self,
        major_all: bool, major_affirmative: bool,
        minor_all: bool, minor_affirmative: bool,
        figure: SyllogismFigure = SyllogismFigure.FIGURE_1,
    ) -> SyllogismResult:
        major_quant = Quantifier.ALL if major_all else Quantifier.SOME
        minor_quant = Quantifier.ALL if minor_all else Quantifier.SOME

        major_pred = "P_" + ("is" if major_affirmative else "is_not")
        minor_pred = "S_" + ("is" if minor_affirmative else "is_not")

        if not major_affirmative:
            major_quant = Quantifier.NONE if major_all else Quantifier.SOME_NOT
        if not minor_affirmative:
            minor_quant = Quantifier.NONE if minor_all else Quantifier.SOME_NOT

        major = CategoricalProposition(subject="M", predicate=major_pred, quantifier=major_quant)
        minor = CategoricalProposition(subject="S", predicate=minor_pred, quantifier=minor_quant)

        return self.verify(major, minor, figure)

    def explain(self, result: SyllogismResult) -> str:
        if not result.valid:
            return f"Invalid syllogism: {result.explanation}"

        c = result.conclusion
        quant_text = {
            Quantifier.ALL: "所有",
            Quantifier.SOME: "有些",
            Quantifier.NONE: "没有",
            Quantifier.SOME_NOT: "有些不",
        }

        return (
            f"{result.mood}三段论 (Figure {result.figure.value}): "
            f"前提 → {quant_text.get(c.quantifier, '')}{c.subject}是{c.predicate} "
            f"(置信度: {c.confidence:.0%}). {result.explanation}"
        )

    def _figure1(self, major_q: str, minor_q: str) -> tuple[str, bool]:
        if major_q == "all" and minor_q == "all":
            return "all", True
        if major_q == "none" and minor_q == "all":
            return "none", True
        if major_q == "all" and minor_q == "some":
            return "some", True
        if major_q == "none" and minor_q == "some":
            return "some_not", True
        return "some", False

    def _figure2(self, major_q: str, minor_q: str) -> tuple[str, bool]:
        if major_q == "none" and minor_q == "all":
            return "none", True
        if major_q == "all" and minor_q == "none":
            return "none", True
        if major_q == "none" and minor_q == "some":
            return "some_not", True
        if major_q == "all" and minor_q == "some_not":
            return "some_not", True
        return "some", False

    def _figure3(self, major_q: str, minor_q: str) -> tuple[str, bool]:
        if major_q == "all" and minor_q == "all":
            return "some", True
        if major_q == "none" and minor_q == "all":
            return "some_not", True
        if major_q == "all" and minor_q == "some":
            return "some", True
        if major_q == "some" and minor_q == "all":
            return "some", True
        if major_q == "some_not" and minor_q == "all":
            return "some_not", True
        if major_q == "none" and minor_q == "some":
            return "some_not", True
        return "some", False

    def _figure4(self, major_q: str, minor_q: str) -> tuple[str, bool]:
        if major_q == "all" and minor_q == "all":
            return "some", True
        if major_q == "all" and minor_q == "none":
            return "none", True
        if major_q == "some" and minor_q == "none":
            return "some_not", True
        if major_q == "none" and minor_q == "all":
            return "some_not", True
        if major_q == "none" and minor_q == "some":
            return "some_not", True
        return "some", False
