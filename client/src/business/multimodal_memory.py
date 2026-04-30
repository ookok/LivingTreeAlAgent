"""
多模态记忆系统 (Multimodal Memory System)
=========================================

借鉴 Claude Managed Agents 的多模态记忆能力：
1. 文本记忆 - 传统文本内容存储和检索
2. 图像记忆 - 图片内容存储和语义理解
3. 图文混合 - 支持图文混合查询和检索
4. 多模态摘要 - 生成包含图文信息的摘要

核心特性：
- 支持多种媒体类型
- 图像语义理解
- 图文关联存储
- 跨模态检索

Author: LivingTreeAlAgent Team
Date: 2026-04-30
"""

import json
import time
import asyncio
from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from uuid import uuid4

logger = __import__('logging').getLogger(__name__)


class MediaType(Enum):
    """媒体类型"""
    TEXT = "text"           # 纯文本
    IMAGE = "image"         # 图像
    AUDIO = "audio"         # 音频
    VIDEO = "video"         # 视频
    DOCUMENT = "document"   # 文档
    CODE = "code"           # 代码


class Modality(Enum):
    """模态类型"""
    TEXT_ONLY = "text_only"           # 纯文本模态
    VISUAL_ONLY = "visual_only"       # 纯视觉模态
    MULTIMODAL = "multimodal"         # 多模态混合


@dataclass
class MultimodalContent:
    """多模态内容"""
    media_type: MediaType
    content: Any           # 内容（文本为字符串，图像为路径或base64）
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None  # 语义向量


@dataclass
class MultimodalMemoryItem:
    """多模态记忆项"""
    id: str
    contents: List[MultimodalContent]
    timestamp: float
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    conversation_id: Optional[str] = None


@dataclass
class MultimodalQuery:
    """多模态查询"""
    query_text: str = ""
    query_image: Optional[str] = None  # 图像路径或base64
    modalities: List[Modality] = field(default_factory=lambda: [Modality.MULTIMODAL])
    limit: int = 10
    threshold: float = 0.5


@dataclass
class MultimodalResult:
    """多模态检索结果"""
    items: List[MultimodalMemoryItem]
    relevance_scores: List[float]
    execution_time: float


