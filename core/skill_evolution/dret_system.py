"""
Document-Driven Recursive Expert Training (DRET)
文档驱动的递归专家训练系统

核心功能：
1. 文档解析与知识空白检测
2. 矛盾发现与辩论机制
3. 递归补课（知识库 + 深度搜索）
4. 多专家辩论引擎
5. 知识图谱构建
"""

import json
import re
import time
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable
from enum import Enum
from pathlib import Path
from collections import defaultdict

# ============ 枚举定义 ============

class RecursionLevel(Enum):
    """递归层级"""
    SURFACE = 1      # 表层：仅检测空白
    SHALLOW = 2      # 浅层：基础搜索补课
    DEEP = 3         # 深层：深度搜索 + 辩论
    EXPERT = 4       # 专家级：完整递归

class GapType(Enum):
    """知识空白类型"""
    DEFINITION = "definition"        # 定义缺失
    PROCEDURE = "procedure"         # 步骤缺失
    COMPARISON = "comparison"        # 对比缺失
    CAUSATION = "causation"         # 因果缺失
    EXAMPLE = "example"              # 示例缺失
    REFERENCE = "reference"          # 引用缺失

class ConflictLevel(Enum):
    """矛盾级别"""
    FATAL = "fatal"      # 致命矛盾
    WARNING = "warning"   # 警告矛盾
    HINT = "hint"        # 提示矛盾

class DebateRole(Enum):
    """辩论角色"""
    OPTIMIST = "optimist"      # 乐观派
    SKEPTIC = "skeptic"        # 质疑派
    SYNTHESIZER = "synthesizer" # 综合派
    HISTORIAN = "historian"    # 历史派


# ============ 数据结构 ============

@dataclass
class KnowledgeGap:
    """知识空白"""
    gap_id: str
    gap_type: GapType
    description: str
    related_entities: List[str] = field(default_factory=list)
    recursion_level: int = 1
    filled: bool = False
    fill_content: str = ""
    fill_sources: List[str] = field(default_factory=list)


@dataclass
class KnowledgeConflict:
    """知识矛盾"""
    conflict_id: str
    level: ConflictLevel
    statement_a: str
    statement_b: str
    evidence_a: List[str] = field(default_factory=list)
    evidence_b: List[str] = field(default_factory=list)
    resolution: str = ""
    resolved: bool = False


@dataclass
class DebateResult:
    """辩论结果"""
    topic: str
    perspectives: Dict[DebateRole, str]
    consensus: str
    confidence: float
    key_points: List[str]


@dataclass
class LearningReport:
    """学习报告"""
    doc_id: str
    gaps_found: int
    gaps_filled: int
    conflicts_found: int
    conflicts_resolved: int
    debate_rounds: int
    knowledge_graph_nodes: int
    knowledge_graph_edges: int
    total_time: float
    recursion_levels_used: List[int]


# ============ 核心组件 ============

class GapDetector:
    """知识空白检测器"""

    # 空白检测模式 - 增强版
    GAP_PATTERNS = [
        # 未定义的概念
        (r"使用\s*(\w+)\s*进行", GapType.DEFINITION, "未说明 '{0}' 是什么"),
        (r"通过\s*(\w+)\s*实现", GapType.DEFINITION, "未解释 '{0}' 的原理"),
        (r"调用\s*(\w+)\s*函数", GapType.DEFINITION, "未说明 '{0}' 函数的作用"),
        (r"基于\s*(\w+)\s*技术", GapType.DEFINITION, "未介绍 '{0}' 技术背景"),
        # 缺失步骤
        (r"首先|第一步", GapType.PROCEDURE, "可能存在步骤缺失"),
        (r"首先.*然后", GapType.PROCEDURE, "步骤链不完整"),
        # 缺失对比
        (r"比\s*(\w+)\s*[更]*好", GapType.COMPARISON, "未说明与 '{0}' 的对比基准"),
        (r"优于\s*(\w+)", GapType.COMPARISON, "未提供与 '{0}' 的详细对比"),
        # 缺失原因
        (r"因此|所以|导致|由于", GapType.CAUSATION, "因果关系需要更明确的解释"),
        # 缺失示例
        (r"例如|比如|像.*这样", GapType.EXAMPLE, "缺乏具体示例"),
        # 缺失引用
        (r"参见|参考|详见", GapType.REFERENCE, "引用来源未明确标注"),
    ]

    def __init__(self, llm_client=None):
        self.llm = llm_client

    def detect_gaps(self, content: str, max_gaps: int = 20) -> List[KnowledgeGap]:
        """检测知识空白"""
        gaps = []
        gap_id = 0
        seen_descriptions = set()

        # 模式匹配检测
        for pattern, gap_type, template in self.GAP_PATTERNS:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                if len(gaps) >= max_gaps:
                    break

                # 提取相关实体
                entities = []
                if match.groups():
                    entities = [g for g in match.groups() if g]

                # 生成描述
                desc = template.format(*entities) if entities else template

                # 去重
                if desc in seen_descriptions:
                    continue
                seen_descriptions.add(desc)

                gap = KnowledgeGap(
                    gap_id=f"gap_{gap_id:04d}",
                    gap_type=gap_type,
                    description=desc,
                    related_entities=entities,
                    recursion_level=1
                )
                gaps.append(gap)
                gap_id += 1

        # 如果没有检测到，添加默认空白检测
        if not gaps:
            # 检测可能的知识点（标题或技术术语）
            tech_terms = re.findall(r'`([^`]+)`|(\b[A-Z][a-zA-Z]+(?:\+?|Plus)?(?:\d+\.\d+)?\b)', content)
            if tech_terms:
                for term in tech_terms[:3]:
                    actual_term = term[0] or term[1]
                    if actual_term and len(actual_term) > 2:
                        gaps.append(KnowledgeGap(
                            gap_id=f"gap_{gap_id:04d}",
                            gap_type=GapType.DEFINITION,
                            description=f"未详细解释 '{actual_term}'",
                            related_entities=[actual_term],
                            recursion_level=1
                        ))
                        gap_id += 1

        # LLM 深度检测（如果可用）
        if self.llm and len(gaps) < max_gaps:
            llm_gaps = self._llm_detect(content, max_gaps - len(gaps))
            gaps.extend(llm_gaps)

        return gaps[:max_gaps]

    def _llm_detect(self, content: str, limit: int) -> List[KnowledgeGap]:
        """使用 LLM 深度检测"""
        # 实现 LLM 调用逻辑
        return []


