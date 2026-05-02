"""
多代理分析器 (Multi-Agent Analyzer)

并行分析和协作：
- 任务分派到多个分析代理
- 并行处理大文本
- 结果聚合和冲突解决
"""

import concurrent.futures
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class AnalysisFocus(Enum):
    STRUCTURE = "structure"
    SEMANTICS = "semantics"
    QUALITY = "quality"
    SECURITY = "security"
    PERFORMANCE = "performance"


@dataclass
class AgentAnalysis:
    agent_id: str
    focus: AnalysisFocus
    findings: List[str] = field(default_factory=list)
    confidence: float = 0.0


@dataclass
class AggregatedAnalysis:
    topic: str
    agent_analyses: List[AgentAnalysis] = field(default_factory=list)
    merged_findings: List[str] = field(default_factory=list)
    conflicts: List[Dict[str, Any]] = field(default_factory=list)


class MultiAgentAnalyzer:

    def __init__(self, num_agents: int = 3):
        self.num_agents = num_agents
        self._agents: Dict[str, Callable[[str, AnalysisFocus],
                                         AgentAnalysis]] = {}
        self._init_default_agents()

    def _init_default_agents(self):
        self.register_agent("struct_agent",
                           self._structure_agent)
        self.register_agent("semantic_agent",
                           self._semantic_agent)
        self.register_agent("quality_agent",
                           self._quality_agent)

    def register_agent(self, agent_id: str,
                       analyze_func: Callable):
        self._agents[agent_id] = analyze_func

    def analyze(self, content: str, topic: str = ""
                ) -> AggregatedAnalysis:
        agents = list(self._agents.items())[:self.num_agents]
        foci = list(AnalysisFocus)[:len(agents)]

        tasks = [(agent_id, func, focus)
                 for (agent_id, func), focus in zip(agents, foci)]

        with concurrent.futures.ThreadPoolExecutor(
                max_workers=len(tasks)) as executor:
            futures = {
                executor.submit(func, content, focus): agent_id
                for agent_id, func, focus in tasks
            }

            analyses = []
            for future in concurrent.futures.as_completed(futures):
                try:
                    result = future.result()
                    analyses.append(result)
                except Exception as e:
                    logger.error(f"代理分析失败: {e}")

        merged = self._merge_analyses(analyses)
        merged.topic = topic or content[:50]

        return merged

    def _structure_agent(self, content: str,
                         focus: AnalysisFocus) -> AgentAnalysis:
        findings = []
        lines = content.splitlines()

        if 'class ' in content or 'def ' in content:
            findings.append("检测到结构化代码元素")
        if len(lines) > 50:
            findings.append(f"文档较长: {len(lines)} 行")

        return AgentAnalysis(
            agent_id="struct_agent", focus=focus,
            findings=findings, confidence=0.7 if findings else 0.4)

    def _semantic_agent(self, content: str,
                        focus: AnalysisFocus) -> AgentAnalysis:
        findings = []

        if '?' in content:
            findings.append("包含疑问或待解决问题")
        if any(k in content.lower() for k in
               ['分析', '评估', '优化']):
            findings.append("检测到分析或优化意图")

        return AgentAnalysis(
            agent_id="semantic_agent", focus=focus,
            findings=findings, confidence=0.6)

    def _quality_agent(self, content: str,
                       focus: AnalysisFocus) -> AgentAnalysis:
        findings = []

        if 'TODO' in content or 'FIXME' in content:
            findings.append("存在待办事宜标记")
        if content.count('pass') > 3:
            findings.append("存在多处占位代码")

        return AgentAnalysis(
            agent_id="quality_agent", focus=focus,
            findings=findings, confidence=0.5)

    def _merge_analyses(self, analyses: List[AgentAnalysis]
                        ) -> AggregatedAnalysis:
        merged = AggregatedAnalysis(topic="", agent_analyses=analyses)
        all_findings = []
        confidence_sum = 0

        for analysis in analyses:
            all_findings.extend(analysis.findings)
            confidence_sum += analysis.confidence

        merged.merged_findings = list(set(all_findings))
        return merged


__all__ = ["AnalysisFocus", "AgentAnalysis", "AggregatedAnalysis",
          "MultiAgentAnalyzer"]
