"""
数据映射与对齐层 (Entity Linker)
=================================

实现外部数据与内部知识图谱的深度融合：
1. 实体链接 - 将外部数据ID映射到内部实体节点
2. 单位转换 - 统一不同来源的数据单位
3. 数据一致性验证 - 确保融合后的数据质量
4. 关系映射 - 建立内外节点间的关联关系

核心理念：外部数据不是孤立的查询工具，而是知识图谱的"外部节点"

Author: Hermes Desktop Team
"""

import logging
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import re
import threading

logger = logging.getLogger(__name__)


class LinkDirection(Enum):
    """链接方向"""
    INTERNAL_TO_EXTERNAL = "int_to_ext"    # 内部节点引用外部
    EXTERNAL_TO_INTERNAL = "ext_to_int"    # 外部节点关联内部
    BIDIRECTIONAL = "bidirectional"        # 双向链接


class MappingQuality(Enum):
    """映射质量"""
    HIGH = "high"           # 精确匹配
    MEDIUM = "medium"       # 模糊匹配
    LOW = "low"            # 低质量映射
    PENDING = "pending"     # 待审核


@dataclass
class EntityMapping:
    """实体映射"""
    mapping_id: str
    internal_id: str              # 内部实体ID
    external_id: str              # 外部实体ID
    external_source: str          # 外部数据源
    entity_type: str              # 实体类型
    confidence: float = 1.0       # 置信度
    quality: MappingQuality = MappingQuality.HIGH
    mapping_method: str = ""      # 映射方法（exact/fuzzy/vector）
    verified: bool = False
    verified_by: str = ""
    verified_at: datetime = None
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UnitConversion:
    """单位转换规则"""
    from_unit: str
    to_unit: str
    factor: float              # 转换因子（to = from * factor）
    offset: float = 0.0        # 偏移量（用于温度等）
    description: str = ""


@dataclass
class DataAlignment:
    """数据对齐结果"""
    source_id: str
    target_id: str
    alignment_type: str         # 对齐类型
    value_before: Any           # 对齐前的值
    value_after: Any            # 对齐后的值
    conversion_applied: str = ""  # 应用的转换
    confidence: float = 1.0


