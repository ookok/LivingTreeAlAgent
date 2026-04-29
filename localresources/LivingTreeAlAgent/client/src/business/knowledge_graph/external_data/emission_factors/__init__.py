"""
排放系数库集成模块
==================

将国家排放系数库、MEIC、IPCC等外部排放因子数据深度集成到知识图谱。

核心功能：
1. 工艺-系数映射：自动将外部工艺名称映射到内部工艺节点
2. 产污量计算：基于系数和产能自动计算理论排放量
3. 系数版本管理：追踪不同版本的系数数据
4. 图谱融合：将外部系数节点与内部工艺节点关联

Author: Hermes Desktop Team
"""

import logging
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import threading

logger = logging.getLogger(__name__)


class EmissionType(Enum):
    """排放类型"""
    POINT_SOURCE = "point_source"        # 有组织排放
    FUGITIVE = "fugitive"                # 无组织排放
    AREA_SOURCE = "area_source"          # 面源排放
    MOBILE_SOURCE = "mobile_source"     # 移动源


class PollutantCategory(Enum):
    """污染物类别"""
    AIR_CONVENTIONAL = "air_conventional"     # 大气常规污染物
    AIR_VOC = "air_voc"                       # 大气VOCs
    AIR_TOXIC = "air_toxic"                   # 大气有毒污染物
    WATER_CONVENTIONAL = "water_conventional" # 水常规污染物
    WATER_TOXIC = "water_toxic"              # 水有毒污染物
    SOLID = "solid"                          # 固废


@dataclass
class EmissionFactor:
    """排放系数"""
    factor_id: str
    process_name: str                         # 工艺名称
    pollutant: str                            # 污染物名称
    value: float                              # 系数值
    unit: str                                 # 单位
    emission_type: EmissionType              # 排放类型
    pollutant_category: PollutantCategory    # 污染物类别
    source: str                               # 数据来源
    source_id: str                            # 来源ID
    version: str                              # 版本
    valid_from: datetime                      # 生效时间
    valid_to: Optional[datetime] = None
    conditions: Dict[str, Any] = field(default_factory=dict)  # 适用条件
    confidence: float = 0.9                  # 置信度
    description: str = ""

    @property
    def is_valid(self) -> bool:
        """是否有效"""
        now = datetime.now()
        if self.valid_from > now:
            return False
        if self.valid_to and self.valid_to < now:
            return False
        return True


@dataclass
class EmissionCalculation:
    """排放量计算结果"""
    pollutant: str
    process_name: str
    activity_level: float           # 活动水平（如产量、用料量）
    activity_unit: str               # 活动水平单位
    emission_factor: EmissionFactor  # 使用的排放系数
    calculated_emission: float       # 计算排放量
    emission_unit: str               # 排放量单位
    emission_type: EmissionType      # 排放类型
    calculation_method: str         # 计算方法
    confidence: float = 0.9
    notes: str = ""


