"""
Shared Knowledge Base
共享知识库 - 多Agent共享和检索知识
"""

import asyncio
import hashlib
import time
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Set
from datetime import datetime
from collections import defaultdict


@dataclass
class KnowledgeEntry:
    """知识条目"""
    entry_id: str                   # 知识ID
    content: str                    # 知识内容
    source_agent: str               # 来源Agent
    domain: str                    # 知识领域
    tags: List[str] = field(default_factory=list)  # 标签
    embedding: Optional[List[float]] = None  # 向量嵌入(可选)
    
    # 元数据
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
    access_count: int = 0          # 访问次数
    usefulness_score: float = 0.5   # 有用性评分 (0-1)
    
    # 验证状态
    verified_by: List[str] = field(default_factory=list)  # 验证过的Agent
    verified_at: Optional[datetime] = None
    is_verified: bool = False
    
    # 关联
    related_entries: List[str] = field(default_factory=list)  # 关联知识ID
    parent_entry: Optional[str] = None  # 父知识ID (用于知识演进)


@dataclass
class KnowledgeQuery:
    """知识查询"""
    query_text: str                # 查询文本
    domain: Optional[str] = None   # 限定领域
    tags: List[str] = field(default_factory=list)  # 标签过滤
    min_usefulness: float = 0.0    # 最低有用性评分
    limit: int = 10                # 返回数量限制
    require_verified: bool = False  # 只返回已验证的


@dataclass
class KnowledgeResult:
    """知识检索结果"""
    entries: List[KnowledgeEntry]   # 匹配的知识条目
    total_matches: int = 0         # 总匹配数
    search_time: float = 0.0       # 搜索耗时(秒)
    relevance_scores: Dict[str, float] = field(default_factory=dict)  # entry_id -> 相关度


