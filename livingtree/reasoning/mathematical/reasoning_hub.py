"""Mathematical Logic — Reasoning Hub: FOL Knowledge Representation + Bayesian Reasoning.
 (数理逻辑在 LivingTree 中的工程实现)

一阶谓词演算: 将知识编码为可机器推理的谓词逻辑公式
描述逻辑: TBox (术语公理) + ABox (断言事实) 知识库
贝叶斯推理: 先验概率 → 似然 → 后验概率

Modules merged into this hub:
  - knowledge_representation: KnowledgeRepresentation predicate calculus
  - bayesian_reasoner: BayesianReasoner probabilistic reasoning
"""

from __future__ import annotations

import math
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from loguru import logger


# ──────────────────────────────────────────
#  FOL Knowledge Representation
# ──────────────────────────────────────────

@dataclass
class Predicate:
    name: str
    arity: int
    definition: Optional[Callable] = None

    def __call__(self, *args) -> bool:
        if self.definition:
            try:
                return bool(self.definition(*args))
            except Exception:
                return False
        return False


@dataclass
class Individual:
    name: str
    properties: dict[str, Any] = field(default_factory=dict)
    type_hierarchy: list[str] = field(default_factory=list)

    def is_a(self, concept: str) -> bool:
        return concept in self.type_hierarchy


@dataclass
class Axiom:
    name: str
    axiom_type: str
    body: str
    formula: Optional[Callable] = None


class KnowledgeRepresentation:
    def __init__(self, name: str = "default"):
        self.name = name
        self._concepts: dict[str, Callable] = {}
        self._roles: dict[str, Callable] = {}
        self._axioms: dict[str, Axiom] = {}
        self._individuals: dict[str, Individual] = {}
        self._relations: dict[tuple[str, str, str], bool] = {}
        self._predicates: dict[str, Predicate] = {}
        self._disjoints: list[tuple[str, str]] = []

    def define_concept(self, name: str, condition: Callable[[dict], bool]) -> None:
        self._concepts[name] = condition
        logger.debug("KR[%s]: defined concept '%s'", self.name, name)

    def define_role(self, name: str, condition: Callable[[Any, Any], bool]) -> None:
        self._roles[name] = condition
        logger.debug("KR[%s]: defined role '%s'", self.name, name)

    def define_axiom(self, axiom: Axiom) -> None:
        self._axioms[axiom.name] = axiom

    def declare_disjoint(self, concept_a: str, concept_b: str) -> None:
        self._disjoints.append((concept_a, concept_b))

    def assert_individual(self, name: str, **properties) -> Individual:
        individual = Individual(name=name, properties=properties)
        self._individuals[name] = individual
        return individual

    def assert_type(self, individual_name: str, concept_name: str) -> bool:
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
        ind = self._individuals.get(individual_name)
        if not ind:
            return False
        return ind.is_a(concept_name)

    def query_relation(self, subject: str, role: str, obj: str) -> bool:
        return self._relations.get((subject, role, obj), False)

    def query_all_of_type(self, concept_name: str) -> list[Individual]:
        return [ind for ind in self._individuals.values() if ind.is_a(concept_name)]

    def check_consistency(self) -> tuple[bool, list[str]]:
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
        pred = Predicate(name=name, arity=arity, definition=definition)
        self._predicates[name] = pred
        return pred

    def evaluate_formula(self, formula_str: str) -> tuple[bool, float]:
        formula_str = formula_str.strip()

        if formula_str.startswith("¬") or formula_str.startswith("!"):
            inner = formula_str[1:].strip()
            val, conf = self.evaluate_formula(inner)
            return not val, conf

        if " ∧ " in formula_str:
            parts = formula_str.split(" ∧ ", 1)
            a_val, a_conf = self.evaluate_formula(parts[0])
            b_val, b_conf = self.evaluate_formula(parts[1])
            return a_val and b_val, min(a_conf, b_conf)

        if " ∨ " in formula_str:
            parts = formula_str.split(" ∨ ", 1)
            a_val, a_conf = self.evaluate_formula(parts[0])
            b_val, b_conf = self.evaluate_formula(parts[1])
            return a_val or b_val, max(a_conf, b_conf)

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


# ──────────────────────────────────────────
#  Bayesian Reasoner
# ──────────────────────────────────────────

@dataclass
class Hypothesis:
    name: str
    prior: float = 0.5
    posterior: float = 0.5
    evidence_log: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def update(self, likelihood: float, evidence_name: str = "") -> None:
        self.evidence_log.append({
            "evidence": evidence_name,
            "likelihood": likelihood,
            "prior": self.posterior,
        })
        self.posterior = self.posterior * likelihood
        self.posterior = self.posterior / (
            self.posterior * likelihood + (1 - self.posterior) * (1 - likelihood)
        )
        self.posterior = max(0.001, min(0.999, self.posterior))


