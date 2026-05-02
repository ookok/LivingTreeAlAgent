"""
推理引擎 - 三层推理策略
=========================

1. 规则推理 (RuleReasoner) - 基于预定义规则的因果推理
2. 嵌入推理 (EmbeddingReasoner) - 基于向量相似度的知识补全
3. LLM推理 (LLMReasoner) - 基于大模型的复杂推理

Author: Hermes Desktop Team
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple, Callable
import random

from .. import (
    KnowledgeGraph, Entity, Relation, Process, Pollutant,
    EntityType, RelationType, ProcessType, PollutantType, KnowledgeSource
)


# ============================================================
# 第一部分：推理结果
# ============================================================

@dataclass
class ReasoningResult:
    """推理结果"""
    inferred_entities: List[Entity] = field(default_factory=list)
    inferred_relations: List[Relation] = field(default_factory=list)
    confidence: float = 0.0
    reasoning_type: str = ""
    explanation: str = ""
    evidence: List[str] = field(default_factory=list)


# ============================================================
# 第二部分：规则推理引擎
# ============================================================

class RuleReasoner:
    """基于规则的推理引擎"""

    # 工艺因果链规则
    PROCESS_RULES = [
        {
            "name": "喷砂后必须清洁",
            "condition": lambda e: "喷砂" in e.name,
            "action": {"type": "require", "target": "清洁"},
            "confidence": 0.95
        },
        {
            "name": "喷漆后必须流平+固化",
            "condition": lambda e: "喷漆" in e.name,
            "action": {"type": "require_sequence", "targets": ["流平", "固化"]},
            "confidence": 0.95
        },
        {
            "name": "固化后必须冷却",
            "condition": lambda e: "固化" in e.name,
            "action": {"type": "require", "target": "冷却"},
            "confidence": 0.9
        },
        {
            "name": "打磨后必须表面清洁",
            "condition": lambda e: "打磨" in e.name,
            "action": {"type": "require", "target": "表面清洁"},
            "confidence": 0.9
        },
        {
            "name": "除油后必须水洗",
            "condition": lambda e: "除油" in e.name,
            "action": {"type": "require", "target": "水洗"},
            "confidence": 0.9
        },
        {
            "name": "磷化后必须水洗+干燥",
            "condition": lambda e: "磷化" in e.name,
            "action": {"type": "require_sequence", "targets": ["水洗", "干燥"]},
            "confidence": 0.9
        },
        {
            "name": "热处理后必须冷却",
            "condition": lambda e: "热处理" in e.name,
            "action": {"type": "require", "target": "冷却"},
            "confidence": 0.85
        },
    ]

    # 污染物产生规则
    POLLUTANT_RULES = [
        {
            "name": "喷砂产生颗粒物",
            "condition": lambda e: "喷砂" in e.name,
            "pollutant": {"name": "颗粒物", "type": PollutantType.PARTICULATE, "amount": "0.5-1.2kg/h"},
            "confidence": 0.95
        },
        {
            "name": "打磨产生颗粒物",
            "condition": lambda e: "打磨" in e.name,
            "pollutant": {"name": "颗粒物", "type": PollutantType.PARTICULATE, "amount": "0.3-0.8kg/h"},
            "confidence": 0.95
        },
        {
            "name": "喷漆产生VOCs",
            "condition": lambda e: "喷漆" in e.name,
            "pollutant": {"name": "VOCs", "type": PollutantType.VOC, "amount": "1-3kg/h"},
            "confidence": 0.95
        },
        {
            "name": "焊接产生NOx",
            "condition": lambda e: "焊接" in e.name,
            "pollutant": {"name": "NOx", "type": PollutantType.NOX, "amount": "0.1-0.5kg/h"},
            "confidence": 0.85
        },
        {
            "name": "焊接产生颗粒物",
            "condition": lambda e: "焊接" in e.name,
            "pollutant": {"name": "颗粒物", "type": PollutantType.PARTICULATE, "amount": "0.2-0.6kg/h"},
            "confidence": 0.9
        },
        {
            "name": "铸造产生颗粒物",
            "condition": lambda e: "铸造" in e.name,
            "pollutant": {"name": "颗粒物", "type": PollutantType.PARTICULATE, "amount": "0.5-1.5kg/h"},
            "confidence": 0.9
        },
        {
            "name": "熔炼产生SO2",
            "condition": lambda e: "熔炼" in e.name,
            "pollutant": {"name": "SO2", "type": PollutantType.SOX, "amount": "0.3-1.0kg/h"},
            "confidence": 0.85
        },
        {
            "name": "除油产生COD",
            "condition": lambda e: "除油" in e.name,
            "pollutant": {"name": "COD", "type": PollutantType.COD, "amount": "0.5-2.0kg/h"},
            "confidence": 0.9
        },
        {
            "name": "除油产生石油类",
            "condition": lambda e: "除油" in e.name,
            "pollutant": {"name": "石油类", "type": PollutantType.OIL, "amount": "0.2-1.0kg/h"},
            "confidence": 0.9
        },
    ]

    # 设备推荐规则
    EQUIPMENT_RULES = [
        {
            "name": "喷砂设备",
            "condition": lambda e: "喷砂" in e.name,
            "equipment": ["喷砂机", "除尘器", "空压机", "砂料回收系统"],
            "confidence": 0.95
        },
        {
            "name": "喷漆设备",
            "condition": lambda e: "喷漆" in e.name,
            "equipment": ["喷漆枪", "空压机", "喷漆房", "除湿机", "废气处理系统"],
            "confidence": 0.95
        },
        {
            "name": "打磨设备",
            "condition": lambda e: "打磨" in e.name,
            "equipment": ["角磨机", "砂纸/砂轮", "集尘器", "防护设备"],
            "confidence": 0.95
        },
        {
            "name": "焊接设备",
            "condition": lambda e: "焊接" in e.name,
            "equipment": ["焊接电源", "焊枪", "保护气", "除尘器", "防护设备"],
            "confidence": 0.95
        },
        {
            "name": "固化设备",
            "condition": lambda e: "固化" in e.name,
            "equipment": ["固化炉", "温控系统", "输送系统"],
            "confidence": 0.9
        },
    ]

    def reason(self, kg: KnowledgeGraph) -> ReasoningResult:
        """执行规则推理"""
        inferred_entities = []
        inferred_relations = []
        evidence = []
        confidence_sum = 0
        count = 0

        # 遍历所有工艺实体
        for entity in kg.entities.values():
            if entity.entity_type != EntityType.PROCESS:
                continue

            # 应用工艺规则
            for rule in self.PROCESS_RULES:
                if rule["condition"](entity):
                    action = rule["action"]
                    if action["type"] == "require":
                        target_name = action["target"]
                        inferred_entity, inferred_rel = self._create_requirement(
                            entity, target_name, rule["confidence"]
                        )
                        inferred_entities.append(inferred_entity)
                        inferred_relations.append(inferred_rel)
                        evidence.append(f"{entity.name} {rule['name']}")
                        confidence_sum += rule["confidence"]
                        count += 1
                    elif action["type"] == "require_sequence":
                        for i, target_name in enumerate(action["targets"]):
                            inferred_entity, inferred_rel = self._create_requirement(
                                entity, target_name, rule["confidence"]
                            )
                            if i > 0:
                                # 序列中的前一个
                                prev_target = action["targets"][i - 1]
                            inferred_entities.append(inferred_entity)
                            inferred_relations.append(inferred_rel)
                            evidence.append(f"{entity.name} {rule['name']}: {target_name}")

            # 应用污染物规则
            for rule in self.POLLUTANT_RULES:
                if rule["condition"](entity):
                    pollutant = self._create_pollutant(rule["pollutant"], rule["confidence"])
                    inferred_entities.append(pollutant)
                    rel = Relation(
                        source_id=entity.id,
                        target_id=pollutant.id,
                        relation_type=RelationType.EMITS,
                        confidence=rule["confidence"],
                        source=KnowledgeSource.RULE_EXTRACTION
                    )
                    inferred_relations.append(rel)
                    evidence.append(f"{entity.name} {rule['name']}")
                    confidence_sum += rule["confidence"]
                    count += 1

            # 应用设备规则
            for rule in self.EQUIPMENT_RULES:
                if rule["condition"](entity):
                    for eq_name in rule["equipment"]:
                        equipment = self._create_equipment(eq_name)
                        inferred_entities.append(equipment)
                        rel = Relation(
                            source_id=entity.id,
                            target_id=equipment.id,
                            relation_type=RelationType.OPERATES,
                            confidence=rule["confidence"],
                            source=KnowledgeSource.RULE_EXTRACTION
                        )
                        inferred_relations.append(rel)
                        evidence.append(f"{entity.name} 使用 {eq_name}")

        avg_confidence = confidence_sum / count if count > 0 else 0.8

        return ReasoningResult(
            inferred_entities=inferred_entities,
            inferred_relations=inferred_relations,
            confidence=avg_confidence,
            reasoning_type="rule",
            explanation=f"基于{len(evidence)}条规则进行推理",
            evidence=evidence
        )

    def _create_requirement(self, source: Entity, target_name: str, confidence: float) -> Tuple[Entity, Relation]:
        """创建必要工序"""
        from .. import Process
        process = Process(
            name=target_name,
            process_type=ProcessType.SURFACE_TREATMENT,
            source=KnowledgeSource.RULE_EXTRACTION,
            confidence=confidence
        )
        rel = Relation(
            source_id=source.id,
            target_id=process.id,
            relation_type=RelationType.REQUIRES,
            confidence=confidence,
            source=KnowledgeSource.RULE_EXTRACTION
        )
        return process, rel

    def _create_pollutant(self, pollutant_info: Dict, confidence: float) -> Pollutant:
        """创建污染物"""
        return Pollutant(
            name=pollutant_info["name"],
            pollutant_type=PollutantType(pollutant_info["type"].value),
            emission_amount=pollutant_info.get("amount"),
            source=KnowledgeSource.RULE_EXTRACTION,
            confidence=confidence
        )

    def _create_equipment(self, name: str) -> Entity:
        """创建设备"""
        from .. import Equipment
        return Equipment(
            name=name,
            equipment_type="工艺设备",
            source=KnowledgeSource.RULE_EXTRACTION,
            confidence=0.9
        )


# ============================================================
# 第三部分：嵌入推理引擎
# ============================================================

class EmbeddingReasoner:
    """基于向量嵌入的推理"""

    def __init__(self, dimension: int = 384):
        self.dimension = dimension
        self._entity_vectors: Dict[str, List[float]] = {}

    def reason(self, kg: KnowledgeGraph, target_entity: Optional[Entity] = None) -> ReasoningResult:
        """基于嵌入的推理"""
        inferred_entities = []
        inferred_relations = []
        evidence = []

        # 为实体生成向量
        self._generate_vectors(kg)

        # 如果没有目标实体，推理缺失的工序
        if target_entity is None:
            inferred_entities, inferred_relations = self._infer_missing_processes(kg)
            evidence.append("基于向量相似度推断缺失工序")
        else:
            # 查找相似实体
            similar = self._find_similar_entities(kg, target_entity)
            for entity, score in similar[:3]:
                evidence.append(f"与{entity.name}相似度: {score:.2f}")

        return ReasoningResult(
            inferred_entities=inferred_entities,
            inferred_relations=inferred_relations,
            confidence=0.8,
            reasoning_type="embedding",
            explanation="基于向量嵌入的相似度推理",
            evidence=evidence
        )

    def _generate_vectors(self, kg: KnowledgeGraph) -> None:
        """生成实体向量（简化实现）"""
        for entity in kg.entities.values():
            if entity.id not in self._entity_vectors:
                # 简化的向量生成：基于名称的hash
                import hashlib
                name_bytes = entity.name.encode('utf-8')
                hash_obj = hashlib.md5(name_bytes)
                # 用hash值初始化向量
                vector = [0.0] * self.dimension
                for i, byte in enumerate(hash_obj.digest()):
                    vector[i % self.dimension] += byte / 255.0
                # 归一化
                norm = sum(v * v for v in vector) ** 0.5
                if norm > 0:
                    vector = [v / norm for v in vector]
                self._entity_vectors[entity.id] = vector

    def _infer_missing_processes(self, kg: KnowledgeGraph) -> Tuple[List[Entity], List[Relation]]:
        """推断缺失工序"""
        inferred = []
        inferred_rels = []

        # 获取所有工艺
        processes = kg.get_entities_by_type(EntityType.PROCESS)
        if len(processes) < 2:
            return inferred, inferred_rels

        # 检查相邻工序之间是否缺失常见工序
        for i in range(len(processes) - 1):
            p1, p2 = processes[i], processes[i + 1]

            # 如果是喷砂后面没有清洁
            if "喷砂" in p1.name and not any("清洁" in p.name for p in processes[i + 1:]):
                inferred.append(Process(
                    name="清洁",
                    process_type=ProcessType.CLEANING,
                    source=KnowledgeSource.MODEL_EXTRACTION,
                    confidence=0.85
                ))

            # 如果是打磨后面没有表面清洁
            if "打磨" in p1.name and not any("表面清洁" in p.name for p in processes[i + 1:]):
                inferred.append(Process(
                    name="表面清洁",
                    process_type=ProcessType.CLEANING,
                    source=KnowledgeSource.MODEL_EXTRACTION,
                    confidence=0.85
                ))

            # 如果是喷漆后面没有流平/固化
            if "喷漆" in p1.name:
                if not any("流平" in p.name for p in processes[i + 1:]):
                    inferred.append(Process(
                        name="流平",
                        process_type=ProcessType.COATING,
                        source=KnowledgeSource.MODEL_EXTRACTION,
                        confidence=0.85
                    ))
                if not any("固化" in p.name for p in processes[i + 1:]):
                    inferred.append(Process(
                        name="固化",
                        process_type=ProcessType.COATING,
                        source=KnowledgeSource.MODEL_EXTRACTION,
                        confidence=0.85
                    ))

        return inferred, inferred_rels

    def _find_similar_entities(self, kg: KnowledgeGraph, target: Entity) -> List[Tuple[Entity, float]]:
        """查找相似实体"""
        if target.id not in self._entity_vectors:
            self._generate_vectors(kg)

        target_vec = self._entity_vectors.get(target.id, [0.0] * self.dimension)
        similarities = []

        for entity in kg.entities.values():
            if entity.id == target.id:
                continue
            if entity.id in self._entity_vectors:
                sim = self._cosine_similarity(target_vec, self._entity_vectors[entity.id])
                similarities.append((entity, sim))

        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities

    def _cosine_similarity(self, v1: List[float], v2: List[float]) -> float:
        """计算余弦相似度"""
        dot = sum(a * b for a, b in zip(v1, v2))
        norm1 = sum(a * a for a in v1) ** 0.5
        norm2 = sum(b * b for b in v2) ** 0.5
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot / (norm1 * norm2)


# ============================================================
# 第四部分：LLM推理引擎
# ============================================================

class LLMReasoner:
    """基于大模型的推理引擎"""

    def __init__(self, llm_client: Optional[Any] = None):
        self.llm_client = llm_client

    def reason(self, kg: KnowledgeGraph, query: str) -> ReasoningResult:
        """使用LLM进行推理"""
        # 构建提示词
        prompt = self._build_prompt(kg, query)

        # 调用LLM（这里提供框架，实际需要集成LLM客户端）
        response = self._call_llm(prompt)

        # 解析响应
        result = self._parse_response(response, kg)

        return result

    def _build_prompt(self, kg: KnowledgeGraph, query: str) -> str:
        """构建推理提示词"""
        # 将知识图谱转换为文本
        kg_text = self._kg_to_text(kg)

        prompt = f"""你是一位资深的环评工艺工程师。请基于以下工艺知识图谱进行推理。

