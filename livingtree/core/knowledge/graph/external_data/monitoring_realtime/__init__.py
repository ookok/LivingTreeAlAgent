"""
实时监管库集成模块
==================

集成全国污染源监测信息平台、地方数据开放平台等实时监管数据。

功能：
1. 实时监测数据查询 - 企业排污口小时级数据
2. 异常检测 - 实测数据与理论系数偏差分析
3. 预警通知 - 超标报警推送
4. 数据验证 - 同类项目"三本账"核算参照

Author: Hermes Desktop Team
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import threading
import statistics

logger = logging.getLogger(__name__)


class MonitoringType(Enum):
    """监测类型"""
    AUTOMATIC = "automatic"           # 自动监测
    MANUAL = "manual"               # 手工监测
    VIRTUAL = "virtual"             # 虚拟监测（理论计算）


class OutletType(Enum):
    """排放口类型"""
    EXHAUST_GAS = "exhaust_gas"     # 废气排放口
    WASTE_WATER = "waste_water"     # 废水排放口
    SOLID_WASTE = "solid_waste"     # 固废
    NOISE = "noise"                 # 噪声


class AlertLevel(Enum):
    """预警级别"""
    NORMAL = "normal"               # 正常
    WARNING = "warning"             # 预警
    EXCEED = "exceed"              # 超标
    SERIOUS = "serious"            # 严重超标


@dataclass
class MonitoringPoint:
    """监测点位"""
    point_id: str
    company_name: str
    company_id: str
    outlet_code: str               # 排放口编号
    outlet_name: str               # 排放口名称
    outlet_type: OutletType
    latitude: float = 0.0
    longitude: float = 0.0
    region: str = ""               # 区域
    monitoring_items: List[str] = field(default_factory=list)  # 监测因子


@dataclass
class MonitoringRecord:
    """监测记录"""
    record_id: str
    point_id: str
    outlet_code: str
    pollutant: str
    value: float
    unit: str
    standard_value: float          # 标准限值
    standard_level: str = ""       # 标准级别
    exceed_ratio: float = 0.0      # 超标倍数
    monitor_time: datetime
    monitoring_type: MonitoringType
    data_source: str = ""
    is_valid: bool = True
    remarks: str = ""


@dataclass
class AlertRecord:
    """预警记录"""
    alert_id: str
    point_id: str
    company_name: str
    outlet_code: str
    pollutant: str
    alert_time: datetime
    alert_level: AlertLevel
    current_value: float
    standard_value: float
    exceed_ratio: float
    duration_minutes: int = 0       # 持续时长（分钟）
    is_handled: bool = False
    handled_time: datetime = None
    handled_by: str = ""
    remarks: str = ""


@dataclass
class AnomalyDetection:
    """异常检测结果"""
    detection_id: str
    point_id: str
    pollutant: str
    detected_time: datetime
    anomaly_type: str              # 异常类型（突增、突减、持续偏高、持续偏低）
    theoretical_value: float        # 理论值（基于排放系数）
    actual_value: float            # 实测值
    deviation_ratio: float         # 偏差率
    confidence: float             # 置信度
    possible_causes: List[str] = field(default_factory=list)
    recommendation: str = ""


class RealtimeMonitoringCenter:
    """
    实时监测数据中心

    管理实时监测数据，提供查询、预警、异常检测功能。
    """

    def __init__(self, external_hub=None, emission_registry=None):
        self.external_hub = external_hub
        self.emission_registry = emission_registry
        self._monitoring_points: Dict[str, MonitoringPoint] = {}
        self._monitoring_records: Dict[str, List[MonitoringRecord]] = {}
        self._alert_records: List[AlertRecord] = []
        self._anomaly_cache: Dict[str, AnomalyDetection] = {}
        self._lock = threading.RLock()

        # 预警阈值配置
        self._alert_thresholds = {
            "warning_ratio": 0.8,    # 预警阈值（达到标准的80%）
            "exceed_ratio": 1.0,     # 超标阈值（达到或超过标准）
            "serious_ratio": 1.5     # 严重超标阈值（超过标准1.5倍）
        }

        # 初始化内置监测点位
        self._init_builtin_points()

    def _init_builtin_points(self):
        """初始化内置监测点位"""
        points = [
            MonitoringPoint(
                point_id="MP_NJHG_001",
                company_name="南京化工有限公司",
                company_id="NJHG",
                outlet_code="D001",
                outlet_name="工艺废气排放口1",
                outlet_type=OutletType.EXHAUST_GAS,
                latitude=32.0603,
                longitude=118.7969,
                region="江苏南京",
                monitoring_items=["SO2", "NOx", "VOCs", "颗粒物"]
            ),
            MonitoringPoint(
                point_id="MP_SZPR_001",
                company_name="苏州印染厂",
                company_id="SZPR",
                outlet_code="W001",
                outlet_name="废水排放口1",
                outlet_type=OutletType.WASTE_WATER,
                latitude=31.2989,
                longitude=120.5853,
                region="江苏苏州",
                monitoring_items=["COD", "NH3-N", "TP", "色度"]
            ),
            MonitoringPoint(
                point_id="MP_WXDD_001",
                company_name="无锡电镀中心",
                company_id="WXDD",
                outlet_code="W002",
                outlet_name="电镀废水排放口",
                outlet_type=OutletType.WASTE_WATER,
                latitude=31.4912,
                longitude=120.3119,
                region="江苏无锡",
                monitoring_items=["总铬", "总镍", "COD", "pH"]
            ),
        ]

        for point in points:
            self._monitoring_points[point.point_id] = point

        logger.info(f"内置监测点位初始化完成: {len(points)} 个")

    def register_point(self, point: MonitoringPoint):
        """注册监测点位"""
        with self._lock:
            self._monitoring_points[point.point_id] = point
            logger.info(f"注册监测点位: {point.point_id} - {point.outlet_name}")

    def get_point(self, point_id: str) -> Optional[MonitoringPoint]:
        """获取监测点位"""
        return self._monitoring_points.get(point_id)

    def query_realtime_data(self,
                           company_name: str = None,
                           region: str = None,
                           outlet_type: OutletType = None,
                           time_range: Tuple[datetime, datetime] = None) -> List[MonitoringRecord]:
        """
        查询实时监测数据

        Args:
            company_name: 企业名称
            region: 区域
            outlet_type: 排放口类型
            time_range: 时间范围

        Returns:
            监测记录列表
        """
        # 从外部数据源获取
        if self.external_hub:
            ext_data = self.external_hub.query_realtime_monitoring(
                company_name=company_name,
                region=region
            )

            records = []
            for item in ext_data:
                point_id = f"ext_{item.get('company', '')}_{item.get('outlet', '')}"
                record = MonitoringRecord(
                    record_id=f"ext_record_{len(records)}",
                    point_id=point_id,
                    outlet_code=item.get("outlet", ""),
                    pollutant=item.get("pollutant", ""),
                    value=float(item.get("value", 0)),
                    unit=item.get("unit", ""),
                    standard_value=float(item.get("standard", 100)),
                    monitor_time=datetime.fromisoformat(item.get("timestamp", datetime.now().isoformat())),
                    monitoring_type=MonitoringType.AUTOMATIC,
                    data_source=self.external_hub.sources.get("monitoring_platform", {}).name if hasattr(self.external_hub, 'sources') else "monitoring"
                )
                records.append(record)

            return records

        # 使用内置模拟数据
        return self._get_builtin_records(company_name, region, outlet_type)

    def _get_builtin_records(self,
                            company_name: str = None,
                            region: str = None,
                            outlet_type: OutletType = None) -> List[MonitoringRecord]:
        """获取内置监测记录"""
        records = [
            MonitoringRecord(
                record_id="rec_001",
                point_id="MP_NJHG_001",
                outlet_code="D001",
                pollutant="SO2",
                value=45.2,
                unit="mg/m³",
                standard_value=100,
                standard_level="GB 16297-1996",
                exceed_ratio=0.452,
                monitor_time=datetime.now(),
                monitoring_type=MonitoringType.AUTOMATIC,
                data_source="全国污染源监测信息平台"
            ),
            MonitoringRecord(
                record_id="rec_002",
                point_id="MP_SZPR_001",
                outlet_code="W001",
                pollutant="COD",
                value=85.5,
                unit="mg/L",
                standard_value=100,
                standard_level="GB 8978-1996",
                exceed_ratio=0.855,
                monitor_time=datetime.now(),
                monitoring_type=MonitoringType.AUTOMATIC,
                data_source="全国污染源监测信息平台"
            ),
            MonitoringRecord(
                record_id="rec_003",
                point_id="MP_WXDD_001",
                outlet_code="W002",
                pollutant="总铬",
                value=0.35,
                unit="mg/L",
                standard_value=1.5,
                standard_level="GB 21900-2008",
                exceed_ratio=0.233,
                monitor_time=datetime.now(),
                monitoring_type=MonitoringType.AUTOMATIC,
                data_source="全国污染源监测信息平台"
            ),
        ]

        # 过滤
        if company_name:
            records = [r for r in records
                      if company_name in self._monitoring_points.get(r.point_id, MonitoringPoint("", "", "", "", "", OutletType.EXHAUST_GAS)).company_name]

        if region:
            records = [r for r in records
                      if region in self._monitoring_points.get(r.point_id, MonitoringPoint("", "", "", "", "", OutletType.EXHAUST_GAS)).region]

        return records

    def check_alerts(self, records: List[MonitoringRecord] = None) -> List[AlertRecord]:
        """
        检查预警

        Args:
            records: 监测记录（None表示查询最新）

        Returns:
            预警记录列表
        """
        if records is None:
            records = self.query_realtime_data()

        alerts = []
        for record in records:
            ratio = record.value / record.standard_value if record.standard_value > 0 else 0

            if ratio >= self._alert_thresholds["serious_ratio"]:
                level = AlertLevel.SERIOUS
            elif ratio >= self._alert_thresholds["exceed_ratio"]:
                level = AlertLevel.EXCEED
            elif ratio >= self._alert_thresholds["warning_ratio"]:
                level = AlertLevel.WARNING
            else:
                level = AlertLevel.NORMAL

            if level != AlertLevel.NORMAL:
                point = self._monitoring_points.get(record.point_id)
                alert = AlertRecord(
                    alert_id=f"alert_{record.record_id}_{int(datetime.now().timestamp())}",
                    point_id=record.point_id,
                    company_name=point.company_name if point else "",
                    outlet_code=record.outlet_code,
                    pollutant=record.pollutant,
                    alert_time=record.monitor_time,
                    alert_level=level,
                    current_value=record.value,
                    standard_value=record.standard_value,
                    exceed_ratio=ratio
                )
                alerts.append(alert)
                self._alert_records.append(alert)

        return alerts

    def detect_anomaly(self,
                      point_id: str,
                      pollutant: str,
                      time_range: Tuple[datetime, datetime] = None) -> Optional[AnomalyDetection]:
        """
        异常检测：对比实测值与理论值

        Args:
            point_id: 监测点位ID
            pollutant: 污染物
            time_range: 时间范围

        Returns:
            异常检测结果
        """
        if time_range is None:
            time_range = (datetime.now() - timedelta(hours=24), datetime.now())

        # 获取实测数据
        records = self.query_realtime_data()
        records = [r for r in records
                  if r.point_id == point_id and r.pollutant == pollutant
                  and time_range[0] <= r.monitor_time <= time_range[1]]

        if not records:
            return None

        # 计算平均值
        avg_value = statistics.mean([r.value for r in records])

        # 获取理论值（基于排放系数）
        point = self._monitoring_points.get(point_id)
        theoretical_value = 0.0

        if point and self.emission_registry:
            # 根据企业类型和污染物查找理论排放系数
            factors = self.emission_registry.find_factors(pollutant=pollutant)
            if factors:
                theoretical_value = factors[0].value * 24 * 365  # 年化估算

        # 计算偏差
        if theoretical_value > 0:
            deviation_ratio = (avg_value - theoretical_value) / theoretical_value
        else:
            deviation_ratio = 0.0

        # 判断异常类型
        if abs(deviation_ratio) < 0.2:
            anomaly_type = "normal"
        elif deviation_ratio > 0.5:
            anomaly_type = "突增"
        elif deviation_ratio < -0.5:
            anomaly_type = "突减"
        elif avg_value > theoretical_value:
            anomaly_type = "持续偏高"
        else:
            anomaly_type = "持续偏低"

        detection = AnomalyDetection(
            detection_id=f"anomaly_{point_id}_{pollutant}_{int(datetime.now().timestamp())}",
            point_id=point_id,
            pollutant=pollutant,
            detected_time=datetime.now(),
            anomaly_type=anomaly_type,
            theoretical_value=theoretical_value,
            actual_value=avg_value,
            deviation_ratio=deviation_ratio,
            confidence=0.85,
            possible_causes=self._get_possible_causes(anomaly_type),
            recommendation=self._get_recommendation(anomaly_type)
        )

        self._anomaly_cache[detection.detection_id] = detection
        return detection

    def _get_possible_causes(self, anomaly_type: str) -> List[str]:
        """获取可能原因"""
        causes_db = {
            "突增": ["设备故障导致处理效率下降", "原料/工艺变化", "监测设备异常"],
            "突减": ["生产负荷降低", "治理设施效率提升", "监测设备故障"],
            "持续偏高": ["治理设施老化", "设计能力不足", "操作管理问题"],
            "持续偏低": ["生产工况异常", "排放口合并", "监测点位迁移"]
        }
        return causes_db.get(anomaly_type, ["其他原因"])

    def _get_recommendation(self, anomaly_type: str) -> str:
        """获取处理建议"""
        rec_db = {
            "突增": "建议立即检查治理设施运行状态，排除设备故障",
            "突减": "核实生产情况，确认是否为正常工况变化",
            "持续偏高": "建议进行设施升级改造或优化运行参数",
            "持续偏低": "核实数据准确性，检查监测设备校准情况"
        }
        return rec_db.get(anomaly_type, "持续关注数据变化趋势")

    def generate_verification_report(self,
                                    project_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成数据验证报告（"三本账"核算参照）

        Args:
            project_info: 项目信息

        Returns:
            验证报告
        """
        industry = project_info.get("industry", "")
        region = project_info.get("region", "")

        # 查询同类项目实际排放数据
        similar_data = self.query_realtime_data(region=region)

        # 计算行业平均水平
        pollutant_stats = {}
        for record in similar_data:
            pollutant = record.pollutant
            if pollutant not in pollutant_stats:
                pollutant_stats[pollutant] = []
            pollutant_stats[pollutant].append(record.value)

        stats_result = {}
        for pollutant, values in pollutant_stats.items():
            if values:
                stats_result[pollutant] = {
                    "avg": statistics.mean(values),
                    "max": max(values),
                    "min": min(values),
                    "std": statistics.stdev(values) if len(values) > 1 else 0
                }

        return {
            "title": "同类项目排放数据参照报告",
            "project": project_info,
            "data_source": "全国污染源监测信息平台",
            "region": region,
            "industry": industry,
            "statistics": stats_result,
            "sample_count": len(similar_data),
            "generated_at": datetime.now().isoformat()
        }

    def get_alert_summary(self) -> Dict[str, Any]:
        """获取预警汇总"""
        total = len(self._alert_records)
        unhandled = len([a for a in self._alert_records if not a.is_handled])

        level_counts = {}
        for alert in self._alert_records:
            level = alert.alert_level.value
            level_counts[level] = level_counts.get(level, 0) + 1

        return {
            "total_alerts": total,
            "unhandled_alerts": unhandled,
            "handled_alerts": total - unhandled,
            "level_distribution": level_counts,
            "recent_alerts": [
                {
                    "company": a.company_name,
                    "pollutant": a.pollutant,
                    "level": a.alert_level.value,
                    "time": a.alert_time.isoformat()
                }
                for a in self._alert_records[-5:]
            ]
        }

    def to_dict(self) -> Dict[str, Any]:
        """导出为字典"""
        return {
            "points_count": len(self._monitoring_points),
            "records_count": sum(len(r) for r in self._monitoring_records.values()),
            "alerts_count": len(self._alert_records),
            "unhandled_alerts": len([a for a in self._alert_records if not a.is_handled]),
            "alert_thresholds": self._alert_thresholds
        }


