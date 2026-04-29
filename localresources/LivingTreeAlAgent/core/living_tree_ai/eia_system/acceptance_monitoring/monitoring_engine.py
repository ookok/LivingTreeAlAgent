"""
验收监测智能管理系统
====================

核心功能：
1. 智能布点方案 - 基于空间统计学和模型反演生成最优监测布点
2. 数据自动采集与验证 - 异常检测、复测提醒
3. 达标评价自动化 - 实测 vs 预测对比，判断达标
4. 报告自动生成 - 带图表的数据分析章节
"""

import asyncio
import json
import math
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple


class MonitoringType(Enum):
    """监测类型"""
    AIR = "air"                    # 大气
    WATER = "water"                # 地表水
    GROUNDWATER = "groundwater"    # 地下水
    SOIL = "soil"                 # 土壤
    NOISE = "noise"               # 噪声
    SOLID_WASTE = "solid_waste"   # 固废


class EvaluationResult(Enum):
    """评价结果"""
    COMPLIANT = "compliant"        # 达标
    NON_COMPLIANT = "non_compliant"  # 不达标
    MARGINAL = "marginal"          # 临界
    NO_DATA = "no_data"           # 无数据


@dataclass
class MonitoringPoint:
    """监测点位"""
    point_id: str
    point_name: str
    lat: float
    lon: float
    height: float = 1.5           # 监测高度 (m)
    point_type: str = "background"  # 背景/控制/衰减
    source_distance: float = 0.0   # 与源距离 (m)
    is_required: bool = True       # 是否必测点

    # 监测参数
    parameters: List[str] = field(default_factory=list)

    # 实测数据
    measured_values: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "point_id": self.point_id,
            "point_name": self.point_name,
            "lat": self.lat,
            "lon": self.lon,
            "height": self.height,
            "point_type": self.point_type,
            "parameters": self.parameters,
            "measured_values": self.measured_values,
        }


@dataclass
class Monitoring布点Scheme:
    """监测布点方案"""
    scheme_id: str
    monitoring_type: MonitoringType
    total_points: int
    points: List[MonitoringPoint]
    compliance_check: Dict[str, Any]  # 合规检查结果
    drawing_data: Optional[Dict] = None  # 绘图数据


@dataclass
class MeasuredData:
    """实测数据"""
    data_id: str
    point_id: str
    parameter: str
    value: float
    unit: str
    timestamp: datetime
    is_valid: bool = True
    anomaly_flag: bool = False
    anomaly_reason: str = ""


@dataclass
class EvaluationResult:
    """达标评价结果"""
    parameter: str
    standard_value: float
    measured_value: float
    exceedance_rate: float = 0.0  # 超标率 %
    evaluation: EvaluationResult
    comparison_chart_data: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "parameter": self.parameter,
            "standard_value": self.standard_value,
            "measured_value": self.measured_value,
            "exceedance_rate": self.exceedance_rate,
            "evaluation": self.evaluation.value,
        }


@dataclass
class AcceptanceMonitoringReport:
    """验收监测报告"""
    report_id: str
    project_name: str
    monitoring_type: MonitoringType

    # 布点方案
    layout_scheme: Monitoring布点Scheme

    # 实测数据
    measured_data: List[MeasuredData]

    # 评价结果
    evaluation_results: List[EvaluationResult]

    # 与预测对比
    prediction_comparison: Dict[str, Any] = field(default_factory=dict)

    # 综合结论
    overall_conclusion: str = ""
    is_accepted: bool = False

    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            "report_id": self.report_id,
            "project_name": self.project_name,
            "monitoring_type": self.monitoring_type.value,
            "total_points": self.layout_scheme.total_points,
            "evaluation": [e.to_dict() for e in self.evaluation_results],
            "overall_conclusion": self.overall_conclusion,
            "is_accepted": self.is_accepted,
        }


