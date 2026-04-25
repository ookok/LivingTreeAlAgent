"""
密钥健康监控 (Key Health Monitor)
=================================

功能：
1. 密钥健康状态检查
2. 过期预警
3. 异常检测
4. 监控报告生成

Author: Hermes Desktop AI Assistant
"""

import os
import logging
import threading
from typing import Dict, Optional, List, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json
from pathlib import Path

from core.config.unified_config import UnifiedConfig

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """健康状态"""
    HEALTHY = "healthy"           # 健康
    WARNING = "warning"           # 警告
    CRITICAL = "critical"         # 严重
    UNKNOWN = "unknown"           # 未知
    EXPIRED = "expired"           # 已过期


@dataclass
class KeyHealthReport:
    """
    密钥健康报告

    Attributes:
        provider: 提供商名称
        status: 健康状态
        exists: 是否存在
        is_valid: 是否有效
        expires_in_days: 距离过期的天数
        last_validated: 最后验证时间
        last_used: 最后使用时间
        rotation_needed: 是否需要轮转
        issues: 问题列表
        score: 健康评分 (0-100)
    """
    provider: str
    status: HealthStatus
    exists: bool
    is_valid: bool
    expires_in_days: Optional[int] = None
    last_validated: Optional[datetime] = None
    last_used: Optional[datetime] = None
    rotation_needed: bool = False
    issues: List[str] = field(default_factory=list)
    score: int = 100  # 0-100

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'provider': self.provider,
            'status': self.status.value,
            'exists': self.exists,
            'is_valid': self.is_valid,
            'expires_in_days': self.expires_in_days,
            'last_validated': self.last_validated.isoformat() if self.last_validated else None,
            'last_used': self.last_used.isoformat() if self.last_used else None,
            'rotation_needed': self.rotation_needed,
            'issues': self.issues,
            'score': self.score
        }


@dataclass
class SystemHealthReport:
    """
    系统健康报告

    Attributes:
        timestamp: 报告生成时间
        total_keys: 总密钥数
        healthy_keys: 健康密钥数
        warning_keys: 警告密钥数
        critical_keys: 严重密钥数
        expired_keys: 过期密钥数
        overall_score: 整体评分 (0-100)
        key_reports: 各密钥健康报告
        alerts: 告警列表
    """
    timestamp: datetime
    total_keys: int
    healthy_keys: int
    warning_keys: int
    critical_keys: int
    expired_keys: int
    overall_score: int
    key_reports: Dict[str, KeyHealthReport] = field(default_factory=dict)
    alerts: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'total_keys': self.total_keys,
            'healthy_keys': self.healthy_keys,
            'warning_keys': self.warning_keys,
            'critical_keys': self.critical_keys,
            'expired_keys': self.expired_keys,
            'overall_score': self.overall_score,
            'alerts': self.alerts,
            'keys': {k: v.to_dict() for k, v in self.key_reports.items()}
        }