class ConflictFinder:
    """矛盾发现器"""

    def __init__(self, llm_client=None):
        self.llm = llm_client

    def find_conflicts(self, content: str, external_kb=None) -> List[KnowledgeConflict]:
        """发现矛盾"""
        conflicts = []

        # 1. 内部矛盾检测
        internal_conflicts = self._find_internal_conflicts(content)
        conflicts.extend(internal_conflicts)

        # 2. 外部矛盾检测（如果有知识库）
        if external_kb:
            external_conflicts = self._find_external_conflicts(content, external_kb)
            conflicts.extend(external_conflicts)

        return conflicts

    def _find_internal_conflicts(self, content: str) -> List[KnowledgeConflict]:
        """检测内部矛盾"""
        conflicts = []

        # 量化词矛盾检测 - 简化版本
        contradiction_pairs = [
            ("必须", "可以"),
            ("总是", "有时"),
            ("所有", "某些"),
            ("从不", "经常"),
            ("完全", "部分"),
        ]

        for word_a, word_b in contradiction_pairs:
            # 简单模式：检测两个对立词是否同时存在
            matches_a = re.findall(rf".{{0,50}}{word_a}.{{0,50}}", content[:500])
            matches_b = re.findall(rf".{{0,50}}{word_b}.{{0,50}}", content[:500])

            if matches_a and matches_b:
                conflicts.append(KnowledgeConflict(
                    conflict_id=f"conflict_{len(conflicts):04d}",
                    level=ConflictLevel.WARNING,
                    statement_a=f"声明包含: {word_a}",
                    statement_b=f"声明包含: {word_b}",
                    evidence_a=matches_a[:2],
                    evidence_b=matches_b[:2]
                ))

        return conflicts

        return conflicts

    def _find_external_conflicts(self, content: str, kb) -> List[KnowledgeConflict]:
        """检测外部矛盾"""
        # 实现外部知识库对比
        return []


