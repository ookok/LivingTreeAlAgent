"""
活报告系统 - 基于实时数据的"活报告"
让环评报告从"静态快照"变为"持续更新的生命体"

核心能力：
1. 数据自动更新（实时监测站API）
2. 预测准确性追踪（偏差率计算）
3. 合规状态仪表盘
"""

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional


# ============================================================================
# 数据模型
# ============================================================================

class LivingStatus(Enum):
    """活报告状态"""
    DRAFT = "draft"        # 草稿
    ACTIVE = "active"      # 活跃
    MONITORING = "monitoring"  # 监测中
    WARNING = "warning"    # 预警
    ALERT = "alert"        # 告警
    ARCHIVED = "archived"  # 已归档


class AlertLevel(Enum):
    """预警级别"""
    NORMAL = "normal"      # 正常
    INFO = "info"         # 提示
    WARNING = "warning"    # 警告
    DANGER = "danger"     # 危险
    CRITICAL = "critical" # 严重


@dataclass
class MonitoringStation:
    """监测站"""
    station_id: str
    name: str
    station_type: str  # "air", "water", "noise"
    lat: float
    lon: float
    pollutants: list = field(default_factory=list)
    api_url: str = ""


@dataclass
class RealTimeData:
    """实时数据"""
    station_id: str
    pollutant: str
    value: float
    unit: str
    timestamp: datetime
    quality: str = "normal"  # "normal", "abnormal"


@dataclass
class Prediction偏差:
    """预测偏差"""
    pollutant: str
    predicted_value: float
    actual_value: float
    deviation_rate: float  # (actual - predicted) / predicted * 100
    timestamp: datetime
    is_within_tolerance: bool


@dataclass
class ComplianceStatus:
    """合规状态"""
    emission_vs_predicted: dict  # 实际排放 vs 预测排放
    emission_vs_standard: dict  # 实际排放 vs 标准限值
    measures_status: dict        # 环保措施运行状态
    upcoming_inspections: list    # 即将到来的检查
    alert_level: AlertLevel
    summary: str


@dataclass
class LivingReport:
    """活报告"""
    report_id: str
    project_id: str
    project_name: str
    status: LivingStatus
    baseline_data: dict  # 原始报告数据
    current_data: dict   # 当前最新数据
    predictions: list    # 预测追踪记录
    deviations: list     # 偏差记录
    compliance: ComplianceStatus
    dashboard_url: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    monitoring_stations: list = field(default_factory=list)


# ============================================================================
# 实时数据连接器
# ============================================================================

class RealTimeDataConnector:
    """实时数据连接器"""

    def __init__(self, config: dict = None):
        self.config = config or {}
        self._stations_cache = {}
        self._last_fetch = {}

    async def fetch_air_quality(self, station_id: str) -> list[RealTimeData]:
        """获取空气质量数据"""
        # 实际应用中，这里调用真实API
        # 例如：国家环境监测总站API、地方环保局API

        # 模拟数据
        await asyncio.sleep(0.2)

        pollutants = ["PM2.5", "PM10", "SO2", "NO2", "O3", "CO"]
        data = []

        for pollutant in pollutants:
            import random
            data.append(RealTimeData(
                station_id=station_id,
                pollutant=pollutant,
                value=round(random.uniform(10, 100), 2),
                unit="μg/m³",
                timestamp=datetime.now(),
                quality=random.choice(["normal", "normal", "normal", "abnormal"])
            ))

        return data

    async def fetch_water_quality(self, station_id: str) -> list[RealTimeData]:
        """获取水质数据"""
        await asyncio.sleep(0.2)

        pollutants = ["pH", "COD", "BOD", "NH3-N", "TP", "TN"]
        data = []

        for pollutant in pollutants:
            import random
            data.append(RealTimeData(
                station_id=station_id,
                pollutant=pollutant,
                value=round(random.uniform(5, 50), 2),
                unit="mg/L",
                timestamp=datetime.now()
            ))

        return data

    async def find_nearby_stations(
        self,
        lat: float,
        lon: float,
        radius_km: float = 50,
        station_type: str = "air"
    ) -> list[MonitoringStation]:
        """查找附近的监测站"""
        # 模拟数据
        return [
            MonitoringStation(
                station_id="station_001",
                name="市区环境监测站",
                station_type=station_type,
                lat=lat + 0.01,
                lon=lon + 0.01,
                pollutants=["PM2.5", "PM10", "SO2", "NO2"]
            ),
            MonitoringStation(
                station_id="station_002",
                name="开发区监测站",
                station_type=station_type,
                lat=lat + 0.05,
                lon=lon - 0.02,
                pollutants=["PM2.5", "PM10", "O3", "CO"]
            )
        ]

    async def get_station_data(
        self,
        station_id: str,
        start_time: datetime,
        end_time: datetime
    ) -> list[RealTimeData]:
        """获取监测站历史数据"""
        # 模拟数据
        await asyncio.sleep(0.3)

        data = []
        current = start_time
        while current <= end_time:
            data.append(RealTimeData(
                station_id=station_id,
                pollutant="PM2.5",
                value=round(50 + (current.hour - 12) ** 2 * 0.5, 2),
                unit="μg/m³",
                timestamp=current
            ))
            current += timedelta(hours=1)

        return data


