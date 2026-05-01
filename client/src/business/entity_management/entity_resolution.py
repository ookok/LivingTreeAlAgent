"""
实体解析模块 (Entity Resolution)

实现实体消歧和链接功能，将识别出的实体链接到权威知识库。集成DeepOnto实体嵌入和本体推理。

作者: LivingTreeAI Team
日期: 2026-05-01
版本: 1.1.0
"""

import logging
from typing import List, Dict, Any, Optional

from .models import Entity, EntityType, ResolvedEntity, EntityRelation

logger = logging.getLogger(__name__)

try:
    from deeponto.embedding import OntologyEmbedding
    HAS_DEEPONTO = True
except ImportError:
    HAS_DEEPONTO = False


class EntityResolver:
    """
    实体解析器基类
    """
    
    def resolve(self, entity: Entity, context: str = "") -> ResolvedEntity:
        """
        消歧并链接实体
        
        Args:
            entity: 待解析的实体
            context: 上下文文本
            
        Returns:
            ResolvedEntity 解析后的实体
        """
        raise NotImplementedError
    
    def batch_resolve(self, entities: List[Entity], context: str = "") -> List[ResolvedEntity]:
        """
        批量解析实体
        
        Args:
            entities: 待解析的实体列表
            context: 上下文文本
            
        Returns:
            ResolvedEntity 列表
        """
        return [self.resolve(e, context) for e in entities]


