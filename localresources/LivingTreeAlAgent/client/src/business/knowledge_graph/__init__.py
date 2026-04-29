"""
Hermes Knowledge Graph - 环评工艺知识图谱系统
==============================================

三层架构：
┌─────────────────────────────────────────────────┐
│                 应用层 (用户交互)                 │
│  • 文档上传与解析  • 结果可视化  • 专家审核     │
└───────────────────┬─────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────┐
│              服务层 (智能体调度)                  │
│  • Hermes Agent  • 大模型协同  • 知识图谱构建   │
└─────────────┬─────────────────┬─────────────────┘
              │                 │
    ┌─────────▼─────┐   ┌───────▼────────┐
    │ 信息抽取模块   │   │ 知识生成模块    │
    └───────────────┘   └─────────────────┘
              │                 │
    ┌─────────▼─────────────────▼────────┐
    │          知识存储层                 │
    │  • 图数据库  • 向量数据库  • 文档存储│
    └───────────────────────────────────┘

核心模块：
- core/: 核心实体、关系、本体定义
- agents/: 知识抽取智能体 (规则/模型/LLM三级)
- storage/: 存储层 (图数据库/向量库/对象存储)
- reasoning/: 推理引擎 (规则/嵌入/LLM)
- applications/: 应用层 (问答/报告生成/优化)
- evolution/: 持续学习循环

Author: Hermes Desktop Team
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Set, Any, Tuple
from datetime import datetime
import uuid
import json

# ============================================================
# 第一部分：核心枚举定义
# ============================================================

class EntityType(Enum):
    """实体类型枚举"""
    # 工艺类
    PROCESS = "Process"                    # 工艺过程
    PROCESS_STEP = "ProcessStep"          # 工序
    PROCESS_PARAMETER = "ProcessParameter" # 工艺参数

    # 物料类
    MATERIAL = "Material"                  # 物料
    RAW_MATERIAL = "RawMaterial"           # 原材料
    INTERMEDIATE = "Intermediate"         # 中间产品
    PRODUCT = "Product"                    # 成品
    WASTE_MATERIAL = "WasteMaterial"       # 废料

    # 设备类
    EQUIPMENT = "Equipment"               # 设备
    FACILITY = "Facility"                 # 设施
    PIPELINE = "Pipeline"                 # 管道

    # 污染物类
    POLLUTANT = "Pollutant"                # 污染物
    AIR_POLLUTANT = "AirPollutant"         # 大气污染物
    WATER_POLLUTANT = "WaterPollutant"     # 水污染物
    SOLID_WASTE = "SolidWaste"             # 固体废物
    NOISE_SOURCE = "NoiseSource"           # 噪声源

    # 环境类
    ENVIRONMENT = "Environment"            # 环境要素
    SENSITIVE_TARGET = "SensitiveTarget"  # 环境保护目标

    # 组织类
    COMPANY = "Company"                    # 企业
    FACTORY = "Factory"                    # 工厂
    DEPARTMENT = "Department"             # 部门

    # 标准类
    STANDARD = "Standard"                  # 标准
    EMISSION_STANDARD = "EmissionStandard" # 排放标准

    # 地理类
    LOCATION = "Location"                  # 位置
    AREA = "Area"                          # 区域


class RelationType(Enum):
    """关系类型枚举"""
    # 工艺链关系
    PRECEDES = "precedes"                  # 前驱工序
    SUCCEEDS = "succeeds"                  # 后继工序
    PARALLEL_WITH = "parallel_with"        # 并行工序
    REQUIRES = "requires"                  # 必要工序
    CONTAINS = "contains"                  # 包含工序

    # 物料流关系
    INPUT_OF = "input_of"                  # 输入物料
    OUTPUT_OF = "output_of"                # 输出物料
    CONSUMES = "consumes"                  # 消耗物料
    PRODUCES = "produces"                  # 产生物料
    TRANSFORMS_TO = "transforms_to"        # 转化为

    # 污染关系
    EMITS = "emits"                        # 产生污染物
    CONTROLS = "controls"                  # 控制污染物
    TRANSFERS_TO = "transfers_to"          # 转移
    DISCHARGES_TO = "discharges_to"        # 排放至

    # 设备关系
    INSTALLED_AT = "installed_at"          # 安装在
    OPERATES = "operates"                  # 操作
    MAINTAINS = "maintains"                # 维护
    CONNECTED_TO = "connected_to"          # 连接到

    # 参数关系
    HAS_PARAMETER = "has_parameter"        # 有参数
    AFFECTS = "affects"                    # 影响

    # 位置关系
    LOCATED_IN = "located_in"              # 位于
    ADJACENT_TO = "adjacent_to"            # 相邻

    # 参照关系
    COMPLIES_WITH = "complies_with"       # 符合标准
    SIMILAR_TO = "similar_to"             # 类似于


class PollutantType(Enum):
    """污染物类型"""
    # 大气污染物
    PARTICULATE = "particulate"            # 颗粒物
    VOC = "voc"                           # 挥发性有机物
    SOX = "sox"                          # 硫氧化物
    NOX = "nox"                          # 氮氧化物
    CO = "co"                            # 一氧化碳
    CO2 = "co2"                          # 二氧化碳
    NH3 = "nh3"                          # 氨气

    # 水污染物
    COD = "cod"                          # 化学需氧量
    BOD = "bod"                          # 生化需氧量
    SS = "ss"                            # 悬浮物
    NH3_N = "nh3_n"                      # 氨氮
    TN = "tn"                            # 总氮
    TP = "tp"                            # 总磷
    OIL = "oil"                          # 石油类
    HEAVY_METAL = "heavy_metal"          # 重金属

    # 固体废物
    HAZARDOUS_WASTE = "hazardous_waste"  # 危险废物
    GENERAL_WASTE = "general_waste"      # 一般固废
    SLAG = "slag"                        # 废渣
    SLUDGE = "sludge"                    # 污泥


class ProcessType(Enum):
    """工艺类型"""
    # 表面处理
    SURFACE_TREATMENT = "surface_treatment"       # 表面处理
    SHOT_BLASTING = "shot_blasting"               # 喷砂/喷丸
    GRINDING = "grinding"                         # 打磨
    POLISHING = "polishing"                      # 抛光
    COATING = "coating"                           # 涂装
    PAINTING = "painting"                        # 喷漆
    SPRAY_COATING = "spray_coating"              # 喷涂

    # 热处理
    HEAT_TREATMENT = "heat_treatment"           # 热处理
    QUENCHING = "quenching"                     # 淬火
    TEMPERING = "tempering"                     # 回火
    ANNEALING = "annealing"                     # 退火

    # 焊接加工
    WELDING = "welding"                         # 焊接
    ARC_WELDING = "arc_welding"                 # 电弧焊
    GAS_WELDING = "gas_welding"                 # 气焊

    # 机械加工
    MACHINING = "machining"                     # 机械加工
    MILLING = "milling"                         # 铣削
    TURNING = "turning"                         # 车削
    DRILLING = "drilling"                       # 钻孔

    # 铸造
    CASTING = "casting"                         # 铸造
    MELTING = "melting"                         # 熔炼
    POURING = "pouring"                         # 浇注

    # 化工
    CHEMICAL = "chemical"                       # 化工
    MIXING = "mixing"                           # 混合
    REACTION = "reaction"                       # 反应
    DISTILLATION = "distillation"               # 蒸馏

    # 预处理
    PRETREATMENT = "pretreatment"              # 预处理
    DEGREASING = "deg degreasing"             # 脱脂
    CLEANING = "cleaning"                     # 清洗
    PHOSPHATING = "phosphating"               # 磷化


class ConfidenceLevel(Enum):
    """置信度级别"""
    HIGH = 0.9     # 高置信度 (规则抽取)
    MEDIUM = 0.8   # 中置信度 (模型抽取)
    LOW = 0.7      # 低置信度 (LLM抽取)
    UNCERTAIN = 0.5  # 不确定


class KnowledgeSource(Enum):
    """知识来源"""
    RULE_EXTRACTION = "rule_extraction"      # 规则抽取
    MODEL_EXTRACTION = "model_extraction"    # 模型抽取
    LLM_EXTRACTION = "llm_extraction"       # LLM抽取
    MANUAL_INPUT = "manual_input"            # 人工输入
    EXPERT_REVIEW = "expert_review"          # 专家审核
    USER_FEEDBACK = "user_feedback"          # 用户反馈


# ============================================================
# 第二部分：核心数据类
# ============================================================

@dataclass
class Coordinate:
    """坐标/位置"""
    longitude: Optional[float] = None
    latitude: Optional[float] = None
    altitude: Optional[float] = None
    address: Optional[str] = None


@dataclass
class TimeRange:
    """时间范围"""
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    duration_hours: Optional[float] = None
    duration_days: Optional[float] = None


@dataclass
class ParameterRange:
    """参数范围"""
    min_value: float
    max_value: float
    typical_value: Optional[float] = None
    unit: str = ""


@dataclass
class EmissionStandard:
    """排放标准"""
    standard_id: str
    standard_name: str
    pollutant: str
    limit_value: float
    unit: str
    standard_type: str = "GB"  # GB/GHZB/DB


# ============================================================
# 第三部分：实体类
# ============================================================

@dataclass
class Entity:
    """实体基类"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    entity_type: EntityType = EntityType.PROCESS
    description: str = ""
    properties: Dict[str, Any] = field(default_factory=dict)
    aliases: List[str] = field(default_factory=list)  # 别名/简称
    source: KnowledgeSource = KnowledgeSource.RULE_EXTRACTION
    confidence: float = 0.9
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "entity_type": self.entity_type.value,
            "description": self.description,
            "properties": self.properties,
            "aliases": self.aliases,
            "source": self.source.value,
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'Entity':
        data = data.copy()
        data['entity_type'] = EntityType(data.get('entity_type', 'PROCESS'))
        data['source'] = KnowledgeSource(data.get('source', 'RULE_EXTRACTION'))
        data.pop('created_at', None)
        data.pop('updated_at', None)
        return cls(**data)


