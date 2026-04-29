"""
客户管理模块

管理咨询公司的客户（企业），包括：
1. 客户档案
2. 合规画像
3. 客户关系
4. 合作历史
"""

import json
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
from datetime import datetime


# ==================== 枚举定义 ====================

class ClientType(Enum):
    """客户类型"""
    DIRECT = "direct"                   # 直接客户（建设项目单位）
    AGENT = "agent"                     # 中介（咨询公司、设计院）
    GOVERNMENT = "government"          # 政府客户
    GROUP = "group"                    # 集团客户
    OTHER = "other"


class ClientLevel(Enum):
    """客户等级"""
    A = "A"                             # 战略客户
    B = "B"                             # 重要客户
    C = "C"                             # 普通客户
    D = "D"                             # 潜在客户


class ComplianceLevel(Enum):
    """合规等级"""
    COMPLIANT = "compliant"             # 完全合规
    MINOR_ISSUES = "minor_issues"       # 轻微问题
    MAJOR_ISSUES = "major_issues"       # 重大问题
    NON_COMPLIANT = "non_compliant"     # 不合规
    UNKNOWN = "unknown"


class RelationType(Enum):
    """关系类型"""
    PARENT = "parent"                  # 母公司
    SUBSIDIARY = "subsidiary"          # 子公司
    AFFILIATE = "affiliate"            # 关联公司
    SUPPLIER = "supplier"              # 供应商
    CUSTOMER = "customer"               # 客户


# ==================== 数据模型 ====================

@dataclass
class ComplianceProfile:
    """合规画像"""
    credit_level: str = ""              # 信用等级
    compliance_level: ComplianceLevel = ComplianceLevel.UNKNOWN

    # 证照信息
    has_business_license: bool = False
    has_tax_cert: bool = False
    has_environmental_permit: bool = False
    has_safety_permit: bool = False
    pollution_permit_status: str = ""   # 有效/过期/无

    # 处罚记录
    administrative_penalties: int = 0
    environmental_violations: int = 0
    safety_accidents: int = 0

    # 最后检查
    last_compliance_check: Optional[datetime] = None
    last_environmental_check: Optional[datetime] = None
    last_safety_check: Optional[datetime] = None

    # 备注
    notes: str = ""


@dataclass
class ClientRelation:
    """客户关系"""
    relation_id: str
    related_client_id: str
    relation_type: RelationType
    description: str = ""
    established_date: Optional[datetime] = None
    is_active: bool = True


@dataclass
class Client:
    """
    客户（企业）

    客户档案数据模型
    """
    client_id: str
    client_code: str                     # 客户编号

    # 基本信息
    name: str
    short_name: str = ""
    credit_code: str = ""                # 统一社会信用代码
    client_type: ClientType = ClientType.DIRECT

    # 联系方式
    contact_person: str = ""
    contact_phone: str = ""
    contact_email: str = ""
    website: str = ""

    # 地址
    registered_address: str = ""
    business_address: str = ""

    # 企业信息
    legal_person: str = ""
    registered_capital: float = 0.0
    business_scope: List[str] = field(default_factory=list)
    industry_code: str = ""             # 行业分类
    employee_count: int = 0

    # 客户分级
    client_level: ClientLevel = ClientLevel.C
    since: Optional[datetime] = None    # 首次合作时间

    # 合规画像
    compliance_profile: ComplianceProfile = field(default_factory=ComplianceProfile)

    # Enterprise Profile ID（关联到enterprise_os）
    enterprise_profile_id: str = ""

    # 客户关系
    relations: List[ClientRelation] = field(default_factory=list)

    # 客户经理
    account_manager: str = ""           # 客户经理用户ID

    # 标签
    tags: List[str] = field(default_factory=list)

    # 备注
    notes: str = ""

    # 统计
    total_projects: int = 0
    total_contract_amount: float = 0.0
    total_revenue: float = 0.0

    # 元数据
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    created_by: str = ""


# ==================== 客户分析 ====================

