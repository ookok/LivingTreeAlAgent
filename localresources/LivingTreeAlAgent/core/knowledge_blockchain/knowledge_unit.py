# -*- coding: utf-8 -*-
"""
去中心化知识区块链系统 - 知识单元管理

实现知识的创建、更新、检索和学习
"""

import asyncio
import logging
import json
import hashlib
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from dataclasses import dataclass

from .models import (
    KnowledgeUnit, KnowledgeMetadata, KnowledgeContent,
    KnowledgeType, VerificationInfo, ValueInfo
)

logger = logging.getLogger(__name__)


class KnowledgeManager:
    """知识管理器"""

    def __init__(
        self,
        blockchain: 'KnowledgeBlockchain',
        storage: 'DistributedStorage'
    ):
        """
        初始化知识管理器
        
        Args:
            blockchain: 区块链实例
            storage: 分布式存储
        """
        self.blockchain = blockchain
        self.storage = storage
        
        # 知识索引
        self.title_index: Dict[str, List[str]] = {}  # 标题关键词 -> knowledge_ids
        self.tag_index: Dict[str, List[str]] = {}  # 标签 -> knowledge_ids
        self.creator_index: Dict[str, List[str]] = {}  # 创建者 -> knowledge_ids
        self.type_index: Dict[str, List[str]] = {}  # 类型 -> knowledge_ids
        
        # 学习记录
        self.learning_records: Dict[str, List[Dict[str, Any]]] = {}  # knowledge_id -> records
        
        # 语义索引（简化实现）
        self.semantic_vectors: Dict[str, List[float]] = {}  # knowledge_id -> 向量
        
        logger.info("知识管理器初始化完成")

    async def create_knowledge(
        self,
        creator_id: str,
        title: str,
        content: str,
        knowledge_type: KnowledgeType,
        domain_tags: List[str],
        references: Optional[List[str]] = None,
        attachments: Optional[Dict[str, Any]] = None,
        summary: Optional[str] = None,
        keywords: Optional[List[str]] = None
    ) -> Optional[KnowledgeUnit]:
        """
        创建知识单元
        
        Args:
            creator_id: 创建者ID
            title: 标题
            content: 内容
            knowledge_type: 知识类型
            domain_tags: 领域标签
            references: 引用
            attachments: 附件
            summary: 摘要
            keywords: 关键词
            
        Returns:
            创建的知识单元
        """
        try:
            timestamp = datetime.now()
            
            # 生成内容哈希
            content_obj = KnowledgeContent(
                title=title,
                summary=summary or "",
                content=content,
                references=references or [],
                attachments=attachments or {},
                keywords=keywords or []
            )
            content_hash = content_obj.get_content_hash()
            
            # 生成知识ID
            knowledge_id = self._generate_knowledge_id(
                content_hash, creator_id, timestamp
            )
            
            # 创建元数据
            metadata = KnowledgeMetadata(
                knowledge_id=knowledge_id,
                creator_id=creator_id,
                creator_signature="",  # 签名将在共识阶段添加
                created_at=timestamp,
                updated_at=timestamp,
                version=1,
                knowledge_type=knowledge_type.value if isinstance(knowledge_type, KnowledgeType) else knowledge_type,
                domain_tags=domain_tags,
                language="zh-CN"
            )
            
            # 创建知识单元
            knowledge = KnowledgeUnit(
                metadata=metadata,
                content=content_obj,
                verification_info=VerificationInfo(),
                value_info=ValueInfo()
            )
            
            # 更新索引
            await self._update_indexes(knowledge)
            
            # 生成语义向量
            await self._generate_semantic_vector(knowledge)
            
            logger.info(f"✅ 知识创建: {knowledge_id} - {title[:30]}...")
            
            return knowledge
            
        except Exception as e:
            logger.error(f"创建知识失败: {e}")
            return None

    async def get_knowledge(self, knowledge_id: str) -> Optional[KnowledgeUnit]:
        """
        获取知识
        
        Args:
            knowledge_id: 知识ID
            
        Returns:
            知识单元
        """
        # 先从缓存获取
        knowledge = self.blockchain.get_knowledge(knowledge_id)
        
        if not knowledge:
            # 从存储加载
            knowledge = await self._load_knowledge(knowledge_id)
        
        return knowledge

    async def update_knowledge(
        self,
        knowledge_id: str,
        updates: Dict[str, Any],
        updater_id: str
    ) -> Optional[KnowledgeUnit]:
        """
        更新知识
        
        Args:
            knowledge_id: 知识ID
            updates: 更新内容
            updater_id: 更新者ID
            
        Returns:
            更新后的知识单元
        """
        knowledge = await self.get_knowledge(knowledge_id)
        if not knowledge:
            return None
        
        # 检查权限
        if knowledge.creator_id != updater_id:
            logger.warning(f"无权限更新知识: {knowledge_id}")
            return None
        
        # 更新内容
        if "title" in updates:
            knowledge.content.title = updates["title"]
        if "content" in updates:
            knowledge.content.content = updates["content"]
        if "summary" in updates:
            knowledge.content.summary = updates["summary"]
        if "references" in updates:
            knowledge.content.references = updates["references"]
        if "keywords" in updates:
            knowledge.content.keywords = updates["keywords"]
        if "domain_tags" in updates:
            knowledge.metadata.domain_tags = updates["domain_tags"]
        
        # 更新元数据
        knowledge.metadata.version += 1
        knowledge.metadata.updated_at = datetime.now()
        
        # 更新索引
        await self._update_indexes(knowledge)
        
        # 保存
        await self._save_knowledge(knowledge)
        
        logger.info(f"✅ 知识更新: {knowledge_id}")
        
        return knowledge

    async def record_learning(
        self,
        knowledge_id: str,
        learner_id: str,
        notes: Optional[str] = None,
        quiz_score: Optional[float] = None
    ) -> bool:
        """
        记录学习
        
        Args:
            knowledge_id: 知识ID
            learner_id: 学习者ID
            notes: 学习笔记
            quiz_score: 测试分数
            
        Returns:
            是否成功
        """
        try:
            knowledge = await self.get_knowledge(knowledge_id)
            if not knowledge:
                return False
            
            record = {
                "learner_id": learner_id,
                "learned_at": datetime.now().isoformat(),
                "notes": notes or "",
                "quiz_score": quiz_score
            }
            
            # 更新知识的学习记录
            knowledge.learning_records.append(record)
            knowledge.value_info.learning_count += 1
            
            # 更新个人的学习记录
            if knowledge_id not in self.learning_records:
                self.learning_records[knowledge_id] = []
            self.learning_records[knowledge_id].append(record)
            
            # 保存
            await self._save_knowledge(knowledge)
            
            logger.info(f"📚 学习记录: {learner_id} -> {knowledge_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"记录学习失败: {e}")
            return False

    async def increment_spread_count(self, knowledge_id: str) -> bool:
        """增加传播计数"""
        try:
            knowledge = await self.get_knowledge(knowledge_id)
            if knowledge:
                knowledge.value_info.spread_count += 1
                await self._save_knowledge(knowledge)
                return True
            return False
        except Exception as e:
            logger.error(f"增加传播计数失败: {e}")
            return False

    async def search(
        self,
        query: str,
        search_type: str = "semantic",
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 20
    ) -> List[KnowledgeUnit]:
        """
        搜索知识
        
        Args:
            query: 搜索查询
            search_type: 搜索类型 (keyword/semantic/related)
            filters: 过滤条件
            limit: 限制数量
            
        Returns:
            匹配的知识列表
        """
        results = []
        
        if search_type == "keyword":
            results = await self._keyword_search(query, filters, limit)
        elif search_type == "semantic":
            results = await self._semantic_search(query, filters, limit)
        elif search_type == "related":
            results = await self._related_search(query, filters, limit)
        else:
            results = await self._keyword_search(query, filters, limit)
        
        return results[:limit]

    async def _keyword_search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]],
        limit: int
    ) -> List[KnowledgeUnit]:
        """关键词搜索"""
        query_lower = query.lower()
        results = []
        
        # 获取所有知识
        for knowledge_id in list(self.blockchain.knowledge_cache.keys()):
            knowledge = self.blockchain.knowledge_cache.get(knowledge_id)
            if not knowledge:
                continue
            
            # 匹配检查
            matched = False
            
            # 标题匹配
            if query_lower in knowledge.content.title.lower():
                matched = True
            
            # 内容匹配
            if query_lower in knowledge.content.content.lower():
                matched = True
            
            # 关键词匹配
            for keyword in knowledge.content.keywords:
                if query_lower in keyword.lower():
                    matched = True
                    break
            
            # 标签匹配
            for tag in knowledge.metadata.domain_tags:
                if query_lower in tag.lower():
                    matched = True
                    break
            
            if matched:
                # 应用过滤器
                if filters:
                    if "knowledge_type" in filters:
                        if knowledge.metadata.knowledge_type != filters["knowledge_type"]:
                            continue
                    if "creator_id" in filters:
                        if knowledge.creator_id != filters["creator_id"]:
                            continue
                    if "min_verification" in filters:
                        if knowledge.verification_info.verification_count < filters["min_verification"]:
                            continue
                
                results.append(knowledge)
        
        return results

    async def _semantic_search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]],
        limit: int
    ) -> List[KnowledgeUnit]:
        """语义搜索"""
        # 生成查询向量
        query_vector = self._generate_simple_vector(query)
        
        results = []
        
        for knowledge_id, stored_vector in self.semantic_vectors.items():
            knowledge = self.blockchain.knowledge_cache.get(knowledge_id)
            if not knowledge:
                continue
            
            # 计算相似度
            similarity = self._cosine_similarity(query_vector, stored_vector)
            
            results.append((similarity, knowledge))
        
        # 按相似度排序
        results.sort(key=lambda x: x[0], reverse=True)
        
        return [k for _, k in results[:limit]]

    async def _related_search(
        self,
        knowledge_id: str,
        filters: Optional[Dict[str, Any]],
        limit: int
    ) -> List[KnowledgeUnit]:
        """关联搜索"""
        knowledge = await self.get_knowledge(knowledge_id)
        if not knowledge:
            return []
        
        # 基于引用搜索
        results = []
        
        # 添加引用的知识
        for ref_id in knowledge.content.references:
            ref = await self.get_knowledge(ref_id)
            if ref:
                results.append(ref)
        
        # 基于相同标签搜索
        for tag in knowledge.metadata.domain_tags:
            tag_knowledge = self.tag_index.get(tag, [])
            for kid in tag_knowledge:
                if kid != knowledge_id:
                    k = await self.get_knowledge(kid)
                    if k and k not in results:
                        results.append(k)
        
        return results[:limit]

    async def sync(self) -> bool:
        """同步知识"""
        try:
            # 重建索引
            await self._rebuild_indexes()
            logger.info("✅ 知识同步完成")
            return True
        except Exception as e:
            logger.error(f"知识同步失败: {e}")
            return False

    def get_knowledge_count(self) -> int:
        """获取知识数量"""
        return len(self.blockchain.knowledge_cache)

    # ==================== 内部方法 ====================

    def _generate_knowledge_id(
        self,
        content_hash: str,
        creator_id: str,
        timestamp: datetime
    ) -> str:
        """生成知识ID"""
        data = f"{content_hash}{creator_id}{timestamp.isoformat()}"
        return hashlib.sha256(data.encode()).hexdigest()[:32]

    async def _update_indexes(self, knowledge: KnowledgeUnit):
        """更新索引"""
        kid = knowledge.knowledge_id
        title = knowledge.content.title
        
        # 标题索引
        words = self._tokenize(title)
        for word in words:
            if word not in self.title_index:
                self.title_index[word] = []
            if kid not in self.title_index[word]:
                self.title_index[word].append(kid)
        
        # 标签索引
        for tag in knowledge.metadata.domain_tags:
            if tag not in self.tag_index:
                self.tag_index[tag] = []
            if kid not in self.tag_index[tag]:
                self.tag_index[tag].append(kid)
        
        # 创建者索引
        creator = knowledge.creator_id
        if creator not in self.creator_index:
            self.creator_index[creator] = []
        if kid not in self.creator_index[creator]:
            self.creator_index[creator].append(kid)
        
        # 类型索引
        ktype = knowledge.metadata.knowledge_type
        if ktype not in self.type_index:
            self.type_index[ktype] = []
        if kid not in self.type_index[ktype]:
            self.type_index[ktype].append(kid)

    async def _rebuild_indexes(self):
        """重建所有索引"""
        self.title_index.clear()
        self.tag_index.clear()
        self.creator_index.clear()
        self.type_index.clear()
        
        for knowledge in self.blockchain.knowledge_cache.values():
            await self._update_indexes(knowledge)

    async def _generate_semantic_vector(self, knowledge: KnowledgeUnit):
        """生成语义向量（简化实现）"""
        text = f"{knowledge.content.title} {knowledge.content.summary} {knowledge.content.content}"
        vector = self._generate_simple_vector(text)
        self.semantic_vectors[knowledge.knowledge_id] = vector

    def _generate_simple_vector(self, text: str, dim: int = 128) -> List[float]:
        """生成简单向量"""
        import random
        
        # 基于文本哈希生成确定性随机向量
        random.seed(hash(text) % (2**32))
        return [random.uniform(-1, 1) for _ in range(dim)]

    def _cosine_similarity(self, v1: List[float], v2: List[float]) -> float:
        """计算余弦相似度"""
        if len(v1) != len(v2):
            return 0.0
        
        dot = sum(a * b for a, b in zip(v1, v2))
        mag1 = sum(a * a for a in v1) ** 0.5
        mag2 = sum(b * b for b in v2) ** 0.5
        
        if mag1 == 0 or mag2 == 0:
            return 0.0
        
        return dot / (mag1 * mag2)

    def _tokenize(self, text: str) -> List[str]:
        """简单分词"""
        # 移除标点，分割单词
        import re
        words = re.findall(r'\w+', text.lower())
        return [w for w in words if len(w) >= 2]

    async def _save_knowledge(self, knowledge: KnowledgeUnit):
        """保存知识到存储"""
        try:
            key = f"knowledge_{knowledge.knowledge_id}"
            data = json.dumps(knowledge.to_dict(), ensure_ascii=False)
            await self.storage.put(key, data)
        except Exception as e:
            logger.error(f"保存知识失败: {e}")

    async def _load_knowledge(self, knowledge_id: str) -> Optional[KnowledgeUnit]:
        """从存储加载知识"""
        try:
            key = f"knowledge_{knowledge_id}"
            data = await self.storage.get(key)
            if data:
                return KnowledgeUnit.from_dict(json.loads(data))
            return None
        except Exception as e:
            logger.error(f"加载知识失败: {e}")
            return None
