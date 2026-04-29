"""
产业级环境知识网络 (Industry Environmental Knowledge Network)
=========================================================

构建"产业级环境知识网络"，揭示产业链、区域的环境关联和风险传导。

核心功能：
1. 供应链环境风险穿透式审计
2. 区域环境容量"占卜"与预测
3. 排放权交易撮合
4. 产业链环境风险传导分析

Author: Hermes Desktop Team
"""

import logging
import json
import threading
import math
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class NodeType(Enum):
    """节点类型"""
    COMPANY = "company"
    FACILITY = "facility"          # 设施/工厂
    SUPPLIER = "supplier"
    PRODUCT = "product"
    MATERIAL = "material"
    PROCESS = "process"
    EMISSION_SOURCE = "emission_source"


class EdgeType(Enum):
    """边类型"""
    SUPPLIES = "supplies"          # 供应关系
    LOCATED_AT = "located_at"       # 位于
    EMITS_TO = "emits_to"          # 排放到
    AFFECTS = "affects"            # 影响
    DEPENDS_ON = "depends_on"      # 依赖
    PART_OF = "part_of"            # 是...的一部分


class RiskLevel(Enum):
    """风险等级"""
    NEGLIGIBLE = "negligible"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class NetworkNode:
    """网络节点"""
    node_id: str
    name: str
    node_type: NodeType
    properties: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NetworkEdge:
    """网络边"""
    edge_id: str
    source_id: str
    target_id: str
    edge_type: EdgeType
    weight: float = 1.0  # 权重
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SupplyChainNode:
    """供应链节点"""
    node_id: str
    company_name: str
    tier: int                      # 层级（1=直接供应商，2=二级供应商）
    industry: str
    location: Dict[str, float]     # lat, lon
    risk_score: float = 0.0
    environmental_data: Dict = field(default_factory=dict)


@dataclass
class SupplyChainAudit:
    """供应链审计报告"""
    audit_id: str
    timestamp: datetime
    target_company: str
    supplier_count: int
    total_risk_score: float
    high_risk_suppliers: List[Dict]
    emission_transfer_risks: List[Dict]
    recommendations: List[str]


@dataclass
class RegionalCapacity:
    """区域环境容量"""
    region_id: str
    region_name: str
    capacity_type: str              # air/water/soil
    total_capacity: float
    used_capacity: float
    remaining_capacity: float
    utilization_rate: float
    prediction_3month: float       # 3个月预测
    prediction_6month: float       # 6个月预测
    confidence: float = 0.85


@dataclass
class EmissionPermit:
    """排放权"""
    permit_id: str
    owner_company: str
    pollutant: str
    quantity: float                # 吨
    unit: str = "t"
    valid_from: datetime
    valid_to: datetime
    price: float = 0.0            # 元/吨
    status: str = "available"     # available/sold/expired


@dataclass
class TradeMatch:
    """交易匹配"""
    match_id: str
    seller_company: str
    buyer_company: str
    pollutant: str
    quantity: float
    suggested_price: float
    confidence: float
    savings: float                # 相对市场价的节省
    reasons: List[str] = field(default_factory=list)


@dataclass
class RegionalRiskAssessment:
    """区域风险评估"""
    assessment_id: str
    region_id: str
    timestamp: datetime
    overall_risk_level: RiskLevel
    risk_hotspots: List[Dict]      # 风险热点区域
    传导路径: List[Dict]             # 传导路径
    recommendations: List[str]


