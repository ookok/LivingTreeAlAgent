"""
模型计算引擎 (Model Calculation Engine)
=======================================

核心理念：
- AI 负责"编造数据" → AI 负责"解释数据"
- 计算结果由内置模型产生，而非 AI 幻觉
- 所有计算可复现、可追溯

计算闭环：
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  绘图/输入   │ → │  模型计算    │ → │  原始结果    │
│  参数        │    │  引擎        │    │  数据        │
└─────────────┘    └─────────────┘    └──────┬──────┘
                                              │
                                              ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  最终报告    │ ←  │  AI 仅负责   │ ←  │  报告生成器  │
│             │    │  文字描述    │    │             │
└─────────────┘    └─────────────┘    └─────────────┘
"""

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional


class ModelType(Enum):
    """模型类型"""
    # 大气扩散模型
    AERMOD_SIMPLIFIED = "aermod_simplified"  # 简化高斯模型
    AERMOD_FULL = "aermod_full"              # 完整AERMOD
    CALPUFF = "calpuff"                      # CALPUFF

    # 水质模型
    QUAL2K = "qual2k"                        # QUAL2K
    MIKE = "mike"                           # MIKE系列

    # 噪声模型
    NOISE_CALCULATION = "noise_calculation"  # 工业噪声计算
    NOISE_MAPPING = "noise_mapping"          # 噪声地图

    # 风险模型
    ALOHA_LIKE = "aloha_like"               # 风险事故扩散

    # 其他
    GAUSSIAN_PLUME = "gaussian_plume"        # 通用高斯烟羽