class KnowledgeBaseLinker:
    """
    知识库链接器
    
    将实体链接到权威知识库。
    """
    
    def __init__(self):
        """初始化知识库链接器"""
        # 内置知识库（示例数据）
        self.knowledge_base = self._load_knowledge_base()
        logger.info("KnowledgeBaseLinker 初始化完成")
    
    def _load_knowledge_base(self) -> Dict[str, Dict[str, Any]]:
        """加载内置知识库"""
        return {
            "人工智能": {
                "canonical_name": "人工智能",
                "description": "人工智能（Artificial Intelligence，AI）是计算机科学的一个分支，致力于研究、开发用于模拟、延伸和扩展人的智能的理论、方法、技术及应用系统。",
                "aliases": ["AI", "人工智能技术"],
                "type": "concept",
                "attributes": {
                    "领域": "计算机科学",
                    "应用": ["机器学习", "自然语言处理", "计算机视觉"],
                    "发展阶段": "强人工智能、弱人工智能",
                },
            },
            "机器学习": {
                "canonical_name": "机器学习",
                "description": "机器学习是人工智能的一个分支，它使计算机系统能够从数据中学习并改进其性能，而无需进行明确编程。",
                "aliases": ["ML", "机器学习算法"],
                "type": "concept",
                "attributes": {
                    "类型": ["监督学习", "无监督学习", "强化学习"],
                    "算法": ["决策树", "随机森林", "神经网络"],
                },
            },
            "深度学习": {
                "canonical_name": "深度学习",
                "description": "深度学习是机器学习的一个子领域，使用多层神经网络来学习数据的特征表示。",
                "aliases": ["Deep Learning", "深度神经网络"],
                "type": "concept",
                "attributes": {
                    "架构": ["CNN", "RNN", "Transformer"],
                    "应用": ["图像识别", "语音识别", "自然语言处理"],
                },
            },
            "Python": {
                "canonical_name": "Python",
                "description": "Python是一种高级通用编程语言，以其简洁的语法和强大的库生态系统而闻名。",
                "aliases": ["Python语言", "Py"],
                "type": "language",
                "attributes": {
                    "创建者": "Guido van Rossum",
                    "发布年份": 1991,
                    "用途": ["数据科学", "Web开发", "自动化"],
                },
            },
            "PyTorch": {
                "canonical_name": "PyTorch",
                "description": "PyTorch是一个开源的机器学习框架，由Facebook开发，提供灵活的张量计算和自动微分功能。",
                "aliases": ["Torch"],
                "type": "framework",
                "attributes": {
                    "开发者": "Meta（前Facebook）",
                    "发布年份": 2016,
                    "语言": "Python",
                },
            },
            "TensorFlow": {
                "canonical_name": "TensorFlow",
                "description": "TensorFlow是Google开发的开源机器学习框架，用于构建和训练各种机器学习模型。",
                "aliases": ["TF"],
                "type": "framework",
                "attributes": {
                    "开发者": "Google",
                    "发布年份": 2015,
                    "语言": "Python",
                },
            },
            "爱因斯坦": {
                "canonical_name": "阿尔伯特·爱因斯坦",
                "description": "阿尔伯特·爱因斯坦（1879-1955）是德国出生的理论物理学家，提出了相对论，被认为是现代物理学之父。",
                "aliases": ["Einstein", "爱神"],
                "type": "person",
                "attributes": {
                    "国籍": "美国（后入籍）",
                    "出生年份": 1879,
                    "逝世年份": 1955,
                    "成就": ["相对论", "光电效应", "质能方程"],
                },
            },
            "乔布斯": {
                "canonical_name": "史蒂夫·乔布斯",
                "description": "史蒂夫·乔布斯（1955-2011）是苹果公司的联合创始人，被誉为现代科技产业的标志性人物。",
                "aliases": ["Steve Jobs", "乔帮主"],
                "type": "person",
                "attributes": {
                    "国籍": "美国",
                    "出生年份": 1955,
                    "逝世年份": 2011,
                    "成就": ["苹果公司", "iPhone", "Mac"],
                },
            },
            "苹果公司": {
                "canonical_name": "苹果公司",
                "description": "苹果公司（Apple Inc.）是一家美国跨国科技公司，设计、开发和销售消费电子、软件和在线服务。",
                "aliases": ["Apple", "苹果"],
                "type": "organization",
                "attributes": {
                    "总部": "美国加利福尼亚州库比蒂诺",
                    "成立年份": 1976,
                    "产品": ["iPhone", "Mac", "iPad", "Apple Watch"],
                },
            },
            "北京": {
                "canonical_name": "北京市",
                "description": "北京是中华人民共和国的首都，是全国政治、文化中心。",
                "aliases": ["京城", "帝都"],
                "type": "location",
                "attributes": {
                    "所属国家": "中国",
                    "人口": "约2150万",
                    "著名景点": ["故宫", "天安门", "长城"],
                },
            },
            "清华大学": {
                "canonical_name": "清华大学",
                "description": "清华大学是中国著名的综合性研究型大学，位于北京市。",
                "aliases": ["清华"],
                "type": "organization",
                "attributes": {
                    "成立年份": 1911,
                    "类型": "公立大学",
                    "校训": "自强不息，厚德载物",
                },
            },
        }
    
    def link(self, entity: Entity) -> Optional[Dict[str, Any]]:
        """
        将实体链接到知识库
        
        Args:
            entity: 待链接的实体
            
        Returns:
            知识库条目，如果未找到则返回 None
        """
        # 精确匹配
        if entity.text in self.knowledge_base:
            return self.knowledge_base[entity.text]
        
        # 模糊匹配（小写）
        text_lower = entity.text.lower()
        for key, info in self.knowledge_base.items():
            if key.lower() == text_lower:
                return info
            
            # 检查别名
            for alias in info.get("aliases", []):
                if alias.lower() == text_lower:
                    return info
        
        return None
    
    def search(self, query: str) -> List[Dict[str, Any]]:
        """
        搜索知识库
        
        Args:
            query: 搜索词
            
        Returns:
            匹配的知识库条目列表
        """
        results = []
        query_lower = query.lower()
        
        for key, info in self.knowledge_base.items():
            if query_lower in key.lower():
                results.append(info)
            else:
                for alias in info.get("aliases", []):
                    if query_lower in alias.lower():
                        results.append(info)
                        break
        
        return results


