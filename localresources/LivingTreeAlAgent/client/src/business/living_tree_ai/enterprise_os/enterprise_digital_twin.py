"""
企业数字孪生核心架构

为企业创建动态的八维数字孪生体，实时映射企业全生命周期状态。
"""

import json
import hashlib
import asyncio
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set
from enum import Enum
from datetime import datetime


# ==================== 数据模型 ====================

class LifecycleStage(Enum):
    """企业生命周期阶段"""
    INCUBATION = "incubation"           # 孕育与诞生
    CONSTRUCTION = "construction"       # 准入与建设
    OPERATION = "operation"             # 运营与生产
    MARKETING = "marketing"             # 市场与经营
    HR_ADMIN = "hr_admin"              # 人力与组织
    FINANCE = "finance"                # 财税与审计
    DEVELOPMENT = "development"        # 发展与升级
    EXIT = "exit"                      # 退市与注销


class ComplianceStatus(Enum):
    """合规状态"""
    COMPLIANT = "compliant"            # 合规
    WARNING = "warning"                # 预警
    VIOLATION = "violation"            # 违规
    PENDING = "pending"               # 待处理
    UNKNOWN = "unknown"               # 未知


@dataclass
class IdentityInfo:
    """身份信息"""
    credit_code: str = ""              # 统一社会信用代码
    company_name: str = ""
    legal_person: str = ""
    registered_capital: float = 0.0
    business_scope: List[str] = field(default_factory=list)
    industry_code: str = ""           # 国民经济行业分类代码
    tax_id: str = ""                  # 纳税人识别号
    tax_types: List[str] = field(default_factory=list)  # 税种核定
    qualifications: List[str] = field(default_factory=list)  # 高新、专精特新等
    credit_rating: str = ""


@dataclass
class PhysicalAsset:
    """物理实体"""
    addresses: List[Dict] = field(default_factory=list)  # 注册/经营地址
    facilities: List[Dict] = field(default_factory=list)  # 生产设施
    environmental_facilities: List[Dict] = field(default_factory=list)  # 环保设施
    safety_facilities: List[Dict] = field(default_factory=list)  # 安全设施
    coordinates: Dict[str, float] = field(default_factory=dict)  # 经纬度


@dataclass
class PersonnelInfo:
    """人员组织"""
    departments: List[Dict] = field(default_factory=list)
    employee_count: int = 0
    employees: List[Dict] = field(default_factory=list)  # 员工档案
    payroll: Dict = field(default_factory=dict)  # 薪酬信息


@dataclass
class BusinessProcess:
    """业务流程"""
    core_processes: List[Dict] = field(default_factory=list)  # 研发→生产→销售→服务
    support_processes: List[Dict] = field(default_factory=list)  # 人财物
    compliance_processes: List[Dict] = field(default_factory=list)  # 报批→备案→年报
    risk_processes: List[Dict] = field(default_factory=list)


@dataclass
class AssetInfo:
    """资产信息"""
    tangible: Dict = field(default_factory=dict)  # 土地、厂房、设备
    intangible: Dict = field(default_factory=dict)  # 专利、商标、软件
    financial: Dict = field(default_factory=dict)  # 现金、应收、投资
    digital: Dict = field(default_factory=dict)  # 代码、算法、数据


@dataclass
class ComplianceObligation:
    """合规义务"""
    category: str = ""               # 工商/税务/环保/安全/人社
    obligation_type: str = ""         # 年报/申报/许可/检查
    due_date: Optional[datetime] = None
    status: ComplianceStatus = ComplianceStatus.UNKNOWN
    last_completion: Optional[datetime] = None
    next_due: Optional[datetime] = None
    penalty_risk: float = 0.0       # 违规罚款风险


@dataclass
class OperationalData:
    """经营数据"""
    financial: Dict = field(default_factory=dict)  # 三张表、现金流
    business: Dict = field(default_factory=dict)   # 订单、交付、回款
    production: Dict = field(default_factory=dict)  # 产量、质量、能耗
    market: Dict = field(default_factory=dict)    # 份额、竞对


@dataclass
class RiskInfo:
    """风险信息"""
    market_risks: List[Dict] = field(default_factory=list)
    operational_risks: List[Dict] = field(default_factory=list)
    financial_risks: List[Dict] = field(default_factory=list)
    compliance_risks: List[Dict] = field(default_factory=list)
    tech_risks: List[Dict] = field(default_factory=list)


@dataclass
class EnterpriseDimensions:
    """企业八维数字孪生"""
    identity: IdentityInfo = field(default_factory=IdentityInfo)
    physical: PhysicalAsset = field(default_factory=PhysicalAsset)
    personnel: PersonnelInfo = field(default_factory=PersonnelInfo)
    business: BusinessProcess = field(default_factory=BusinessProcess)
    assets: AssetInfo = field(default_factory=AssetInfo)
    compliance: List[ComplianceObligation] = field(default_factory=list)
    operational_data: OperationalData = field(default_factory=OperationalData)
    risks: RiskInfo = field(default_factory=RiskInfo)


@dataclass
class EnterpriseDigitalTwin:
    """
    企业数字孪生体

    动态映射企业全生命周期状态的八维数字孪生。
    """
    twin_id: str
    company_name: str
    credit_code: str
    lifecycle_stage: LifecycleStage = LifecycleStage.INCUBATION

    # 八维数据
    dimensions: EnterpriseDimensions = field(default_factory=EnterpriseDimensions)

    # 状态
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    last_sync: Optional[datetime] = None

    # 关联
    related_docs: List[str] = field(default_factory=list)  # 关联文档
    compliance_score: float = 100.0  # 合规评分
    risk_level: str = "LOW"          # 风险等级

    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)


