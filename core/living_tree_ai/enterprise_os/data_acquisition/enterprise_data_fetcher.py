"""
企业数据获取器 (Enterprise Data Fetcher)

从各政府系统自动抓取企业背景数据，填充项目档案。

支持的数据源：
1. 国家企业信用信息公示系统 - 工商主体信息
2. 地方生态环境局"亲清服务平台" - 环保底账
3. 应急管理部安全生产许可系统 - 安全许可
4. 信用中国、法院执行信息网 - 信用风险

核心逻辑：
新建项目 → 输入企业名称/信用代码 → AI浏览器自动抓取 → 存入企业Profile
"""

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, List, Any
import json
import hashlib


class DataSourceType(Enum):
    """数据源类型"""
    GOVERNMENT_API = "government_api"       # 政府开放API
    GOVERNMENT_WEB = "government_web"       # 政府网站抓取
    THIRD_PARTY_API = "third_party_api"     # 第三方API（企查查、天眼查）
    MANUAL_INPUT = "manual_input"           # 手动录入
    AI_EXTRACTION = "ai_extraction"          # AI从文档提取


class FetchStatus(Enum):
    """获取状态"""
    PENDING = "pending"
    FETCHING = "fetching"
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"     # 部分成功
    FAILED = "failed"
    NOT_FOUND = "not_found"


class GovernmentSystem(Enum):
    """政府系统枚举"""
    # 工商系统
    SAMR_CREDIT_INFO = "samr_credit_info"           # 国家企业信用信息公示系统
    SAMR_BUSINESS_REG = "samr_business_reg"         # 企业登记注册系统

    # 环保系统
    MEP_PERMIT_PLATFORM = "mep_permit"              # 全国排污许可管理信息平台
    MEP_EIA_CREDIT = "mep_eia_credit"               # 环境影响评价信用平台
    LOCAL_EPB = "local_epb"                         # 地方生态环境局

    # 安全系统
    MEM_SAFETY_LICENSE = "mem_safety_license"       # 应急管理部安全生产许可
    SAFETY_PRODUCTION_CREDIT = "safety_production_credit"  # 安全生产信用

    # 信用系统
    CREDIT_CHINA = "credit_china"                   # 信用中国
    COURT_EXECUTION = "court_execution"              # 法院执行信息网
    TAX_CREDIT = "tax_credit"                       # 税务信用

    # 其他
    CUSTOM_CLEARANCE = "customs"                     # 海关
    SOCIAL_INSURANCE = "social_insurance"           # 社保


@dataclass
class EnterpriseBasicInfo:
    """企业基本信息"""
    credit_code: str                                 # 统一信用代码
    company_name: str                                # 企业名称
    legal_representative: Optional[str] = None      # 法定代表人
    registered_capital: Optional[float] = None       # 注册资本（万元）
    paid_capital: Optional[float] = None            # 实缴资本（万元）
    establishment_date: Optional[str] = None        # 成立日期
    business_term_start: Optional[str] = None       # 营业期限起
    business_term_end: Optional[str] = None          # 营业期限止
    registration_authority: Optional[str] = None     # 登记机关
    company_type: Optional[str] = None               # 公司类型
    business_scope: Optional[str] = None            # 经营范围
    address: Optional[str] = None                   # 注册地址
    annual_inspection_status: Optional[str] = None  # 年报状态
    employee_count: Optional[int] = None            # 员工人数

    # 运营信息
    industry: Optional[str] = None                  # 所属行业
    product_type: Optional[str] = None              # 产品类型
    production_scale: Optional[str] = None          # 生产规模

    # 元数据
    data_source: Optional[str] = None
    fetch_time: Optional[datetime] = None
    fetch_status: FetchStatus = FetchStatus.PENDING
    confidence: float = 0.0


@dataclass
class EnvironmentalRecord:
    """环保记录"""
    credit_code: str

    # 排污许可
    pollution_permit_number: Optional[str] = None   # 排污许可证编号
    pollution_permit_issue_date: Optional[str] = None  # 发证日期
    pollution_permit_expiry: Optional[str] = None     # 有效期至
    permitted_discharge: Optional[Dict[str, float]] = None  # 许可排放量 (kg/a)

    # 历史环评
    eia_records: List[Dict[str, Any]] = field(default_factory=list)  # 环评批复记录
    eia_compliance_status: Optional[str] = None     # 环评合规状态

    # 处罚记录
    environmental_penalties: List[Dict[str, Any]] = field(default_factory=list)
    total_penalty_amount: float = 0.0

    # 监测数据
    recent_monitoring_data: Optional[Dict[str, Any]] = None  # 最近监测数据
    self_monitoring_plan: Optional[str] = None      # 自行监测方案

    # 清洁生产
    clean_production_audit_status: Optional[str] = None  # 清洁生产审核状态

    # 元数据
    data_source: Optional[str] = None
    fetch_time: Optional[datetime] = None
    fetch_status: FetchStatus = FetchStatus.PENDING
    confidence: float = 0.0


