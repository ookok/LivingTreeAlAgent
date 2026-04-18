"""
模块4: 排污许可智能管家 - Permit Intelligence Engine
=================================================

从"静态纸质证"转向"动态数据驱动的电子证"

核心能力：
1. 自动申请与延续 - AI填写40+张申请表
2. 执行报告自动填报 - 物联网数据一键上报
3. 智能预警与自动纠偏 - 预测性风险控制
4. 许可证到期智能提醒
"""

import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


class PermitType(Enum):
    """许可证类型"""
    SIMPLE = "simple"        # 简化管理
    STANDARD = "standard"    # 重点管理
    DETAILED = "detailed"    # 精细管理


class AlertLevel(Enum):
    """预警级别"""
    GREEN = "green"    # 正常
    YELLOW = "yellow"  # 提醒
    ORANGE = "orange"  # 警告
    RED = "red"        # 紧急


@dataclass
class PermitQuota:
    """许可排放量"""
    pollutant: str
    annual_quota: float  # 年许可量 (t)
    daily_quota: float   # 日许可量 (kg)
    monthly_limit: float  # 月度预警阈值

    # 实时追踪
    used_this_year: float = 0.0
    used_this_month: float = 0.0
    used_today: float = 0.0

    # 状态
    alert_level: AlertLevel = AlertLevel.GREEN
    predicted_exceed_date: str = ""


@dataclass
class PermitIntelligence:
    """排污许可证智能体"""
    permit_id: str
    company_id: str
    company_name: str

    # 许可证信息
    permit_type: PermitType
    permit_number: str = ""
    issue_date: str = ""
    expire_date: str = ""
    issuing_authority: str = ""

    # 许可排放量
    quotas: List[PermitQuota] = field(default_factory=list)

    # 台账信息
    record_frequency: str = ""  # 填报频次
    report_due_dates: List[str] = field(default_factory=list)

    # 状态
    status: str = "valid"  # valid/expired/suspended
    days_to_expire: int = 999
    renewal_reminded: bool = False

    # 元数据
    metadata: Dict = field(default_factory=dict)


@dataclass
class ExecutionReport:
    """执行报告"""
    report_id: str
    report_type: str  # monthly/quarterly/annual

    # 报告期间
    period_start: str = ""
    period_end: str = ""

    # 排放数据
    emissions: List[Dict] = field(default_factory=list)  # 各污染物排放量
    total_emissions: Dict = field(default_factory=dict)   # 汇总

    # 监测数据
    monitoring_data: List[Dict] = field(default_factory=list)

    # 合规判定
    compliance_status: str = "compliant"  # compliant/exceeded
    exceedance_details: List[str] = field(default_factory=list)

    # 附件
    attachments: List[str] = field(default_factory=list)

    # 状态
    auto_generated: bool = True
    submitted: bool = False
    submitted_at: str = ""
    confirmed_by: str = ""


@dataclass
class ProductionSchedule:
    """生产调度建议"""
    date: str
    recommended_production: float  # 建议产能利用率 %
    reason: str
    affected_permits: List[str] = field(default_factory=list)
    estimated_savings: Dict = field(default_factory=dict)  # 节省的许可量


