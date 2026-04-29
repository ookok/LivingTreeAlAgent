"""
数字孪生验证器 - 审查即"数字孪生验证"
==========================================

核心思想：不只看文字，而是用模型和计算能力，实时复现报告中的每一项预测和数据。

功能：
1. 预测结果"一键复算" - 用相同模型重新计算，验证结果真实性
2. 敏感点距离"空间验证" - 用地图底图+项目坐标验证距离陈述
3. 数据链追溯 - 从结论追溯到原始输入参数
"""

import asyncio
import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from .spatial_intelligence import (
    POIPoint,
    SensitiveZone,
    SpatialIntelligenceEngine,
    get_spatial_engine,
)


class VerificationStatus(Enum):
    """验证状态"""
    PENDING = "pending"
    VERIFYING = "verifying"
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    CANNOT_VERIFY = "cannot_verify"  # 缺少必要数据


class DataSource(Enum):
    """数据来源"""
    REPORT_TEXT = "report_text"      # 报告中直接提取
    CALCULATED = "calculated"        # 计算得出
    EXTRACTED = "extracted"          # 从图表中提取
    UNKNOWN = "unknown"


@dataclass
class PredictionInput:
    """预测模型输入参数"""
    # 源强参数
    emission_rate: Optional[float] = None          # 排放速率 (g/s)
    emission_height: Optional[float] = None        # 排放高度 (m)
    emission_temperature: Optional[float] = None   # 排放温度 (K)
    emission_velocity: Optional[float] = None      # 排放速度 (m/s)
    emission_diameter: Optional[float] = None       # 排放口直径 (m)

    # 气象参数
    wind_speed: Optional[float] = None             # 风速 (m/s)
    wind_direction: Optional[float] = None         # 风向 (度)
    stability_class: Optional[str] = None          # 稳定度等级 (A-F)
    ambient_temperature: Optional[float] = None    # 环境温度 (K)
    mixing_height: Optional[float] = None           # 混合层高度 (m)

    # 地形参数
    terrain_height: Optional[float] = None         # 地形高度 (m)
    surface_roughness: Optional[float] = None      # 地面粗糙度 (m)

    # 位置参数
    source_lat: Optional[float] = None
    source_lon: Optional[float] = None
    receptor_lat: Optional[float] = None
    receptor_lon: Optional[float] = None

    data_source: DataSource = DataSource.UNKNOWN
    confidence: float = 0.0                         # 数据可信度 0-1
    raw_text: Optional[str] = None                  # 原始文本

    def to_dict(self) -> Dict:
        return {
            "emission_rate": self.emission_rate,
            "emission_height": self.emission_height,
            "emission_temperature": self.emission_temperature,
            "emission_velocity": self.emission_velocity,
            "emission_diameter": self.emission_diameter,
            "wind_speed": self.wind_speed,
            "wind_direction": self.wind_direction,
            "stability_class": self.stability_class,
            "ambient_temperature": self.ambient_temperature,
            "mixing_height": self.mixing_height,
            "terrain_height": self.terrain_height,
            "surface_roughness": self.surface_roughness,
            "source_lat": self.source_lat,
            "source_lon": self.source_lon,
            "receptor_lat": self.receptor_lat,
            "receptor_lon": self.receptor_lon,
            "data_source": self.data_source.value,
            "confidence": self.confidence,
        }


@dataclass
class PredictionResult:
    """预测结果"""
    compound: str                          # 污染物名称
    max_concentration: float               # 最大浓度 (mg/m³)
    distance: Optional[float] = None       # 落地距离 (m)
    direction: Optional[str] = None         # 方位 (如"下风向")
    prediction_model: str = "AERMOD"       # 预测模型
    calculation_status: VerificationStatus = VerificationStatus.PENDING
    original_value: Optional[float] = None # 报告原始值
    recalculated_value: Optional[float] = None  # 复算值
    relative_error: Optional[float] = None  # 相对误差 %
    verification_message: str = ""

    def to_dict(self) -> Dict:
        return {
            "compound": self.compound,
            "max_concentration": self.max_concentration,
            "distance": self.distance,
            "direction": self.direction,
            "prediction_model": self.prediction_model,
            "status": self.calculation_status.value,
            "original_value": self.original_value,
            "recalculated_value": self.recalculated_value,
            "relative_error": self.relative_error,
            "message": self.verification_message,
        }


