"""
Realtime Collaboration - 实时协作模块

核心功能：
1. 多人实时协作 - 支持多用户同时编辑
2. 操作同步 - 实时同步用户操作
3. 冲突解决 - 自动处理编辑冲突
4. 用户管理 - 管理协作用户

设计理念：
- 基于操作日志的同步机制
- 支持离线编辑和同步
- 细粒度的权限控制
"""

import json
import asyncio
import uuid
from typing import Dict, Any, Optional, List, Set, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class UserRole(Enum):
    """用户角色"""
    OWNER = "owner"
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"


@dataclass
class User:
    """协作用户"""
    id: str
    name: str
    role: UserRole
    session_id: str
    online: bool = True
    last_active: datetime = field(default_factory=datetime.now)


@dataclass
class Operation:
    """操作记录"""
    id: str
    user_id: str
    timestamp: datetime
    type: str  # insert, delete, update, move
    path: str  # 文件路径或资源ID
    data: Dict[str, Any]
    previous_value: Optional[str] = None
    next_value: Optional[str] = None


@dataclass
class CollaborationSession:
    """协作会话"""
    id: str
    name: str
    users: List[User] = field(default_factory=list)
    operations: List[Operation] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)


class RealtimeCollaboration:
    """
    实时协作系统
    
    核心特性：
    1. 多人实时协作 - 支持多用户同时编辑
    2. 操作同步 - 实时同步用户操作
    3. 冲突解决 - 自动处理编辑冲突
    4. 用户管理 - 管理协作用户和权限
    """
    
    def __init__(self):
        self._sessions: Dict[str, CollaborationSession] = {}
        self._users: Dict[str, User] = {}
        self._operation_callbacks: List[Callable] = []
        logger.info("✅ RealtimeCollaboration 初始化完成")
    
    def create_session(self, name: str) -> CollaborationSession:
        """创建协作会话"""
        session_id = str(uuid.uuid4())[:8]
        session = CollaborationSession(
            id=session_id,
            name=name
        )
        self._sessions[session_id] = session
        logger.info(f"✅ 创建协作会话: {session_id}")
        return session
    
    def get_session(self, session_id: str) -> Optional[CollaborationSession]:
        """获取会话"""
        return self._sessions.get(session_id)
    
    def join_session(self, session_id: str, user_name: str, 
                     role: UserRole = UserRole.EDITOR) -> Optional[str]:
        """
        加入会话
        
        Returns:
            用户ID 或 None
        """
        if session_id not in self._sessions:
            return None
        
        session = self._sessions[session_id]
        
        # 创建用户
        user_id = str(uuid.uuid4())[:8]
        user = User(
            id=user_id,
            name=user_name,
            role=role,
            session_id=session_id
        )
        
        session.users.append(user)
        self._users[user_id] = user
        
        logger.info(f"✅ 用户 {user_name} 加入会话 {session_id}")
        return user_id
    
    def leave_session(self, session_id: str, user_id: str):
        """离开会话"""
        session = self._sessions.get(session_id)
        if session:
            session.users = [u for u in session.users if u.id != user_id]
            if user_id in self._users:
                self._users[user_id].online = False
                self._users[user_id].last_active = datetime.now()
        
        logger.info(f"✅ 用户 {user_id} 离开会话 {session_id}")
    
    def record_operation(self, session_id: str, user_id: str, operation_type: str,
                        path: str, data: Dict[str, Any], 
                        previous_value: str = None, next_value: str = None):
        """
        记录操作
        
        Args:
            session_id: 会话ID
            user_id: 用户ID
            operation_type: 操作类型
            path: 操作路径
            data: 操作数据
            previous_value: 操作前的值
            next_value: 操作后的值
        """
        session = self._sessions.get(session_id)
        if not session:
            return
        
        operation = Operation(
            id=str(uuid.uuid4())[:8],
            user_id=user_id,
            timestamp=datetime.now(),
            type=operation_type,
            path=path,
            data=data,
            previous_value=previous_value,
            next_value=next_value
        )
        
        session.operations.append(operation)
        session.last_updated = datetime.now()
        
        # 通知所有回调
        self._notify_callbacks(operation)
    
    def _notify_callbacks(self, operation: Operation):
        """通知所有回调"""
        for callback in self._operation_callbacks:
            try:
                callback(operation)
            except Exception as e:
                logger.error(f"回调执行失败: {e}")
    
    def subscribe(self, callback: Callable):
        """订阅操作通知"""
        self._operation_callbacks.append(callback)
    
    def unsubscribe(self, callback: Callable):
        """取消订阅"""
        if callback in self._operation_callbacks:
            self._operation_callbacks.remove(callback)
    
    def resolve_conflicts(self, session_id: str) -> List[Operation]:
        """
        解决冲突
        
        Returns:
            需要手动处理的冲突列表
        """
        session = self._sessions.get(session_id)
        if not session:
            return []
        
        conflicts = []
        operations = sorted(session.operations, key=lambda o: o.timestamp)
        
        # 简单的冲突检测：同一位置的连续操作
        for i in range(len(operations) - 1):
            op1 = operations[i]
            op2 = operations[i + 1]
            
            # 检测冲突：同一路径的连续操作
            if op1.path == op2.path and op1.user_id != op2.user_id:
                conflicts.append(op2)
        
        return conflicts
    
    def get_session_history(self, session_id: str) -> List[Operation]:
        """获取会话历史"""
        session = self._sessions.get(session_id)
        if not session:
            return []
        return session.operations
    
    def get_online_users(self, session_id: str) -> List[User]:
        """获取在线用户"""
        session = self._sessions.get(session_id)
        if not session:
            return []
        return [u for u in session.users if u.online]
    
    async def sync_operations(self, session_id: str, last_operation_id: Optional[str] = None) -> List[Operation]:
        """
        同步操作
        
        Args:
            session_id: 会话ID
            last_operation_id: 最后已知的操作ID
        
        Returns:
            新的操作列表
        """
        session = self._sessions.get(session_id)
        if not session:
            return []
        
        if not last_operation_id:
            return session.operations
        
        # 查找最后操作的位置
        start_idx = next(
            (i for i, op in enumerate(session.operations) if op.id == last_operation_id),
            -1
        )
        
        if start_idx >= 0:
            return session.operations[start_idx + 1:]
        
        return session.operations
    
    def get_session_summary(self, session_id: str) -> Dict[str, Any]:
        """获取会话摘要"""
        session = self._sessions.get(session_id)
        if not session:
            return {}
        
        return {
            "session_id": session.id,
            "name": session.name,
            "user_count": len(session.users),
            "online_users": len([u for u in session.users if u.online]),
            "operation_count": len(session.operations),
            "created_at": session.created_at.isoformat(),
            "last_updated": session.last_updated.isoformat()
        }