# ============================================================================
# 预测准确性追踪器
# ============================================================================

class PredictionTracker:
    """预测准确性追踪器"""

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.tolerance_threshold = self.config.get("tolerance_threshold", 20)  # 20%容差

    async def track_prediction(
        self,
        report_id: str,
        pollutant: str,
        predicted_value: float,
        actual_value: float,
        timestamp: datetime = None
    ) -> Prediction偏差:
        """追踪预测偏差"""
        timestamp = timestamp or datetime.now()

        deviation_rate = ((actual_value - predicted_value) / predicted_value) * 100
        is_within_tolerance = abs(deviation_rate) <= self.tolerance_threshold

        deviation = Prediction偏差(
            pollutant=pollutant,
            predicted_value=predicted_value,
            actual_value=actual_value,
            deviation_rate=deviation_rate,
            timestamp=timestamp,
            is_within_tolerance=is_within_tolerance
        )

        # 如果偏差过大，触发预警
        if not is_within_tolerance:
            await self._trigger_alert(report_id, deviation)

        return deviation

    async def _trigger_alert(self, report_id: str, deviation: Prediction偏差):
        """触发预警"""
        # 实际应用中，这里会发送通知
        print(f"[ALERT] Report {report_id}: {deviation.pollutant} 偏差 {deviation.deviation_rate:.1f}%")

    async def calculate_model_accuracy(
        self,
        deviations: list[Prediction偏差]
    ) -> dict:
        """计算模型准确率"""
        if not deviations:
            return {"accuracy": 0, "avg_deviation": 0, "count": 0}

        within_tolerance = sum(1 for d in deviations if d.is_within_tolerance)
        accuracy = within_tolerance / len(deviations) * 100
        avg_deviation = sum(abs(d.deviation_rate) for d in deviations) / len(deviations)

        return {
            "accuracy": round(accuracy, 2),
            "avg_deviation": round(avg_deviation, 2),
            "count": len(deviations)
        }


# ============================================================================
# 合规状态仪表盘
# ============================================================================

class ComplianceDashboard:
    """合规状态仪表盘"""

    def __init__(self, config: dict = None):
        self.config = config or {}

    def generate_dashboard_url(self, report_id: str, project_name: str) -> str:
        """生成仪表盘URL"""
        # 实际应用中，这里部署到P2P网络或本地服务器
        return f"/dashboard/{report_id}"

    def generate_dashboard_html(self, report: LivingReport) -> str:
        """生成仪表盘HTML"""
        compliance = report.compliance

        emission_cards = ""
        for pollutant, data in compliance.emission_vs_predicted.items():
            predicted = data.get("predicted", 0)
            actual = data.get("actual", 0)
            ratio = (actual / predicted * 100) if predicted > 0 else 0

            color = "success" if ratio <= 100 else "warning" if ratio <= 120 else "danger"

            emission_cards += f"""
            <div class="col-md-4 mb-3">
                <div class="card border-{color}">
                    <div class="card-header bg-{color} text-white">
                        {pollutant}
                    </div>
                    <div class="card-body">
                        <h4>{actual:.2f}</h4>
                        <p class="mb-1">实测值</p>
                        <hr>
                        <p class="mb-0 text-muted">
                            预测: {predicted:.2f} |
                            比例: {ratio:.0f}%
                        </p>
                    </div>
                </div>
            </div>
            """

        alert_badge = self._get_alert_badge(compliance.alert_level)

        return f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{report.project_name} - 合规仪表盘</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
    <style>
        body {{
            background: #f0f2f5;
            font-family: 'Microsoft YaHei', sans-serif;
        }}
        .dashboard-header {{
            background: linear-gradient(135deg, #1976D2, #42A5F5);
            color: white;
            padding: 2rem 0;
        }}
        .status-badge {{
            font-size: 1.5rem;
            padding: 0.5rem 1.5rem;
            border-radius: 30px;
        }}
        .card {{ border-radius: 12px; }}
        .card.border-success {{ border-width: 2px; }}
        .card.border-warning {{ border-width: 2px; }}
        .card.border-danger {{ border-width: 2px; }}
        #mainChart, #trendChart {{
            height: 300px;
        }}
    </style>