@dataclass
class DistanceVerification:
    """距离验证结果"""
    description: str                       # 报告中的描述
    claimed_distance: float                 # 声称的距离 (m)
    actual_distance: float                 # 实际计算的距离 (m)
    distance_error: float                   # 误差 (m)
    relative_error_percent: float           # 相对误差 %
    status: VerificationStatus
    sensitive_point: Optional[str] = None  # 敏感点名称
    verification_message: str = ""

    def to_dict(self) -> Dict:
        return {
            "description": self.description,
            "claimed_distance": self.claimed_distance,
            "actual_distance": self.actual_distance,
            "distance_error": self.distance_error,
            "relative_error_percent": self.relative_error_percent,
            "status": self.status.value,
            "sensitive_point": self.sensitive_point,
            "message": self.verification_message,
        }


@dataclass
class VerificationReport:
    """完整验证报告"""
    report_id: str
    project_name: str
    verification_time: datetime
    predictions: List[PredictionResult] = field(default_factory=list)
    distance_verifications: List[DistanceVerification] = field(default_factory=list)
    data_traceability: Dict[str, Any] = field(default_factory=dict)
    overall_status: VerificationStatus = VerificationStatus.PENDING
    risk_level: str = "UNKNOWN"  # LOW, MEDIUM, HIGH, CRITICAL
    summary: str = ""

    def to_dict(self) -> Dict:
        return {
            "report_id": self.report_id,
            "project_name": self.project_name,
            "verification_time": self.verification_time.isoformat(),
            "predictions": [p.to_dict() for p in self.predictions],
            "distance_verifications": [d.to_dict() for d in self.distance_verifications],
            "data_traceability": self.data_traceability,
            "overall_status": self.overall_status.value,
            "risk_level": self.risk_level,
            "summary": self.summary,
        }

    def get_pass_rate(self) -> float:
        """获取通过率"""
        total = len(self.predictions) + len(self.distance_verifications)
        if total == 0:
            return 0.0
        passed = sum(1 for p in self.predictions if p.calculation_status == VerificationStatus.PASSED)
        passed += sum(1 for d in self.distance_verifications if d.status == VerificationStatus.PASSED)
        return (passed / total) * 100

    def get_failed_items(self) -> List[str]:
        """获取失败项列表"""
        failed = []
        for p in self.predictions:
            if p.calculation_status in [VerificationStatus.FAILED, VerificationStatus.WARNING]:
                failed.append(f"预测复算-{p.compound}: {p.verification_message}")
        for d in self.distance_verifications:
            if d.status in [VerificationStatus.FAILED, VerificationStatus.WARNING]:
                failed.append(f"距离验证-{d.sensitive_point}: {d.verification_message}")
        return failed