class ContextAwareEntityResolver(EntityResolver):
    """
    上下文感知实体解析器
    
    根据上下文进行实体消歧和链接，集成DeepOnto实体嵌入。
    """
    
    def __init__(self):
        """初始化上下文感知解析器"""
        self.kb_linker = KnowledgeBaseLinker()
        self._entity_embedding_service = None
        self._init_embedding_service()
        logger.info("ContextAwareEntityResolver v1.1.0 初始化完成")
    
    def _init_embedding_service(self):
        """初始化实体嵌入服务"""
        try:
            from ..deeponto_integration import get_entity_embedding_service
            self._entity_embedding_service = get_entity_embedding_service()
            self._entity_embedding_service.initialize()
            logger.info("实体嵌入服务初始化成功")
        except ImportError as e:
            logger.warning(f"实体嵌入服务初始化失败: {e}")
    
    def resolve(self, entity: Entity, context: str = "") -> ResolvedEntity:
        """消歧并链接实体"""
        # 1. 尝试链接到知识库
        kb_entry = self.kb_linker.link(entity)
        
        if kb_entry:
            return ResolvedEntity(
                entity=entity,
                canonical_name=kb_entry["canonical_name"],
                description=kb_entry.get("description"),
                aliases=kb_entry.get("aliases", []),
                attributes=kb_entry.get("attributes", {}),
                confidence=self._calculate_confidence(entity, kb_entry, context),
                source="internal_knowledge_base"
            )
        
        # 2. 如果未找到，返回原始实体
        return ResolvedEntity(
            entity=entity,
            canonical_name=entity.text,
            confidence=0.5,
            source="unknown"
        )
    
    def _calculate_confidence(self, entity: Entity, kb_entry: Dict[str, Any], 
                              context: str = "") -> float:
        """计算解析置信度"""
        confidence = 0.7  # 基础置信度
        
        # 如果上下文包含相关关键词，增加置信度
        if context:
            context_lower = context.lower()
            # 检查实体类型相关词
            type_keywords = {
                EntityType.TECH_TERM: ["技术", "算法", "模型", "框架"],
                EntityType.PERSON: ["说", "认为", "提出", "发明"],
                EntityType.ORGANIZATION: ["公司", "大学", "研究院", "机构"],
                EntityType.LOCATION: ["位于", "在", "来自"],
            }
            
            keywords = type_keywords.get(entity.entity_type, [])
            if any(kw in context_lower for kw in keywords):
                confidence += 0.15
        
        # 如果有别名匹配，增加置信度
        if entity.text.lower() in [a.lower() for a in kb_entry.get("aliases", [])]:
            confidence += 0.1
        
        return min(confidence, 0.95)


    def resolve_with_embedding(self, entity: Entity, context: str = "") -> ResolvedEntity:
        """
        使用实体嵌入进行语义解析
        
        Args:
            entity: 待解析的实体
            context: 上下文文本
            
        Returns:
            ResolvedEntity 解析后的实体
        """
        if not self._entity_embedding_service:
            return self.resolve(entity, context)
        
        try:
            kb_entries = list(self.kb_linker.knowledge_base.keys())
            
            matches = self._entity_embedding_service.find_similar_entities(
                entity.text, kb_entries, top_k=3
            )
            
            if matches and matches[0].score > 0.7:
                best_match = matches[0]
                kb_entry = self.kb_linker.knowledge_base.get(best_match.entity_id)
                
                if kb_entry:
                    return ResolvedEntity(
                        entity=entity,
                        canonical_name=kb_entry["canonical_name"],
                        description=kb_entry.get("description"),
                        aliases=kb_entry.get("aliases", []),
                        attributes=kb_entry.get("attributes", {}),
                        confidence=min(best_match.score, 0.95),
                        source="embedding_based"
                    )
            
            return self.resolve(entity, context)
        except Exception as e:
            logger.error(f"基于嵌入的解析失败: {e}")
            return self.resolve(entity, context)
    
    def batch_resolve_with_embedding(self, entities: List[Entity], context: str = "") -> List[ResolvedEntity]:
        """
        批量使用实体嵌入进行语义解析
        
        Args:
            entities: 待解析的实体列表
            context: 上下文文本
            
        Returns:
            ResolvedEntity 列表
        """
        results = []
        for entity in entities:
            results.append(self.resolve_with_embedding(entity, context))
        return results
    
    def cluster_entities(self, entities: List[Entity], num_clusters: int = 5) -> Dict[int, List[Entity]]:
        """
        对实体进行聚类
        
        Args:
            entities: 实体列表
            num_clusters: 聚类数量
            
        Returns:
            Dict 聚类结果
        """
        if not self._entity_embedding_service:
            clusters = {}
            for i, entity in enumerate(entities):
                cluster_id = i % num_clusters
                if cluster_id not in clusters:
                    clusters[cluster_id] = []
                clusters[cluster_id].append(entity)
            return clusters
        
        try:
            entity_texts = [e.text for e in entities]
            clusters = self._entity_embedding_service.cluster_entities(entity_texts, num_clusters)
            
            result = {}
            for cluster_id, texts in clusters.items():
                result[cluster_id] = [e for e in entities if e.text in texts]
            
            return result
        except Exception as e:
            logger.error(f"实体聚类失败: {e}")
            clusters = {}
            for i, entity in enumerate(entities):
                cluster_id = i % num_clusters
                if cluster_id not in clusters:
                    clusters[cluster_id] = []
                clusters[cluster_id].append(entity)
            return clusters


# 全局解析器实例
_resolver_instance = None

def get_entity_resolver() -> EntityResolver:
    """获取全局实体解析器实例"""
    global _resolver_instance
    if _resolver_instance is None:
        _resolver_instance = ContextAwareEntityResolver()
    return _resolver_instance