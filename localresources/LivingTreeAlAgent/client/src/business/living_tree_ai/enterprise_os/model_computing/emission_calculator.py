"""
排放核算引擎 (Emission Calculator)

实现产排污系数法和物料衡算法，计算污染物排放量。

支持：
1. 大气污染物（SO2、NOx、烟尘、VOCs等）
2. 水污染物（COD、氨氮、总磷等）
3. 固体废物
4. 噪声

使用方法：
```python
calculator = get_emission_calculator()

# 基于产排污系数计算
result = await calculator.calculate_by_factor(
    project_id="PROJ001",
    source_type="boiler",
    fuel_type="coal",
    fuel_consumption=10000,  # 吨/年
    capacity=20,  # 蒸吨
    emission_factors={...}
)

# 基于物料衡算
result = await calculator.calculate_by_mass_balance(
    project_id="PROJ001",
    process="溶剂使用",
    input_materials=[{"name": "甲苯", "amount": 100}],
    output_products=[...],
    control_efficiency={...}
)
```
"""

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, List, Any
import math


class EmissionSource(Enum):
    """排放源类型"""
    # 燃烧源
    BOILER = "boiler"                           # 锅炉
    FURNACE = "furnace"                         # 炉窑
    HEATING_FURNACE = "heating_furnace"         # 热风炉

    # 工艺源
    PROCESS_EMISSION = "process_emission"      # 工艺排气
    SOLVENT_USAGE = "solvent_usage"            # 溶剂使用
    CHEMICAL_REACTION = "chemical_reaction"    # 化学反应

    # 无组织源
    UNORGANIZED = "unorganized"               # 无组织排放
    STORAGE_TANK = "storage_tank"             # 储罐呼吸
    LOADING_UNLOADING = "loading_unloading"   # 装卸
    WASTEWATER_TREATMENT = "wastewater_treatment"  # 污水处理

    # 移动源
    VEHICLE = "vehicle"                        # 车辆
    MACHINERY = "machinery"                   # 机械

    # 固体废物
    SOLID_WASTE_GENERATION = "solid_waste"     # 固废产生


class PollutantType(Enum):
    """污染物类型"""
    # 大气污染物
    SO2 = "SO2"                                # 二氧化硫
    NOx = "NOx"                                # 氮氧化物
    TSP = "TSP"                                # 总悬浮颗粒物
    PM10 = "PM10"                              # 可吸入颗粒物
    PM25 = "PM2.5"                             # 细颗粒物
    CO = "CO"                                  # 一氧化碳
    VOCs = "VOCs"                              # 挥发性有机物
    BENZENE = "benzene"                        # 苯
    TOLUENE = "toluene"                        # 甲苯
    FORMALDEHYDE = "formaldehyde"              # 甲醛
    HCL = "HCl"                                # 氯化氢
    HF = "HF"                                  # 氟化氢
    NH3 = "NH3"                                # 氨气

    # 水污染物
    COD = "COD"                                # 化学需氧量
    BOD5 = "BOD5"                              # 五日生化需氧量
    SS = "SS"                                  # 悬浮物
    NH3_N = "NH3-N"                            # 氨氮
    TN = "TN"                                  # 总氮
    TP = "TP"                                  # 总磷
    OIL = "oil"                                # 石油类
    PHENOL = "phenol"                          # 挥发酚
    CHROMIUM = "Cr"                            # 六价铬
    LEAD = "Pb"                                # 铅
    CADMIUM = "Cd"                             # 镉
    MERCURY = "Hg"                             # 汞
    ARSENIC = "As"                            # 砷

    # 固废
    HAZARDOUS_WASTE = "hazardous_waste"       # 危险废物
    GENERAL_WASTE = "general_waste"           # 一般固废


@dataclass
class EmissionFactor:
    """排放系数"""
    pollutant: str
    value: float
    unit: str                                  # 如 "kg/t", "g/kWh"
    source: str                                # 系数来源（国家标准、行业标准、实测）
    standard: str                              # 依据标准编号
    applicability: str = ""                    # 适用范围


@dataclass
class CalculatedEmission:
    """计算得到的排放量"""
    pollutant: str
    emission_amount: float                     # 排放量（t/a或kg/a）
    unit: str = "t/a"

    # 计算详情
    calculation_method: str = ""               # 计算方法
    formula: str = ""                           # 使用的公式
    parameters: Dict[str, Any] = field(default_factory=dict)  # 计算参数

    # 排放特征
    concentration: Optional[float] = None       # 排放浓度 (mg/m3)
    discharge_rate: Optional[float] = None    # 排放速率 (kg/h)

    # 控制措施
    control_measures: List[str] = field(default_factory=list)  # 控制的措施
    control_efficiency: float = 0.0           # 去除效率

    # 源信息
    source_type: str = ""
    source_id: Optional[str] = None

    # 置信度
    confidence: float = 0.9
    quality_score: float = 0.85

    # 合规判定
    is_compliant: bool = True
    limit_value: Optional[float] = None        # 排放限值
    exceedance_ratio: Optional[float] = None  # 超标倍数