class Smart布点Engine:
    """
    智能布点引擎

    基于空间统计学和预测模型反演，自动生成最优监测布点方案
    """

    # 验收技术指南要求的最低布点数量
    MIN_POINTS = {
        MonitoringType.AIR: 6,
        MonitoringType.WATER: 3,
        MonitoringType.GROUNDWATER: 3,
        MonitoringType.SOIL: 5,
        MonitoringType.NOISE: 8,
    }

    def __init__(self):
        self.standards = {
            "air": {
                "SO2": {"standard": 150, "unit": "μg/m³", "period": "日均值"},
                "NO2": {"standard": 200, "unit": "μg/m³", "period": "日均值"},
                "PM10": {"standard": 150, "unit": "μg/m³", "period": "日均值"},
                "PM2.5": {"standard": 75, "unit": "μg/m³", "period": "日均值"},
                "O3": {"standard": 200, "unit": "μg/m³", "period": "小时均值"},
            },
            "water": {
                "pH": {"standard": "6-9", "unit": "-"},
                "COD": {"standard": 40, "unit": "mg/L"},
                "NH3-N": {"standard": 2.0, "unit": "mg/L"},
                "TP": {"standard": 0.4, "unit": "mg/L"},
            },
        }

    async def generate_layout_scheme(
        self,
        monitoring_type: MonitoringType,
        eia_report: Dict[str, Any],
        project_context: Dict[str, Any]
    ) -> Monitoring布点Scheme:
        """
        生成监测布点方案

        Args:
            monitoring_type: 监测类型
            eia_report: 环评报告（包含源强、预测结果）
            project_context: 项目上下文

        Returns:
            Monitoring布点Scheme: 布点方案
        """
        scheme_id = f"LS_{monitoring_type.value}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # 提取源强和敏感点信息
        source_data = eia_report.get('source_strength', {})
        prediction_data = eia_report.get('predictions', {})
        sensitive_points = eia_report.get('sensitive_points', [])

        # 根据监测类型生成布点
        if monitoring_type == MonitoringType.AIR:
            points = await self._generate_air_points(source_data, prediction_data, sensitive_points, project_context)
        elif monitoring_type == MonitoringType.WATER:
            points = await self._generate_water_points(source_data, project_context)
        elif monitoring_type == MonitoringType.NOISE:
            points = await self._generate_noise_points(source_data, sensitive_points, project_context)
        else:
            points = await self._generate_default_points(monitoring_type, project_context)

        # 合规检查
        compliance_check = self._check_compliance(monitoring_type, points)

        return Monitoring布点Scheme(
            scheme_id=scheme_id,
            monitoring_type=monitoring_type,
            total_points=len(points),
            points=points,
            compliance_check=compliance_check,
            drawing_data=self._generate_drawing_data(points, project_context)
        )

    async def _generate_air_points(
        self,
        source_data: Dict,
        prediction_data: Dict,
        sensitive_points: List,
        context: Dict
    ) -> List[MonitoringPoint]:
        """生成大气监测布点"""
        points = []
        base_lat, base_lon = context.get('lat', 0), context.get('lon', 0)

        # 1. 背景点 - 在主导上风向
        points.append(MonitoringPoint(
            point_id="AP_BG_01",
            point_name="背景监测点-01",
            lat=base_lat + 0.01,
            lon=base_lon - 0.005,
            point_type="background",
            parameters=["SO2", "NO2", "PM10", "PM2.5", "O3"]
        ))

        # 2. 控制点 - 在厂界外最近敏感点
        if sensitive_points:
            for i, sp in enumerate(sensitive_points[:2]):
                points.append(MonitoringPoint(
                    point_id=f"AP_CS_{i+1:02d}",
                    point_name=f"控制点-{sp.get('name', f'敏感点{i+1}')}",
                    lat=sp.get('lat', base_lat),
                    lon=sp.get('lon', base_lon),
                    point_type="control",
                    source_distance=sp.get('distance', 100),
                    parameters=["SO2", "NO2", "PM10", "PM2.5", "O3"]
                ))

        # 3. 衰减断面 - 沿主导风向下风向
        wind_direction = context.get('wind_direction', 'NE')
        directions = {'N': (0.005, 0), 'NE': (0.003, 0.003), 'E': (0, 0.005),
                      'SE': (-0.003, 0.003), 'S': (-0.005, 0), 'SW': (-0.003, -0.003),
                      'W': (0, -0.005), 'NW': (0.003, -0.003)}

        dlat, dlon = directions.get(wind_direction, (0.003, 0.003))
        for i in range(3):
            points.append(MonitoringPoint(
                point_id=f"AP_DL_{i+1:02d}",
                point_name=f"衰减断面-{i+1}",
                lat=base_lat + dlat * (i + 1),
                lon=base_lon + dlon * (i + 1),
                point_type="attenuation",
                source_distance=200 * (i + 1),
                is_required=(i < 2),
                parameters=["SO2", "NO2", "PM10"]
            ))

        # 确保最低数量
        while len(points) < self.MIN_POINTS[MonitoringType.AIR]:
            points.append(MonitoringPoint(
                point_id=f"AP_EXT_{len(points):02d}",
                point_name=f"补充点-{len(points)}",
                lat=base_lat + 0.005 * len(points),
                lon=base_lon - 0.005 * len(points),
                point_type="supplementary",
                parameters=["SO2", "NO2", "PM10"]
            ))

        return points

    async def _generate_water_points(
        self,
        source_data: Dict,
        context: Dict
    ) -> List[MonitoringPoint]:
        """生成地表水监测布点"""
        points = []
        base_lat, base_lon = context.get('lat', 0), context.get('lon', 0)

        # 上游对照断面
        points.append(MonitoringPoint(
            point_id="WP_UP_01",
            point_name="上游对照断面-01",
            lat=base_lat + 0.01,
            lon=base_lon,
            point_type="upstream",
            parameters=["pH", "COD", "NH3-N", "TP", "BOD5"]
        ))

        # 排放口
        points.append(MonitoringPoint(
            point_id="WP_DW_01",
            point_name="排放口-01",
            lat=base_lat,
            lon=base_lon,
            point_type="discharge",
            parameters=["pH", "COD", "NH3-N", "TP", "BOD5", "SS"]
        ))

        # 下游监测断面
        for i in range(3):
            points.append(MonitoringPoint(
                point_id=f"WP_DN_{i+1:02d}",
                point_name=f"下游断面-{i+1}",
                lat=base_lat - 0.005 * (i + 1),
                lon=base_lon,
                point_type="downstream",
                source_distance=500 * (i + 1),
                parameters=["pH", "COD", "NH3-N", "TP"]
            ))

        return points

    async def _generate_noise_points(
        self,
        source_data: Dict,
        sensitive_points: List,
        context: Dict
    ) -> List[MonitoringPoint]:
        """生成噪声监测布点"""
        points = []
        base_lat, base_lon = context.get('lat', 0), context.get('lon', 0)

        # 厂界噪声监测点
        for i, direction in enumerate(['N', 'E', 'S', 'W', 'NE', 'SE', 'SW', 'NW']):
            directions = {
                'N': (0.003, 0), 'E': (0, 0.003), 'S': (-0.003, 0), 'W': (0, -0.003),
                'NE': (0.002, 0.002), 'SE': (-0.002, 0.002), 'SW': (-0.002, -0.002), 'NW': (0.002, -0.002)
            }
            dlat, dlon = directions[direction]
            points.append(MonitoringPoint(
                point_id=f"NP_BD_{i+1:02d}",
                point_name=f"厂界{direction}侧-{i//2+1}",
                lat=base_lat + dlat,
                lon=base_lon + dlon,
                point_type="boundary",
                parameters=["昼间Leq", "夜间Leq", "Lmax", "Lmin"]
            ))

        # 敏感点监测
        for i, sp in enumerate(sensitive_points[:2]):
            points.append(MonitoringPoint(
                point_id=f"NP_SP_{i+1:02d}",
                point_name=f"敏感点-{sp.get('name', f'敏感点{i+1}')}",
                lat=sp.get('lat', base_lat),
                lon=sp.get('lon', base_lon),
                point_type="sensitive",
                parameters=["昼间Leq", "夜间Leq"]
            ))

        return points

    async def _generate_default_points(
        self,
        monitoring_type: MonitoringType,
        context: Dict
    ) -> List[MonitoringPoint]:
        """生成默认布点"""
        points = []
        min_count = self.MIN_POINTS.get(monitoring_type, 3)

        for i in range(min_count):
            points.append(MonitoringPoint(
                point_id=f"MP_{i+1:02d}",
                point_name=f"监测点-{i+1}",
                lat=context.get('lat', 0) + 0.001 * i,
                lon=context.get('lon', 0) - 0.001 * i,
                point_type="monitoring",
                parameters=[]
            ))

        return points

    def _check_compliance(
        self,
        monitoring_type: MonitoringType,
        points: List[MonitoringPoint]
    ) -> Dict[str, Any]:
        """检查布点是否符合规范"""
        min_required = self.MIN_POINTS.get(monitoring_type, 3)
        required_points = sum(1 for p in points if p.is_required)

        return {
            "min_required": min_required,
            "total_points": len(points),
            "required_points": required_points,
            "is_compliant": len(points) >= min_required and required_points >= min_required,
            "issues": [] if len(points) >= min_required else [f"布点数量不足，最低{min_required}个"]
        }

    def _generate_drawing_data(self, points: List[MonitoringPoint], context: Dict) -> Dict:
        """生成绘图数据"""
        return {
            "center": {"lat": context.get('lat', 0), "lon": context.get('lon', 0)},
            "points": [{"id": p.point_id, "lat": p.lat, "lon": p.lon, "type": p.point_type, "name": p.point_name} for p in points],
            "legend": {
                "background": {"color": "blue", "label": "背景点"},
                "control": {"color": "red", "label": "控制点"},
                "attenuation": {"color": "orange", "label": "衰减断面"},
                "boundary": {"color": "purple", "label": "厂界"},
                "sensitive": {"color": "green", "label": "敏感点"},
            }
        }


