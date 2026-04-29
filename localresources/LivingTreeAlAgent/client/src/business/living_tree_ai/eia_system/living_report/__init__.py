"""
活报告系统
让环评报告从"静态快照"变为"持续更新的生命体"
"""

from .living_report_system import (
    # 枚举
    LivingStatus,
    AlertLevel,
    # 数据模型
    MonitoringStation,
    RealTimeData,
    Prediction偏差,
    ComplianceStatus,
    LivingReport,
    # 核心类
    RealTimeDataConnector,
    PredictionTracker,
    ComplianceDashboard,
    LivingReportManager,
    # 工厂函数
    get_living_report_manager,
    create_living_report_async,
    activate_living_report_async,
)

__all__ = [
    "LivingStatus",
    "AlertLevel",
    "MonitoringStation",
    "RealTimeData",
    "Prediction偏差",
    "ComplianceStatus",
    "LivingReport",
    "RealTimeDataConnector",
    "PredictionTracker",
    "ComplianceDashboard",
    "LivingReportManager",
    "get_living_report_manager",
    "create_living_report_async",
    "activate_living_report_async",
]
