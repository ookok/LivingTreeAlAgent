"""
实体向量存储模块 (Entity Vector Store)

为实体创建专用向量索引，支持基于语义的实体搜索。

作者: LivingTreeAI Team
日期: 2026-04-30
版本: 1.0.0
"""

import logging
from typing import List, Dict, Any, Optional

from .models import Entity, ResolvedEntity, EntityType
from ..fusion_rag.smart_vector_store import get_smart_vector_store, SearchResult

logger = logging.getLogger(__name__)


class EntityVectorStore:
    """
    实体向量存储
    
    将实体信息转换为向量表示，支持语义搜索。
    """
    
    def __init__(self):
        """初始化实体向量存储"""
        self.vector_store = get_smart_vector_store()
        self.entity_id_map: Dict[str, str] = {}  # vector_id -> entity_id
        self.entity_metadata: Dict[str, Dict[str, Any]] = {}  # entity_id -> metadata
        
        logger.info("EntityVectorStore 初始化完成")
    
    def _generate_entity_text(self, entity: ResolvedEntity) -> str:
        """生成实体的文本表示用于向量化"""
        parts = []
        parts.append(entity.canonical_name)
        if entity.description:
            parts.append(entity.description)
        if entity.aliases:
            parts.append("别名: " + ", ".join(entity.aliases))
        if entity.attributes:
            attr_text = "属性: " + ", ".join(f"{k}: {v}" for k, v in entity.attributes.items())
            parts.append(attr_text)
        return " ".join(parts)
    
    def _generate_embedding(self, text: str) -> List[float]:
        """生成文本的嵌入向量"""
        # 简化实现：使用简单的哈希向量化
        import re
        
        text = text.lower()
        words = re.findall(r'[\w]+', text)
        vec = [0.0] * 384
        
        for word in words:
            word_hash = hash(word) % 384
            vec[word_hash] += 1.0
        
        # L2 归一化
        norm = sum(v * v for v in vec) ** 0.5
        if norm > 0:
            vec = [v / norm for v in vec]
        
        return vec
    
    async def index_entity(self, entity: ResolvedEntity):
        """
        为实体创建向量索引
        
        Args:
            entity: 已解析的实体
        """
        if not entity.entity_id:
            entity_id = f"entity_{hash(entity.canonical_name)}"
            entity.entity_id = entity_id
        else:
            entity_id = entity.entity_id
        
        # 生成文本表示
        text = self._generate_entity_text(entity)
        
        # 生成嵌入向量
        embedding = self._generate_embedding(text)
        
        # 准备元数据
        metadata = {
            "entity_id": entity_id,
            "name": entity.canonical_name,
            "type": entity.entity.entity_type.value,
            "description": entity.description,
            "aliases": entity.aliases,
            "attributes": entity.attributes,
        }
        
        # 添加到向量存储
        await self.vector_store.add([embedding], [entity_id], [metadata])
        
        # 更新映射
        self.entity_id_map[entity_id] = entity_id
        self.entity_metadata[entity_id] = metadata
        
        logger.debug(f"实体已索引: {entity.canonical_name}")
    
    async def batch_index_entities(self, entities: List[ResolvedEntity]):
        """
        批量索引实体
        
        Args:
            entities: 已解析的实体列表
        """
        embeddings = []
        ids = []
        metadatas = []
        
        for entity in entities:
            if not entity.entity_id:
                entity.entity_id = f"entity_{hash(entity.canonical_name)}"
            
            text = self._generate_entity_text(entity)
            embedding = self._generate_embedding(text)
            
            metadata = {
                "entity_id": entity.entity_id,
                "name": entity.canonical_name,
                "type": entity.entity.entity_type.value,
                "description": entity.description,
                "aliases": entity.aliases,
                "attributes": entity.attributes,
            }
            
            embeddings.append(embedding)
            ids.append(entity.entity_id)
            metadatas.append(metadata)
        
        await self.vector_store.add(embeddings, ids, metadatas)
        
        for entity_id, metadata in zip(ids, metadatas):
            self.entity_id_map[entity_id] = entity_id
            self.entity_metadata[entity_id] = metadata
        
        logger.info(f"批量索引完成，共 {len(entities)} 个实体")
    
    async def search_similar_entities(self, query: str, top_k: int = 10, 
                                      entity_type: Optional[EntityType] = None) -> List[ResolvedEntity]:
        """
        基于语义搜索相似实体
        
        Args:
            query: 查询文本
            top_k: 返回数量
            entity_type: 可选的实体类型过滤
            
        Returns:
            相似实体列表
        """
        # 生成查询向量
        query_embedding = self._generate_embedding(query)
        
        # 搜索向量存储
        results = await self.vector_store.search(query_embedding, top_k)
        
        # 过滤和格式化结果
        formatted_results = []
        for result in results:
            metadata = result.metadata
            
            # 如果指定了类型，进行过滤
            if entity_type and metadata.get("type") != entity_type.value:
                continue
            
            entity = ResolvedEntity(
                entity=Entity(
                    text=metadata.get("name", ""),
                    entity_type=EntityType(metadata.get("type", "unknown")),
                    start=0,
                    end=len(metadata.get("name", "")),
                    confidence=result.score
                ),
                canonical_name=metadata.get("name", ""),
                entity_id=metadata.get("entity_id"),
                description=metadata.get("description"),
                aliases=metadata.get("aliases", []),
                attributes=metadata.get("attributes", {}),
                confidence=result.score,
                source="vector_store"
            )
            formatted_results.append(entity)
        
        return formatted_results
    
    async def get_entity_by_id(self, entity_id: str) -> Optional[ResolvedEntity]:
        """
        根据实体ID获取实体信息
        
        Args:
            entity_id: 实体ID
            
        Returns:
            实体信息，如果未找到则返回 None
        """
        metadata = self.entity_metadata.get(entity_id)
        if not metadata:
            return None
        
        return ResolvedEntity(
            entity=Entity(
                text=metadata.get("name", ""),
                entity_type=EntityType(metadata.get("type", "unknown")),
                start=0,
                end=len(metadata.get("name", "")),
                confidence=1.0
            ),
            canonical_name=metadata.get("name", ""),
            entity_id=entity_id,
            description=metadata.get("description"),
            aliases=metadata.get("aliases", []),
            attributes=metadata.get("attributes", {}),
            confidence=1.0,
            source="vector_store"
        )
    
    async def delete_entity(self, entity_id: str):
        """
        删除实体索引
        
        Args:
            entity_id: 实体ID
        """
        await self.vector_store.delete([entity_id])
        self.entity_id_map.pop(entity_id, None)
        self.entity_metadata.pop(entity_id, None)
        
        logger.debug(f"实体已删除: {entity_id}")
    
    async def clear_all(self):
        """清空所有实体索引"""
        await self.vector_store.clear()
        self.entity_id_map.clear()
        self.entity_metadata.clear()
        
        logger.info("实体向量存储已清空")
    
    async def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        count = await self.vector_store.count()
        return {
            "indexed_entities": count,
            "vector_dimension": 384,
        }


# 全局实体向量存储实例
_vector_store_instance = None

def get_entity_vector_store() -> EntityVectorStore:
    """获取全局实体向量存储实例"""
    global _vector_store_instance
    if _vector_store_instance is None:
        _vector_store_instance = EntityVectorStore()
    return _vector_store_instance