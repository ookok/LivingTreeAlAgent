"""
Short-term Memory - 会话级记忆

存储最近的对话历史和精确匹配数据，用于快速响应常见问题。

特性：
- 低延迟访问（毫秒级）
- 有限容量（避免内存膨胀）
- 自动过期（1小时内未访问自动删除）
- 支持精确匹配和模糊匹配

包含：
- SessionMemory: 会话级对话历史
- ExactMemory: 精确匹配缓存
"""

import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class SessionEntry:
    """会话条目"""
    session_id: str
    user_id: str
    messages: List[Dict] = field(default_factory=list)
    created_at: float = field(default_factory=lambda: time.time())
    last_accessed: float = field(default_factory=lambda: time.time())


@dataclass
class CacheEntry:
    """缓存条目"""
    key: str
    value: Any
    expires_at: float
    access_count: int = 0
    last_accessed: float = field(default_factory=lambda: time.time())


class SessionMemory:
    """会话级记忆 - 存储对话历史"""
    
    def __init__(self, max_sessions: int = 100, max_messages_per_session: int = 50):
        self._logger = logger.bind(component="SessionMemory")
        self._sessions: Dict[str, SessionEntry] = {}
        self._max_sessions = max_sessions
        self._max_messages_per_session = max_messages_per_session
        self._cleanup_interval = 3600  # 每小时清理一次
        self._last_cleanup = time.time()
        
        self._logger.info(f"SessionMemory 初始化: max_sessions={max_sessions}")
    
    def _cleanup_expired(self):
        """清理过期会话（超过1小时未访问）"""
        if time.time() - self._last_cleanup < self._cleanup_interval:
            return
        
        now = time.time()
        expired_count = 0
        
        for session_id in list(self._sessions.keys()):
            entry = self._sessions[session_id]
            if now - entry.last_accessed > 3600:  # 1小时过期
                del self._sessions[session_id]
                expired_count += 1
        
        self._last_cleanup = time.time()
        if expired_count > 0:
            self._logger.debug(f"清理过期会话: {expired_count}")
    
    def _enforce_limits(self):
        """强制执行容量限制"""
        # 如果会话数超过限制，删除最旧的
        while len(self._sessions) > self._max_sessions:
            oldest = min(self._sessions.keys(), key=lambda k: self._sessions[k].created_at)
            del self._sessions[oldest]
            self._logger.debug(f"会话数超限，删除最旧会话: {oldest}")
    
    def query(self, query: str, context: Dict) -> Dict:
        """
        查询会话记忆
        
        Args:
            query: 查询内容
            context: 上下文（包含 session_id）
        
        Returns:
            查询结果
        """
        session_id = context.get("session_id")
        if not session_id:
            return {"success": False, "content": "", "confidence": 0.0}
        
        self._cleanup_expired()
        
        if session_id not in self._sessions:
            return {"success": False, "content": "", "confidence": 0.0}
        
        session = self._sessions[session_id]
        session.last_accessed = time.time()
        
        # 简单匹配：在历史消息中查找相似内容
        history = session.messages
        recent_messages = history[-10:] if len(history) > 10 else history
        
        for msg in reversed(recent_messages):
            if query.lower() in msg.get("content", "").lower():
                return {
                    "success": True,
                    "content": msg.get("content", ""),
                    "confidence": 0.85,
                    "type": "session_memory",
                    "source": "short_term"
                }
        
        return {"success": False, "content": "", "confidence": 0.0}
    
    def store(self, content: str, **kwargs) -> str:
        """
        存储会话消息
        
        Args:
            content: 消息内容
            **kwargs: 包含 session_id, user_id, role 等
        
        Returns:
            会话ID
        """
        session_id = kwargs.get("session_id", "default")
        user_id = kwargs.get("user_id", "unknown")
        role = kwargs.get("role", "user")
        
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionEntry(
                session_id=session_id,
                user_id=user_id
            )
        
        session = self._sessions[session_id]
        session.last_accessed = time.time()
        
        # 添加消息
        session.messages.append({
            "role": role,
            "content": content,
            "timestamp": time.time()
        })
        
        # 限制消息数量
        while len(session.messages) > self._max_messages_per_session:
            session.messages.pop(0)
        
        self._enforce_limits()
        
        return session_id
    
    def get_session_history(self, session_id: str) -> List[Dict]:
        """获取会话历史"""
        if session_id not in self._sessions:
            return []
        
        self._sessions[session_id].last_accessed = time.time()
        return self._sessions[session_id].messages
    
    def clear_session(self, session_id: str):
        """清除会话"""
        if session_id in self._sessions:
            del self._sessions[session_id]
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        self._cleanup_expired()
        return {
            "total_sessions": len(self._sessions),
            "total_messages": sum(len(s.messages) for s in self._sessions.values())
        }


