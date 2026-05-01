"""
证据记忆系统 (Evidence Memory System)
基于 Doc-V* 的结构化工作记忆设计

功能:
- 存储和管理证据片段
- 跟踪来源、置信度、相关性
- 支持证据聚合与推理链构建
- 实现选择性注意力机制
"""

import uuid
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import OrderedDict


class EvidenceType(Enum):
    """证据类型"""
    TEXT = "text"
    VISUAL = "visual"
    STRUCTURED = "structured"
    SEMANTIC = "semantic"
    METADATA = "metadata"


class EvidenceStatus(Enum):
    """证据状态"""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    IN_PROGRESS = "in_progress"


@dataclass
class Evidence:
    """证据片段数据结构"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    content: str = ""
    content_type: EvidenceType = EvidenceType.TEXT
    source: str = ""
    source_type: str = "document"  # document, image, web, etc.
    page_number: Optional[int] = None
    region: Optional[Tuple[int, int, int, int]] = None  # x, y, width, height
    confidence: float = 0.0
    relevance: float = 0.0
    status: EvidenceStatus = EvidenceStatus.PENDING
    timestamp: float = field(default_factory=lambda: 0)
    metadata: Dict[str, Any] = field(default_factory=dict)
    references: List[str] = field(default_factory=list)  # 引用的其他证据ID
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "id": self.id,
            "content": self.content,
            "content_type": self.content_type.value,
            "source": self.source,
            "source_type": self.source_type,
            "page_number": self.page_number,
            "region": self.region,
            "confidence": self.confidence,
            "relevance": self.relevance,
            "status": self.status.value,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
            "references": self.references
        }


class EvidenceMemory:
    """
    结构化工作记忆系统
    
    实现 Doc-V* 的核心思想：
    1. 证据聚合 - 收集来自不同页面的证据
    2. 选择性注意力 - 关注高相关性证据
    3. 可追溯性 - 记录证据来源和推理链
    """
    
    def __init__(self, max_capacity: int = 1000):
        """
        初始化证据记忆系统
        
        Args:
            max_capacity: 最大存储容量
        """
        self._evidences: OrderedDict[str, Evidence] = OrderedDict()
        self._max_capacity = max_capacity
        self._metadata: Dict[str, Any] = {
            "total_added": 0,
            "total_used": 0,
            "total_confirmed": 0,
            "total_rejected": 0
        }
        
        # 索引
        self._source_index: Dict[str, List[str]] = {}  # source -> [evidence_ids]
        self._page_index: Dict[int, List[str]] = {}    # page -> [evidence_ids]
        self._type_index: Dict[str, List[str]] = {}     # type -> [evidence_ids]
        
        print("[EvidenceMemory] 初始化完成，最大容量:", max_capacity)
    
    @property
    def evidence_count(self) -> int:
        """当前证据数量"""
        return len(self._evidences)
    
    @property
    def metadata(self) -> Dict[str, Any]:
        """获取元数据统计"""
        return self._metadata.copy()
    
    def add_evidence(
        self,
        content: str,
        source: str,
        content_type: EvidenceType = EvidenceType.TEXT,
        source_type: str = "document",
        page_number: Optional[int] = None,
        region: Optional[Tuple[int, int, int, int]] = None,
        confidence: float = 0.5,
        relevance: float = 0.5,
        references: Optional[List[str]] = None,
        **kwargs
    ) -> str:
        """
        添加证据片段
        
        Args:
            content: 证据内容
            source: 来源标识（如文档路径、URL等）
            content_type: 内容类型
            source_type: 来源类型
            page_number: 页码（如果来自多页文档）
            region: 视觉区域（x, y, width, height）
            confidence: 置信度 (0-1)
            relevance: 相关性 (0-1)
            references: 引用的其他证据ID列表
            
        Returns:
            证据ID
        """
        # 确保容量
        self._ensure_capacity()
        
        evidence = Evidence(
            content=content,
            content_type=content_type,
            source=source,
            source_type=source_type,
            page_number=page_number,
            region=region,
            confidence=confidence,
            relevance=relevance,
            references=references or [],
            metadata=kwargs
        )
        
        # 添加到存储
        self._evidences[evidence.id] = evidence
        
        # 更新索引
        self._update_index(evidence)
        
        # 更新统计
        self._metadata["total_added"] += 1
        
        return evidence.id
    
    def _ensure_capacity(self):
        """确保存储空间不超过最大容量"""
        while len(self._evidences) >= self._max_capacity:
            # 移除最老的或相关性最低的证据
            oldest_id = next(iter(self._evidences.keys()))
            self.remove_evidence(oldest_id)
    
    def _update_index(self, evidence: Evidence):
        """更新索引"""
        # 来源索引
        if evidence.source not in self._source_index:
            self._source_index[evidence.source] = []
        if evidence.id not in self._source_index[evidence.source]:
            self._source_index[evidence.source].append(evidence.id)
        
        # 页码索引
        if evidence.page_number is not None:
            if evidence.page_number not in self._page_index:
                self._page_index[evidence.page_number] = []
            if evidence.id not in self._page_index[evidence.page_number]:
                self._page_index[evidence.page_number].append(evidence.id)
        
        # 类型索引
        type_key = evidence.content_type.value
        if type_key not in self._type_index:
            self._type_index[type_key] = []
        if evidence.id not in self._type_index[type_key]:
            self._type_index[type_key].append(evidence.id)
    
    def remove_evidence(self, evidence_id: str) -> bool:
        """
        移除证据
        
        Args:
            evidence_id: 证据ID
            
        Returns:
            是否成功移除
        """
        if evidence_id not in self._evidences:
            return False
        
        evidence = self._evidences[evidence_id]
        
        # 从索引中移除
        if evidence.source in self._source_index:
            self._source_index[evidence.source].remove(evidence_id)
            if not self._source_index[evidence.source]:
                del self._source_index[evidence.source]
        
        if evidence.page_number is not None and evidence.page_number in self._page_index:
            self._page_index[evidence.page_number].remove(evidence_id)
            if not self._page_index[evidence.page_number]:
                del self._page_index[evidence.page_number]
        
        type_key = evidence.content_type.value
        if type_key in self._type_index:
            self._type_index[type_key].remove(evidence_id)
            if not self._type_index[type_key]:
                del self._type_index[type_key]
        
        # 从存储中移除
        del self._evidences[evidence_id]
        
        return True
    
    def get_evidence(self, evidence_id: str) -> Optional[Evidence]:
        """获取单个证据"""
        return self._evidences.get(evidence_id)
    
    def get_evidences_by_source(self, source: str) -> List[Evidence]:
        """按来源获取证据"""
        ids = self._source_index.get(source, [])
        return [self._evidences[id] for id in ids if id in self._evidences]
    
    def get_evidences_by_page(self, page_number: int) -> List[Evidence]:
        """按页码获取证据"""
        ids = self._page_index.get(page_number, [])
        return [self._evidences[id] for id in ids if id in self._evidences]
    
    def get_evidences_by_type(self, content_type: EvidenceType) -> List[Evidence]:
        """按类型获取证据"""
        ids = self._type_index.get(content_type.value, [])
        return [self._evidences[id] for id in ids if id in self._evidences]
    
    def get_top_evidences(
        self,
        top_k: int = 10,
        min_confidence: float = 0.0,
        min_relevance: float = 0.0,
        status_filter: Optional[EvidenceStatus] = None
    ) -> List[Evidence]:
        """
        获取排序后的证据列表
        
        排序依据: relevance * confidence
        
        Args:
            top_k: 返回数量
            min_confidence: 最小置信度
            min_relevance: 最小相关性
            status_filter: 状态过滤
            
        Returns:
            排序后的证据列表
        """
        filtered = []
        
        for evidence in self._evidences.values():
            # 应用过滤条件
            if evidence.confidence < min_confidence:
                continue
            if evidence.relevance < min_relevance:
                continue
            if status_filter is not None and evidence.status != status_filter:
                continue
            
            filtered.append(evidence)
        
        # 按 (relevance * confidence) 排序
        filtered.sort(
            key=lambda e: e.relevance * e.confidence,
            reverse=True
        )
        
        return filtered[:top_k]
    
    def aggregate_reasoning(self, query: Optional[str] = None) -> Dict[str, Any]:
        """
        基于证据聚合进行推理
        
        Args:
            query: 查询问题（用于上下文感知）
            
        Returns:
            推理结果，包含证据摘要和推理链
        """
        # 获取高置信度证据
        top_evidences = self.get_top_evidences(
            top_k=20,
            min_confidence=0.3,
            min_relevance=0.3
        )
        
        # 按来源分组
        grouped_by_source = {}
        for evidence in top_evidences:
            if evidence.source not in grouped_by_source:
                grouped_by_source[evidence.source] = []
            grouped_by_source[evidence.source].append(evidence)
        
        # 构建推理链
        reasoning_chain = []
        for source, evidences in grouped_by_source.items():
            source_summary = {
                "source": source,
                "evidence_count": len(evidences),
                "total_confidence": sum(e.confidence for e in evidences) / len(evidences),
                "total_relevance": sum(e.relevance for e in evidences) / len(evidences),
                "key_points": [e.content[:100] + "..." if len(e.content) > 100 else e.content 
                              for e in sorted(evidences, key=lambda x: x.relevance, reverse=True)[:3]]
            }
            reasoning_chain.append(source_summary)
        
        # 统计信息
        stats = {
            "total_evidences_considered": len(top_evidences),
            "unique_sources": len(grouped_by_source),
            "avg_confidence": sum(e.confidence for e in top_evidences) / len(top_evidences) if top_evidences else 0,
            "avg_relevance": sum(e.relevance for e in top_evidences) / len(top_evidences) if top_evidences else 0
        }
        
        return {
            "query": query,
            "reasoning_chain": reasoning_chain,
            "statistics": stats,
            "evidence_ids": [e.id for e in top_evidences]
        }
    
    def update_evidence_status(self, evidence_id: str, status: EvidenceStatus) -> bool:
        """
        更新证据状态
        
        Args:
            evidence_id: 证据ID
            status: 新状态
            
        Returns:
            是否成功更新
        """
        if evidence_id not in self._evidences:
            return False
        
        old_status = self._evidences[evidence_id].status
        self._evidences[evidence_id].status = status
        
        # 更新统计
        if old_status == EvidenceStatus.CONFIRMED:
            self._metadata["total_confirmed"] -= 1
        elif old_status == EvidenceStatus.REJECTED:
            self._metadata["total_rejected"] -= 1
        
        if status == EvidenceStatus.CONFIRMED:
            self._metadata["total_confirmed"] += 1
            self._metadata["total_used"] += 1
        elif status == EvidenceStatus.REJECTED:
            self._metadata["total_rejected"] += 1
        
        return True
    
    def clear(self):
        """清空所有证据"""
        self._evidences.clear()
        self._source_index.clear()
        self._page_index.clear()
        self._type_index.clear()
        self._metadata = {
            "total_added": 0,
            "total_used": 0,
            "total_confirmed": 0,
            "total_rejected": 0
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式（用于序列化）"""
        return {
            "evidences": [e.to_dict() for e in self._evidences.values()],
            "metadata": self._metadata,
            "max_capacity": self._max_capacity
        }


# 单例模式
_evidence_memory_instance = None

def get_evidence_memory() -> EvidenceMemory:
    """获取全局证据记忆实例"""
    global _evidence_memory_instance
    if _evidence_memory_instance is None:
        _evidence_memory_instance = EvidenceMemory()
    return _evidence_memory_instance
