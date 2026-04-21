"""
污染源源强核算 (Source Calculator)
================================

污染源源强核算模型，支持大气、水、噪声、固废等多种类型。
"""

import asyncio
import math
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional


class SourceType(Enum):
    """污染源类型"""
    AIR = "air"               # 大气污染源
    WATER = "water"           # 水污染源
    NOISE = "noise"           # 噪声污染源
    SOLID_WASTE = "solid_waste"  # 固废污染源


class EmissionType(Enum):
    """排放方式"""
    ORGANIZED = "organized"   # 有组织排放
    UNORGANIZED = "unorganized"  # 无组织排放
    AREA = "area"            # 面源
    LINE = "line"            # 线源


@dataclass
class PollutionSource:
    """污染源"""
    source_id: str
    name: str                           # 源名称（如"破碎工段"）
    source_type: SourceType
    emission_type: EmissionType

    # 位置信息
    x: float = 0                         # X坐标
    y: float = 0                         # Y坐标
    z: float = 0                         # Z坐标（高度）

    # 排放参数
    emission_rate: float = 0            # 排放速率 (g/s 或 kg/h)
    concentration: float = 0            # 排放浓度 (mg/m³)
    temperature: float = 25              # 排放温度 (℃)
    velocity: float = 0                 # 排放速度 (m/s)
    diameter: float = 0                 # 排放口直径 (m)

    # 污染物类型
    pollutants: list[str] = field(default_factory=list)  # 污染物列表

    # 附加数据
    metadata: dict = field(default_factory=dict)


@dataclass
class CalculationResult:
    """计算结果"""
    source_id: str
    source_type: SourceType
    calculated_at: datetime
    parameters: dict = field(default_factory=dict)
    results: dict = field(default_factory=dict)
    compliance: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)


