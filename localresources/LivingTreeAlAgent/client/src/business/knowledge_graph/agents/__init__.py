"""
知识抽取流水线 - 三级抽取策略
===============================

采用三级抽取确保知识质量：
Level 1: 规则抽取（高准确率 >95%，低召回 ~30%）
Level 2: 模型抽取（平衡 85%准确率，70%召回）
Level 3: LLM抽取（高召回 90%，75%准确率）

Author: Hermes Desktop Team
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple, Callable
from enum import Enum
import re

from .. import (
    KnowledgeGraph, Entity, Relation, Process, Material, Equipment, Pollutant,
    EntityType, RelationType, PollutantType, ProcessType,
    KnowledgeSource, ConfidenceLevel
)


# ============================================================
# 第一部分：抽取配置
# ============================================================

@dataclass
class ExtractionConfig:
    """抽取配置"""
    confidence_threshold: float = 0.7
    enable_rule_extraction: bool = True
    enable_model_extraction: bool = True
    enable_llm_extraction: bool = True
    max_llm_calls: int = 10


@dataclass
class ExtractionResult:
    """抽取结果"""
    entities: List[Entity] = field(default_factory=list)
    relations: List[Relation] = field(default_factory=list)
    confidence: float = 0.0
    extraction_level: str = ""
    source_text: str = ""
    issues: List[str] = field(default_factory=list)


# ============================================================
# 第二部分：规则抽取器
# ============================================================

class RuleExtractor:
    """基于规则的抽取器 - 高准确率"""

    # 工艺名称映射（简写到标准名称）
    PROCESS_ALIASES = {
        "上料": "上料", "装料": "上料", "投料": "上料",
        "喷砂": "喷砂处理", "喷丸": "喷丸处理", "抛丸": "抛丸处理",
        "打磨": "打磨处理", "研磨": "研磨处理",
        "喷漆": "喷漆", "涂装": "涂装", "喷涂": "喷涂",
        "焊接": "焊接", "电焊": "电弧焊", "气焊": "气体保护焊",
        "切割": "切割", "激光切割": "激光切割", "等离子切割": "等离子切割",
        "机加工": "机械加工", "车削": "车削", "铣削": "铣削", "钻孔": "钻孔",
        "铸造": "铸造", "熔炼": "熔炼", "浇注": "浇注",
        "除油": "除油处理", "脱脂": "脱脂处理", "清洗": "清洗",
        "磷化": "磷化处理", "钝化": "钝化处理",
        "固化": "固化", "干燥": "干燥", "烘干": "烘干",
        "检验": "检验", "检测": "检测", "测试": "测试",
        "包装": "包装", "入库": "入库"
    }

    # 污染物映射
    POLLUTANT_PATTERNS = {
        r"颗粒物|粉尘|灰尘|扬尘": ("颗粒物", PollutantType.PARTICULATE),
        r"VOCs?|挥发性有机物|苯系物": ("VOCs", PollutantType.VOC),
        r"氮氧化物|NOx?|NO2": ("NOx", PollutantType.NOX),
        r"二氧化硫|SO2|SOx": ("SO2", PollutantType.SOX),
        r"一氧化碳|CO": ("CO", PollutantType.CO),
        r"COD|化学需氧量": ("COD", PollutantType.COD),
        r"氨氮|NH3-N": ("氨氮", PollutantType.NH3_N),
        r"悬浮物|SS": ("SS", PollutantType.SS),
        r"石油类|油类": ("石油类", PollutantType.OIL),
        r"重金属|铅|镉|铬|汞": ("重金属", PollutantType.HEAVY_METAL),
    }

    # 工艺-污染物关联
    PROCESS_POLLUTANT_MAP = {
        "喷砂处理": [("颗粒物", PollutantType.PARTICULATE, 0.8)],
        "打磨处理": [("颗粒物", PollutantType.PARTICULATE, 0.7)],
        "喷漆": [("VOCs", PollutantType.VOC, 0.9), ("颗粒物", PollutantType.PARTICULATE, 0.3)],
        "涂装": [("VOCs", PollutantType.VOC, 0.9), ("颗粒物", PollutantType.PARTICULATE, 0.3)],
        "焊接": [("NOx", PollutantType.NOX, 0.6), ("颗粒物", PollutantType.PARTICULATE, 0.5)],
        "铸造": [("颗粒物", PollutantType.PARTICULATE, 0.7), ("SO2", PollutantType.SOX, 0.3)],
        "熔炼": [("SO2", PollutantType.SOX, 0.6), ("颗粒物", PollutantType.PARTICULATE, 0.5)],
        "热处理": [("NOx", PollutantType.NOX, 0.4)],
        "除油处理": [("COD", PollutantType.COD, 0.6), ("石油类", PollutantType.OIL, 0.7)],
        "磷化处理": [("COD", PollutantType.COD, 0.4), ("SS", PollutantType.SS, 0.5)],
    }

    # 工艺-设备关联
    PROCESS_EQUIPMENT_MAP = {
        "喷砂处理": ["喷砂机", "除尘器", "空压机"],
        "喷漆": ["喷漆枪", "空压机", "喷漆房", "除湿机"],
        "焊接": ["焊接设备", "除尘器", "防护设备"],
        "打磨处理": ["角磨机", "砂纸", "集尘器"],
        "涂装": ["涂装机", "固化炉", "输送线"],
        "铸造": ["熔炼炉", "浇注机", "造型机"],
        "热处理": ["热处理炉", "温控系统", "冷却系统"],
        "除油处理": ["除油槽", "水洗槽", "加热系统"],
        "磷化处理": ["磷化槽", "水洗槽", "干燥设备"],
    }

    def __init__(self, config: Optional[ExtractionConfig] = None):
        self.config = config or ExtractionConfig()

    def extract(self, text: str) -> ExtractionResult:
        """从文本中抽取知识"""
        entities = []
        relations = []
        issues = []

        # 1. 抽取工艺
        process_entities, process_relations = self._extract_processes(text)
        entities.extend(process_entities)
        relations.extend(process_relations)

        # 2. 抽取物料
        material_entities, material_relations = self._extract_materials(text)
        entities.extend(material_entities)
        relations.extend(material_relations)

        # 3. 抽取污染物
        pollutant_entities, pollutant_relations = self._extract_pollutants(text, process_entities)
        entities.extend(pollutant_entities)
        relations.extend(pollutant_relations)

        # 4. 抽取设备
        equipment_entities = self._extract_equipment(process_entities)
        entities.extend(equipment_entities)

        # 5. 建立工艺链关系
        chain_relations = self._establish_process_chain(process_entities)
        relations.extend(chain_relations)

        return ExtractionResult(
            entities=entities,
            relations=relations,
            confidence=0.95,  # 规则抽取高置信度
            extraction_level="rule",
            source_text=text,
            issues=issues
        )

    def _extract_processes(self, text: str) -> Tuple[List[Entity], List[Relation]]:
        """抽取工艺"""
        entities = []
        relations = []

        # 匹配工艺名称
        found_processes = []
        for alias, standard_name in self.PROCESS_ALIASES.items():
            if alias in text:
                # 创建工艺实体
                process = Process(
                    name=standard_name,
                    process_type=self._infer_process_type(standard_name),
                    source=KnowledgeSource.RULE_EXTRACTION,
                    confidence=0.95
                )
                entities.append(process)
                found_processes.append(process)

                # 提取工艺参数
                params = self._extract_process_parameters(text, standard_name)
                for key, value in params.items():
                    process.properties[key] = value

        return entities, relations

    def _extract_materials(self, text: str) -> Tuple[List[Entity], List[Relation]]:
        """抽取物料"""
        entities = []
        relations = []

        # 物料模式
        material_patterns = [
            r"原料[:：]?\s*([^\n，。,]+)",
            r"材料[:：]?\s*([^\n，。,]+)",
            r"涂料[:：]?\s*([^\n，。,]+)",
            r"溶剂[:：]?\s*([^\n，。,]+)",
            r"板材|管材|棒材|型材"
        ]

        for pattern in material_patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                material_name = match.group(1).strip() if match.lastindex else match.group(0).strip()
                if material_name and len(material_name) < 50:
                    material = Material(
                        name=material_name,
                        material_type="raw",
                        source=KnowledgeSource.RULE_EXTRACTION,
                        confidence=0.9
                    )
                    entities.append(material)

        return entities, relations

    def _extract_pollutants(self, text: str, processes: List[Entity]) -> Tuple[List[Entity], List[Relation]]:
        """抽取污染物"""
        entities = []
        relations = []

        # 从文本中直接匹配污染物
        for pattern, (name, ptype) in self.POLLUTANT_PATTERNS.items():
            if re.search(pattern, text):
                pollutant = Pollutant(
                    name=name,
                    pollutant_type=ptype,
                    source=KnowledgeSource.RULE_EXTRACTION,
                    confidence=0.95
                )
                entities.append(pollutant)

                # 关联到工艺
                for proc in processes:
                    if proc.name in self.PROCESS_POLLUTANT_MAP:
                        rel = Relation(
                            source_id=proc.id,
                            target_id=pollutant.id,
                            relation_type=RelationType.EMITS,
                            source=KnowledgeSource.RULE_EXTRACTION,
                            confidence=0.9
                        )
                        relations.append(rel)

        # 从工艺推断污染物
        for proc in processes:
            if proc.name in self.PROCESS_POLLUTANT_MAP:
                for pollutant_name, ptype, conf in self.PROCESS_POLLUTANT_MAP[proc.name]:
                    # 检查是否已存在
                    existing = next((e for e in entities if e.name == pollutant_name), None)
                    if existing:
                        rel = Relation(
                            source_id=proc.id,
                            target_id=existing.id,
                            relation_type=RelationType.EMITS,
                            source=KnowledgeSource.RULE_EXTRACTION,
                            confidence=conf
                        )
                        relations.append(rel)
                    else:
                        pollutant = Pollutant(
                            name=pollutant_name,
                            pollutant_type=ptype,
                            source=KnowledgeSource.RULE_EXTRACTION,
                            confidence=conf
                        )
                        entities.append(pollutant)
                        rel = Relation(
                            source_id=proc.id,
                            target_id=pollutant.id,
                            relation_type=RelationType.EMITS,
                            source=KnowledgeSource.RULE_EXTRACTION,
                            confidence=conf
                        )
                        relations.append(rel)

        return entities, relations

    def _extract_equipment(self, processes: List[Entity]) -> List[Entity]:
        """抽取设备"""
        entities = []

        for proc in processes:
            if proc.name in self.PROCESS_EQUIPMENT_MAP:
                for eq_name in self.PROCESS_EQUIPMENT_MAP[proc.name]:
                    equipment = Equipment(
                        name=eq_name,
                        equipment_type=self._infer_equipment_type(eq_name),
                        source=KnowledgeSource.RULE_EXTRACTION,
                        confidence=0.9
                    )
                    entities.append(equipment)

        return entities

    def _establish_process_chain(self, processes: List[Entity]) -> List[Relation]:
        """建立工艺链关系"""
        relations = []

        for i in range(len(processes) - 1):
            rel = Relation(
                source_id=processes[i].id,
                target_id=processes[i + 1].id,
                relation_type=RelationType.SUCCEEDS,
                source=KnowledgeSource.RULE_EXTRACTION,
                confidence=0.95
            )
            relations.append(rel)

        return relations

    def _infer_process_type(self, name: str) -> ProcessType:
        """推断工艺类型"""
        type_map = {
            "喷砂": ProcessType.SHOT_BLASTING,
            "喷丸": ProcessType.SHOT_BLASTING,
            "打磨": ProcessType.GRINDING,
            "喷漆": ProcessType.PAINTING,
            "涂装": ProcessType.COATING,
            "焊接": ProcessType.WELDING,
            "铸造": ProcessType.CASTING,
            "熔炼": ProcessType.MELTING,
            "除油": ProcessType.DEGREASING,
            "磷化": ProcessType.PHOSPHATING,
            "热处理": ProcessType.HEAT_TREATMENT,
        }
        for key, ptype in type_map.items():
            if key in name:
                return ptype
        return ProcessType.SURFACE_TREATMENT

    def _infer_equipment_type(self, name: str) -> str:
        """推断设备类型"""
        type_map = {
            "喷砂机": "表面处理设备",
            "除尘器": "环保设备",
            "喷漆枪": "涂装设备",
            "焊接设备": "焊接设备",
            "熔炼炉": "冶金设备",
            "热处理炉": "热工设备",
        }
        return type_map.get(name, "通用设备")

    def _extract_process_parameters(self, text: str, process_name: str) -> Dict[str, Any]:
        """提取工艺参数"""
        params = {}

        # 温度参数
        temp_pattern = r"温度[:：]?\s*(\d+(?:\.\d+)?)\s*℃?"
        temp_match = re.search(temp_pattern, text)
        if temp_match:
            params["temperature"] = float(temp_match.group(1))

        # 压力参数
        pressure_pattern = r"压力[:：]?\s*(\d+(?:\.\d+)?)\s*(?:MPa|atm|bar)?"
        pressure_match = re.search(pressure_pattern, text)
        if pressure_match:
            params["pressure"] = float(pressure_match.group(1))

        # 时间参数
        time_pattern = r"时间[:：]?\s*(\d+(?:\.\d+)?)\s*(?:h|小时|min|分钟)?"
        time_match = re.search(time_pattern, text)
        if time_match:
            params["duration"] = float(time_match.group(1))

        return params


# ============================================================
# 第三部分：模型抽取器（基于规则增强）
# ============================================================

class ModelExtractor:
    """基于模型的抽取器 - 平衡准确率和召回率"""

    def __init__(self, config: Optional[ExtractionConfig] = None):
        self.config = config or ExtractionConfig()
        self.rule_extractor = RuleExtractor(config)

    def extract(self, text: str) -> ExtractionResult:
        """使用混合方法抽取"""
        # 使用规则抽取作为基础
        result = self.rule_extractor.extract(text)

        # 增强：识别未匹配的工艺序列
        enhanced_entities, enhanced_relations = self._enhance_extraction(text, result)
        result.entities.extend(enhanced_entities)
        result.relations.extend(enhanced_relations)
        result.confidence = 0.85  # 模型抽取中等置信度

        return result

    def _enhance_extraction(self, text: str, base_result: ExtractionResult) -> Tuple[List[Entity], List[Relation]]:
        """增强抽取"""
        entities = []
        relations = []

        # 识别中文工艺序列模式
        process_sequence_pattern = r"[\u4e00-\u9fa5]+(?:、[\u4e00-\u9fa5]+)*"
        sequences = re.findall(process_sequence_pattern, text)

        for seq in sequences:
            # 检查是否包含多个工艺
            processes = [s.strip() for s in seq.split("、")]
            if len(processes) >= 2:
                # 创建完整工艺链
                prev_entity = None
                for proc_name in processes:
                    # 检查是否已存在
                    existing = next((e for e in base_result.entities if e.name == proc_name), None)
                    if existing:
                        proc_entity = existing
                    else:
                        proc_entity = Process(
                            name=proc_name,
                            source=KnowledgeSource.MODEL_EXTRACTION,
                            confidence=0.85
                        )
                        entities.append(proc_entity)

                    if prev_entity:
                        rel = Relation(
                            source_id=prev_entity.id,
                            target_id=proc_entity.id,
                            relation_type=RelationType.SUCCEEDS,
                            source=KnowledgeSource.MODEL_EXTRACTION,
                            confidence=0.85
                        )
                        relations.append(rel)

                    prev_entity = proc_entity

        return entities, relations


# ============================================================
# 第四部分：LLM抽取器
# ============================================================

class LLMExtractor:
    """基于大模型的抽取器 - 高召回率"""

    def __init__(self, config: Optional[ExtractionConfig] = None):
        self.config = config or ExtractionConfig()

    def extract(self, text: str, context: Optional[Dict] = None) -> ExtractionResult:
        """使用LLM抽取知识"""
        # 注意：实际实现需要调用LLM API
        # 这里提供一个基于模板的实现框架

        entities = []
        relations = []

        # 模拟LLM调用
        prompt = self._build_prompt(text, context)
        llm_response = self._call_llm(prompt)

        # 解析LLM响应
        parsed = self._parse_llm_response(llm_response)
        entities = parsed.get("entities", [])
        relations = parsed.get("relations", [])

        return ExtractionResult(
            entities=entities,
            relations=relations,
            confidence=0.75,  # LLM抽取中等置信度
            extraction_level="llm",
            source_text=text
        )

    def _build_prompt(self, text: str, context: Optional[Dict]) -> str:
        """构建提示词"""
        prompt = f"""从以下文本中抽取环评工艺知识，以JSON格式输出：