class ExactMemory:
    """精确匹配缓存 - 存储高频查询的精确结果"""
    
    def __init__(self, max_entries: int = 1000, ttl_seconds: int = 3600):
        self._logger = logger.bind(component="ExactMemory")
        self._cache: Dict[str, CacheEntry] = {}
        self._max_entries = max_entries
        self._ttl_seconds = ttl_seconds
        
        self._logger.info(f"ExactMemory 初始化: max_entries={max_entries}, ttl={ttl_seconds}s")
    
    def _is_expired(self, entry: CacheEntry) -> bool:
        """检查条目是否过期"""
        return time.time() > entry.expires_at
    
    def _cleanup_expired(self):
        """清理过期条目"""
        expired_keys = [k for k, entry in self._cache.items() if self._is_expired(entry)]
        for key in expired_keys:
            del self._cache[key]
        
        if expired_keys:
            self._logger.debug(f"清理过期缓存: {len(expired_keys)}")
    
    def _enforce_limits(self):
        """强制执行容量限制（LRU策略）"""
        while len(self._cache) > self._max_entries:
            # 删除访问次数最少的
            lru_key = min(self._cache.keys(), key=lambda k: self._cache[k].access_count)
            del self._cache[lru_key]
            self._logger.debug(f"缓存超限，删除LRU条目: {lru_key}")
    
    def query(self, query: str, context: Dict = None) -> Dict:
        """
        查询精确匹配缓存
        
        Args:
            query: 查询内容
            context: 上下文
        
        Returns:
            查询结果
        """
        self._cleanup_expired()
        
        # 使用查询字符串作为key（简单实现）
        cache_key = query.strip().lower()
        
        if cache_key not in self._cache:
            return {"success": False, "content": "", "confidence": 0.0}
        
        entry = self._cache[cache_key]
        
        if self._is_expired(entry):
            del self._cache[cache_key]
            return {"success": False, "content": "", "confidence": 0.0}
        
        # 更新访问统计
        entry.access_count += 1
        entry.last_accessed = time.time()
        
        return {
            "success": True,
            "content": entry.value,
            "confidence": 1.0,
            "type": "exact_cache",
            "source": "short_term",
            "access_count": entry.access_count
        }
    
    def store(self, content: str, **kwargs) -> str:
        """
        存储精确匹配条目
        
        Args:
            content: 要存储的内容
            **kwargs: 包含 key（可选，默认为内容）
        
        Returns:
            缓存key
        """
        cache_key = kwargs.get("key", content.strip().lower())
        ttl = kwargs.get("ttl_seconds", self._ttl_seconds)
        
        self._cache[cache_key] = CacheEntry(
            key=cache_key,
            value=content,
            expires_at=time.time() + ttl
        )
        
        self._enforce_limits()
        
        return cache_key
    
    def invalidate(self, key: str):
        """失效指定缓存"""
        if key in self._cache:
            del self._cache[key]
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        self._cleanup_expired()
        return {
            "total_entries": len(self._cache),
            "total_accesses": sum(e.access_count for e in self._cache.values())
        }


# 单例模式
_session_memory_instance = None
_exact_memory_instance = None

def get_session_memory() -> SessionMemory:
    """获取会话记忆实例"""
    global _session_memory_instance
    if _session_memory_instance is None:
        _session_memory_instance = SessionMemory()
    return _session_memory_instance

def get_exact_memory() -> ExactMemory:
    """获取精确匹配缓存实例"""
    global _exact_memory_instance
    if _exact_memory_instance is None:
        _exact_memory_instance = ExactMemory()
    return _exact_memory_instance


if __name__ == "__main__":
    print("=" * 60)
    print("Short-term Memory 测试")
    print("=" * 60)
    
    # 测试 SessionMemory
    session_mem = get_session_memory()
    
    session_mem.store("你好！", session_id="test_session", user_id="user1", role="user")
    session_mem.store("你好！有什么我可以帮助你的吗？", session_id="test_session", user_id="user1", role="assistant")
    session_mem.store("什么是AI？", session_id="test_session", user_id="user1", role="user")
    
    history = session_mem.get_session_history("test_session")
    print(f"会话历史: {len(history)} 条消息")
    
    result = session_mem.query("什么是AI？", {"session_id": "test_session"})
    print(f"查询 '什么是AI？': 成功={result['success']}, 置信度={result['confidence']}")
    
    # 测试 ExactMemory
    exact_mem = get_exact_memory()
    
    exact_mem.store("42", key="答案是什么？")
    
    result = exact_mem.query("答案是什么？")
    print(f"精确匹配 '答案是什么？': 成功={result['success']}, 内容={result.get('content')}")
    
    result = exact_mem.query("未知问题")
    print(f"精确匹配 '未知问题': 成功={result['success']}")
    
    print("\n" + "=" * 60)