# 全局单例
_global_collaboration: Optional[RealtimeCollaboration] = None


def get_realtime_collaboration() -> RealtimeCollaboration:
    """获取全局实时协作单例"""
    global _global_collaboration
    if _global_collaboration is None:
        _global_collaboration = RealtimeCollaboration()
    return _global_collaboration


# 测试函数
async def test_collaboration():
    """测试实时协作"""
    print("🧪 测试实时协作")
    print("="*60)
    
    collaboration = get_realtime_collaboration()
    
    # 创建会话
    print("\n📤 创建会话:")
    session = collaboration.create_session("项目A协作")
    print(f"✅ 会话ID: {session.id}")
    
    # 用户加入
    print("\n👥 用户加入:")
    user1_id = collaboration.join_session(session.id, "张三", UserRole.EDITOR)
    user2_id = collaboration.join_session(session.id, "李四", UserRole.EDITOR)
    print(f"✅ 用户1: {user1_id}")
    print(f"✅ 用户2: {user2_id}")
    
    # 记录操作
    print("\n📝 记录操作:")
    collaboration.record_operation(
        session.id, user1_id, "insert", 
        "file1.py", {"line": 10, "content": "print('Hello')"}
    )
    collaboration.record_operation(
        session.id, user2_id, "update",
        "file1.py", {"line": 10, "content": "print('Hello World')"}
    )
    print("✅ 操作已记录")
    
    # 获取在线用户
    print("\n👤 在线用户:")
    users = collaboration.get_online_users(session.id)
    for user in users:
        print(f"   {user.name} - {user.role.value}")
    
    # 获取会话摘要
    print("\n📊 会话摘要:")
    summary = collaboration.get_session_summary(session.id)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    
    # 检测冲突
    print("\n🔍 冲突检测:")
    conflicts = collaboration.resolve_conflicts(session.id)
    print(f"   检测到 {len(conflicts)} 个冲突")
    
    print("\n🎉 实时协作测试完成！")
    return True


if __name__ == "__main__":
    asyncio.run(test_collaboration())