知识图谱：
{kg_text}

需要解决的问题：
{query}

请按照以下步骤推理：
1. 分析现有信息的完整性
2. 推断可能缺失的环节
3. 预测合理的工艺参数
4. 识别潜在的环境风险
5. 提出优化建议

请以JSON格式输出推理结果：
{{
  "inferred_entities": [
    {{"name": "...", "type": "...", "properties": {{}}}}
  ],
  "inferred_relations": [
    {{"source": "...", "target": "...", "type": "..."}}
  ],
  "explanation": "推理过程解释",
  "confidence": 0.85
}}
"""
        return prompt

    def _kg_to_text(self, kg: KnowledgeGraph) -> str:
        """将知识图谱转换为文本"""
        lines = ["## 工艺实体"]

        for entity in kg.entities.values():
            lines.append(f"- {entity.name} ({entity.entity_type.value})")
            if entity.properties:
                for key, value in entity.properties.items():
                    lines.append(f"  - {key}: {value}")

        lines.append("\n## 关系")
        for rel in kg.relations.values():
            src = kg.entities.get(rel.source_id)
            tgt = kg.entities.get(rel.target_id)
            if src and tgt:
                lines.append(f"- {src.name} --[{rel.relation_type.value}]--> {tgt.name}")

        return "\n".join(lines)

    def _call_llm(self, prompt: str) -> str:
        """调用LLM"""
        # TODO: 集成实际LLM调用
        # 这里返回一个空结果作为框架
        return "{}"

    def _parse_response(self, response: str, kg: KnowledgeGraph) -> ReasoningResult:
        """解析LLM响应"""
        import json
        try:
            data = json.loads(response)
            inferred_entities = []
            inferred_relations = []

            for e_data in data.get("inferred_entities", []):
                entity = Entity(
                    name=e_data["name"],
                    entity_type=EntityType[e_data["type"].upper()] if e_data["type"] else EntityType.PROCESS,
                    properties=e_data.get("properties", {}),
                    source=KnowledgeSource.LLM_EXTRACTION,
                    confidence=data.get("confidence", 0.75)
                )
                inferred_entities.append(entity)

            for r_data in data.get("inferred_relations", []):
                src = kg.get_entity_by_name(r_data["source"])
                tgt = kg.get_entity_by_name(r_data["target"])
                if src and tgt:
                    rel = Relation(
                        source_id=src.id,
                        target_id=tgt.id,
                        relation_type=RelationType(r_data["type"]),
                        source=KnowledgeSource.LLM_EXTRACTION,
                        confidence=data.get("confidence", 0.75)
                    )
                    inferred_relations.append(rel)

            return ReasoningResult(
                inferred_entities=inferred_entities,
                inferred_relations=inferred_relations,
                confidence=data.get("confidence", 0.75),
                reasoning_type="llm",
                explanation=data.get("explanation", ""),
                evidence=[f"LLM推理: {data.get('explanation', '')}"]
            )
        except:
            return ReasoningResult(
                inferred_entities=[],
                inferred_relations=[],
                confidence=0.5,
                reasoning_type="llm",
                explanation="LLM响应解析失败",
                evidence=[]
            )


# ============================================================
# 第五部分：混合推理管理器
# ============================================================

class ReasoningEngine:
    """混合推理引擎"""

    def __init__(self, llm_client: Optional[Any] = None):
        self.rule_reasoner = RuleReasoner()
        self.embedding_reasoner = EmbeddingReasoner()
        self.llm_reasoner = LLMReasoner(llm_client)

    def reason(self, kg: KnowledgeGraph, strategy: str = "hybrid", query: Optional[str] = None) -> ReasoningResult:
        """
        执行推理

        Args:
            kg: 知识图谱
            strategy: 推理策略 (rule/embedding/llm/hybrid)
            query: 查询字符串（用于LLM推理）
        """
        if strategy == "rule":
            return self.rule_reasoner.reason(kg)
        elif strategy == "embedding":
            return self.embedding_reasoner.reason(kg)
        elif strategy == "llm":
            if query:
                return self.llm_reasoner.reason(kg, query)
            else:
                return self.embedding_reasoner.reason(kg)
        else:  # hybrid
            # 综合多种推理结果
            return self._hybrid_reason(kg, query)

    def _hybrid_reason(self, kg: KnowledgeGraph, query: Optional[str]) -> ReasoningResult:
        """混合推理"""
        all_entities = []
        all_relations = []
        evidence = []
        total_confidence = 0
        count = 0

        # 规则推理
        rule_result = self.rule_reasoner.reason(kg)
        all_entities.extend(rule_result.inferred_entities)
        all_relations.extend(rule_result.inferred_relations)
        evidence.extend(rule_result.evidence)
        total_confidence += rule_result.confidence * len(rule_result.evidence)
        count += len(rule_result.evidence)

        # 嵌入推理
        embed_result = self.embedding_reasoner.reason(kg)
        all_entities.extend(embed_result.inferred_entities)
        all_relations.extend(embed_result.inferred_relations)
        evidence.extend(embed_result.evidence)
        total_confidence += embed_result.confidence * len(embed_result.evidence)
        count += len(embed_result.evidence)

        # 去重
        seen_entities = set()
        unique_entities = []
        for e in all_entities:
            if e.name not in seen_entities:
                seen_entities.add(e.name)
                unique_entities.append(e)

        seen_relations = set()
        unique_relations = []
        for r in all_relations:
            key = (r.source_id, r.target_id, r.relation_type.value)
            if key not in seen_relations:
                seen_relations.add(key)
                unique_relations.append(r)

        avg_confidence = total_confidence / count if count > 0 else 0.8

        return ReasoningResult(
            inferred_entities=unique_entities,
            inferred_relations=unique_relations,
            confidence=avg_confidence,
            reasoning_type="hybrid",
            explanation=f"混合推理，综合{len(evidence)}条推理证据",
            evidence=evidence
        )

    def complete_knowledge_graph(self, kg: KnowledgeGraph) -> KnowledgeGraph:
        """补全知识图谱"""
        result = self.reason(kg, strategy="hybrid")

        # 添加推断的实体
        for entity in result.inferred_entities:
            if not kg.get_entity_by_name(entity.name):
                kg.add_entity(entity)

        # 添加推断的关系
        for relation in result.inferred_relations:
            existing = any(
                r.source_id == relation.source_id and
                r.target_id == relation.target_id and
                r.relation_type == relation.relation_type
                for r in kg.relations.values()
            )
            if not existing:
                kg.add_relation(relation)

        return kg


__all__ = [
    'ReasoningResult', 'RuleReasoner', 'EmbeddingReasoner',
    'LLMReasoner', 'ReasoningEngine'
]
