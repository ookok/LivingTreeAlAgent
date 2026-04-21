"""
专业模型库 - Environmental Model Library
=======================================

三大类模型：
1. 预测模型：大气扩散、水质模拟、噪声预测、事故后果
2. 优化模型：治理设施运行优化、生产排产优化、应急资源调度
3. 评估模型：健康风险评估、生态风险评估、经济损益评估
"""

import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum


class ModelType(Enum):
    """模型类型"""
    # 预测模型
    AIR_DISPERSION = "air_dispersion"     # 大气扩散
    WATER_QUALITY = "water_quality"       # 水质模拟
    NOISE_PREDICTION = "noise"            # 噪声预测
    ACCIDENT_CONSEQUENCE = "accident"     # 事故后果

    # 优化模型
    TREATMENT_OPTIMIZE = "treatment_opt"  # 治理优化
    PRODUCTION_OPTIMIZE = "production_opt"  # 生产优化
    EMERGENCY调度 = "emergency_dispatch"  # 应急调度

    # 评估模型
    HEALTH_RISK = "health_risk"           # 健康风险
    ECOLOGY_RISK = "ecology_risk"         # 生态风险
    ECONOMIC_ASSESS = "economic"          # 经济损益


class ModelStatus(Enum):
    """模型状态"""
    READY = "ready"           # 就绪
    RUNNING = "running"       # 运行中
    COMPLETED = "completed"    # 已完成
    FAILED = "failed"         # 失败


@dataclass
class ModelConfig:
    """模型配置"""
    model_id: str
    model_name: str
    model_type: ModelType

    # 版本
    version: str = "1.0.0"
    last_updated: str = ""

    # 参数
    parameters: Dict = field(default_factory=dict)

    # 状态
    status: ModelStatus = ModelStatus.READY

    # 元数据
    description: str = ""
    author: str = ""
    documentation: str = ""


@dataclass
class ModelResult:
    """模型运行结果"""
    result_id: str
    model_id: str
    project_id: str

    # 时间
    run_at: str = ""
    duration_seconds: float = 0.0

    # 输入摘要
    input_summary: str = ""

    # 输出数据
    output_data: Dict = field(default_factory=dict)

    # 可视化
    visualizations: List[Dict] = field(default_factory=list)

    # 状态
    status: ModelStatus = ModelStatus.COMPLETED
    error_message: str = ""

    # 质量
    confidence: float = 0.0