class SourceCalculator:
    """
    污染源源强计算器

    用法:
        calculator = SourceCalculator()

        # 识别污染源
        source = calculator.identify_pollution_source({
            "name": "破碎机",
            "type": "dust",
            "capacity": "50t/h"
        })

        # 计算源强
        result = await calculator.calculate(source)
    """

    def __init__(self):
        self._models: dict[str, Callable] = {}
        self._register_default_models()

    def _register_default_models(self) -> None:
        """注册默认计算模型"""
        # 大气模型
        self._models["air_gaussian"] = self._calc_air_gaussian
        self._models["air_stack"] = self._calc_air_stack
        self._models["air_area"] = self._calc_air_area

        # 水模型
        self._models["water_point"] = self._calc_water_point
        self._models["water_nonpoint"] = self._calc_water_nonpoint

        # 噪声模型
        self._models["noise_point"] = self._calc_noise_point
        self._models["noise_line"] = self._calc_noise_line

    def identify_pollution_source(self, equipment: dict) -> Optional[PollutionSource]:
        """
        从设备数据中识别污染源

        Args:
            equipment: 设备数据

        Returns:
            PollutionSource: 识别的污染源，如果没有识别到则返回 None
        """
        name = equipment.get("name", "").lower()
        equip_type = equipment.get("type", "").lower()
        capacity = equipment.get("capacity", "")

        # 污染物关键词映射
        pollutant_map = {
            "dust": ["粉尘", "dust", "颗粒物", "PM"],
            "vocs": ["VOCs", "挥发性", "有机", "苯"],
            "so2": ["二氧化硫", "SO2", "硫"],
            "nox": ["氮氧化物", "NOx", "NO2"],
            "cod": ["COD", "化学需氧量", "有机物"],
            "ammonia": ["氨氮", "NH3", "氨"],
        }

        # 设备类型识别
        identified_type = None
        emission_type = EmissionType.ORGANIZED
        pollutants = []

        # 破碎/粉碎设备 → 粉尘
        if any(kw in name for kw in ["破碎", "粉碎", "研磨", "crush", "mill"]):
            identified_type = SourceType.AIR
            pollutants.append("dust")

        # 反应/化工设备 → VOCs
        elif any(kw in name for kw in ["反应", "蒸馏", "萃取", "反应釜"]):
            identified_type = SourceType.AIR
            emission_type = EmissionType.ORGANIZED
            pollutants.extend(["VOCs", "苯"])

        # 燃烧设备 → SO2, NOx
        elif any(kw in name for kw in ["锅炉", "炉", "燃烧", "heating"]):
            identified_type = SourceType.AIR
            pollutants.extend(["SO2", "NOx", "烟尘"])

        # 废水设备 → 水污染
        elif any(kw in name for kw in ["废水", "污水", "水处理", " wastewater"]):
            identified_type = SourceType.WATER
            emission_type = EmissionType.UNORGANIZED
            pollutants.extend(["COD", "NH3-N", "SS"])

        # 风机/空压机 → 噪声
        elif any(kw in name for kw in ["风机", "空压机", "泵", "fan", "compressor", "pump"]):
            identified_type = SourceType.NOISE
            emission_type = EmissionType.POINT if "pump" in name else EmissionType.LINE
            pollutants.append("noise")

        # 储罐 → VOCs 无组织
        elif any(kw in name for kw in ["储罐", "储槽", "storage", "tank"]):
            identified_type = SourceType.AIR
            emission_type = EmissionType.UNORGANIZED
            pollutants.append("VOCs")

        # 固废仓库 → 固废
        elif any(kw in name for kw in ["固废", "危废", "仓库", "storage"]):
            identified_type = SourceType.SOLID_WASTE
            emission_type = EmissionType.AREA
            pollutants.append("solid_waste")

        if not identified_type:
            return None

        # 计算源强（简化版，实际需要更复杂的公式）
        emission_rate = self._estimate_emission_rate(identified_type, pollutants, capacity)

        return PollutionSource(
            source_id=equipment.get("id", f"src_{hash(name)[:8]}"),
            name=equipment.get("name", "未知源"),
            source_type=identified_type,
            emission_type=emission_type,
            pollutants=pollutants,
            emission_rate=emission_rate,
            metadata=equipment
        )

    def _estimate_emission_rate(self, source_type: SourceType, pollutants: list[str], capacity: str) -> float:
        """估算排放速率"""
        # 简化估算，实际需要根据行业标准计算
        base_rates = {
            SourceType.AIR: 0.5,     # g/s
            SourceType.WATER: 10.0,   # mg/L
            SourceType.NOISE: 85.0,   # dB(A)
            SourceType.SOLID_WASTE: 100.0,  # kg/d
        }

        base = base_rates.get(source_type, 1.0)

        # 根据污染物类型调整
        if "dust" in pollutants:
            base *= 1.2
        if "VOCs" in pollutants:
            base *= 1.5

        return base

    async def calculate(self, source: PollutionSource) -> CalculationResult:
        """
        计算污染源强度

        Args:
            source: 污染源

        Returns:
            CalculationResult: 计算结果
        """
        calc_start = datetime.now()

        if source.source_type == SourceType.AIR:
            if source.emission_type == EmissionType.ORGANIZED:
                if source.diameter > 0:
                    result = await self._calc_air_stack(source)
                else:
                    result = await self._calc_air_gaussian(source)
            else:
                result = await self._calc_air_area(source)

        elif source.source_type == SourceType.WATER:
            if source.emission_type == EmissionType.POINT:
                result = await self._calc_water_point(source)
            else:
                result = await self._calc_water_nonpoint(source)

        elif source.source_type == SourceType.NOISE:
            if source.emission_type == EmissionType.LINE:
                result = await self._calc_noise_line(source)
            else:
                result = await self._calc_noise_point(source)

        elif source.source_type == SourceType.SOLID_WASTE:
            result = await self._calc_solid_waste(source)

        else:
            result = {"error": "Unknown source type"}

        return CalculationResult(
            source_id=source.source_id,
            source_type=source.source_type,
            calculated_at=calc_start,
            parameters=self._get_source_parameters(source),
            results=result,
            compliance=self._check_compliance(source, result)
        )

    def _get_source_parameters(self, source: PollutionSource) -> dict:
        """获取源参数"""
        return {
            "name": source.name,
            "type": source.source_type.value,
            "emission_type": source.emission_type.value,
            "position": {"x": source.x, "y": source.y, "z": source.z},
            "emission_rate": source.emission_rate,
            "concentration": source.concentration,
            "temperature": source.temperature,
            "velocity": source.velocity,
            "diameter": source.diameter,
            "pollutants": source.pollutants
        }

    async def _calc_air_stack(self, source: PollutionSource) -> dict:
        """计算有组织大气排放（烟囱）"""
        # 简化高斯模型
        # 实际应调用专业的 AERMOD 或 similar

        # 抬升高度计算 (Briggs公式简化)
        v_s = source.velocity  # 出口速度
        d = source.diameter    # 出口直径
        delta_t = source.temperature - 25  # 温差

        if v_s > 0 and d > 0 and delta_t > 0:
            # 浮力抬升
            h_e = 0 if False else 2 * (v_s * d) ** 0.5 * (delta_t / source.temperature) ** 0.25
        else:
            h_e = 0

        effective_height = source.z + h_e

        return {
            "effective_height": round(effective_height, 2),
            "plume_rise": round(h_e, 2),
            "max_concentration": round(source.emission_rate * 0.01, 4),
            "downwind_distance": 100,  # 最大落地浓度距离 (m)
            "model_used": "simplified_gaussian"
        }

    async def _calc_air_gaussian(self, source: PollutionSource) -> dict:
        """计算高斯扩散模型"""
        # 简化版
        sigma_y = 20  # 横向扩散参数
        sigma_z = 10  # 垂直扩散参数

        return {
            "max_concentration": round(source.emission_rate / (2 * math.pi * sigma_y * sigma_z), 4),
            "model_used": "gaussian_plume",
            "half_width": sigma_y * 3,
            "plume_depth": sigma_z * 3
        }

    async def _calc_air_area(self, source: PollutionSource) -> dict:
        """计算面源扩散"""
        # 简化为多个点源
        return {
            "equivalent_sources": 4,
            "avg_concentration": round(source.emission_rate * 0.001, 4),
            "model_used": "area_source"
        }

    async def _calc_water_point(self, source: PollutionSource) -> dict:
        """计算点源水污染"""
        # 河流稀释模型
        q = source.emission_rate / 1000  # 排放流量 m³/s
        c = source.concentration  # 浓度 mg/L

        # 河流背景
        q_river = 10  # 假设河流流量 m³/s
        c_river = 5   # 背景浓度 mg/L

        # 稀释混合后浓度
        c_mix = (q * c + q_river * c_river) / (q + q_river)

        return {
            "discharge_flow": round(q, 3),
            "mixing_concentration": round(c_mix, 2),
            "background_concentration": c_river,
            "dilution_factor": round((q + q_river) / q, 1),
            "model_used": "simple_mixing"
        }

    async def _calc_water_nonpoint(self, source: PollutionSource) -> dict:
        """计算非点源水污染"""
        area = source.metadata.get("area", 1000)  # 汇水面积 m²

        return {
            "catchment_area": area,
            "runoff_coefficient": 0.8,
            "pollutant_load": round(source.emission_rate * area / 1000, 2),
            "model_used": "runoff_load"
        }

    async def _calc_noise_point(self, source: PollutionSource) -> dict:
        """计算点源噪声"""
        # 噪声衰减模型
        l_w = source.emission_rate  # 源声功率级 dB(A)
        r = 10  # 预测距离 m

        # 几何衰减
        l_p = l_w - 20 * math.log10(r) - 8

        return {
            "source_level": l_w,
            "distance": r,
            "predicted_level": round(max(30, l_p), 1),
            "ground_absorption": 0,
            "model_used": "point_source"
        }

    async def _calc_noise_line(self, source: PollutionSource) -> dict:
        """计算线源噪声"""
        l_w = source.emission_rate
        l_p = l_w - 10 * math.log10(source.metadata.get("length", 100)) + 3

        return {
            "source_level": l_w,
            "length": source.metadata.get("length", 100),
            "predicted_level": round(max(30, l_p), 1),
            "model_used": "line_source"
        }

    async def _calc_solid_waste(self, source: PollutionSource) -> dict:
        """计算固废源强"""
        capacity = source.metadata.get("capacity", 1000)  # 吨/年

        # 危废比例估算
        hazardous_ratio = 0.2

        return {
            "total_waste": round(capacity, 2),
            "hazardous_waste": round(capacity * hazardous_ratio, 2),
            "general_waste": round(capacity * (1 - hazardous_ratio), 2),
            "storage_area": round(capacity / 100, 2),  # 估算存储面积 m²
            "model_used": "emission_factor"
        }

    def _check_compliance(self, source: PollutionSource, result: dict) -> dict:
        """检查合规性"""
        # 标准限值（简化）
        standards = {
            "dust": 120,       # mg/m³
            "SO2": 50,         # mg/m³
            "NOx": 100,        # mg/m³
            "VOCs": 60,        # mg/m³
            "COD": 100,        # mg/L
            "NH3-N": 15,       # mg/L
        }

        compliance_results = {}

        for pollutant in source.pollutants:
            if pollutant in standards:
                limit = standards[pollutant]
                actual = result.get("max_concentration", 0) or result.get("mixing_concentration", 0)

                compliance_results[pollutant] = {
                    "limit": limit,
                    "actual": actual,
                    "pass": actual <= limit,
                    "exceed_ratio": round((actual - limit) / limit * 100, 1) if actual > limit else 0
                }

        return compliance_results

    def batch_calculate(self, sources: list[PollutionSource]) -> list[CalculationResult]:
        """
        批量计算

        Args:
            sources: 污染源列表

        Returns:
            list[CalculationResult]: 计算结果列表
        """
        return [asyncio.run(self.calculate(s)) for s in sources]


def calculate_source_strength(source_data: dict) -> Optional[PollutionSource]:
    """便捷函数：从字典创建并返回污染源"""
    calculator = SourceCalculator()
    return calculator.identify_pollution_source(source_data)