"""
ConceptNode - 抽象概念节点

实现"举一反三"能力的核心组件：
- 从具体经验中提取抽象概念
- 将新问题与已知概念匹配
- 验证概念在当前场景的适用性

借鉴人类文明的抽象与符号化能力：
具体经验 → 抽象概念 → 应用场景

Author: LivingTreeAI Agent
Date: 2026-04-28
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger
import time


class RelationType(Enum):
    """概念关系类型"""
    IS_A = "is_a"           # 是一种
    PART_OF = "part_of"     # 属于
    LEADS_TO = "leads_to"   # 导致
    ENABLES = "enables"     # 使能
    OPPOSES = "opposes"     # 对立
    SIMILAR_TO = "similar_to" # 相似
    EXAMPLE_OF = "example_of" # 是...的例子


@dataclass
class ConceptNode:
    """
    抽象概念节点
    
    代表一个从具体经验中抽象出来的概念，如"杠杆原理"、"供需定律"等。
    """
    name: str                    # 概念名称（如"杠杆原理"）
    definition: str = ""         # 定义描述
    preconditions: List[str] = field(default_factory=list)  # 适用前提条件
    not_applicable: List[str] = field(default_factory=list) # 不适用场景
    confidence: float = 0.0      # 抽象置信度 (0-1)
    examples: List[str] = field(default_factory=list)       # 具体应用案例
    related_concepts: List[str] = field(default_factory=list) # 相关概念
    created_at: float = field(default_factory=lambda: time.time())
    updated_at: float = field(default_factory=lambda: time.time())
    
    def is_applicable(self, context: str) -> float:
        """
        判断概念在当前上下文是否适用
        
        Args:
            context: 当前场景描述
            
        Returns:
            适用度 (0-1)
        """
        # 检查不适用场景
        for not_applicable_condition in self.not_applicable:
            if not_applicable_condition.lower() in context.lower():
                return 0.0
        
        # 检查适用前提
        matched_conditions = 0
        for condition in self.preconditions:
            if condition.lower() in context.lower():
                matched_conditions += 1
        
        if not self.preconditions:
            # 没有前提条件，默认适用
            return min(0.5 + self.confidence * 0.5, 1.0)
        
        # 计算适用度
        condition_score = matched_conditions / len(self.preconditions)
        return min(condition_score * self.confidence, 1.0)
    
    def add_example(self, example: str):
        """添加应用案例"""
        if example not in self.examples:
            self.examples.append(example)
            self.updated_at = time.time()
    
    def update_confidence(self, evidence: str, supports: bool):
        """根据证据更新置信度"""
        if supports:
            self.confidence = min(self.confidence + 0.05, 1.0)
        else:
            self.confidence = max(self.confidence - 0.1, 0.0)
        self.updated_at = time.time()


@dataclass
class ConceptRelation:
    """
    概念之间的关系
    
    描述两个概念之间的语义关系。
    """
    source: str                 # 源概念名称
    target: str                 # 目标概念名称
    relation_type: RelationType # 关系类型
    confidence: float = 0.0     # 关系置信度 (0-1)
    evidence: List[str] = field(default_factory=list) # 证据支持


class ConceptGraph:
    """
    概念图谱
    
    存储和管理抽象概念及其关系，支持：
    1. 概念的添加和查询
    2. 概念匹配（根据上下文找到最适用的概念）
    3. 关系推理
    """
    
    def __init__(self):
        self._logger = logger.bind(component="ConceptGraph")
        self._concepts: Dict[str, ConceptNode] = {}
        self._relations: List[ConceptRelation] = []
        
        # 预定义一些基础概念
        self._init_basic_concepts()
        
        self._logger.info("✅ ConceptGraph 初始化完成")
    
    def _init_basic_concepts(self):
        """初始化基础概念"""
        # 杠杆原理
        self.add_concept(ConceptNode(
            name="杠杆原理",
            definition="通过支点放大力的原理，力臂越长，所需力越小",
            preconditions=["支点", "力臂", "力"],
            not_applicable=["无支点", "柔性材料"],
            confidence=0.95,
            examples=["用撬棍撬石头", "剪刀剪东西", "跷跷板"]
        ))
        
        # 供需定律
        self.add_concept(ConceptNode(
            name="供需定律",
            definition="需求增加导致价格上升，供应增加导致价格下降",
            preconditions=["市场", "价格", "需求", "供应"],
            not_applicable=["非市场化", "垄断"],
            confidence=0.92,
            examples=["iPhone发布导致黄牛涨价", "产能过剩导致价格下跌"]
        ))
        
        # 边际效应
        self.add_concept(ConceptNode(
            name="边际效应",
            definition="随着投入增加，每单位投入带来的收益逐渐减少",
            preconditions=["资源投入", "收益"],
            not_applicable=["初始阶段", "非线性系统"],
            confidence=0.88,
            examples=["学习时间越长效率越低", "吃越多边际效用递减"]
        ))
    
    def add_concept(self, concept: ConceptNode):
        """添加概念"""
        self._concepts[concept.name] = concept
        self._logger.debug(f"➕ 添加概念: {concept.name}")
    
    def get_concept(self, name: str) -> Optional[ConceptNode]:
        """获取概念"""
        return self._concepts.get(name)
    
    def remove_concept(self, name: str):
        """删除概念"""
        if name in self._concepts:
            del self._concepts[name]
            # 删除相关关系
            self._relations = [r for r in self._relations 
                              if r.source != name and r.target != name]
            self._logger.debug(f"🗑️ 删除概念: {name}")
    
    def add_relation(self, source: str, target: str, relation_type: RelationType, evidence: str = ""):
        """添加概念关系"""
        if source not in self._concepts or target not in self._concepts:
            self._logger.warning(f"概念不存在: {source} 或 {target}")
            return
        
        relation = ConceptRelation(
            source=source,
            target=target,
            relation_type=relation_type,
            confidence=0.7,
            evidence=[evidence] if evidence else []
        )
        
        self._relations.append(relation)
        self._logger.debug(f"➕ 添加关系: {source} -{relation_type.value}-> {target}")
    
    def match_concepts(self, context: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        根据上下文匹配最适用的概念
        
        Args:
            context: 当前场景描述
            top_k: 返回前k个匹配结果
            
        Returns:
            匹配结果列表，按适用度排序
        """
        results = []
        
        for name, concept in self._concepts.items():
            applicability = concept.is_applicable(context)
            if applicability > 0.1:  # 过滤低适用度
                results.append({
                    "concept": concept,
                    "applicability": applicability,
                    "confidence": concept.confidence
                })
        
        # 按适用度排序
        results.sort(key=lambda x: x["applicability"], reverse=True)
        
        return results[:top_k]
    
    def infer_relations(self, concept_name: str) -> List[Dict[str, Any]]:
        """
        推理与指定概念相关的关系
        
        Args:
            concept_name: 概念名称
            
        Returns:
            相关关系列表
        """
        related = []
        
        for relation in self._relations:
            if relation.source == concept_name:
                related.append({
                    "type": "outgoing",
                    "relation_type": relation.relation_type.value,
                    "target": relation.target,
                    "confidence": relation.confidence
                })
            elif relation.target == concept_name:
                related.append({
                    "type": "incoming",
                    "relation_type": relation.relation_type.value,
                    "source": relation.source,
                    "confidence": relation.confidence
                })
        
        return related
    
    def abstract_from_experience(self, experience: str, concept_name: str = None) -> ConceptNode:
        """
        从具体经验中抽象概念
        
        Args:
            experience: 具体经验描述
            concept_name: 概念名称（可选，自动生成时为None）
            
        Returns:
            抽象出的概念节点
        """
        # 自动生成概念名称
        if not concept_name:
            concept_name = self._generate_concept_name(experience)
        
        # 提取前提条件（简单实现：提取名词短语）
        preconditions = self._extract_key_phrases(experience)
        
        concept = ConceptNode(
            name=concept_name,
            definition=f"从经验中抽象的概念: {experience[:100]}...",
            preconditions=preconditions,
            examples=[experience],
            confidence=0.6  # 初始置信度
        )
        
        self.add_concept(concept)
        self._logger.info(f"🔍 从经验抽象概念: {concept_name}")
        
        return concept
    
    def _generate_concept_name(self, experience: str) -> str:
        """生成概念名称"""
        # 简单实现：提取关键词组合
        keywords = self._extract_key_phrases(experience)[:3]
        if keywords:
            return " ".join(keywords) + "原理"
        return f"概念_{int(time.time())}"
    
    def _extract_key_phrases(self, text: str) -> List[str]:
        """提取关键词短语（简单实现）"""
        import re
        # 提取中文名词短语（简化版）
        patterns = [
            r'([\u4e00-\u9fa5]{2,})',  # 中文词
            r'([a-zA-Z_]+)',            # 英文词
        ]
        
        phrases = []
        for pattern in patterns:
            matches = re.findall(pattern, text)
            phrases.extend(matches)
        
        return list(set(phrases))[:5]
    
    def get_all_concepts(self) -> List[ConceptNode]:
        """获取所有概念"""
        return list(self._concepts.values())
    
    def get_concept_count(self) -> int:
        """获取概念数量"""
        return len(self._concepts)