class MonitoringGraphIntegrator:
    """
    监测数据图谱融合器

    将实时监测数据与异常检测结果集成到知识图谱。
    """

    def __init__(self, knowledge_graph=None, monitoring_center: RealtimeMonitoringCenter = None):
        self.kg = knowledge_graph
        self.monitoring = monitoring_center or RealtimeMonitoringCenter()

    def integrate_monitoring_point(self, point: MonitoringPoint) -> bool:
        """
        将监测点位集成到图谱

        Args:
            point: 监测点位

        Returns:
            是否成功
        """
        if not self.kg:
            return False

        try:
            # 创建企业节点
            company_id = f"company_{point.company_id}"
            self.kg.add_entity(
                entity_id=company_id,
                entity_type="Company",
                properties={
                    "name": point.company_name,
                    "company_id": point.company_id,
                    "region": point.region
                }
            )

            # 创建监测点位节点
            self.kg.add_entity(
                entity_id=point.point_id,
                entity_type="MonitoringPoint",
                properties={
                    "outlet_code": point.outlet_code,
                    "outlet_name": point.outlet_name,
                    "outlet_type": point.outlet_type.value,
                    "latitude": point.latitude,
                    "longitude": point.longitude,
                    "region": point.region,
                    "monitoring_items": ",".join(point.monitoring_items)
                }
            )

            # 建立关系
            self.kg.add_relation(
                from_id=company_id,
                to_id=point.point_id,
                relation_type="hasMonitoringPoint",
                properties={"outlet_code": point.outlet_code}
            )

            return True

        except Exception as e:
            logger.error(f"监测点位融合失败: {e}")
            return False

    def integrate_alert(self, alert: AlertRecord) -> bool:
        """
        将预警记录集成到图谱

        Args:
            alert: 预警记录

        Returns:
            是否成功
        """
        if not self.kg:
            return False

        try:
            alert_node_id = f"alert_{alert.alert_id}"

            self.kg.add_entity(
                entity_id=alert_node_id,
                entity_type="AlertRecord",
                properties={
                    "company_name": alert.company_name,
                    "outlet_code": alert.outlet_code,
                    "pollutant": alert.pollutant,
                    "alert_time": alert.alert_time.isoformat(),
                    "alert_level": alert.alert_level.value,
                    "current_value": alert.current_value,
                    "standard_value": alert.standard_value,
                    "exceed_ratio": alert.exceed_ratio,
                    "is_handled": alert.is_handled
                }
            )

            self.kg.add_relation(
                from_id=alert.point_id,
                to_id=alert_node_id,
                relation_type="hasAlert",
                properties={
                    "level": alert.alert_level.value,
                    "time": alert.alert_time.isoformat()
                }
            )

            return True

        except Exception as e:
            logger.error(f"预警记录融合失败: {e}")
            return False

    def auto_integrate_region(self, region: str) -> int:
        """
        自动融合区域所有监测点位

        Args:
            region: 区域

        Returns:
            融合的点位数
        """
        count = 0
        for point in self.monitoring._monitoring_points.values():
            if region in point.region:
                if self.integrate_monitoring_point(point):
                    count += 1

        return count


# 全局单例
_monitoring_instance: Optional[RealtimeMonitoringCenter] = None
_monitoring_lock = threading.Lock()


def get_monitoring_center(external_hub=None, emission_registry=None) -> RealtimeMonitoringCenter:
    """获取实时监测中心单例"""
    global _monitoring_instance
    if _monitoring_instance is None:
        with _monitoring_lock:
            if _monitoring_instance is None:
                _monitoring_instance = RealtimeMonitoringCenter(external_hub, emission_registry)
    return _monitoring_instance


def get_monitoring_integrator(knowledge_graph=None) -> MonitoringGraphIntegrator:
    """获取监测数据图谱融合器"""
    return MonitoringGraphIntegrator(
        knowledge_graph=knowledge_graph,
        monitoring_center=get_monitoring_center()
    )