@dataclass
class Process(Entity):
    """工艺过程实体"""
    process_type: ProcessType = ProcessType.SURFACE_TREATMENT
    duration_hours: Optional[float] = None
    temperature: Optional[float] = None
    temperature_unit: str = "℃"
    pressure: Optional[float] = None
    pressure_unit: str = "MPa"
    energy_consumption: Optional[float] = None
    energy_unit: str = "kWh"
    equipment_list: List[str] = field(default_factory=list)
    material_input: List[str] = field(default_factory=list)
    material_output: List[str] = field(default_factory=list)
    steps: List['ProcessStep'] = field(default_factory=list)

    def __post_init__(self):
        self.entity_type = EntityType.PROCESS
        self.properties.update({
            "process_type": self.process_type.value,
            "duration_hours": self.duration_hours,
            "temperature": self.temperature,
            "pressure": self.pressure,
            "energy_consumption": self.energy_consumption,
            "equipment_list": self.equipment_list,
            "material_input": self.material_input,
            "material_output": self.material_output
        })


@dataclass
class ProcessStep:
    """工艺步骤"""
    step_id: str
    name: str
    description: str = ""
    order: int = 0
    duration_minutes: Optional[float] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    pollutants_emitted: List[str] = field(default_factory=list)
    equipment_needed: List[str] = field(default_factory=list)