class AlertRule:
    """
    告警规则

    定义何时触发告警
    """

    # 告警阈值配置
    DEFAULT_THRESHOLDS = {
        'expiry_warning_days': 7,      # 过期前7天警告
        'expiry_critical_days': 3,     # 过期前3天严重
        'rotation_warning_days': 30,   # 轮转警告阈值
        'rotation_critical_days': 7,   # 轮转严重阈值
        'validation_age_hours': 24,    # 验证结果有效期
        'unused_days': 30,             # 未使用天数警告
    }

    def __init__(self, thresholds: Dict = None):
        self.thresholds = thresholds or self.DEFAULT_THRESHOLDS.copy()

    def evaluate(self, report: KeyHealthReport) -> List[str]:
        """
        评估密钥健康状态，返回告警列表

        Returns:
            告警消息列表
        """
        alerts = []

        # 已过期
        if report.expires_in_days is not None and report.expires_in_days <= 0:
            alerts.append(f"密钥已过期 {abs(report.expires_in_days)} 天")
            return alerts

        # 即将过期
        if report.expires_in_days is not None:
            if report.expires_in_days <= self.thresholds['expiry_critical_days']:
                alerts.append(f"密钥即将在 {report.expires_in_days} 天后过期（严重）")
            elif report.expires_in_days <= self.thresholds['expiry_warning_days']:
                alerts.append(f"密钥即将在 {report.expires_in_days} 天后过期")

        # 需要轮转
        if report.rotation_needed:
            alerts.append("密钥需要轮转")

        # 未验证
        if report.last_validated:
            age_hours = (datetime.now() - report.last_validated).total_seconds() / 3600
            if age_hours > self.thresholds['validation_age_hours']:
                alerts.append(f"密钥验证结果已过期（{int(age_hours)}小时前）")

        # 未使用
        if report.last_used:
            unused_days = (datetime.now() - report.last_used).days
            if unused_days > self.thresholds['unused_days']:
                alerts.append(f"密钥已 {unused_days} 天未使用")

        # 无效密钥
        if not report.is_valid:
            alerts.append("密钥状态无效")

        return alerts

    def calculate_score(self, report: KeyHealthReport) -> int:
        """
        计算健康评分 (0-100)

        评分规则：
        - 100: 完全健康
        - 80-99: 基本健康，有轻微问题
        - 60-79: 警告状态
        - 30-59: 严重问题
        - 0-29: 危急
        """
        score = 100

        # 过期扣分
        if report.expires_in_days is not None:
            if report.expires_in_days <= 0:
                return 0  # 已过期直接0分
            elif report.expires_in_days <= 3:
                score -= 50
            elif report.expires_in_days <= 7:
                score -= 30
            elif report.expires_in_days <= 30:
                score -= 10

        # 需要轮转扣分
        if report.rotation_needed:
            score -= 20

        # 无效扣分
        if not report.is_valid:
            score -= 50

        # 未验证扣分
        if report.last_validated:
            age_hours = (datetime.now() - report.last_validated).total_seconds() / 3600
            if age_hours > 24:
                score -= 10
            if age_hours > 72:
                score -= 10

        # 未使用扣分
        if report.last_used:
            unused_days = (datetime.now() - report.last_used).days
            if unused_days > 30:
                score -= 10
            if unused_days > 90:
                score -= 10

        return max(0, min(100, score))


