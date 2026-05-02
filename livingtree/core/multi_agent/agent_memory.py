#!/usr/bin/env python3
"""
LivingTreeAI Phase 2 - Agent Memory 共享系统
多智能体共享记忆、状态同步、经验传递
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import threading
import json


class MemoryType(Enum):
    """记忆类型"""
    SHORT_TERM = "short_term"      # 短期记忆
    LONG_TERM = "long_term"        # 长期记忆
    SHARED = "shared"              # 共享记忆
    EPISODIC = "episodic"          # 情景记忆
    SEMANTIC = "semantic"          # 语义记忆


@dataclass
class MemoryEntry:
    """记忆条目"""
    id: str
    agent_id: str
    memory_type: MemoryType
    content: Any
    tags: List[str] = field(default_factory=list)
    importance: float = 0.5  # 0.0 - 1.0
    created_at: float = field(default_factory=datetime.now().timestamp)
    accessed_at: float = field(default_factory=datetime.now().timestamp)
    access_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class AgentMemoryStore:
    """
    Agent Memory 存储
    支持多智能体记忆的存储和检索
    """
    
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.memories: Dict[str, MemoryEntry] = {}
        self._lock = threading.RLock()
    
    def store(self, memory_type: MemoryType, content: Any,
              tags: List[str] = None, importance: float = 0.5) -> str:
        """存储记忆"""
        import uuid
        
        memory_id = str(uuid.uuid4())[:8]
        entry = MemoryEntry(
            id=memory_id,
            agent_id=self.agent_id,
            memory_type=memory_type,
            content=content,
            tags=tags or [],
            importance=importance
        )
        
        with self._lock:
            self.memories[memory_id] = entry
        
        return memory_id
    
    def retrieve(self, memory_id: str) -> Optional[MemoryEntry]:
        """检索记忆"""
        with self._lock:
            entry = self.memories.get(memory_id)
            if entry:
                entry.access_count += 1
                entry.accessed_at = datetime.now().timestamp
            return entry
    
    def search(self, memory_type: MemoryType = None,
               tags: List[str] = None, keyword: str = None) -> List[MemoryEntry]:
        """搜索记忆"""
        with self._lock:
            results = list(self.memories.values())
            
            # 按类型过滤
            if memory_type:
                results = [m for m in results if m.memory_type == memory_type]
            
            # 按标签过滤
            if tags:
                results = [m for m in results if any(t in m.tags for t in tags)]
            
            # 按关键词过滤
            if keyword:
                keyword_lower = keyword.lower()
                results = [
                    m for m in results
                    if keyword_lower in str(m.content).lower()
                ]
            
            # 按重要性和访问时间排序
            results.sort(key=lambda m: (m.importance, m.accessed_at), reverse=True)
            
            return results
    
    def forget(self, memory_id: str) -> bool:
        """遗忘记忆"""
        with self._lock:
            if memory_id in self.memories:
                del self.memories[memory_id]
                return True
            return False
    
    def consolidate(self, threshold: float = 0.3) -> int:
        """整合记忆，遗忘低重要性记忆"""
        with self._lock:
            to_remove = [
                mid for mid, m in self.memories.items()
                if m.importance < threshold and m.access_count < 2
            ]
            
            for mid in to_remove:
                del self.memories[mid]
            
            return len(to_remove)


class SharedMemorySpace:
    """
    共享记忆空间
    多智能体共享的记忆区域
    """
    
    def __init__(self, space_id: str, name: str):
        self.space_id = space_id
        self.name = name
        self.participants: List[str] = []
        self.memories: Dict[str, MemoryEntry] = {}
        self._lock = threading.RLock()
    
    def add_participant(self, agent_id: str) -> bool:
        """添加参与者"""
        with self._lock:
            if agent_id not in self.participants:
                self.participants.append(agent_id)
                return True
            return False
    
    def remove_participant(self, agent_id: str) -> bool:
        """移除参与者"""
        with self._lock:
            if agent_id in self.participants:
                self.participants.remove(agent_id)
                return True
            return False
    
    def write(self, agent_id: str, content: Any, tags: List[str] = None,
              importance: float = 0.5) -> str:
        """写入共享记忆"""
        import uuid
        
        if agent_id not in self.participants:
            return None
        
        memory_id = str(uuid.uuid4())[:8]
        entry = MemoryEntry(
            id=memory_id,
            agent_id=agent_id,
            memory_type=MemoryType.SHARED,
            content=content,
            tags=tags or [],
            importance=importance
        )
        
        with self._lock:
            self.memories[memory_id] = entry
        
        return memory_id
    
    def read(self, memory_id: str) -> Optional[MemoryEntry]:
        """读取共享记忆"""
        with self._lock:
            entry = self.memories.get(memory_id)
            if entry:
                entry.access_count += 1
                entry.accessed_at = datetime.now().timestamp
            return entry
    
    def search(self, tags: List[str] = None, keyword: str = None) -> List[MemoryEntry]:
        """搜索共享记忆"""
        with self._lock:
            results = list(self.memories.values())
            
            if tags:
                results = [m for m in results if any(t in m.tags for t in tags)]
            
            if keyword:
                keyword_lower = keyword.lower()
                results = [
                    m for m in results
                    if keyword_lower in str(m.content).lower()
                ]
            
            results.sort(key=lambda m: (m.importance, m.accessed_at), reverse=True)
            return results
    
    def get_participant_memories(self, agent_id: str) -> List[MemoryEntry]:
        """获取特定智能体的记忆"""
        with self._lock:
            return [m for m in self.memories.values() if m.agent_id == agent_id]


class AgentMemoryBridge:
    """
    Agent Memory 桥接器
    连接多个智能体的记忆系统，支持经验传递
    """
    
    def __init__(self):
        self.agent_stores: Dict[str, AgentMemoryStore] = {}
        self.shared_spaces: Dict[str, SharedMemorySpace] = {}
        self._lock = threading.RLock()
    
    def register_agent(self, agent_id: str) -> AgentMemoryStore:
        """注册智能体记忆存储"""
        with self._lock:
            if agent_id not in self.agent_stores:
                self.agent_stores[agent_id] = AgentMemoryStore(agent_id)
            return self.agent_stores[agent_id]
    
    def get_agent_store(self, agent_id: str) -> Optional[AgentMemoryStore]:
        """获取智能体记忆存储"""
        with self._lock:
            return self.agent_stores.get(agent_id)
    
    def create_shared_space(self, space_id: str, name: str,
                          participants: List[str] = None) -> SharedMemorySpace:
        """创建共享记忆空间"""
        with self._lock:
            space = SharedMemorySpace(space_id, name)
            if participants:
                for agent_id in participants:
                    space.add_participant(agent_id)
            self.shared_spaces[space_id] = space
            return space
    
    def get_shared_space(self, space_id: str) -> Optional[SharedMemorySpace]:
        """获取共享记忆空间"""
        with self._lock:
            return self.shared_spaces.get(space_id)
    
    def share_experience(self, from_agent: str, to_agent: str,
                        content: Any, tags: List[str] = None) -> bool:
        """经验传递：复制记忆从一个智能体到另一个"""
        with self._lock:
            from_store = self.agent_stores.get(from_agent)
            to_store = self.agent_stores.get(to_agent)
            
            if not from_store or not to_store:
                return False
            
            # 获取最新且重要的记忆
            memories = from_store.search(tags=tags)
            if not memories:
                return False
            
            # 复制到目标智能体
            for memory in memories[:3]:  # 最多复制3条
                to_store.store(
                    memory_type=MemoryType.LONG_TERM,
                    content=memory.content,
                    tags=["shared", f"from_{from_agent}"] + (tags or []),
                    importance=memory.importance * 0.8  # 降低重要性
                )
            
            return True
    
    def get_collaborative_insights(self, agent_ids: List[str],
                                  topic: str) -> List[Dict[str, Any]]:
        """获取协作洞察：多个智能体关于某主题的记忆"""
        with self._lock:
            insights = []
            
            for agent_id in agent_ids:
                store = self.agent_stores.get(agent_id)
                if store:
                    memories = store.search(keyword=topic)
                    for memory in memories[:2]:
                        insights.append({
                            'agent_id': agent_id,
                            'content': memory.content,
                            'importance': memory.importance,
                            'tags': memory.tags
                        })
            
            # 按重要性排序
            insights.sort(key=lambda x: x['importance'], reverse=True)
            return insights


# ==================== 全局实例 ====================

_memory_bridge: Optional[AgentMemoryBridge] = None


def get_memory_bridge() -> AgentMemoryBridge:
    """获取全局记忆桥接器"""
    global _memory_bridge
    if _memory_bridge is None:
        _memory_bridge = AgentMemoryBridge()
    return _memory_bridge


# ==================== CLI ====================

def main():
    """命令行工具"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Agent Memory 共享系统')
    parser.add_argument('--agent', '-a', help='智能体ID')
    parser.add_argument('--space', '-s', help='共享空间ID')
    parser.add_argument('--share', action='store_true', help='共享记忆')
    
    args = parser.parse_args()
    
    bridge = get_memory_bridge()
    
    if args.agent:
        store = bridge.register_agent(args.agent)
        print(f"注册智能体: {args.agent}")
        
        # 存储测试记忆
        mid = store.store(MemoryType.SHORT_TERM, "测试记忆内容", tags=["test"])
        print(f"存储记忆: {mid}")
        
        # 检索记忆
        memories = store.search(tags=["test"])
        print(f"找到 {len(memories)} 条相关记忆")
    
    if args.space:
        space = bridge.create_shared_space(args.space, f"空间{args.space}")
        print(f"创建共享空间: {args.space}")
        
        if args.share:
            # 添加参与者并写入
            bridge.register_agent("agent1")
            space.add_participant("agent1")
            mid = space.write("agent1", "共享内容", tags=["shared"])
            print(f"写入共享记忆: {mid}")


if __name__ == "__main__":
    main()