@dataclass
class Material(Entity):
    """物料实体"""
    material_type: str = "raw"  # raw/intermediate/product/waste
    state: str = "solid"  # solid/liquid/gas
    composition: List[Dict[str, float]] = field(default_factory=list)  # 成分
    hazard_class: Optional[str] = None  # 危险类别
    cas_number: Optional[str] = None  # CAS号
    quantity: Optional[float] = None
    unit: str = "kg"

    def __post_init__(self):
        self.entity_type = EntityType.MATERIAL
        self.properties.update({
            "material_type": self.material_type,
            "state": self.state,
            "composition": self.composition,
            "hazard_class": self.hazard_class,
            "cas_number": self.cas_number,
            "quantity": self.quantity
        })


@dataclass
class Equipment(Entity):
    """设备实体"""
    equipment_type: str = ""
    model: Optional[str] = None
    capacity: Optional[float] = None
    capacity_unit: str = ""
    supplier: Optional[str] = None
    installation_date: Optional[datetime] = None
    location: Optional[str] = None

    def __post_init__(self):
        self.entity_type = EntityType.EQUIPMENT
        self.properties.update({
            "equipment_type": self.equipment_type,
            "model": self.model,
            "capacity": self.capacity,
            "supplier": self.supplier,
            "location": self.location
        })