class MultiDebater:
    """多专家辩论引擎"""

    ROLES = {
        DebateRole.OPTIMIST: "你是一个乐观的技术倡导者，总是看到新技术的优势和潜力。",
        DebateRole.SKEPTIC: "你是一个严谨的技术质疑者，善于发现风险、局限和潜在问题。",
        DebateRole.SYNTHESIZER: "你是一个中立的技术分析师，擅长权衡利弊、形成客观结论。",
        DebateRole.HISTORIAN: "你是一个技术历史学家，擅长引用历史案例进行对比分析。",
    }

    ROLE_DESCRIPTIONS = {
        "optimist": "乐观派",
        "skeptic": "质疑派",
        "synthesizer": "综合派",
        "historian": "历史派",
    }

    def __init__(self, llm_client=None):
        self.llm = llm_client
        self.max_rounds = 3

    def debate(self, topic: str, context: str = "") -> DebateResult:
        """执行多专家辩论"""
        perspectives = {}

        for role in DebateRole:
            perspective = self._generate_perspective(topic, context, role)
            perspectives[role] = perspective

        # 综合各方观点形成共识
        consensus = self._synthesize(perspectives, topic)

        return DebateResult(
            topic=topic,
            perspectives=perspectives,
            consensus=consensus,
            confidence=0.8,
            key_points=self._extract_key_points(consensus)
        )

    def _generate_perspective(self, topic: str, context: str, role: DebateRole) -> str:
        """生成特定角色的观点"""
        role_desc = self.ROLES.get(role, "")
        role_name = self.ROLE_DESCRIPTIONS.get(role.value, role.value)

        # 模板化观点（无 LLM 时）
        templates = {
            DebateRole.OPTIMIST: f"[{role_name}] {topic} 具有显著优势：自动化程度高、效率提升明显、多 Agent 协同增强了能力边界。",
            DebateRole.SKEPTIC: f"[{role_name}] {topic} 存在风险：依赖特定环境、错误传播可能、调试困难、学习曲线陡峭。",
            DebateRole.SYNTHESIZER: f"[{role_name}] {topic} 需要权衡：优势在于效率，劣势在于复杂度和可控性。建议选择性使用。",
            DebateRole.HISTORIAN: f"[{role_name}] 对比历史 AI 工具演进：自动化工具从单步执行到多步协作是必然趋势，但需要保持人类监督。",
        }

        return templates.get(role, f"[{role_name}] 关于 {topic} 的观点")

    def _synthesize(self, perspectives: Dict[DebateRole, str], topic: str) -> str:
        """综合观点形成共识"""
        return f"综合分析: {topic} 需要权衡多方因素后做出判断。"

    def _extract_key_points(self, consensus: str) -> List[str]:
        """提取关键论点"""
        return [consensus]


class RecursiveLearner:
    """递归学习控制器"""

    def __init__(
        self,
        max_depth: int = 3,
        kb_layer=None,
        deep_search=None,
        llm_client=None
    ):
        self.max_depth = max_depth
        self.kb = kb_layer          # 知识库补课
        self.deep_search = deep_search  # 深度搜索
        self.llm = llm_client
        self.gap_detector = GapDetector(llm_client)
        self.conflict_finder = ConflictFinder(llm_client)
        self.debater = MultiDebater(llm_client)

    def learn_from_document(
        self,
        doc_content: str,
        doc_id: str = "doc_001"
    ) -> LearningReport:
        """从文档递归学习"""
        start_time = time.time()
        report = LearningReport(
            doc_id=doc_id,
            gaps_found=0,
            gaps_filled=0,
            conflicts_found=0,
            conflicts_resolved=0,
            debate_rounds=0,
            knowledge_graph_nodes=0,
            knowledge_graph_edges=0,
            total_time=0,
            recursion_levels_used=[]
        )

        # Phase 1: 空白检测
        gaps = self.gap_detector.detect_gaps(doc_content)
        report.gaps_found = len(gaps)

        # Phase 2: 矛盾发现
        conflicts = self.conflict_finder.find_conflicts(doc_content)
        report.conflicts_found = len(conflicts)

        # Phase 3: 递归补课
        filled_gaps = self._recursive_fill(gaps, current_depth=0, report=report)

        # Phase 4: 矛盾辩论解决
        resolved = self._resolve_conflicts(conflicts, report)

        # Phase 5: 构建知识图谱
        nodes, edges = self._build_knowledge_graph(doc_content, filled_gaps)
        report.knowledge_graph_nodes = nodes
        report.knowledge_graph_edges = edges

        report.total_time = time.time() - start_time

        return report

    def _recursive_fill(
        self,
        gaps: List[KnowledgeGap],
        current_depth: int,
        report: LearningReport
    ) -> List[KnowledgeGap]:
        """递归补课"""
        if current_depth >= self.max_depth or not gaps:
            return gaps

        report.recursion_levels_used.append(current_depth)
        filled = []

        for gap in gaps:
            fill_result = self._fill_single_gap(gap, current_depth)
            if fill_result:
                filled.append(fill_result)
                report.gaps_filled += 1

                # 检查是否需要进一步递归
                if fill_result.filled and current_depth < self.max_depth:
                    # 对补全内容再次检测空白
                    sub_gaps = self.gap_detector.detect_gaps(
                        fill_result.fill_content,
                        max_gaps=5
                    )
                    # 递归填充子空白
                    self._recursive_fill(sub_gaps, current_depth + 1, report)

        return filled

    def _fill_single_gap(self, gap: KnowledgeGap, depth: int) -> Optional[KnowledgeGap]:
        """填充单个空白"""
        gap.recursion_level = depth

        # 方法1: 知识库搜索
        if self.kb:
            kb_results = self.kb.search(gap.description, top_k=3)
            if kb_results:
                gap.fill_content = kb_results[0]["content"]
                gap.filled = True
                gap.fill_sources.extend([r.get("source", "") for r in kb_results])
                return gap

        # 方法2: 深度搜索
        if self.deep_search:
            search_results = self.deep_search.search(gap.description)
            if search_results:
                gap.fill_content = search_results[0]["content"]
                gap.filled = True
                gap.fill_sources.extend([r.get("url", "") for r in search_results])
                return gap

        # 方法3: LLM 生成
        if self.llm:
            gap.fill_content = f"基于 {gap.description} 的深度分析..."
            gap.filled = True
            return gap

        return None

    def _resolve_conflicts(
        self,
        conflicts: List[KnowledgeConflict],
        report: LearningReport
    ) -> int:
        """通过辩论解决矛盾"""
        resolved = 0

        for conflict in conflicts:
            # 使用多专家辩论
            debate_result = self.debater.debate(
                topic=f"{conflict.statement_a} vs {conflict.statement_b}",
                context=f"证据A: {conflict.evidence_a}\n证据B: {conflict.evidence_b}"
            )

            conflict.resolution = debate_result.consensus
            conflict.resolved = True
            resolved += 1
            report.debate_rounds += 1

        return resolved

    def _build_knowledge_graph(
        self,
        content: str,
        filled_gaps: List[KnowledgeGap]
    ) -> tuple:
        """构建知识图谱"""
        # 简化实现：统计节点和边
        nodes = len(filled_gaps) + 1
        edges = len(filled_gaps)
        return nodes, edges


