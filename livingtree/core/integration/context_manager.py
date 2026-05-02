"""
上下文管理器 - Context Manager

功能：
1. 全局上下文存储
2. 上下文感知路由
3. 上下文生命周期管理
4. 多会话支持

上下文包含：
- 当前对话状态
- 用户偏好设置
- 系统运行状态
- 历史记录
- 环境信息
"""

import logging
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SessionContext:
    """会话上下文"""
    session_id: str
    user_id: str = ""
    conversation_history: list = None
    current_goal: str = ""
    preferences: Dict = None
    system_state: Dict = None
    last_activity: float = None
    
    def __post_init__(self):
        if self.conversation_history is None:
            self.conversation_history = []
        if self.preferences is None:
            self.preferences = {}
        if self.system_state is None:
            self.system_state = {}
        if self.last_activity is None:
            self.last_activity = time.time()
    
    def update_activity(self):
        """更新活动时间"""
        self.last_activity = time.time()
    
    def add_message(self, role: str, content: str):
        """添加对话消息"""
        self.conversation_history.append({
            'role': role,
            'content': content,
            'timestamp': time.time()
        })
        
        # 限制历史长度
        max_history = 100
        if len(self.conversation_history) > max_history:
            self.conversation_history = self.conversation_history[-max_history:]


class ContextManager:
    """
    上下文管理器 - 管理全局和会话级上下文
    
    核心能力：
    1. 全局上下文存储
    2. 多会话管理
    3. 上下文感知
    4. 自动清理过期会话
    """
    
    def __init__(self):
        self._global_context: Dict[str, Any] = {
            'system_start_time': time.time(),
            'total_requests': 0,
            'active_sessions': 0,
            'system_metrics': {},
            'feature_flags': {}
        }
        
        self._sessions: Dict[str, SessionContext] = {}
        self._session_timeout = 3600  # 会话超时时间（秒）
        
        # 初始化默认特性标志
        self._init_feature_flags()
    
    def _init_feature_flags(self):
        """初始化特性标志"""
        self._global_context['feature_flags'] = {
            'memory_enabled': True,
            'learning_enabled': True,
            'reasoning_enabled': True,
            'self_awareness_enabled': True,
            'mcp_enabled': True,
            'fallback_enabled': True
        }
    
    def get_global_context(self) -> Dict[str, Any]:
        """获取全局上下文"""
        return self._global_context
    
    def set_global_context(self, key: str, value: Any):
        """设置全局上下文"""
        self._global_context[key] = value
    
    def update_global_metrics(self, metrics: Dict):
        """更新全局指标"""
        self._global_context['system_metrics'].update(metrics)
    
    def create_session(self, user_id: str = "") -> str:
        """
        创建新会话
        
        Args:
            user_id: 用户ID
        
        Returns:
            会话ID
        """
        session_id = f"session_{int(time.time() * 1000)}_{hash(user_id) % 10000}"
        
        self._sessions[session_id] = SessionContext(
            session_id=session_id,
            user_id=user_id
        )
        
        self._global_context['active_sessions'] += 1
        logger.info(f"创建会话: {session_id}")
        
        return session_id
    
    def get_session(self, session_id: str) -> Optional[SessionContext]:
        """
        获取会话上下文
        
        Args:
            session_id: 会话ID
        
        Returns:
            会话上下文
        """
        session = self._sessions.get(session_id)
        
        if session:
            # 检查是否过期
            if time.time() - session.last_activity > self._session_timeout:
                self._remove_session(session_id)
                return None
            
            session.update_activity()
        
        return session
    
    def remove_session(self, session_id: str):
        """
        删除会话
        
        Args:
            session_id: 会话ID
        """
        self._remove_session(session_id)
    
    def _remove_session(self, session_id: str):
        """内部删除会话"""
        if session_id in self._sessions:
            del self._sessions[session_id]
            self._global_context['active_sessions'] -= 1
            logger.info(f"删除会话: {session_id}")
    
    def cleanup_expired_sessions(self):
        """清理过期会话"""
        expired = []
        
        for session_id, session in self._sessions.items():
            if time.time() - session.last_activity > self._session_timeout:
                expired.append(session_id)
        
        for session_id in expired:
            self._remove_session(session_id)
        
        if expired:
            logger.info(f"清理过期会话: {len(expired)}")
    
    def get_active_sessions(self) -> list:
        """获取活跃会话列表"""
        self.cleanup_expired_sessions()
        return list(self._sessions.keys())
    
    def get_session_count(self) -> int:
        """获取会话数量"""
        self.cleanup_expired_sessions()
        return len(self._sessions)
    
    def update_session_goal(self, session_id: str, goal: str):
        """更新会话目标"""
        session = self.get_session(session_id)
        if session:
            session.current_goal = goal
    
    def add_conversation_message(self, session_id: str, role: str, content: str):
        """添加对话消息"""
        session = self.get_session(session_id)
        if session:
            session.add_message(role, content)
    
    def get_conversation_history(self, session_id: str) -> list:
        """获取对话历史"""
        session = self.get_session(session_id)
        return session.conversation_history if session else []
    
    def get_feature_flag(self, flag_name: str) -> bool:
        """获取特性标志"""
        return self._global_context['feature_flags'].get(flag_name, False)
    
    def set_feature_flag(self, flag_name: str, value: bool):
        """设置特性标志"""
        self._global_context['feature_flags'][flag_name] = value
        logger.info(f"特性标志更新: {flag_name} = {value}")


# 单例模式
_context_instance = None

def get_context_manager() -> ContextManager:
    """获取上下文管理器实例"""
    global _context_instance
    if _context_instance is None:
        _context_instance = ContextManager()
    return _context_instance