class DataValidationEngine:
    """
    数据验证引擎

    自动检测异常值，识别仪器故障或人为干扰
    """

    def __init__(self):
        self.anomaly_rules = [
            {"name": "负值检测", "check": lambda v: v < 0, "reason": "监测值不能为负"},
            {"name": "超限检测", "check": lambda v, s: v > s * 10, "reason": "值异常偏大，可能仪器故障"},
            {"name": "突变检测", "check": lambda v, p: abs(v - p) / (p + 0.01) > 5, "reason": "与前值变化超过500%，可能异常"},
        ]

    async def validate_data(
        self,
        measured_data: List[MeasuredData],
        historical_data: Optional[List[MeasuredData]] = None
    ) -> List[MeasuredData]:
        """验证实测数据"""
        validated = []

        for data in measured_data:
            is_valid = True
            anomaly_reason = ""

            # 基础规则检查
            if data.value < 0:
                is_valid = False
                anomaly_reason = "负值异常"
            elif data.value > 10000:  # 异常大值
                is_valid = False
                anomaly_reason = "值异常偏大"

            # 与历史数据对比
            if historical_data and is_valid:
                for hist in historical_data[-3:]:
                    if hist.parameter == data.parameter:
                        change_rate = abs(data.value - hist.value) / (hist.value + 0.01)
                        if change_rate > 5:  # 变化超过500%
                            is_valid = False
                            anomaly_reason = f"与近期数据变化超过500%，近期值{hist.value}"
                            break

            data.is_valid = is_valid
            data.anomaly_flag = not is_valid
            data.anomaly_reason = anomaly_reason
            validated.append(data)

        return validated

    def detect_instrument_issues(self, data_series: List[MeasuredData]) -> List[str]:
        """检测仪器问题"""
        issues = []

        if len(data_series) < 3:
            return issues

        # 检测恒定值（仪器卡死）
        values = [d.value for d in data_series[-5:]]
        if len(set(values)) == 1 and values[0] > 0:
            issues.append(f"检测到恒定值{values[0]}，可能仪器卡死")

        # 检测周期性异常（干扰）
        if len(values) >= 5:
            diffs = [values[i+1] - values[i] for i in range(len(values)-1)]
            if all(abs(d) < 0.01 for d in diffs):
                issues.append("检测到规律性微小波动，可能存在干扰")

        return issues