@dataclass
class ClientAnalysis:
    """客户分析"""
    client_id: str
    total_projects: int = 0
    total_contract_amount: float = 0.0
    total_revenue: float = 0.0
    avg_project_value: float = 0.0
    completion_rate: float = 0.0        # 项目完成率
    on_time_rate: float = 0.0           # 准时交付率
    satisfaction_score: float = 0.0     # 满意度评分

    # 合作趋势
    first_project_date: Optional[datetime] = None
    last_project_date: Optional[datetime] = None
    project_count_trend: List[int] = field(default_factory=list)  # 近年项目数

    # 业务分布
    project_type_distribution: Dict[str, int] = field(default_factory=dict)

    # 付款分析
    avg_payment_days: float = 0.0       # 平均付款天数
    outstanding_amount: float = 0.0     # 欠款金额

    # 风险分析
    risk_level: str = "LOW"             # LOW/MEDIUM/HIGH
    risk_factors: List[str] = field(default_factory=list)


# ==================== 客户画像 ====================

@dataclass
class ClientPortrait:
    """客户画像标签"""
    portrait_id: str
    client_id: str

    # 基本特征
    industry: str = ""                   # 行业特征
    scale: str = ""                      # 规模（大型/中型/小型）
    region: str = ""                     # 地区

    # 行为特征
    project_frequency: str = "medium"    # high/medium/low
    decision_making_style: str = ""     # 决策风格
    communication_preference: str = ""   # 沟通偏好

    # 偏好特征
    prefers_email: bool = False
    prefers_wechat: bool = False
    prefers_meetings: bool = False
    prefers_online: bool = False

    # 关注点
    key_concerns: List[str] = field(default_factory=list)  # 核心关切
    price_sensitivity: str = "medium"     # high/medium/low

    # 历史偏好
    preferred_delivery_format: str = ""  # 偏好的交付格式
    revision_rounds_avg: float = 0.0     # 平均修改轮次
    requires_explanation: bool = False    # 需要详细解释

    # 风险偏好
    risk_appetite: str = "medium"        # high/medium/low
    urgency_preference: str = "balanced"  # 赶工期偏好

    updated_at: datetime = field(default_factory=datetime.now)


# ==================== 客户合并/查重 ====================

@dataclass
class ClientMatch:
    """客户匹配结果"""
    match_type: str                       # exact/fuzzy/potential
    confidence: float                     # 0-1
    matched_fields: List[str] = field(default_factory=list)
    suggested_action: str = "review"     # merge/ignore/review


# ==================== 客户合并服务 ====================

class ClientDeduplicationService:
    """客户查重合并服务"""

    def __init__(self):
        self._index: Dict[str, List[str]] = {}  # hash -> [client_ids]

    def index_client(self, client: Client):
        """索引客户用于查重"""
        keys = []

        # 信用代码索引
        if client.credit_code:
            keys.append(f"credit:{client.credit_code.lower()}")

        # 名称索引
        if client.name:
            name_hash = hashlib.md5(client.name.encode()).hexdigest()[:8]
            keys.append(f"name:{name_hash}")

        # 电话索引
        if client.contact_phone:
            phone = ''.join(c for c in client.contact_phone if c.isdigit())
            if len(phone) >= 7:
                keys.append(f"phone:{phone[-7:]}")

        for key in keys:
            if key not in self._index:
                self._index[key] = []
            self._index[key].append(client.client_id)

    async def find_duplicates(self, client: Client) -> List[ClientMatch]:
        """查找重复客户"""
        matches = []
        candidates = set()

        # 信用代码匹配
        if client.credit_code:
            key = f"credit:{client.credit_code.lower()}"
            candidates.update(self._index.get(key, []))

        # 名称相似匹配
        if client.name:
            name_hash = hashlib.md5(client.name.encode()).hexdigest()[:8]
            key = f"name:{name_hash}"
            candidates.update(self._index.get(key, []))

        # 电话匹配
        if client.contact_phone:
            phone = ''.join(c for c in client.contact_phone if c.isdigit())
            if len(phone) >= 7:
                key = f"phone:{phone[-7:]}"
                candidates.update(self._index.get(key, []))

        # 生成匹配结果
        for cid in candidates:
            if cid == client.client_id:
                continue

            match = ClientMatch(
                match_type="potential",
                confidence=0.7,
                matched_fields=["name", "contact"],
                suggested_action="review"
            )
            matches.append(match)

        return matches


# ==================== 客户智能推荐 ====================

