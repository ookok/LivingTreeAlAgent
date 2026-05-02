"""
类比推理器 (Analogical Reasoner)

基于结构映射理论实现领域间的类比推理：
- 源域到目标域的知识迁移
- 结构相似性分析
- 类比匹配和推断
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .reasoning_coordinator import ReasoningResult

logger = logging.getLogger(__name__)


@dataclass
class AnalogyCase:
    case_id: str
    domain: str
    description: str
    structure: Dict[str, Any] = field(default_factory=dict)
    outcome: str = ""
    relevance_score: float = 0.0


@dataclass
class AnalogyMapping:
    source_case: AnalogyCase
    target_query: str
    mapped_elements: Dict[str, str] = field(default_factory=dict)
    similarity_score: float = 0.0
    inferred_conclusion: str = ""


class AnalogicalReasoner:

    def __init__(self):
        self._case_base: Dict[str, AnalogyCase] = {}
        self._init_example_cases()

    def _init_example_cases(self):
        cases = [
            AnalogyCase(
                case_id="case_01",
                domain="软件开发",
                description="微服务架构将一个大型单体应用拆分为多个小型独立服务",
                structure={
                    "problem": "单体应用难以扩展和维护",
                    "solution": "拆分为小服务",
                    "benefit": "独立部署和扩展",
                    "challenge": "服务间通信复杂性"},
                outcome="提高了灵活性和可维护性", relevance_score=0.8),
            AnalogyCase(
                case_id="case_02",
                domain="组织管理",
                description="扁平化管理减少层级，提高决策效率",
                structure={
                    "problem": "层级过多导致决策缓慢",
                    "solution": "减少层级",
                    "benefit": "加快决策速度",
                    "challenge": "管理幅度增大"},
                outcome="提高了组织效率", relevance_score=0.7),
        ]
        for case in cases:
            self._case_base[case.case_id] = case

    def add_case(self, case: AnalogyCase):
        self._case_base[case.case_id] = case

    def reason(self, query: str, context: Dict[str, Any] = None) -> ReasoningResult:
        matches = self._find_analogical_matches(query)

        if not matches:
            return ReasoningResult(
                task_id="analogy_default",
                domain=None,
                engine="analogical_reasoner",
                conclusion=f"未找到合适的类比案例来推理: {query[:100]}",
                reasoning_chain=["未匹配到类比"],
                confidence=0.2)

        best = matches[0]
        mapping = self._build_mapping(best, query)
        conclusion = f"基于'{best.domain}'领域的类比分析：\n"
        conclusion += f"类比案例: {best.description}\n"
        conclusion += f"相似度: {best.similarity_score:.2f}\n"
        conclusion += f"推断: {mapping.inferred_conclusion}"

        return ReasoningResult(
            task_id="analogy_result",
            domain=None,
            engine="analogical_reasoner",
            conclusion=conclusion,
            reasoning_chain=[
                f"检索案例库({len(self._case_base)}个)",
                f"匹配到 {len(matches)} 个相关案例",
                f"最佳匹配: {best.case_id} (分数 {best.similarity_score:.2f})"],
            confidence=min(0.9, best.similarity_score),
            metadata={"matched_case": best.case_id})

    def _find_analogical_matches(self, query: str) -> List[AnalogyMapping]:
        mappings = []
        for case in self._case_base.values():
            score = self._calculate_similarity(case, query)
            if score > 0.3:
                mapping = AnalogyMapping(
                    source_case=case,
                    target_query=query,
                    similarity_score=score,
                    mapped_elements=self._extract_mappings(case, query),
                    inferred_conclusion=f"类似{case.domain}领域中的案例，可预期: {case.outcome}")
                mappings.append(mapping)

        mappings.sort(key=lambda m: -m.similarity_score)
        return mappings[:3]

    def _calculate_similarity(self, case: AnalogyCase, query: str) -> float:
        query_lower = query.lower()
        score = 0.0

        for key, value in case.structure.items():
            if isinstance(value, str):
                words = set(value.lower().split())
                query_words = set(query_lower.split())
                overlap = words & query_words
                if overlap:
                    score += len(overlap) / max(len(words), 1) * 0.3

        score *= case.relevance_score
        return min(1.0, score)

    def _extract_mappings(self, case: AnalogyCase, query: str) -> Dict[str, str]:
        return {k: str(v)[:100] for k, v in case.structure.items()}

    def _build_mapping(self, mapping: AnalogyMapping, query: str) -> AnalogyMapping:
        return mapping


__all__ = ["AnalogyCase", "AnalogyMapping", "AnalogicalReasoner"]
