"""
FusionRAG 统一类型定义

合并增强自:
- engine.py RAGResult + IngestResult
- query_engine.py QueryResult + SearchHit
- smart_vector_store.py SearchResult
- triple_chain_engine.py ReasoningStep + Evidence + TripleChainResult

统一后：7个重复类型 → 4个清晰类型，避免类型不兼容问题。
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
import re
import hashlib


# ============================================================================
# 统一结果类型
# ============================================================================

@dataclass
class SearchHit:
    """搜索结果项（统一 smart_vector_store.SearchResult + query_engine.SearchHit）"""
    id: str = ""
    content: str = ""
    score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    source_type: str = ""          # "vector" / "graph" / "cache" / "database"
    source_layer: str = ""         # "L1" / "L2" / "L3" / "L4"
    embedding: Optional[List[float]] = None


@dataclass
class RAGResult:
    """RAG 查询结果（统一 engine.RAGResult + query_engine.QueryResult）

    增强: 可选的推理链和证据链（来自 triple_chain_engine）
    """
    content: str = ""
    sources: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    reasoning: Optional[str] = None
    entities: List[Dict[str, Any]] = field(default_factory=list)
    related_queries: List[str] = field(default_factory=list)
    reasoning_steps: List[Dict[str, Any]] = field(default_factory=list)
    evidences: List[Dict[str, Any]] = field(default_factory=list)
    search_hits: List[SearchHit] = field(default_factory=list)

    @property
    def has_reasoning(self) -> bool:
        return bool(self.reasoning_steps and self.evidences)

    @property
    def is_high_confidence(self) -> bool:
        return self.confidence >= 0.7


@dataclass
class IngestResult:
    """数据摄入结果"""
    success: bool = False
    document_id: str = ""
    entities_count: int = 0
    relations_count: int = 0
    chunks_count: int = 0
    message: str = ""


# ============================================================================
# 共享嵌入工具（消除 engine.py 和 query_engine.py 的重复代码）
# ============================================================================

# 中英文分词正则
_WORD_PATTERN = re.compile(r'[\w]+')
_CJK_PATTERN = re.compile(r'[\u4e00-\u9fa5]{2,8}|[A-Za-z]{2,}|[A-Za-z]+\d+')


def generate_embedding(text: str, dim: int = 384) -> List[float]:
    """生成文本嵌入向量（共享实现，消除 DRY 违规）

    基于 hash 的轻量级嵌入，用于快速原型和降级模式。
    生产环境应使用 LLM embedding API。

    Args:
        text: 输入文本
        dim: 向量维度（默认384，与 SmartVectorStore 默认一致）

    Returns:
        L2归一化的嵌入向量
    """
    if not text:
        return [0.0] * dim

    text_lower = text.lower()
    vector = [0.0] * dim

    # 提取中文词组 + 英文单词
    tokens = _CJK_PATTERN.findall(text_lower)
    if not tokens:
        tokens = _WORD_PATTERN.findall(text_lower)

    for token in tokens:
        idx = hash(token) % dim
        vector[idx] += 1.0

    # 也处理单个字符（补充低频信息）
    for i, ch in enumerate(text_lower[:dim * 2]):
        idx = (hash(ch) + i) % dim
        vector[idx] += 0.1

    # L2 归一化
    norm = sum(v * v for v in vector) ** 0.5
    if norm > 0:
        vector = [v / norm for v in vector]

    return vector


def generate_content_hash(content: str) -> str:
    """生成内容哈希（用于结果去重）"""
    return hashlib.md5(content.encode()).hexdigest()[:12]


def extract_entities(text: str) -> List[str]:
    """提取文本中的命名实体"""
    entities = []
    # 英文大写词
    entities.extend(re.findall(r'\b[A-Z][a-z]+\b', text))
    # 中文实体（2-6字连续）
    entities.extend(re.findall(r'[\u4e00-\u9fa5]{2,6}', text))
    return list(set(entities))
