"""
智能去重模块 (Smart Deduplication)

核心功能：
1. 内容级去重：布隆过滤器快速粗筛
2. 语义级去重：向量相似度匹配
3. 支持完全重复和语义重复的区分

参考文档：智能去重：语义指纹与布隆过滤器
"""

import hashlib
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class DeduplicationResult:
    """去重结果"""
    is_duplicate: bool
    duplicate_type: str = ""  # content/semantic/none
    similarity_score: float = 0.0
    matched_id: Optional[str] = None
    message: str = ""


class SmartDeduplication:
    """智能去重器"""
    
    def __init__(self):
        self._logger = logger.bind(component="SmartDeduplication")
        
        # 布隆过滤器（简化实现，使用集合模拟）
        self._content_hashes: set = set()
        
        # 语义向量存储（简化实现，使用字典存储文本和向量）
        self._semantic_store: Dict[str, dict] = {}
        
        # 相似度阈值
        self._semantic_threshold = 0.9
        
        self._logger.info("智能去重模块初始化完成")
    
    def is_duplicate_content(self, content: str) -> bool:
        """
        内容级去重：检查是否完全重复
        
        Args:
            content: 内容文本
        
        Returns:
            是否重复
        """
        # 计算内容哈希
        content_hash = self._compute_content_hash(content)
        
        if content_hash in self._content_hashes:
            self._logger.debug(f"内容重复检测：哈希匹配")
            return True
        
        # 添加到集合
        self._content_hashes.add(content_hash)
        return False
    
    def _compute_content_hash(self, content: str) -> str:
        """计算内容哈希"""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    def is_duplicate_semantic(self, content: str, content_id: str = None) -> DeduplicationResult:
        """
        语义级去重：检查是否语义重复
        
        Args:
            content: 内容文本
            content_id: 内容ID（用于排除自身对比）
        
        Returns:
            去重结果
        """
        if not self._semantic_store:
            # 没有存储的语义向量，直接添加
            self._add_semantic(content, content_id)
            return DeduplicationResult(is_duplicate=False, duplicate_type="none")
        
        # 获取当前内容的向量表示（简化实现：使用TF-IDF思想）
        current_vector = self._text_to_vector(content)
        
        # 搜索最相似的内容
        max_similarity = 0.0
        matched_id = None
        
        for stored_id, stored_data in self._semantic_store.items():
            # 排除自身对比
            if stored_id == content_id:
                continue
            
            stored_vector = stored_data["vector"]
            similarity = self._cosine_similarity(current_vector, stored_vector)
            
            if similarity > max_similarity:
                max_similarity = similarity
                matched_id = stored_id
        
        # 判断是否语义重复
        if max_similarity >= self._semantic_threshold:
            self._logger.debug(f"语义重复检测：相似度 {max_similarity:.2f}, 匹配ID: {matched_id}")
            return DeduplicationResult(
                is_duplicate=True,
                duplicate_type="semantic",
                similarity_score=max_similarity,
                matched_id=matched_id,
                message=f"语义相似度 {max_similarity:.2f} >= 阈值 {self._semantic_threshold}"
            )
        
        # 添加新内容
        self._add_semantic(content, content_id)
        
        return DeduplicationResult(
            is_duplicate=False,
            duplicate_type="none",
            similarity_score=max_similarity
        )
    
    def _text_to_vector(self, text: str) -> Dict[str, float]:
        """
        将文本转换为向量表示（简化实现）
        
        使用词频作为向量值
        """
        words = self._tokenize(text)
        word_counts = {}
        
        for word in words:
            word_counts[word] = word_counts.get(word, 0) + 1
        
        # 归一化
        total = sum(word_counts.values())
        if total > 0:
            return {word: count / total for word, count in word_counts.items()}
        
        return {}
    
    def _tokenize(self, text: str) -> List[str]:
        """简单分词"""
        import re
        return re.findall(r'[\u4e00-\u9fa5a-zA-Z0-9]+', text.lower())
    
    def _cosine_similarity(self, vec1: Dict[str, float], vec2: Dict[str, float]) -> float:
        """计算余弦相似度"""
        if not vec1 or not vec2:
            return 0.0
        
        dot_product = 0.0
        norm1 = 0.0
        norm2 = 0.0
        
        # 计算点积和范数
        for word, val1 in vec1.items():
            if word in vec2:
                dot_product += val1 * vec2[word]
            norm1 += val1 * val1
        
        for val2 in vec2.values():
            norm2 += val2 * val2
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 ** 0.5 * norm2 ** 0.5)
    
    def _add_semantic(self, content: str, content_id: str = None):
        """添加语义向量到存储"""
        if content_id is None:
            content_id = str(hash(content))
        
        self._semantic_store[content_id] = {
            "content": content,
            "vector": self._text_to_vector(content),
            "added_at": 0.0  # 简化实现
        }
    
    def check_duplicate(self, content: str, content_id: str = None) -> DeduplicationResult:
        """
        综合去重检查：先内容级，再语义级
        
        Args:
            content: 内容文本
            content_id: 内容ID
        
        Returns:
            去重结果
        """
        # 1. 先检查内容级重复
        if self.is_duplicate_content(content):
            return DeduplicationResult(
                is_duplicate=True,
                duplicate_type="content",
                message="内容完全重复"
            )
        
        # 2. 再检查语义级重复
        return self.is_duplicate_semantic(content, content_id)
    
    def set_semantic_threshold(self, threshold: float):
        """设置语义相似度阈值"""
        self._semantic_threshold = max(0.0, min(1.0, threshold))
    
    def get_statistics(self) -> Dict:
        """获取统计信息"""
        return {
            "content_hash_count": len(self._content_hashes),
            "semantic_store_count": len(self._semantic_store),
            "semantic_threshold": self._semantic_threshold
        }