@dataclass
class SafetyLicense:
    """安全许可信息"""
    credit_code: str

    # 安全生产许可
    safety_production_license: Optional[str] = None  # 安全生产许可证编号
    safety_license_issue_date: Optional[str] = None
    safety_license_expiry: Optional[str] = None

    # 危险化学品
    hazardous_chemical_permit: Optional[str] = None  # 危化品安全生产许可
    hazardous_chemical_expiry: Optional[str] = None

    # 安全评价
    safety_evaluation_report: Optional[str] = None   # 安全评价报告
    safety_evaluation_date: Optional[str] = None

    # 应急预案
    emergency_plan_recorded: bool = False             # 应急预案已备案
    emergency_plan_date: Optional[str] = None

    # 特种作业
    special_operation_cert_count: int = 0             # 特种作业证数量

    # 安全培训
    safety_training_coverage: float = 0.0            # 安全培训覆盖率

    # 事故记录
    accident_records: List[Dict[str, Any]] = field(default_factory=list)
    total_accidents: int = 0

    # 元数据
    data_source: Optional[str] = None
    fetch_time: Optional[datetime] = None
    fetch_status: FetchStatus = FetchStatus.PENDING
    confidence: float = 0.0


@dataclass
class CreditRiskInfo:
    """信用风险信息"""
    credit_code: str

    # 信用等级
    credit_rating: Optional[str] = None              # 信用评级
    credit_rating_agency: Optional[str] = None       # 评级机构

    # 法院执行
    is_executed: bool = False                        # 是否有未结执行案件
    execution_cases: List[Dict[str, Any]] = field(default_factory=list)
    total_execution_amount: float = 0.0

    # 行政处罚
    administrative_penalties: List[Dict[str, Any]] = field(default_factory=list)
    total_administrative_penalty: float = 0.0

    # 税务信用
    tax_credit_level: Optional[str] = None            # 纳税信用等级
    tax_credit_score: Optional[int] = None            # 纳税信用评分

    # 经营异常
    is_abnormal_operation: bool = False             # 是否经营异常
    abnormal_reasons: List[str] = field(default_factory=list)

    # 严重违法
    is_serious_violation: bool = False              # 是否严重违法
    serious_violation_reasons: List[str] = field(default_factory=list)

    # 失信联合惩戒
    is_untrustworthy: bool = False                   # 是否失信
    untrustworthy_records: List[Dict[str, Any]] = field(default_factory=list)

    # 元数据
    data_source: Optional[str] = None
    fetch_time: Optional[datetime] = None
    fetch_status: FetchStatus = FetchStatus.PENDING
    confidence: float = 0.0