class DigitalTwinVerifier:
    """
    数字孪生验证器

    核心能力：
    1. 预测结果复算 - 用相同模型重新计算，验证报告数据真实性
    2. 空间距离验证 - 用GIS能力验证敏感点距离陈述
    3. 数据链追溯 - 从结论追溯到原始输入参数
    """

    def __init__(self):
        self.spatial_engine: Optional[SpatialIntelligenceEngine] = None
        self.calculation_callback: Optional[Callable] = None
        self.verification_history: List[VerificationReport] = []

    def set_spatial_engine(self, engine: SpatialIntelligenceEngine):
        """设置空间分析引擎"""
        self.spatial_engine = engine

    def set_calculation_callback(self, callback: Callable):
        """
        设置计算回调函数

        回调函数签名: async def calculate(params: PredictionInput, model: str) -> float
        返回计算得到的最大浓度
        """
        self.calculation_callback = callback

    async def verify_prediction(
        self,
        report_text: str,
        project_context: Dict[str, Any]
    ) -> PredictionResult:
        """
        验证报告中的一条预测结果

        Args:
            report_text: 包含预测结果的报告文本
            project_context: 项目上下文，包含坐标、行业等信息

        Returns:
            PredictionResult: 验证结果
        """
        # 1. 从文本中提取预测结果
        prediction = self._extract_prediction_from_text(report_text)

        # 2. 提取原始输入参数
        input_params = self._extract_input_params(report_text, project_context)

        # 3. 如果有计算回调，进行复算
        if self.calculation_callback and input_params:
            prediction.calculation_status = VerificationStatus.VERIFYING

            try:
                recalculated = await self.calculation_callback(input_params, prediction.prediction_model)
                prediction.recalculated_value = recalculated

                # 计算相对误差
                if prediction.original_value and prediction.original_value > 0:
                    prediction.relative_error = abs(
                        (recalculated - prediction.original_value) / prediction.original_value * 100
                    )

                    # 判断是否通过 (允许误差 ±5%)
                    if prediction.relative_error <= 5.0:
                        prediction.calculation_status = VerificationStatus.PASSED
                        prediction.verification_message = f"复算通过，误差{prediction.relative_error:.2f}%"
                    elif prediction.relative_error <= 10.0:
                        prediction.calculation_status = VerificationStatus.WARNING
                        prediction.verification_message = f"复算存在偏差，误差{prediction.relative_error:.2f}%"
                    else:
                        prediction.calculation_status = VerificationStatus.FAILED
                        prediction.verification_message = f"复算误差过大，误差{prediction.relative_error:.2f}%"
                else:
                    prediction.calculation_status = VerificationStatus.CANNOT_VERIFY
                    prediction.verification_message = "无法计算相对误差（原始值为0或缺失）"

            except Exception as e:
                prediction.calculation_status = VerificationStatus.FAILED
                prediction.verification_message = f"复算失败: {str(e)}"
        else:
            prediction.calculation_status = VerificationStatus.CANNOT_VERIFY
            prediction.verification_message = "缺少计算回调或输入参数"

        return prediction

    def _extract_prediction_from_text(self, text: str) -> PredictionResult:
        """从文本中提取预测结果"""
        result = PredictionResult(
            compound="未知",
            max_concentration=0.0
        )

        # 提取浓度值和单位
        # 匹配模式: "XX最大落地浓度为X.XX mg/m³"
        concentration_patterns = [
            r'([A-Za-z0-9₂₃⁺⁻²³]+)最大落地浓度[为]?\s*([0-9.]+)\s*(mg/m³|μg/m³|ug/m³)',
            r'([A-Za-z0-9₂₃⁺⁻²³]+)最大浓度[为]?\s*([0-9.]+)\s*(mg/m³|μg/m³|ug/m³)',
            r'([A-Za-z0-9₂₃⁺⁻²³]+)\s*最大落地浓度\s*([0-9.]+)\s*(mg/m³|μg/m³|ug/m³)',
            r'浓度.*?([0-9.]+)\s*(mg/m³|μg/m³|ug/m³)',
        ]

        for pattern in concentration_patterns:
            match = re.search(pattern, text)
            if match:
                if len(match.groups()) >= 2:
                    result.compound = match.group(1)
                    result.original_value = float(match.group(2))
                    result.max_concentration = result.original_value

                    unit = match.group(3)
                    # 统一转换为 mg/m³
                    if unit in ['μg/m³', 'ug/m³']:
                        result.max_concentration = result.original_value / 1000
                        result.original_value = result.max_concentration
                break

        # 提取落地距离
        distance_patterns = [
            r'落地距离[为]?\s*([0-9]+)\s*m',
            r'出现在下风向\s*([0-9]+)\s*m',
            r'距离\s*([0-9]+)\s*m',
        ]
        for pattern in distance_patterns:
            match = re.search(pattern, text)
            if match:
                result.distance = float(match.group(1))
                break

        # 提取方向
        if '下风向' in text:
            result.direction = '下风向'
        elif '上风向' in text:
            result.direction = '上风向'

        return result

    def _extract_input_params(
        self,
        text: str,
        project_context: Dict[str, Any]
    ) -> Optional[PredictionInput]:
        """从文本和上下文中提取模型输入参数"""
        params = PredictionInput()

        # 从项目上下文中提取坐标
        if 'lat' in project_context:
            params.source_lat = project_context['lat']
        if 'lon' in project_context:
            params.source_lon = project_context['lon']

        # 从文本中提取源强
        emission_patterns = [
            (r'排放速率\s*[为]?\s*([0-9.]+)\s*(g/s|kg/h)', 'emission_rate', 1),
            (r'源强\s*[为]?\s*([0-9.]+)\s*(g/s|kg/h)', 'emission_rate', 1),
        ]

        for pattern, field, group_idx in emission_patterns:
            match = re.search(pattern, text)
            if match:
                value = float(match.group(1))
                unit = match.group(2)
                # 统一转换为 g/s
                if unit == 'kg/h':
                    value = value * 1000 / 3600
                setattr(params, field, value)
                params.data_source = DataSource.EXTRACTED
                params.confidence = 0.8
                break

        # 从文本中提取气象参数
        wind_speed_patterns = [
            r'平均风速\s*[为]?\s*([0-9.]+)\s*(m/s)',
            r'风速\s*[为]?\s*([0-9.]+)\s*(m/s)',
        ]
        for pattern in wind_speed_patterns:
            match = re.search(pattern, text)
            if match:
                params.wind_speed = float(match.group(1))
                params.confidence = max(params.confidence, 0.7)
                break

        # 提取稳定度等级
        stability_match = re.search(r'稳定度[为]?([A-F])类?', text)
        if stability_match:
            params.stability_class = stability_match.group(1)
            params.confidence = max(params.confidence, 0.8)

        # 从项目上下文中提取更多参数
        if 'industry_type' in project_context:
            # 根据行业类型设置默认排放高度
            if project_context.get('industry_type') == '化工':
                params.emission_height = project_context.get('stack_height', 30.0)
            elif project_context.get('industry_type') == '电力':
                params.emission_height = project_context.get('stack_height', 120.0)

        if params.emission_rate or params.wind_speed:
            return params
        return None

    async def verify_distance_statement(
        self,
        description: str,
        project_lat: float,
        project_lon: float,
        project_context: Dict[str, Any]
    ) -> DistanceVerification:
        """
        验证报告中关于敏感点距离的陈述

        Args:
            description: 报告中的距离描述，如"位于项目北侧500m"
            project_lat: 项目纬度
            project_lon: 项目经度
            project_context: 项目上下文

        Returns:
            DistanceVerification: 验证结果
        """
        result = DistanceVerification(
            description=description,
            claimed_distance=0.0,
            actual_distance=0.0,
            distance_error=0.0,
            relative_error_percent=0.0,
            status=VerificationStatus.PENDING
        )

        # 1. 从描述中提取声称的距离和方位
        claimed = self._extract_claimed_distance(description)
        if claimed is None:
            result.status = VerificationStatus.CANNOT_VERIFY
            result.verification_message = "无法从描述中提取距离信息"
            return result

        result.claimed_distance = claimed

        # 2. 提取敏感点信息
        sensitive_point = self._extract_sensitive_point_name(description)

        # 3. 如果有空间引擎，使用它计算实际距离
        if self.spatial_engine:
            try:
                # 根据方位和描述推断敏感点类型
                poi_category = self._infer_poi_category(description)

                # 搜索附近的敏感点
                pois = await self.spatial_engine.search_nearby_pois(
                    lat=project_lat,
                    lon=project_lon,
                    keywords=[sensitive_point] if sensitive_point else [poi_category.value],
                    radius=10000  # 10km范围
                )

                # 找到最近的匹配敏感点
                nearest = None
                min_distance = float('inf')

                for poi in pois:
                    # 计算实际距离
                    actual_dist = self._haversine_distance(
                        project_lat, project_lon,
                        poi.latitude, poi.longitude
                    )

                    # 检查方位是否匹配
                    bearing = self._calculate_bearing(
                        project_lat, project_lon,
                        poi.latitude, poi.longitude
                    )

                    if self._bearing_matches_direction(bearing, description):
                        if actual_dist < min_distance:
                            min_distance = actual_dist
                            nearest = poi

                if nearest:
                    result.actual_distance = min_distance
                    result.sensitive_point = nearest.name
                    result.distance_error = abs(result.actual_distance - result.claimed_distance)
                    result.relative_error_percent = (
                        result.distance_error / result.claimed_distance * 100
                        if result.claimed_distance > 0 else 0
                    )

                    # 判断是否通过（允许误差10%）
                    if result.relative_error_percent <= 10.0:
                        result.status = VerificationStatus.PASSED
                        result.verification_message = f"距离验证通过，实际距离{int(result.actual_distance)}m"
                    elif result.relative_error_percent <= 20.0:
                        result.status = VerificationStatus.WARNING
                        result.verification_message = f"距离存在偏差，误差{result.relative_error_percent:.1f}%"
                    else:
                        result.status = VerificationStatus.FAILED
                        result.verification_message = f"距离误差过大，误差{result.relative_error_percent:.1f}%"
                else:
                    result.status = VerificationStatus.CANNOT_VERIFY
                    result.verification_message = f"在指定方位未找到敏感点{sensitive_point or poi_category.value}"

            except Exception as e:
                result.status = VerificationStatus.FAILED
                result.verification_message = f"空间验证失败: {str(e)}"
        else:
            # 没有空间引擎时，标记为无法验证
            result.status = VerificationStatus.CANNOT_VERIFY
            result.verification_message = "空间分析引擎未配置，无法验证距离"

        return result

    def _extract_claimed_distance(self, description: str) -> Optional[float]:
        """从描述中提取声称的距离"""
        patterns = [
            r'北侧|南侧|东侧|西侧|东北|西北|东南|西南\s*(\d+)\s*m',
            r'(\d+)\s*m.*?(?:北侧|南侧|东侧|西侧|东北|西北|东南|西南)',
            r'距离.*?(\d+)\s*m',
            r'约\s*(\d+)\s*m',
        ]

        for pattern in patterns:
            match = re.search(pattern, description)
            if match:
                return float(match.group(1))
        return None

    def _extract_sensitive_point_name(self, description: str) -> Optional[str]:
        """从描述中提取敏感点名称"""
        # 常见的敏感点描述模式
        patterns = [
            r'([^\s]+?(?:学校|医院|居民区|村庄|养老院|保护区|水源地))',
            r'([A-Za-z0-9]+(?:村|镇|庄|社区|小学|中学))',
        ]

        for pattern in patterns:
            match = re.search(pattern, description)
            if match:
                return match.group(1)
        return None

    def _infer_poi_category(self, description: str) -> 'POICategory':
        """从描述推断POI类别"""
        if any(kw in description for kw in ['学校', '小学', '中学']):
            return POICategory.SCHOOL
        elif any(kw in description for kw in ['医院', '卫生院']):
            return POICategory.HOSPITAL
        elif any(kw in description for kw in ['居民区', '村庄', '屯', '庄']):
            return POICategory.RESIDENTIAL
        elif any(kw in description for kw in ['养老院', '敬老院']):
            return POICategory.NURSING_HOME
        elif any(kw in description for kw in ['水源地', '饮用水']):
            return POICategory.WATER_SOURCE
        elif any(kw in description for kw in ['保护区', '生态']):
            return POICategory.NATURE_RESERVE
        return POICategory.RESIDENTIAL  # 默认

    def _haversine_distance(
        self,
        lat1: float, lon1: float,
        lat2: float, lon2: float
    ) -> float:
        """计算两点间的大圆距离（米）"""
        import math

        R = 6371000  # 地球半径（米）

        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)

        a = (math.sin(delta_phi / 2) ** 2 +
             math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c

    def _calculate_bearing(
        self,
        lat1: float, lon1: float,
        lat2: float, lon2: float
    ) -> float:
        """计算从点1到点2的方位角（度）"""
        import math

        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_lambda = math.radians(lon2 - lon1)

        x = math.sin(delta_lambda) * math.cos(phi2)
        y = (math.cos(phi1) * math.sin(phi2) -
             math.sin(phi1) * math.cos(phi2) * math.cos(delta_lambda))

        bearing = math.degrees(math.atan2(x, y))
        return (bearing + 360) % 360

    def _bearing_matches_direction(self, bearing: float, description: str) -> bool:
        """判断方位角是否匹配描述中的方向"""
        # 方位角: 0=北, 90=东, 180=南, 270=西
        direction_ranges = {
            '北': (315, 45),      # 北侧: 315-360 或 0-45
            '南': (135, 225),    # 南侧: 135-225
            '东': (45, 135),     # 东侧: 45-135
            '西': (225, 315),    # 西侧: 225-315
            '东北': (0, 90),     # 东北: 0-90
            '西北': (270, 360),  # 西北: 270-360
            '东南': (90, 180),   # 东南: 90-180
            '西南': (180, 270),  # 西南: 180-270
        }

        # 检查是否在允许范围内（±30度）
        tolerance = 30

        for direction, (start, end) in direction_ranges.items():
            if direction in description:
                if direction == '北':
                    # 北侧需要特殊处理（跨越0度）
                    if bearing >= 360 - tolerance or bearing <= tolerance:
                        return True
                elif direction == '西北':
                    if bearing >= 360 - tolerance or bearing <= tolerance:
                        return True
                else:
                    mid = (start + end) / 2
                    if abs(bearing - mid) <= tolerance:
                        return True

        return True  # 如果无法判断，返回True（不过滤）

    async def verify_full_report(
        self,
        report_id: str,
        project_name: str,
        report_content: Dict[str, Any],
        project_context: Dict[str, Any]
    ) -> VerificationReport:
        """
        对整份报告进行全面验证

        Args:
            report_id: 报告ID
            project_name: 项目名称
            report_content: 报告内容，结构化数据
            project_context: 项目上下文

        Returns:
            VerificationReport: 完整验证报告
        """
        report = VerificationReport(
            report_id=report_id,
            project_name=project_name,
            verification_time=datetime.now()
        )

        # 1. 验证预测结果
        if 'predictions' in report_content:
            for pred_text in report_content['predictions']:
                result = await self.verify_prediction(pred_text, project_context)
                report.predictions.append(result)

        # 2. 验证距离陈述
        if 'distance_statements' in report_content:
            for desc in report_content['distance_statements']:
                result = await self.verify_distance_statement(
                    desc,
                    project_context.get('lat', 0),
                    project_context.get('lon', 0),
                    project_context
                )
                report.distance_verifications.append(result)

        # 3. 计算整体状态
        all_verified = (
            len(report.predictions) + len(report.distance_verifications)
        )
        if all_verified == 0:
            report.overall_status = VerificationStatus.CANNOT_VERIFY
            report.summary = "报告中没有可验证的预测结果或距离陈述"
        else:
            failed = sum(
                1 for p in report.predictions
                if p.calculation_status in [VerificationStatus.FAILED]
            )
            failed += sum(
                1 for d in report.distance_verifications
                if d.status == VerificationStatus.FAILED
            )

            if failed == 0:
                warnings = sum(
                    1 for p in report.predictions
                    if p.calculation_status == VerificationStatus.WARNING
                )
                warnings += sum(
                    1 for d in report.distance_verifications
                    if d.status == VerificationStatus.WARNING
                )

                if warnings == 0:
                    report.overall_status = VerificationStatus.PASSED
                    report.summary = f"所有验证项均通过，通过率{report.get_pass_rate():.1f}%"
                else:
                    report.overall_status = VerificationStatus.WARNING
                    report.summary = f"存在{warnings}项警告，通过率{report.get_pass_rate():.1f}%"
            else:
                report.overall_status = VerificationStatus.FAILED
                report.summary = f"存在{failed}项验证失败，通过率{report.get_pass_rate():.1f}%"

        # 4. 计算风险等级
        pass_rate = report.get_pass_rate()
        if pass_rate >= 95:
            report.risk_level = "LOW"
        elif pass_rate >= 80:
            report.risk_level = "MEDIUM"
        elif pass_rate >= 60:
            report.risk_level = "HIGH"
        else:
            report.risk_level = "CRITICAL"

        # 保存历史
        self.verification_history.append(report)

        return report

    def generate_verification_hash(self, verification_report: VerificationReport) -> str:
        """生成验证报告的哈希值，用于追溯"""
        content = json.dumps(verification_report.to_dict(), sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]


# 全局实例
_verifier_instance: Optional[DigitalTwinVerifier] = None


def get_verifier() -> DigitalTwinVerifier:
    """获取数字孪生验证器全局实例"""
    global _verifier_instance
    if _verifier_instance is None:
        _verifier_instance = DigitalTwinVerifier()
    return _verifier_instance


async def verify_prediction_async(
    report_text: str,
    project_context: Dict[str, Any]
) -> PredictionResult:
    """异步验证预测结果的便捷函数"""
    verifier = get_verifier()
    return await verifier.verify_prediction(report_text, project_context)


async def verify_distance_async(
    description: str,
    project_lat: float,
    project_lon: float,
    project_context: Dict[str, Any]
) -> DistanceVerification:
    """异步验证距离陈述的便捷函数"""
    verifier = get_verifier()
    return await verifier.verify_distance_statement(
        description, project_lat, project_lon, project_context
    )


async def verify_full_report_async(
    report_id: str,
    project_name: str,
    report_content: Dict[str, Any],
    project_context: Dict[str, Any]
) -> VerificationReport:
    """异步验证整份报告的便捷函数"""
    verifier = get_verifier()
    return await verifier.verify_full_report(
        report_id, project_name, report_content, project_context
    )