@dataclass
class Pollutant(Entity):
    """污染物实体"""
    pollutant_type: PollutantType = PollutantType.PARTICULATE
    code: Optional[str] = None  # 污染物编号
    cas_number: Optional[str] = None
    emission_amount: Optional[float] = None
    emission_unit: str = "kg/h"
    concentration: Optional[float] = None
    concentration_unit: str = "mg/m³"
    emission_standard: Optional[str] = None
    toxicity: Optional[str] = None  # 毒性描述
    environmental_effect: Optional[str] = None  # 环境影响

    def __post_init__(self):
        self.entity_type = EntityType.POLLUTANT
        self.properties.update({
            "pollutant_type": self.pollutant_type.value,
            "code": self.code,
            "emission_amount": self.emission_amount,
            "concentration": self.concentration,
            "emission_standard": self.emission_standard,
            "toxicity": self.toxicity
        })


@dataclass
class EmissionStandard2(Entity):
    """排放标准实体"""
    standard_id: str = ""
    standard_type: str = "GB"  # GB/GHZB/DB
    scope: str = ""  # 适用范围
    pollutant_list: List[Dict] = field(default_factory=list)  # 污染物限值列表

    def __post_init__(self):
        self.entity_type = EntityType.EMISSION_STANDARD
        self.properties.update({
            "standard_id": self.standard_id,
            "standard_type": self.standard_type,
            "scope": self.scope,
            "pollutant_list": self.pollutant_list
        })


# ============================================================
# 第四部分：关系类
# ============================================================