class IndustryEnvironmentalNetwork:
    """
    产业级环境知识网络

    构建和分析产业链、区域的环境关联和风险传导。

    使用示例：
    ```python
    network = IndustryEnvironmentalNetwork()

    # 1. 构建供应链网络
    network.build_supply_chain_network(company_id="automaker_001")

    # 2. 供应链环境审计
    audit = network.audit_supply_chain("automaker_001")

    # 3. 区域环境容量预测
    capacity = network.predict_region_capacity("南京江宁区")

    # 4. 排放权交易撮合
    matches = network.match_emission_trades(pollutant="NOx")

    # 5. 区域风险评估
    assessment = network.assess_regional_risk("江苏南京")
    ```
    """

    def __init__(self, knowledge_graph=None):
        self.kg = knowledge_graph

        # 网络数据
        self.nodes: Dict[str, NetworkNode] = {}
        self.edges: Dict[str, NetworkEdge] = {}
        self.supply_chains: Dict[str, List[SupplyChainNode]] = {}
        self.regional_capacities: Dict[str, RegionalCapacity] = {}
        self.emission_permits: Dict[str, EmissionPermit] = {}

        # 统计
        self._stats = {
            "total_nodes": 0,
            "total_edges": 0,
            "networks_built": 0
        }

        self._lock = threading.RLock()

        # 初始化示例网络
        self._init_sample_network()

        logger.info("初始化产业级环境知识网络")

    def _init_sample_network(self):
        """初始化示例网络数据"""
        # 示例公司节点
        companies = [
            NetworkNode("company_auto_001", "某汽车制造商", NodeType.COMPANY,
                       {"industry": "汽车制造", "annual_output": 500000}),
            NetworkNode("company_paint_001", "涂料供应商A", NodeType.SUPPLIER,
                       {"industry": "涂料", "tier": 1, "products": ["水性涂料", "溶剂型涂料"]}),
            NetworkNode("company_paint_002", "涂料供应商B", NodeType.SUPPLIER,
                       {"industry": "涂料", "tier": 1, "products": ["粉末涂料"]}),
            NetworkNode("company_steel_001", "钢材供应商", NodeType.SUPPLIER,
                       {"industry": "钢材", "tier": 1, "products": ["冷轧钢板", "镀锌板"]}),
            NetworkNode("company_chems_001", "溶剂供应商", NodeType.SUPPLIER,
                       {"industry": "化工", "tier": 2, "products": ["乙酸乙酯", "丙酮"]}),
        ]

        for node in companies:
            self.add_node(node)

        # 供应关系边
        edges = [
            NetworkEdge("edge_1", "company_paint_001", "company_auto_001",
                       EdgeType.SUPPLIES, weight=0.8,
                       properties={"annual_value": 5000, "占比": "30%"}),
            NetworkEdge("edge_2", "company_paint_002", "company_auto_001",
                       EdgeType.SUPPLIES, weight=0.5,
                       properties={"annual_value": 3000, "占比": "20%"}),
            NetworkEdge("edge_3", "company_steel_001", "company_auto_001",
                       EdgeType.SUPPLIES, weight=0.9,
                       properties={"annual_value": 8000, "占比": "40%"}),
            NetworkEdge("edge_4", "company_chems_001", "company_paint_001",
                       EdgeType.SUPPLIES, weight=0.7,
                       properties={"annual_value": 2000}),
        ]

        for edge in edges:
            self.add_edge(edge)

    def add_node(self, node: NetworkNode) -> bool:
        """添加节点"""
        with self._lock:
            self.nodes[node.node_id] = node
            self._stats["total_nodes"] = len(self.nodes)
            return True

    def add_edge(self, edge: NetworkEdge) -> bool:
        """添加边"""
        with self._lock:
            self.edges[edge.edge_id] = edge
            self._stats["total_edges"] = len(self.edges)
            return True

    def get_node(self, node_id: str) -> Optional[NetworkNode]:
        """获取节点"""
        return self.nodes.get(node_id)

    def get_neighbors(self, node_id: str, edge_type: EdgeType = None) -> List[NetworkNode]:
        """获取邻居节点"""
        neighbors = []

        for edge in self.edges.values():
            if edge_type and edge.edge_type != edge_type:
                continue

            if edge.source_id == node_id:
                neighbor = self.nodes.get(edge.target_id)
                if neighbor:
                    neighbors.append(neighbor)
            elif edge.target_id == node_id:
                neighbor = self.nodes.get(edge.source_id)
                if neighbor:
                    neighbors.append(neighbor)

        return neighbors

    def build_supply_chain_network(self, company_id: str) -> List[SupplyChainNode]:
        """
        构建供应链网络

        Args:
            company_id: 公司ID

        Returns:
            供应链节点列表
        """
        supply_chain = []

        # 查找直接供应商
        direct_suppliers = self.get_neighbors(company_id, EdgeType.SUPPLIES)

        for i, supplier in enumerate(direct_suppliers):
            node = SupplyChainNode(
                node_id=supplier.node_id,
                company_name=supplier.name,
                tier=1,
                industry=supplier.properties.get("industry", ""),
                location={"lat": 31.0 + i * 0.1, "lon": 118.0 + i * 0.1},
                risk_score=self._assess_supplier_risk(supplier)
            )
            supply_chain.append(node)

            # 查找二级供应商
            sub_suppliers = self.get_neighbors(supplier.node_id, EdgeType.SUPPLIES)
            for j, sub in enumerate(sub_suppliers):
                sub_node = SupplyChainNode(
                    node_id=sub.node_id,
                    company_name=sub.name,
                    tier=2,
                    industry=sub.properties.get("industry", ""),
                    location={"lat": 31.0 + i * 0.1 + j * 0.05,
                             "lon": 118.0 + i * 0.1 + j * 0.05},
                    risk_score=self._assess_supplier_risk(sub)
                )
                supply_chain.append(sub_node)

        self.supply_chains[company_id] = supply_chain
        self._stats["networks_built"] += 1

        return supply_chain

    def _assess_supplier_risk(self, supplier: NetworkNode) -> float:
        """评估供应商风险"""
        risk_score = 0.3  # 基础风险

        # 基于行业评估
        high_risk_industries = ["化工", "电镀", "皮革", "造纸"]
        if supplier.properties.get("industry", "") in high_risk_industries:
            risk_score += 0.3

        # 基于产品评估
        products = supplier.properties.get("products", [])
        if any(p in ["溶剂型涂料", "油性漆"] for p in products):
            risk_score += 0.2

        return min(risk_score, 1.0)

    def audit_supply_chain(self, company_id: str) -> SupplyChainAudit:
        """
        供应链环境审计

        Args:
            company_id: 公司ID

        Returns:
            审计报告
        """
        if company_id not in self.supply_chains:
            self.build_supply_chain_network(company_id)

        supply_chain = self.supply_chains.get(company_id, [])

        # 评估风险
        high_risk_suppliers = []
        emission_transfer_risks = []

        for node in supply_chain:
            if node.risk_score >= 0.6:
                high_risk_suppliers.append({
                    "supplier_id": node.node_id,
                    "supplier_name": node.company_name,
                    "industry": node.industry,
                    "risk_score": node.risk_score,
                    "risk_factors": self._get_risk_factors(node)
                })

            # 排放转移风险
            if node.industry == "化工":
                emission_transfer_risks.append({
                    "supplier_id": node.node_id,
                    "supplier_name": node.company_name,
                    "risk_type": "上游污染转移",
                    "description": f"{node.company_name}可能将环境污染转移至下游"
                })

        # 计算总风险评分
        total_risk = sum(n.risk_score for n in supply_chain) / max(len(supply_chain), 1)

        # 生成建议
        recommendations = []
        if high_risk_suppliers:
            recommendations.append(
                f"⚠️ 发现{len(high_risk_suppliers)}家高风险供应商，建议加强环境审核"
            )
        if emission_transfer_risks:
            recommendations.append(
                "🔗 检测到潜在的上游污染转移风险，建议追溯原料来源"
            )
        if not high_risk_suppliers:
            recommendations.append("✅ 供应链环境风险整体可控")

        recommendations.append("📋 建议每季度更新供应商环境评估")

        return SupplyChainAudit(
            audit_id=f"audit_{company_id}_{int(datetime.now().timestamp())}",
            timestamp=datetime.now(),
            target_company=self.nodes.get(company_id, NetworkNode("", "", NodeType.COMPANY)).name,
            supplier_count=len(supply_chain),
            total_risk_score=total_risk,
            high_risk_suppliers=high_risk_suppliers,
            emission_transfer_risks=emission_transfer_risks,
            recommendations=recommendations
        )

    def _get_risk_factors(self, node: SupplyChainNode) -> List[str]:
        """获取风险因素"""
        factors = []

        if node.industry in ["化工", "电镀", "皮革"]:
            factors.append("高污染行业")

        if node.risk_score >= 0.7:
            factors.append("历史环境违规记录")

        if node.tier >= 2:
            factors.append("二级供应商，监管难度大")

        return factors

    def predict_region_capacity(self, region_name: str,
                               capacity_type: str = "air") -> RegionalCapacity:
        """
        预测区域环境容量

        Args:
            region_name: 区域名称
            capacity_type: 容量类型（air/water/soil）

        Returns:
            区域环境容量预测
        """
        # 模拟数据
        capacity_data = {
            "air": {"total": 10000, "used": 6500},  # 吨/年
            "water": {"total": 5000, "used": 4200},
            "soil": {"total": 8000, "used": 3000}
        }

        data = capacity_data.get(capacity_type, {"total": 10000, "used": 5000})

        total = data["total"]
        used = data["used"]
        remaining = total - used
        utilization = used / total

        # 简单预测（考虑增长率）
        growth_rate = 0.05  # 假设年增长5%
        used_3month = used * (1 + growth_rate * 0.25)  # 3个月
        used_6month = used * (1 + growth_rate * 0.5)   # 6个月

        return RegionalCapacity(
            region_id=f"region_{region_name}",
            region_name=region_name,
            capacity_type=capacity_type,
            total_capacity=total,
            used_capacity=used,
            remaining_capacity=remaining,
            utilization_rate=utilization,
            prediction_3month=remaining - (used_3month - used),
            prediction_6month=remaining - (used_6month - used),
            confidence=0.85
        )

    def assess_emission_transfer(self, source_company: str,
                               target_company: str) -> Dict:
        """
        评估排放转移风险

        Args:
            source_company: 源公司
            target_company: 目标公司

        Returns:
            评估结果
        """
        # 查找供应链关系
        source_node = self.nodes.get(source_company)
        target_node = self.nodes.get(target_company)

        if not source_node or not target_node:
            return {"risk_level": "unknown", "description": "未找到公司节点"}

        # 模拟评估
        risk_factors = []

        if source_node.properties.get("industry") == "化工":
            risk_factors.append("上游化工原料可能携带污染物")

        # 地理位置接近度
        source_loc = source_node.properties.get("location", {})
        target_loc = target_node.properties.get("location", {})
        if source_loc and target_loc:
            distance = self._calculate_distance(source_loc, target_loc)
            if distance < 50:  # 50km以内
                risk_factors.append(f"地理距离近（{distance:.0f}km），大气传输风险高")

        # 综合评估
        if len(risk_factors) >= 2:
            risk_level = RiskLevel.HIGH
        elif len(risk_factors) == 1:
            risk_level = RiskLevel.MEDIUM
        else:
            risk_level = RiskLevel.LOW

        return {
            "source_company": source_node.name,
            "target_company": target_node.name,
            "risk_level": risk_level.value,
            "risk_factors": risk_factors,
            "recommendations": self._get_transfer_recommendations(risk_level)
        }

    def _calculate_distance(self, loc1: Dict, loc2: Dict) -> float:
        """计算两点间距离（km）"""
        # 简化 Haversine 公式
        R = 6371  # 地球半径

        lat1 = math.radians(loc1.get("lat", 0))
        lat2 = math.radians(loc2.get("lat", 0))
        dlat = lat2 - lat1

        lon1 = math.radians(loc1.get("lon", 0))
        lon2 = math.radians(loc2.get("lon", 0))
        dlon = lon2 - lon1

        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))

        return R * c

    def _get_transfer_recommendations(self, risk_level: RiskLevel) -> List[str]:
        """获取转移风险建议"""
        recommendations = {
            RiskLevel.HIGH: [
                "⚠️ 高风险：建议实地考察上游供应商",
                "要求供应商提供环境检测报告",
                "考虑替换为低风险供应商"
            ],
            RiskLevel.MEDIUM: [
                "⚡ 中风险：建议增加审核频率",
                "获取供应商的环境认证",
                "监控原料的环境指标"
            ],
            RiskLevel.LOW: [
                "✅ 风险可控，继续常规监控"
            ]
        }
        return recommendations.get(risk_level, [])

    def assess_regional_risk(self, region_name: str) -> RegionalRiskAssessment:
        """
        区域风险评估

        Args:
            region_name: 区域名称

        Returns:
            风险评估报告
        """
        # 查找区域内企业
        companies = [
            n for n in self.nodes.values()
            if n.node_type == NodeType.COMPANY or n.node_type == NodeType.SUPPLIER
        ]

        # 识别风险热点
        risk_hotspots = []
        传导路径 = []

        for company in companies:
            industry = company.properties.get("industry", "")
            if industry in ["化工", "电镀", "皮革", "造纸"]:
                risk_hotspots.append({
                    "company_id": company.node_id,
                    "company_name": company.name,
                    "industry": industry,
                    "risk_type": "高污染行业聚集",
                    "location": company.properties.get("location", {})
                })

        # 识别传导路径
        for edge in self.edges.values():
            source = self.nodes.get(edge.source_id)
            target = self.nodes.get(edge.target_id)
            if source and target:
                source_industry = source.properties.get("industry", "")
                target_industry = target.properties.get("industry", "")
                if source_industry == "化工" and target_industry == "制造":
                    传导路径.append({
                        "from": source.name,
                        "to": target.name,
                        "risk_type": "原料-产品传导"
                    })

        # 综合评估
        if len(risk_hotspots) >= 3:
            overall_risk = RiskLevel.HIGH
        elif len(risk_hotspots) >= 1:
            overall_risk = RiskLevel.MEDIUM
        else:
            overall_risk = RiskLevel.LOW

        recommendations = []
        if overall_risk.value >= RiskLevel.MEDIUM.value:
            recommendations.append(f"🚨 区域内有{len(risk_hotspots)}个风险热点，需重点关注")
            recommendations.append("建议建立区域环境联防联控机制")
        else:
            recommendations.append("✅ 区域环境风险整体可控")

        recommendations.append("建议定期更新区域环境容量评估")

        return RegionalRiskAssessment(
            assessment_id=f"assess_{region_name}_{int(datetime.now().timestamp())}",
            region_id=f"region_{region_name}",
            timestamp=datetime.now(),
            overall_risk_level=overall_risk,
            risk_hotspots=risk_hotspots,
            传导路径=传导路径,
            recommendations=recommendations
        )

    def register_emission_permit(self, permit: EmissionPermit) -> bool:
        """注册排放权"""
        with self._lock:
            self.emission_permits[permit.permit_id] = permit
            return True

    def match_emission_trades(self, pollutant: str,
                             buyer_company: str = None,
                             required_quantity: float = None) -> List[TradeMatch]:
        """
        排放权交易撮合

        Args:
            pollutant: 污染物类型
            buyer_company: 买方公司（可选）
            required_quantity: 需求量（可选）

        Returns:
            匹配列表
        """
        matches = []

        # 查找可交易的排放权
        available_permits = [
            p for p in self.emission_permits.values()
            if p.pollutant == pollutant and p.status == "available"
        ]

        for permit in available_permits:
            # 计算匹配度
            confidence = 0.8
            reasons = [f"卖方{permit.owner_company}有{permit.quantity}吨{permit.pollutant}排放权"]

            # 模拟市场均价
            market_price = 5000  # 元/吨

            # 计算建议价格（考虑供需关系）
            if len(available_permits) > 5:
                suggested_price = market_price * 0.9  # 供大于求，价格下降
                reasons.append("市场供应充足，价格优惠")
            elif len(available_permits) < 2:
                suggested_price = market_price * 1.2  # 供不应求，价格上涨
                reasons.append("市场供应紧张，价格偏高")
            else:
                suggested_price = market_price

            match = TradeMatch(
                match_id=f"match_{permit.permit_id}_{int(datetime.now().timestamp())}",
                seller_company=permit.owner_company,
                buyer_company=buyer_company or "待匹配",
                pollutant=permit.pollutant,
                quantity=permit.quantity,
                suggested_price=suggested_price,
                confidence=confidence,
                savings=(market_price - suggested_price) * permit.quantity,
                reasons=reasons
            )
            matches.append(match)

        # 排序
        matches.sort(key=lambda m: m.confidence, reverse=True)

        return matches

    def generate_supply_chain_report(self, company_id: str) -> Dict:
        """
        生成供应链环境报告

        Args:
            company_id: 公司ID

        Returns:
            报告
        """
        # 构建网络
        if company_id not in self.supply_chains:
            self.build_supply_chain_network(company_id)

        # 审计
        audit = self.audit_supply_chain(company_id)

        # 区域评估
        company = self.nodes.get(company_id)
        region_name = "江苏南京"  # 简化

        assessment = self.assess_regional_risk(region_name)

        return {
            "company": company.name if company else company_id,
            "generated_at": datetime.now().isoformat(),
            "supply_chain_summary": {
                "total_suppliers": audit.supplier_count,
                "high_risk_count": len(audit.high_risk_suppliers),
                "total_risk_score": audit.total_risk_score
            },
            "risk_hotspots": audit.high_risk_suppliers,
            "emission_transfer_risks": audit.emission_transfer_risks,
            "regional_assessment": {
                "risk_level": assessment.overall_risk_level.value,
                "risk_hotspots_count": len(assessment.risk_hotspots)
            },
            "recommendations": audit.recommendations
        }

    def to_dict(self) -> Dict[str, Any]:
        """导出网络状态"""
        return {
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges),
            "networks_built": self._stats["networks_built"],
            "registered_permits": len(self.emission_permits),
            "capabilities": [
                "供应链环境审计",
                "区域环境容量预测",
                "排放权交易撮合",
                "区域风险评估"
            ]
        }


# 全局单例
_network_instance: Optional[IndustryEnvironmentalNetwork] = None
_network_lock = threading.Lock()


def get_industry_network(knowledge_graph=None) -> IndustryEnvironmentalNetwork:
    """获取产业级知识网络实例"""
    global _network_instance
    if _network_instance is None:
        with _network_lock:
            if _network_instance is None:
                _network_instance = IndustryEnvironmentalNetwork(knowledge_graph)
    return _network_instance