class KeyHealthMonitor:
    """
    密钥健康监控

    功能：
    1. 定期检查所有密钥健康状态
    2. 生成健康报告
    3. 触发告警
    4. 提供监控API

    使用示例：
        monitor = KeyHealthMonitor(key_manager)
        report = monitor.check_all_keys()

        # 启动后台监控
        monitor.start(interval=3600)
    """

    def __init__(self, key_manager, config: Optional[Dict] = None):
        """
        初始化健康监控

        Args:
            key_manager: KeyManager实例
            config: 配置字典
        """
        self.key_manager = key_manager
        self.config = config or {}

        # 告警规则
        self.alert_rule = AlertRule(
            thresholds=self.config.get('thresholds')
        )

        # 告警回调
        self._alert_callbacks: List[Callable] = []

        # 监控历史
        self._history: List[SystemHealthReport] = []
        config = UnifiedConfig.get_instance()
        key_health_config = config.get_key_health_config()
        self._max_history = self.config.get('max_history', key_health_config.get("max_history", 100))

        # 后台监控线程
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # 报告输出目录
        self._report_dir = Path(
            self.config.get('report_dir', '~/.ecohub/reports')
        ).expanduser()
        self._report_dir.mkdir(parents=True, exist_ok=True)

        logger.info("KeyHealthMonitor 初始化完成")

    def check_all_keys(self) -> SystemHealthReport:
        """
        检查所有密钥健康状态

        Returns:
            SystemHealthReport: 系统健康报告
        """
        key_reports: Dict[str, KeyHealthReport] = {}
        alerts: List[str] = []

        providers = self.key_manager.storage.list_providers()

        for provider in providers:
            report = self.check_key_health(provider)
            key_reports[provider] = report

            # 收集告警
            key_alerts = self.alert_rule.evaluate(report)
            if key_alerts:
                alerts.extend([f"[{provider}] {alert}" for alert in key_alerts])

        # 统计
        status_counts = {
            HealthStatus.HEALTHY: 0,
            HealthStatus.WARNING: 0,
            HealthStatus.CRITICAL: 0,
            HealthStatus.EXPIRED: 0,
        }

        for report in key_reports.values():
            status_counts[report.status] = status_counts.get(report.status, 0) + 1

        # 计算整体评分
        if key_reports:
            overall_score = sum(r.score for r in key_reports.values()) // len(key_reports)
        else:
            overall_score = 100

        # 确定整体状态
        if status_counts[HealthStatus.EXPIRED] > 0 or status_counts[HealthStatus.CRITICAL] > 0:
            overall_status = HealthStatus.CRITICAL
        elif status_counts[HealthStatus.WARNING] > 0:
            overall_status = HealthStatus.WARNING
        else:
            overall_status = HealthStatus.HEALTHY

        system_report = SystemHealthReport(
            timestamp=datetime.now(),
            total_keys=len(key_reports),
            healthy_keys=status_counts[HealthStatus.HEALTHY],
            warning_keys=status_counts[HealthStatus.WARNING],
            critical_keys=status_counts[HealthStatus.CRITICAL] + status_counts[HealthStatus.EXPIRED],
            expired_keys=status_counts[HealthStatus.EXPIRED],
            overall_score=overall_score,
            key_reports=key_reports,
            alerts=alerts
        )

        # 保存历史
        self._history.append(system_report)
        if len(self._history) > self._max_history:
            self._history.pop(0)

        # 保存报告到文件
        self._save_report(system_report)

        # 触发告警回调
        if alerts:
            self._trigger_alerts(alerts, system_report)

        return system_report

    def check_key_health(self, provider: str) -> KeyHealthReport:
        """
        检查单个密钥健康状态

        Args:
            provider: 提供商名称

        Returns:
            KeyHealthReport: 密钥健康报告
        """
        issues: List[str] = []
        status = HealthStatus.HEALTHY
        score = 100

        # 获取密钥信息
        processed_key = self.key_manager.storage.get_key(provider)
        consumer_info = self.key_manager.consumer.get_key_info(provider) if self.key_manager.consumer else None

        # 检查是否存在
        exists = processed_key is not None

        if not exists:
            return KeyHealthReport(
                provider=provider,
                status=HealthStatus.UNKNOWN,
                exists=False,
                is_valid=False,
                issues=["密钥不存在"],
                score=0
            )

        # 检查有效性
        is_valid = processed_key.is_valid
        if not is_valid:
            issues.append("密钥无效")
            score -= 50

        # 检查过期
        expires_in_days = processed_key.days_until_expiry()
        if expires_in_days is not None:
            if expires_in_days <= 0:
                status = HealthStatus.EXPIRED
                issues.append("密钥已过期")
                score = 0
            elif expires_in_days <= 3:
                status = HealthStatus.CRITICAL
                issues.append(f"密钥将在 {expires_in_days} 天后过期")
                score -= 50
            elif expires_in_days <= 7:
                if status != HealthStatus.CRITICAL:
                    status = HealthStatus.WARNING
                issues.append(f"密钥将在 {expires_in_days} 天后过期")
                score -= 20

        # 检查轮转需求
        rotation_needed = processed_key.needs_rotation(30)
        if rotation_needed:
            if status == HealthStatus.HEALTHY:
                status = HealthStatus.WARNING
            issues.append("密钥需要轮转")
            score -= 15

        # 检查验证状态
        last_validated = getattr(processed_key, 'validation_time', None)
        if last_validated:
            age_hours = (datetime.now() - last_validated).total_seconds() / 3600
            if age_hours > 72:
                issues.append(f"验证结果已过期（{int(age_hours)}小时前）")
                score -= 10

        # 检查使用情况
        last_used = consumer_info.get('last_access') if consumer_info else None
        if last_used:
            if isinstance(last_used, str):
                last_used = datetime.fromisoformat(last_used)
            unused_days = (datetime.now() - last_used).days
            if unused_days > 90:
                issues.append(f"密钥长期未使用（{unused_days}天）")
                score -= 10

        # 确保状态被正确设置
        if not issues and status == HealthStatus.HEALTHY:
            status = HealthStatus.HEALTHY

        return KeyHealthReport(
            provider=provider,
            status=status,
            exists=True,
            is_valid=is_valid,
            expires_in_days=expires_in_days,
            last_validated=last_validated,
            last_used=last_used,
            rotation_needed=rotation_needed,
            issues=issues,
            score=max(0, min(100, score))
        )

    def start(self, interval: Optional[int] = None):
        """
        启动后台监控

        Args:
            interval: 检查间隔（秒），默认从配置读取
        """
        if self._monitor_thread and self._monitor_thread.is_alive():
            logger.warning("监控线程已在运行")
            return

        # 从配置获取监控间隔
        if interval is None:
            config = UnifiedConfig.get_instance()
            interval = config.get_key_health_config()["interval"]

        self._stop_event.clear()
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(interval,),
            daemon=True,
            name="KeyHealthMonitor"
        )
        self._monitor_thread.start()

        logger.info(f"健康监控已启动，间隔: {interval}秒")

    def stop(self):
        """停止后台监控"""
        if not self._monitor_thread:
            return

        self._stop_event.set()
        config = UnifiedConfig.get_instance()
        timeout = config.get_timeout("quick")
        self._monitor_thread.join(timeout=timeout)
        self._monitor_thread = None

        logger.info("健康监控已停止")

    def _monitor_loop(self, interval: int):
        """监控主循环"""
        while not self._stop_event.is_set():
            try:
                report = self.check_all_keys()

                # 记录日志
                if report.alerts:
                    logger.warning(f"健康检查发现 {len(report.alerts)} 个问题")
                else:
                    logger.debug(f"健康检查通过，整体评分: {report.overall_score}")

            except Exception as e:
                logger.error(f"健康监控错误: {e}")

            self._stop_event.wait(interval)

    def _save_report(self, report: SystemHealthReport):
        """保存报告到文件"""
        try:
            # JSON格式
            date_str = report.timestamp.strftime('%Y%m%d')
            json_file = self._report_dir / f"health_report_{date_str}.json"

            # 追加到现有文件或创建新文件
            existing_data = {}
            if json_file.exists():
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        existing_data = json.load(f)
                except Exception:
                    pass

            # 更新数据
            hour_key = report.timestamp.strftime('%H')
            existing_data[hour_key] = report.to_dict()

            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"保存健康报告失败: {e}")

    def _trigger_alerts(self, alerts: List[str], report: SystemHealthReport):
        """触发告警回调"""
        for callback in self._alert_callbacks:
            try:
                callback(alerts, report)
            except Exception as e:
                logger.error(f"告警回调执行失败: {e}")

    def register_alert_callback(self, callback: Callable):
        """注册告警回调"""
        self._alert_callbacks.append(callback)

    def get_health_summary(self) -> Dict[str, Any]:
        """获取健康摘要"""
        if not self._history:
            return {'status': 'no_data'}

        latest = self._history[-1]

        return {
            'overall_score': latest.overall_score,
            'total_keys': latest.total_keys,
            'healthy_keys': latest.healthy_keys,
            'warning_keys': latest.warning_keys,
            'critical_keys': latest.critical_keys,
            'alerts_count': len(latest.alerts),
            'timestamp': latest.timestamp.isoformat()
        }

    def get_history(self, limit: int = 24) -> List[SystemHealthReport]:
        """获取历史报告"""
        return self._history[-limit:]

    def export_report(self, format: str = 'json') -> str:
        """
        导出最新报告

        Args:
            format: 导出格式（json/markdown/html）

        Returns:
            报告内容
        """
        if not self._history:
            return "{}"

        latest = self._history[-1]

        if format == 'json':
            return json.dumps(latest.to_dict(), ensure_ascii=False, indent=2)

        elif format == 'markdown':
            return self._export_markdown(latest)

        elif format == 'html':
            return self._export_html(latest)

        return "{}"

    def _export_markdown(self, report: SystemHealthReport) -> str:
        """导出为Markdown格式"""
        lines = [
            f"# 密钥健康报告",
            f"",
            f"**生成时间**: {report.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            f"",
            f"## 整体状态",
            f"",
            f"| 指标 | 数值 |",
            f"|------|------|",
            f"| 整体评分 | {report.overall_score}/100 |",
            f"| 总密钥数 | {report.total_keys} |",
            f"| 健康 | {report.healthy_keys} |",
            f"| 警告 | {report.warning_keys} |",
            f"| 严重 | {report.critical_keys} |",
            f"| 过期 | {report.expired_keys} |",
            f"",
        ]

        if report.alerts:
            lines.append("## 告警")
            lines.append("")
            for alert in report.alerts:
                lines.append(f"- {alert}")
            lines.append("")

        lines.append("## 密钥详情")
        lines.append("")
        lines.append("| 提供商 | 状态 | 评分 | 过期天数 | 轮转 |")
        lines.append("|--------|------|------|----------|------|")

        for provider, key_report in report.key_reports.items():
            lines.append(
                f"| {provider} | {key_report.status.value} | "
                f"{key_report.score} | {key_report.expires_in_days or 'N/A'} | "
                f"{'是' if key_report.rotation_needed else '否'} |"
            )

        return "\n".join(lines)

    def _export_html(self, report: SystemHealthReport) -> str:
        """导出为HTML格式"""
        # 颜色映射
        status_colors = {
            HealthStatus.HEALTHY: '#4CAF50',
            HealthStatus.WARNING: '#FF9800',
            HealthStatus.CRITICAL: '#F44336',
            HealthStatus.EXPIRED: '#9C27B0',
            HealthStatus.UNKNOWN: '#9E9E9E',
        }

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>密钥健康报告</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .score {{ font-size: 48px; font-weight: bold; }}
        .healthy {{ color: #4CAF50; }}
        .warning {{ color: #FF9800; }}
        .critical {{ color: #F44336; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #4CAF50; color: white; }}
    </style>
</head>
<body>
    <h1>密钥健康报告</h1>
    <p>生成时间: {report.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</p>

    <h2>整体状态</h2>
    <div class="score {'healthy' if report.overall_score >= 80 else 'warning' if report.overall_score >= 60 else 'critical'}">
        {report.overall_score}/100
    </div>

    <h2>统计</h2>
    <ul>
        <li>总密钥数: {report.total_keys}</li>
        <li>健康: {report.healthy_keys}</li>
        <li>警告: {report.warning_keys}</li>
        <li>严重: {report.critical_keys}</li>
        <li>过期: {report.expired_keys}</li>
    </ul>
"""

        if report.alerts:
            html += "<h2>告警</h2><ul>"
            for alert in report.alerts:
                html += f"<li>{alert}</li>"
            html += "</ul>"

        html += """
    <h2>密钥详情</h2>
    <table>
        <tr>
            <th>提供商</th>
            <th>状态</th>
            <th>评分</th>
            <th>过期天数</th>
            <th>需要轮转</th>
        </tr>
"""

        for provider, key_report in report.key_reports.items():
            color = status_colors.get(key_report.status, '#9E9E9E')
            html += f"""
        <tr>
            <td>{provider}</td>
            <td style="color: {color}">{key_report.status.value}</td>
            <td>{key_report.score}</td>
            <td>{key_report.expires_in_days or 'N/A'}</td>
            <td>{'是' if key_report.rotation_needed else '否'}</td>
        </tr>
"""

        html += """
    </table>
</body>
</html>
"""
        return html