@dataclass
class Relation:
    """关系类"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_id: str = ""
    target_id: str = ""
    relation_type: RelationType = RelationType.PRECEDES
    properties: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.9
    source: KnowledgeSource = KnowledgeSource.RULE_EXTRACTION
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation_type": self.relation_type.value,
            "properties": self.properties,
            "confidence": self.confidence,
            "source": self.source.value,
            "created_at": self.created_at.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'Relation':
        data = data.copy()
        data['relation_type'] = RelationType(data.get('relation_type', 'PRECEDES'))
        data['source'] = KnowledgeSource(data.get('source', 'RULE_EXTRACTION'))
        data.pop('created_at', None)
        return cls(**data)


# ============================================================
# 第五部分：知识图谱类
# ============================================================

@dataclass
class KnowledgeGraph:
    """知识图谱"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "unnamed"
    description: str = ""
    entities: Dict[str, Entity] = field(default_factory=dict)
    relations: Dict[str, Relation] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # 索引缓存
    _name_index: Dict[str, List[str]] = field(default_factory=dict, repr=False)
    _type_index: Dict[EntityType, List[str]] = field(default_factory=dict, repr=False)
    _relation_index: Dict[Tuple[str, RelationType], List[str]] = field(default_factory=dict, repr=False)

    def add_entity(self, entity: Entity) -> None:
        """添加实体"""
        self.entities[entity.id] = entity
        self._build_indices(entity)

    def add_relation(self, relation: Relation) -> None:
        """添加关系"""
        self.relations[relation.id] = relation
        # 更新关系索引
        key = (relation.source_id, relation.relation_type)
        if key not in self._relation_index:
            self._relation_index[key] = []
        self._relation_index[key].append(relation.id)

    def _build_indices(self, entity: Entity) -> None:
        """构建索引"""
        # 名称索引
        name_key = entity.name.lower()
        if name_key not in self._name_index:
            self._name_index[name_key] = []
        self._name_index[name_key].append(entity.id)

        # 类型索引
        if entity.entity_type not in self._type_index:
            self._type_index[entity.entity_type] = []
        self._type_index[entity.entity_type].append(entity.id)

    def get_entity_by_name(self, name: str) -> Optional[Entity]:
        """按名称查找实体"""
        name_key = name.lower()
        entity_ids = self._name_index.get(name_key, [])
        if entity_ids:
            return self.entities.get(entity_ids[0])
        return None

    def get_entities_by_type(self, entity_type: EntityType) -> List[Entity]:
        """按类型查找实体"""
        entity_ids = self._type_index.get(entity_type, [])
        return [self.entities[eid] for eid in entity_ids if eid in self.entities]

    def get_neighbors(self, entity_id: str, relation_type: Optional[RelationType] = None) -> List[Tuple[Entity, Relation]]:
        """获取邻居实体"""
        results = []
        for rel in self.relations.values():
            if rel.source_id == entity_id:
                target = self.entities.get(rel.target_id)
                if target and (relation_type is None or rel.relation_type == relation_type):
                    results.append((target, rel))
        return results

    def get_process_chain(self, start_process: str, max_depth: int = 10) -> List[Entity]:
        """获取工艺链"""
        chain = []
        visited = set()
        current = start_process
        depth = 0

        while current and depth < max_depth:
            if current in visited:
                break
            visited.add(current)
            entity = self.entities.get(current)
            if entity:
                chain.append(entity)
            # 查找后继工序
            successors = self.get_neighbors(current, RelationType.SUCCEEDS)
            if successors:
                current = successors[0][0].id
            else:
                break
            depth += 1

        return chain

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "entities": {k: v.to_dict() for k, v in self.entities.items()},
            "relations": {k: v.to_dict() for k, v in self.relations.items()},
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'KnowledgeGraph':
        """从字典创建"""
        kg = cls(
            id=data.get('id', str(uuid.uuid4())),
            name=data.get('name', 'unnamed'),
            description=data.get('description', ''),
            metadata=data.get('metadata', {})
        )

        for eid, edata in data.get('entities', {}).items():
            entity = Entity.from_dict(edata)
            kg.add_entity(entity)

        for rid, rdata in data.get('relations', {}).items():
            relation = Relation.from_dict(rdata)
            kg.add_relation(relation)

        return kg

    def merge(self, other: 'KnowledgeGraph', strategy: str = "confidence") -> None:
        """合并另一个知识图谱"""
        # 合并实体
        for eid, entity in other.entities.items():
            if eid in self.entities:
                if strategy == "confidence" and entity.confidence > self.entities[eid].confidence:
                    self.entities[eid] = entity
            else:
                self.add_entity(entity)

        # 合并关系
        for rid, relation in other.relations.items():
            if rid not in self.relations:
                self.add_relation(relation)

        self.updated_at = datetime.now()


# ============================================================
# 第六部分：知识验证器
# ============================================================

@dataclass
class ValidationResult:
    """验证结果"""
    is_valid: bool
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    fixes_applied: List[str] = field(default_factory=list)