class EntityLinker:
    """
    实体链接器

    负责外部数据与内部图谱的实体匹配和链接。
    """

    def __init__(self, knowledge_graph=None):
        self.kg = knowledge_graph
        self._mappings: Dict[str, EntityMapping] = {}  # mapping_id -> mapping
        self._internal_to_external: Dict[str, Set[str]] = {}  # internal_id -> external_ids
        self._external_to_internal: Dict[str, str] = {}  # external_id -> internal_id
        self._lock = threading.RLock()

        # 初始化内置同义词词典（工艺名称映射）
        self._process_synonyms = self._build_process_synonyms()

        # 初始化单位转换规则
        self._unit_conversions = self._build_unit_conversions()

    def _build_process_synonyms(self) -> Dict[str, List[str]]:
        """构建工艺同义词词典"""
        return {
            # 表面处理类
            "喷漆": ["涂装", "喷涂", "油漆", "喷漆作业", "涂装作业"],
            "电镀": ["镀层", "表面处理", "电沉积"],
            "阳极氧化": ["氧化", "阳极处理", "电解氧化"],
            "钝化": ["防锈处理", "钝化处理"],

            # 焊接类
            "焊接": ["焊装", "焊接作业", "电弧焊", "气体保护焊", "CO2保护焊"],
            "切割": ["下料", "激光切割", "等离子切割"],
            "打磨": ["研磨", "抛光", "表面处理"],

            # 热处理类
            "热处理": ["淬火", "回火", "退火", "正火"],
            "铸造": ["浇铸", "熔炼", "压铸"],
            "锻造": ["锻压", "锻造作业"],

            # 印刷包装类
            "印刷": ["印染", "丝印", "胶印", "凹印"],
            "复合": ["层压", "复合加工"],
            "涂布": ["涂层", "涂覆"],

            # 化工类
            "反应": ["化学反应", "合成", "加工"],
            "蒸馏": ["精馏", "分离"],
            "萃取": ["提取", "浸取"],
            "干燥": ["烘干", "脱水"],

            # 废水处理类
            "生化处理": ["好氧处理", "厌氧处理", "活性污泥法"],
            "物化处理": ["混凝", "沉淀", "过滤"],
            "深度处理": ["膜处理", "高级氧化"],
        }

    def _build_unit_conversions(self) -> Dict[str, List[UnitConversion]]:
        """构建单位转换规则"""
        conversions = {
            # 质量单位
            "mg": [
                UnitConversion("mg", "kg", 0.000001, description="毫克转千克"),
                UnitConversion("mg", "g", 0.001, description="毫克转克"),
            ],
            "g": [
                UnitConversion("g", "kg", 0.001, description="克转千克"),
                UnitConversion("g", "t", 0.000001, description="克转吨"),
            ],
            "kg": [
                UnitConversion("kg", "t", 0.001, description="千克转吨"),
            ],
            "t": [
                UnitConversion("t", "kg", 1000, description="吨转千克"),
            ],

            # 体积单位
            "mL": [
                UnitConversion("mL", "L", 0.001, description="毫升转升"),
                UnitConversion("mL", "m³", 0.000001, description="毫升转立方米"),
            ],
            "L": [
                UnitConversion("L", "m³", 0.001, description="升转立方米"),
            ],
            "m³": [
                UnitConversion("m³", "L", 1000, description="立方米转升"),
            ],

            # 浓度单位
            "mg/m³": [
                UnitConversion("mg/m³", "g/m³", 0.001, description="毫克/立方米转克/立方米"),
                UnitConversion("mg/m³", "μg/m³", 1000, description="毫克/立方米转微克/立方米"),
            ],
            "μg/m³": [
                UnitConversion("μg/m³", "mg/m³", 0.001, description="微克/立方米转毫克/立方米"),
            ],
            "mg/L": [
                UnitConversion("mg/L", "g/L", 0.001, description="毫克/升转克/升"),
                UnitConversion("mg/L", "kg/m³", 0.001, description="毫克/升转千克/立方米"),
            ],

            # 时间单位
            "h": [
                UnitConversion("h", "min", 60, description="小时转分钟"),
                UnitConversion("h", "s", 3600, description="小时转秒"),
            ],
        }
        return conversions

    def register_mapping(self, mapping: EntityMapping) -> bool:
        """
        注册实体映射

        Args:
            mapping: 实体映射

        Returns:
            是否成功
        """
        with self._lock:
            self._mappings[mapping.mapping_id] = mapping

            # 更新索引
            if mapping.internal_id not in self._internal_to_external:
                self._internal_to_external[mapping.internal_id] = set()
            self._internal_to_external[mapping.internal_id].add(mapping.external_id)
            self._external_to_internal[mapping.external_id] = mapping.internal_id

            logger.info(f"注册映射: {mapping.internal_id} -> {mapping.external_id}")
            return True

    def find_mapping(self,
                    internal_id: str = None,
                    external_id: str = None) -> Optional[EntityMapping]:
        """查找映射"""
        if internal_id:
            ext_ids = self._internal_to_external.get(internal_id, set())
            if ext_ids:
                ext_id = list(ext_ids)[0]
                for m in self._mappings.values():
                    if m.external_id == ext_id:
                        return m
        if external_id:
            int_id = self._external_to_internal.get(external_id)
            if int_id:
                for m in self._mappings.values():
                    if m.internal_id == int_id:
                        return m
        return None

    def get_external_links(self, internal_id: str) -> Set[str]:
        """获取内部节点的外部链接"""
        return self._internal_to_external.get(internal_id, set())

    def get_internal_link(self, external_id: str) -> Optional[str]:
        """获取外部节点的内部链接"""
        return self._external_to_internal.get(external_id)

    def link_process(self,
                    internal_process: str,
                    external_process: str,
                    external_source: str,
                    confidence: float = 0.9) -> Optional[EntityMapping]:
        """
        链接工艺实体

        Args:
            internal_process: 内部工艺名称
            external_process: 外部工艺名称
            external_source: 外部数据源
            confidence: 置信度

        Returns:
            映射结果
        """
        mapping_id = f"map_process_{internal_process}_{external_source}"

        # 判断映射质量
        quality = MappingQuality.MEDIUM
        if internal_process == external_process:
            quality = MappingQuality.HIGH
        elif self._is_synonym(internal_process, external_process):
            quality = MappingQuality.HIGH
            confidence = 0.95
        elif self._fuzzy_match(internal_process, external_process):
            quality = MappingQuality.MEDIUM
            confidence = 0.7

        mapping = EntityMapping(
            mapping_id=mapping_id,
            internal_id=internal_process,
            external_id=external_process,
            external_source=external_source,
            entity_type="Process",
            confidence=confidence,
            quality=quality,
            mapping_method="synonym" if self._is_synonym(internal_process, external_process) else "fuzzy"
        )

        self.register_mapping(mapping)
        return mapping

    def _is_synonym(self, term1: str, term2: str) -> bool:
        """判断是否为同义词"""
        term1_lower = term1.lower()
        term2_lower = term2.lower()

        # 直接检查
        for canonical, synonyms in self._process_synonyms.items():
            all_terms = [canonical] + synonyms
            if term1_lower in [t.lower() for t in all_terms] and \
               term2_lower in [t.lower() for t in all_terms]:
                return True

        return term1_lower == term2_lower

    def _fuzzy_match(self, term1: str, term2: str) -> bool:
        """模糊匹配"""
        # 简单的包含匹配
        term1_lower = term1.lower()
        term2_lower = term2.lower()

        if term1_lower in term2_lower or term2_lower in term1_lower:
            return True

        # 编辑距离（简单版本）
        if self._levenshtein_distance(term1_lower, term2_lower) <= 2:
            return True

        return False

    def _levenshtein_distance(self, s1: str, s2: str) -> int:
        """计算编辑距离"""
        if len(s1) < len(s2):
            return self._levenshtein_distance(s2, s1)

        if len(s2) == 0:
            return len(s1)

        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row

        return previous_row[-1]

    def convert_unit(self, value: float, from_unit: str,
                    to_unit: str) -> Optional[float]:
        """
        单位转换

        Args:
            value: 原始值
            from_unit: 原始单位
            to_unit: 目标单位

        Returns:
            转换后的值
        """
        if from_unit == to_unit:
            return value

        # 查找转换规则
        conversions = self._unit_conversions.get(from_unit, [])
        for conv in conversions:
            if conv.to_unit == to_unit:
                return value * conv.factor + conv.offset

        logger.warning(f"未找到单位转换规则: {from_unit} -> {to_unit}")
        return None

    def align_data(self,
                  source_data: Dict[str, Any],
                  target_schema: Dict[str, Any]) -> DataAlignment:
        """
        数据对齐

        将外部数据按照内部schema进行对齐。

        Args:
            source_data: 源数据
            target_schema: 目标schema

        Returns:
            对齐结果
        """
        # 简化实现
        alignment = DataAlignment(
            source_id=source_data.get("id", ""),
            target_id=target_schema.get("id", ""),
            alignment_type="schema_alignment",
            value_before=source_data,
            value_after=source_data,
            conversion_applied="none",
            confidence=1.0
        )

        return alignment

    def auto_link_processes(self, processes: List[str],
                           external_source: str) -> List[EntityMapping]:
        """
        自动链接工艺列表

        Args:
            processes: 工艺名称列表
            external_source: 外部数据源

        Returns:
            映射结果列表
        """
        mappings = []

        for process in processes:
            # 尝试在同义词表中找到匹配
            matched = False
            for canonical, synonyms in self._process_synonyms.items():
                if process.lower() in [s.lower() for s in synonyms]:
                    mapping = self.link_process(
                        internal_process=canonical,
                        external_process=process,
                        external_source=external_source,
                        confidence=0.95
                    )
                    mappings.append(mapping)
                    matched = True
                    break

            if not matched:
                # 没有匹配，创建低质量映射
                mapping = self.link_process(
                    internal_process=process,
                    external_process=process,
                    external_source=external_source,
                    confidence=0.5
                )
                mapping.quality = MappingQuality.LOW
                mappings.append(mapping)

        return mappings

    def verify_mapping(self, mapping_id: str, verified: bool,
                      verified_by: str = "") -> bool:
        """
        验证映射

        Args:
            mapping_id: 映射ID
            verified: 是否验证通过
            verified_by: 验证人

        Returns:
            是否成功
        """
        mapping = self._mappings.get(mapping_id)
        if not mapping:
            return False

        mapping.verified = verified
        mapping.verified_by = verified_by
        mapping.verified_at = datetime.now()

        return True

    def get_mapping_quality_report(self) -> Dict[str, Any]:
        """获取映射质量报告"""
        total = len(self._mappings)
        verified = len([m for m in self._mappings.values() if m.verified])

        quality_counts = {}
        for m in self._mappings.values():
            quality = m.quality.value
            quality_counts[quality] = quality_counts.get(quality, 0) + 1

        return {
            "total_mappings": total,
            "verified_mappings": verified,
            "verification_rate": verified / total if total > 0 else 0,
            "quality_distribution": quality_counts,
            "high_quality_count": quality_counts.get("high", 0),
            "medium_quality_count": quality_counts.get("medium", 0),
            "low_quality_count": quality_counts.get("low", 0),
            "pending_count": quality_counts.get("pending", 0)
        }

    def to_dict(self) -> Dict[str, Any]:
        """导出为字典"""
        return {
            "mappings_count": len(self._mappings),
            "quality_report": self.get_mapping_quality_report(),
            "synonyms_count": len(self._process_synonyms),
            "unit_conversions_count": sum(len(v) for v in self._unit_conversions.values())
        }


