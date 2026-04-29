"""
排污许可智能管理系统
====================

核心功能：
1. 智能填报 - 从环评报告、验收监测自动继承数据
2. 许可量智能核算 - 基于行业产排污系数模型计算
3. 证后管理智能提醒 - 日历集成、预警系统
4. 合规校验 - 检查申请量与批复总量的关系
"""

import asyncio
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class PermitType(Enum):
    """许可类型"""
    SIMPLE = "simple"              # 简化管理
    NORMAL = "normal"            # 重点管理
    DETAILED = "detailed"       # 精细管理


class WorkCondition(Enum):
    """工况类型"""
    NORMAL = "normal"            # 正常工况
    ABNORMAL = "abnormal"        # 非正常工况
    ACCIDENT = "accident"        # 事故工况


@dataclass
class Pollutant:
    """污染物"""
    name: str
    code: str                    # 污染物编码
    category: str                # 大气/水/固废
    emission_limit: float        # 排放限值
    unit: str                   # 单位
    permit_quantity: float       # 许可排放量
    permit_concentration: float  # 许可浓度


@dataclass
class PollutionSource:
    """污染源"""
    source_id: str
    source_name: str
    source_type: str            # 有组织/无组织
    pollutants: List[Pollutant]
    emission_point_height: float = 0.0  # 排放口高度 (m)
    diameter: float = 0.0        # 排放口直径 (m)


@dataclass
class PermitApplication:
    """许可证申请"""
    application_id: str
    company_name: str
    social_credit_code: str      # 统一社会信用代码

    # 行业信息
    industry_code: str           # 行业代码
    industry_name: str
    main_product: str           # 主要产品
    production_scale: float      # 生产规模
    production_unit: str         # 单位

    # 污染源信息
    pollution_sources: List[PollutionSource]

    # 许可信息
    permit_type: PermitType
    permit_scope: str           # 许可范围

    # 执行标准
    execution_standards: List[str]

    # 自行监测要求
    monitoring_requirements: Dict[str, Any]

    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class PermitQuantityCalculation:
    """许可量核算结果"""
    pollutant_name: str
    calculation_method: str      # 计算方法
    production_base: float       # 产量
    emission_factor: float       # 排放因子
    calculated_quantity: float   # 计算排放量
    approved_quantity: float     # 批复排放量
    safety_margin: float         # 安全余量
    final_permit_quantity: float  # 最终许可量

    def to_dict(self) -> Dict:
        return {
            "pollutant_name": self.pollutant_name,
            "calculation_method": self.calculation_method,
            "production_base": self.production_base,
            "emission_factor": self.emission_factor,
            "calculated_quantity": self.calculated_quantity,
            "approved_quantity": self.approved_quantity,
            "final_permit_quantity": self.final_permit_quantity,
        }


@dataclass
class ComplianceCheck:
    """合规检查结果"""
    check_type: str              # 检查类型
    status: str                 # PASS/FAIL/WARNING
    description: str
    suggestion: str = ""

    def to_dict(self) -> Dict:
        return {
            "check_type": self.check_type,
            "status": self.status,
            "description": self.description,
            "suggestion": self.suggestion,
        }


@dataclass
class MonitoringReminder:
    """监测提醒"""
    reminder_id: str
    reminder_type: str          # 自行监测/执行报告/信息公开
    title: str
    description: str
    due_date: datetime
    frequency: str              # 频次
    is_overdue: bool = False

    def to_dict(self) -> Dict:
        return {
            "reminder_id": self.reminder_id,
            "reminder_type": self.reminder_type,
            "title": self.title,
            "description": self.description,
            "due_date": self.due_date.isoformat(),
            "frequency": self.frequency,
            "is_overdue": self.is_overdue,
        }


