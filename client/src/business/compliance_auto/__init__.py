"""
环境合规自动驾驶仪 (Compliance Autopilot)
========================================

让系统像一个"副驾驶"，实时监控企业生产全过程，确保永远不"违规"。

核心功能：
1. 实时合规性监控与预警
2. 动态合规检查（秒级比对）
3. 智能预警与自动联锁
4. 排污许可智能管理

Author: Hermes Desktop Team
"""

import logging
import json
import threading
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import statistics

logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    """预警级别"""
    NORMAL = "normal"
    INFO = "info"                   # 提示
    WARNING = "warning"             # 黄色预警
    CRITICAL = "critical"           # 红色预警
    EMERGENCY = "emergency"         # 紧急


class ComplianceStatus(Enum):
    """合规状态"""
    COMPLIANT = "compliant"         # 合规
    AT_RISK = "at_risk"           # 风险
    NON_COMPLIANT = "non_compliant"  # 不合规
    UNKNOWN = "unknown"            # 未知


class PermitType(Enum):
    """许可类型"""
    AIR_POLLUTION = "air_pollution"     # 大气排放许可
    WATER_POLLUTION = "water_pollution"  # 水排放许可
    SOLID_WASTE = "solid_waste"        # 固废许可
    NOISE = "noise"                   # 噪声许可
    INTEGRATED = "integrated"         # 综合许可


@dataclass
class MonitoringPoint:
    """监控点位"""
    point_id: str
    name: str
    outlet_id: str              # 排放口编号
    pollutant: str              # 监测污染物
    standard_value: float       # 标准限值
    standard_unit: str          # 标准单位
    current_value: float = 0.0  # 当前值
    monitor_time: datetime = None
    equipment_id: str = ""     # 关联设备ID
    location: str = ""          # 位置描述


@dataclass
class ComplianceRule:
    """合规规则"""
    rule_id: str
    name: str
    description: str
    pollutant: str
    standard_type: str          # hourly/daily/monthly/annual
    limit_value: float
    unit: str
    limit_type: str             # max/min/average
    source: str                 # 标准来源（如GB 16297-1996）


@dataclass
class Alert:
    """预警记录"""
    alert_id: str
    timestamp: datetime
    level: AlertLevel
    point_id: str
    point_name: str
    pollutant: str
    current_value: float
    standard_value: float
    exceed_ratio: float         # 超标倍数
    predicted_exceed_time: datetime = None  # 预测超标时间
    message: str = ""
    recommendations: List[str] = field(default_factory=list)
    auto_actions: List[str] = field(default_factory=list)  # 自动执行的动作
    is_handled: bool = False
    handled_time: datetime = None
    handled_by: str = ""


@dataclass
class Permit:
    """排污许可证"""
    permit_id: str
    company_name: str
    permit_type: PermitType
    permit_no: str             # 许可证编号
    issue_date: datetime
    expire_date: datetime
    limits: Dict[str, Dict] = field(default_factory=dict)  # pollutant -> {limit, unit, used, remaining}
    status: str = "valid"     # valid/expired/suspended


@dataclass
class PermitUsage:
    """许可用量追踪"""
    pollutant: str
    annual_limit: float        # 年度许可量
    current_usage: float       # 当前用量
    unit: str
    usage_ratio: float         # 使用比例
    remaining: float          # 剩余量
    warnings: List[str] = field(default_factory=list)


@dataclass
class ComplianceReport:
    """合规报告"""
    report_id: str
    timestamp: datetime
    period_start: datetime
    period_end: datetime
    overall_status: ComplianceStatus
    compliance_rate: float     # 合规率 (0-1)
    alert_summary: Dict[str, int]  # 各级预警数量
    permit_usage: List[PermitUsage]
    recommendations: List[str]
    details: List[Dict] = field(default_factory=list)