class ComputationStatus(Enum):
    """计算状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ParameterSource(Enum):
    """参数来源"""
    DRAWING_EXTRACTED = "drawing_extracted"   # 从绘图提取
    MANUAL_INPUT = "manual_input"           # 手动输入
    DEFAULT_VALUE = "default_value"          # 默认值
    DATABASE_LOOKUP = "database_lookup"      # 数据库查找
    CALCULATED = "calculated"               # 计算得出


@dataclass
class ModelParameter:
    """模型参数"""
    name: str
    value: Any
    unit: str = ""
    source: ParameterSource = ParameterSource.MANUAL_INPUT

    # 元数据
    description: str = ""
    valid_range: tuple = None              # (min, max)
    required: bool = True
    sensitivity: float = 1.0               # 敏感性系数


@dataclass
class ComputationInput:
    """计算输入"""
    model_type: ModelType
    project_id: str

    # 参数
    parameters: dict[str, ModelParameter] = field(default_factory=dict)

    # 地理数据
    sources: list = field(default_factory=list)       # 污染源
    receptors: list = field(default_factory=list)     # 关心点
    terrain: dict = field(default_factory=dict)        # 地形数据

    # 气象数据
    meteorology: dict = field(default_factory=dict)   # 气象条件

    # 环境参数
    environment: dict = field(default_factory=dict)   # 环境背景值

    # 元数据
    created_at: datetime = field(default_factory=datetime.now)
    created_by: str = "system"
    version: str = "1.0"


@dataclass
class ComputationResult:
    """计算结果"""
    model_type: ModelType
    status: ComputationStatus

    # 结果数据
    raw_output: Any = None                  # 原始输出
    processed_output: dict = field(default_factory=dict)  # 处理后的结果

    # 预测值
    predictions: list = field(default_factory=list)  # 预测结果列表

    # 统计
    max_concentration: float = 0.0
    max_concentration_location: str = ""
    max_concentration_x: float = 0.0
    max_concentration_y: float = 0.0

    # 占标率
    max_ratio: float = 0.0                 # 最大占标率
    standards: dict = field(default_factory=dict)  # 标准限值

    # 执行信息
    execution_time: float = 0.0            # 计算耗时（秒）
    computed_at: datetime = None
    node_id: str = ""                      # 计算节点ID

    # 指纹
    fingerprint: str = ""                  # 计算指纹

    # 错误信息
    error_message: str = ""
    warning_messages: list = field(default_factory=list)


@dataclass
class ComputationPackage:
    """计算包（用于复现和审计）"""
    package_id: str
    input: ComputationInput
    result: ComputationResult

    # 版本信息
    model_version: str = "1.0"
    engine_version: str = "1.0"

    # 哈希链
    input_hash: str = ""                   # 输入哈希
    parameter_hash: str = ""               # 参数哈希
    output_hash: str = ""                  # 输出哈希
    package_hash: str = ""                 # 整个包的哈希

    # 时间戳
    created_at: datetime = field(default_factory=datetime.now)

    def verify(self) -> bool:
        """验证计算包完整性"""
        # 重新计算哈希
        expected_input_hash = self._compute_hash(self.input)
        expected_output_hash = self._compute_hash(self.result.raw_output)

        return (
            expected_input_hash == self.input_hash and
            expected_output_hash == self.output_hash
        )

    def _compute_hash(self, obj) -> str:
        """计算对象哈希"""
        serialized = json.dumps(obj, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()[:16]


class ModelCalculationEngine:
    """
    模型计算引擎

    核心理念：
    - 所有计算由内置模型产生
    - 计算结果可复现、可追溯
    - AI 只负责"解释"数据，不负责"编造"数据

    用法:
        engine = ModelCalculationEngine()

        # 创建计算输入
        inp = ComputationInput(
            model_type=ModelType.GAUSSIAN_PLUME,
            project_id="proj_001"
        )
        inp.parameters["emission_rate"] = ModelParameter(
            name="emission_rate", value=0.5, unit="g/s"
        )
        inp.sources.append({"name": "烟囱1", "x": 0, "y": 0, "height": 15})

        # 执行计算
        result = await engine.calculate(inp)

        # 获取计算包（用于复现）
        package = engine.create_package(inp, result)
    """

    def __init__(self, data_dir: str = "./data/eia/models"):
        self.data_dir = data_dir
        self._models: dict[ModelType, Callable] = {}
        self._register_builtin_models()

    def _register_builtin_models(self) -> None:
        """注册内置模型"""
        self._models[ModelType.GAUSSIAN_PLUME] = self._gaussian_plume
        self._models[ModelType.AERMOD_SIMPLIFIED] = self._aermod_simplified
        self._models[ModelType.NOISE_CALCULATION] = self._noise_calculation
        self._models[ModelType.GAUSSIAN_PLUME] = self._gaussian_plume

    async def calculate(self, input_data: ComputationInput) -> ComputationResult:
        """
        执行模型计算

        Args:
            input_data: 计算输入

        Returns:
            ComputationResult: 计算结果
        """
        result = ComputationResult(
            model_type=input_data.model_type,
            status=ComputationStatus.RUNNING,
            computed_at=datetime.now()
        )

        start_time = datetime.now()

        try:
            # 获取模型
            model = self._models.get(input_data.model_type)
            if not model:
                raise ValueError(f"未知的模型类型: {input_data.model_type}")

            # 执行计算
            raw_output = await model(input_data)

            # 处理结果
            result.raw_output = raw_output
            result.processed_output = self._process_output(raw_output)
            result.predictions = self._extract_predictions(raw_output)
            result.status = Com Com
            result.execution_time = (datetime.now() - start_time).total_seconds()

            # 计算指纹
            result.fingerprint = self._compute_fingerprint(input_data, result)

        except Exception as e:
            result.status = ComputationStatus.FAILED
            result.error_message = str(e)
            result.execution_time = (datetime.now() - start_time).total_seconds()

        return result

    def _gaussian_plume(self, input_data: ComputationInput) -> dict:
        """
        简化高斯烟羽模型

        公式：
        C = (Q / (2π·σy·σz·u)) · exp(-y²/2σy²) · exp(-z²/2σz²)

        Args:
            input_data: 计算输入

        Returns:
            dict: 原始计算结果
        """
        import math

        # 提取参数
        emission_rate = input_data.parameters.get("emission_rate", ModelParameter(value=0.0)).value
        wind_speed = input_data.parameters.get("wind_speed", ModelParameter(value=2.0)).value
        stack_height = input_data.parameters.get("stack_height", ModelParameter(value=15.0)).value
        stability = input_data.parameters.get("stability", ModelParameter(value="D")).value

        # 扩散参数（根据稳定度）
        sigma_y, sigma_z = self._get_dispersion_params(stability)

        results = []

        # 对每个源计算
        for source in input_data.sources:
            x0 = source.get("x", 0)
            y0 = source.get("y", 0)
            height = source.get("height", stack_height)

            # 预测点网格
            for x in range(0, 5001, 100):  # 0-5000m
                for y in range(-500, 501, 100):  # -500到500m
                    # 距离
                    d = math.sqrt((x - x0)**2 + y**2)
                    if d < 1:
                        continue

                    # 扩散
                    sy = sigma_y * d / 100
                    sz = sigma_z * d / 100

                    if sy < 0.1 or sz < 0.1:
                        continue

                    # 高斯公式
                    u = wind_speed  # 简化假设
                    coefficient = emission_rate / (2 * math.pi * sy * sz * u)

                    # z方向（考虑地面反射）
                    z = 1.5  # 呼吸带高度
                    c_z = math.exp(-z**2 / (2 * sz**2)) + math.exp(-(2*height + z)**2 / (2 * sz**2))

                    # y方向
                    c_y = math.exp(-y**2 / (2 * sy**2))

                    concentration = coefficient * c_y * c_z

                    if concentration > 0.001:  # 只记录有意义的值
                        results.append({
                            "x": x,
                            "y": y,
                            "concentration": concentration,
                            "source": source.get("name", "unknown")
                        })

        return {
            "model": "gaussian_plume",
            "parameters": {
                "emission_rate": emission_rate,
                "wind_speed": wind_speed,
                "stack_height": stack_height,
                "stability": stability
            },
            "data_points": results
        }

    def _aermod_simplified(self, input_data: ComputationInput) -> dict:
        """
        简化AERMOD模型

        基于HJ 2.2-2018推荐的估算模式
        """
        import math

        # 提取参数
        emission_rate = input_data.parameters.get("emission_rate", ModelParameter(value=0.0)).value
        stack_height = input_data.parameters.get("stack_height", ModelParameter(value=15.0)).value
        stack_diameter = input_data.parameters.get("stack_diameter", ModelParameter(value=0.5)).value
        exit_velocity = input_data.parameters.get("exit_velocity", ModelParameter(value=5.0)).value
        temperature = input_data.parameters.get("temperature", ModelParameter(value=373)).value  # K

        ambient_temp = input_data.parameters.get("ambient_temp", ModelParameter(value=288)).value  # K
        wind_speed = input_data.parameters.get("wind_speed", ModelParameter(value=2.0)).value
        stability = input_data.parameters.get("stability", ModelParameter(value="D")).value

        # 计算烟气抬升
        dt = temperature - ambient_temp
        if dt > 0 and wind_speed > 0:
            # 布里格斯公式
            rise = 0.5 * exit_velocity * stack_diameter / wind_speed
            delta_h = rise * (1 + 0.5 * dt / temperature)
        else:
            delta_h = 0

        effective_height = stack_height + delta_h

        # 扩散参数
        sigma_y, sigma_z = self._get_dispersion_params(stability)

        results = []
        max_conc = 0
        max_loc = (0, 0)

        # 预测网格
        for x in range(10, 5001, 50):
            for y in range(-500, 501, 50):
                sy = sigma_y * x / 100
                sz = sigma_z * x / 100

                if sy < 0.1 or sz < 0.1:
                    continue

                # 有效高度处的浓度
                u = wind_speed
                coefficient = emission_rate / (2 * math.pi * sy * sz * u)

                z = 1.5  # 呼吸带高度
                c_z = (math.exp(-z**2 / (2 * sz**2)) +
                       math.exp(-(2*effective_height + z)**2 / (2 * sz**2)))
                c_y = math.exp(-y**2 / (2 * sy**2))

                concentration = coefficient * c_y * c_z

                if concentration > max_conc:
                    max_conc = concentration
                    max_loc = (x, y)

                if concentration > 0.0001:
                    results.append({
                        "x": x,
                        "y": y,
                        "concentration": concentration,
                        "effective_height": effective_height
                    })

        return {
            "model": "aermod_simplified",
            "parameters": {
                "emission_rate": emission_rate,
                "stack_height": stack_height,
                "effective_height": effective_height,
                "wind_speed": wind_speed,
                "stability": stability
            },
            "max_concentration": max_conc,
            "max_location": max_loc,
            "data_points": results
        }

    def _noise_calculation(self, input_data: ComputationInput) -> dict:
        """
        工业噪声预测计算

        基于GB 12348-2008的噪声衰减公式
        """
        import math

        results = []

        for source in input_data.sources:
            source_name = source.get("name", "unknown")
            source_level = source.get("sound_power", 85)  # dB(A)
            source_x = source.get("x", 0)
            source_y = source.get("y", 0)

            # 对每个关心点计算
            for receptor in input_data.receptors:
                receptor_name = receptor.get("name", "unknown")
                receptor_x = receptor.get("x", 100)
                receptor_y = receptor.get("y", 0)

                # 距离
                distance = math.sqrt((receptor_x - source_x)**2 + (receptor_y - source_y)**2)

                if distance < 1:
                    continue

                # 几何衰减
                geometric_attenuation = 20 * math.log10(distance)

                # 附加衰减（地面效应、空气吸收等）
                additional_attenuation = 0

                # 屏障衰减（如有）
                barrier_attenuation = receptor.get("barrier_attenuation", 0)

                # 预测噪声级
                predicted_level = source_level - geometric_attenuation - additional_attenuation - barrier_attenuation

                results.append({
                    "source": source_name,
                    "receptor": receptor_name,
                    "distance": distance,
                    "source_level": source_level,
                    "predicted_level": max(predicted_level, 0),  # 不低于0
                    "geometric_attenuation": geometric_attenuation,
                    "barrier_attenuation": barrier_attenuation
                })

        return {
            "model": "noise_calculation",
            "results": results
        }

    def _get_dispersion_params(self, stability: str) -> tuple:
        """
        获取扩散参数

        Args:
            stability: 稳定度等级 (A, B, C, D, E, F)

        Returns:
            tuple: (sigma_y, sigma_z) 扩散参数系数
        """
        # 简化取值（GB/T 39499-2020）
        params = {
            "A": (0.22, 0.20),
            "B": (0.16, 0.12),
            "C": (0.11, 0.08),
            "D": (0.08, 0.06),
            "E": (0.06, 0.03),
            "F": (0.04, 0.016),
        }
        return params.get(stability, (0.08, 0.06))  # 默认D

    def _process_output(self, raw_output: dict) -> dict:
        """处理原始输出"""
        processed = {
            "max_concentration": raw_output.get("max_concentration", 0),
            "max_location": raw_output.get("max_location", (0, 0)),
            "model": raw_output.get("model", ""),
            "parameter_summary": raw_output.get("parameters", {})
        }

        # 提取浓度数组（用于绘图）
        data_points = raw_output.get("data_points", [])
        if data_points:
            processed["concentrations"] = [p["concentration"] for p in data_points]
            processed["x_coords"] = [p["x"] for p in data_points]
            processed["y_coords"] = [p["y"] for p in data_points]

        return processed

    def _extract_predictions(self, raw_output: dict) -> list:
        """提取预测结果列表"""
        predictions = []

        # 从关心点提取结果
        data_points = raw_output.get("data_points", [])

        # 按距离分组取最大值
        from collections import defaultdict
        by_distance = defaultdict(list)

        for point in data_points:
            dist = round(point["x"] / 100) * 100  # 按100m分组
            by_distance[dist].append(point["concentration"])

        for dist, concentrations in sorted(by_distance.items()):
            max_c = max(concentrations)
            predictions.append({
                "distance": dist,
                "max_concentration": max_c,
                "std_concentration": sum(concentrations) / len(concentrations)
            })

        return predictions

    def _compute_fingerprint(
        self,
        input_data: ComputationInput,
        result: ComputationResult
    ) -> str:
        """计算计算指纹"""
        data = {
            "model_type": result.model_type.value,
            "parameters": {k: v.value for k, v in input_data.parameters.items()},
            "sources": input_data.sources,
            "raw_output_hash": hashlib.sha256(
                json.dumps(result.raw_output, sort_keys=True, default=str).encode()
            ).hexdigest()[:16],
            "computed_at": result.computed_at.isoformat() if result.computed_at else ""
        }

        fingerprint = hashlib.sha256(
            json.dumps(data, sort_keys=True).encode()
        ).hexdigest()[:16]

        return fingerprint

    def create_package(
        self,
        input_data: ComputationInput,
        result: ComputationResult
    ) -> ComputationPackage:
        """
        创建计算包（用于复现和审计）

        Args:
            input_data: 计算输入
            result: 计算结果

        Returns:
            ComputationPackage: 完整的计算包
        """
        # 计算各部分哈希
        input_json = json.dumps(input_data.parameters, sort_keys=True, default=str)
        parameter_hash = hashlib.sha256(input_json.encode()).hexdigest()[:16]

        output_json = json.dumps(result.raw_output, sort_keys=True, default=str)
        output_hash = hashlib.sha256(output_json.encode()).hexdigest()[:16]

        # 整个包的哈希
        package_data = {
            "parameter_hash": parameter_hash,
            "output_hash": output_hash,
            "model_type": result.model_type.value,
            "computed_at": result.computed_at.isoformat() if result.computed_at else ""
        }
        package_hash = hashlib.sha256(
            json.dumps(package_data, sort_keys=True).encode()
        ).hexdigest()[:16]

        package = ComputationPackage(
            package_id=f"pkg_{package_hash}",
            input=input_data,
            result=result,
            input_hash=parameter_hash,
            output_hash=output_hash,
            package_hash=package_hash
        )

        return package

    async def verify_computation(self, package: ComputationPackage) -> dict:
        """
        验证计算（复现计算）

        Args:
            package: 计算包

        Returns:
            dict: {
                "verified": bool,
                "matches": bool,
                "new_result": ComputationResult,
                "differences": dict
            }
        """
        # 重新执行计算
        new_result = await self.calculate(package.input)

        # 比较结果
        original_output = package.result.raw_output
        new_output = new_result.raw_output

        # 计算相似度
        matches = self._compare_outputs(original_output, new_output)

        return {
            "verified": True,
            "matches": matches,
            "new_result": new_result,
            "differences": self._find_differences(original_output, new_output),
            "original_fingerprint": package.package_hash,
            "new_fingerprint": new_result.fingerprint
        }

    def _compare_outputs(self, output1: dict, output2: dict) -> bool:
        """比较两个输出是否一致"""
        # 简单比较：最大浓度差异 < 1%
        max1 = output1.get("max_concentration", 0)
        max2 = output2.get("max_concentration", 0)

        if max1 == 0 and max2 == 0:
            return True

        diff = abs(max1 - max2) / max(max1, max2)
        return diff < 0.01

    def _find_differences(self, output1: dict, output2: dict) -> dict:
        """找出输出差异"""
        differences = {}

        # 比较最大浓度
        max1 = output1.get("max_concentration", 0)
        max2 = output2.get("max_concentration", 0)

        if abs(max1 - max2) > 0.0001:
            differences["max_concentration"] = {
                "original": max1,
                "new": max2,
                "difference": max2 - max1,
                "relative_diff": (max2 - max1) / max(max1, 0.0001)
            }

        return differences

    def extract_parameters_from_drawing(self, drawing_data: dict) -> dict[str, ModelParameter]:
        """
        从绘图中提取模型参数

        Args:
            drawing_data: 绘图数据

        Returns:
            dict: 模型参数字典
        """
        parameters = {}

        # 从污染源提取
        sources = drawing_data.get("sources", [])
        for i, source in enumerate(sources):
            parameters[f"source_{i}_emission_rate"] = ModelParameter(
                name=f"source_{i}_emission_rate",
                value=source.get("emission_rate", 0),
                unit="g/s",
                source=ParameterSource.DRAWING_EXTRACTED,
                description=f"污染源 {source.get('name', i+1)} 排放速率"
            )

            parameters[f"source_{i}_height"] = ModelParameter(
                name=f"source_{i}_height",
                value=source.get("height", 15),
                unit="m",
                source=ParameterSource.DRAWING_EXTRACTED,
                description=f"污染源 {source.get('name', i+1)} 排气筒高度"
            )

            parameters[f"source_{i}_diameter"] = ModelParameter(
                name=f"source_{i}_diameter",
                value=source.get("diameter", 0.5),
                unit="m",
                source=ParameterSource.DRAWING_EXTRACTED,
                description=f"污染源 {source.get('name', i+1)} 排气筒内径"
            )

            parameters[f"source_{i}_velocity"] = ModelParameter(
                name=f"source_{i}_velocity",
                value=source.get("velocity", 5),
                unit="m/s",
                source=ParameterSource.DRAWING_EXTRACTED,
                description=f"污染源 {source.get('name', i+1)} 出口流速"
            )

        return parameters

    def generate_parameter_summary(self, parameters: dict[str, ModelParameter]) -> str:
        """生成参数摘要（用于报告）"""
        lines = ["### 模型参数\n"]

        for name, param in parameters.items():
            source_icon = {
                ParameterSource.DRAWING_EXTRACTED: "📐",
                ParameterSource.MANUAL_INPUT: "✏️",
                ParameterSource.DEFAULT_VALUE: "📋",
                ParameterSource.CALCULATED: "🧮"
            }.get(param.source, "•")

            lines.append(f"{source_icon} **{param.name}**: {param.value} {param.unit}")

        return "\n".join(lines)


def create_calculation_engine(data_dir: str = "./data/eia/models") -> ModelCalculationEngine:
    """创建模型计算引擎实例"""
    return ModelCalculationEngine(data_dir=data_dir)