"""
Collective Memory
集体记忆 - 跨Agent的持久化记忆系统
"""

import asyncio
import json
import hashlib
import time
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Set
from datetime import datetime
from collections import defaultdict


@dataclass
class MemoryEntry:
    """记忆条目"""
    entry_id: str                   # 记忆ID
    content: str                    # 记忆内容
    event_type: str                 # 事件类型: success, failure, insight, decision
    agents_involved: List[str] = field(default_factory=list)  # 涉及的Agent
    
    # 上下文
    context: Dict[str, Any] = field(default_factory=dict)  # 上下文信息
    outcome: Optional[str] = None   # 结果描述
    lessons_learned: List[str] = field(default_factory=list)  # 经验教训
    
    # 元数据
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    importance: float = 0.5         # 重要性 (0-1)
    
    # 关联
    related_memories: List[str] = field(default_factory=list)  # 关联记忆ID
    parent_memory: Optional[str] = None  # 父记忆 (用于记忆演进)


@dataclass
class MemoryPattern:
    """记忆模式
    
    发现的成功模式，可用于指导未来决策
    """
    pattern_id: str                  # 模式ID
    name: str                        # 模式名称
    description: str                # 模式描述
    trigger_conditions: List[str] = field(default_factory=list)  # 触发条件
    
    # 效果
    success_rate: float = 0.0       # 成功率
    total_uses: int = 0              # 使用次数
    avg_outcome_quality: float = 0.0  # 平均结果质量
    
    # 来源
    source_memories: List[str] = field(default_factory=list)  # 来源记忆ID
    discovered_at: datetime = field(default_factory=datetime.now)
    last_used: Optional[datetime] = None
    
    # 验证状态
    validation_count: int = 0       # 验证次数
    is_validated: bool = False      # 是否已验证
    

@dataclass
class AgentMemory:
    """Agent个人记忆
    
    每个Agent的私人记忆空间
    """
    agent_id: str                    # Agent ID
    private_entries: Dict[str, MemoryEntry] = field(default_factory=dict)  # 私有记忆
    shared_access_log: List[str] = field(default_factory=list)  # 访问过的共享记忆ID
    
    # 统计数据
    total_insights: int = 0         # 总洞察数
    successful_predictions: int = 0  # 成功预测数
    total_predictions: int = 0       # 总预测数
    
    last_sync: datetime = field(default_factory=datetime.now)


