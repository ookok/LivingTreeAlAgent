"""
实体知识库模块 (Entity Knowledge Base)

提供实体信息的存储、检索和管理功能。

作者: LivingTreeAI Team
日期: 2026-04-30
版本: 1.0.0
"""

import json
import logging
import time
from typing import List, Dict, Any, Optional

from .models import Entity, EntityType, ResolvedEntity, KnowledgeBaseEntry, EntitySearchResult

logger = logging.getLogger(__name__)


class EntityKnowledgeBase:
    """
    实体知识库
    
    管理实体信息，支持检索和更新。
    """
    
    def __init__(self):
        """初始化知识库"""
        self.entities: Dict[str, KnowledgeBaseEntry] = {}
        self.alias_map: Dict[str, str] = {}  # 别名到实体ID的映射
        self.type_index: Dict[EntityType, List[str]] = {}  # 类型索引
        
        # 加载内置数据
        self._load_builtin_data()
        
        logger.info("EntityKnowledgeBase 初始化完成")
    
    def _load_builtin_data(self):
        """加载内置实体数据"""
        builtin_entities = [
            {
                "entity_id": "ai",
                "name": "人工智能",
                "type": "concept",
                "description": "人工智能（Artificial Intelligence，AI）是计算机科学的一个分支，致力于研究、开发用于模拟、延伸和扩展人的智能的理论、方法、技术及应用系统。",
                "aliases": ["AI", "人工智能技术"],
                "attributes": {
                    "领域": "计算机科学",
                    "应用": ["机器学习", "自然语言处理", "计算机视觉"],
                },
            },
            {
                "entity_id": "ml",
                "name": "机器学习",
                "type": "concept",
                "description": "机器学习是人工智能的一个分支，它使计算机系统能够从数据中学习并改进其性能，而无需进行明确编程。",
                "aliases": ["ML", "机器学习算法"],
                "attributes": {
                    "类型": ["监督学习", "无监督学习", "强化学习"],
                },
            },
            {
                "entity_id": "dl",
                "name": "深度学习",
                "type": "concept",
                "description": "深度学习是机器学习的一个子领域，使用多层神经网络来学习数据的特征表示。",
                "aliases": ["Deep Learning", "深度神经网络"],
                "attributes": {
                    "架构": ["CNN", "RNN", "Transformer"],
                },
            },
            {
                "entity_id": "python",
                "name": "Python",
                "type": "language",
                "description": "Python是一种高级通用编程语言，以其简洁的语法和强大的库生态系统而闻名。",
                "aliases": ["Python语言", "Py"],
                "attributes": {
                    "创建者": "Guido van Rossum",
                    "发布年份": 1991,
                },
            },
            {
                "entity_id": "pytorch",
                "name": "PyTorch",
                "type": "framework",
                "description": "PyTorch是一个开源的机器学习框架，由Facebook开发，提供灵活的张量计算和自动微分功能。",
                "aliases": ["Torch"],
                "attributes": {
                    "开发者": "Meta",
                    "发布年份": 2016,
                },
            },
            {
                "entity_id": "tensorflow",
                "name": "TensorFlow",
                "type": "framework",
                "description": "TensorFlow是Google开发的开源机器学习框架，用于构建和训练各种机器学习模型。",
                "aliases": ["TF"],
                "attributes": {
                    "开发者": "Google",
                    "发布年份": 2015,
                },
            },
            {
                "entity_id": "einstein",
                "name": "阿尔伯特·爱因斯坦",
                "type": "person",
                "description": "阿尔伯特·爱因斯坦（1879-1955）是德国出生的理论物理学家，提出了相对论。",
                "aliases": ["爱因斯坦", "Einstein"],
                "attributes": {
                    "国籍": "美国",
                    "出生年份": 1879,
                    "逝世年份": 1955,
                },
            },
            {
                "entity_id": "jobs",
                "name": "史蒂夫·乔布斯",
                "type": "person",
                "description": "史蒂夫·乔布斯（1955-2011）是苹果公司的联合创始人。",
                "aliases": ["乔布斯", "Steve Jobs"],
                "attributes": {
                    "国籍": "美国",
                    "出生年份": 1955,
                    "逝世年份": 2011,
                },
            },
            {
                "entity_id": "apple",
                "name": "苹果公司",
                "type": "organization",
                "description": "苹果公司（Apple Inc.）是一家美国跨国科技公司。",
                "aliases": ["Apple", "苹果"],
                "attributes": {
                    "总部": "美国加利福尼亚州库比蒂诺",
                    "成立年份": 1976,
                },
            },
            {
                "entity_id": "beijing",
                "name": "北京市",
                "type": "location",
                "description": "北京是中华人民共和国的首都。",
                "aliases": ["北京", "京城"],
                "attributes": {
                    "所属国家": "中国",
                    "人口": "约2150万",
                },
            },
            {
                "entity_id": "tsinghua",
                "name": "清华大学",
                "type": "organization",
                "description": "清华大学是中国著名的综合性研究型大学。",
                "aliases": ["清华"],
                "attributes": {
                    "成立年份": 1911,
                    "校训": "自强不息，厚德载物",
                },
            },
            {
                "entity_id": "transformer",
                "name": "Transformer",
                "type": "algorithm",
                "description": "Transformer是一种基于自注意力机制的深度学习架构，由Google在2017年提出。",
                "aliases": ["Transformer架构"],
                "attributes": {
                    "提出年份": 2017,
                    "作者": "Google",
                    "应用": ["BERT", "GPT", "T5"],
                },
            },
            {
                "entity_id": "gpt",
                "name": "GPT",
                "type": "model",
                "description": "GPT（Generative Pre-trained Transformer）是OpenAI开发的大型语言模型系列。",
                "aliases": ["GPT-3", "GPT-4", "ChatGPT"],
                "attributes": {
                    "开发者": "OpenAI",
                    "首次发布": 2020,
                    "类型": "大语言模型",
                },
            },
            {
                "entity_id": "bert",
                "name": "BERT",
                "type": "model",
                "description": "BERT（Bidirectional Encoder Representations from Transformers）是Google开发的预训练语言模型。",
                "aliases": ["BERT模型"],
                "attributes": {
                    "开发者": "Google",
                    "发布年份": 2018,
                    "类型": "预训练语言模型",
                },
            },
            {
                "entity_id": "rag",
                "name": "RAG",
                "type": "concept",
                "description": "RAG（Retrieval-Augmented Generation）是一种结合检索和生成的AI技术。",
                "aliases": ["检索增强生成"],
                "attributes": {
                    "组成": ["检索系统", "生成模型"],
                    "应用": ["问答系统", "文档理解"],
                },
            },
        ]
        
        for data in builtin_entities:
            entity_type = EntityType(data["type"]) if data["type"] in [t.value for t in EntityType] else EntityType.UNKNOWN
            entry = KnowledgeBaseEntry(
                entity_id=data["entity_id"],
                name=data["name"],
                type=entity_type,
                description=data["description"],
                aliases=data.get("aliases", []),
                attributes=data.get("attributes", {}),
                last_updated=str(time.time())
            )
            self.add_entry(entry)
    
    def add_entry(self, entry: KnowledgeBaseEntry):
        """添加知识库条目"""
        self.entities[entry.entity_id] = entry
        
        # 更新别名映射
        for alias in entry.aliases:
            self.alias_map[alias.lower()] = entry.entity_id
        self.alias_map[entry.name.lower()] = entry.entity_id
        
        # 更新类型索引
        if entry.type not in self.type_index:
            self.type_index[entry.type] = []
        if entry.entity_id not in self.type_index[entry.type]:
            self.type_index[entry.type].append(entry.entity_id)
    
    def get_entity_info(self, entity_id: str) -> Optional[KnowledgeBaseEntry]:
        """获取实体详细信息"""
        return self.entities.get(entity_id)
    
    def search_entities(self, query: str) -> List[EntitySearchResult]:
        """
        搜索实体
        
        Args:
            query: 搜索词
            
        Returns:
            搜索结果列表
        """
        results = []
        query_lower = query.lower()
        
        for entity_id, entry in self.entities.items():
            # 精确匹配
            if entry.name.lower() == query_lower:
                results.append(EntitySearchResult(
                    entity=ResolvedEntity(
                        entity=Entity(
                            text=entry.name,
                            entity_type=entry.type,
                            start=0,
                            end=len(entry.name),
                            confidence=1.0
                        ),
                        canonical_name=entry.name,
                        entity_id=entity_id,
                        description=entry.description,
                        aliases=entry.aliases,
                        attributes=entry.attributes,
                        confidence=1.0,
                        source="knowledge_base"
                    ),
                    score=1.0,
                    match_type="exact"
                ))
                continue
            
            # 模糊匹配（名称包含）
            if query_lower in entry.name.lower():
                results.append(EntitySearchResult(
                    entity=ResolvedEntity(
                        entity=Entity(
                            text=entry.name,
                            entity_type=entry.type,
                            start=0,
                            end=len(entry.name),
                            confidence=0.8
                        ),
                        canonical_name=entry.name,
                        entity_id=entity_id,
                        description=entry.description,
                        aliases=entry.aliases,
                        attributes=entry.attributes,
                        confidence=0.8,
                        source="knowledge_base"
                    ),
                    score=0.8,
                    match_type="fuzzy"
                ))
                continue
            
            # 别名匹配
            for alias in entry.aliases:
                if query_lower in alias.lower():
                    results.append(EntitySearchResult(
                        entity=ResolvedEntity(
                            entity=Entity(
                                text=alias,
                                entity_type=entry.type,
                                start=0,
                                end=len(alias),
                                confidence=0.7
                            ),
                            canonical_name=entry.name,
                            entity_id=entity_id,
                            description=entry.description,
                            aliases=entry.aliases,
                            attributes=entry.attributes,
                            confidence=0.7,
                            source="knowledge_base"
                        ),
                        score=0.7,
                        match_type="fuzzy"
                    ))
                    break
        
        # 按分数排序
        results.sort(key=lambda x: x.score, reverse=True)
        return results
    
    def get_entities_by_type(self, entity_type: EntityType) -> List[KnowledgeBaseEntry]:
        """获取指定类型的所有实体"""
        entity_ids = self.type_index.get(entity_type, [])
        return [self.entities.get(eid) for eid in entity_ids if self.entities.get(eid)]
    
    def get_all_entities(self) -> List[KnowledgeBaseEntry]:
        """获取所有实体"""
        return list(self.entities.values())
    
    def update_entity(self, entity_id: str, updates: Dict[str, Any]):
        """更新实体信息"""
        if entity_id not in self.entities:
            logger.warning(f"实体不存在: {entity_id}")
            return
        
        entry = self.entities[entity_id]
        
        if "name" in updates:
            # 更新别名映射
            self.alias_map.pop(entry.name.lower(), None)
            entry.name = updates["name"]
            self.alias_map[entry.name.lower()] = entity_id
        
        if "description" in updates:
            entry.description = updates["description"]
        
        if "aliases" in updates:
            # 移除旧别名
            for alias in entry.aliases:
                self.alias_map.pop(alias.lower(), None)
            entry.aliases = updates["aliases"]
            # 添加新别名
            for alias in entry.aliases:
                self.alias_map[alias.lower()] = entity_id
        
        if "attributes" in updates:
            entry.attributes.update(updates["attributes"])
        
        entry.last_updated = str(time.time())
    
    def delete_entity(self, entity_id: str):
        """删除实体"""
        if entity_id not in self.entities:
            logger.warning(f"实体不存在: {entity_id}")
            return
        
        entry = self.entities[entity_id]
        
        # 移除别名映射
        self.alias_map.pop(entry.name.lower(), None)
        for alias in entry.aliases:
            self.alias_map.pop(alias.lower(), None)
        
        # 移除类型索引
        if entry.type in self.type_index:
            self.type_index[entry.type].remove(entity_id)
        
        # 删除实体
        del self.entities[entity_id]
    
    def get_stats(self) -> Dict[str, Any]:
        """获取知识库统计信息"""
        type_counts = {}
        for entry in self.entities.values():
            type_name = entry.type.value
            type_counts[type_name] = type_counts.get(type_name, 0) + 1
        
        return {
            "total_entities": len(self.entities),
            "total_aliases": len(self.alias_map),
            "type_distribution": type_counts,
        }


# 全局知识库实例
_knowledge_base_instance = None

def get_entity_knowledge_base() -> EntityKnowledgeBase:
    """获取全局实体知识库实例"""
    global _knowledge_base_instance
    if _knowledge_base_instance is None:
        _knowledge_base_instance = EntityKnowledgeBase()
    return _knowledge_base_instance