</head>
<body>
    <div class="dashboard-header">
        <div class="container">
            <h1>🌲 {report.project_name}</h1>
            <p class="mb-0">
                合规状态仪表盘 |
                <span class="status-badge bg-{self._get_alert_color(compliance.alert_level)}">
                    {alert_badge}
                </span>
            </p>
        </div>
    </div>

    <div class="container my-4">
        <!-- 概览 -->
        <div class="row mb-4">
            <div class="col-md-3">
                <div class="card text-center">
                    <div class="card-body">
                        <h3>{len(compliance.emission_vs_predicted)}</h3>
                        <p class="mb-0 text-muted">监测污染物</p>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-center">
                    <div class="card-body">
                        <h3>{len(report.deviations)}</h3>
                        <p class="mb-0 text-muted">偏差记录</p>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-center">
                    <div class="card-body">
                        <h3>{len(compliance.upcoming_inspections)}</h3>
                        <p class="mb-0 text-muted">待执行检查</p>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-center">
                    <div class="card-body">
                        <h3>{report.updated_at.strftime('%Y-%m-%d')}</h3>
                        <p class="mb-0 text-muted">最后更新</p>
                    </div>
                </div>
            </div>
        </div>

        <!-- 排放对比 -->
        <div class="card mb-4">
            <div class="card-header">
                <h5 class="mb-0">📊 实际排放 vs 预测排放</h5>
            </div>
            <div class="card-body">
                <div class="row">
                    {emission_cards}
                </div>
                <div id="mainChart" class="mt-4"></div>
            </div>
        </div>

        <!-- 趋势图 -->
        <div class="card mb-4">
            <div class="card-header">
                <h5 class="mb-0">📈 预测偏差趋势</h5>
            </div>
            <div class="card-body">
                <div id="trendChart"></div>
            </div>
        </div>

        <!-- 预警信息 -->
        <div class="card">
            <div class="card-header bg-{self._get_alert_color(compliance.alert_level)} text-white">
                <h5 class="mb-0">{alert_badge} {compliance.summary}</h5>
            </div>
            <div class="card-body">
                <ul class="list-group">
                    {self._generate_alert_items(compliance)}
                </ul>
            </div>
        </div>
    </div>

    <script>
        // 初始化图表
        document.addEventListener('DOMContentLoaded', function() {{
            // 主图表
            var mainChart = echarts.init(document.getElementById('mainChart'));
            mainChart.setOption({{
                tooltip: {{ trigger: 'axis' }},
                legend: {{ data: ['预测值', '实测值'] }},
                xAxis: {{ type: 'category', data: ['1月', '2月', '3月', '4月', '5月', '6月'] }},
                yAxis: {{ type: 'value' }},
                series: [
                    {{
                        name: '预测值',
                        type: 'bar',
                        data: [820, 932, 901, 934, 1290, 1330]
                    }},
                    {{
                        name: '实测值',
                        type: 'bar',
                        data: [850, 950, 880, 980, 1250, 1380]
                    }}
                ]
            }});

            // 趋势图
            var trendChart = echarts.init(document.getElementById('trendChart'));
            trendChart.setOption({{
                tooltip: {{ trigger: 'axis' }},
                xAxis: {{ type: 'category', data: ['1月', '2月', '3月', '4月', '5月', '6月'] }},
                yAxis: {{ type: 'value', name: '偏差率%' }},
                series: [{{
                    type: 'line',
                    data: [5, 8, -3, 12, 15, -7],
                    smooth: true,
                    areaStyle: {{}}
                }}]
            }});
        }});
    </script>