class GraphFusionEngine:
    """
    图谱融合引擎

    核心功能：将外部数据源深度融合到企业私有知识图谱。
    """

    def __init__(self, knowledge_graph=None, linker: EntityLinker = None,
                 emission_registry=None, env_data=None, monitoring_center=None):
        self.kg = knowledge_graph
        self.linker = linker or EntityLinker(knowledge_graph)
        self.emission_registry = emission_registry
        self.env_data = env_data
        self.monitoring_center = monitoring_center

    def fuse_external_factor(self,
                            internal_process_id: str,
                            process_name: str,
                            pollutant: str = None) -> bool:
        """
        融合外部排放系数

        在内部工艺节点上创建 :hasEmissionFactor 关系指向外部系数。

        Args:
            internal_process_id: 内部工艺节点ID
            process_name: 工艺名称
            pollutant: 污染物

        Returns:
            是否成功
        """
        if not self.kg:
            return False

        try:
            # 查找排放系数
            if self.emission_registry:
                factors = self.emission_registry.find_factors(
                    process_name=process_name,
                    pollutant=pollutant
                )

                if not factors:
                    factors = self.emission_registry.query_from_external(
                        process_name=process_name,
                        pollutant=pollutant
                    )

                for factor in factors:
                    # 创建外部系数节点
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
                            "confidence": factor.confidence
                        }
                    )

                    # 创建关系
                    self.kg.add_relation(
                        from_id=internal_process_id,
                        to_id=factor_node_id,
                        relation_type="hasEmissionFactor",
                        properties={
                            "source": "外部数据融合",
                            "link_quality": "high"
                        }
                    )

                    # 记录映射
                    self.linker.link_process(
                        internal_process=process_name,
                        external_process=f"{factor.process_name}@{factor.source}",
                        external_source=factor.source
                    )

            return True

        except Exception as e:
            logger.error(f"排放系数融合失败: {e}")
            return False

    def fuse_regional_data(self,
                          internal_region_id: str,
                          province: str,
                          year: int = None) -> int:
        """
        融合区域环境数据

        Args:
            internal_region_id: 内部区域节点ID
            province: 省份
            year: 年份

        Returns:
            融合的数据条数
        """
        if not self.kg or not self.env_data:
            return 0

        count = 0
        try:
            # 查询区域数据
            data_list = self.env_data.query_regional_data(province, year=year)

            for data in data_list:
                data_node_id = f"ext_env_{data.data_id}"
                self.kg.add_entity(
                    entity_id=data_node_id,
                    entity_type="RegionalEnvData",
                    properties={
                        "region": data.region,
                        "year": data.year,
                        "medium": data.medium.value,
                        "pollutant": data.pollutant,
                        "value": data.value,
                        "unit": data.unit,
                        "rank": data.rank,
                        "data_source": data.data_source,
                        "confidence": data.confidence
                    }
                )

                self.kg.add_relation(
                    from_id=internal_region_id,
                    to_id=data_node_id,
                    relation_type="hasEnvData",
                    properties={"year": data.year}
                )
                count += 1

            logger.info(f"融合区域环境数据: {province} - {count}条")
            return count

        except Exception as e:
            logger.error(f"区域数据融合失败: {e}")
            return 0

    def fuse_realtime_monitoring(self,
                                internal_company_id: str,
                                region: str = None) -> int:
        """
        融合实时监测数据

        Args:
            internal_company_id: 内部企业节点ID
            region: 区域

        Returns:
            融合的记录数
        """
        if not self.kg or not self.monitoring_center:
            return 0

        count = 0
        try:
            # 查询实时数据
            records = self.monitoring_center.query_realtime_data(region=region)

            for record in records:
                # 创建监测记录节点
                record_node_id = f"ext_monitor_{record.record_id}"
                self.kg.add_entity(
                    entity_id=record_node_id,
                    entity_type="MonitoringRecord",
                    properties={
                        "pollutant": record.pollutant,
                        "value": record.value,
                        "unit": record.unit,
                        "standard_value": record.standard_value,
                        "exceed_ratio": record.exceed_ratio,
                        "monitor_time": record.monitor_time.isoformat(),
                        "data_source": record.data_source
                    }
                )

                self.kg.add_relation(
                    from_id=internal_company_id,
                    to_id=record_node_id,
                    relation_type="hasMonitoringRecord",
                    properties={
                        "time": record.monitor_time.isoformat(),
                        "type": "external"
                    }
                )
                count += 1

            logger.info(f"融合实时监测数据: {count}条")
            return count

        except Exception as e:
            logger.error(f"实时监测数据融合失败: {e}")
            return 0

    def generate_cypher_for_fusion(self,
                                   entity_type: str,
                                   entity_id: str,
                                   external_data: Dict[str, Any]) -> str:
        """
        生成融合Cypher语句

        Args:
            entity_type: 实体类型
            entity_id: 实体ID
            external_data: 外部数据

        Returns:
            Cypher语句
        """
        props_str = ", ".join([f"{k}: '{v}'" for k, v in external_data.items()])
        return f"""
// 融合 {entity_type} - {entity_id}
CREATE (e:{entity_type} {{id: '{entity_id}', {props_str}, _fused_from_external: true}})
// 建立与源数据的关联
// 实际使用时替换为具体的外部数据节点关联
        """

    def full_fusion(self, internal_node_id: str,
                   node_type: str) -> Dict[str, Any]:
        """
        全面融合

        将该节点相关的所有外部数据融合到图谱。

        Args:
            internal_node_id: 内部节点ID
            node_type: 节点类型

        Returns:
            融合报告
        """
        report = {
            "internal_node": internal_node_id,
            "node_type": node_type,
            "fusions": {},
            "total_fused": 0
        }

        if node_type == "Process":
            # 获取工艺名称
            process = self.kg.get_entity(internal_node_id) if self.kg else None
            process_name = process.get("name", "") if process else ""

            # 融合排放系数
            if self.fuse_external_factor(internal_node_id, process_name):
                report["fusions"]["emission_factors"] = "success"
            else:
                report["fusions"]["emission_factors"] = "failed"

        elif node_type == "Location":
            # 获取区域
            location = self.kg.get_entity(internal_node_id) if self.kg else None
            region = location.get("name", "") if location else ""

            # 融合区域环境数据
            count = self.fuse_regional_data(internal_node_id, region)
            report["fusions"]["regional_data"] = count
            report["total_fused"] += count

        return report


# 全局单例
_linker_instance: Optional[EntityLinker] = None
_linker_lock = threading.Lock()


def get_entity_linker(knowledge_graph=None) -> EntityLinker:
    """获取实体链接器单例"""
    global _linker_instance
    if _linker_instance is None:
        with _linker_lock:
            if _linker_instance is None:
                _linker_instance = EntityLinker(knowledge_graph)
    return _linker_instance


def get_fusion_engine(knowledge_graph=None) -> GraphFusionEngine:
    """获取图谱融合引擎"""
    return GraphFusionEngine(
        knowledge_graph=knowledge_graph,
        linker=get_entity_linker(knowledge_graph)
    )
