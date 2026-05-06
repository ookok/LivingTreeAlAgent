"""Bayesian Reasoner — 贝叶斯推理引擎。

数理逻辑的概率化延伸，处理不确定性推理：
  - 先验概率 → 似然 → 后验概率 (Bayes' theorem)
  - 条件概率网络 (简化贝叶斯网络)
  - 证据更新：多源证据融合

应用场景：
  - GC 决策置信度：基于 trace 证据更新 discard vs compact 的后验概率
  - 知识库事实置信度：多源证据合成
  - 冲突消解概率：多文档矛盾的概率化判定
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger


@dataclass
class Hypothesis:
    """一个假设 H — 具有先验概率，可通过证据更新后验。"""
    name: str
    prior: float = 0.5              # P(H)
    posterior: float = 0.5           # P(H|E) — current belief
    evidence_log: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def update(self, likelihood: float, evidence_name: str = "") -> None:
        """使用一个似然证据更新后验 (naive Bayes update)。"""
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
    """一条证据 E，有似然比 P(E|H)/P(E|¬H)。"""
    name: str
    likelihood_given_h: float = 0.8    # P(E|H)
    likelihood_given_not_h: float = 0.2  # P(E|¬H)
    weight: float = 1.0               # 证据权重
    source: str = ""


class BayesianReasoner:
    """贝叶斯推理机 — 概率化不确定性推理。

    核心公式: P(H|E) = P(E|H) × P(H) / P(E)
              P(E) = P(E|H)×P(H) + P(E|¬H)×(1-P(H))

    Usage:
        reasoner = BayesianReasoner()
        reasoner.add_hypothesis("use_discard", prior=0.6)
        reasoner.add_evidence("high_stale_ratio", lh=0.85, ln=0.1)
        reasoner.update("use_discard", "high_stale_ratio")
        belief = reasoner.belief("use_discard")  # → updated posterior
    """

    def __init__(self, name: str = "default"):
        self.name = name
        self._hypotheses: dict[str, Hypothesis] = {}
        self._evidences: dict[str, Evidence] = {}
        self._dependencies: dict[str, list[str]] = defaultdict(list)  # causal links

    def add_hypothesis(self, name: str, prior: float = 0.5, **metadata) -> Hypothesis:
        prior = max(0.01, min(0.99, prior))
        h = Hypothesis(name=name, prior=prior, posterior=prior, metadata=metadata)
        self._hypotheses[name] = h
        logger.debug("Bayes[%s]: hypothesis '%s' prior=%.2f", self.name, name, prior)
        return h

    def add_evidence(self, name: str, lh: float = 0.8, ln: float = 0.2,
                     weight: float = 1.0, source: str = "") -> Evidence:
        """添加证据定义。

        lh = P(E|H): 假设为真时观察到证据的概率
        ln = P(E|¬H): 假设为假时观察到证据的概率
        """
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
        """建立假设→证据的因果关系。"""
        self._dependencies[hypothesis].append(evidence)

    def update(self, hypothesis_name: str, evidence_name: str) -> float:
        """用一条证据更新假设的后验概率。

        Bayes rule: P(H|E) = P(E|H)×P(H) / [P(E|H)×P(H) + P(E|¬H)×(1-P(H))]
        """
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
        """多证据独立更新（朴素贝叶斯假设：证据条件独立）。"""
        for ename in evidence_names:
            self.update(hypothesis_name, ename)
        return self.belief(hypothesis_name)

    def belief(self, hypothesis_name: str) -> float:
        """获取当前后验信念。"""
        h = self._hypotheses.get(hypothesis_name)
        return h.posterior if h else 0.0

    def compare_hypotheses(self, names: list[str]) -> dict[str, float]:
        """比较多个假设的后验概率。"""
        return {n: self.belief(n) for n in names if n in self._hypotheses}

    def best_hypothesis(self) -> tuple[str, float]:
        """返回当前最优假设。"""
        if not self._hypotheses:
            return ("none", 0.0)
        best = max(self._hypotheses.items(), key=lambda x: x[1].posterior)
        return best[0], best[1].posterior

    def get_evidence_strength(self, evidence_name: str) -> float:
        """评估证据的区分力: |P(E|H) - P(E|¬H)|。"""
        e = self._evidences.get(evidence_name)
        if not e:
            return 0.0
        return abs(e.likelihood_given_h - e.likelihood_given_not_h)

    def reset_hypothesis(self, hypothesis_name: str) -> None:
        """复位假设到先验概率。"""
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