class PermitIntelligenceEngine:
    """
    排污许可智能管家
    ================

    创新点：
    - 从"静态纸质证"转向"动态数据驱动的电子证"
    - AI自动填写40+张申请表
    - 执行报告一键上报全国排污许可平台
    - 预测性预警，自动生成错峰减产建议
    """

    def __init__(self, lifecycle_manager=None):
        self.lifecycle_manager = lifecycle_manager

        # 许可证存储
        self._permits: Dict[str, PermitIntelligence] = {}

        # 执行报告存储
        self._reports: Dict[str, List[ExecutionReport]] = {}

        # 预警规则配置
        self.alert_rules = {
            "daily_usage_ratio": 0.85,  # 日用量超过日均配额85%触发预警
            "monthly_usage_ratio": 0.90,  # 月用量超过年均月配额90%触发预警
            "annual_usage_ratio": 0.80,   # 年用量超过年配额80%触发警告
        }

    def register_permit(self, permit_data: Dict) -> PermitIntelligence:
        """
        注册排污许可证
        ==============
        """
        permit = PermitIntelligence(
            permit_id=permit_data.get('permit_id', str(uuid.uuid4())[:12]),
            company_id=permit_data['company_id'],
            company_name=permit_data['company_name'],
            permit_type=PermitType(permit_data.get('permit_type', 'standard')),
            permit_number=permit_data.get('permit_number', ''),
            issue_date=permit_data.get('issue_date', ''),
            expire_date=permit_data.get('expire_date', ''),
            issuing_authority=permit_data.get('issuing_authority', ''),
            quotas=[],
            metadata=permit_data
        )

        # 计算到期天数
        if permit.expire_date:
            expire_dt = datetime.strptime(permit.expire_date, '%Y-%m-%d')
            permit.days_to_expire = (expire_dt - datetime.now()).days

        self._permits[permit.permit_id] = permit
        return permit

    def add_quota(self, permit_id: str, quota_data: Dict) -> bool:
        """添加许可排放量"""
        permit = self._permits.get(permit_id)
        if not permit:
            return False

        quota = PermitQuota(
            pollutant=quota_data['pollutant'],
            annual_quota=quota_data['annual_quota'],
            daily_quota=quota_data.get('daily_quota', quota_data['annual_quota'] / 365),
            monthly_limit=quota_data.get('monthly_limit', quota_data['annual_quota'] / 12),
        )
        permit.quotas.append(quota)
        return True

    def update_emissions(self, permit_id: str, date: str,
                        emissions: Dict[str, float]) -> bool:
        """
        更新排放数据
        ============

        从DCS/在线监测系统实时抽取数据
        """
        permit = self._permits.get(permit_id)
        if not permit:
            return False

        for quota in permit.quotas:
            pollutant = quota.pollutant
            if pollutant in emissions:
                value = emissions[pollutant]

                # 更新用量
                quota.used_today += value
                quota.used_this_month += value
                quota.used_this_year += value

                # 更新预警状态
                self._update_alert(quota, date)

        return True

    def _update_alert(self, quota: PermitQuota, date: str):
        """更新预警状态"""
        daily_ratio = quota.used_today / quota.daily_quota if quota.daily_quota > 0 else 0
        monthly_ratio = quota.used_this_month / quota.monthly_limit if quota.monthly_limit > 0 else 0
        annual_ratio = quota.used_this_year / quota.annual_quota if quota.annual_quota > 0 else 0

        if daily_ratio >= 1.0 or monthly_ratio >= 1.0:
            quota.alert_level = AlertLevel.RED
            # 预测哪天会超
            if daily_ratio >= 1.0:
                quota.predicted_exceed_date = date
        elif daily_ratio >= 0.95 or monthly_ratio >= 0.95:
            quota.alert_level = AlertLevel.ORANGE
        elif daily_ratio >= 0.85 or annual_ratio >= 0.80:
            quota.alert_level = AlertLevel.YELLOW
        else:
            quota.alert_level = AlertLevel.GREEN

    def predict_exceedance(self, permit_id: str,
                          forecast_days: int = 7) -> List[ProductionSchedule]:
        """
        预测超标风险
        ============

        基于历史数据和当前趋势，预测未来N天是否可能超总量
        生成错峰减产建议
        """
        permit = self._permits.get(permit_id)
        if not permit:
            return []

        schedules = []

        for quota in permit.quotas:
            if quota.alert_level != AlertLevel.GREEN:
                continue

            # 简单预测：基于当前日均用量预测
            if quota.used_this_month > 0:
                avg_daily = quota.used_this_month / 30  # 简化计算
                remaining_days = 30 - datetime.now().day
                projected_monthly = quota.used_this_month + avg_daily * remaining_days

                if projected_monthly > quota.monthly_limit:
                    # 需要减产
                    excess = projected_monthly - quota.monthly_limit
                    recommended_reduction = excess / remaining_days if remaining_days > 0 else 0
                    recommended_rate = max(50, 100 - (recommended_reduction / avg_daily * 100))

                    schedule = ProductionSchedule(
                        date=datetime.now().strftime('%Y-%m-%d'),
                        recommended_production=min(100, recommended_rate),
                        reason=f"{quota.pollutant}月用量预计超标{ excess:.1f}kg，建议减产",
                        affected_permits=[quota.pollutant],
                        estimated_savings={
                            quota.pollutant: excess
                        }
                    )
                    schedules.append(schedule)

        return schedules

    def generate_execution_report(self, permit_id: str,
                                 report_type: str = "monthly",
                                 period: str = None) -> ExecutionReport:
        """
        执行报告自动生成
        ================

        每月1日自动从DCS/在线监测抽取数据，一键上报
        """
        permit = self._permits.get(permit_id)
        if not permit:
            raise ValueError(f"Permit {permit_id} not found")

        # 确定期间
        if period is None:
            if report_type == "monthly":
                now = datetime.now()
                period_start = (now.replace(day=1)).strftime('%Y-%m-%d')
                period_end = (now - timedelta(days=1)).strftime('%Y-%m-%d')
            elif report_type == "quarterly":
                quarter = (datetime.now().month - 1) // 3 + 1
                period_start = f"{datetime.now().year}-{(quarter-1)*3+1:02d}-01"
                period_end = f"{datetime.now().year}-{quarter*3:02d}-01"
            else:
                period_start = f"{datetime.now().year}-01-01"
                period_end = f"{datetime.now().year}-12-31"
        else:
            period_start, period_end = period.split('_')

        # 汇总排放数据
        emissions = []
        total_emissions = {}
        exceedance_details = []

        for quota in permit.quotas:
            if report_type == "monthly":
                used = quota.used_this_month
            elif report_type == "quarterly":
                used = quota.used_this_month * 3  # 简化
            else:
                used = quota.used_this_year

            emissions.append({
                "pollutant": quota.pollutant,
                "used": round(used, 2),
                "quota": quota.annual_quota,
                "usage_rate": round(used / quota.annual_quota * 100, 1) if quota.annual_quota > 0 else 0
            })

            total_emissions[quota.pollutant] = round(used, 2)

            # 合规判定
            if used > quota.annual_quota:
                exceedance_details.append(
                    f"{quota.pollutant}年度用量{used:.2f}t超过年许可量{quota.annual_quota}t"
                )

        report = ExecutionReport(
            report_id=f"ER-{permit_id}-{report_type[:3].upper()}-{datetime.now().strftime('%Y%m')}",
            report_type=report_type,
            period_start=period_start,
            period_end=period_end,
            emissions=emissions,
            total_emissions=total_emissions,
            compliance_status="exceeded" if exceedance_details else "compliant",
            exceedance_details=exceedance_details,
            auto_generated=True
        )

        # 存储
        if permit_id not in self._reports:
            self._reports[permit_id] = []
        self._reports[permit_id].append(report)

        return report

    def submit_report(self, report_id: str) -> bool:
        """
        一键上报执行报告
        ================

        对接全国排污许可证管理信息平台
        """
        # 模拟上报
        print(f"[上报] 执行报告 {report_id} 已提交至全国排污许可信息平台")

        # 更新状态
        for reports in self._reports.values():
            for report in reports:
                if report.report_id == report_id:
                    report.submitted = True
                    report.submitted_at = datetime.now().isoformat()
                    return True

        return False

    def check_renewal_reminder(self, permit_id: str) -> Dict:
        """
        续期提醒检查
        ============

        到期前90天自动提醒，并预填延续申请
        """
        permit = self._permits.get(permit_id)
        if not permit:
            return {}

        reminder = {
            "permit_id": permit_id,
            "days_to_expire": permit.days_to_expire,
            "should_remind": permit.days_to_expire <= 90 and not permit.renewal_reminded,
            "can_renew": 30 <= permit.days_to_expire <= 90,
            "overdue": permit.days_to_expire < 0,
            "actions": []
        }

        if permit.days_to_expire <= 0:
            reminder["actions"].append({
                "action": "许可证已过期，立即停止排放",
                "priority": "critical"
            })
        elif permit.days_to_expire <= 30:
            reminder["actions"].append({
                "action": "立即申请延续，否则面临处罚",
                "priority": "high"
            })
        elif permit.days_to_expire <= 90:
            reminder["actions"].append({
                "action": "开始准备延续申请材料",
                "priority": "medium"
            })
            reminder["actions"].append({
                "action": "AI预填延续申请表（待确认）",
                "priority": "low"
            })

        return reminder

    def auto_fill_renewal_application(self, permit_id: str) -> Dict:
        """
        AI预填延续申请
        ==============

        自动填写40+张申请表
        """
        permit = self._permits.get(permit_id)
        if not permit:
            return {}

        # 模拟预填数据
        application = {
            "basic_info": {
                "permit_number": permit.permit_number,
                "company_name": permit.company_name,
                "report_date": datetime.now().strftime('%Y-%m-%d'),
            },
            "production变化": "无" if permit.metadata.get('production_changed') is False else "需详细填写",
            "pollutant变化": "无" if permit.metadata.get('pollutant_changed') is False else "需详细填写",
            "treatment设施": permit.metadata.get('treatment_equipment', ''),
            "排放口信息": self._generate_outlet_info(permit),
            "许可限值变更申请": "不申请变更",
            "附件清单": [
                "最新监测报告",
                "营业执照",
                "原排污许可证副本",
                "整改证明材料（如有）"
            ]
        }

        return application

    def _generate_outlet_info(self, permit: PermitIntelligence) -> List[Dict]:
        """生成排放口信息"""
        outlets = []
        for quota in permit.quotas:
            outlets.append({
                "排放口编号": f"DA-{quota.pollutant[:2]}",
                "污染物种类": quota.pollutant,
                "排放方式": "有组织排放",
                "年许可排放量": f"{quota.annual_quota}t",
                "排放标准": f"GB{quota.pollutant[:2]}97-1996"
            })
        return outlets

    def get_permit_status(self, permit_id: str) -> Dict:
        """获取许可证状态"""
        permit = self._permits.get(permit_id)
        if not permit:
            return {}

        return {
            "permit_id": permit.permit_id,
            "company_name": permit.company_name,
            "permit_number": permit.permit_number,
            "permit_type": permit.permit_type.value,
            "status": permit.status,
            "days_to_expire": permit.days_to_expire,
            "expire_date": permit.expire_date,
            "quotas": [{
                "pollutant": q.pollutant,
                "annual_quota": q.annual_quota,
                "used_this_year": q.used_this_year,
                "usage_rate": f"{q.used_this_year/q.annual_quota*100:.1f}%" if q.annual_quota > 0 else "0%",
                "alert_level": q.alert_level.value
            } for q in permit.quotas],
            "overall_alert": max([q.alert_level for q in permit.quotas],
                                default=AlertLevel.GREEN).value
        }

    def get_all_alerts(self, company_id: str = None) -> List[Dict]:
        """获取所有预警"""
        alerts = []

        for permit in self._permits.values():
            if company_id and permit.company_id != company_id:
                continue

            for quota in permit.quotas:
                if quota.alert_level != AlertLevel.GREEN:
                    alerts.append({
                        "permit_id": permit.permit_id,
                        "company_name": permit.company_name,
                        "pollutant": quota.pollutant,
                        "alert_level": quota.alert_level.value,
                        "usage_rate": f"{quota.used_this_year/quota.annual_quota*100:.1f}%" if quota.annual_quota > 0 else "0%",
                        "predicted_exceed_date": quota.predicted_exceed_date,
                        "message": self._get_alert_message(quota)
                    })

        return alerts

    def _get_alert_message(self, quota: PermitQuota) -> str:
        """生成预警消息"""
        if quota.alert_level == AlertLevel.RED:
            return f"CRITICAL: {quota.pollutant}今日用量已达日配额{qota.used_today/quota.daily_quota*100:.0f}%，立即处理！"
        elif quota.alert_level == AlertLevel.ORANGE:
            return f"WARNING: {quota.pollutant}用量接近预警线，请关注"
        else:
            return f"INFO: {quota.pollutant}当前用量正常"


def create_permit_engine(lifecycle_manager=None) -> PermitIntelligenceEngine:
    """创建排污许可管家"""
    return PermitIntelligenceEngine(lifecycle_manager)
