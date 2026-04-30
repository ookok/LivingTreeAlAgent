"""
AdaptiveDeduplicator - 自适应三级去重器

核心功能：
1. 第一级：快速哈希匹配（精确去重）
2. 第二级：语义相似度匹配（模糊去重）
3. 第三级：增量更新检测（版本去重）

支持根据上下文动态调整去重阈值：
- 法律文档：严格（0.95）
- 创意写作：宽松（0.7）
- 代码：中等（0.85）
"""

import hashlib
import json
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class DeduplicationResult:
    """去重结果"""
    is_duplicate: bool
    duplicate_type: str = ""  # exact/semantic/version/none
    similarity_score: float = 0.0
    matched_id: Optional[str] = None
    message: str = ""
    base_version: Optional[str] = None


@dataclass
class VersionInfo:
    """版本信息"""
    content_id: str
    version: int
    parent_version: Optional[int] = None
    timestamp: float = 0.0
    content_hash: str = ""


class AdaptiveDeduplicator:
    """自适应三级去重器"""
    
    # 上下文阈值配置
    CONTEXT_THRESHOLDS = {
        "legal": 0.95,      # 法律文档：严格
        "creative": 0.7,     # 创意写作：宽松
        "code": 0.85,        # 代码：中等
        "technical": 0.9,    # 技术文档：较严格
        "financial": 0.92,   # 财务文档：严格
        "medical": 0.93,     # 医疗文档：严格
        "default": 0.9       # 默认：中等严格
    }
    
    def __init__(self):
        self._logger = logger.bind(component="AdaptiveDeduplicator")
        
        # 第一级：哈希去重（精确匹配）
        self._content_hashes: set = set()
        
        # 第二级：语义去重（模糊匹配）
        self._semantic_store: Dict[str, dict] = {}
        
        # 第三级：版本去重
        self._version_store: Dict[str, List[VersionInfo]] = {}
        
        self._logger.info("AdaptiveDeduplicator 初始化完成")
    
    def deduplicate(self, content: str, context: str = "default", content_id: str = None) -> DeduplicationResult:
        """
        三级去重检测
        
        Args:
            content: 待检测内容
            context: 上下文类型（legal/creative/code/technical/financial/medical/default）
            content_id: 内容ID（用于版本追踪）
        
        Returns:
            去重结果
        """
        # 第一级：快速哈希匹配（精确去重）
        content_hash = self._calculate_hash(content)
        if self._fast_hash_check(content_hash):
            return DeduplicationResult(
                is_duplicate=True,
                duplicate_type="exact",
                message="内容完全重复"
            )
        
        # 第二级：语义相似度匹配（模糊去重）
        threshold = self._get_threshold(context)
        semantic_result = self._semantic_check(content, content_id, threshold)
        if semantic_result.is_duplicate:
            return semantic_result
        
        # 第三级：增量更新检测（版本去重）
        version_result = self._version_check(content, content_id)
        if version_result.is_duplicate:
            return version_result
        
        # 不是重复，添加到存储
        self._add_content(content, content_hash, content_id)
        
        return DeduplicationResult(
            is_duplicate=False,
            duplicate_type="unique",
            message="内容唯一"
        )
    
    def _calculate_hash(self, content: str) -> str:
        """计算内容哈希"""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    def _fast_hash_check(self, content_hash: str) -> bool:
        """快速哈希检查"""
        if content_hash in self._content_hashes:
            self._logger.debug(f"精确重复检测：哈希匹配")
            return True
        return False
    
    def _get_threshold(self, context: str) -> float:
        """根据上下文动态调整去重阈值"""
        threshold = self.CONTEXT_THRESHOLDS.get(context, self.CONTEXT_THRESHOLDS["default"])
        self._logger.debug(f"使用上下文阈值: {context} -> {threshold}")
        return threshold
    
    def _semantic_check(self, content: str, content_id: str, threshold: float) -> DeduplicationResult:
        """语义相似度匹配"""
        if not self._semantic_store:
            return DeduplicationResult(is_duplicate=False, duplicate_type="none")
        
        # 获取当前内容的向量表示
        current_vector = self._text_to_vector(content)
        
        # 搜索最相似的内容
        max_similarity = 0.0
        matched_id = None
        
        for stored_id, stored_data in self._semantic_store.items():
            if stored_id == content_id:
                continue
            
            stored_vector = stored_data["vector"]
            similarity = self._cosine_similarity(current_vector, stored_vector)
            
            if similarity > max_similarity:
                max_similarity = similarity
                matched_id = stored_id
        
        if max_similarity >= threshold:
            self._logger.debug(f"语义重复检测：相似度 {max_similarity:.2f} >= 阈值 {threshold}")
            return DeduplicationResult(
                is_duplicate=True,
                duplicate_type="semantic",
                similarity_score=max_similarity,
                matched_id=matched_id,
                message=f"语义相似度 {max_similarity:.2f} >= 阈值 {threshold}"
            )
        
        return DeduplicationResult(
            is_duplicate=False,
            duplicate_type="none",
            similarity_score=max_similarity
        )
    
    def _text_to_vector(self, text: str) -> Dict[str, float]:
        """将文本转换为向量表示"""
        import re
        words = re.findall(r'[\u4e00-\u9fa5a-zA-Z0-9]+', text.lower())
        word_counts = {}
        
        for word in words:
            word_counts[word] = word_counts.get(word, 0) + 1
        
        total = sum(word_counts.values())
        if total > 0:
            return {word: count / total for word, count in word_counts.items()}
        
        return {}
    
    def _cosine_similarity(self, vec1: Dict[str, float], vec2: Dict[str, float]) -> float:
        """计算余弦相似度"""
        if not vec1 or not vec2:
            return 0.0
        
        dot_product = 0.0
        norm1 = 0.0
        norm2 = 0.0
        
        for word, val1 in vec1.items():
            if word in vec2:
                dot_product += val1 * vec2[word]
            norm1 += val1 * val1
        
        for val2 in vec2.values():
            norm2 += val2 * val2
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 ** 0.5 * norm2 ** 0.5)
    
    def _version_check(self, content: str, content_id: str) -> DeduplicationResult:
        """增量更新检测"""
        if not content_id:
            return DeduplicationResult(is_duplicate=False, duplicate_type="none")
        
        if content_id not in self._version_store:
            return DeduplicationResult(is_duplicate=False, duplicate_type="none")
        
        # 检查是否是已有版本的更新
        versions = self._version_store[content_id]
        if versions:
            latest_version = versions[-1]
            content_hash = self._calculate_hash(content)
            
            if content_hash == latest_version.content_hash:
                return DeduplicationResult(
                    is_duplicate=True,
                    duplicate_type="version",
                    base_version=f"{content_id}_v{latest_version.version}",
                    message="与最新版本相同"
                )
        
        return DeduplicationResult(is_duplicate=False, duplicate_type="none")
    
    def _add_content(self, content: str, content_hash: str, content_id: str = None):
        """添加内容到存储"""
        # 添加哈希
        self._content_hashes.add(content_hash)
        
        # 添加语义向量
        if content_id:
            self._semantic_store[content_id] = {
                "content": content,
                "vector": self._text_to_vector(content),
                "content_hash": content_hash
            }
            
            # 添加版本信息
            if content_id not in self._version_store:
                self._version_store[content_id] = []
            
            versions = self._version_store[content_id]
            new_version = VersionInfo(
                content_id=content_id,
                version=len(versions) + 1,
                parent_version=versions[-1].version if versions else None,
                timestamp=0.0,
                content_hash=content_hash
            )
            self._version_store[content_id].append(new_version)
    
    def add_version(self, content_id: str, content: str):
        """显式添加版本"""
        content_hash = self._calculate_hash(content)
        
        if content_id not in self._version_store:
            self._version_store[content_id] = []
        
        versions = self._version_store[content_id]
        new_version = VersionInfo(
            content_id=content_id,
            version=len(versions) + 1,
            parent_version=versions[-1].version if versions else None,
            timestamp=0.0,
            content_hash=content_hash
        )
        self._version_store[content_id].append(new_version)
        
        # 更新语义存储
        self._semantic_store[content_id] = {
            "content": content,
            "vector": self._text_to_vector(content),
            "content_hash": content_hash
        }
    
    def get_version_history(self, content_id: str) -> List[VersionInfo]:
        """获取版本历史"""
        return self._version_store.get(content_id, [])
    
    def set_context_threshold(self, context: str, threshold: float):
        """设置上下文阈值"""
        if 0.0 <= threshold <= 1.0:
            self.CONTEXT_THRESHOLDS[context] = threshold
            self._logger.info(f"更新上下文阈值: {context} -> {threshold}")
        else:
            raise ValueError("阈值必须在0.0到1.0之间")
    
    def get_statistics(self) -> Dict:
        """获取统计信息"""
        return {
            "total_hashes": len(self._content_hashes),
            "semantic_entries": len(self._semantic_store),
            "versioned_contents": len(self._version_store),
            "context_thresholds": dict(self.CONTEXT_THRESHOLDS)
        }