class MultimodalMemorySystem:
    """
    多模态记忆系统
    
    核心功能：
    1. 存储多模态内容（文本、图像等）
    2. 图像语义理解和描述生成
    3. 图文混合检索
    4. 跨模态关联
    
    技术架构：
    - 文本处理：语义向量化
    - 图像处理：图像描述生成 + 向量化
    - 检索：多模态相似度匹配
    """
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        # 存储
        self._memory_store: Dict[str, MultimodalMemoryItem] = {}
        
        # LLM 调用函数（用于图像描述）
        self._llm_callable = None
        
        # 图像描述模型
        self._image_captioner = None
        
        # 配置参数
        self._config = {
            "max_memory_items": 1000,
            "image_description_enabled": True,
            "cross_modal_retrieval": True,
            "similarity_threshold": 0.5,
        }
        
        # 图像描述提示词
        self._image_caption_prompt = """请详细描述这张图片的内容，包括：
1. 主要对象和场景
2. 对象的特征和属性
3. 场景氛围和背景
4. 关键细节

描述："""
        
        self._initialized = True
        logger.info("[MultimodalMemorySystem] 多模态记忆系统初始化完成")
    
    def set_llm_callable(self, llm_callable: Callable[[str], str]):
        """设置 LLM 调用函数"""
        self._llm_callable = llm_callable
    
    def configure(self, **kwargs):
        """配置多模态记忆系统"""
        self._config.update(kwargs)
        logger.info(f"[MultimodalMemorySystem] 配置更新: {kwargs}")
    
    def store(self, contents: List[MultimodalContent], 
              conversation_id: str = None, tags: List[str] = None) -> str:
        """
        存储多模态内容
        
        Args:
            contents: 多模态内容列表
            conversation_id: 对话ID（可选）
            tags: 标签列表（可选）
            
        Returns:
            记忆项ID
        """
        # 为图像内容生成描述
        processed_contents = []
        for content in contents:
            if content.media_type == MediaType.IMAGE and self._config["image_description_enabled"]:
                description = self._describe_image(content.content)
                if description:
                    # 添加描述到元数据
                    content.metadata["description"] = description
                    content.metadata["has_description"] = True
                
            processed_contents.append(content)
        
        # 创建记忆项
        item_id = f"mm_{uuid4().hex[:8]}"
        item = MultimodalMemoryItem(
            id=item_id,
            contents=processed_contents,
            timestamp=time.time(),
            tags=tags or [],
            conversation_id=conversation_id
        )
        
        # 存储
        self._memory_store[item_id] = item
        
        # 清理超出限制的旧记忆
        self._cleanup_excess()
        
        logger.debug(f"[MultimodalMemorySystem] 存储多模态记忆: {item_id}")
        return item_id
    
    def store_text(self, text: str, conversation_id: str = None, 
                   tags: List[str] = None) -> str:
        """
        便捷方法：存储纯文本
        
        Args:
            text: 文本内容
            conversation_id: 对话ID
            tags: 标签
            
        Returns:
            记忆项ID
        """
        content = MultimodalContent(
            media_type=MediaType.TEXT,
            content=text
        )
        return self.store([content], conversation_id, tags)
    
    def store_image(self, image_path: str, description: str = None,
                    conversation_id: str = None, tags: List[str] = None) -> str:
        """
        便捷方法：存储图像
        
        Args:
            image_path: 图像路径
            description: 图像描述（可选，自动生成如果为空）
            conversation_id: 对话ID
            tags: 标签
            
        Returns:
            记忆项ID
        """
        content = MultimodalContent(
            media_type=MediaType.IMAGE,
            content=image_path,
            metadata={"description": description} if description else {}
        )
        return self.store([content], conversation_id, tags)
    
    def store_multimodal(self, text: str, image_paths: List[str] = None,
                         conversation_id: str = None, tags: List[str] = None) -> str:
        """
        便捷方法：存储图文混合内容
        
        Args:
            text: 文本内容
            image_paths: 图像路径列表
            conversation_id: 对话ID
            tags: 标签
            
        Returns:
            记忆项ID
        """
        contents = []
        
        # 添加文本内容
        if text:
            contents.append(MultimodalContent(
                media_type=MediaType.TEXT,
                content=text
            ))
        
        # 添加图像内容
        if image_paths:
            for image_path in image_paths:
                contents.append(MultimodalContent(
                    media_type=MediaType.IMAGE,
                    content=image_path
                ))
        
        return self.store(contents, conversation_id, tags)
    
    def retrieve(self, query: MultimodalQuery) -> MultimodalResult:
        """
        多模态检索
        
        Args:
            query: 多模态查询
            
        Returns:
            MultimodalResult: 检索结果
        """
        start_time = time.time()
        
        results = []
        scores = []
        
        # 简单的检索逻辑（可扩展为向量化检索）
        for item_id, item in self._memory_store.items():
            score = self._calculate_similarity(query, item)
            if score >= query.threshold:
                results.append(item)
                scores.append(score)
        
        # 按相似度排序
        sorted_pairs = sorted(zip(results, scores), key=lambda x: x[1], reverse=True)
        results, scores = zip(*sorted_pairs) if sorted_pairs else ([], [])
        
        # 限制结果数量
        results = list(results)[:query.limit]
        scores = list(scores)[:query.limit]
        
        return MultimodalResult(
            items=results,
            relevance_scores=scores,
            execution_time=time.time() - start_time
        )
    
    def retrieve_text(self, query_text: str, limit: int = 10) -> List[MultimodalMemoryItem]:
        """
        便捷方法：文本检索
        
        Args:
            query_text: 查询文本
            limit: 结果数量限制
            
        Returns:
            记忆项列表
        """
        query = MultimodalQuery(
            query_text=query_text,
            modalities=[Modality.TEXT_ONLY],
            limit=limit
        )
        result = self.retrieve(query)
        return result.items
    
    def retrieve_image(self, query_image: str, limit: int = 10) -> List[MultimodalMemoryItem]:
        """
        便捷方法：图像检索（以图搜图）
        
        Args:
            query_image: 查询图像路径
            limit: 结果数量限制
            
        Returns:
            记忆项列表
        """
        # 先为查询图像生成描述
        description = self._describe_image(query_image)
        
        query = MultimodalQuery(
            query_text=description,
            query_image=query_image,
            modalities=[Modality.VISUAL_ONLY],
            limit=limit
        )
        result = self.retrieve(query)
        return result.items
    
    def get_item(self, item_id: str) -> Optional[MultimodalMemoryItem]:
        """获取指定记忆项"""
        return self._memory_store.get(item_id)
    
    def delete_item(self, item_id: str) -> bool:
        """删除指定记忆项"""
        if item_id in self._memory_store:
            del self._memory_store[item_id]
            return True
        return False
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        text_count = 0
        image_count = 0
        for item in self._memory_store.values():
            for content in item.contents:
                if content.media_type == MediaType.TEXT:
                    text_count += 1
                elif content.media_type == MediaType.IMAGE:
                    image_count += 1
        
        return {
            "total_items": len(self._memory_store),
            "text_items": text_count,
            "image_items": image_count,
            "config": self._config,
        }
    
    # ========== 私有方法 ==========
    
    def _describe_image(self, image_path: str) -> Optional[str]:
        """
        为图像生成文字描述
        
        Args:
            image_path: 图像路径
            
        Returns:
            图像描述（如果生成成功）
        """
        if not self._llm_callable:
            # 尝试使用多模态模型
            try:
                # 这里可以集成多模态模型如 Claude 3 Opus
                # 目前返回简单的占位描述
                return f"图像: {image_path}"
            except Exception as e:
                logger.warning(f"[MultimodalMemorySystem] 图像描述失败: {e}")
                return None
        
        try:
            # 使用 LLM 生成描述（需要多模态模型支持）
            # 这里模拟生成描述
            prompt = self._image_caption_prompt
            response = self._llm_callable(prompt)
            return response.strip()
        except Exception as e:
            logger.error(f"[MultimodalMemorySystem] 生成图像描述失败: {e}")
            return None
    
    def _calculate_similarity(self, query: MultimodalQuery, item: MultimodalMemoryItem) -> float:
        """
        计算查询与记忆项的相似度
        
        Args:
            query: 查询
            item: 记忆项
            
        Returns:
            相似度分数 0-1
        """
        score = 0.0
        match_count = 0
        total_checks = 0
        
        # 文本相似度
        if query.query_text:
            query_words = set(query.query_text.lower().split())
            
            for content in item.contents:
                if content.media_type == MediaType.TEXT:
                    text_content = str(content.content).lower()
                    text_words = set(text_content.split())
                    overlap = query_words & text_words
                    if overlap:
                        match_count += len(overlap) / max(len(query_words), len(text_words))
                    total_checks += 1
                
                elif content.media_type == MediaType.IMAGE:
                    # 使用图像描述进行匹配
                    description = content.metadata.get("description", "")
                    if description:
                        desc_words = set(description.lower().split())
                        overlap = query_words & desc_words
                        if overlap:
                            match_count += len(overlap) / max(len(query_words), len(desc_words))
                        total_checks += 1
        
        # 如果没有检查项，返回0
        if total_checks == 0:
            return 0.0
        
        return match_count / total_checks
    
    def _cleanup_excess(self):
        """清理超出限制的旧记忆"""
        max_items = self._config["max_memory_items"]
        
        if len(self._memory_store) <= max_items:
            return
        
        # 按时间排序，删除最旧的
        sorted_items = sorted(
            self._memory_store.items(),
            key=lambda x: x[1].timestamp
        )
        
        # 删除超出限制的部分
        items_to_delete = sorted_items[:-max_items]
        for item_id, _ in items_to_delete:
            del self._memory_store[item_id]
        
        logger.info(f"[MultimodalMemorySystem] 清理了 {len(items_to_delete)} 个旧记忆")


# 便捷函数
def get_multimodal_memory() -> MultimodalMemorySystem:
    """获取多模态记忆系统单例"""
    return MultimodalMemorySystem()


__all__ = [
    "MediaType",
    "Modality",
    "MultimodalContent",
    "MultimodalMemoryItem",
    "MultimodalQuery",
    "MultimodalResult",
    "MultimodalMemorySystem",
    "get_multimodal_memory",
]