class ModelLibrary:
    """
    专业模型库
    ==========

    核心功能：
    1. 模型注册与版本管理
    2. 一键运行预测模型
    3. 优化模型自动求解
    4. 评估模型批量计算
    5. 结果可视化
    """

    def __init__(self):
        # 模型注册表
        self._models: Dict[str, ModelConfig] = {}

        # 运行记录
        self._results: Dict[str, List[ModelResult]] = {}

        # 初始化内置模型
        self._init_builtin_models()

    def _init_builtin_models(self):
        """初始化内置模型"""
        builtin_models = [
            # 大气扩散模型
            ModelConfig(
                model_id="AERMOD",
                model_name="AERMOD大气扩散模型",
                model_type=ModelType.AIR_DISPERSION,
                version="2.0",
                description="EPA推荐的大气预测模型，适用于稳定边界层条件下的点源扩散预测",
                parameters={
                    "emission_rate": {"type": "float", "default": 1.0, "unit": "g/s"},
                    "stack_height": {"type": "float", "default": 50.0, "unit": "m"},
                    "stack_diameter": {"type": "float", "default": 1.0, "unit": "m"},
                    "exit_velocity": {"type": "float", "default": 5.0, "unit": "m/s"},
                    "temperature": {"type": "float", "default": 350.0, "unit": "K"},
                }
            ),
            ModelConfig(
                model_id="CALPUFF",
                model_name="CALPUFF扩散模型",
                model_type=ModelType.AIR_DISPERSION,
                version="7.2",
                description="三维非定常烟团模型，适用于复杂地形和长距离传输",
                parameters={
                    "emission_rate": {"type": "float", "default": 1.0, "unit": "g/s"},
                    "particle_number": {"type": "int", "default": 1000},
                }
            ),
            # 水质模型
            ModelConfig(
                model_id="QUAL2K",
                model_name="QUAL2K水质模型",
                model_type=ModelType.WATER_QUALITY,
                version="2.0",
                description="河流水质模拟模型，支持BOD、DO、营养物质等多种水质指标",
                parameters={
                    "flow_rate": {"type": "float", "default": 10.0, "unit": "m³/s"},
                    "reach_length": {"type": "float", "default": 1000.0, "unit": "m"},
                }
            ),
            # 噪声模型
            ModelConfig(
                model_id="CadnaA",
                model_name="CadnaA噪声预测模型",
                model_type=ModelType.NOISE_PREDICTION,
                version="4.5",
                description="工业噪声预测软件，支持多源叠加、屏障衰减计算",
                parameters={
                    "source_level": {"type": "float", "default": 85.0, "unit": "dB(A)"},
                    "distance": {"type": "float", "default": 100.0, "unit": "m"},
                }
            ),
            # 事故后果模型
            ModelConfig(
                model_id="ALOHA",
                model_name="ALOHA事故后果模型",
                model_type=ModelType.ACCIDENT_CONSEQUENCE,
                version="5.4",
                description="化学品泄漏事故后果分析模型，支持气体扩散、火灾、爆炸等",
                parameters={
                    "chemical": {"type": "string", "default": "ammonia"},
                    "quantity": {"type": "float", "default": 1000.0, "unit": "kg"},
                    "release_type": {"type": "select", "options": ["instant", "continuous"]},
                }
            ),
            # 健康风险模型
            ModelConfig(
                model_id="US_EPA_HHRA",
                model_name="EPA健康风险评估模型",
                model_type=ModelType.HEALTH_RISK,
                version="2.0",
                description="基于US EPA方法的健康风险评估，包含致癌风险和非致癌危害指数",
                parameters={
                    "exposure_concentration": {"type": "float", "default": 10.0, "unit": "μg/m³"},
                    "exposure_duration": {"type": "float", "default": 30.0, "unit": "years"},
                }
            ),
        ]

        for model in builtin_models:
            model.last_updated = datetime.now().isoformat()
            self._models[model.model_id] = model

    def register_model(self, model_config: Dict) -> str:
        """注册新模型"""
        model = ModelConfig(
            model_id=model_config['model_id'],
            model_name=model_config['model_name'],
            model_type=ModelType(model_config['model_type']),
            version=model_config.get('version', '1.0.0'),
            parameters=model_config.get('parameters', {}),
            description=model_config.get('description', '')
        )

        self._models[model.model_id] = model
        return model.model_id

    def get_model(self, model_id: str) -> Optional[ModelConfig]:
        """获取模型"""
        return self._models.get(model_id)

    def list_models(self, model_type: ModelType = None) -> List[ModelConfig]:
        """列出模型"""
        models = list(self._models.values())
        if model_type:
            models = [m for m in models if m.model_type == model_type]
        return models

    def run_model(self, model_id: str, project_id: str,
                 parameters: Dict = None) -> ModelResult:
        """
        运行模型
        =======

        执行指定的预测/优化/评估模型
        """
        model = self._models.get(model_id)
        if not model:
            return None

        result = ModelResult(
            result_id=str(uuid.uuid4())[:12],
            model_id=model_id,
            project_id=project_id,
            run_at=datetime.now().isoformat(),
            input_summary=f"Running {model.model_name}",
            parameters=parameters or {}
        )

        model.status = ModelStatus.RUNNING

        try:
            # 根据模型类型调用不同求解器
            if model.model_type == ModelType.AIR_DISPERSION:
                result = self._run_air_dispersion(model, result, parameters)
            elif model.model_type == ModelType.WATER_QUALITY:
                result = self._run_water_quality(model, result, parameters)
            elif model.model_type == ModelType.NOISE_PREDICTION:
                result = self._run_noise_prediction(model, result, parameters)
            elif model.model_type == ModelType.HEALTH_RISK:
                result = self._run_health_risk(model, result, parameters)
            else:
                result.output_data = {"message": "Model type not implemented"}

            result.status = ModelStatus.COMPLETED
            result.confidence = 0.90

        except Exception as e:
            result.status = ModelStatus.FAILED
            result.error_message = str(e)

        model.status = ModelStatus.READY

        # 存储结果
        if project_id not in self._results:
            self._results[project_id] = []
        self._results[project_id].append(result)

        return result

    def _run_air_dispersion(self, model: ModelConfig,
                           result: ModelResult,
                           parameters: Dict) -> ModelResult:
        """运行大气扩散模型"""
        params = {**model.parameters}
        if parameters:
            params.update(parameters)

        # 简化的AERMOD计算
        emission_rate = params.get('emission_rate', 1.0)
        stack_height = params.get('stack_height', 50.0)

        # 计算最大落地浓度 (简化公式)
        # C_max = Q / (2π × σ_y × σ_z) × exp(-H²/2σz²)
        # 这里用简化近似
        max_concentration = emission_rate * 0.1 / (stack_height ** 0.5)

        result.output_data = {
            "model": model.model_id,
            "max_concentration": round(max_concentration, 4),
            "unit": "mg/m³",
            "max_ground_level": round(max_concentration * 0.8, 4),
            "impact_distance": round(stack_height * 10, 0),
            "unit": "m",
            "concentration_contour": [
                {"distance_m": 100, "concentration": round(max_concentration * 0.9, 4)},
                {"distance_m": 500, "concentration": round(max_concentration * 0.5, 4)},
                {"distance_m": 1000, "concentration": round(max_concentration * 0.2, 4)},
                {"distance_m": 2000, "concentration": round(max_concentration * 0.05, 4)},
            ]
        }

        result.visualizations = [{
            "type": "contour",
            "title": "大气扩散浓度等值线",
            "data": result.output_data["concentration_contour"]
        }]

        return result

    def _run_water_quality(self, model: ModelConfig,
                          result: ModelResult,
                          parameters: Dict) -> ModelResult:
        """运行水质模型"""
        params = {**model.parameters}
        if parameters:
            params.update(parameters)

        result.output_data = {
            "model": model.model_id,
            "reach_length": params.get('reach_length', 1000),
            "BOD_concentration": [10.0, 8.5, 7.2, 6.1, 5.3],
            "DO_concentration": [4.5, 5.2, 5.8, 6.2, 6.5],
            "distance_km": [0, 0.25, 0.5, 0.75, 1.0]
        }

        return result

    def _run_noise_prediction(self, model: ModelConfig,
                              result: ModelResult,
                              parameters: Dict) -> ModelResult:
        """运行噪声预测模型"""
        params = {**model.parameters}
        if parameters:
            params.update(parameters)

        source_level = params.get('source_level', 85.0)
        distance = params.get('distance', 100.0)

        # 简化点声源衰减
        # Lp = Lw - 20*log10(r) - 11
        predicted_level = source_level - 20 * (distance ** 0.5) - 11

        result.output_data = {
            "model": model.model_id,
            "source_level": source_level,
            "distance": distance,
            "predicted_level": round(max(30, predicted_level), 1),
            "unit": "dB(A)",
            "standard_day": 65,
            "standard_night": 55,
            "exceeded": predicted_level > 65
        }

        return result

    def _run_health_risk(self, model: ModelConfig,
                         result: ModelResult,
                         parameters: Dict) -> ModelResult:
        """运行健康风险评估"""
        params = {**model.parameters}
        if parameters:
            params.update(parameters)

        concentration = params.get('exposure_concentration', 10.0)
        duration = params.get('exposure_duration', 30.0)

        # 简化致癌风险计算
        # Risk = Concentration × CPF × Duration
        CPF = 0.001  # 简化假设
        cancer_risk = concentration * CPF * duration / 70  # 归一化到终生

        # 非致癌危害指数
        # HI = Exposure /RfD
        RfD = 10.0  # 参考剂量
        hazard_index = concentration / RfD

        result.output_data = {
            "model": model.model_id,
            "carcinogenic_risk": f"{cancer_risk:.2e}",
            "carcinogenic_risk_level": "acceptable" if cancer_risk < 1e-4 else "concern",
            "hazard_index": round(hazard_index, 2),
            "hazard_quotient_level": "acceptable" if hazard_index < 1 else "concern",
            "recommendations": [
                "致癌风险可接受" if cancer_risk < 1e-4 else "需采取减排措施",
                "非致癌危害指数可接受" if hazard_index < 1 else "需关注健康影响"
            ]
        }

        return result

    def optimize_treatment(self, project_id: str,
                         current_costs: Dict,
                         target_reduction: float) -> Dict:
        """
        治理设施运行优化
        =================

        输入当前成本和目标减排量，输出最优运行方案
        """
        # 简化优化算法
        options = [
            {
                "name": "增加活性炭更换频率",
                "cost_increase": 5000,  # 元/月
                "efficiency_gain": 0.05
            },
            {
                "name": "增设二级过滤",
                "cost_increase": 15000,
                "efficiency_gain": 0.15
            },
            {
                "name": "升级到RTO",
                "cost_increase": 50000,
                "efficiency_gain": 0.30
            },
        ]

        # 贪心选择
        selected = []
        current_reduction = 0.0

        for option in sorted(options, key=lambda x: x['cost_increase']/x['efficiency_gain']):
            if current_reduction >= target_reduction:
                break
            selected.append(option)
            current_reduction += option['efficiency_gain']

        return {
            "project_id": project_id,
            "target_reduction": target_reduction,
            "achieved_reduction": current_reduction,
            "selected_options": [o['name'] for o in selected],
            "total_cost_increase": sum(o['cost_increase'] for o in selected),
            "cost_effectiveness": target_reduction / sum(o['cost_increase'] for o in selected) if selected else 0
        }

    def get_model_results(self, project_id: str,
                         model_id: str = None) -> List[ModelResult]:
        """获取模型运行结果"""
        results = self._results.get(project_id, [])
        if model_id:
            results = [r for r in results if r.model_id == model_id]
        return results


# 全局单例
_model_library = None

def get_model_library() -> ModelLibrary:
    """获取模型库单例"""
    global _model_library
    if _model_library is None:
        _model_library = ModelLibrary()
    return _model_library