class ComplianceAutopilot:
    """
    环境合规自动驾驶仪

    实时监控企业合规状态，提供智能预警和自动联锁。

    使用示例：
    ```python
    autopilot = ComplianceAutopilot(company_id="company_001")

    # 添加监控点位
    autopilot.add_monitoring_point(MonitoringPoint(...))

    # 添加合规规则
    autopilot.add_rule(ComplianceRule(...))

    # 设置排污许可
    autopilot.set_permit(Permit(...))

    # 启动实时监控
    autopilot.start_monitoring()

    # 获取当前合规状态
    status = autopilot.get_compliance_status()

    # 获取预警
    alerts = autopilot.get_active_alerts()
    ```
    """

    def __init__(self, company_id: str, company_name: str = ""):
        self.company_id = company_id
        self.company_name = company_name

        # 监控配置
        self.monitoring_points: Dict[str, MonitoringPoint] = {}
        self.compliance_rules: Dict[str, ComplianceRule] = {}
        self.permits: Dict[str, Permit] = {}

        # 实时数据
        self._realtime_data: Dict[str, List[Tuple[datetime, float]]] = {}  # point_id -> [(time, value)]
        self._alert_history: List[Alert] = []
        self._active_alerts: Dict[str, Alert] = {}  # point_id -> current alert

        # 状态
        self._is_monitoring = False
        self._monitoring_thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()

        # 回调函数
        self._alert_callbacks: List[Callable[[Alert], None]] = []
        self._action_callbacks: List[Callable[[str, Dict], None]] = []  # action, params

        # 阈值配置
        self._thresholds = {
            "warning_ratio": 0.8,      # 预警阈值（80%标准）
            "critical_ratio": 0.9,       # 红色预警阈值（90%标准）
            "prediction_horizon": 120,   # 预测时间范围（分钟）
            "data_retention_days": 90    # 数据保留天数
        }

        # 初始化内置合规规则
        self._init_builtin_rules()

        logger.info(f"创建环境合规自动驾驶仪: {company_id}")

    def _init_builtin_rules(self):
        """初始化内置合规规则"""
        # 大气污染物排放标准 GB 16297-1996
        air_rules = [
            ComplianceRule("GB16297_SO2", "二氧化硫排放限值", "GB 16297-1996",
                         "SO2", "hourly", 500, "mg/m³", "max", "GB 16297-1996"),
            ComplianceRule("GB16297_NO2", "氮氧化物排放限值", "GB 16297-1996",
                         "NO2", "hourly", 200, "mg/m³", "max", "GB 16297-1996"),
            ComplianceRule("GB16297_VOC", "VOCs排放限值", "涂料工业",
                         "VOCs", "hourly", 80, "mg/m³", "max", "GB 16297-1996"),
            ComplianceRule("GB16297_DUST", "颗粒物排放限值", "GB 16297-1996",
                         "颗粒物", "hourly", 30, "mg/m³", "max", "GB 16297-1996"),
        ]

        # 水污染物排放标准 GB 8978-1996
        water_rules = [
            ComplianceRule("GB8978_COD", "COD排放限值", "GB 8978-1996",
                         "COD", "daily", 100, "mg/L", "max", "GB 8978-1996"),
            ComplianceRule("GB8978_NHN", "氨氮排放限值", "GB 8978-1996",
                         "NH3-N", "daily", 15, "mg/L", "max", "GB 8978-1996"),
            ComplianceRule("GB8978_TP", "总磷排放限值", "GB 8978-1996",
                         "TP", "daily", 0.5, "mg/L", "max", "GB 8978-1996"),
        ]

        for rule in air_rules + water_rules:
            self.compliance_rules[rule.rule_id] = rule

    def add_monitoring_point(self, point: MonitoringPoint) -> bool:
        """添加监控点位"""
        with self._lock:
            self.monitoring_points[point.point_id] = point
            self._realtime_data[point.point_id] = []
            logger.info(f"添加监控点位: {point.name}")
            return True

    def remove_monitoring_point(self, point_id: str) -> bool:
        """移除监控点位"""
        with self._lock:
            if point_id in self.monitoring_points:
                del self.monitoring_points[point_id]
                if point_id in self._realtime_data:
                    del self._realtime_data[point_id]
                return True
            return False

    def add_rule(self, rule: ComplianceRule) -> bool:
        """添加合规规则"""
        with self._lock:
            self.compliance_rules[rule.rule_id] = rule
            return True

    def set_permit(self, permit: Permit) -> bool:
        """设置排污许可"""
        with self._lock:
            self.permits[permit.permit_id] = permit
            logger.info(f"设置排污许可: {permit.permit_no}")
            return True

    def update_realtime_value(self, point_id: str, value: float,
                           timestamp: datetime = None) -> Optional[Alert]:
        """
        更新实时数据并检查合规

        Args:
            point_id: 点位ID
            value: 监测值
            timestamp: 时间戳

        Returns:
            如果产生预警，返回预警对象
        """
        if timestamp is None:
            timestamp = datetime.now()

        with self._lock:
            if point_id not in self.monitoring_points:
                return None

            point = self.monitoring_points[point_id]
            point.current_value = value
            point.monitor_time = timestamp

            # 存储数据
            self._realtime_data[point_id].append((timestamp, value))

            # 检查合规
            alert = self._check_compliance(point, timestamp)

            return alert

    def _check_compliance(self, point: MonitoringPoint,
                        timestamp: datetime) -> Optional[Alert]:
        """检查合规状态"""
        standard = point.standard_value
        current = point.current_value

        if standard <= 0:
            return None

        ratio = current / standard

        # 判断预警级别
        level = AlertLevel.NORMAL
        message = ""
        recommendations = []
        auto_actions = []

        if ratio >= self._thresholds["critical_ratio"]:
            level = AlertLevel.CRITICAL
            message = f"红色预警：{point.name} {point.pollutant}浓度达到标准的{ratio*100:.1f}%，接近超标！"
            recommendations = ["立即检查治理设施", "降低生产负荷", "准备应急响应"]
            auto_actions = ["发送紧急通知", "联动中控系统"]

        elif ratio >= self._thresholds["warning_ratio"]:
            level = AlertLevel.WARNING
            message = f"黄色预警：{point.name} {point.pollutant}浓度达到标准的{ratio*100:.1f}%"
            recommendations = ["加强监测频率", "检查设备运行状态", "考虑调整工况"]

        elif ratio >= 1.0:
            level = AlertLevel.EMERGENCY
            message = f"紧急：{point.name} {point.pollutant}浓度超标！"
            recommendations = ["立即停产整改", "启动应急响应", "通知监管部门"]
            auto_actions = ["紧急停机指令", "通知应急部门"]

        # 预测超标时间
        predicted_time = self._predict_exceed_time(point)

        # 创建预警
        alert = None
        if level != AlertLevel.NORMAL:
            alert = Alert(
                alert_id=f"alert_{point_id}_{int(timestamp.timestamp())}",
                timestamp=timestamp,
                level=level,
                point_id=point_id,
                point_name=point.name,
                pollutant=point.pollutant,
                current_value=current,
                standard_value=standard,
                exceed_ratio=ratio,
                predicted_exceed_time=predicted_time,
                message=message,
                recommendations=recommendations,
                auto_actions=auto_actions
            )

            # 更新活跃预警
            if point_id in self._active_alerts:
                old_alert = self._active_alerts[point_id]
                if old_alert.level.value >= level.value:
                    # 保留更高级别的预警
                    return None

            self._active_alerts[point_id] = alert
            self._alert_history.append(alert)

            # 触发回调
            self._trigger_alert_callbacks(alert)

            # 执行自动动作
            if auto_actions:
                self._execute_auto_actions(alert)

        elif point_id in self._active_alerts:
            # 恢复正常，关闭预警
            old_alert = self._active_alerts[point_id]
            old_alert.is_handled = True
            old_alert.handled_time = timestamp
            del self._active_alerts[point_id]

        return alert

    def _predict_exceed_time(self, point: MonitoringPoint) -> Optional[datetime]:
        """预测超标时间"""
        if point.point_id not in self._realtime_data:
            return None

        data = self._realtime_data[point.point_id]
        if len(data) < 10:
            return None

        # 简单线性回归预测
        values = [v for _, v in data[-30:]]  # 最近30个点
        times = list(range(len(values)))

        try:
            # 计算趋势
            mean_x = sum(times) / len(times)
            mean_y = sum(values) / len(values)
            slope = sum((t - mean_x) * (v - mean_y) for t, v in zip(times, values)) / \
                    max(sum((t - mean_x) ** 2 for t in times), 0.001)

            current_value = values[-1]
            threshold = point.standard_value * self._thresholds["critical_ratio"]

            # 预测达到阈值的时间
            if slope > 0 and current_value < threshold:
                minutes_to_threshold = (threshold - current_value) / slope
                if minutes_to_threshold < self._thresholds["prediction_horizon"]:
                    return datetime.now() + timedelta(minutes=minutes_to_threshold)
        except:
            pass

        return None

    def _trigger_alert_callbacks(self, alert: Alert):
        """触发预警回调"""
        for callback in self._alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"预警回调执行失败: {e}")

    def _execute_auto_actions(self, alert: Alert):
        """执行自动动作"""
        for action in alert.auto_actions:
            for callback in self._action_callbacks:
                try:
                    callback(action, {
                        "alert_id": alert.alert_id,
                        "point_id": alert.point_id,
                        "level": alert.level.value
                    })
                except Exception as e:
                    logger.error(f"自动动作执行失败: {e}")

    def register_alert_callback(self, callback: Callable[[Alert], None]):
        """注册预警回调"""
        self._alert_callbacks.append(callback)

    def register_action_callback(self, callback: Callable[[str, Dict], None]):
        """注册动作回调"""
        self._action_callbacks.append(callback)

    def start_monitoring(self, interval_seconds: int = 60):
        """启动实时监控"""
        with self._lock:
            if self._is_monitoring:
                return

            self._is_monitoring = True
            self._monitoring_thread = threading.Thread(
                target=self._monitoring_loop,
                args=(interval_seconds,),
                daemon=True
            )
            self._monitoring_thread.start()
            logger.info("启动环境合规监控")

    def stop_monitoring(self):
        """停止监控"""
        with self._lock:
            self._is_monitoring = False
            if self._monitoring_thread:
                self._monitoring_thread.join(timeout=5)
            logger.info("停止环境合规监控")

    def _monitoring_loop(self, interval_seconds: int):
        """监控循环"""
        while self._is_monitoring:
            try:
                # 模拟从DCS/PLC获取数据
                self._fetch_dcs_data()
            except Exception as e:
                logger.error(f"监控循环异常: {e}")

            threading.Event().wait(interval_seconds)

    def _fetch_dcs_data(self):
        """从DCS/PLC获取数据（实际需要对接真实系统）"""
        # 模拟数据
        for point in self.monitoring_points.values():
            # 模拟波动
            base_value = point.standard_value * random.uniform(0.3, 0.9)
            noise = random.uniform(-0.1, 0.1) * base_value
            value = base_value + noise

            self.update_realtime_value(point.point_id, value)

    def get_compliance_status(self) -> ComplianceStatus:
        """获取当前合规状态"""
        if not self._active_alerts:
            return ComplianceStatus.COMPLIANT

        # 检查是否有高等级预警
        has_critical = any(
            a.level in [AlertLevel.CRITICAL, AlertLevel.EMERGENCY]
            for a in self._active_alerts.values()
        )
        has_warning = any(
            a.level == AlertLevel.WARNING
            for a in self._active_alerts.values()
        )

        if has_critical:
            return ComplianceStatus.NON_COMPLIANT
        elif has_warning:
            return ComplianceStatus.AT_RISK

        return ComplianceStatus.COMPLIANT

    def get_active_alerts(self, level: AlertLevel = None) -> List[Alert]:
        """获取活跃预警"""
        alerts = list(self._active_alerts.values())
        if level:
            alerts = [a for a in alerts if a.level == level]
        return alerts

    def get_permit_usage(self) -> List[PermitUsage]:
        """获取许可用量"""
        usage_list = []

        for permit in self.permits.values():
            for pollutant, limit_info in permit.limits.items():
                annual_limit = limit_info.get("limit", 0)
                used = limit_info.get("used", 0)
                unit = limit_info.get("unit", "t")

                remaining = max(annual_limit - used, 0)
                usage_ratio = used / max(annual_limit, 1)

                warnings = []
                if usage_ratio >= 0.95:
                    warnings.append("⚠️ 接近年度许可总量！")
                elif usage_ratio >= 0.80:
                    warnings.append("📊 已使用80%以上年度配额")

                usage_list.append(PermitUsage(
                    pollutant=pollutant,
                    annual_limit=annual_limit,
                    current_usage=used,
                    unit=unit,
                    usage_ratio=usage_ratio,
                    remaining=remaining,
                    warnings=warnings
                ))

        return usage_list

    def generate_compliance_report(self,
                                 period_start: datetime,
                                 period_end: datetime) -> ComplianceReport:
        """
        生成合规报告

        Args:
            period_start: 报告期起始
            period_end: 报告期结束

        Returns:
            合规报告
        """
        # 统计预警
        period_alerts = [
            a for a in self._alert_history
            if period_start <= a.timestamp <= period_end
        ]

        alert_summary = {
            "total": len(period_alerts),
            "critical": len([a for a in period_alerts if a.level == AlertLevel.CRITICAL]),
            "warning": len([a for a in period_alerts if a.level == AlertLevel.WARNING]),
            "info": len([a for a in period_alerts if a.level == AlertLevel.INFO]),
        }

        # 计算合规率
        total_checks = sum(
            len(self._realtime_data.get(p.point_id, []))
            for p in self.monitoring_points.values()
        )
        exceed_checks = len(period_alerts)
        compliance_rate = 1.0 - (exceed_checks / max(total_checks, 1))

        # 获取许可用量
        permit_usage = self.get_permit_usage()

        # 生成建议
        recommendations = []

        if alert_summary["critical"] > 0:
            recommendations.append("🚨 立即处理红色预警，避免超标排放")

        if alert_summary["warning"] > 5:
            recommendations.append("⚠️ 黄色预警频繁，建议全面检查治理设施")

        for usage in permit_usage:
            if usage.usage_ratio > 0.9:
                recommendations.append(
                    f"📊 {usage.pollutant}已使用{usage.usage_ratio*100:.0f}%年度配额，"
                    f"剩余{usage.remaining}{usage.unit}，建议规划减产或购买排污权"
                )

        if not recommendations:
            recommendations.append("✅ 当前合规状态良好，继续保持")

        report = ComplianceReport(
            report_id=f"report_{int(datetime.now().timestamp())}",
            timestamp=datetime.now(),
            period_start=period_start,
            period_end=period_end,
            overall_status=self.get_compliance_status(),
            compliance_rate=compliance_rate,
            alert_summary=alert_summary,
            permit_usage=permit_usage,
            recommendations=recommendations
        )

        return report

    def export_report(self, report: ComplianceReport,
                    format: str = "json") -> str:
        """导出报告"""
        if format == "json":
            return json.dumps({
                "report_id": report.report_id,
                "timestamp": report.timestamp.isoformat(),
                "period": f"{report.period_start.isoformat()} ~ {report.period_end.isoformat()}",
                "overall_status": report.overall_status.value,
                "compliance_rate": f"{report.compliance_rate*100:.2f}%",
                "alert_summary": report.alert_summary,
                "permit_usage": [
                    {
                        "pollutant": u.pollutant,
                        "usage": f"{u.current_usage}/{u.annual_limit} {u.unit}",
                        "ratio": f"{u.usage_ratio*100:.1f}%"
                    }
                    for u in report.permit_usage
                ],
                "recommendations": report.recommendations
            }, ensure_ascii=False, indent=2)
        return ""

    def to_dict(self) -> Dict[str, Any]:
        """导出配置"""
        return {
            "company_id": self.company_id,
            "company_name": self.company_name,
            "monitoring_points_count": len(self.monitoring_points),
            "rules_count": len(self.compliance_rules),
            "permits_count": len(self.permits),
            "active_alerts_count": len(self._active_alerts),
            "compliance_status": self.get_compliance_status().value,
            "is_monitoring": self._is_monitoring
        }


