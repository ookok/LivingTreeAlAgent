"""
工艺数字孪生体 (Process Digital Twin)
======================================

为每个企业项目创建可实时仿真、预测、优化的"工艺数字孪生体"。

核心功能：
1. 实时环境影响动态仿真 - 污染扩散模型
2. 基于图谱的智能工艺优化 - 参数对比与优化建议
3. 虚拟试错与What-If分析 - 工艺改造可行性评估
4. 用户数字分身管理 - 支持出租和参与活动

Author: Hermes Desktop Team
"""

import logging
import json
import uuid
import math
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import threading
import random

from .user_twin import (
    TwinStatus, TwinSkillLevel, ActivityType, RentalStatus,
    UserTwin, Activity, RentalRequest,
    UserTwinManager, get_user_twin_manager,
    create_user_twin, get_user_twins
)


# 用户数字分身相关导出
__all__ = [
    # 枚举
    "TwinStatus",
    "TwinSkillLevel",
    "ActivityType",
    "RentalStatus",
    # 数据类
    "UserTwin",
    "Activity",
    "RentalRequest",
    # 管理器
    "UserTwinManager",
    "get_user_twin_manager",
    # 工具函数
    "create_user_twin",
    "get_user_twins",
    # 工艺数字孪生体
    "ProcessDigitalTwin",
    "DigitalTwinFactory",
    "get_twin_factory",
    "create_digital_twin"
]

logger = logging.getLogger(__name__)


class SimulationStatus(Enum):
    """仿真状态"""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"


class ScenarioType(Enum):
    """情景类型"""
    NORMAL = "normal"                 # 正常工况
    FULL_LOAD = "full_load"          # 满负荷生产
    EQUIPMENT_FAILURE = "equipment_failure"  # 设备故障
    MAINTENANCE = "maintenance"       # 维护保养
    EXTREME_WEATHER = "extreme_weather"  # 极端天气
    EMERGENCY = "emergency"           # 应急情况
    CUSTOM = "custom"                 # 自定义


@dataclass
class TimeSeriesPoint:
    """时间序列数据点"""
    timestamp: datetime
    value: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SpatialPoint:
    """空间坐标点"""
    x: float  # 经度或相对X
    y: float  # 纬度或相对Y
    z: float = 0.0  # 高度


@dataclass
class EmissionSource:
    """排放源"""
    source_id: str
    name: str
    source_type: str              # point/area/line
    location: SpatialPoint
    emission_rate: float          # 排放速率 (kg/h)
    pollutant: str                # 污染物类型
    exit_velocity: float = 0.0    # 出口流速 (m/s)
    exit_temperature: float = 0.0  # 出口温度 (℃)
    stack_height: float = 0.0     # 烟囱高度 (m)
    parameters: Dict[str, float] = field(default_factory=dict)


@dataclass
class Receptor:
    """受体点（敏感目标）"""
    receptor_id: str
    name: str
    location: SpatialPoint
    receptor_type: str            # residential/school/hospital/industry
    sensitivity: str              # high/medium/low
    distance_to_source: float = 0.0  # 到最近排放源距离


@dataclass
class WeatherCondition:
    """气象条件"""
    wind_speed: float             # 风速 (m/s)
    wind_direction: float         # 风向 (度，正北为0)
    temperature: float            # 温度 (℃)
    humidity: float               # 湿度 (%)
    atmospheric_stability: str     # 大气稳定度 (A/B/C/D/E/F)
    mixing_height: float           # 混合层高度 (m)
    precipitation: float = 0.0     # 降水量 (mm/h)
    cloud_cover: float = 0.0      # 云量 (0-10)


@dataclass
class ConcentrationField:
    """浓度场（仿真结果）"""
    field_id: str
    timestamp: datetime
    grid_resolution: float         # 网格分辨率 (m)
    grid_extent: Tuple[float, float, float, float]  # x_min, x_max, y_min, y_max
    concentrations: List[List[float]]  # 二维浓度矩阵
    max_concentration: float
    max_location: SpatialPoint
    affected_receptors: List[Dict]  # 受影响的受体
    unit: str = "μg/m³"