class ClientRecommendationEngine:
    """客户智能推荐引擎"""

    def __init__(self):
        self._behavior_cache: Dict[str, Dict] = {}

    async def analyze_client_behavior(self, client_id: str) -> Dict:
        """分析客户行为"""
        # TODO: 接入实际数据
        return {
            "preferred_contact_time": "weekday_morning",
            "communication_style": "formal",
            "decision_makers": ["legal", "technical"],
            "budget_cycle": "annual",
            "competitive_sensitivity": "medium"
        }

    async def recommend_next_action(
        self,
        client_id: str,
        project_id: str = None
    ) -> List[Dict]:
        """推荐下一步行动"""
        # TODO: 基于客户画像和项目状态推荐
        recommendations = []

        # 检查是否需要跟进
        recommendations.append({
            "action": "check_contract_status",
            "priority": "medium",
            "reason": "定期客户维护"
        })

        return recommendations

    async def predict_project_opportunity(
        self,
        client_id: str
    ) -> List[Dict]:
        """预测项目机会"""
        opportunities = []

        # 基于合规画像预测
        opportunities.append({
            "type": "permit_renewal",
            "confidence": 0.8,
            "timeline": "3-6个月",
            "description": "排污许可证续期"
        })

        opportunities.append({
            "type": "annual_report",
            "confidence": 0.9,
            "timeline": "12个月",
            "description": "年度监测方案"
        })

        return opportunities


# ==================== 客户分析报告 ====================

class ClientAnalysisReportGenerator:
    """客户分析报告生成器"""

    @staticmethod
    async def generate_full_report(
        client: Client,
        projects: List = None
    ) -> Dict:
        """生成完整分析报告"""
        analysis = ClientAnalysis(
            client_id=client.client_id,
            total_projects=client.total_projects,
            total_contract_amount=client.total_contract_amount,
            total_revenue=client.total_revenue
        )

        if client.total_projects > 0:
            analysis.avg_project_value = (
                client.total_contract_amount / client.total_projects
            )

        return {
            "client": {
                "client_id": client.client_id,
                "name": client.name,
                "client_level": client.client_level.value
            },
            "analysis": analysis.__dict__,
            "compliance": {
                "level": client.compliance_profile.compliance_level.value,
                "penalties": client.compliance_profile.administrative_penalties
            },
            "recommendations": [
                "考虑升级客户等级",
                "推荐环保整体解决方案"
            ]
        }


# ==================== 客户管理服务 ====================

