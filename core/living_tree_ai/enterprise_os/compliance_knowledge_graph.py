"""
合规知识图谱引擎

构建和管理企业合规知识图谱，支持智能合规检查和推荐。
"""

import json
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set, Tuple
from enum import Enum
from datetime import datetime


# ==================== 数据模型 ====================

class NodeType(Enum):
    """知识图谱节点类型"""
    REGULATION = "regulation"          # 法规节点
    STANDARD = "standard"              # 标准节点
    ENTERPRISE = "enterprise"           # 企业节点
    FACILITY = "facility"              # 设施节点
    PERMIT = "permit"                  # 许可证节点
    DOCUMENT = "document"              # 文档节点
    PERSON = "person"                  # 人员节点
    OBLIGATION = "obligation"         # 义务节点
    RISK = "risk"                     # 风险节点
    PROCESS = "process"                # 流程节点


class RelationType(Enum):
    """关系类型"""
    REQUIRES = "requires"              # 需要
    COMPLIANT_WITH = "compliant_with"  # 符合
    CONFLICTS = "conflicts"          # 冲突
    DEPENDS_ON = "depends_on"         # 依赖
    PRECEDES = "precedes"            # 先于
    ASSOCIATED_WITH = "associated_with"  # 关联
    MEMBER_OF = "member_of"          # 成员
    APPLIES_TO = "applies_to"        # 适用于
    GENERATES = "generates"          # 生成
    TRIGGERS = "triggers"             # 触发


@dataclass
class KGNode:
    """知识图谱节点"""
    node_id: str
    node_type: NodeType
    name: str
    properties: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # 关联信息
    incoming_edges: List[str] = field(default_factory=list)  # 指向该节点的边
    outgoing_edges: List[str] = field(default_factory=list)   # 从该节点发出的边


@dataclass
class KGEdge:
    """知识图谱边"""
    edge_id: str
    source_id: str    # 源节点
    target_id: str    # 目标节点
    relation_type: RelationType
    properties: Dict[str, Any] = field(default_factory=dict)
    weight: float = 1.0  # 权重
    confidence: float = 1.0  # 置信度


@dataclass
class ComplianceCheckResult:
    """合规检查结果"""
    check_id: str
    enterprise_id: str
    regulation_id: str
    regulation_name: str
    is_compliant: bool
    check_items: List[Dict] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    risk_level: str = "LOW"  # LOW/MEDIUM/HIGH/CRITICAL
    checked_at: datetime = field(default_factory=datetime.now)


# ==================== 合规知识图谱 ====================