class KnowledgeValidator:
    """知识验证器"""

    # 工艺参数合理性范围
    PROCESS_CONSTRAINTS = {
        "temperature": {"min": -50, "max": 2000, "unit": "℃"},
        "pressure": {"min": -0.1, "max": 100, "unit": "MPa"},
        "duration": {"min": 0.1, "max": 720, "unit": "h"}
    }

    def validate(self, kg: KnowledgeGraph) -> ValidationResult:
        """多维度验证"""
        issues = []
        warnings = []
        fixes = []

        # 一致性检查
        issues.extend(self.check_consistency(kg))

        # 完整性检查
        issues.extend(self.check_completeness(kg))

        # 合理性检查
        issues.extend(self.check_plausibility(kg))

        # 专家规则检查
        issues.extend(self.check_expert_rules(kg))

        # 自动修复
        kg, fix_list = self.auto_fix(kg, issues)
        fixes.extend(fix_list)

        return ValidationResult(
            is_valid=len(issues) == 0,
            issues=issues,
            warnings=warnings,
            fixes_applied=fixes
        )

    def check_consistency(self, kg: KnowledgeGraph) -> List[str]:
        """一致性检查"""
        issues = []

        for entity in kg.entities.values():
            # 检查自环关系
            for rel in kg.relations.values():
                if rel.source_id == rel.target_id:
                    issues.append(f"实体{entity.name}存在自环关系")

            # 检查孤立实体
            if not kg.get_neighbors(entity.id):
                issues.append(f"实体{entity.name}是孤立的，无关联关系")

        return issues

    def check_completeness(self, kg: KnowledgeGraph) -> List[str]:
        """完整性检查"""
        issues = []

        # 检查关键实体是否有名称
        for entity in kg.entities.values():
            if not entity.name:
                issues.append(f"实体{entity.id}缺少名称")

        # 检查工艺链是否完整
        processes = kg.get_entities_by_type(EntityType.PROCESS)
        for proc in processes:
            predecessors = kg.get_neighbors(proc.id, RelationType.PRECEDES)
            successors = kg.get_neighbors(proc.id, RelationType.SUCCEEDS)
            if not predecessors and not successors and len(processes) > 1:
                issues.append(f"工艺{proc.name}是孤立的，未接入工艺链")

        return issues

    def check_plausibility(self, kg: KnowledgeGraph) -> List[str]:
        """合理性检查"""
        issues = []

        for entity in kg.entities.values():
            if isinstance(entity, Process):
                # 温度检查
                if entity.temperature:
                    if entity.temperature > 1500 or entity.temperature < -100:
                        issues.append(f"工艺{entity.name}温度{entity.temperature}℃异常")

                # 压力检查
                if entity.pressure:
                    if entity.pressure > 50 or entity.pressure < -0.05:
                        issues.append(f"工艺{entity.name}压力{entity.pressure}异常")

                # 时长检查
                if entity.duration_hours:
                    if entity.duration_hours > 168:  # 7天
                        issues.append(f"工艺{entity.name}时长{entity.duration_hours}小时过长")

        return issues

    def check_expert_rules(self, kg: KnowledgeGraph) -> List[str]:
        """专家规则检查"""
        issues = []

        # 规则1：喷砂后必须有清洁工序
        sandblasting = kg.get_entity_by_name("喷砂")
        if sandblasting:
            successors = kg.get_neighbors(sandblasting.id, RelationType.SUCCEEDS)
            has_cleaning = any("清洁" in str(s[0].name) for s in successors)
            if not has_cleaning:
                issues.append("喷砂后缺少清洁工序")

        # 规则2：喷漆后必须有固化工序
        painting = kg.get_entity_by_name("喷漆")
        if painting:
            successors = kg.get_neighbors(painting.id, RelationType.SUCCEEDS)
            has_curing = any("固化" in str(s[0].name) for s in successors)
            if not has_curing:
                issues.append("喷漆后缺少固化工序")

        return issues

    def auto_fix(self, kg: KnowledgeGraph, issues: List[str]) -> Tuple[KnowledgeGraph, List[str]]:
        """自动修复"""
        fixes = []

        # 修复孤立工艺（添加虚拟连接）
        processes = kg.get_entities_by_type(EntityType.PROCESS)
        if len(processes) > 1:
            # 尝试按名称顺序连接
            sorted_procs = sorted(processes, key=lambda p: p.name)
            for i in range(len(sorted_procs) - 1):
                p1, p2 = sorted_procs[i], sorted_procs[i + 1]
                # 检查是否已存在关系
                existing = kg.get_neighbors(p1.id, RelationType.SUCCEEDS)
                if not any(s[0].id == p2.id for s in existing):
                    # 添加关系
                    rel = Relation(
                        source_id=p1.id,
                        target_id=p2.id,
                        relation_type=RelationType.SUCCEEDS,
                        source=KnowledgeSource.RULE_EXTRACTION
                    )
                    kg.add_relation(rel)
                    fixes.append(f"自动连接工艺链: {p1.name} -> {p2.name}")

        return kg, fixes