class SharedKnowledgeBase:
    """共享知识库
    
    多Agent共享知识的中心存储，支持知识添加、检索、验证和演进
    """
    
    def __init__(self, max_entries: int = 10000):
        """初始化知识库
        
        Args:
            max_entries: 最大条目数(超过后自动清理低分知识)
        """
        self._entries: Dict[str, KnowledgeEntry] = {}  # entry_id -> entry
        self._domain_index: Dict[str, Set[str]] = defaultdict(set)  # domain -> entry_ids
        self._tag_index: Dict[str, Set[str]] = defaultdict(set)  # tag -> entry_ids
        self._keyword_index: Dict[str, Set[str]] = defaultdict(set)  # keyword -> entry_ids
        self._agent_contributions: Dict[str, List[str]] = defaultdict(list)  # agent_id -> entry_ids
        self._max_entries = max_entries
        self._lock = asyncio.Lock()
    
    def _extract_keywords(self, content: str) -> Set[str]:
        """从内容中提取关键词"""
        # 简单的关键词提取(实际应用中应使用NLP)
        words = content.lower().split()
        # 过滤停用词
        stopwords = {"的", "是", "在", "和", "了", "我", "你", "他", "它", "这", "那", "a", "the", "is", "and", "or"}
        keywords = {w for w in words if len(w) > 2 and w not in stopwords}
        return keywords
    
    def _generate_id(self, content: str) -> str:
        """生成知识ID"""
        return hashlib.md5(f"{content}{time.time()}".encode()).hexdigest()[:16]
    
    async def add_knowledge(
        self,
        content: str,
        source_agent: str,
        domain: str = "general",
        tags: List[str] = None,
        embedding: List[float] = None
    ) -> KnowledgeEntry:
        """添加知识条目
        
        Args:
            content: 知识内容
            source_agent: 来源Agent ID
            domain: 知识领域
            tags: 标签列表
            embedding: 向量嵌入
            
        Returns:
            创建的知识条目
        """
        async with self._lock:
            tags = tags or []
            
            # 创建条目
            entry = KnowledgeEntry(
                entry_id=self._generate_id(content),
                content=content,
                source_agent=source_agent,
                domain=domain,
                tags=tags,
                embedding=embedding
            )
            
            # 索引
            self._entries[entry.entry_id] = entry
            self._domain_index[domain].add(entry.entry_id)
            self._agent_contributions[source_agent].append(entry.entry_id)
            
            for tag in tags:
                self._tag_index[tag].add(entry.entry_id)
            
            # 关键词索引
            keywords = self._extract_keywords(content)
            for keyword in keywords:
                self._keyword_index[keyword].add(entry.entry_id)
            
            # 检查是否需要清理
            if len(self._entries) > self._max_entries:
                await self._cleanup_low_score_entries()
            
            return entry
    
    async def _cleanup_low_score_entries(self):
        """清理低评分条目"""
        # 按有用性评分排序，删除最低的10%
        sorted_entries = sorted(
            self._entries.values(),
            key=lambda e: e.usefulness_score
        )
        
        to_remove = int(len(sorted_entries) * 0.1)
        for entry in sorted_entries[:to_remove]:
            await self.remove_knowledge(entry.entry_id)
    
    async def remove_knowledge(self, entry_id: str) -> bool:
        """删除知识条目"""
        async with self._lock:
            if entry_id not in self._entries:
                return False
            
            entry = self._entries[entry_id]
            
            # 从所有索引中移除
            self._domain_index[entry.domain].discard(entry_id)
            self._agent_contributions[entry.source_agent].remove(entry_id)
            
            for tag in entry.tags:
                self._tag_index[tag].discard(entry_id)
            
            keywords = self._extract_keywords(entry.content)
            for keyword in keywords:
                self._keyword_index[keyword].discard(entry_id)
            
            del self._entries[entry_id]
            return True
    
    async def search(self, query: KnowledgeQuery) -> KnowledgeResult:
        """搜索知识
        
        Args:
            query: 查询条件
            
        Returns:
            检索结果
        """
        start_time = time.time()
        
        # 收集候选条目
        candidate_ids: Set[str] = set()
        
        # 1. 域名过滤
        if query.domain:
            candidate_ids.update(self._domain_index.get(query.domain, set()))
        else:
            candidate_ids.update(self._entries.keys())
        
        # 2. 标签过滤
        if query.tags:
            tag_candidates = set()
            for tag in query.tags:
                tag_candidates.update(self._tag_index.get(tag, set()))
            candidate_ids &= tag_candidates
        
        # 3. 过滤已验证要求
        if query.require_verified:
            candidate_ids = {
                eid for eid in candidate_ids
                if self._entries[eid].is_verified
            }
        
        # 4. 过滤有用性评分
        candidate_ids = {
            eid for eid in candidate_ids
            if self._entries[eid].usefulness_score >= query.min_usefulness
        }
        
        # 计算相关性并排序
        relevance_scores: Dict[str, float] = {}
        query_keywords = self._extract_keywords(query.query_text)
        
        for entry_id in candidate_ids:
            entry = self._entries[entry_id]
            content_keywords = self._extract_keywords(entry.content)
            
            # Jaccard相似度
            if query_keywords and content_keywords:
                intersection = len(query_keywords & content_keywords)
                union = len(query_keywords | content_keywords)
                similarity = intersection / union if union > 0 else 0.0
            else:
                similarity = 0.0
            
            # 结合有用性评分
            relevance_scores[entry_id] = similarity * 0.7 + entry.usefulness_score * 0.3
        
        # 排序并取前N个
        sorted_ids = sorted(
            candidate_ids,
            key=lambda eid: relevance_scores.get(eid, 0),
            reverse=True
        )[:query.limit]
        
        entries = [self._entries[eid] for eid in sorted_ids]
        
        # 更新访问记录
        for entry in entries:
            entry.last_accessed = datetime.now()
            entry.access_count += 1
        
        return KnowledgeResult(
            entries=entries,
            total_matches=len(candidate_ids),
            search_time=time.time() - start_time,
            relevance_scores={eid: relevance_scores.get(eid, 0) for eid in sorted_ids}
        )
    
    async def verify_knowledge(self, entry_id: str, agent_id: str) -> bool:
        """验证知识条目
        
        Args:
            entry_id: 知识ID
            agent_id: 验证Agent ID
            
        Returns:
            是否验证成功
        """
        async with self._lock:
            if entry_id not in self._entries:
                return False
            
            entry = self._entries[entry_id]
            
            # 不能验证自己创建的知识
            if entry.source_agent == agent_id:
                return False
            
            if agent_id not in entry.verified_by:
                entry.verified_by.append(agent_id)
            
            # 超过3个验证视为已验证
            if len(entry.verified_by) >= 3:
                entry.is_verified = True
                entry.verified_at = datetime.now()
            
            return True
    
    async def update_usefulness(
        self,
        entry_id: str,
        helpful: bool,
        feedback_agent: str
    ) -> bool:
        """更新知识有用性评分
        
        Args:
            entry_id: 知识ID
            helpful: 是否有帮助
            feedback_agent: 反馈Agent ID
            
        Returns:
            是否更新成功
        """
        async with self._lock:
            if entry_id not in self._entries:
                return False
            
            entry = self._entries[entry_id]
            
            # 贝叶斯更新
            alpha = 1.0  # 先验参数
            beta = 1.0
            
            if helpful:
                alpha += 1
            else:
                beta += 1
            
            # 简化: 直接调整
            if helpful:
                entry.usefulness_score = min(1.0, entry.usefulness_score + 0.05)
            else:
                entry.usefulness_score = max(0.0, entry.usefulness_score - 0.1)
            
            return True
    
    async def link_knowledge(self, entry_id1: str, entry_id2: str) -> bool:
        """关联两个知识条目"""
        async with self._lock:
            if entry_id1 not in self._entries or entry_id2 not in self._entries:
                return False
            
            self._entries[entry_id1].related_entries.append(entry_id2)
            self._entries[entry_id2].related_entries.append(entry_id1)
            return True
    
    async def evolve_knowledge(
        self,
        parent_id: str,
        new_content: str,
        evolved_by: str
    ) -> Optional[KnowledgeEntry]:
        """知识演进 - 创建知识的新版本
        
        Args:
            parent_id: 父知识ID
            new_content: 新内容
            evolved_by: 演进Agent ID
            
        Returns:
            新创建的知识条目
        """
        async with self._lock:
            if parent_id not in self._entries:
                return None
            
            parent = self._entries[parent_id]
            
            # 创建新条目
            new_entry = await self.add_knowledge(
                content=new_content,
                source_agent=evolved_by,
                domain=parent.domain,
                tags=parent.tags
            )
            
            # 设置父子关系
            new_entry.parent_entry = parent_id
            
            return new_entry
    
    async def get_agent_knowledge_count(self, agent_id: str) -> int:
        """获取某个Agent贡献的知识数量"""
        return len(self._agent_contributions.get(agent_id, []))
    
    async def get_domain_stats(self) -> Dict[str, int]:
        """获取各领域的知识数量"""
        return {domain: len(entry_ids) for domain, entry_ids in self._domain_index.items()}
    
    async def get_verified_count(self) -> int:
        """获取已验证知识数量"""
        return sum(1 for entry in self._entries.values() if entry.is_verified)