@dataclass
class PollutionPermit:
    """排污许可证"""
    permit_id: str
    company_name: str
    permit_number: str           # 许可证编号
    valid_from: datetime
    valid_until: datetime

    # 许可内容
    emission_permits: List[Pollutant]
    self_monitoring: Dict[str, Any]

    # 合规检查
    compliance_checks: List[ComplianceCheck]

    # 证后管理日历
    reminders: List[MonitoringReminder]

    # 状态
    status: str = "active"       # active/expired/revoked
    last_check_date: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            "permit_id": self.permit_id,
            "company_name": self.company_name,
            "permit_number": self.permit_number,
            "valid_from": self.valid_from.isoformat(),
            "valid_until": self.valid_until.isoformat(),
            "status": self.status,
            "pollutants": [{"name": p.name, "permit_quantity": p.permit_quantity} for p in self.emission_permits],
            "compliance": [c.to_dict() for c in self.compliance_checks],
            "reminders": [r.to_dict() for r in self.reminders],
        }


class EmissionFactorKnowledgeBase:
    """排放因子知识库"""

    # 行业产排污系数
    FACTORS = {
        "火电": {
            "产品": "电力",
            "unit": "MW",
            "SO2": {"factor": 2.5, "unit": "kg/t标煤"},
            "NOx": {"factor": 3.5, "unit": "kg/t标煤"},
            "烟尘": {"factor": 0.5, "unit": "kg/t标煤"},
        },
        "水泥": {
            "产品": "水泥熟料",
            "unit": "t",
            "SO2": {"factor": 0.5, "unit": "kg/t熟料"},
            "NOx": {"factor": 1.5, "unit": "kg/t熟料"},
            "颗粒物": {"factor": 0.2, "unit": "kg/t熟料"},
        },
        "钢铁": {
            "产品": "粗钢",
            "unit": "万t",
            "SO2": {"factor": 1.8, "unit": "kg/t铁"},
            "NOx": {"factor": 1.5, "unit": "kg/t铁"},
            "颗粒物": {"factor": 1.0, "unit": "kg/t铁"},
        },
        "化工": {
            "产品": "乙烯",
            "unit": "t",
            "SO2": {"factor": 15.5, "unit": "kg/t产品"},
            "NOx": {"factor": 5.0, "unit": "kg/t产品"},
            "VOCs": {"factor": 10.0, "unit": "kg/t产品"},
        },
        "造纸": {
            "产品": "纸张",
            "unit": "t",
            "COD": {"factor": 15.0, "unit": "kg/t产品"},
            "NH3-N": {"factor": 0.5, "unit": "kg/t产品"},
            "SS": {"factor": 10.0, "unit": "kg/t产品"},
        },
    }

    @classmethod
    def get_factor(cls, industry: str, pollutant: str) -> Optional[Dict]:
        """获取排放因子"""
        if industry in cls.FACTORS:
            factors = cls.FACTORS[industry]
            if pollutant in factors:
                return factors[pollutant]
        return None

    @classmethod
    def get_all_industries(cls) -> List[str]:
        """获取所有行业"""
        return list(cls.FACTORS.keys())


class PermitQuantityCalculator:
    """许可量核算器"""

    def __init__(self):
        self.factor_kb = EmissionFactorKnowledgeBase()

    async def calculate(
        self,
        industry: str,
        product: str,
        production: float,
        pollutant: str,
        eia_approved_quantity: Optional[float] = None
    ) -> PermitQuantityCalculation:
        """
        核算许可排放量

        Args:
            industry: 行业
            product: 产品
            production: 产量
            pollutant: 污染物
            eia_approved_quantity: 环评批复排放量

        Returns:
            PermitQuantityCalculation: 核算结果
        """
        factor_data = self.factor_kb.get_factor(industry, pollutant)

        if factor_data:
            emission_factor = factor_data['factor']
            unit = factor_data['unit']
            calculated = production * emission_factor
        else:
            # 默认因子
            emission_factor = 1.0
            calculated = production * emission_factor

        # 取环评批复量和计算量的较小值（取严）
        if eia_approved_quantity:
            approved = min(calculated, eia_approved_quantity)
            # 安全余量 5%
            final = approved * 0.95
        else:
            approved = calculated
            final = calculated * 0.9  # 默认90%

        return PermitQuantityCalculation(
            pollutant_name=pollutant,
            calculation_method="产排污系数法" if factor_data else "类比法",
            production_base=production,
            emission_factor=emission_factor,
            calculated_quantity=round(calculated, 2),
            approved_quantity=round(approved, 2),
            safety_margin=0.05 if eia_approved_quantity else 0.1,
            final_permit_quantity=round(final, 2)
        )

    async def calculate_all(
        self,
        industry: str,
        product: str,
        production: float,
        pollutants: List[str],
        eia_approved_quantities: Optional[Dict[str, float]] = None
    ) -> List[PermitQuantityCalculation]:
        """计算所有污染物"""
        results = []
        for pollutant in pollutants:
            result = await self.calculate(
                industry, product, production, pollutant,
                eia_approved_quantities.get(pollutant) if eia_approved_quantities else None
            )
            results.append(result)
        return results