class CollectiveMemory:
    """集体记忆系统
    
    跨Agent共享的记忆系统，支持经验积累、模式发现和知识传承
    """
    
    def __init__(self, max_entries: int = 5000):
        """初始化集体记忆
        
        Args:
            max_entries: 最大记忆条目数
        """
        self._shared_memories: Dict[str, MemoryEntry] = {}  # entry_id -> entry
        self._agent_memories: Dict[str, AgentMemory] = {}   # agent_id -> memory
        self._patterns: Dict[str, MemoryPattern] = {}      # pattern_id -> pattern
        
        # 索引
        self._event_type_index: Dict[str, Set[str]] = defaultdict(set)
        self._agent_involved_index: Dict[str, Set[str]] = defaultdict(set)
        self._keyword_index: Dict[str, Set[str]] = defaultdict(set)
        
        self._max_entries = max_entries
        self._lock = asyncio.Lock()
    
    def _generate_id(self, content: str) -> str:
        """生成记忆ID"""
        return hashlib.md5(f"{content}{time.time()}".encode()).hexdigest()[:16]
    
    def _extract_keywords(self, content: str) -> Set[str]:
        """提取关键词"""
        words = content.lower().split()
        stopwords = {"的", "是", "在", "和", "了", "我", "你", "a", "the", "is", "and"}
        return {w for w in words if len(w) > 2 and w not in stopwords}
    
    async def store_shared_memory(
        self,
        content: str,
        event_type: str,
        agents_involved: List[str],
        context: Dict[str, Any] = None,
        outcome: str = None,
        lessons: List[str] = None,
        importance: float = 0.5
    ) -> MemoryEntry:
        """存储共享记忆
        
        Args:
            content: 记忆内容
            event_type: 事件类型
            agents_involved: 涉及的Agent列表
            context: 上下文
            outcome: 结果
            lessons: 经验教训
            importance: 重要性
            
        Returns:
            创建的记忆条目
        """
        async with self._lock:
            lessons = lessons or []
            context = context or {}
            
            entry = MemoryEntry(
                entry_id=self._generate_id(content),
                content=content,
                event_type=event_type,
                agents_involved=agents_involved,
                context=context,
                outcome=outcome,
                lessons_learned=lessons,
                importance=importance
            )
            
            # 索引
            self._shared_memories[entry.entry_id] = entry
            self._event_type_index[event_type].add(entry.entry_id)
            self._agent_involved_index[entry.agents_involved[0]].add(entry.entry_id)
            
            keywords = self._extract_keywords(content)
            for keyword in keywords:
                self._keyword_index[keyword].add(entry.entry_id)
            
            # 更新Agent记忆
            for agent_id in agents_involved:
                await self._ensure_agent_memory(agent_id)
            
            # 检查是否需要清理
            if len(self._shared_memories) > self._max_entries:
                await self._cleanup_low_importance()
            
            return entry
    
    async def _ensure_agent_memory(self, agent_id: str) -> AgentMemory:
        """确保Agent记忆存在"""
        if agent_id not in self._agent_memories:
            self._agent_memories[agent_id] = AgentMemory(agent_id=agent_id)
        return self._agent_memories[agent_id]
    
    async def _cleanup_low_importance(self):
        """清理低重要性记忆"""
        sorted_entries = sorted(
            self._shared_memories.values(),
            key=lambda e: e.importance
        )
        
        to_remove = int(len(sorted_entries) * 0.1)
        for entry in sorted_entries[:to_remove]:
            await self._remove_from_indexes(entry.entry_id)
            del self._shared_memories[entry.entry_id]
    
    async def _remove_from_indexes(self, entry_id: str):
        """从索引中移除"""
        if entry_id in self._shared_memories:
            entry = self._shared_memories[entry_id]
            self._event_type_index[entry.event_type].discard(entry_id)
            for agent_id in entry.agents_involved:
                self._agent_involved_index[agent_id].discard(entry_id)
            keywords = self._extract_keywords(entry.content)
            for keyword in keywords:
                self._keyword_index[keyword].discard(entry_id)
    
    async def store_agent_memory(
        self,
        agent_id: str,
        content: str,
        event_type: str,
        context: Dict[str, Any] = None
    ) -> MemoryEntry:
        """存储Agent个人记忆
        
        Args:
            agent_id: Agent ID
            content: 记忆内容
            event_type: 事件类型
            context: 上下文
            
        Returns:
            创建的记忆条目
        """
        async with self._lock:
            agent_memory = await self._ensure_agent_memory(agent_id)
            context = context or {}
            
            entry = MemoryEntry(
                entry_id=self._generate_id(content),
                content=content,
                event_type=event_type,
                agents_involved=[agent_id],
                context=context
            )
            
            agent_memory.private_entries[entry.entry_id] = entry
            
            if event_type == "insight":
                agent_memory.total_insights += 1
            
            return entry
    
    async def search_memories(
        self,
        query: str,
        event_type: Optional[str] = None,
        agent_id: Optional[str] = None,
        limit: int = 10
    ) -> List[MemoryEntry]:
        """搜索记忆
        
        Args:
            query: 查询文本
            event_type: 事件类型过滤
            agent_id: Agent过滤
            limit: 返回数量
            
        Returns:
            匹配的记忆列表
        """
        # 收集候选
        candidates: Set[str] = set()
        
        if event_type:
            candidates.update(self._event_type_index.get(event_type, set()))
        else:
            candidates.update(self._shared_memories.keys())
        
        if agent_id:
            agent_candidates = self._agent_involved_index.get(agent_id, set())
            candidates &= agent_candidates
        
        # 关键词匹配
        query_keywords = self._extract_keywords(query)
        if query_keywords:
            keyword_candidates: Set[str] = set()
            for keyword in query_keywords:
                keyword_candidates.update(self._keyword_index.get(keyword, set()))
            candidates &= keyword_candidates
        
        # 按重要性排序
        results = []
        for entry_id in candidates:
            entry = self._shared_memories.get(entry_id)
            if entry:
                entry.last_accessed = datetime.now()
                entry.access_count += 1
                results.append((entry.importance, entry))
        
        results.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in results[:limit]]
    
    async def get_success_patterns(
        self,
        domain: Optional[str] = None,
        min_success_rate: float = 0.6,
        limit: int = 5
    ) -> List[MemoryPattern]:
        """获取成功模式
        
        Args:
            domain: 领域过滤
            min_success_rate: 最低成功率
            limit: 返回数量
            
        Returns:
            成功模式列表
        """
        patterns = [
            p for p in self._patterns.values()
            if p.success_rate >= min_success_rate and p.is_validated
        ]
        
        patterns.sort(key=lambda p: (p.success_rate, p.total_uses), reverse=True)
        return patterns[:limit]
    
    async def discover_pattern(
        self,
        source_memory_ids: List[str],
        name: str,
        description: str,
        trigger_conditions: List[str] = None
    ) -> MemoryPattern:
        """发现新模式
        
        Args:
            source_memory_ids: 来源记忆ID
            name: 模式名称
            description: 模式描述
            trigger_conditions: 触发条件
            
        Returns:
            创建的模式
        """
        async with self._lock:
            # 计算成功率
            successes = 0
            total = len(source_memory_ids)
            
            for mem_id in source_memory_ids:
                mem = self._shared_memories.get(mem_id)
                if mem and mem.outcome == "success":
                    successes += 1
            
            success_rate = successes / total if total > 0 else 0.0
            
            pattern = MemoryPattern(
                pattern_id=self._generate_id(name),
                name=name,
                description=description,
                trigger_conditions=trigger_conditions or [],
                success_rate=success_rate,
                total_uses=total,
                source_memories=source_memory_ids
            )
            
            self._patterns[pattern.pattern_id] = pattern
            return pattern
    
    async def apply_pattern(
        self,
        pattern_id: str
    ) -> bool:
        """应用模式 (标记为使用)
        
        Args:
            pattern_id: 模式ID
            
        Returns:
            是否成功
        """
        async with self._lock:
            if pattern_id not in self._patterns:
                return False
            
            pattern = self._patterns[pattern_id]
            pattern.total_uses += 1
            pattern.last_used = datetime.now()
            
            return True
    
    async def validate_pattern(
        self,
        pattern_id: str,
        success: bool,
        outcome_quality: float = 0.5
    ) -> bool:
        """验证模式效果
        
        Args:
            pattern_id: 模式ID
            success: 是否成功
            outcome_quality: 结果质量 (0-1)
            
        Returns:
            是否更新成功
        """
        async with self._lock:
            if pattern_id not in self._patterns:
                return False
            
            pattern = self._patterns[pattern_id]
            pattern.validation_count += 1
            
            # 贝叶斯更新成功率
            n = pattern.validation_count
            old_rate = pattern.success_rate
            
            if success:
                new_rate = (old_rate * (n - 1) + 1) / n
            else:
                new_rate = old_rate * (n - 1) / n
            
            pattern.success_rate = new_rate
            pattern.avg_outcome_quality = (
                pattern.avg_outcome_quality * (n - 1) + outcome_quality
            ) / n
            
            # 3次以上验证视为已验证
            if pattern.validation_count >= 3:
                pattern.is_validated = True
            
            return True
    
    async def sync_agent_memories(self, agent_id: str) -> List[MemoryEntry]:
        """同步Agent记忆
        
        获取该Agent可以访问的所有共享记忆
        
        Args:
            agent_id: Agent ID
            
        Returns:
            相关记忆列表
        """
        agent_memory = await self._ensure_agent_memory(agent_id)
        agent_memory.last_sync = datetime.now()
        
        # 获取该Agent参与的记忆
        return list(self._shared_memories.values())
    
    async def get_collective_insights(self, limit: int = 10) -> List[str]:
        """获取集体洞察
        
        获取所有Agent共享的重要洞察
        
        Args:
            limit: 返回数量
            
        Returns:
            洞察列表
        """
        insights = [
            m for m in self._shared_memories.values()
            if m.event_type == "insight" and m.importance >= 0.6
        ]
        
        insights.sort(key=lambda m: (m.importance, m.access_count), reverse=True)
        return [m.content for m in insights[:limit]]