class EmissionCalculator:
    """
    排放核算引擎

    支持两种核算方法：
    1. 产排污系数法 - 基于活动水平和排放系数的简易算法
    2. 物料衡算法 - 基于质量守恒原理的精确算法
    """

    # 内置排放系数库（示例数据，实际应引用国家标准）
    DEFAULT_FACTORS = {
        ("boiler", "coal", "SO2"): EmissionFactor("SO2", 16.0, "kg/t", "国家标准", "HJ 274-2015", "燃煤锅炉"),
        ("boiler", "coal", "NOx"): EmissionFactor("NOx", 7.5, "kg/t", "国家标准", "HJ 274-2015", "燃煤锅炉"),
        ("boiler", "coal", "TSP"): EmissionFactor("TSP", 8.0, "kg/t", "国家标准", "HJ 274-2015", "燃煤锅炉"),
        ("boiler", "coal", "VOCs"): EmissionFactor("VOCs", 0.5, "kg/t", "行业数据", "参考值", "燃煤"),
        ("boiler", "natural_gas", "SO2"): EmissionFactor("SO2", 0.1, "kg/10^4m3", "国家标准", "HJ 274-2015", "燃气锅炉"),
        ("boiler", "natural_gas", "NOx"): EmissionFactor("NOx", 3.5, "kg/10^4m3", "国家标准", "HJ 274-2015", "燃气锅炉"),
        ("boiler", "natural_gas", "VOCs"): EmissionFactor("VOCs", 0.1, "kg/10^4m3", "行业数据", "参考值", "燃气"),
    }

    # 典型行业排放系数
    INDUSTRY_FACTORS = {
        "化工": {
            "VOCs": {
                "storage_tank": 0.5,  # kg/(t·年) - 储罐呼吸
                "loading": 0.2,       # kg/t - 装卸
                "process": 2.0,       # kg/t - 工艺过程
            },
            "COD": {
                "production": 1.5,    # kg/t产品
            }
        },
        "印刷": {
            "VOCs": {
                "printing": 50.0,     # kg/t油墨
                "drying": 30.0,        # kg/t油墨
                "cleaning": 5.0,      # kg/t溶剂
            }
        },
        "表面涂装": {
            "VOCs": {
                "spray": 80.0,         # kg/t涂料
                "drying": 20.0,        # kg/t涂料
            }
        }
    }

    def __init__(self):
        self._custom_factors: Dict[str, EmissionFactor] = {}
        self._calculation_history: List[Dict[str, Any]] = []

    async def calculate_by_factor(
        self,
        project_id: str,
        source_type: str,
        fuel_type: Optional[str] = None,
        fuel_consumption: Optional[float] = None,
        capacity: Optional[float] = None,
        operating_hours: int = 8760,
        emission_factors: Optional[Dict[str, float]] = None,
        control_efficiency: Optional[Dict[str, float]] = None,
        pollutant_list: Optional[List[str]] = None,
        **kwargs
    ) -> Dict[str, CalculatedEmission]:
        """
        基于产排污系数法计算排放量

        公式：排放量 = 活动水平 × 排放系数 × (1 - 去除效率)

        Args:
            project_id: 项目ID
            source_type: 排放源类型
            fuel_type: 燃料类型（如 "coal", "natural_gas"）
            fuel_consumption: 燃料消耗量（根据单位确定）
            capacity: 设备容量（蒸吨、kW等）
            operating_hours: 年运行小时数
            emission_factors: 排放系数（覆盖默认系数）
            control_efficiency: 各污染物的去除效率
            pollutant_list: 需计算的污染物列表

        Returns:
            Dict[str, CalculatedEmission]: 各污染物的排放量
        """
        results = {}

        # 确定要计算的污染物
        if pollutant_list is None:
            # 根据排放源类型推断
            pollutant_list = self._get_default_pollutants(source_type)

        # 获取排放系数
        factors = emission_factors or {}

        for pollutant in pollutant_list:
            # 查找系数
            factor_key = (source_type, fuel_type, pollutant) if fuel_type else (source_type, pollutant)
            factor = factors.get(pollutant)

            if not factor:
                # 尝试从内置库获取
                default_factor = self.DEFAULT_FACTORS.get(factor_key)
                if default_factor:
                    factor = default_factor.value
                else:
                    factor = 0.0

            # 计算活动水平
            if fuel_consumption:
                activity_level = fuel_consumption
                formula = f"排放量 = 燃料消耗量 × 排放系数"
            elif capacity:
                activity_level = capacity * operating_hours
                formula = f"排放量 = 设备容量 × 运行时间 × 排放系数"
            else:
                activity_level = 1.0
                formula = "排放量 = 排放系数（无活动水平数据）"

            # 计算排放量
            # 注意：实际需要根据单位转换
            emission_amount = activity_level * factor / 1000 if factor else 0  # 转为t或kg

            # 应用去除效率
            efficiency = control_efficiency.get(pollutant, 0.0) if control_efficiency else 0.0
            final_amount = emission_amount * (1 - efficiency)

            results[pollutant] = CalculatedEmission(
                pollutant=pollutant,
                emission_amount=final_amount,
                unit="t/a",
                calculation_method="产排污系数法",
                formula=formula,
                parameters={
                    "source_type": source_type,
                    "fuel_type": fuel_type,
                    "activity_level": activity_level,
                    "raw_factor": factor,
                    "control_efficiency": efficiency,
                },
                source_type=source_type,
                control_efficiency=efficiency,
                confidence=0.9 if factor else 0.5,
                quality_score=0.85,
            )

        return results

    async def calculate_by_mass_balance(
        self,
        project_id: str,
        process: str,
        input_materials: List[Dict[str, Any]],
        output_products: Optional[List[Dict[str, Any]]] = None,
        byproducts: Optional[List[Dict[str, Any]]] = None,
        control_efficiency: Optional[Dict[str, float]] = None,
        pollutant_list: Optional[List[str]] = None,
        **kwargs
    ) -> Dict[str, CalculatedEmission]:
        """
        基于物料衡算法计算排放量

        原理：质量守恒 - 输入 = 输出 + 积累 + 去除

        Args:
            project_id: 项目ID
            process: 工艺过程名称
            input_materials: 输入物料 [{"name": "甲苯", "amount": 100, "voc_content": 0.95}]
            output_products: 产出产品
            byproducts: 副产物
            control_efficiency: 控制措施效率
            pollutant_list: 需计算的污染物

        Returns:
            Dict[str, CalculatedEmission]: 各污染物的排放量
        """
        results = {}

        # 确定要计算的污染物
        if pollutant_list is None:
            pollutant_list = self._get_default_pollutants("process_emission")

        # 提取VOC类物料
        voc_materials = [m for m in input_materials if "voc" in str(m.get("name", "")).lower()
                         or "voc_content" in m or "content" in m]

        for pollutant in pollutant_list:
            total_input = 0.0
            total_output = 0.0
            parameters = {"input_materials": [], "output_products": [], "byproducts": []}

            # 计算输入
            for mat in voc_materials:
                name = mat.get("name", "")
                amount = mat.get("amount", 0)  # 吨/年
                content = mat.get("voc_content", mat.get("content", 1.0))
               挥发_content = mat.get("挥发_content", content)

                input_amount = amount *挥发_content
                total_input += input_amount

                parameters["input_materials"].append({
                    "name": name,
                    "amount": amount,
                    "voc_content":挥发_content,
                    "input_voc": input_amount
                })

            # 计算输出
            if output_products:
                for prod in output_products:
                    amount = prod.get("amount", 0)
                    content = prod.get("voc_content", prod.get("content", 0))
                    output_amount = amount * content
                    total_output += output_amount
                    parameters["output_products"].append({
                        "name": prod.get("name", ""),
                        "amount": amount,
                        "voc_content": content,
                        "output_voc": output_amount
                    })

            if byproducts:
                for bp in byproducts:
                    amount = bp.get("amount", 0)
                    content = bp.get("voc_content", 0)
                    total_output += amount * content
                    parameters["byproducts"].append({
                        "name": bp.get("name", ""),
                        "amount": amount,
                        "voc_content": content
                    })

            # 挥发量 = 输入 - 回收/处理 - 转化 - 产品带走
            unrecovered = total_input - total_output

            # 应用控制效率
            efficiency = control_efficiency.get(pollutant, 0.0) if control_efficiency else 0.0
            final_emission = unrecovered * (1 - efficiency)

            results[pollutant] = CalculatedEmission(
                pollutant=pollutant,
                emission_amount=max(0, final_emission),  # 确保非负
                unit="t/a",
                calculation_method="物料衡算法",
                formula="排放量 = 输入量 - 产品带走量 - 回收量 - 去除量",
                parameters={
                    **parameters,
                    "total_input": total_input,
                    "total_output": total_output,
                    "unrecovered": unrecovered,
                    "control_efficiency": efficiency,
                },
                source_type=process,
                control_measures=list(control_efficiency.keys()) if control_efficiency else [],
                control_efficiency=efficiency,
                confidence=0.95,  # 物料衡算置信度较高
                quality_score=0.90,
            )

        return results

    async def calculate_permitted_emission(
        self,
        current_emission: Dict[str, CalculatedEmission],
        permit_limits: Dict[str, float],
        exhaust_volume: float,  # 年排放体积 m3/a
        concentration_limits: Optional[Dict[str, float]] = None,
        **kwargs
    ) -> Dict[str, Dict[str, Any]]:
        """
        计算许可排放量建议

        基于现有排放量和排放标准，给出许可排放量建议。

        Args:
            current_emission: 当前排放量
            permit_limits: 排放标准限值
            exhaust_volume: 年排放体积
            concentration_limits: 浓度限值 (mg/m3)

        Returns:
            Dict[str, Dict]: 各污染物的许可排放量建议
        """
        recommendations = {}

        for pollutant, emission in current_emission.items():
            limit = permit_limits.get(pollutant)
            conc_limit = concentration_limits.get(pollutant) if concentration_limits else None

            if limit is None:
                continue

            # 基于浓度限值推算
            if conc_limit and exhaust_volume > 0:
                emission_by_conc = conc_limit * exhaust_volume / 1e9  # 转为t/a
                recommended = min(emission.emission_amount * 1.1, emission_by_conc)  # 取小值，但允许10%裕量
            else:
                recommended = emission.emission_amount * 1.1  # 默认10%裕量

            # 合规判定
            is_compliant = emission.emission_amount <= limit
            exceedance_ratio = (emission.emission_amount / limit - 1) if limit > 0 else 0

            recommendations[pollutant] = {
                "current_emission": emission.emission_amount,
                "recommended_permit": round(recommended, 3),
                "standard_limit": limit,
                "is_compliant": is_compliant,
                "exceedance_ratio": round(exceedance_ratio, 3) if not is_compliant else 0,
                "suggestion": "达标" if is_compliant else "需治理",
            }

            # 更新原始对象
            emission.is_compliant = is_compliant
            emission.limit_value = limit
            emission.exceedance_ratio = exceedance_ratio if not is_compliant else None

        return recommendations

    def _get_default_pollutants(self, source_type: str) -> List[str]:
        """获取默认的污染物列表"""
        defaults = {
            "boiler": ["SO2", "NOx", "TSP", "VOCs"],
            "furnace": ["SO2", "NOx", "TSP", "VOCs"],
            "process_emission": ["VOCs", "苯", "甲苯", "二甲苯"],
            "solvent_usage": ["VOCs", "苯", "甲苯", "二甲苯"],
            "unorganized": ["VOCs", "NH3", "H2S"],
            "wastewater_treatment": ["COD", "NH3_N", "TN", "TP", "VOCs"],
        }
        return defaults.get(source_type, ["COD", "VOCs"])

    def get_emission_factors(
        self,
        source_type: str,
        fuel_type: Optional[str] = None,
        pollutant: Optional[str] = None
    ) -> List[EmissionFactor]:
        """查询排放系数"""
        factors = []

        # 从默认库查询
        for (s, f, p), factor in self.DEFAULT_FACTORS.items():
            if s == source_type:
                if fuel_type is None or f == fuel_type:
                    if pollutant is None or p == pollutant:
                        factors.append(factor)

        # 从自定义库查询
        for (s, f, p), factor in self._custom_factors.items():
            if s == source_type:
                if fuel_type is None or f == fuel_type:
                    if pollutant is None or p == pollutant:
                        factors.append(factor)

        return factors

    def add_custom_factor(self, factor: EmissionFactor, source_type: str, fuel_type: Optional[str] = None) -> None:
        """添加自定义排放系数"""
        key = (source_type, fuel_type or "", factor.pollutant)
        self._custom_factors[key] = factor


# 全局单例
_emission_calculator: Optional[EmissionCalculator] = None


def get_emission_calculator() -> EmissionCalculator:
    """获取排放核算引擎单例"""
    global _emission_calculator
    if _emission_calculator is None:
        _emission_calculator = EmissionCalculator()
    return _emission_calculator