"""
A2A 协议会话管理
Session Management for A2A Protocol

功能：
- 独立会话持久化
- 会话注入（Session Injection）
- 会话生命周期管理
"""

import json
import time
import uuid
import threading
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path

from business.logger import get_logger

logger = get_logger('a2a_session')


class SessionState(str, Enum):
    """会话状态"""
    ACTIVE = "active"
    IDLE = "idle"
    EXPIRED = "expired"
    TERMINATED = "terminated"


@dataclass
class ConversationTurn:
    """对话轮次"""
    turn_id: str
    role: str  # user, assistant, system
    content: str
    timestamp: int
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class A2ASession:
    """
    A2A 会话
    支持独立持久化和会话注入
    """
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    context_id: Optional[str] = None
    
    # 参与者
    participants: List[str] = field(default_factory=list)  # Agent IDs
    
    # 对话历史
    turns: List[ConversationTurn] = field(default_factory=list)
    
    # 注入的上下文
    injected_context: Dict[str, Any] = field(default_factory=dict)
    
    # 状态
    state: SessionState = SessionState.ACTIVE
    created_at: int = field(default_factory=lambda: int(time.time() * 1000))
    updated_at: int = field(default_factory=lambda: int(time.time() * 1000))
    last_activity_at: int = field(default_factory=lambda: int(time.time() * 1000))
    
    # 过期设置
    ttl_seconds: int = 3600  # 默认 1 小时
    expires_at: Optional[int] = None
    
    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_turn(self, role: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> ConversationTurn:
        """添加对话轮次"""
        turn = ConversationTurn(
            turn_id=str(uuid.uuid4()),
            role=role,
            content=content,
            timestamp=int(time.time() * 1000),
            metadata=metadata or {}
        )
        self.turns.append(turn)
        self.last_activity_at = turn.timestamp
        self.updated_at = turn.timestamp
        return turn
    
    def inject_context(self, key: str, value: Any, overwrite: bool = True):
        """注入上下文"""
        if key in self.injected_context and not overwrite:
            return
        self.injected_context[key] = value
        self.updated_at = int(time.time() * 1000)
    
    def get_context_summary(self) -> Dict[str, Any]:
        """获取上下文摘要"""
        return {
            'session_id': self.session_id,
            'user_id': self.user_id,
            'context_id': self.context_id,
            'turn_count': len(self.turns),
            'injected_context': self.injected_context,
            'state': self.state.value,
            'participants': self.participants
        }
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result['state'] = self.state.value
        result['turns'] = [
            {**asdict(t), 'role': t.role} for t in self.turns
        ]
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'A2ASession':
        if isinstance(data.get('state'), str):
            data['state'] = SessionState(data['state'])
        data['turns'] = [
            ConversationTurn(**t) for t in data.get('turns', [])
        ]
        return cls(**data)
    
    def is_expired(self) -> bool:
        """检查是否过期"""
        if self.expires_at:
            return time.time() * 1000 > self.expires_at
        if self.ttl_seconds > 0:
            return time.time() * 1000 > self.created_at + self.ttl_seconds * 1000
        return False
    
    def is_idle(self, idle_threshold_seconds: int = 300) -> bool:
        """检查是否空闲"""
        return time.time() * 1000 - self.last_activity_at > idle_threshold_seconds * 1000


class SessionPersistence:
    """
    会话持久化存储
    支持文件存储和内存缓存
    """
    
    def __init__(self, storage_dir: Optional[str] = None):
        """
        Args:
            storage_dir: 存储目录，None 则仅使用内存
        """
        self._storage_dir = Path(storage_dir) if storage_dir else None
        self._memory_cache: Dict[str, A2ASession] = {}
        self._lock = threading.RLock()
        
        if self._storage_dir:
            self._storage_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Session storage initialized at: {self._storage_dir}")
    
    def save(self, session: A2ASession) -> bool:
        """保存会话"""
        with self._lock:
            try:
                # 更新内存缓存
                self._memory_cache[session.session_id] = session
                
                # 持久化到磁盘
                if self._storage_dir:
                    file_path = self._storage_dir / f"{session.session_id}.json"
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(session.to_dict(), f, ensure_ascii=False, indent=2)
                    logger.debug(f"Session saved to disk: {session.session_id}")
                
                return True
                
            except Exception as e:
                logger.error(f"Failed to save session {session.session_id}: {e}")
                return False
    
    def load(self, session_id: str) -> Optional[A2ASession]:
        """加载会话"""
        with self._lock:
            # 先检查内存缓存
            if session_id in self._memory_cache:
                session = self._memory_cache[session_id]
                if not session.is_expired():
                    return session
                else:
                    del self._memory_cache[session_id]
            
            # 从磁盘加载
            if self._storage_dir:
                file_path = self._storage_dir / f"{session_id}.json"
                if file_path.exists():
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        session = A2ASession.from_dict(data)
                        if not session.is_expired():
                            self._memory_cache[session_id] = session
                            return session
                    except Exception as e:
                        logger.error(f"Failed to load session {session_id}: {e}")
            
            return None
    
    def delete(self, session_id: str) -> bool:
        """删除会话"""
        with self._lock:
            try:
                # 从内存移除
                if session_id in self._memory_cache:
                    del self._memory_cache[session_id]
                
                # 从磁盘删除
                if self._storage_dir:
                    file_path = self._storage_dir / f"{session_id}.json"
                    if file_path.exists():
                        file_path.unlink()
                
                return True
                
            except Exception as e:
                logger.error(f"Failed to delete session {session_id}: {e}")
                return False
    
    def list_sessions(self, user_id: Optional[str] = None) -> List[str]:
        """列出所有会话 ID"""
        with self._lock:
            if user_id:
                return [
                    sid for sid, s in self._memory_cache.items()
                    if s.user_id == user_id and not s.is_expired()
                ]
            return list(self._memory_cache.keys())
    
    def cleanup_expired(self) -> int:
        """清理过期会话"""
        with self._lock:
            expired_ids = [
                sid for sid, s in self._memory_cache.items()
                if s.is_expired()
            ]
            for sid in expired_ids:
                self.delete(sid)
            return len(expired_ids)


class SessionManager:
    """
    会话管理器
    管理 A2A 协议中的会话生命周期
    """
    
    def __init__(
        self,
        persistence: Optional[SessionPersistence] = None,
        default_ttl: int = 3600
    ):
        self._persistence = persistence or SessionPersistence()
        self._default_ttl = default_ttl
        self._active_sessions: Dict[str, A2ASession] = {}
        self._lock = threading.RLock()
        
        # 回调
        self._on_session_create: Optional[Callable] = None
        self._on_session_expire: Optional[Callable] = None
    
    def create_session(
        self,
        user_id: str,
        participants: List[str],
        context_id: Optional[str] = None,
        ttl: Optional[int] = None,
        initial_context: Optional[Dict[str, Any]] = None
    ) -> A2ASession:
        """创建新会话"""
        with self._lock:
            session = A2ASession(
                user_id=user_id,
                context_id=context_id,
                participants=participants,
                ttl_seconds=ttl or self._default_ttl,
                expires_at=int(time.time() * 1000) + (ttl or self._default_ttl) * 1000,
                injected_context=initial_context or {}
            )
            
            self._active_sessions[session.session_id] = session
            self._persistence.save(session)
            
            if self._on_session_create:
                self._on_session_create(session)
            
            logger.info(f"Session created: {session.session_id}")
            return session
    
    def get_session(self, session_id: str) -> Optional[A2ASession]:
        """获取会话"""
        with self._lock:
            if session_id in self._active_sessions:
                session = self._active_sessions[session_id]
                if not session.is_expired():
                    return session
                else:
                    self._expire_session(session)
            
            # 从持久化存储加载
            session = self._persistence.load(session_id)
            if session:
                self._active_sessions[session_id] = session
            return session
    
    def inject_session(
        self,
        session_id: str,
        context: Dict[str, Any],
        agent_id: str
    ) -> bool:
        """
        注入会话上下文
        用于 Agent 之间的上下文传递
        """
        session = self.get_session(session_id)
        if not session:
            logger.warning(f"Session not found for injection: {session_id}")
            return False
        
        if agent_id not in session.participants:
            logger.warning(f"Agent {agent_id} not in session participants")
            return False
        
        for key, value in context.items():
            session.inject_context(key, value)
        
        self._persistence.save(session)
        logger.info(f"Context injected into session {session_id} by {agent_id}")
        return True
    
    def terminate_session(self, session_id: str) -> bool:
        """终止会话"""
        with self._lock:
            if session_id in self._active_sessions:
                session = self._active_sessions[session_id]
                session.state = SessionState.TERMINATED
                self._persistence.save(session)
                del self._active_sessions[session_id]
                logger.info(f"Session terminated: {session_id}")
                return True
            return False
    
    def _expire_session(self, session: A2ASession):
        """使会话过期"""
        with self._lock:
            session.state = SessionState.EXPIRED
            if session.session_id in self._active_sessions:
                del self._active_sessions[session.session_id]
            
            if self._on_session_expire:
                self._on_session_expire(session)
            
            logger.info(f"Session expired: {session.session_id}")
    
    def cleanup_idle_sessions(self, idle_threshold: int = 300) -> int:
        """清理空闲会话"""
        with self._lock:
            cleaned = 0
            for session_id in list(self._active_sessions.keys()):
                session = self._active_sessions[session_id]
                if session.is_idle(idle_threshold):
                    self._expire_session(session)
                    cleaned += 1
            return cleaned