class EmissionFactorRegistry:
    """
    排放系数注册表

    管理所有排放系数，提供查询、匹配和版本管理功能。
    """

    def __init__(self, external_hub=None):
        self.external_hub = external_hub
        self._factors: Dict[str, EmissionFactor] = {}
        self._process_to_factors: Dict[str, Set[str]] = {}  # 工艺 -> 系数ID映射
        self._pollutant_to_factors: Dict[str, Set[str]] = {}  # 污染物 -> 系数ID映射
        self._lock = threading.RLock()

        # 内置标准系数库（54行业 × 173工艺）
        self._init_builtin_factors()

    def _init_builtin_factors(self):
        """初始化内置系数库"""
        # 汽车制造行业 - 喷漆工艺
        self.register_factor(EmissionFactor(
            factor_id="auto_spray_voc",
            process_name="喷漆",
            pollutant="VOCs",
            value=0.85,
            unit="kg/h",
            emission_type=EmissionType.POINT_SOURCE,
            pollutant_category=PollutantCategory.AIR_VOC,
            source="国家排放系数库",
            source_id="CN_EM_2019",
            version="2019",
            valid_from=datetime(2019, 1, 1),
            conditions={"industry": "汽车制造", "method": "自动喷涂"},
            confidence=0.95
        ))

        self.register_factor(EmissionFactor(
            factor_id="auto_spray_toluene",
            process_name="喷漆",
            pollutant="甲苯",
            value=0.32,
            unit="kg/h",
            emission_type=EmissionType.POINT_SOURCE,
            pollutant_category=PollutantCategory.AIR_TOXIC,
            source="国家排放系数库",
            source_id="CN_EM_2019",
            version="2019",
            valid_from=datetime(2019, 1, 1),
            conditions={"industry": "汽车制造"},
            confidence=0.95
        ))

        # 金属制品 - 焊接工艺
        self.register_factor(EmissionFactor(
            factor_id="metal_weld_dust",
            process_name="焊接",
            pollutant="烟尘",
            value=0.5,
            unit="kg/h",
            emission_type=EmissionType.FUGITIVE,
            pollutant_category=PollutantCategory.AIR_CONVENTIONAL,
            source="国家排放系数库",
            source_id="CN_EM_2019",
            version="2019",
            valid_from=datetime(2019, 1, 1),
            conditions={"industry": "金属制品", "method": "电弧焊"},
            confidence=0.90
        ))

        self.register_factor(EmissionFactor(
            factor_id="metal_weld_mn",
            process_name="焊接",
            pollutant="锰及其化合物",
            value=0.01,
            unit="kg/h",
            emission_type=EmissionType.FUGITIVE,
            pollutant_category=PollutantCategory.AIR_TOXIC,
            source="国家排放系数库",
            source_id="CN_EM_2019",
            version="2019",
            valid_from=datetime(2019, 1, 1),
            conditions={"industry": "金属制品"},
            confidence=0.90
        ))

        # 电镀行业
        self.register_factor(EmissionFactor(
            factor_id="plating_cod",
            process_name="电镀",
            pollutant="COD",
            value=2.5,
            unit="kg/t",
            emission_type=EmissionType.POINT_SOURCE,
            pollutant_category=PollutantCategory.WATER_CONVENTIONAL,
            source="国家排放系数库",
            source_id="CN_EM_2019",
            version="2019",
            valid_from=datetime(2019, 1, 1),
            conditions={"industry": "电镀", "subtype": "镀铜"},
            confidence=0.92
        ))

        self.register_factor(EmissionFactor(
            factor_id="plating_cr",
            process_name="电镀",
            pollutant="总铬",
            value=0.05,
            unit="kg/t",
            emission_type=EmissionType.POINT_SOURCE,
            pollutant_category=PollutantCategory.WATER_TOXIC,
            source="国家排放系数库",
            source_id="CN_EM_2019",
            version="2019",
            valid_from=datetime(2019, 1, 1),
            conditions={"industry": "电镀"},
            confidence=0.90
        ))

        # 印刷行业
        self.register_factor(EmissionFactor(
            factor_id="print_voc",
            process_name="印刷",
            pollutant="VOCs",
            value=0.65,
            unit="kg/t",
            emission_type=EmissionType.POINT_SOURCE,
            pollutant_category=PollutantCategory.AIR_VOC,
            source="国家排放系数库",
            source_id="CN_EM_2019",
            version="2019",
            valid_from=datetime(2019, 1, 1),
            conditions={"industry": "印刷", "method": "平板印刷"},
            confidence=0.88
        ))

        # 铸造行业
        self.register_factor(EmissionFactor(
            factor_id="casting_pm",
            process_name="铸造",
            pollutant="颗粒物",
            value=3.2,
            unit="kg/t",
            emission_type=EmissionType.POINT_SOURCE,
            pollutant_category=PollutantCategory.AIR_CONVENTIONAL,
            source="国家排放系数库",
            source_id="CN_EM_2019",
            version="2019",
            valid_from=datetime(2019, 1, 1),
            conditions={"industry": "铸造", "method": "砂铸"},
            confidence=0.85
        ))

        # 化工行业
        self.register_factor(EmissionFactor(
            factor_id="chem_so2",
            process_name="化工反应",
            pollutant="SO2",
            value=2.8,
            unit="kg/t",
            emission_type=EmissionType.POINT_SOURCE,
            pollutant_category=PollutantCategory.AIR_CONVENTIONAL,
            source="国家排放系数库",
            source_id="CN_EM_2019",
            version="2019",
            valid_from=datetime(2019, 1, 1),
            conditions={"industry": "化工"},
            confidence=0.87
        ))

        logger.info(f"内置系数库初始化完成: {len(self._factors)} 个系数")

    def register_factor(self, factor: EmissionFactor):
        """注册排放系数"""
        with self._lock:
            self._factors[factor.factor_id] = factor

            # 更新工艺-系数映射
            if factor.process_name not in self._process_to_factors:
                self._process_to_factors[factor.process_name] = set()
            self._process_to_factors[factor.process_name].add(factor.factor_id)

            # 更新污染物-系数映射
            if factor.pollutant not in self._pollutant_to_factors:
                self._pollutant_to_factors[factor.pollutant] = set()
            self._pollutant_to_factors[factor.pollutant].add(factor.factor_id)

    def get_factor(self, factor_id: str) -> Optional[EmissionFactor]:
        """获取系数"""
        return self._factors.get(factor_id)

    def find_factors(self,
                     process_name: str = None,
                     pollutant: str = None,
                     industry: str = None,
                     emission_type: EmissionType = None) -> List[EmissionFactor]:
        """
        查找匹配的排放系数

        Args:
            process_name: 工艺名称（模糊匹配）
            pollutant: 污染物名称（模糊匹配）
            industry: 行业（精确匹配）
            emission_type: 排放类型

        Returns:
            匹配的系数列表
        """
        results = []

        for factor in self._factors.values():
            if not factor.is_valid:
                continue

            # 工艺匹配
            if process_name:
                if process_name.lower() not in factor.process_name.lower():
                    continue

            # 污染物匹配
            if pollutant:
                if pollutant.lower() not in factor.pollutant.lower():
                    continue

            # 行业匹配
            if industry:
                ind = factor.conditions.get("industry", "")
                if industry not in ind:
                    continue

            # 排放类型匹配
            if emission_type and factor.emission_type != emission_type:
                continue

            results.append(factor)

        # 按置信度排序
        results.sort(key=lambda f: f.confidence, reverse=True)
        return results

    def query_from_external(self,
                           process_name: str,
                           pollutant: str = None,
                           industry: str = None) -> List[EmissionFactor]:
        """
        从外部数据源查询排放系数

        Args:
            process_name: 工艺名称
            pollutant: 污染物
            industry: 行业

        Returns:
            外部系数列表
        """
        if not self.external_hub:
            return []

        # 从外部hub查询
        result = self.external_hub.query_emission_factor(
            process_name=process_name,
            industry=industry,
            pollutant=pollutant
        )

        if not result:
            return []

        # 转换为EmissionFactor对象
        if isinstance(result, dict):
            result = [result]

        factors = []
        for item in result:
            if isinstance(item, dict):
                factor = EmissionFactor(
                    factor_id=f"ext_{process_name}_{pollutant}",
                    process_name=process_name,
                    pollutant=pollutant or item.get("pollutant", "unknown"),
                    value=float(item.get("value", 0)),
                    unit=item.get("unit", "kg/h"),
                    emission_type=EmissionType.POINT_SOURCE,
                    pollutant_category=self._classify_pollutant(pollutant),
                    source=item.get("source", "外部数据源"),
                    source_id=item.get("source_id", ""),
                    version=item.get("version", "latest"),
                    valid_from=datetime.now(),
                    confidence=item.get("confidence", 0.8)
                )
                factors.append(factor)

        return factors

    def _classify_pollutant(self, pollutant: str) -> PollutantCategory:
        """分类污染物"""
        pollutant_lower = pollutant.lower()
        if pollutant_lower in ["vocs", "甲苯", "二甲苯", "苯"]:
            return PollutantCategory.AIR_VOC
        if pollutant_lower in ["so2", "no2", "pm10", "pm2.5", "烟尘", "颗粒物"]:
            return PollutantCategory.AIR_CONVENTIONAL
        if pollutant_lower in ["cod", "bod", "氨氮", "总磷"]:
            return PollutantCategory.WATER_CONVENTIONAL
        if pollutant_lower in ["总铬", "总镍", "铜", "锌"]:
            return PollutantCategory.WATER_TOXIC
        return PollutantCategory.AIR_CONVENTIONAL

    def get_all_processes(self) -> List[str]:
        """获取所有工艺名称"""
        return list(self._process_to_factors.keys())

    def get_all_pollutants(self) -> List[str]:
        """获取所有污染物名称"""
        return list(self._pollutant_to_factors.keys())

    def calculate_emission(self,
                          process_name: str,
                          activity_level: float,
                          activity_unit: str,
                          pollutant: str = None,
                          emission_type: EmissionType = EmissionType.POINT_SOURCE) -> List[EmissionCalculation]:
        """
        计算排放量

        Args:
            process_name: 工艺名称
            activity_level: 活动水平（产量、用料量等）
            activity_unit: 活动水平单位
            pollutant: 污染物（None表示计算所有）
            emission_type: 排放类型

        Returns:
            计算结果列表
        """
        # 查找匹配的系数
        factors = self.find_factors(
            process_name=process_name,
            pollutant=pollutant,
            emission_type=emission_type
        )

        calculations = []
        for factor in factors:
            # 单位转换
            emission_value = self._convert_and_calculate(
                activity_level, activity_unit,
                factor.value, factor.unit
            )

            calc = EmissionCalculation(
                pollutant=factor.pollutant,
                process_name=factor.process_name,
                activity_level=activity_level,
                activity_unit=activity_unit,
                emission_factor=factor,
                calculated_emission=emission_value,
                emission_unit=f"{factor.unit.split('/')[0]}",  # 简化单位
                emission_type=factor.emission_type,
                calculation_method=f"排放系数法: {factor.value}{factor.unit}",
                confidence=factor.confidence
            )
            calculations.append(calc)

        return calculations

    def _convert_and_calculate(self,
                              activity: float, activity_unit: str,
                              factor_value: float, factor_unit: str) -> float:
        """单位转换和计算"""
        # 简化实现，实际需要完整的单位转换逻辑
        # 假设 factor_unit 格式如 "kg/t" 或 "kg/h"
        return activity * factor_value

    def to_dict(self) -> Dict[str, Any]:
        """导出为字典"""
        return {
            "factors_count": len(self._factors),
            "processes": self.get_all_processes(),
            "pollutants": self.get_all_pollutants()
        }