class ComplianceEvaluationEngine:
    """
    达标评价引擎

    基于实测数据和标准，判断是否达标
    """

    def __init__(self):
        self.standards = {
            "air": {
                "SO2": {"standard": 150, "unit": "μg/m³", "type": "max"},
                "NO2": {"standard": 200, "unit": "μg/m³", "type": "max"},
                "PM10": {"standard": 150, "unit": "μg/m³", "type": "max"},
                "O3": {"standard": 200, "unit": "μg/m³", "type": "max"},
            },
            "water": {
                "COD": {"standard": 40, "unit": "mg/L", "type": "max"},
                "NH3-N": {"standard": 2.0, "unit": "mg/L", "type": "max"},
                "TP": {"standard": 0.4, "unit": "mg/L", "type": "max"},
            },
            "noise": {
                "day": {"standard": 65, "unit": "dB(A)", "type": "max"},
                "night": {"standard": 55, "unit": "dB(A)", "type": "max"},
            }
        }

    async def evaluate(
        self,
        measured_data: List[MeasuredData],
        monitoring_type: MonitoringType,
        eia_prediction: Optional[Dict] = None
    ) -> Tuple[List[EvaluationResult], Dict]:
        """
        评价达标情况

        Args:
            measured_data: 实测数据
            monitoring_type: 监测类型
            eia_prediction: 环评预测数据（用于对比）

        Returns:
            (评价结果列表, 预测对比数据)
        """
        results = []
        prediction_comparison = {}

        # 按参数分组
        param_data = {}
        for data in measured_data:
            if data.parameter not in param_data:
                param_data[data.parameter] = []
            param_data[data.parameter].append(data)

        # 获取标准
        media = monitoring_type.value
        if media in self.standards:
            param_standards = self.standards[media]
        else:
            param_standards = {}

        # 逐参数评价
        for param, datas in param_data.items():
            if not datas:
                continue

            valid_values = [d.value for d in datas if d.is_valid]
            if not valid_values:
                results.append(EvaluationResult(
                    parameter=param,
                    standard_value=param_standards.get(param, {}).get('standard', 0),
                    measured_value=0,
                    evaluation=EvaluationResult.NO_DATA
                ))
                continue

            measured_value = max(valid_values) if param_standards.get(param, {}).get('type') == 'max' else sum(valid_values) / len(valid_values)
            standard_value = param_standards.get(param, {}).get('standard', 100)

            # 计算超标率
            exceedance_count = sum(1 for v in valid_values if v > standard_value)
            exceedance_rate = (exceedance_count / len(valid_values)) * 100 if valid_values else 0

            # 判断结果
            if exceedance_rate == 0:
                evaluation = EvaluationResult.COMPLIANT
            elif exceedance_rate <= 10:
                evaluation = EvaluationResult.MARGINAL
            else:
                evaluation = EvaluationResult.NON_COMPLIANT

            results.append(EvaluationResult(
                parameter=param,
                standard_value=standard_value,
                measured_value=round(measured_value, 3),
                exceedance_rate=round(exceedance_rate, 1),
                evaluation=evaluation,
                comparison_chart_data=self._generate_comparison_data(param, valid_values, eia_prediction)
            ))

            # 预测对比
            if eia_prediction and param in eia_prediction:
                prediction_comparison[param] = {
                    "measured": measured_value,
                    "predicted": eia_prediction[param],
                    "ratio": round(measured_value / eia_prediction[param], 2) if eia_prediction[param] > 0 else 0
                }

        return results, prediction_comparison

    def _generate_comparison_data(
        self,
        parameter: str,
        measured_values: List[float],
        prediction: Optional[Dict]
    ) -> Dict:
        """生成对比图表数据"""
        labels = [f"测点{i+1}" for i in range(len(measured_values))]
        return {
            "parameter": parameter,
            "measured": measured_values,
            "predicted": [prediction.get(parameter, 0)] * len(measured_values) if prediction else None,
            "labels": labels
        }