@dataclass
class SimulationResult:
    """仿真结果"""
    simulation_id: str
    scenario_name: str
    status: SimulationStatus
    start_time: datetime
    end_time: datetime = None
    duration_seconds: float = 0.0

    # 浓度场
    concentration_fields: List[ConcentrationField] = field(default_factory=list)

    # 统计信息
    max_ground_level: float = 0.0    # 最大地面浓度
    exceedance_areas: List[Dict] = field(default_factory=list)  # 超标区域
    receptor_impacts: List[Dict] = field(default_factory=list)  # 受体影响

    # 参数
    parameters: Dict[str, Any] = field(default_factory=dict)

    # 导出数据
    export_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WhatIfScenario:
    """What-If情景"""
    scenario_id: str
    name: str
    description: str
    modifications: List[Dict] = field(default_factory=dict)  # 修改内容

    # 预期效果
    expected_emission_reduction: float = 0.0  # 预期减排量 (%)
    expected_cost: float = 0.0               # 预期成本
    expected_benefit: float = 0.0            # 预期收益
    payback_period: float = 0.0              # 投资回收期 (年)

    # 评估结果
    feasibility_score: float = 0.0           # 可行性评分 (0-1)
    risk_level: str = "low"                  # 风险等级
    recommendations: List[str] = field(default_factory=list)


