"""
IdentityAwareness - 身份感知能力

功能：
1. 用户身份识别（多账户支持）
2. 用户画像构建（兴趣、偏好、历史行为）
3. 访问权限管理（RBAC）
4. 个性化推荐
5. 上下文感知（当前任务、对话历史）

遵循自我进化原则：
- 从用户行为中学习用户偏好
- 动态调整服务策略
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from loguru import logger
from datetime import datetime
from enum import Enum


class UserRole(Enum):
    """用户角色"""
    ADMIN = "admin"
    USER = "user"
    GUEST = "guest"


class PermissionLevel(Enum):
    """权限级别"""
    FULL = "full"
    LIMITED = "limited"
    READ_ONLY = "read_only"


@dataclass
class UserProfile:
    """用户画像"""
    user_id: str
    username: str
    role: UserRole
    permission_level: PermissionLevel
    preferences: Dict[str, Any] = field(default_factory=dict)
    interests: List[str] = field(default_factory=list)
    history: List[Dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    last_active: datetime = field(default_factory=datetime.now)


@dataclass
class SessionContext:
    """会话上下文"""
    session_id: str
    user_id: str
    current_task: Optional[str] = None
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.now)


class IdentityAwareness:
    """
    身份感知能力
    
    识别用户身份，构建用户画像，提供个性化服务。
    """

    def __init__(self):
        self._logger = logger.bind(component="IdentityAwareness")
        self._users: Dict[str, UserProfile] = {}
        self._sessions: Dict[str, SessionContext] = {}
        self._current_user_id: Optional[str] = None

    def register_user(self, user_id: str, username: str, role: UserRole = UserRole.USER) -> UserProfile:
        """
        注册用户
        
        Args:
            user_id: 用户 ID
            username: 用户名
            role: 用户角色
            
        Returns:
            UserProfile
        """
        if user_id in self._users:
            raise ValueError(f"用户已存在: {user_id}")

        profile = UserProfile(
            user_id=user_id,
            username=username,
            role=role,
            permission_level=self._get_permission_level(role)
        )

        self._users[user_id] = profile
        self._logger.info(f"已注册用户: {username}")
        return profile

    def _get_permission_level(self, role: UserRole) -> PermissionLevel:
        """根据角色获取权限级别"""
        if role == UserRole.ADMIN:
            return PermissionLevel.FULL
        elif role == UserRole.USER:
            return PermissionLevel.LIMITED
        else:
            return PermissionLevel.READ_ONLY

    def login(self, user_id: str) -> bool:
        """
        用户登录
        
        Args:
            user_id: 用户 ID
            
        Returns:
            是否登录成功
        """
        if user_id not in self._users:
            return False

        self._current_user_id = user_id
        
        # 更新最后活跃时间
        self._users[user_id].last_active = datetime.now()

        # 创建会话
        session_id = f"session_{user_id}_{len(self._sessions)}"
        self._sessions[session_id] = SessionContext(
            session_id=session_id,
            user_id=user_id
        )

        self._logger.info(f"用户登录: {user_id}")
        return True

    def logout(self):
        """用户登出"""
        self._current_user_id = None
        self._logger.info("用户已登出")

    def get_current_user(self) -> Optional[UserProfile]:
        """获取当前用户"""
        if self._current_user_id:
            return self._users.get(self._current_user_id)
        return None

    def get_user(self, user_id: str) -> Optional[UserProfile]:
        """获取用户"""
        return self._users.get(user_id)

    def update_preferences(self, user_id: str, preferences: Dict[str, Any]):
        """
        更新用户偏好
        
        Args:
            user_id: 用户 ID
            preferences: 偏好字典
        """
        if user_id not in self._users:
            raise ValueError(f"用户不存在: {user_id}")

        self._users[user_id].preferences.update(preferences)
        self._logger.info(f"更新用户偏好: {user_id}")

    def record_activity(self, user_id: str, activity: Dict[str, Any]):
        """
        记录用户活动
        
        Args:
            user_id: 用户 ID
            activity: 活动记录
        """
        if user_id not in self._users:
            return

        activity["timestamp"] = datetime.now().isoformat()
        self._users[user_id].history.append(activity)
        
        # 限制历史记录数量
        if len(self._users[user_id].history) > 1000:
            self._users[user_id].history = self._users[user_id].history[-500:]

        # 从活动中学习兴趣
        self._learn_interests(user_id, activity)

    def _learn_interests(self, user_id: str, activity: Dict[str, Any]):
        """从活动中学习用户兴趣"""
        user = self._users[user_id]
        task = activity.get("task", "")
        
        # 简单的兴趣提取规则
        keywords = ["编程", "写作", "数据分析", "设计", "音乐", "学习", "游戏"]
        
        for keyword in keywords:
            if keyword in task and keyword not in user.interests:
                user.interests.append(keyword)

    def has_permission(self, user_id: str, permission: str) -> bool:
        """
        检查用户权限
        
        Args:
            user_id: 用户 ID
            permission: 权限名称
            
        Returns:
            是否有权限
        """
        user = self._users.get(user_id)
        if not user:
            return False

        if user.permission_level == PermissionLevel.FULL:
            return True
        
        if user.permission_level == PermissionLevel.LIMITED:
            # 有限权限允许大部分操作
            return permission not in ["admin", "delete_all"]
        
        return False

    def get_personalized_response(self, query: str) -> Dict[str, Any]:
        """
        获取个性化响应
        
        Args:
            query: 用户查询
            
        Returns:
            个性化建议
        """
        user = self.get_current_user()
        if not user:
            return {"response": "请先登录以获取个性化服务"}

        # 根据用户兴趣提供个性化建议
        recommendations = []
        
        if "编程" in user.interests:
            recommendations.append("您可能对代码生成工具感兴趣")
        if "写作" in user.interests:
            recommendations.append("您可能对文案助手感兴趣")
        if "数据分析" in user.interests:
            recommendations.append("您可能对数据可视化工具感兴趣")

        return {
            "user": user.username,
            "recommendations": recommendations,
            "context": "个性化服务已启用"
        }

    def get_session_context(self, session_id: str) -> Optional[SessionContext]:
        """获取会话上下文"""
        return self._sessions.get(session_id)

    def update_session_context(self, session_id: str, current_task: Optional[str] = None):
        """更新会话上下文"""
        session = self._sessions.get(session_id)
        if session:
            if current_task:
                session.current_task = current_task

    def get_stats(self) -> Dict[str, Any]:
        """获取身份感知统计信息"""
        active_users = sum(1 for u in self._users.values() if (datetime.now() - u.last_active).seconds < 3600)
        
        return {
            "total_users": len(self._users),
            "active_users": active_users,
            "active_sessions": len(self._sessions),
            "current_user": self._current_user_id
        }