# 创建全局实例
concept_graph = ConceptGraph()


def get_concept_graph() -> ConceptGraph:
    """获取概念图谱实例"""
    return concept_graph


# 测试函数
async def test_concept_graph():
    """测试概念图谱"""
    import sys
    logger.remove()
    logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}", colorize=False)
    
    print("=" * 60)
    print("测试 ConceptGraph")
    print("=" * 60)
    
    graph = ConceptGraph()
    
    # 1. 测试概念匹配
    print("\n[1] 测试概念匹配...")
    context = "我想用一根棍子撬开一块大石头"
    matches = graph.match_concepts(context, top_k=3)
    print(f"    ✓ 上下文: {context}")
    for i, match in enumerate(matches):
        print(f"    ✓ 匹配#{i+1}: {match['concept'].name} (适用度: {match['applicability']:.2f})")
    
    # 2. 测试抽象概念
    print("\n[2] 测试从经验抽象...")
    experience = "当我不断学习时，一开始进步很快，但后来进步越来越慢"
    concept = graph.abstract_from_experience(experience)
    print(f"    ✓ 抽象概念: {concept.name}")
    print(f"    ✓ 置信度: {concept.confidence}")
    print(f"    ✓ 前提条件: {concept.preconditions}")
    
    # 3. 测试关系推理
    print("\n[3] 测试关系推理...")
    relations = graph.infer_relations("杠杆原理")
    print(f"    ✓ 杠杆原理相关关系: {len(relations)} 条")
    
    # 4. 测试添加关系
    print("\n[4] 测试添加关系...")
    graph.add_relation("杠杆原理", "边际效应", RelationType.SIMILAR_TO)
    relations = graph.infer_relations("杠杆原理")
    print(f"    ✓ 添加关系后: {len(relations)} 条")
    
    # 5. 测试适用度验证
    print("\n[5] 测试适用度验证...")
    context1 = "用剪刀剪纸"
    context2 = "用绳子捆东西"
    lever_concept = graph.get_concept("杠杆原理")
    print(f"    ✓ '{context1}' 适用度: {lever_concept.is_applicable(context1):.2f}")
    print(f"    ✓ '{context2}' 适用度: {lever_concept.is_applicable(context2):.2f}")
    
    print("\n" + "=" * 60)
    print("🎉 所有测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_concept_graph())