class ComplianceChecker:
    """合规检查器"""

    async def check_application(
        self,
        application: PermitApplication,
        eia_report: Optional[Dict] = None
    ) -> List[ComplianceCheck]:
        """
        检查申请合规性

        Args:
            application: 申请
            eia_report: 环评报告（用于比对）

        Returns:
            List[ComplianceCheck]: 检查结果
        """
        checks = []

        # 1. 检查排放量是否超出环评批复
        if eia_report:
            eia_quantities = eia_report.get('approved_emission_quantities', {})
            for source in application.pollution_sources:
                for pollutant in source.pollutants:
                    eia_q = eia_quantities.get(pollutant.name)
                    if eia_q and pollutant.permit_quantity > eia_q:
                        checks.append(ComplianceCheck(
                            check_type="total_quantity_check",
                            status="FAIL",
                            description=f"{pollutant.name}申请排放量({pollutant.permit_quantity})超过环评批复({eia_q})",
                            suggestion="应不大于环评批复排放量"
                        ))

        # 2. 检查标准是否严于环评要求
        eia_standards = eia_report.get('emission_standards', []) if eia_report else []
        for std in application.execution_standards:
            if std in eia_standards:
                checks.append(ComplianceCheck(
                    check_type="standard_check",
                    status="PASS",
                    description=f"执行标准{std}符合要求"
                ))

        # 3. 检查行业编码
        if not application.industry_code:
            checks.append(ComplianceCheck(
                check_type="industry_code_check",
                status="WARNING",
                description="行业代码未填写",
                suggestion="请填写正确的行业代码"
            ))

        return checks

    async def check_permit_compliance(
        self,
        permit: PollutionPermit,
        current_data: Dict[str, float]
    ) -> List[ComplianceCheck]:
        """
        检查许可证合规状态

        Args:
            permit: 许可证
            current_data: 当前排放数据

        Returns:
            List[ComplianceCheck]: 检查结果
        """
        checks = []

        for pollutant in permit.emission_permits:
            current = current_data.get(pollutant.name)
            if current:
                # 检查浓度
                if current > pollutant.emission_limit:
                    checks.append(ComplianceCheck(
                        check_type="concentration_compliance",
                        status="FAIL",
                        description=f"{pollutant.name}排放浓度({current}{pollutant.unit})超过限值({pollutant.emission_limit}{pollutant.unit})",
                        suggestion="立即采取措施降低排放浓度"
                    ))
                elif current > pollutant.emission_limit * 0.8:
                    checks.append(ComplianceCheck(
                        check_type="concentration_warning",
                        status="WARNING",
                        description=f"{pollutant.name}排放浓度接近限值，当前值{current}{pollutant.unit}",
                        suggestion="密切关注，确保不超标"
                    ))

                # 检查总量
                if hasattr(pollutant, 'permit_quantity') and current > pollutant.permit_quantity:
                    checks.append(ComplianceCheck(
                        check_type="quantity_compliance",
                        status="FAIL",
                        description=f"{pollutant.name}排放总量超过许可量",
                        suggestion="立即控制生产负荷"
                    ))

        return checks