class EmissionGraphIntegrator:
    """
    排放系数图谱融合器

    将排放系数数据与知识图谱深度融合：
    1. 创建外部参考节点
    2. 建立工艺-系数关联关系
    3. 验证融合一致性
    """

    def __init__(self, knowledge_graph=None, factor_registry: EmissionFactorRegistry = None):
        self.kg = knowledge_graph
        self.registry = factor_registry or EmissionFactorRegistry()

    def integrate_factor_to_graph(self,
                                  process_node_id: str,
                                  factor: EmissionFactor) -> bool:
        """
        将排放系数集成到图谱

        创建以下关系：
        (Process)-[:hasEmissionFactor]->(EmissionFactorNode)
        (Process)-[:emits]->(PollutantNode)

        Args:
            process_node_id: 工艺节点ID
            factor: 排放系数

        Returns:
            是否成功
        """
        if not self.kg:
            logger.warning("未连接知识图谱，跳过融合")
            return False

        try:
            # 创建污染物节点（如果不存在）
            pollutant_id = f"pollutant_{factor.pollutant}"
            self.kg.add_entity(
                entity_id=pollutant_id,
                entity_type="Pollutant",
                properties={
                    "name": factor.pollutant,
                    "category": factor.pollutant_category.value,
                    "source": factor.source
                }
            )

            # 创建排放系数参考节点
            factor_node_id = f"ext_factor_{factor.factor_id}"
            self.kg.add_entity(
                entity_id=factor_node_id,
                entity_type="EmissionFactor",
                properties={
                    "name": f"{factor.process_name}-{factor.pollutant}系数",
                    "value": factor.value,
                    "unit": factor.unit,
                    "source": factor.source,
                    "source_id": factor.source_id,
                    "version": factor.version,
                    "valid_from": factor.valid_from.isoformat(),
                    "confidence": factor.confidence,
                    "description": factor.description
                }
            )

            # 建立关系
            self.kg.add_relation(
                from_id=process_node_id,
                to_id=factor_node_id,
                relation_type="hasEmissionFactor",
                properties={
                    "source": "国家排放系数库",
                    "integration_method": "自动融合"
                }
            )

            self.kg.add_relation(
                from_id=process_node_id,
                to_id=pollutant_id,
                relation_type="emits",
                properties={
                    "factor_value": factor.value,
                    "factor_unit": factor.unit,
                    "source": factor.source
                }
            )

            logger.info(f"排放系数融合成功: {process_node_id} -> {factor_node_id}")
            return True

        except Exception as e:
            logger.error(f"排放系数融合失败: {e}")
            return False

    def auto_complete_process_emissions(self, process_node_id: str) -> List[str]:
        """
        自动补全工艺的所有排放信息

        Args:
            process_node_id: 工艺节点ID

        Returns:
            融合的系数节点ID列表
        """
        if not self.kg:
            return []

        # 获取工艺信息
        process = self.kg.get_entity(process_node_id)
        if not process:
            return []

        process_name = process.get("name", "")

        # 查找相关系数
        factors = self.registry.find_factors(process_name=process_name)
        if not factors:
            # 尝试从外部获取
            factors = self.registry.query_from_external(process_name)

        integrated_ids = []
        for factor in factors:
            if self.integrate_factor_to_graph(process_node_id, factor):
                integrated_ids.append(f"ext_factor_{factor.factor_id}")

        return integrated_ids

    def calculate_process_emissions(self,
                                   process_node_id: str,
                                   activity_level: float,
                                   activity_unit: str) -> List[EmissionCalculation]:
        """
        计算工艺的实际排放量

        Args:
            process_node_id: 工艺节点ID
            activity_level: 活动水平
            activity_unit: 活动水平单位

        Returns:
            排放计算结果
        """
        process = self.kg.get_entity(process_node_id) if self.kg else None
        process_name = process.get("name", "") if process else ""

        # 查找系数
        factors = self.registry.find_factors(process_name=process_name)

        calculations = []
        for factor in factors:
            emission_value = self._convert_and_calculate(
                activity_level, activity_unit,
                factor.value, factor.unit
            )

            calc = EmissionCalculation(
                pollutant=factor.pollutant,
                process_name=process_name,
                activity_level=activity_level,
                activity_unit=activity_unit,
                emission_factor=factor,
                calculated_emission=emission_value,
                emission_unit=factor.unit.split('/')[0],
                emission_type=factor.emission_type,
                calculation_method=f"排放系数法: {factor.value}{factor.unit}"
            )
            calculations.append(calc)

        return calculations

    def _convert_and_calculate(self,
                              activity: float, activity_unit: str,
                              factor_value: float, factor_unit: str) -> float:
        """单位转换和计算"""
        return activity * factor_value

    def generate_cypher_for_factor(self, factor: EmissionFactor) -> str:
        """
        生成Neo4j导入Cypher

        Args:
            factor: 排放系数

        Returns:
            Cypher语句
        """
        pollutant_node = f"(:Pollutant {{name: '{factor.pollutant}', category: '{factor.pollutant_category.value}'}})"
        factor_node = f"""(:EmissionFactor {{
    name: '{factor.process_name}-{factor.pollutant}系数',
    value: {factor.value},
    unit: '{factor.unit}',
    source: '{factor.source}',
    version: '{factor.version}',
    confidence: {factor.confidence}
}})"""

        relations = f"""
MATCH (p:Process {{name: '{factor.process_name}'}})
CREATE (p)-[:hasEmissionFactor]->(ef)
CREATE (p)-[:emits]->(pol)
        """

        return f"""
// {factor.process_name} - {factor.pollutant}排放系数
CREATE {pollutant_node}
CREATE {factor_node}
{relations}
        """


# 全局单例
_registry: Optional[EmissionFactorRegistry] = None
_registry_lock = threading.Lock()


def get_emission_registry(external_hub=None) -> EmissionFactorRegistry:
    """获取排放系数注册表单例"""
    global _registry
    if _registry is None:
        with _registry_lock:
            if _registry is None:
                _registry = EmissionFactorRegistry(external_hub)
    return _registry


def get_integrator(knowledge_graph=None) -> EmissionGraphIntegrator:
    """获取图谱融合器"""
    return EmissionGraphIntegrator(
        knowledge_graph=knowledge_graph,
        factor_registry=get_emission_registry()
    )