class ProcessDigitalTwin:
    """
    工艺数字孪生体

    为企业项目创建可实时仿真、预测、优化的数字孪生体。

    使用示例：
    ```python
    twin = ProcessDigitalTwin(project_id="project_001")

    # 添加排放源
    twin.add_emission_source(EmissionSource(...))

    # 添加受体点
    twin.add_receptor(Receptor(...))

    # 设置气象条件
    twin.set_weather(WeatherCondition(...))

    # 运行仿真
    result = twin.simulate(duration_hours=24)

    # What-If分析
    scenario = twin.create_whatif_scenario(
        name="干式喷漆房改造",
        modifications=[
            {"type": "replace_equipment", "target": "spray_booth", "new": "dry_booth"},
            {"type": "add_equipment", "target": "rco", "capacity": 5000}
        ]
    )
    report = twin.evaluate_scenario(scenario)
    ```
    """

    def __init__(self, project_id: str, project_name: str = ""):
        self.project_id = project_id
        self.project_name = project_name

        # 孪生体数据
        self.emission_sources: Dict[str, EmissionSource] = {}
        self.receptors: Dict[str, Receptor] = {}
        self.weather_condition: Optional[WeatherCondition] = None

        # 图谱链接
        self.process_node_ids: Set[str] = set()
        self.equipment_node_ids: Set[str] = set()

        # 仿真引擎
        self._diffusion_model = None
        self._current_simulation: Optional[SimulationResult] = None

        # 历史数据
        self._historical_data: Dict[str, List[TimeSeriesPoint]] = {}

        # 优化建议
        self._optimization_cache: Dict[str, Any] = {}

        # 锁
        self._lock = threading.RLock()

        logger.info(f"创建工艺数字孪生体: {project_id}")

    def add_emission_source(self, source: EmissionSource) -> bool:
        """添加排放源"""
        with self._lock:
            self.emission_sources[source.source_id] = source
            logger.info(f"添加排放源: {source.name}")
            return True

    def remove_emission_source(self, source_id: str) -> bool:
        """移除排放源"""
        with self._lock:
            if source_id in self.emission_sources:
                del self.emission_sources[source_id]
                return True
            return False

    def add_receptor(self, receptor: Receptor) -> bool:
        """添加受体点"""
        with self._lock:
            self.receptors[receptor.receptor_id] = receptor
            # 计算到最近排放源的距离
            if self.emission_sources:
                min_dist = float('inf')
                for source in self.emission_sources.values():
                    dist = self._calculate_distance(receptor.location, source.location)
                    if dist < min_dist:
                        min_dist = dist
                receptor.distance_to_source = min_dist
            return True

    def set_weather(self, weather: WeatherCondition):
        """设置气象条件"""
        with self._lock:
            self.weather_condition = weather

    def link_to_knowledge_graph(self, process_node_ids: List[str],
                               equipment_node_ids: List[str] = None):
        """链接到知识图谱"""
        with self._lock:
            self.process_node_ids = set(process_node_ids)
            if equipment_node_ids:
                self.equipment_node_ids = set(equipment_node_ids)

    def simulate(self, duration_hours: float = 24,
                time_step_minutes: float = 10,
                scenario_type: ScenarioType = ScenarioType.NORMAL) -> SimulationResult:
        """
        运行仿真

        Args:
            duration_hours: 仿真时长（小时）
            time_step_minutes: 时间步长（分钟）
            scenario_type: 情景类型

        Returns:
            仿真结果
        """
        simulation_id = f"sim_{self.project_id}_{int(datetime.now().timestamp())}"

        # 创建仿真结果对象
        result = SimulationResult(
            simulation_id=simulation_id,
            scenario_name=scenario_type.value,
            status=SimulationStatus.RUNNING,
            start_time=datetime.now(),
            parameters={
                "duration_hours": duration_hours,
                "time_step_minutes": time_step_minutes,
                "scenario_type": scenario_type.value,
                "emission_sources_count": len(self.emission_sources),
                "receptors_count": len(self.receptors)
            }
        )

        try:
            # 使用扩散模型计算
            concentration_fields = self._run_diffusion_simulation(
                duration_hours, time_step_minutes, scenario_type
            )
            result.concentration_fields = concentration_fields

            # 计算统计信息
            if concentration_fields:
                result.max_ground_level = max(
                    cf.max_concentration for cf in concentration_fields
                )

            # 评估受体影响
            result.receptor_impacts = self._evaluate_receptor_impacts(concentration_fields)

            # 检测超标区域
            result.exceedance_areas = self._detect_exceedance_areas(concentration_fields)

            result.status = SimulationStatus.COMPLETED
            result.end_time = datetime.now()
            result.duration_seconds = (result.end_time - result.start_time).total_seconds()

            self._current_simulation = result

            logger.info(f"仿真完成: {simulation_id}, 最大地面浓度: {result.max_ground_level:.2f}")

        except Exception as e:
            result.status = SimulationStatus.ERROR
            result.parameters["error"] = str(e)
            logger.error(f"仿真失败: {e}")

        return result

    def _run_diffusion_simulation(self, duration_hours: float,
                                 time_step_minutes: float,
                                 scenario_type: ScenarioType) -> List[ConcentrationField]:
        """
        运行扩散仿真（高斯羽流模型）

        实际实现应使用专业的大气扩散模型（如AERMOD、CALPUFF）
        这里实现简化的梯度风模型
        """
        fields = []

        if not self.weather_condition:
            # 使用默认气象条件
            self.weather_condition = WeatherCondition(
                wind_speed=3.0,
                wind_direction=90,
                temperature=25.0,
                humidity=60.0,
                atmospheric_stability="D",
                mixing_height=800.0
            )

        weather = self.weather_condition

        # 网格参数
        grid_resolution = 50.0  # 50m
        grid_extent = (-1000, 1000, -1000, 1000)  # 2km x 2km

        # 计算时间步数
        n_steps = int(duration_hours * 60 / time_step_minutes)

        for step in range(n_steps):
            current_time = datetime.now() + timedelta(minutes=step * time_step_minutes)

            # 初始化浓度矩阵
            n_x = int((grid_extent[1] - grid_extent[0]) / grid_resolution)
            n_y = int((grid_extent[3] - grid_extent[2]) / grid_resolution)
            concentrations = [[0.0] * n_x for _ in range(n_y)]

            max_conc = 0.0
            max_loc = SpatialPoint(0, 0, 0)

            # 对每个排放源计算贡献
            for source in self.emission_sources.values():
                # 根据情景调整排放速率
                emission_rate = self._adjust_emission_for_scenario(
                    source.emission_rate, scenario_type, source.source_id
                )

                # 高斯羽流模型
                source_conc = self._gaussian_plume(
                    source=source,
                    weather=weather,
                    grid_resolution=grid_resolution,
                    grid_extent=grid_extent,
                    time_step=time_step_minutes
                )

                # 叠加浓度
                for i in range(n_y):
                    for j in range(n_x):
                        concentrations[i][j] += source_conc[i][j]
                        if concentrations[i][j] > max_conc:
                            max_conc = concentrations[i][j]
                            max_loc = SpatialPoint(
                                grid_extent[0] + j * grid_resolution,
                                grid_extent[2] + i * grid_resolution,
                                0
                            )

            # 创建浓度场
            field = ConcentrationField(
                field_id=f"field_{step}",
                timestamp=current_time,
                grid_resolution=grid_resolution,
                grid_extent=grid_extent,
                concentrations=concentrations,
                max_concentration=max_conc,
                max_location=max_loc,
                affected_receptors=[]
            )

            fields.append(field)

        return fields

    def _gaussian_plume(self, source: EmissionSource, weather: WeatherCondition,
                       grid_resolution: float, grid_extent: Tuple[float, float, float, float],
                       time_step: float) -> List[List[float]]:
        """
        高斯羽流模型

        简化版，实际应使用AERMOD等专业模型
        """
        n_x = int((grid_extent[1] - grid_extent[0]) / grid_resolution)
        n_y = int((grid_extent[3] - grid_extent[2]) / grid_resolution)

        concentrations = [[0.0] * n_x for _ in range(n_y)]

        # 大气稳定度对应的扩散参数
        stability_params = {
            "A": (0.1, 0.1),
            "B": (0.15, 0.12),
            "C": (0.2, 0.16),
            "D": (0.25, 0.21),
            "E": (0.3, 0.25),
            "F": (0.4, 0.3)
        }
        sigma_y, sigma_z = stability_params.get(weather.atmospheric_stability, (0.25, 0.21))

        # 有效高度
        effective_height = source.stack_height + 0.5 * source.exit_velocity * math.sqrt(
            source.stack_height / max(weather.wind_speed, 0.1)
        ) if source.stack_height > 0 else 2.0

        # 风向下
        wind_rad = math.radians(weather.wind_direction)
        wind_dx = math.cos(wind_rad)
        wind_dy = math.sin(wind_rad)

        # 计算每个网格点的浓度
        for i in range(n_y):
            for j in range(n_x):
                # 网格中心坐标
                x = grid_extent[0] + j * grid_resolution
                y = grid_extent[2] + i * grid_resolution

                # 到源的距离（顺风方向）
                downwind = x * wind_dx + y * wind_dy

                if downwind < 0:
                    continue

                # 垂直于风向距离
                crosswind = abs(x * wind_dy - y * wind_dx)

                # 下风向距离太近
                if downwind < 1.0:
                    continue

                # 高斯公式
                sigma_y_val = sigma_y * downwind * (1 + 0.001 * downwind) ** 0.5
                sigma_z_val = sigma_z * downwind * (1 + 0.001 * downwind) ** 0.5

                # 浓度计算
                emission_kg_h = source.emission_rate * (time_step / 60.0)

                conc = (emission_kg_h / (2 * math.pi * sigma_y_val * sigma_z_val * weather.wind_speed)) * \
                       math.exp(-0.5 * (crosswind / sigma_y_val) ** 2) * \
                       (math.exp(-0.5 * ((effective_height - 0) / sigma_z_val) ** 2) +
                        math.exp(-0.5 * ((effective_height + 0) / sigma_z_val) ** 2))

                # 转换为 μg/m³ (假设排放物均匀分布在1m³中)
                concentrations[i][j] = conc * 1e9  # kg -> μg

        return concentrations

    def _adjust_emission_for_scenario(self, base_rate: float,
                                     scenario_type: ScenarioType,
                                     source_id: str) -> float:
        """根据情景调整排放速率"""
        scenario_factors = {
            ScenarioType.NORMAL: 1.0,
            ScenarioType.FULL_LOAD: 1.2,
            ScenarioType.EQUIPMENT_FAILURE: 2.5,  # 处理设施故障，排放增加
            ScenarioType.MAINTENANCE: 0.5,
            ScenarioType.EXTREME_WEATHER: 1.1,
            ScenarioType.EMERGENCY: 3.0,
            ScenarioType.CUSTOM: 1.0
        }
        return base_rate * scenario_factors.get(scenario_type, 1.0)

    def _evaluate_receptor_impacts(self,
                                   concentration_fields: List[ConcentrationField]) -> List[Dict]:
        """评估受体影响"""
        impacts = []

        if not concentration_fields or not self.receptors:
            return impacts

        # 使用最终时间点的浓度场
        final_field = concentration_fields[-1]

        for receptor in self.receptors.values():
            # 计算受体位置的浓度
            conc = self._get_concentration_at_location(
                final_field, receptor.location
            )

            # 计算健康风险
            risk = self._calculate_health_risk(
                conc, receptor.receptor_type, receptor.sensitivity
            )

            impacts.append({
                "receptor_id": receptor.receptor_id,
                "receptor_name": receptor.name,
                "receptor_type": receptor.receptor_type,
                "concentration": conc,
                "unit": final_field.unit,
                "risk_level": risk["level"],
                "risk_score": risk["score"],
                "recommendations": risk["recommendations"]
            })

        return impacts

    def _get_concentration_at_location(self, field: ConcentrationField,
                                      location: SpatialPoint) -> float:
        """获取某位置的浓度"""
        grid_extent = field.grid_extent
        resolution = field.grid_resolution

        # 计算网格索引
        j = int((location.x - grid_extent[0]) / resolution)
        i = int((location.y - grid_extent[2]) / resolution)

        if 0 <= i < len(field.concentrations) and 0 <= j < len(field.concentrations[0]):
            return field.concentrations[i][j]
        return 0.0

    def _calculate_health_risk(self, concentration: float,
                              receptor_type: str, sensitivity: str) -> Dict:
        """计算健康风险"""
        # 标准限值 (μg/m³)
        standards = {
            "residential": {"VOCs": 200, "SO2": 150, "PM2.5": 75, "NO2": 80},
            "school": {"VOCs": 100, "SO2": 50, "PM2.5": 35, "NO2": 40},
            "hospital": {"VOCs": 100, "SO2": 50, "PM2.5": 35, "NO2": 40},
            "industry": {"VOCs": 300, "SO2": 200, "PM2.5": 150, "NO2": 100}
        }

        std = standards.get(receptor_type, standards["residential"])["VOCs"]  # 简化用VOCs
        ratio = concentration / std

        if ratio < 0.5:
            level, score, recommendations = "low", ratio, ["无需措施"]
        elif ratio < 1.0:
            level, score, recommendations = "medium", ratio, ["加强监测", "关注敏感人群"]
        elif ratio < 2.0:
            level, score, recommendations = "high", ratio, ["减少排放", "健康提示"]
        else:
            level, score, recommendations = "critical", ratio, ["立即减排", "健康预警", "应急响应"]

        if sensitivity == "high":
            score *= 1.2

        return {
            "level": level,
            "score": min(score, 2.0),
            "recommendations": recommendations
        }

    def _detect_exceedance_areas(self,
                               concentration_fields: List[ConcentrationField]) -> List[Dict]:
        """检测超标区域"""
        exceedance_areas = []

        if not concentration_fields:
            return exceedance_areas

        # 标准限值 (μg/m³)
        standard_limit = 200.0  # VOCs日均浓度

        final_field = concentration_fields[-1]

        # 找出超标区域
        grid_extent = final_field.grid_extent
        resolution = final_field.grid_resolution

        for i in range(len(final_field.concentrations)):
            for j in range(len(final_field.concentrations[0])):
                conc = final_field.concentrations[i][j]
                if conc > standard_limit:
                    x = grid_extent[0] + j * resolution
                    y = grid_extent[2] + i * resolution
                    exceedance_areas.append({
                        "location": {"x": x, "y": y},
                        "concentration": conc,
                        "exceedance_ratio": conc / standard_limit
                    })

        return exceedance_areas

    def create_whatif_scenario(self, name: str,
                             modifications: List[Dict]) -> WhatIfScenario:
        """
        创建What-If情景

        Args:
            name: 情景名称
            modifications: 修改列表
                - type: replace_equipment/add_equipment/remove_equipment
                - target: 目标设备ID
                - new: 新设备配置（如果是replace）

        Returns:
            What-If情景对象
        """
        scenario_id = f"whatif_{name}_{int(datetime.now().timestamp())}"

        scenario = WhatIfScenario(
            scenario_id=scenario_id,
            name=name,
            description=self._generate_description(modifications),
            modifications=modifications
        )

        return scenario

    def _generate_description(self, modifications: List[Dict]) -> str:
        """生成情景描述"""
        descriptions = []
        for mod in modifications:
            mod_type = mod.get("type", "")
            target = mod.get("target", "")

            if mod_type == "replace_equipment":
                new = mod.get("new", "")
                descriptions.append(f"将{target}替换为{new}")
            elif mod_type == "add_equipment":
                equipment = mod.get("equipment", "")
                descriptions.append(f"新增{equipment}")
            elif mod_type == "reduce_output":
                rate = mod.get("rate", 0)
                descriptions.append(f"降低产能{rate}%")

        return "; ".join(descriptions)

    def evaluate_scenario(self, scenario: WhatIfScenario) -> Dict:
        """
        评估What-If情景

        Args:
            scenario: What-If情景

        Returns:
            评估报告
        """
        # 模拟修改后的仿真
        original_sources = self.emission_sources.copy()

        try:
            # 应用修改
            self._apply_modifications(scenario.modifications)

            # 运行仿真
            result = self.simulate(
                duration_hours=24,
                scenario_type=ScenarioType.CUSTOM
            )

            # 计算减排效果
            if self._current_simulation:
                original_max = self._current_simulation.max_ground_level if self._current_simulation else 0
                new_max = result.max_ground_level
                emission_reduction = (original_max - new_max) / max(original_max, 0.001) * 100
                scenario.expected_emission_reduction = emission_reduction

            # 估算成本和收益
            cost_benefit = self._estimate_cost_benefit(scenario)
            scenario.expected_cost = cost_benefit["cost"]
            scenario.expected_benefit = cost_benefit["benefit"]
            scenario.payback_period = cost_benefit["payback_years"]

            # 计算可行性评分
            scenario.feasibility_score = self._calculate_feasibility(scenario)

            # 风险评估
            scenario.risk_level = self._assess_risk(scenario)

            # 生成建议
            scenario.recommendations = self._generate_recommendations(scenario)

        finally:
            # 恢复原始配置
            self.emission_sources = original_sources

        return {
            "scenario_id": scenario.scenario_id,
            "name": scenario.name,
            "emission_reduction_percent": scenario.expected_emission_reduction,
            "estimated_cost": scenario.expected_cost,
            "estimated_benefit": scenario.expected_benefit,
            "payback_years": scenario.payback_period,
            "feasibility_score": scenario.feasibility_score,
            "risk_level": scenario.risk_level,
            "recommendations": scenario.recommendations,
            "simulation_result": result if 'result' in dir() else None
        }

    def _apply_modifications(self, modifications: List[Dict]):
        """应用修改到孪生体"""
        for mod in modifications:
            mod_type = mod.get("type", "")

            if mod_type == "replace_equipment":
                # 替换设备
                old_id = mod.get("target", "")
                new_config = mod.get("new", {})
                if old_id in self.emission_sources:
                    old_source = self.emission_sources[old_id]
                    # 假设新设备效率更高，排放更低
                    old_source.emission_rate *= 0.5  # 简化：假设减排50%

            elif mod_type == "add_equipment":
                # 添加设备（如RCO）
                equipment = mod.get("equipment", "")
                capacity = mod.get("capacity", 5000)
                # 添加新的处理设施节点
                pass

            elif mod_type == "reduce_output":
                rate = mod.get("rate", 0)
                for source in self.emission_sources.values():
                    source.emission_rate *= (1 - rate / 100)

    def _estimate_cost_benefit(self, scenario: WhatIfScenario) -> Dict:
        """估算成本收益"""
        # 简化估算模型
        base_cost = 1000000  # 基础投资100万
        annual_benefit = 200000  # 年节约成本20万

        # 根据情景调整
        if "干式" in scenario.name or "dry" in scenario.name.lower():
            base_cost = 2000000
            annual_benefit = 450000
        elif "RCO" in scenario.name:
            base_cost = 3000000
            annual_benefit = 600000
        elif "RTO" in scenario.name:
            base_cost = 5000000
            annual_benefit = 900000

        # 减排效益（碳配额等）
        emission_value = scenario.expected_emission_reduction * 10000  # 每吨减排价值

        total_benefit = annual_benefit + emission_value
        payback_years = base_cost / max(total_benefit, 1)

        return {
            "cost": base_cost,
            "benefit": total_benefit,
            "payback_years": payback_years
        }

    def _calculate_feasibility(self, scenario: WhatIfScenario) -> float:
        """计算可行性评分"""
        score = 0.5  # 基础分

        # 减排效果好加分
        if scenario.expected_emission_reduction > 30:
            score += 0.2
        elif scenario.expected_emission_reduction > 50:
            score += 0.3

        # 回收期短加分
        if scenario.payback_period < 3:
            score += 0.2
        elif scenario.payback_period < 5:
            score += 0.1

        # 风险低加分
        if scenario.risk_level == "low":
            score += 0.1
        elif scenario.risk_level == "high":
            score -= 0.2

        return min(max(score, 0), 1)

    def _assess_risk(self, scenario: WhatIfScenario) -> str:
        """评估风险"""
        risks = []

        # 检查是否有设备故障风险
        for mod in scenario.modifications:
            if mod.get("type") == "replace_equipment":
                risks.append("技术风险：新设备稳定性待验证")

        # 检查成本风险
        if scenario.expected_cost > 5000000:
            risks.append("财务风险：投资较大")

        # 检查合规风险
        if scenario.expected_emission_reduction < 20:
            risks.append("合规风险：可能不满足新标准要求")

        if len(risks) >= 3:
            return "high"
        elif len(risks) >= 1:
            return "medium"
        else:
            return "low"

    def _generate_recommendations(self, scenario: WhatIfScenario) -> List[str]:
        """生成建议"""
        recommendations = []

        if scenario.feasibility_score > 0.7:
            recommendations.append("✅ 建议实施：该方案可行性较高")

        if scenario.expected_emission_reduction > 30:
            recommendations.append("🌿 环保效益显著：预计可减排{:.0f}%".format(
                scenario.expected_emission_reduction))

        if scenario.payback_period < 5:
            recommendations.append("💰 经济可行：投资回收期约{:.1f}年".format(
                scenario.payback_period))

        if scenario.risk_level == "medium":
            recommendations.append("⚠️ 注意风险：建议先进行小规模试验")

        if scenario.risk_level == "high":
            recommendations.append("🚨 高风险：建议重新评估方案")

        # 合规建议
        recommendations.append("📋 后续步骤：编制《工艺改造可行性研究报告》")

        return recommendations

    def get_optimization_suggestions(self) -> List[Dict]:
        """
        获取基于图谱的智能优化建议

        Returns:
            优化建议列表
        """
        suggestions = []

        # 从知识图谱获取行业最佳参数
        # 这里使用模拟数据，实际应连接知识图谱
        industry_best_practices = {
            "喷漆": {
                "固化温度": {"best": 75, "current": 80, "saving": "8%节能"},
                "喷涂速率": {"best": 0.8, "current": 1.0, "unit": "m/s"}
            },
            "焊接": {
                "烟尘处理效率": {"best": 95, "current": 85, "unit": "%"}
            }
        }

        # 分析每个排放源
        for source in self.emission_sources.values():
            process_name = source.name

            if process_name in industry_best_practices:
                practices = industry_best_practices[process_name]

                for param, data in practices.items():
                    if isinstance(data, dict) and "best" in data:
                        current = data.get("current", 0)
                        best = data["best"]

                        if current != best:
                            suggestions.append({
                                "source_id": source.source_id,
                                "source_name": source.name,
                                "parameter": param,
                                "current_value": current,
                                "recommended_value": best,
                                "potential_benefit": data.get("saving", f"可优化至{best}"),
                                "category": "process_optimization"
                            })

        return suggestions

    def _calculate_distance(self, loc1: SpatialPoint, loc2: SpatialPoint) -> float:
        """计算两点距离"""
        return math.sqrt(
            (loc1.x - loc2.x) ** 2 +
            (loc1.y - loc2.y) ** 2 +
            (loc1.z - loc2.z) ** 2
        )

    def export_simulation_result(self, result: SimulationResult,
                                format: str = "json") -> str:
        """导出仿真结果"""
        if format == "json":
            return json.dumps({
                "simulation_id": result.simulation_id,
                "scenario_name": result.scenario_name,
                "status": result.status.value,
                "duration_seconds": result.duration_seconds,
                "max_ground_level": result.max_ground_level,
                "exceedance_count": len(result.exceedance_areas),
                "receptor_impacts": result.receptor_impacts,
                "parameters": result.parameters
            }, ensure_ascii=False, indent=2)
        elif format == "csv":
            lines = ["receptor,concentration,unit,risk_level,recommendations"]
            for impact in result.receptor_impacts:
                lines.append(
                    f"{impact['receptor_name']},{impact['concentration']},"
                    f"{impact['unit']},{impact['risk_level']},"
                    f"{';'.join(impact['recommendations'])}"
                )
            return "\n".join(lines)
        return ""

    def to_dict(self) -> Dict[str, Any]:
        """导出配置"""
        return {
            "project_id": self.project_id,
            "project_name": self.project_name,
            "emission_sources": {
                sid: {
                    "name": s.name,
                    "location": {"x": s.location.x, "y": s.location.y},
                    "emission_rate": s.emission_rate,
                    "pollutant": s.pollutant
                }
                for sid, s in self.emission_sources.items()
            },
            "receptors_count": len(self.receptors),
            "weather": {
                "wind_speed": self.weather_condition.wind_speed if self.weather_condition else None,
                "wind_direction": self.weather_condition.wind_direction if self.weather_condition else None
            }
        }