class ClientService:
    """
    客户管理服务

    核心功能：
    1. 客户CRUD
    2. 客户关系管理
    3. 客户分析
    4. 客户推荐
    """

    def __init__(self):
        self._clients: Dict[str, Client] = {}
        self._dedup_service = ClientDeduplicationService()
        self._recommend_engine = ClientRecommendationEngine()
        self._report_generator = ClientAnalysisReportGenerator()
        self._code_counter = 0

    def _generate_client_id(self) -> str:
        """生成客户ID"""
        return f"CLT:{datetime.now().strftime('%Y%m%d%H%M%S')}"

    def _generate_client_code(self) -> str:
        """生成客户编号"""
        self._code_counter += 1
        return f"CLIENT-{self._code_counter:05d}"

    async def create_client(
        self,
        name: str,
        created_by: str,
        client_type: ClientType = ClientType.DIRECT,
        credit_code: str = "",
        contact_person: str = "",
        contact_phone: str = "",
        **kwargs
    ) -> Client:
        """创建客户"""
        client_id = self._generate_client_id()
        client_code = self._generate_client_code()

        client = Client(
            client_id=client_id,
            client_code=client_code,
            name=name,
            client_type=client_type,
            credit_code=credit_code,
            contact_person=contact_person,
            contact_phone=contact_phone,
            created_by=created_by,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

        # 设置其他属性
        for key, value in kwargs.items():
            if hasattr(client, key):
                setattr(client, key, value)

        self._clients[client_id] = client
        self._dedup_service.index_client(client)

        return client

    async def get_client(self, client_id: str) -> Optional[Client]:
        """获取客户"""
        return self._clients.get(client_id)

    async def get_client_by_credit_code(self, credit_code: str) -> Optional[Client]:
        """通过信用代码获取客户"""
        for client in self._clients.values():
            if client.credit_code == credit_code:
                return client
        return None

    async def list_clients(
        self,
        client_type: ClientType = None,
        client_level: ClientLevel = None,
        tags: List[str] = None,
        search: str = None
    ) -> List[Client]:
        """列出客户"""
        results = list(self._clients.values())

        if client_type:
            results = [c for c in results if c.client_type == client_type]

        if client_level:
            results = [c for c in results if c.client_level == client_level]

        if tags:
            results = [
                c for c in results
                if any(tag in c.tags for tag in tags)
            ]

        if search:
            search = search.lower()
            results = [
                c for c in results
                if search in c.name.lower()
                or search in (c.short_name or "").lower()
                or search in (c.contact_person or "").lower()
            ]

        return sorted(results, key=lambda x: x.updated_at, reverse=True)

    async def update_client(
        self,
        client_id: str,
        **updates
    ) -> Optional[Client]:
        """更新客户"""
        client = self._clients.get(client_id)
        if not client:
            return None

        for key, value in updates.items():
            if hasattr(client, key):
                setattr(client, key, value)

        client.updated_at = datetime.now()
        return client

    async def delete_client(self, client_id: str) -> bool:
        """删除客户"""
        if client_id in self._clients:
            del self._clients[client_id]
            return True
        return False

    async def add_relation(
        self,
        client_id: str,
        related_client_id: str,
        relation_type: RelationType,
        description: str = ""
    ) -> bool:
        """添加客户关系"""
        client = self._clients.get(client_id)
        if not client:
            return False

        relation = ClientRelation(
            relation_id=f"{client_id}:{related_client_id}",
            related_client_id=related_client_id,
            relation_type=relation_type,
            description=description,
            established_date=datetime.now()
        )

        client.relations.append(relation)
        client.updated_at = datetime.now()
        return True

    async def update_compliance_profile(
        self,
        client_id: str,
        **updates
    ) -> bool:
        """更新合规画像"""
        client = self._clients.get(client_id)
        if not client:
            return False

        for key, value in updates.items():
            if hasattr(client.compliance_profile, key):
                setattr(client.compliance_profile, key, value)

        client.updated_at = datetime.now()
        return True

    async def find_duplicates(
        self,
        name: str = None,
        credit_code: str = None,
        contact_phone: str = None
    ) -> List[ClientMatch]:
        """查找重复客户"""
        # 构造临时客户对象
        temp_client = Client(
            client_id="temp",
            client_code="temp",
            name=name or "",
            credit_code=credit_code or "",
            contact_phone=contact_phone or ""
        )

        return await self._dedup_service.find_duplicates(temp_client)

    async def get_client_analysis(self, client_id: str) -> Optional[Dict]:
        """获取客户分析"""
        client = self._clients.get(client_id)
        if not client:
            return None

        return await self._report_generator.generate_full_report(client)

    async def get_client_portrait(self, client_id: str) -> Optional[ClientPortrait]:
        """获取客户画像"""
        # TODO: 从数据库加载
        return ClientPortrait(
            portrait_id=f"portrait:{client_id}",
            client_id=client_id
        )

    async def recommend_actions(
        self,
        client_id: str,
        project_id: str = None
    ) -> List[Dict]:
        """获取推荐行动"""
        return await self._recommend_engine.recommend_next_action(
            client_id, project_id
        )

    async def predict_opportunities(self, client_id: str) -> List[Dict]:
        """预测项目机会"""
        return await self._recommend_engine.predict_project_opportunity(client_id)

    async def get_client_summary(self, client_id: str) -> Dict:
        """获取客户摘要"""
        client = self._clients.get(client_id)
        if not client:
            return {}

        return {
            "client_id": client.client_id,
            "client_code": client.client_code,
            "name": client.name,
            "short_name": client.short_name,
            "client_type": client.client_type.value,
            "client_level": client.client_level.value,
            "contact_person": client.contact_person,
            "contact_phone": client.contact_phone,
            "total_projects": client.total_projects,
            "total_contract_amount": client.total_contract_amount,
            "compliance_level": client.compliance_profile.compliance_level.value,
            "last_project": client.updated_at.isoformat()
        }


# ==================== 单例模式 ====================

_client_service: Optional[ClientService] = None


def get_client_service() -> ClientService:
    """获取客户管理服务单例"""
    global _client_service
    if _client_service is None:
        _client_service = ClientService()
    return _client_service