</body>
</html>
"""

    def _get_alert_badge(self, level: AlertLevel) -> str:
        badges = {
            AlertLevel.NORMAL: "✅ 正常",
            AlertLevel.INFO: "ℹ️ 提示",
            AlertLevel.WARNING: "⚠️ 警告",
            AlertLevel.DANGER: "🚨 危险",
            AlertLevel.CRITICAL: "🔴 严重"
        }
        return badges.get(level, "❓ 未知")

    def _get_alert_color(self, level: AlertLevel) -> str:
        colors = {
            AlertLevel.NORMAL: "success",
            AlertLevel.INFO: "info",
            AlertLevel.WARNING: "warning",
            AlertLevel.DANGER: "danger",
            AlertLevel.CRITICAL: "dark"
        }
        return colors.get(level, "secondary")

    def _generate_alert_items(self, compliance: ComplianceStatus) -> str:
        items = []

        # 检查超标
        for pollutant, data in compliance.emission_vs_standard.items():
            limit = data.get("limit", 0)
            actual = data.get("actual", 0)
            if actual > limit:
                items.append(f'<li class="list-group-item list-group-item-danger">🚨 {pollutant} 实测值 {actual} 超过标准限值 {limit}</li>')

        # 检查即将到来的检查
        for inspection in compliance.upcoming_inspections:
            items.append(f'<li class="list-group-item list-group-item-warning">📅 {inspection["name"]} - {inspection["date"]}</li>')

        # 检查措施状态
        for measure, status in compliance.measures_status.items():
            if status != "running":
                items.append(f'<li class="list-group-item list-group-item-info">🔧 {measure}: {status}</li>')

        if not items:
            return '<li class="list-group-item list-group-item-success">✅ 所有指标正常，无预警信息</li>'

        return "\n".join(items)


# ============================================================================
# 活报告管理器（主入口）
# ============================================================================

class LivingReportManager:
    """活报告管理器"""

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.data_connector = RealTimeDataConnector(config)
        self.prediction_tracker = PredictionTracker(config)
        self.dashboard = ComplianceDashboard(config)
        self._reports: dict = {}
        self._monitoring_tasks: dict = {}

    async def create_living_report(
        self,
        report_id: str,
        project_name: str,
        baseline_data: dict,
        project_lat: float = None,
        project_lon: float = None
    ) -> LivingReport:
        """创建活报告"""
        # 查找附近监测站
        stations = []
        if project_lat and project_lon:
            stations = await self.data_connector.find_nearby_stations(
                project_lat, project_lon
            )

        # 创建合规状态
        compliance = ComplianceStatus(
            emission_vs_predicted={},
            emission_vs_standard={},
            measures_status={},
            upcoming_inspections=[],
            alert_level=AlertLevel.NORMAL,
            summary="暂无预警信息"
        )

        report = LivingReport(
            report_id=report_id,
            project_id=baseline_data.get("project_id", report_id),
            project_name=project_name,
            status=LivingStatus.DRAFT,
            baseline_data=baseline_data,
            current_data={},
            predictions=[],
            deviations=[],
            compliance=compliance,
            dashboard_url=self.dashboard.generate_dashboard_url(report_id, project_name),
            monitoring_stations=stations
        )

        self._reports[report_id] = report
        return report

    async def activate_report(self, report_id: str) -> LivingReport:
        """激活报告监测"""
        report = self._reports.get(report_id)
        if not report:
            raise ValueError(f"Report {report_id} not found")

        report.status = LivingStatus.ACTIVE

        # 启动监测任务
        self._monitoring_tasks[report_id] = asyncio.create_task(
            self._monitor_loop(report_id)
        )

        return report

    async def _monitor_loop(self, report_id: str):
        """监测循环"""
        report = self._reports.get(report_id)
        if not report:
            return

        while report.status in [LivingStatus.ACTIVE, LivingStatus.MONITORING]:
            try:
                # 更新实时数据
                await self._update_current_data(report)

                # 检查合规状态
                self._check_compliance(report)

                # 更新状态
                if report.compliance.alert_level in [AlertLevel.DANGER, AlertLevel.CRITICAL]:
                    report.status = LivingStatus.ALERT
                elif report.compliance.alert_level == AlertLevel.WARNING:
                    report.status = LivingStatus.WARNING
                else:
                    report.status = LivingStatus.MONITORING

                report.updated_at = datetime.now()

            except Exception as e:
                print(f"Monitor error: {e}")

            # 每小时检查一次
            await asyncio.sleep(3600)

    async def _update_current_data(self, report: LivingReport):
        """更新当前数据"""
        for station in report.monitoring_stations:
            if station.station_type == "air":
                data = await self.data_connector.fetch_air_quality(station.station_id)
            else:
                data = await self.data_connector.fetch_water_quality(station.station_id)

            for item in data:
                key = f"{item.station_id}_{item.pollutant}"
                if key not in report.current_data:
                    report.current_data[key] = []

                report.current_data[key].append(item)

    def _check_compliance(self, report: LivingReport):
        """检查合规状态"""
        # 简化实现
        max_alert = AlertLevel.NORMAL

        # 检查排放
        for pollutant, data in report.baseline_data.get("predicted_emissions", {}).items():
            predicted = data.get("value", 0)
            actual = self._get_latest_value(report, pollutant)

            report.compliance.emission_vs_predicted[pollutant] = {
                "predicted": predicted,
                "actual": actual
            }

            # 检查是否超标
            limit = data.get("limit", predicted * 1.2)
            report.compliance.emission_vs_standard[pollutant] = {
                "limit": limit,
                "actual": actual
            }

            if actual > limit:
                max_alert = max(max_alert, AlertLevel.DANGER)

        # 生成总结
        if max_alert == AlertLevel.NORMAL:
            report.compliance.summary = "所有指标正常"
        elif max_alert == AlertLevel.WARNING:
            report.compliance.summary = "部分指标接近限值，建议关注"
        else:
            report.compliance.summary = "存在超标情况，需要立即处理"

        report.compliance.alert_level = max_alert

    def _get_latest_value(self, report: LivingReport, pollutant: str) -> float:
        """获取最新值"""
        for key, data_list in report.current_data.items():
            if pollutant in key and data_list:
                return data_list[-1].value
        return 0

    async def record_prediction_偏差(
        self,
        report_id: str,
        pollutant: str,
        predicted_value: float,
        actual_value: float
    ) -> Prediction偏差:
        """记录预测偏差"""
        report = self._reports.get(report_id)
        if not report:
            raise ValueError(f"Report {report_id} not found")

        deviation = await self.prediction_tracker.track_prediction(
            report_id, pollutant, predicted_value, actual_value
        )

        report.deviations.append(deviation)
        return deviation

    def generate_dashboard(self, report_id: str) -> str:
        """生成仪表盘"""
        report = self._reports.get(report_id)
        if not report:
            raise ValueError(f"Report {report_id} not found")

        return self.dashboard.generate_dashboard_html(report)

    def get_report(self, report_id: str) -> Optional[LivingReport]:
        """获取报告"""
        return self._reports.get(report_id)

    def get_model_accuracy(self, report_id: str) -> dict:
        """获取模型准确率"""
        report = self._reports.get(report_id)
        if not report:
            return {"accuracy": 0, "avg_deviation": 0, "count": 0}

        return asyncio.get_event_loop().run_until_complete(
            self.prediction_tracker.calculate_model_accuracy(report.deviations)
        )


# ============================================================================
# 工厂函数
# ============================================================================

_manager: Optional[LivingReportManager] = None


def get_living_report_manager() -> LivingReportManager:
    """获取活报告管理器单例"""
    global _manager
    if _manager is None:
        _manager = LivingReportManager()
    return _manager


async def create_living_report_async(
    report_id: str,
    project_name: str,
    baseline_data: dict,
    project_lat: float = None,
    project_lon: float = None
) -> LivingReport:
    """异步创建活报告"""
    manager = get_living_report_manager()
    return await manager.create_living_report(
        report_id, project_name, baseline_data, project_lat, project_lon
    )


async def activate_living_report_async(report_id: str) -> LivingReport:
    """异步激活活报告"""
    manager = get_living_report_manager()
    return await manager.activate_report(report_id)
