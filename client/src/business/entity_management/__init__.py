"""
实体管理模块 (Entity Management)

提供完整的实体识别、解析、知识库和向量存储功能。

功能：
1. 命名实体识别（NER）- 从文本中识别实体
2. 实体解析 - 消歧并链接到权威知识库
3. 实体知识库 - 存储和检索实体信息
4. 实体向量存储 - 基于语义的实体搜索

架构：
┌─────────────────────────────────────────────────────────────┐
│                    实体处理管道                              │
├─────────────────────────────────────────────────────────────┤
│  输入文本 → NER识别 → 实体消歧 → 实体链接 → 知识图谱增强     │
└─────────────────────────────────────────────────────────────┘

作者: LivingTreeAI Team
日期: 2026-04-30
版本: 1.0.0
"""

# 版本信息
__version__ = "1.0.0"
__author__ = "LivingTreeAI Team"
__module_name__ = "entity_management"

# 导出数据模型
from .models import (
    EntityType,
    Entity,
    ResolvedEntity,
    EntityRelation,
    KnowledgeBaseEntry,
    EntitySearchResult,
    EntityRecognitionResult,
)

# 导出核心组件
from .entity_recognition import (
    EntityRecognizer,
    RuleBasedEntityRecognizer,
    HybridEntityRecognizer,
    get_entity_recognizer,
)

from .entity_resolution import (
    EntityResolver,
    KnowledgeBaseLinker,
    ContextAwareEntityResolver,
    get_entity_resolver,
)

from .entity_knowledge_base import (
    EntityKnowledgeBase,
    get_entity_knowledge_base,
)

from .entity_vector_store import (
    EntityVectorStore,
    get_entity_vector_store,
)

# 便捷函数
def recognize_and_resolve(text: str) -> list:
    """
    识别并解析文本中的实体
    
    Args:
        text: 输入文本
        
    Returns:
        解析后的实体列表
    """
    recognizer = get_entity_recognizer()
    resolver = get_entity_resolver()
    
    # 识别实体
    result = recognizer.recognize(text)
    
    # 解析实体
    resolved = resolver.batch_resolve(result.entities, text)
    
    return resolved

def search_entities(query: str) -> list:
    """
    搜索实体
    
    Args:
        query: 搜索词
        
    Returns:
        搜索结果列表
    """
    kb = get_entity_knowledge_base()
    return kb.search_entities(query)

# 初始化日志
import logging
logger = logging.getLogger(__name__)
logger.info(f"Entity Management 模块 v{__version__} 已加载")