# ============================================================
# 第七部分：本体定义
# ============================================================

class Ontology:
    """环评工艺知识图谱本体"""

    # 实体类型定义
    ENTITY_DEFINITIONS = {
        EntityType.PROCESS: {
            "description": "工艺过程",
            "required_properties": ["name", "process_type"],
            "optional_properties": ["temperature", "pressure", "duration", "equipment"]
        },
        EntityType.MATERIAL: {
            "description": "物料",
            "required_properties": ["name", "material_type"],
            "optional_properties": ["state", "composition", "hazard_class"]
        },
        EntityType.EQUIPMENT: {
            "description": "设备",
            "required_properties": ["name", "equipment_type"],
            "optional_properties": ["model", "capacity", "location"]
        },
        EntityType.POLLUTANT: {
            "description": "污染物",
            "required_properties": ["name", "pollutant_type"],
            "optional_properties": ["emission_amount", "concentration", "standard"]
        }
    }

    # 关系定义
    RELATION_DEFINITIONS = {
        RelationType.PRECEDES: {
            "description": "前驱工序",
            "domain": EntityType.PROCESS,
            "range": EntityType.PROCESS,
            "inverse": RelationType.SUCCEEDS
        },
        RelationType.INPUT_OF: {
            "description": "输入物料",
            "domain": EntityType.MATERIAL,
            "range": EntityType.PROCESS
        },
        RelationType.OUTPUT_OF: {
            "description": "产出物料",
            "domain": EntityType.MATERIAL,
            "range": EntityType.PROCESS
        },
        RelationType.EMITS: {
            "description": "产生污染物",
            "domain": EntityType.PROCESS,
            "range": EntityType.POLLUTANT
        },
        RelationType.CONTROLS: {
            "description": "控制污染物",
            "domain": EntityType.EQUIPMENT,
            "range": EntityType.POLLUTANT
        }
    }

    # 推理规则
    INFERENCE_RULES = [
        {
            "name": "喷砂_requires_清洁",
            "if": {"entity_type": EntityType.PROCESS, "name": "喷砂"},
            "then": {"relation": RelationType.REQUIRES, "target_type": "清洁"}
        },
        {
            "name": "喷漆_requires_固化",
            "if": {"entity_type": EntityType.PROCESS, "name": "喷漆"},
            "then": {"relation": RelationType.REQUIRES, "target_type": "固化"}
        },
        {
            "name": "焊接_emits_NOx",
            "if": {"entity_type": EntityType.PROCESS, "name_pattern": "焊接"},
            "then": {"emits": {"name": "NOx", "type": PollutantType.NOX}}
        }
    ]

    @classmethod
    def get_entity_schema(cls, entity_type: EntityType) -> Dict:
        """获取实体类型定义"""
        return cls.ENTITY_DEFINITIONS.get(entity_type, {})

    @classmethod
    def get_relation_schema(cls, relation_type: RelationType) -> Dict:
        """获取关系定义"""
        return cls.RELATION_DEFINITIONS.get(relation_type, {})


# ============================================================
# 第八部分：工具函数
# ============================================================