# 单例模式
_smart_deduplication_instance = None

def get_smart_deduplication() -> SmartDeduplication:
    """获取智能去重器实例"""
    global _smart_deduplication_instance
    if _smart_deduplication_instance is None:
        _smart_deduplication_instance = SmartDeduplication()
    return _smart_deduplication_instance


if __name__ == "__main__":
    print("=" * 60)
    print("智能去重模块测试")
    print("=" * 60)
    
    deduplicator = get_smart_deduplication()
    
    # 测试内容级去重
    print("\n[1] 内容级去重测试")
    text1 = "今天天气很好，我想去公园散步。"
    text2 = "今天天气很好，我想去公园散步。"  # 完全相同
    text3 = "今天天气不错，我想去公园散步。"  # 略有不同
    
    result1 = deduplicator.check_duplicate(text1, "id1")
    print(f"文本1 (新): 重复={result1.is_duplicate}, 类型={result1.duplicate_type}")
    
    result2 = deduplicator.check_duplicate(text2, "id2")
    print(f"文本2 (重复): 重复={result2.is_duplicate}, 类型={result2.duplicate_type}")
    
    result3 = deduplicator.check_duplicate(text3, "id3")
    print(f"文本3 (不同): 重复={result3.is_duplicate}, 类型={result3.duplicate_type}")
    
    # 测试语义级去重
    print("\n[2] 语义级去重测试")
    text4 = "人工智能是研究智能机器的技术。"
    text5 = "AI是研究智能机器的技术。"  # 语义相同
    text6 = "机器学习是人工智能的一个分支。"  # 相关但不同
    
    result4 = deduplicator.check_duplicate(text4, "id4")
    print(f"文本4 (新): 重复={result4.is_duplicate}, 相似度={result4.similarity_score:.2f}")
    
    result5 = deduplicator.check_duplicate(text5, "id5")
    print(f"文本5 (语义相同): 重复={result5.is_duplicate}, 类型={result5.duplicate_type}, 相似度={result5.similarity_score:.2f}")
    
    result6 = deduplicator.check_duplicate(text6, "id6")
    print(f"文本6 (相关): 重复={result6.is_duplicate}, 类型={result6.duplicate_type}, 相似度={result6.similarity_score:.2f}")
    
    # 统计信息
    print("\n[3] 统计信息")
    stats = deduplicator.get_statistics()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)