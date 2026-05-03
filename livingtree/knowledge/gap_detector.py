"""Knowledge gap detection and prioritized learning plans.

Analyzes the current knowledge base and produces a prioritized plan for
learning missing topics/domains.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class Gap(BaseModel):
    domain: str
    topics: List[str] = []
    priority: int


class LearningPlanItem(BaseModel):
    domain: str
    topic: str
    priority: int
    note: Optional[str] = None


class GapDetector:
    def __init__(self) -> None:
        pass

    def analyze_coverage(self, knowledge_base) -> List[Gap]:
        # Simple heuristic: domains with no documents are gaps
        domains = {}
        for doc in knowledge_base.storage.list_documents():
            dom = doc.domain or "UNKNOWN"
            domains[dom] = domains.get(dom, 0) + 1
        gaps: List[Gap] = []
        for d, count in domains.items():
            if count <= 0:
                gaps.append(Gap(domain=d, topics=[d], priority=5))
        # Add a couple of synthetic gaps if no documents exist yet
        if not domains:
            gaps.append(Gap(domain="General", topics=["Ontology", "Taxonomy"], priority=3))
        return gaps

    def find_gaps(self, knowledge_base) -> List[Gap]:
        return self.analyze_coverage(knowledge_base)

    def prioritize_learning(self, gaps: List[Gap]) -> List[LearningPlanItem]:
        plan: List[LearningPlanItem] = []
        for g in gaps:
            for t in g.topics:
                plan.append(LearningPlanItem(domain=g.domain, topic=t, priority=g.priority))
        plan.sort(key=lambda x: x.priority, reverse=True)
        return plan

    def generate_learning_plan(self, knowledge_base) -> List[LearningPlanItem]:
        gaps = self.find_gaps(knowledge_base)
        return self.prioritize_learning(gaps)

    def track_progress(self, plan: List[LearningPlanItem]) -> None:
        # Lightweight placeholder to indicate progress updates
        for item in plan:
            pass


__all__ = ["GapDetector", "Gap", "LearningPlanItem"]