class PermitManager:
    """
    排污许可智能管理器

    自动填报、许可量预警、交易建议
    """

    def __init__(self, autopilot: ComplianceAutopilot = None):
        self.autopilot = autopilot
        self._permit_applications: Dict[str, Dict] = {}  # 待提交的申请

    def calculate_current_usage(self, pollutant: str) -> float:
        """计算当前用量"""
        # 简化实现
        return 0.0

    def check_permit_thresholds(self) -> List[Dict]:
        """检查许可量阈值"""
        warnings = []

        if not self.autopilot:
            return warnings

        usage_list = self.autopilot.get_permit_usage()

        for usage in usage_list:
            ratio = usage.usage_ratio

            if ratio >= 0.95:
                warnings.append({
                    "level": "critical",
                    "pollutant": usage.pollutant,
                    "message": f"{usage.pollutant}已达{ratio*100:.0f}%年度许可量，建议立即减产",
                    "actions": ["错峰生产", "购买排污权", "紧急减排"]
                })
            elif ratio >= 0.90:
                warnings.append({
                    "level": "warning",
                    "pollutant": usage.pollutant,
                    "message": f"{usage.pollutant}已达{ratio*100:.0f}%年度许可量",
                    "actions": ["优化生产工艺", "提升治理效率"]
                })
            elif ratio >= 0.80:
                warnings.append({
                    "level": "info",
                    "pollutant": usage.pollutant,
                    "message": f"{usage.pollutant}已使用{ratio*100:.0f}%年度许可量",
                    "actions": ["关注用量变化"]
                })

        return warnings

    def generate_auto_report(self, period: str = "monthly") -> Dict:
        """生成自动报告"""
        now = datetime.now()

        if period == "monthly":
            start = now.replace(day=1, hour=0, minute=0, second=0)
        elif period == "quarterly":
            quarter = (now.month - 1) // 3
            start = now.replace(month=quarter * 3 + 1, day=1, hour=0, minute=0, second=0)
        else:  # yearly
            start = now.replace(month=1, day=1, hour=0, minute=0, second=0)

        if self.autopilot:
            report = self.autopilot.generate_compliance_report(start, now)
            return self.autopilot.export_report(report)

        return {}

    def suggest_trading(self, pollutant: str) -> Dict:
        """交易建议"""
        if not self.autopilot:
            return {}

        usage_list = self.autopilot.get_permit_usage()
        usage = next((u for u in usage_list if u.pollutant == pollutant), None)

        if not usage:
            return {}

        suggestions = []

        # 如果剩余量充足
        if usage.usage_ratio < 0.7:
            suggestions.append({
                "action": "sell",
                "quantity": usage.remaining * 0.3,  # 建议出售30%的富余量
                "reason": "富余量充足，可考虑交易"
            })

        # 如果剩余量不足
        if usage.usage_ratio > 0.85:
            suggestions.append({
                "action": "buy",
                "quantity": usage.annual_limit * 0.2,  # 建议购买20%的年配额
                "reason": "配额紧张，建议购买"
            })

        return {
            "pollutant": pollutant,
            "current_usage_ratio": usage.usage_ratio,
            "remaining": usage.remaining,
            "suggestions": suggestions
        }


# 全局单例
_autopilot_instances: Dict[str, ComplianceAutopilot] = {}
_autopilot_lock = threading.Lock()


def get_compliance_autopilot(company_id: str, company_name: str = "") -> ComplianceAutopilot:
    """获取合规自动驾驶仪实例"""
    with _autopilot_lock:
        if company_id not in _autopilot_instances:
            _autopilot_instances[company_id] = ComplianceAutopilot(company_id, company_name)
        return _autopilot_instances[company_id]