class PostPermitManager:
    """证后管理器"""

    def __init__(self):
        self.frequencies = {
            "废气": {"常规监测": "季度", "在线监测": "实时"},
            "废水": {"常规监测": "季度", "在线监测": "实时"},
            "噪声": {"监测频次": "半年"},
            "固废": {"监测频次": "年"},
        }

    async def generate_reminders(
        self,
        permit: PollutionPermit,
        company_context: Dict
    ) -> List[MonitoringReminder]:
        """生成证后管理提醒"""
        reminders = []
        now = datetime.now()

        # 1. 自行监测提醒
        for pollutant in permit.emission_permits[:3]:
            category = pollutant.category
            freq = self.frequencies.get(category, {}).get("常规监测", "季度")

            reminder = MonitoringReminder(
                reminder_id=f"MR_{permit.permit_id}_{pollutant.name}",
                reminder_type="self_monitoring",
                title=f"{pollutant.name}自行监测",
                description=f"应按照许可证要求对{pollutant.name}进行自行监测，频次：{freq}",
                due_date=now + timedelta(days=90),
                frequency=freq
            )
            reminders.append(reminder)

        # 2. 执行报告提醒
        reminder = MonitoringReminder(
            reminder_id=f"ER_{permit.permit_id}",
            reminder_type="execution_report",
            title="排污许可执行报告",
            description="应于每年1月底前提交上年度执行报告",
            due_date=datetime(now.year + 1, 1, 31),
            frequency="年度"
        )
        reminders.append(reminder)

        # 3. 信息公开提醒
        reminder = MonitoringReminder(
            reminder_id=f"PI_{permit.permit_id}",
            reminder_type="public_disclosure",
            title="排污许可信息公开",
            description="应按规定在平台公开污染物排放信息",
            due_date=now + timedelta(days=30),
            frequency="月度"
        )
        reminders.append(reminder)

        # 4. 到期提醒（提前6个月）
        if permit.valid_until:
            reminder = MonitoringReminder(
                reminder_id=f"VR_{permit.permit_id}",
                reminder_type="validity_reminder",
                title="许可证到期提醒",
                description=f"许可证将于{permit.valid_until.strftime('%Y-%m-%d')}到期，请提前6个月申请延续",
                due_date=permit.valid_until - timedelta(days=180),
                frequency="一次性"
            )
            reminders.append(reminder)

        return reminders

    def check_overdue(self, reminders: List[MonitoringReminder]) -> List[MonitoringReminder]:
        """检查过期提醒"""
        now = datetime.now()
        for reminder in reminders:
            if reminder.due_date < now:
                reminder.is_overdue = True
        return reminders


