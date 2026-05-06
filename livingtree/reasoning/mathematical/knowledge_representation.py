"""Mathematical Logic — FOL Knowledge Representation + Predicate Calculus.

数理逻辑在 LivingTree 中的工程实现：
  一阶谓词演算: 将知识编码为可机器推理的谓词逻辑公式
  描述逻辑: TBox (术语公理) + ABox (断言事实) 知识库
  可满足性: 检查知识库一致性

Usage:
    kr = KnowledgeRepresentation()
    kr.define_concept("工业项目", lambda x: x.type == "industrial")
    kr.assert_fact("项目A", type="industrial", location="朝阳区")
    result = kr.query("工业项目(项目A)")  # → True
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from loguru import logger


@dataclass
class Predicate:
    """一阶谓词 — P(x1, x2, ..., xn)"""
    name: str
    arity: int
    definition: Optional[Callable] = None  # 可选的 Python 函数实现

    def __call__(self, *args) -> bool:
        if self.definition:
            try:
                return bool(self.definition(*args))
            except Exception:
                return False
        return False


@dataclass
class Individual:
    """个体常量 — 知识库中的具体实体。"""
    name: str
    properties: dict[str, Any] = field(default_factory=dict)
    type_hierarchy: list[str] = field(default_factory=list)  # 类型链 (is-a)

    def is_a(self, concept: str) -> bool:
        return concept in self.type_hierarchy


@dataclass
class Axiom:
    """TBox 公理 — 术语层知识（概念定义、关系约束）。"""
    name: str
    axiom_type: str  # "concept_definition", "role_inclusion", "disjointness"
    body: str        # 自然语言描述
    formula: Optional[Callable] = None  # 可计算的形式化定义


class KnowledgeRepresentation:
    """FOL + 描述逻辑混合知识表示。

    TBox (Terminological Box): 概念定义、关系约束
    ABox (Assertional Box): 个体断言、关系实例
    """

    def __init__(self, name: str = "default"):
        self.name = name
        self._concepts: dict[str, Callable] = {}         # TBox: 概念定义
        self._roles: dict[str, Callable] = {}             # TBox: 角色/关系
        self._axioms: dict[str, Axiom] = {}               # TBox: 公理
        self._individuals: dict[str, Individual] = {}     # ABox: 个体
        self._relations: dict[tuple[str, str, str], bool] = {}  # ABox: R(a,b)
        self._predicates: dict[str, Predicate] = {}
        self._disjoints: list[tuple[str, str]] = []       # 互斥概念对

    def define_concept(self, name: str, condition: Callable[[dict], bool]) -> None:
        """定义概念（TBox 一元谓词）。"""
        self._concepts[name] = condition
        logger.debug("KR[%s]: defined concept '%s'", self.name, name)

    def define_role(self, name: str, condition: Callable[[Any, Any], bool]) -> None:
        """定义角色/关系（TBox 二元谓词）。"""
        self._roles[name] = condition
        logger.debug("KR[%s]: defined role '%s'", self.name, name)

    def define_axiom(self, axiom: Axiom) -> None:
        self._axioms[axiom.name] = axiom

    def declare_disjoint(self, concept_a: str, concept_b: str) -> None:
        """声明两个概念互斥（矛盾律：不可同时属于两者）。"""
        self._disjoints.append((concept_a, concept_b))

    def assert_individual(self, name: str, **properties) -> Individual:
        """声明个体（ABox 断言）。"""
        individual = Individual(name=name, properties=properties)
        self._individuals[name] = individual
        return individual

    def assert_type(self, individual_name: str, concept_name: str) -> bool:
        """断言个体属于某概念: concept(individual)。"""
        if individual_name not in self._individuals:
            return False
        if concept_name not in self._concepts:
            logger.warning("KR[%s]: concept '%s' not defined", self.name, concept_name)
            self._individuals[individual_name].type_hierarchy.append(concept_name)
            return True
        individual = self._individuals[individual_name]
        result = self._concepts[concept_name](individual.properties)
        if result:
            individual.type_hierarchy.append(concept_name)
        return result

    def assert_relation(self, subject: str, role: str, obj: str) -> bool:
        """断言关系: role(subject, object)。"""
        key = (subject, role, obj)
        if role in self._roles:
            subj = self._individuals.get(subject)
            obji = self._individuals.get(obj)
            if subj and obji:
                result = self._roles[role](subj.properties, obji.properties)
                self._relations[key] = result
                return result
        self._relations[key] = True
        return True

    def query_concept(self, individual_name: str, concept_name: str) -> bool:
        """查询个体是否属于某概念。"""
        ind = self._individuals.get(individual_name)
        if not ind:
            return False
        return ind.is_a(concept_name)

    def query_relation(self, subject: str, role: str, obj: str) -> bool:
        """查询关系是否成立。"""
        return self._relations.get((subject, role, obj), False)

    def query_all_of_type(self, concept_name: str) -> list[Individual]:
        """获取所有属于某概念的个体。"""
        return [ind for ind in self._individuals.values() if ind.is_a(concept_name)]

    def check_consistency(self) -> tuple[bool, list[str]]:
        """检查知识库一致性（矛盾律）。

        检测：
          - 同一个体不可能同时属于互斥概念
          - 关系不可能同时成立和不成立
        """
        violations = []

        for ind in self._individuals.values():
            for a, b in self._disjoints:
                if ind.is_a(a) and ind.is_a(b):
                    violations.append(
                        f"DISJOINT VIOLATION: '{ind.name}' is both '{a}' and '{b}'"
                    )

        for (s, r, o), val in self._relations.items():
            if not val:
                violations.append(f"RELATION VIOLATION: {r}({s}, {o}) is False")

        consistent = len(violations) == 0
        if not consistent:
            logger.warning("KR[%s]: consistency check found %d violations", self.name, len(violations))

        return consistent, violations

    def define_predicate(self, name: str, arity: int, definition: Callable) -> Predicate:
        """定义一阶谓词。"""
        pred = Predicate(name=name, arity=arity, definition=definition)
        self._predicates[name] = pred
        return pred

    def evaluate_formula(self, formula_str: str) -> tuple[bool, float]:
        """简化的一阶公式求值。

        支持:
          - 概念断言: concept(individual)
          - 关系断言: role(subject, object)
          - AND: formula_a ∧ formula_b
          - OR: formula_a ∨ formula_b
          - NOT: ¬formula

        返回 (truth_value, confidence)。
        """
        formula_str = formula_str.strip()

        # NOT
        if formula_str.startswith("¬") or formula_str.startswith("!"):
            inner = formula_str[1:].strip()
            val, conf = self.evaluate_formula(inner)
            return not val, conf

        # AND
        if " ∧ " in formula_str:
            parts = formula_str.split(" ∧ ", 1)
            a_val, a_conf = self.evaluate_formula(parts[0])
            b_val, b_conf = self.evaluate_formula(parts[1])
            return a_val and b_val, min(a_conf, b_conf)

        # OR
        if " ∨ " in formula_str:
            parts = formula_str.split(" ∨ ", 1)
            a_val, a_conf = self.evaluate_formula(parts[0])
            b_val, b_conf = self.evaluate_formula(parts[1])
            return a_val or b_val, max(a_conf, b_conf)

        # Predicate evaluation: P(arg1, arg2, ...)
        import re
        match = re.match(r'(\w+)\((.+)\)', formula_str)
        if match:
            pred_name = match.group(1)
            args = [a.strip() for a in match.group(2).split(",")]
            if pred_name in self._predicates:
                try:
                    pred = self._predicates[pred_name]
                    result = pred(*args)
                    return bool(result), 1.0 if result else 0.5
                except Exception:
                    pass

            if pred_name in self._concepts and len(args) == 1:
                result = self.query_concept(args[0], pred_name)
                return result, 0.9 if result else 0.1

            if pred_name in self._roles and len(args) == 2:
                result = self.query_relation(args[0], pred_name, args[1])
                return result, 0.9 if result else 0.1

        return False, 0.0

    def get_stats(self) -> dict:
        return {
            "name": self.name,
            "concepts": len(self._concepts),
            "roles": len(self._roles),
            "axioms": len(self._axioms),
            "individuals": len(self._individuals),
            "relations": len(self._relations),
            "predicates": len(self._predicates),
            "disjoints": len(self._disjoints),
        }