def create_process_chain(processes: List[str], kg: Optional[KnowledgeGraph] = None) -> KnowledgeGraph:
    """创建工艺链"""
    if kg is None:
        kg = KnowledgeGraph(name="工艺链")

    prev_id = None
    for name in processes:
        # 创建或获取工艺实体
        existing = kg.get_entity_by_name(name)
        if existing:
            proc_id = existing.id
        else:
            proc = Process(name=name)
            kg.add_entity(proc)
            proc_id = proc.id

        # 添加工艺链关系
        if prev_id:
            rel = Relation(
                source_id=prev_id,
                target_id=proc_id,
                relation_type=RelationType.SUCCEEDS
            )
            kg.add_relation(rel)

        prev_id = proc_id

    return kg


def export_to_cypher(kg: KnowledgeGraph) -> str:
    """导出为Cypher查询"""
    queries = []

    # 创建约束
    queries.append("// 创建约束")
    queries.append("CREATE CONSTRAINT IF NOT EXISTS ON (p:Process) ASSERT p.id IS UNIQUE;")
    queries.append("CREATE CONSTRAINT IF NOT EXISTS ON (m:Material) ASSERT m.id IS UNIQUE;")
    queries.append("CREATE CONSTRAINT IF NOT EXISTS ON (e:Equipment) ASSERT e.id IS UNIQUE;")
    queries.append("CREATE CONSTRAINT IF NOT EXISTS ON (pol:Pollutant) ASSERT pol.id IS UNIQUE;")
    queries.append("")

    # 创建实体
    queries.append("// 创建实体")
    for entity in kg.entities.values():
        label = entity.entity_type.value
        props = json.dumps(entity.to_dict(), ensure_ascii=False)
        queries.append(f'CREATE (:{label} {{{props}}})')

    # 创建关系
    queries.append("")
    queries.append("// 创建关系")
    for rel in kg.relations.values():
        src = kg.entities.get(rel.source_id)
        tgt = kg.entities.get(rel.target_id)
        if src and tgt:
            rel_type = rel.relation_type.value.upper()
            queries.append(f"""
MATCH (a:{{src.entity_type.value}} {{id: '{src.id}'}})
MATCH (b:{{tgt.entity_type.value}} {{id: '{tgt.id}'}})
CREATE (a)-[:{rel_type}]->(b)
""")

    return "\n".join(queries)


def export_to_graphviz(kg: KnowledgeGraph) -> str:
    """导出为Graphviz DOT格式"""
    lines = ["digraph KnowledgeGraph {", '  rankdir=LR;', '  node [shape=box];']

    # 节点定义
    for entity in kg.entities.values():
        label = entity.name.replace('"', '\\"')
        color = {
            EntityType.PROCESS: "lightblue",
            EntityType.MATERIAL: "lightgreen",
            EntityType.EQUIPMENT: "lightyellow",
            EntityType.POLLUTANT: "lightpink"
        }.get(entity.entity_type, "lightgray")

        lines.append(f'  "{entity.id}" [label="{label}" fillcolor={color} style=filled];')

    # 关系定义
    for rel in kg.relations.values():
        rel_label = rel.relation_type.value
        lines.append(f'  "{rel.source_id}" -> "{rel.target_id}" [label="{rel_label}"];')

    lines.append("}")
    return "\n".join(lines)


# 导出
__all__ = [
    # 枚举
    'EntityType', 'RelationType', 'PollutantType', 'ProcessType',
    'ConfidenceLevel', 'KnowledgeSource',

    # 数据类
    'Coordinate', 'TimeRange', 'ParameterRange', 'EmissionStandard',

    # 实体类
    'Entity', 'Process', 'ProcessStep', 'Material', 'Equipment',
    'Pollutant', 'EmissionStandard2',

    # 关系类
    'Relation',

    # 知识图谱
    'KnowledgeGraph', 'KnowledgeValidator', 'ValidationResult', 'Ontology',

    # 工具函数
    'create_process_chain', 'export_to_cypher', 'export_to_graphviz'
]