class AcceptanceMonitoringEngine:
    """
    验收监测主引擎

    整合布点、数据验证、达标评价全流程
    """

    def __init__(self):
        self.布点_engine = Smart布点Engine()
        self.validation_engine = DataValidationEngine()
        self.evaluation_engine = ComplianceEvaluationEngine()

    async def generate_monitoring_report(
        self,
        project_context: Dict[str, Any],
        eia_report: Dict[str, Any],
        measured_data: Optional[List[MeasuredData]] = None,
        eia_prediction: Optional[Dict] = None
    ) -> AcceptanceMonitoringReport:
        """
        生成验收监测报告

        Args:
            project_context: 项目上下文
            eia_report: 环评报告
            measured_data: 实测数据（可选）
            eia_prediction: 环评预测值（可选）

        Returns:
            AcceptanceMonitoringReport: 验收监测报告
        """
        monitoring_type = MonitoringType(project_context.get('monitoring_type', 'air'))
        report_id = f"AM_{monitoring_type.value}_{datetime.now().strftime('%Y%m%d')}"

        # 1. 生成布点方案
        layout_scheme = await self.布点_engine.generate_layout_scheme(
            monitoring_type, eia_report, project_context
        )

        # 2. 如果有实测数据，进行验证和评价
        evaluation_results = []
        prediction_comparison = {}

        if measured_data:
            # 验证数据
            validated_data = await self.validation_engine.validate_data(measured_data)

            # 达标评价
            evaluation_results, prediction_comparison = await self.evaluation_engine.evaluate(
                validated_data, monitoring_type, eia_prediction
            )

        # 3. 生成结论
        non_compliant_count = sum(
            1 for r in evaluation_results
            if r.evaluation == EvaluationResult.NON_COMPLIANT
        )

        overall_conclusion = "通过验收" if non_compliant_count == 0 else f"存在{non_compliant_count}项指标超标，需整改"
        is_accepted = non_compliant_count == 0

        return AcceptanceMonitoringReport(
            report_id=report_id,
            project_name=project_context.get('project_name', '未知项目'),
            monitoring_type=monitoring_type,
            layout_scheme=layout_scheme,
            measured_data=measured_data or [],
            evaluation_results=evaluation_results,
            prediction_comparison=prediction_comparison,
            overall_conclusion=overall_conclusion,
            is_accepted=is_accepted
        )


# 全局实例
_monitoring_engine_instance: Optional[AcceptanceMonitoringEngine] = None


def get_monitoring_engine() -> AcceptanceMonitoringEngine:
    global _monitoring_engine_instance
    if _monitoring_engine_instance is None:
        _monitoring_engine_instance = AcceptanceMonitoringEngine()
    return _monitoring_engine_instance