@dataclass
class Evidence:
    name: str
    likelihood_given_h: float = 0.8
    likelihood_given_not_h: float = 0.2
    weight: float = 1.0
    source: str = ""


class BayesianReasoner:
    def __init__(self, name: str = "default"):
        self.name = name
        self._hypotheses: dict[str, Hypothesis] = {}
        self._evidences: dict[str, Evidence] = {}
        self._dependencies: dict[str, list[str]] = defaultdict(list)

    def add_hypothesis(self, name: str, prior: float = 0.5, **metadata) -> Hypothesis:
        prior = max(0.01, min(0.99, prior))
        h = Hypothesis(name=name, prior=prior, posterior=prior, metadata=metadata)
        self._hypotheses[name] = h
        logger.debug("Bayes[%s]: hypothesis '%s' prior=%.2f", self.name, name, prior)
        return h

    def add_evidence(self, name: str, lh: float = 0.8, ln: float = 0.2,
                     weight: float = 1.0, source: str = "") -> Evidence:
        e = Evidence(
            name=name,
            likelihood_given_h=lh,
            likelihood_given_not_h=ln,
            weight=weight,
            source=source,
        )
        self._evidences[name] = e
        return e

    def link(self, hypothesis: str, evidence: str) -> None:
        self._dependencies[hypothesis].append(evidence)

    def update(self, hypothesis_name: str, evidence_name: str) -> float:
        h = self._hypotheses.get(hypothesis_name)
        e = self._evidences.get(evidence_name)

        if not h or not e:
            logger.warning("Bayes[%s]: unknown hypothesis '%s' or evidence '%s'",
                         self.name, hypothesis_name, evidence_name)
            return 0.0

        numerator = e.likelihood_given_h * h.posterior
        denominator = (e.likelihood_given_h * h.posterior +
                      e.likelihood_given_not_h * (1 - h.posterior))

        if denominator == 0:
            return h.posterior

        new_posterior = numerator / denominator * e.weight
        new_posterior += h.posterior * (1 - e.weight)
        new_posterior = max(0.001, min(0.999, new_posterior))

        h.evidence_log.append({
            "evidence": evidence_name,
            "likelihood": e.likelihood_given_h,
            "prior": h.posterior,
            "posterior": new_posterior,
        })
        h.posterior = new_posterior

        logger.debug("Bayes[%s]: %s | %s → posterior=%.3f",
                    self.name, hypothesis_name, evidence_name, new_posterior)
        return new_posterior

    def update_multi(self, hypothesis_name: str, evidence_names: list[str]) -> float:
        for ename in evidence_names:
            self.update(hypothesis_name, ename)
        return self.belief(hypothesis_name)

    def belief(self, hypothesis_name: str) -> float:
        h = self._hypotheses.get(hypothesis_name)
        return h.posterior if h else 0.0

    def compare_hypotheses(self, names: list[str]) -> dict[str, float]:
        return {n: self.belief(n) for n in names if n in self._hypotheses}

    def best_hypothesis(self) -> tuple[str, float]:
        if not self._hypotheses:
            return ("none", 0.0)
        best = max(self._hypotheses.items(), key=lambda x: x[1].posterior)
        return best[0], best[1].posterior

    def get_evidence_strength(self, evidence_name: str) -> float:
        e = self._evidences.get(evidence_name)
        if not e:
            return 0.0
        return abs(e.likelihood_given_h - e.likelihood_given_not_h)

    def reset_hypothesis(self, hypothesis_name: str) -> None:
        h = self._hypotheses.get(hypothesis_name)
        if h:
            h.posterior = h.prior
            h.evidence_log.clear()

    def get_stats(self) -> dict:
        return {
            "name": self.name,
            "hypotheses": len(self._hypotheses),
            "evidences": len(self._evidences),
            "best_hypothesis": self.best_hypothesis(),
            "active_dependencies": sum(len(v) for v in self._dependencies.values()),
        }


_kr_instance: Optional[KnowledgeRepresentation] = None
_kr_lock = threading.Lock()


def get_knowledge_representation(name: str = "default") -> KnowledgeRepresentation:
    global _kr_instance
    if _kr_instance is None:
        with _kr_lock:
            if _kr_instance is None:
                _kr_instance = KnowledgeRepresentation(name=name)
    return _kr_instance


_bayesian_reasoner_instance: Optional[BayesianReasoner] = None
_bayesian_lock = threading.Lock()


def get_bayesian_reasoner(name: str = "default") -> BayesianReasoner:
    global _bayesian_reasoner_instance
    if _bayesian_reasoner_instance is None:
        with _bayesian_lock:
            if _bayesian_reasoner_instance is None:
                _bayesian_reasoner_instance = BayesianReasoner(name=name)
    return _bayesian_reasoner_instance