# ============================================================
# 数字孪生体工厂
# ============================================================

class DigitalTwinFactory:
    """
    数字孪生体工厂

    管理所有项目的数字孪生体实例
    """

    def __init__(self):
        self._twins: Dict[str, ProcessDigitalTwin] = {}
        self._lock = threading.RLock()

    def create_twin(self, project_id: str, project_name: str = "") -> ProcessDigitalTwin:
        """创建数字孪生体"""
        with self._lock:
            if project_id in self._twins:
                return self._twins[project_id]

            twin = ProcessDigitalTwin(project_id, project_name)
            self._twins[project_id] = twin
            return twin

    def get_twin(self, project_id: str) -> Optional[ProcessDigitalTwin]:
        """获取数字孪生体"""
        return self._twins.get(project_id)

    def delete_twin(self, project_id: str) -> bool:
        """删除数字孪生体"""
        with self._lock:
            if project_id in self._twins:
                del self._twins[project_id]
                return True
            return False

    def list_twins(self) -> List[Dict]:
        """列出所有数字孪生体"""
        return [
            {"project_id": pid, "project_name": t.project_name}
            for pid, t in self._twins.items()
        ]


# 全局工厂实例
_twin_factory: Optional[DigitalTwinFactory] = None
_twin_factory_lock = threading.Lock()


def get_twin_factory() -> DigitalTwinFactory:
    """获取数字孪生体工厂"""
    global _twin_factory
    if _twin_factory is None:
        with _twin_factory_lock:
            if _twin_factory is None:
                _twin_factory = DigitalTwinFactory()
    return _twin_factory


def create_digital_twin(project_id: str, project_name: str = "") -> ProcessDigitalTwin:
    """创建数字孪生体的便捷函数"""
    return get_twin_factory().create_twin(project_id, project_name)