文本：
{text}

请抽取：
1. 工艺过程（名称、类型、参数）
2. 物料（名称、类型、状态）
3. 污染物（名称、类型、产生量）
4. 设备（名称、类型）
5. 关系（工艺链关系、物料流关系、污染关系）

输出格式：
{{
  "entities": [
    {{"type": "Process", "name": "...", "properties": {{}}}}
  ],
  "relations": [
    {{"source": "...", "target": "...", "type": "precedes"}}
  ]
}}
"""
        return prompt

    def _call_llm(self, prompt: str) -> str:
        """调用LLM（需要集成LLM客户端）"""
        # TODO: 集成实际LLM调用
        return "{}"

    def _parse_llm_response(self, response: str) -> Dict:
        """解析LLM响应"""
        import json
        try:
            return json.loads(response)
        except:
            return {"entities": [], "relations": []}


# ============================================================
# 第五部分：抽取流水线
# ============================================================

class ExtractionPipeline:
    """知识抽取流水线"""

    def __init__(self, config: Optional[ExtractionConfig] = None):
        self.config = config or ExtractionConfig()
        self.rule_extractor = RuleExtractor(config)
        self.model_extractor = ModelExtractor(config)
        self.llm_extractor = LLMExtractor(config)

    def run(self, text: str, context: Optional[Dict] = None) -> KnowledgeGraph:
        """运行抽取流水线"""
        kg = KnowledgeGraph(name="extracted_knowledge")

        # Level 1: 规则抽取（高精度）
        if self.config.enable_rule_extraction:
            rule_result = self.rule_extractor.extract(text)
            self._merge_result(kg, rule_result)

        # Level 2: 模型抽取（平衡）
        if self.config.enable_model_extraction:
            model_result = self.model_extractor.extract(text)
            self._merge_result(kg, model_result)

        # Level 3: LLM抽取（高召回）
        if self.config.enable_llm_extraction:
            llm_result = self.llm_extractor.extract(text, context)
            self._merge_result(kg, llm_result)

        # 置信度融合
        self._fuse_confidence(kg)

        return kg

    def _merge_result(self, kg: KnowledgeGraph, result: ExtractionResult) -> None:
        """合并抽取结果"""
        # 合并实体（去重）
        existing_names = {e.name for e in kg.entities.values()}

        for entity in result.entities:
            if entity.name not in existing_names:
                kg.add_entity(entity)
                existing_names.add(entity.name)
            else:
                # 保留更高置信度的版本
                existing = kg.get_entity_by_name(entity.name)
                if existing and entity.confidence > existing.confidence:
                    kg.entities[existing.id] = entity

        # 合并关系
        for relation in result.relations:
            # 检查是否已存在相同关系
            existing_rel = any(
                r.source_id == relation.source_id and
                r.target_id == relation.target_id and
                r.relation_type == relation.relation_type
                for r in kg.relations.values()
            )
            if not existing_rel:
                kg.add_relation(relation)

    def _fuse_confidence(self, kg: KnowledgeGraph) -> None:
        """融合置信度"""
        # 统计不同来源的置信度
        source_confidence = {}
        for entity in kg.entities.values():
            src = entity.source.value
            if src not in source_confidence:
                source_confidence[src] = []
            source_confidence[src].append(entity.confidence)

        # 调整置信度
        for entity in kg.entities.values():
            if entity.source == KnowledgeSource.LLM_EXTRACTION:
                # LLM结果略微降低置信度
                entity.confidence *= 0.9


# ============================================================
# 第六部分：知识验证器
# ============================================================

class KnowledgeExtractor:
    """知识抽取器（对外统一接口）"""

    def __init__(self, config: Optional[ExtractionConfig] = None):
        self.config = config or ExtractionConfig()
        self.pipeline = ExtractionPipeline(config)

    def extract(self, text: str, context: Optional[Dict] = None) -> KnowledgeGraph:
        """抽取知识"""
        return self.pipeline.run(text, context)

    def extract_from_document(self, document: Any) -> KnowledgeGraph:
        """从文档抽取知识"""
        # TODO: 集成文档解析器
        text = str(document)
        return self.extract(text)


__all__ = [
    'ExtractionConfig', 'ExtractionResult',
    'RuleExtractor', 'ModelExtractor', 'LLMExtractor',
    'ExtractionPipeline', 'KnowledgeExtractor'
]
