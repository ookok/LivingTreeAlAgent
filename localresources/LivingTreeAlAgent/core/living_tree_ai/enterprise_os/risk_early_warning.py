"""
风险预警引擎

实时监测企业风险，提供智能预警和应对建议。
"""

import json
import asyncio
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set, Callable
from enum import Enum
from datetime import datetime, timedelta


# ==================== 数据模型 ====================

class RiskLevel(Enum):
    """风险等级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskCategory(Enum):
    """风险类别"""
    MARKET = "market"           # 市场风险
    OPERATION = "operation"   # 运营风险
    FINANCIAL = "financial"   # 财务风险
    COMPLIANCE = "compliance"  # 合规风险
    TECHNICAL = "technical"    # 技术风险
    POLICY = "policy"         # 政策风险


class MonitorSource(Enum):
    """监测来源"""
    POLICY_NETWORK = "policy_network"     # 政策监测网络
    NEWS_CRAWLER = "news_crawler"         # 新闻爬虫
    OFFICIAL_WEBSITE = "official_website" # 官方政府网站
    ENTERPRISE_DATA = "enterprise_data"   # 企业数据
    USER_INPUT = "user_input"            # 用户输入
    THIRD_PARTY = "third_party"          # 第三方数据


@dataclass
class RiskAlert:
    """风险预警"""
    alert_id: str
    enterprise_id: str
    risk_category: RiskCategory
    risk_level: RiskLevel
    title: str
    description: str
    source: MonitorSource
    source_url: str = ""

    # 影响分析
    impact_scope: str = ""   # 影响范围
    impact_amount: float = 0.0  # 影响金额
    probability: float = 1.0  # 发生概率 0-1

    # 时间
    detected_at: datetime = field(default_factory=datetime.now)
    due_date: Optional[datetime] = None  # 到期日（如证照到期）
    urgency: str = "NORMAL"  # URGENT/NORMAL/LOW

    # 状态
    status: str = "NEW"  # NEW/ACKNOWLEDGED/IN_PROGRESS/RESOLVED/DISMISSED
    resolved_at: Optional[datetime] = None

    # 应对
    suggestions: List[str] = field(default_factory=list)
    action_plan: str = ""
    assigned_to: str = ""


@dataclass
class RiskTemplate:
    """风险模板"""
    template_id: str
    category: RiskCategory
    name: str
    description: str
    indicators: List[Dict] = field(default_factory=list)  # 监测指标
    thresholds: Dict[str, float] = field(default_factory=dict)  # 触发阈值
    risk_level_rules: List[Dict] = field(default_factory=list)


@dataclass
class MonitorTask:
    """监测任务"""
    task_id: str
    alert_id: str
    source: MonitorSource
    status: str = "PENDING"
    result: Dict = field(default_factory=dict)
    error: str = ""
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


# ==================== 风险预警引擎 ====================

class RiskEarlyWarningEngine:
    """
    风险预警引擎

    功能：
    - 政策监测：10000+政策源实时监测
    - 舆情监测：全网舆情实时分析
    - 数据监测：企业数据异常监测
    - 时间监测：证照到期、年报节点监测
    """

    def __init__(self):
        self._alerts: Dict[str, RiskAlert] = {}
        self._templates: Dict[str, RiskTemplate] = {}
        self._monitors: Dict[str, MonitorTask] = {}
        self._subscribers: Dict[str, List[Callable]] = {}  # enterprise_id -> callbacks

        # 初始化内置风险模板
        self._init_builtin_templates()

    def _init_builtin_templates(self):
        """初始化内置风险模板"""
        templates = [
            RiskTemplate(
                template_id="permit_expiry",
                category=RiskCategory.COMPLIANCE,
                name="证照到期预警",
                description="监测企业证照到期时间",
                indicators=[
                    {"type": "date", "field": "permit_expiry_date"},
                    {"type": "days_before", "threshold": 30},
                ],
                thresholds={"days_before": 30},
                risk_level_rules=[
                    {"days": (0, 7), "level": RiskLevel.CRITICAL},
                    {"days": (7, 30), "level": RiskLevel.HIGH},
                    {"days": (30, 60), "level": RiskLevel.MEDIUM},
                ]
            ),
            RiskTemplate(
                template_id="annual_report",
                category=RiskCategory.COMPLIANCE,
                name="年报截止预警",
                description="工商年报截止前提醒",
                indicators=[
                    {"type": "annual_report_due"},
                ],
                thresholds={"days_before": 30},
                risk_level_rules=[
                    {"days": (0, 7), "level": RiskLevel.CRITICAL},
                    {"days": (7, 30), "level": RiskLevel.HIGH},
                ]
            ),
            RiskTemplate(
                template_id="tax_due",
                category=RiskCategory.FINANCIAL,
                name="税务申报预警",
                description="税务申报截止提醒",
                indicators=[
                    {"type": "tax_declaration_due"},
                ],
                thresholds={"days_before": 5},
                risk_level_rules=[
                    {"days": (0, 2), "level": RiskLevel.CRITICAL},
                    {"days": (2, 5), "level": RiskLevel.HIGH},
                ]
            ),
            RiskTemplate(
                template_id="environmental_standard",
                category=RiskCategory.COMPLIANCE,
                name="环保标准更新",
                description="监测环保标准法规更新",
                indicators=[
                    {"type": "regulation_update", "category": "environmental"},
                ],
                thresholds={},
                risk_level_rules=[
                    {"level": RiskLevel.HIGH}
                ]
            ),
            RiskTemplate(
                template_id="emission_exceed",
                category=RiskCategory.COMPLIANCE,
                name="排放超标预警",
                description="监测企业排放数据是否超标",
                indicators=[
                    {"type": "emission_value"},
                    {"type": "standard_value"},
                ],
                thresholds={"ratio": 0.9},  # 达到标准的90%即预警
                risk_level_rules=[
                    {"ratio": (0.9, 1.0), "level": RiskLevel.HIGH},
                    {"ratio": (1.0, float('inf')), "level": RiskLevel.CRITICAL},
                ]
            ),
        ]

        for t in templates:
            self._templates[t.template_id] = t

    def create_alert(
        self,
        enterprise_id: str,
        risk_category: RiskCategory,
        risk_level: RiskLevel,
        title: str,
        description: str,
        source: MonitorSource,
        **kwargs
    ) -> RiskAlert:
        """创建预警"""
        alert_id = self._generate_alert_id(enterprise_id)

        alert = RiskAlert(
            alert_id=alert_id,
            enterprise_id=enterprise_id,
            risk_category=risk_category,
            risk_level=risk_level,
            title=title,
            description=description,
            source=source,
            source_url=kwargs.get("source_url", ""),
            impact_scope=kwargs.get("impact_scope", ""),
            impact_amount=kwargs.get("impact_amount", 0.0),
            probability=kwargs.get("probability", 1.0),
            due_date=kwargs.get("due_date"),
            suggestions=kwargs.get("suggestions", []),
            action_plan=kwargs.get("action_plan", "")
        )

        self._alerts[alert_id] = alert

        # 通知订阅者
        self._notify_subscribers(enterprise_id, alert)

        return alert

    def get_alert(self, alert_id: str) -> Optional[RiskAlert]:
        """获取预警"""
        return self._alerts.get(alert_id)

    def get_alerts_by_enterprise(
        self,
        enterprise_id: str,
        status: str = None,
        category: RiskCategory = None,
        risk_level: RiskLevel = None
    ) -> List[RiskAlert]:
        """获取企业的预警列表"""
        alerts = [
            a for a in self._alerts.values()
            if a.enterprise_id == enterprise_id
        ]

        if status:
            alerts = [a for a in alerts if a.status == status]
        if category:
            alerts = [a for a in alerts if a.risk_category == category]
        if risk_level:
            alerts = [a for a in alerts if a.risk_level == risk_level]

        # 按检测时间倒序
        alerts.sort(key=lambda x: x.detected_at, reverse=True)

        return alerts

    def update_alert_status(
        self,
        alert_id: str,
        status: str
    ) -> bool:
        """更新预警状态"""
        alert = self._alerts.get(alert_id)
        if not alert:
            return False

        alert.status = status

        if status == "RESOLVED":
            alert.resolved_at = datetime.now()

        return True

    def subscribe_alerts(
        self,
        enterprise_id: str,
        callback: Callable[[RiskAlert], None]
    ) -> bool:
        """订阅预警"""
        if enterprise_id not in self._subscribers:
            self._subscribers[enterprise_id] = []

        self._subscribers[enterprise_id].append(callback)
        return True

    def unsubscribe_alerts(
        self,
        enterprise_id: str,
        callback: Callable
    ) -> bool:
        """取消订阅"""
        if enterprise_id not in self._subscribers:
            return False

        try:
            self._subscribers[enterprise_id].remove(callback)
            return True
        except ValueError:
            return False

    def _notify_subscribers(self, enterprise_id: str, alert: RiskAlert):
        """通知订阅者"""
        callbacks = self._subscribers.get(enterprise_id, [])
        for callback in callbacks:
            try:
                callback(alert)
            except Exception:
                pass

    async def check_risks(
        self,
        enterprise_id: str,
        enterprise_data: Dict
    ) -> List[RiskAlert]:
        """
        执行风险检查

        Args:
            enterprise_id: 企业ID
            enterprise_data: 企业数据

        Returns:
            List[RiskAlert]: 生成的预警列表
        """
        new_alerts = []

        # 检查证照到期
        permits = enterprise_data.get("permits", [])
        for permit in permits:
            expiry_date_str = permit.get("expiry_date")
            if not expiry_date_str:
                continue

            try:
                expiry_date = datetime.fromisoformat(expiry_date_str.replace("Z", "+00:00"))
                days_until = (expiry_date - datetime.now()).days

                if days_until <= 60:  # 60天内到期
                    level = self._calculate_risk_level(
                        "permit_expiry",
                        {"days": days_until}
                    )

                    alert = self.create_alert(
                        enterprise_id=enterprise_id,
                        risk_category=RiskCategory.COMPLIANCE,
                        risk_level=level,
                        title=f"证照即将到期: {permit.get('permit_type', '未知')}",
                        description=f"距离到期还有{days_until}天",
                        source=MonitorSource.ENTERPRISE_DATA,
                        due_date=expiry_date,
                        suggestions=[f"请在到期前完成{permit.get('permit_type', '证照')}的续期或更换"]
                    )
                    new_alerts.append(alert)

            except Exception:
                pass

        # 检查年报截止
        annual_report_due = enterprise_data.get("annual_report_due")
        if annual_report_due:
            try:
                due_date = datetime.fromisoformat(annual_report_due.replace("Z", "+00:00"))
                days_until = (due_date - datetime.now()).days

                if days_until <= 30:
                    level = self._calculate_risk_level(
                        "annual_report",
                        {"days": days_until}
                    )

                    alert = self.create_alert(
                        enterprise_id=enterprise_id,
                        risk_category=RiskCategory.COMPLIANCE,
                        risk_level=level,
                        title="工商年报即将截止",
                        description=f"年报截止日期{due_date.strftime('%Y-%m-%d')}，还剩{days_until}天",
                        source=MonitorSource.ENTERPRISE_DATA,
                        due_date=due_date,
                        suggestions=["请尽快完成工商年报的填报和公示"]
                    )
                    new_alerts.append(alert)

            except Exception:
                pass

        # 检查排放数据
        emission_data = enterprise_data.get("emission_data", {})
        for pollutant, data in emission_data.items():
            actual = data.get("actual", 0)
            standard = data.get("standard", float('inf'))

            if actual > 0 and standard < float('inf'):
                ratio = actual / standard

                if ratio >= 0.9:
                    level = self._calculate_risk_level(
                        "emission_exceed",
                        {"ratio": ratio}
                    )

                    alert = self.create_alert(
                        enterprise_id=enterprise_id,
                        risk_category=RiskCategory.COMPLIANCE,
                        risk_level=level,
                        title=f"排放预警: {pollutant}",
                        description=f"{pollutant}排放浓度达到标准的{ratio*100:.1f}%",
                        source=MonitorSource.ENTERPRISE_DATA,
                        suggestions=["建议检查治理设施运行状况"]
                    )
                    new_alerts.append(alert)

        return new_alerts

    def _calculate_risk_level(
        self,
        template_id: str,
        values: Dict[str, float]
    ) -> RiskLevel:
        """根据模板规则计算风险等级"""
        template = self._templates.get(template_id)
        if not template:
            return RiskLevel.MEDIUM

        for rule in template.risk_level_rules:
            rule_values = {k: v for k, v in values.items() if k in rule}

            if self._match_rule(rule, rule_values):
                return rule.get("level", RiskLevel.MEDIUM)

        return RiskLevel.MEDIUM

    def _match_rule(self, rule: Dict, values: Dict[str, float]) -> bool:
        """匹配规则"""
        for key, threshold in rule.items():
            if key == "level":
                continue

            if isinstance(threshold, tuple):
                if not (threshold[0] <= values.get(key, 0) < threshold[1]):
                    return False
            elif isinstance(threshold, (int, float)):
                if key == "days" and values.get(key, 0) > threshold:
                    return False
                elif key == "ratio" and values.get(key, 0) < threshold:
                    return False

        return True

    def get_statistics(self, enterprise_id: str) -> Dict:
        """获取风险统计"""
        alerts = self.get_alerts_by_enterprise(enterprise_id)

        stats = {
            "total": len(alerts),
            "by_status": {},
            "by_level": {},
            "by_category": {},
            "unresolved": len([a for a in alerts if a.status not in ["RESOLVED", "DISMISSED"]]),
            "critical": len([a for a in alerts if a.risk_level == RiskLevel.CRITICAL]),
        }

        for alert in alerts:
            stats["by_status"][alert.status] = stats["by_status"].get(alert.status, 0) + 1
            stats["by_level"][alert.risk_level.value] = stats["by_level"].get(alert.risk_level.value, 0) + 1
            stats["by_category"][alert.risk_category.value] = stats["by_category"].get(alert.risk_category.value, 0) + 1

        return stats

    def _generate_alert_id(self, enterprise_id: str) -> str:
        """生成预警ID"""
        timestamp = datetime.now().isoformat()
        raw = f"{enterprise_id}_{timestamp}"
        return f"alert_{hashlib.md5(raw.encode()).hexdigest()[:12]}"


# ==================== 便捷函数 ====================

_risk_engine_instance: Optional[RiskEarlyWarningEngine] = None


def get_risk_engine() -> RiskEarlyWarningEngine:
    """获取风险引擎单例"""
    global _risk_engine_instance
    if _risk_engine_instance is None:
        _risk_engine_instance = RiskEarlyWarningEngine()
    return _risk_engine_instance


async def check_risks_async(
    enterprise_id: str,
    enterprise_data: Dict
) -> List[RiskAlert]:
    """执行风险检查的便捷函数"""
    engine = get_risk_engine()
    return await engine.check_risks(enterprise_id, enterprise_data)


def subscribe_alerts_async(
    enterprise_id: str,
    callback
) -> bool:
    """订阅预警的便捷函数"""
    engine = get_risk_engine()
    return engine.subscribe_alerts(enterprise_id, callback)