# ==================== 数字孪生管理器 ====================

class EnterpriseDigitalTwinManager:
    """
    企业数字孪生管理器

    创建、更新、查询企业数字孪生体。
    """

    def __init__(self, db_path: str = None):
        """
        Args:
            db_path: 数据库路径
        """
        self.db_path = db_path
        self._twins: Dict[str, EnterpriseDigitalTwin] = {}

    async def create_twin(
        self,
        company_name: str,
        credit_code: str,
        identity_info: Dict = None
    ) -> EnterpriseDigitalTwin:
        """
        创建企业数字孪生

        Args:
            company_name: 公司名称
            credit_code: 统一社会信用代码
            identity_info: 身份信息

        Returns:
            EnterpriseDigitalTwin: 数字孪生体
        """
        twin_id = self._generate_twin_id(credit_code)

        twin = EnterpriseDigitalTwin(
            twin_id=twin_id,
            company_name=company_name,
            credit_code=credit_code,
            lifecycle_stage=LifecycleStage.INCUBATION,
            dimensions=EnterpriseDimensions(
                identity=IdentityInfo(
                    credit_code=credit_code,
                    company_name=company_name,
                    **(identity_info or {})
                )
            )
        )

        self._twins[twin_id] = twin
        return twin

    async def update_twin(
        self,
        twin_id: str,
        updates: Dict[str, Any]
    ) -> Optional[EnterpriseDigitalTwin]:
        """
        更新数字孪生

        Args:
            twin_id: 孪生体ID
            updates: 更新内容

        Returns:
            Optional[EnterpriseDigitalTwin]: 更新后的孪生体
        """
        twin = self._twins.get(twin_id)
        if not twin:
            return None

        # 更新维度数据
        for key, value in updates.items():
            if hasattr(twin.dimensions, key):
                setattr(twin.dimensions, key, value)

        twin.updated_at = datetime.now()
        return twin

    async def update_lifecycle_stage(
        self,
        twin_id: str,
        stage: LifecycleStage
    ) -> bool:
        """
        更新生命周期阶段

        Args:
            twin_id: 孪生体ID
            stage: 新阶段

        Returns:
            bool: 是否成功
        """
        twin = self._twins.get(twin_id)
        if not twin:
            return False

        twin.lifecycle_stage = stage
        twin.updated_at = datetime.now()
        return True

    async def add_compliance_obligation(
        self,
        twin_id: str,
        obligation: ComplianceObligation
    ) -> bool:
        """
        添加合规义务

        Args:
            twin_id: 孪生体ID
            obligation: 合规义务

        Returns:
            bool: 是否成功
        """
        twin = self._twins.get(twin_id)
        if not twin:
            return False

        twin.dimensions.compliance.append(obligation)
        twin.updated_at = datetime.now()
        return True

    async def sync_compliance_status(
        self,
        twin_id: str
    ) -> Dict[str, ComplianceStatus]:
        """
        同步合规状态

        Args:
            twin_id: 孪生体ID

        Returns:
            Dict[str, ComplianceStatus]: 各类合规状态
        """
        twin = self._twins.get(twin_id)
        if not twin:
            return {}

        statuses = {}
        for ob in twin.dimensions.compliance:
            if ob.category not in statuses:
                statuses[ob.category] = ob.status

        twin.last_sync = datetime.now()
        return statuses

    def get_twin(self, twin_id: str) -> Optional[EnterpriseDigitalTwin]:
        """获取孪生体"""
        return self._twins.get(twin_id)

    def get_twin_by_credit_code(self, credit_code: str) -> Optional[EnterpriseDigitalTwin]:
        """通过信用代码获取孪生体"""
        for twin in self._twins.values():
            if twin.credit_code == credit_code:
                return twin
        return None

    def get_all_twins(self) -> List[EnterpriseDigitalTwin]:
        """获取所有孪生体"""
        return list(self._twins.values())

    def _generate_twin_id(self, credit_code: str) -> str:
        """生成孪生体ID"""
        return f"twin_{credit_code[:8]}_{hashlib.md5(credit_code.encode()).hexdigest()[:8]}"


# ==================== 便捷函数 ====================

_twin_manager: Optional[EnterpriseDigitalTwinManager] = None


def get_twin_manager() -> EnterpriseDigitalTwinManager:
    """获取孪生生管理器单例"""
    global _twin_manager
    if _twin_manager is None:
        _twin_manager = EnterpriseDigitalTwinManager()
    return _twin_manager


async def create_enterprise_twin_async(
    company_name: str,
    credit_code: str,
    identity_info: Dict = None
) -> EnterpriseDigitalTwin:
    """创建企业数字孪生的便捷函数"""
    manager = get_twin_manager()
    return await manager.create_twin(company_name, credit_code, identity_info)


def get_enterprise_twin(twin_id: str = None, credit_code: str = None) -> Optional[EnterpriseDigitalTwin]:
    """获取企业数字孪生"""
    manager = get_twin_manager()
    if twin_id:
        return manager.get_twin(twin_id)
    elif credit_code:
        return manager.get_twin_by_credit_code(credit_code)
    return None