@dataclass
class GovernmentData:
    """政府数据结构（统一封装）"""
    enterprise_id: str                               # 企业ID
    credit_code: str                                  # 统一信用代码

    basic_info: Optional[EnterpriseBasicInfo] = None
    environmental_record: Optional[EnvironmentalRecord] = None
    safety_license: Optional[SafetyLicense] = None
    credit_risk: Optional[CreditRiskInfo] = None

    # 扩展字段（用于未来扩展）
    extensions: Dict[str, Any] = field(default_factory=dict)

    # 获取状态汇总
    fetch_results: Dict[str, FetchStatus] = field(default_factory=dict)
    overall_confidence: float = 0.0

    # 时间戳
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "enterprise_id": self.enterprise_id,
            "credit_code": self.credit_code,
            "basic_info": self.basic_info.__dict__ if self.basic_info else None,
            "environmental_record": self.environmental_record.__dict__ if self.environmental_record else None,
            "safety_license": self.safety_license.__dict__ if self.safety_license else None,
            "credit_risk": self.credit_risk.__dict__ if self.credit_risk else None,
            "extensions": self.extensions,
            "fetch_results": {k: v.value for k, v in self.fetch_results.items()},
            "overall_confidence": self.overall_confidence,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class EnterpriseDataFetcher:
    """
    企业数据获取器

    核心功能：
    1. 根据企业名称/信用代码，从各政府系统获取数据
    2. AI浏览器模拟登录，自动抓取网页数据
    3. 数据结构化存储到企业Profile
    4. 支持增量更新和全量刷新

    使用示例：
    ```python
    fetcher = get_enterprise_fetcher()

    # 获取企业完整数据
    data = await fetcher.fetch_all(
        credit_code="91320000XXXXXXXX",
        company_name="XX化工有限公司"
    )

    # 或按需获取特定系统数据
    basic_info = await fetcher.fetch_basic_info(credit_code)
    env_record = await fetcher.fetch_environmental(credit_code)
    ```
    """

    # 系统配置
    SYSTEM_CONFIGS = {
        GovernmentSystem.SAMR_CREDIT_INFO: {
            "name": "国家企业信用信息公示系统",
            "url": "https://www.gsxt.gov.cn",
            "data_types": ["basic", "annual_report", "shareholder", "change"],
            "requires_login": False,
            "rate_limit": 10,  # 每分钟请求数
        },
        GovernmentSystem.MEP_PERMIT_PLATFORM: {
            "name": "全国排污许可管理信息平台",
            "url": "https://permit.mee.gov.cn",
            "data_types": ["permit", "discharge", "self_monitoring"],
            "requires_login": True,
            "rate_limit": 5,
        },
        GovernmentSystem.CREDIT_CHINA: {
            "name": "信用中国",
            "url": "https://www.creditchina.gov.cn",
            "data_types": ["credit_info", "penalties", "credit_rating"],
            "requires_login": False,
            "rate_limit": 10,
        },
        GovernmentSystem.MEM_SAFETY_LICENSE: {
            "name": "应急管理部安全生产许可系统",
            "url": "https://www.mem.gov.cn",
            "data_types": ["safety_license", "hazardous_chemical"],
            "requires_login": True,
            "rate_limit": 5,
        },
        GovernmentSystem.COURT_EXECUTION: {
            "name": "中国执行信息公开网",
            "url": "http://zxgk.court.gov.cn",
            "data_types": ["execution", "dishonesty"],
            "requires_login": False,
            "rate_limit": 20,
        },
        GovernmentSystem.TAX_CREDIT: {
            "name": "税务信用系统",
            "url": "https://etax.chinatax.gov.cn",
            "data_types": ["tax_credit", "tax_rating"],
            "requires_login": True,
            "rate_limit": 5,
        },
    }

    def __init__(self):
        self._cache: Dict[str, GovernmentData] = {}
        self._cache_ttl = 24 * 3600  # 缓存24小时
        self._fetch_history: List[Dict[str, Any]] = []

    async def fetch_all(
        self,
        credit_code: Optional[str] = None,
        company_name: Optional[str] = None,
        enterprise_id: Optional[str] = None,
        force_refresh: bool = False
    ) -> GovernmentData:
        """
        获取企业所有政府数据

        Args:
            credit_code: 统一信用代码
            company_name: 企业名称（当无法提供信用代码时）
            enterprise_id: 企业ID（当有企业Profile时）
            force_refresh: 是否强制刷新

        Returns:
            GovernmentData: 包含所有政府数据的对象
        """
        # 生成缓存键
        cache_key = credit_code or company_name or enterprise_id
        if not cache_key:
            raise ValueError("必须提供 credit_code、company_name 或 enterprise_id 之一")

        # 检查缓存
        if not force_refresh and cache_key in self._cache:
            cached = self._cache[cache_key]
            age = (datetime.now() - cached.updated_at).total_seconds()
            if age < self._cache_ttl:
                return cached

        # 构建基础信息
        enterprise_id = enterprise_id or f"ENT:{hashlib.md5(cache_key.encode()).hexdigest()[:12].upper()}"

        # 创建数据对象
        gov_data = GovernmentData(
            enterprise_id=enterprise_id,
            credit_code=credit_code or "",
            fetch_results={}
        )

        # 1. 获取工商基本信息
        if credit_code or company_name:
            basic_info = await self._fetch_basic_info(credit_code, company_name)
            gov_data.basic_info = basic_info
            gov_data.fetch_results["basic_info"] = basic_info.fetch_status
            if credit_code and not gov_data.credit_code:
                gov_data.credit_code = credit_code

        # 2. 获取环保数据
        if credit_code:
            env_record = await self._fetch_environmental(credit_code)
            gov_data.environmental_record = env_record
            gov_data.fetch_results["environmental"] = env_record.fetch_status

        # 3. 获取安全许可
        if credit_code:
            safety = await self._fetch_safety(credit_code)
            gov_data.safety_license = safety
            gov_data.fetch_results["safety"] = safety.fetch_status

        # 4. 获取信用风险
        if credit_code:
            credit_risk = await self._fetch_credit_risk(credit_code)
            gov_data.credit_risk = credit_risk
            gov_data.fetch_results["credit_risk"] = credit_risk.fetch_status

        # 计算总体置信度
        gov_data.overall_confidence = self._calculate_confidence(gov_data)

        # 更新缓存
        self._cache[cache_key] = gov_data

        # 记录历史
        self._fetch_history.append({
            "credit_code": credit_code,
            "company_name": company_name,
            "fetch_time": datetime.now().isoformat(),
            "success_count": sum(1 for s in gov_data.fetch_results.values() if s == FetchStatus.SUCCESS),
            "total_count": len(gov_data.fetch_results),
        })

        return gov_data

    async def fetch_basic_info(
        self,
        credit_code: Optional[str] = None,
        company_name: Optional[str] = None
    ) -> EnterpriseBasicInfo:
        """仅获取工商基本信息"""
        return await self._fetch_basic_info(credit_code, company_name)

    async def fetch_environmental(self, credit_code: str) -> EnvironmentalRecord:
        """仅获取环保数据"""
        return await self._fetch_environmental(credit_code)

    async def fetch_safety(self, credit_code: str) -> SafetyLicense:
        """仅获取安全许可数据"""
        return await self._fetch_safety(credit_code)

    async def fetch_credit_risk(self, credit_code: str) -> CreditRiskInfo:
        """仅获取信用风险数据"""
        return await self._fetch_credit_risk(credit_code)

    async def _fetch_basic_info(
        self,
        credit_code: Optional[str],
        company_name: Optional[str]
    ) -> EnterpriseBasicInfo:
        """内部方法：获取工商基本信息"""
        result = EnterpriseBasicInfo(
            credit_code=credit_code or "",
            company_name=company_name or "",
            fetch_status=FetchStatus.FETCHING
        )

        try:
            # 模拟从国家企业信用信息公示系统抓取
            # 实际实现中，这里会调用AI浏览器进行网页抓取
            config = self.SYSTEM_CONFIGS[GovernmentSystem.SAMR_CREDIT_INFO]

            # 模拟数据结构
            if credit_code:
                result.legal_representative = "张三"
                result.registered_capital = 5000.0
                result.paid_capital = 3000.0
                result.establishment_date = "2010-05-15"
                result.business_term_start = "2010-05-15"
                result.business_term_end = "2030-05-14"
                result.registration_authority = "市场监督管理局"
                result.company_type = "有限责任公司"
                result.business_scope = "化工产品生产、销售；危险化学品经营..."
                result.address = "江苏省南京市化工园区XX路XX号"
                result.annual_inspection_status = "正常"
                result.employee_count = 200
                result.industry = "化学原料和化学制品制造业"
                result.product_type = "化工产品"
                result.production_scale = "年产20万吨"
                result.data_source = GovernmentSystem.SAMR_CREDIT_INFO.value
                result.fetch_status = FetchStatus.SUCCESS
                result.confidence = 0.95
            else:
                result.fetch_status = FetchStatus.NOT_FOUND
                result.confidence = 0.0

            result.fetch_time = datetime.now()

        except Exception as e:
            result.fetch_status = FetchStatus.FAILED
            result.confidence = 0.0

        return result

    async def _fetch_environmental(self, credit_code: str) -> EnvironmentalRecord:
        """内部方法：获取环保数据"""
        result = EnvironmentalRecord(
            credit_code=credit_code,
            fetch_status=FetchStatus.FETCHING
        )

        try:
            # 模拟从排污许可平台、环保局抓取
            if credit_code:
                result.pollution_permit_number = "P2024-XXXXX"
                result.pollution_permit_issue_date = "2024-01-15"
                result.pollution_permit_expiry = "2029-01-14"
                result.permitted_discharge = {
                    "SO2": 50.5,      # 吨/年
                    "NOx": 75.2,
                    "烟尘": 15.8,
                    "VOCs": 25.0,
                    "COD": 30.0,
                    "氨氮": 3.0,
                }
                result.eia_records = [
                    {"project": "一期建设项目", "approval_date": "2018-06-20", "status": "已验收"},
                    {"project": "技术改造项目", "approval_date": "2022-03-15", "status": "已批复"},
                ]
                result.eia_compliance_status = "合规"
                result.environmental_penalties = []
                result.total_penalty_amount = 0.0
                result.clean_production_audit_status = "已完成"
                result.data_source = GovernmentSystem.MEP_PERMIT_PLATFORM.value
                result.fetch_status = FetchStatus.SUCCESS
                result.confidence = 0.90
            else:
                result.fetch_status = FetchStatus.NOT_FOUND

            result.fetch_time = datetime.now()

        except Exception as e:
            result.fetch_status = FetchStatus.FAILED

        return result

    async def _fetch_safety(self, credit_code: str) -> SafetyLicense:
        """内部方法：获取安全许可数据"""
        result = SafetyLicense(
            credit_code=credit_code,
            fetch_status=FetchStatus.FETCHING
        )

        try:
            if credit_code:
                result.safety_production_license = "JS 安许证字 [2020]XXXXXX"
                result.safety_license_issue_date = "2020-12-01"
                result.safety_license_expiry = "2023-11-30"
                result.hazardous_chemical_permit = "苏危化经许字 [2021]XXXXXX"
                result.hazardous_chemical_expiry = "2026-12-31"
                result.safety_evaluation_report = "安全现状评价报告"
                result.safety_evaluation_date = "2023-06-15"
                result.emergency_plan_recorded = True
                result.emergency_plan_date = "2023-06-20"
                result.special_operation_cert_count = 45
                result.safety_training_coverage = 0.95
                result.accident_records = []
                result.total_accidents = 0
                result.data_source = GovernmentSystem.MEM_SAFETY_LICENSE.value
                result.fetch_status = FetchStatus.SUCCESS
                result.confidence = 0.88
            else:
                result.fetch_status = FetchStatus.NOT_FOUND

            result.fetch_time = datetime.now()

        except Exception as e:
            result.fetch_status = FetchStatus.FAILED

        return result

    async def _fetch_credit_risk(self, credit_code: str) -> CreditRiskInfo:
        """内部方法：获取信用风险数据"""
        result = CreditRiskInfo(
            credit_code=credit_code,
            fetch_status=FetchStatus.FETCHING
        )

        try:
            if credit_code:
                result.credit_rating = "A"
                result.credit_rating_agency = "中诚信"
                result.is_executed = False
                result.execution_cases = []
                result.total_execution_amount = 0.0
                result.administrative_penalties = []
                result.total_administrative_penalty = 0.0
                result.tax_credit_level = "A级"
                result.tax_credit_score = 92
                result.is_abnormal_operation = False
                result.abnormal_reasons = []
                result.is_serious_violation = False
                result.serious_violation_reasons = []
                result.is_untrustworthy = False
                result.untrustworthy_records = []
                result.data_source = GovernmentSystem.CREDIT_CHINA.value
                result.fetch_status = FetchStatus.SUCCESS
                result.confidence = 0.92
            else:
                result.fetch_status = FetchStatus.NOT_FOUND

            result.fetch_time = datetime.now()

        except Exception as e:
            result.fetch_status = FetchStatus.FAILED

        return result

    def _calculate_confidence(self, gov_data: GovernmentData) -> float:
        """计算总体置信度"""
        confidences = []
        if gov_data.basic_info:
            confidences.append(gov_data.basic_info.confidence * 0.3)
        if gov_data.environmental_record:
            confidences.append(gov_data.environmental_record.confidence * 0.3)
        if gov_data.safety_license:
            confidences.append(gov_data.safety_license.confidence * 0.2)
        if gov_data.credit_risk:
            confidences.append(gov_data.credit_risk.confidence * 0.2)

        return sum(confidences) if confidences else 0.0

    def get_fetch_statistics(self) -> Dict[str, Any]:
        """获取抓取统计"""
        total = len(self._fetch_history)
        if total == 0:
            return {"total_fetches": 0}

        success_count = sum(1 for h in self._fetch_history if h["success_count"] == h["total_count"])
        partial_count = sum(1 for h in self._fetch_history if 0 < h["success_count"] < h["total_count"])

        return {
            "total_fetches": total,
            "full_success": success_count,
            "partial_success": partial_count,
            "success_rate": success_count / total if total > 0 else 0,
        }


# 全局单例
_enterprise_fetcher: Optional[EnterpriseDataFetcher] = None


def get_enterprise_fetcher() -> EnterpriseDataFetcher:
    """获取企业数据获取器单例"""
    global _enterprise_fetcher
    if _enterprise_fetcher is None:
        _enterprise_fetcher = EnterpriseDataFetcher()
    return _enterprise_fetcher