class PollutionPermitEngine:
    """
    排污许可主引擎

    整合智能填报、许可量核算、合规检查、证后管理
    """

    def __init__(self):
        self.calculator = PermitQuantityCalculator()
        self.compliance_checker = ComplianceChecker()
        self.post_manager = PostPermitManager()

    async def generate_application(
        self,
        project_context: Dict[str, Any],
        eia_report: Optional[Dict] = None,
        acceptance_report: Optional[Dict] = None
    ) -> PermitApplication:
        """
        从环评报告/验收监测生成许可证申请

        Args:
            project_context: 项目上下文
            eia_report: 环评报告
            acceptance_report: 验收监测报告

        Returns:
            PermitApplication: 许可证申请
        """
        application_id = f"PA_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # 1. 从环评报告继承数据
        pollution_sources = []
        if eia_report:
            sources_data = eia_report.get('pollution_sources', [])
            for src in sources_data[:5]:
                pollutants = []
                for pol in src.get('pollutants', [])[:5]:
                    pollutants.append(Pollutant(
                        name=pol.get('name', '未知'),
                        code=pol.get('code', ''),
                        category=pol.get('category', '废气'),
                        emission_limit=pol.get('limit', 100),
                        unit=pol.get('unit', 'mg/m³'),
                        permit_quantity=pol.get('quantity', 0),
                        permit_concentration=pol.get('concentration', 0)
                    ))
                pollution_sources.append(PollutionSource(
                    source_id=src.get('id', f"S{src.get('index', 0)}"),
                    source_name=src.get('name', '污染源'),
                    source_type=src.get('type', '有组织'),
                    pollutants=pollutants,
                    emission_point_height=src.get('height', 15),
                    diameter=src.get('diameter', 0.5)
                ))

        # 2. 从验收监测获取实测数据
        monitoring_data = {}
        if acceptance_report:
            for result in acceptance_report.get('evaluation_results', []):
                monitoring_data[result['parameter']] = result['measured_value']

        # 3. 确定许可类型
        industry = project_context.get('industry_type', '')
        if industry in ['火电', '钢铁', '化工', '石油化工']:
            permit_type = PermitType.NORMAL
        elif industry in ['造纸', '印染', '电镀']:
            permit_type = PermitType.DETAILED
        else:
            permit_type = PermitType.SIMPLE

        return PermitApplication(
            application_id=application_id,
            company_name=project_context.get('company_name', '某公司'),
            social_credit_code=project_context.get('credit_code', ''),
            industry_code=project_context.get('industry_code', ''),
            industry_name=industry,
            main_product=project_context.get('main_product', ''),
            production_scale=project_context.get('production_scale', 0),
            production_unit=project_context.get('production_unit', ''),
            pollution_sources=pollution_sources,
            permit_type=permit_type,
            permit_scope="排放口",
            execution_standards=project_context.get('execution_standards', []),
            monitoring_requirements={
                "air": {"frequency": "季度", "method": "手工监测/在线监测"},
                "water": {"frequency": "季度", "method": "手工监测/在线监测"},
            }
        )

    async def calculate_permit_quantities(
        self,
        application: PermitApplication,
        eia_approved_quantities: Optional[Dict[str, float]] = None
    ) -> List[PermitQuantityCalculation]:
        """计算许可排放量"""
        # 获取主要污染物列表
        pollutants = []
        for source in application.pollution_sources:
            for pollutant in source.pollutants:
                if pollutant.name not in pollutants:
                    pollutants.append(pollutant.name)

        return await self.calculator.calculate_all(
            industry=application.industry_name,
            product=application.main_product,
            production=application.production_scale,
            pollutants=pollutants,
            eia_approved_quantities=eia_approved_quantities
        )

    async def generate_permit(
        self,
        application: PermitApplication,
        calculations: List[PermitQuantityCalculation]
    ) -> PollutionPermit:
        """生成排污许可证"""
        permit_id = f"PP_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # 1. 构建许可污染物列表
        emission_permits = []
        for calc in calculations:
            emission_permits.append(Pollutant(
                name=calc.pollutant_name,
                code="",
                category="废气",
                emission_limit=100,  # 默认值
                unit="mg/m³",
                permit_quantity=calc.final_permit_quantity,
                permit_concentration=50
            ))

        # 2. 生成证后管理提醒
        permit = PollutionPermit(
            permit_id=permit_id,
            company_name=application.company_name,
            permit_number=f"9132XXXXXXXXXX{len(calculations)}",
            valid_from=datetime.now(),
            valid_until=datetime.now() + timedelta(days=365 * 5),
            emission_permits=emission_permits,
            self_monitoring=application.monitoring_requirements,
            compliance_checks=[],
            reminders=[]
        )

        permit.reminders = await self.post_manager.generate_reminders(
            permit, {"company_name": application.company_name}
        )

        return permit


# 全局实例
_permit_engine_instance: Optional[PollutionPermitEngine] = None


def get_permit_engine() -> PollutionPermitEngine:
    global _permit_engine_instance
    if _permit_engine_instance is None:
        _permit_engine_instance = PollutionPermitEngine()
    return _permit_engine_instance