class KnowledgeGraphBuilder:
    """知识图谱构建器"""

    def __init__(self):
        self.nodes = []
        self.edges = []

    def build_from_text(self, content: str) -> Dict[str, Any]:
        """从文本构建知识图谱"""
        # 实体识别
        entities = self._extract_entities(content)

        # 关系抽取
        relations = self._extract_relations(content, entities)

        # 构建图谱
        graph = {
            "nodes": [
                {"id": e, "type": "entity", "label": e}
                for e in entities
            ],
            "edges": [
                {"from": r[0], "to": r[2], "type": r[1], "label": r[1]}
                for r in relations
            ]
        }

        return graph

    def _extract_entities(self, content: str) -> List[str]:
        """提取实体"""
        # 简化：提取所有名词短语
        entities = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', content)
        return list(set(entities))[:50]  # 限制数量

    def _extract_relations(self, content: str, entities: List[str]) -> List[tuple]:
        """抽取关系"""
        relations = []
        relation_patterns = [
            (r'(\w+)\s+是\s+(\w+)', 'is_a'),
            (r'(\w+)\s+用于\s+(\w+)', 'used_for'),
            (r'(\w+)\s+基于\s+(\w+)', 'based_on'),
        ]

        for pattern, rel_type in relation_patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                if match.group(1) in entities and match.group(2) in entities:
                    relations.append((match.group(1), rel_type, match.group(2)))

        return relations


# ============ 主入口 ============

def create_dret_system(
    max_recursion_depth: int = 3,
    llm_client=None,
    kb_layer=None,
    deep_search=None
) -> RecursiveLearner:
    """创建 DRET 系统"""
    return RecursiveLearner(
        max_depth=max_recursion_depth,
        kb_layer=kb_layer,
        deep_search=deep_search,
        llm_client=llm_client
    )


# ============ 使用示例 ============

if __name__ == "__main__":
    # 示例文档（OpenCode 安装指南）
    sample_doc = """
    OpenCode 是一个 AI 代码助手，支持以下功能：

    1. 安装: npm install -g opencode-ai
    2. 配置 oh-my-opencode: bunx oh-my-opencode install
    3. 使用 ultrawork 模式可以全自动完成任务

    特点：
    - 支持多 Agent 协同
    - 支持 Tab 切换 (plan/build)
    - 支持 /init 生成 AGENTS.md

    注意：需要先安装 Node.js 环境
    """

    # 创建系统
    dret = create_dret_system(max_recursion_depth=3)

    # 执行学习
    report = dret.learn_from_document(sample_doc, doc_id="opencode_guide")

    # 输出报告
    print(f"""
    ============== Learning Report ==============
    Doc ID: {report.doc_id}
    Gaps Found: {report.gaps_found}
    Gaps Filled: {report.gaps_filled}
    Conflicts Found: {report.conflicts_found}
    Conflicts Resolved: {report.conflicts_resolved}
    Debate Rounds: {report.debate_rounds}
    Knowledge Graph: {report.knowledge_graph_nodes} nodes, {report.knowledge_graph_edges} edges
    Total Time: {report.total_time:.2f}s
    Recursion Levels: {report.recursion_levels_used}
    =============================================
    """)