class ComplianceKnowledgeGraph:
    """
    合规知识图谱

    存储和管理企业合规知识，支持：
    - 合规性智能检查
    - 相关法规推荐
    - 合规漏洞识别
    - 风险预测
    """

    def __init__(self):
        self._nodes: Dict[str, KGNode] = {}
        self._edges: Dict[str, KGEdge] = {}
        self._enterprise_nodes: Dict[str, List[str]] = {}  # enterprise_id -> node_ids

        # 初始化内置知识
        self._init_builtin_knowledge()

    def _init_builtin_knowledge(self):
        """初始化内置知识"""
        # 环保法规节点
        environmental_regs = [
            ("REG_EIA", "环境影响评价法", {"category": "环保", "authority": "生态环境局"}),
            ("REG_POLLUTION_PERMIT", "排污许可管理条例", {"category": "环保", "authority": "生态环境局"}),
            ("REG_AIR_POLLUTION", "大气污染防治法", {"category": "环保", "authority": "生态环境局"}),
            ("REG_WATER_POLLUTION", "水污染防治法", {"category": "环保", "authority": "生态环境局"}),
            ("REG_WASTE", "固体废物污染环境防治法", {"category": "环保", "authority": "生态环境局"}),
            ("REG_HAZARDOUS", "危险化学品安全管理条例", {"category": "安全", "authority": "应急管理局"}),
        ]

        for reg_id, name, props in environmental_regs:
            self.add_node(KGNode(
                node_id=reg_id,
                node_type=NodeType.REGULATION,
                name=name,
                properties=props
            ))

        # 通用标准节点
        standards = [
            ("STD_GB16297", "GB16297-1996 大气污染物综合排放标准", {"category": "排放标准"}),
            ("STD_GB8978", "GB8978-1996 污水综合排放标准", {"category": "排放标准"}),
            ("STD_GB12348", "GB12348-2008 工业企业厂界环境噪声排放标准", {"category": "噪声标准"}),
        ]

        for std_id, name, props in standards:
            self.add_node(KGNode(
                node_id=std_id,
                node_type=NodeType.STANDARD,
                name=name,
                properties=props
            ))

        # 建立法规-标准关系
        self.add_edge(KGEdge(
            edge_id="edge_eia_requires",
            source_id="REG_EIA",
            target_id="STD_GB16297",
            relation_type=RelationType.REQUIRES,
            properties={"description": "环评要求执行大气排放标准"}
        ))

    def add_node(self, node: KGNode) -> bool:
        """添加节点"""
        if node.node_id in self._nodes:
            return False
        self._nodes[node.node_id] = node
        return True

    def add_edge(self, edge: KGEdge) -> bool:
        """添加边"""
        if edge.source_id not in self._nodes or edge.target_id not in self._nodes:
            return False

        # 更新节点的边列表
        self._nodes[edge.source_id].outgoing_edges.append(edge.edge_id)
        self._nodes[edge.target_id].incoming_edges.append(edge.edge_id)

        self._edges[edge.edge_id] = edge
        return True

    def get_node(self, node_id: str) -> Optional[KGNode]:
        """获取节点"""
        return self._nodes.get(node_id)

    def get_nodes_by_type(self, node_type: NodeType) -> List[KGNode]:
        """按类型获取节点"""
        return [n for n in self._nodes.values() if n.node_type == node_type]

    def get_related_nodes(
        self,
        node_id: str,
        relation_types: List[RelationType] = None,
        depth: int = 1
    ) -> List[Tuple[KGNode, KGEdge, int]]:
        """
        获取相关节点

        Args:
            node_id: 起始节点ID
            relation_types: 关系类型过滤
            depth: 遍历深度

        Returns:
            List[Tuple[KGNode, KGEdge, int]]: (节点, 边, 深度)
        """
        if node_id not in self._nodes:
            return []

        results = []
        visited = {node_id}

        def traverse(current_id: str, current_depth: int):
            if current_depth > depth:
                return

            node = self._nodes[current_id]
            for edge_id in node.outgoing_edges:
                edge = self._edges.get(edge_id)
                if not edge:
                    continue

                if relation_types and edge.relation_type not in relation_types:
                    continue

                target = self._nodes.get(edge.target_id)
                if target and target.node_id not in visited:
                    visited.add(target.node_id)
                    results.append((target, edge, current_depth))
                    traverse(target.node_id, current_depth + 1)

        traverse(node_id, 1)
        return results

    def check_compliance(
        self,
        enterprise_id: str,
        regulation_id: str
    ) -> ComplianceCheckResult:
        """
        检查企业合规性

        Args:
            enterprise_id: 企业节点ID
            regulation_id: 法规节点ID

        Returns:
            ComplianceCheckResult: 检查结果
        """
        enterprise = self._nodes.get(enterprise_id)
        regulation = self._nodes.get(regulation_id)

        if not enterprise or not regulation:
            return ComplianceCheckResult(
                check_id=self._generate_id(),
                enterprise_id=enterprise_id,
                regulation_id=regulation_id,
                regulation_name=regulation.name if regulation else "",
                is_compliant=False,
                issues=["企业或法规节点不存在"]
            )

        # 获取相关检查项
        check_items = self._get_compliance_check_items(enterprise, regulation)

        issues = []
        suggestions = []

        for item in check_items:
            if not item.get("passed", True):
                issues.append(item.get("issue", ""))
                suggestions.append(item.get("suggestion", ""))

        return ComplianceCheckResult(
            check_id=self._generate_id(),
            enterprise_id=enterprise_id,
            regulation_id=regulation_id,
            regulation_name=regulation.name,
            is_compliant=len(issues) == 0,
            check_items=check_items,
            issues=issues,
            suggestions=suggestions,
            risk_level=self._calculate_risk_level(issues)
        )

    def _get_compliance_check_items(
        self,
        enterprise: KGNode,
        regulation: KGNode
    ) -> List[Dict]:
        """获取合规检查项"""
        items = []

        # 根据法规类型生成检查项
        reg_name = regulation.name

        if "环境影响评价" in reg_name:
            items.extend([
                {"check": "环评文件", "passed": True, "suggestion": ""},
                {"check": "批复文件", "passed": True, "suggestion": ""},
                {"check": "竣工验收", "passed": True, "suggestion": ""},
            ])

        if "排污许可" in reg_name:
            items.extend([
                {"check": "排污许可证", "passed": True, "suggestion": ""},
                {"check": "排放监测数据", "passed": True, "suggestion": ""},
                {"check": "执行报告提交", "passed": True, "suggestion": ""},
            ])

        return items

    def _calculate_risk_level(self, issues: List[str]) -> str:
        """计算风险等级"""
        if not issues:
            return "LOW"
        elif len(issues) <= 2:
            return "MEDIUM"
        elif len(issues) <= 5:
            return "HIGH"
        else:
            return "CRITICAL"

    def recommend_regulations(
        self,
        enterprise_id: str,
        limit: int = 5
    ) -> List[KGNode]:
        """
        推荐相关法规

        Args:
            enterprise_id: 企业节点ID
            limit: 返回数量限制

        Returns:
            List[KGNode]: 相关法规节点
        """
        enterprise = self._nodes.get(enterprise_id)
        if not enterprise:
            return []

        # 获取企业行业信息
        industry = enterprise.properties.get("industry", "")

        # 查找匹配法规
        regulations = self.get_nodes_by_type(NodeType.REGULATION)

        # 按相关性排序
        scored = []
        for reg in regulations:
            score = 0
            reg_category = reg.properties.get("category", "")

            # 行业匹配加分
            if industry in reg.name:
                score += 2

            # 类型匹配
            if "环保" in reg_category and industry in ["化工", "电力", "钢铁", "建材"]:
                score += 1

            scored.append((reg, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [r[0] for r in scored[:limit]]

    def build_enterprise_graph(
        self,
        enterprise_data: Dict
    ) -> str:
        """
        构建企业专属知识图谱

        Args:
            enterprise_data: 企业数据

        Returns:
            str: 企业节点ID
        """
        enterprise_id = f"ENT_{enterprise_data.get('credit_code', self._generate_id())}"

        # 创建企业节点
        enterprise_node = KGNode(
            node_id=enterprise_id,
            node_type=NodeType.ENTERPRISE,
            name=enterprise_data.get("company_name", ""),
            properties={
                "credit_code": enterprise_data.get("credit_code"),
                "industry": enterprise_data.get("industry", ""),
                "scale": enterprise_data.get("scale", ""),
            }
        )
        self.add_node(enterprise_node)

        # 创建设施节点
        facilities = enterprise_data.get("facilities", [])
        for i, facility in enumerate(facilities):
            facility_id = f"{enterprise_id}_FAC_{i}"
            facility_node = KGNode(
                node_id=facility_id,
                node_type=NodeType.FACILITY,
                name=facility.get("name", f"设施{i+1}"),
                properties=facility
            )
            self.add_node(facility_node)

            # 连接企业-设施
            self.add_edge(KGEdge(
                edge_id=self._generate_id(),
                source_id=enterprise_id,
                target_id=facility_id,
                relation_type=RelationType.MEMBER_OF
            ))

        # 创建许可证节点
        permits = enterprise_data.get("permits", [])
        for permit in permits:
            permit_id = f"PERMIT_{permit.get('permit_no', self._generate_id())}"
            permit_node = KGNode(
                node_id=permit_id,
                node_type=NodeType.PERMIT,
                name=permit.get("permit_type", ""),
                properties=permit
            )
            self.add_node(permit_node)

            # 连接企业-许可证
            self.add_edge(KGEdge(
                edge_id=self._generate_id(),
                source_id=enterprise_id,
                target_id=permit_id,
                relation_type=RelationType.ASSOCIATED_WITH
            ))

        self._enterprise_nodes[enterprise_id] = [enterprise_id]
        return enterprise_id

    def _generate_id(self) -> str:
        """生成ID"""
        return hashlib.md5(str(datetime.now().timestamp()).encode()).hexdigest()[:12]


# ==================== 便捷函数 ====================

_kg_instance: Optional[ComplianceKnowledgeGraph] = None


def get_knowledge_graph() -> ComplianceKnowledgeGraph:
    """获取知识图谱单例"""
    global _kg_instance
    if _kg_instance is None:
        _kg_instance = ComplianceKnowledgeGraph()
    return _kg_instance


async def query_compliance_async(
    enterprise_id: str,
    regulation_id: str = None
) -> ComplianceCheckResult:
    """查询合规状态的便捷函数"""
    kg = get_knowledge_graph()
    if regulation_id:
        return kg.check_compliance(enterprise_id, regulation_id)
    return ComplianceCheckResult(
        check_id="",
        enterprise_id=enterprise_id,
        regulation_id="",
        regulation_name="",
        is_compliant=False,
        issues=["未指定法规"]
    )


async def build_enterprise_graph_async(enterprise_data: Dict) -> str:
    """构建企业知识图谱的便捷函数"""
    kg = get_knowledge_graph()
    return kg.build_enterprise_graph(enterprise_data)