# 单例模式
_adaptive_deduplicator_instance = None

def get_adaptive_deduplicator() -> AdaptiveDeduplicator:
    """获取自适应去重器实例"""
    global _adaptive_deduplicator_instance
    if _adaptive_deduplicator_instance is None:
        _adaptive_deduplicator_instance = AdaptiveDeduplicator()
    return _adaptive_deduplicator_instance


if __name__ == "__main__":
    print("=" * 60)
    print("AdaptiveDeduplicator 测试")
    print("=" * 60)
    
    deduplicator = get_adaptive_deduplicator()
    
    # 测试精确去重
    print("\n[1] 精确去重测试")
    text1 = "今天天气很好，我想去公园散步。"
    text2 = "今天天气很好，我想去公园散步。"  # 完全相同
    
    result1 = deduplicator.deduplicate(text1, content_id="id1")
    print(f"文本1 (新): 重复={result1.is_duplicate}, 类型={result1.duplicate_type}")
    
    result2 = deduplicator.deduplicate(text2, content_id="id2")
    print(f"文本2 (重复): 重复={result2.is_duplicate}, 类型={result2.duplicate_type}")
    
    # 测试语义去重（不同上下文）
    print("\n[2] 语义去重测试")
    text3 = "人工智能是研究智能机器的技术。"
    text4 = "AI是研究智能机器的技术。"  # 语义相同
    text5 = "机器学习是人工智能的一个分支。"  # 相关但不同
    
    result3 = deduplicator.deduplicate(text3, context="technical", content_id="id3")
    print(f"文本3 (新): 重复={result3.is_duplicate}, 相似度={result3.similarity_score:.2f}")
    
    result4 = deduplicator.deduplicate(text4, context="technical", content_id="id4")
    print(f"文本4 (语义相同): 重复={result4.is_duplicate}, 类型={result4.duplicate_type}, 相似度={result4.similarity_score:.2f}")
    
    result5 = deduplicator.deduplicate(text5, context="technical", content_id="id5")
    print(f"文本5 (相关): 重复={result5.is_duplicate}, 相似度={result5.similarity_score:.2f}")
    
    # 测试创意上下文（宽松阈值）
    print("\n[3] 创意上下文测试")
    text6 = "夕阳下的湖面波光粼粼"
    text7 = "落日余晖洒在波光粼粼的湖面上"
    
    result6 = deduplicator.deduplicate(text6, context="creative", content_id="id6")
    result7 = deduplicator.deduplicate(text7, context="creative", content_id="id7")
    print(f"创意文本6 (新): 重复={result6.is_duplicate}")
    print(f"创意文本7 (相似): 重复={result7.is_duplicate}, 相似度={result7.similarity_score:.2f}")
    
    # 测试版本去重
    print("\n[4] 版本去重测试")
    base_text = "版本1: 基础内容"
    update_text = "版本1: 基础内容"  # 与版本1相同
    
    deduplicator.add_version("doc_001", base_text)
    result8 = deduplicator.deduplicate(update_text, content_id="doc_001")
    print(f"重复版本检测: 重复={result8.is_duplicate}, 类型={result8.duplicate_type}, 基础版本={result8.base_version}")
    
    # 统计信息
    print("\n[5] 统计信息")
    stats = deduplicator.get_statistics()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)