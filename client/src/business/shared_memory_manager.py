"""
SharedMemoryManager - 共享知识/记忆层

参考 DeepTutor 的"共享知识/记忆层"设计，实现统一的记忆访问机制。

核心功能：
1. 统一所有智能体、所有工具的记忆访问
2. 记忆包含：用户画像、项目上下文、历史对话、工具使用记录
3. 避免信息孤岛
4. 支持多模态数据存储和检索
"""

from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field
from loguru import logger
from datetime import datetime
from enum import Enum
import json
import os


class MemoryType(Enum):
    """记忆类型"""
    USER_PROFILE = "user_profile"      # 用户画像
    PROJECT_CONTEXT = "project_context"  # 项目上下文
    CONVERSATION_HISTORY = "conversation_history"  # 历史对话
    TOOL_USAGE = "tool_usage"          # 工具使用记录
    KNOWLEDGE_BASE = "knowledge_base"  # 知识库
    SYSTEM_STATE = "system_state"      # 系统状态
    TEMPORARY = "temporary"            # 临时记忆（会话级）


@dataclass
class MemoryEntry:
    """记忆条目"""
    key: str
    value: Any
    memory_type: MemoryType
    user_id: Optional[str] = None
    project_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None  # 过期时间（临时记忆）
    tags: List[str] = field(default_factory=list)


@dataclass
class UserProfile:
    """用户画像"""
    user_id: str
    name: str = ""
    email: str = ""
    preferences: Dict[str, Any] = field(default_factory=dict)
    skills: List[str] = field(default_factory=list)
    history: List[str] = field(default_factory=list)  # 历史任务ID
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class ProjectContext:
    """项目上下文"""
    project_id: str
    name: str = ""
    description: str = ""
    status: str = "active"
    workspace_id: Optional[str] = None
    tools: List[str] = field(default_factory=list)  # 使用的工具列表
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class ConversationHistory:
    """对话历史"""
    conversation_id: str
    user_id: str
    messages: List[Dict[str, Any]] = field(default_factory=list)
    summary: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class ToolUsageRecord:
    """工具使用记录"""
    tool_name: str
    user_id: str
    project_id: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    result: Any = None
    success: bool = True
    execution_time: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)


class SharedMemoryManager:
    """
    共享知识/记忆层管理器
    
    参考 DeepTutor 的设计，提供统一的记忆访问接口：
    - 用户画像管理
    - 项目上下文管理
    - 历史对话管理
    - 工具使用记录
    - 知识库管理
    
    所有智能体和工具通过此管理器访问记忆，避免信息孤岛。
    """
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls, *args, **kwargs)
        return cls._instance
    
    def __init__(self, storage_path: str = None):
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self._logger = logger.bind(component="SharedMemoryManager")
        self._storage_path = storage_path or self._get_default_storage_path()
        self._memories: Dict[str, MemoryEntry] = {}
        self._user_profiles: Dict[str, UserProfile] = {}
        self._projects: Dict[str, ProjectContext] = {}
        self._conversations: Dict[str, ConversationHistory] = {}
        self._tool_usage_records: List[ToolUsageRecord] = []
        
        os.makedirs(self._storage_path, exist_ok=True)
        self._load_from_storage()
        self._initialized = True
    
    def _get_default_storage_path(self) -> str:
        """获取默认存储路径"""
        return os.path.join(os.path.expanduser("~"), ".livingtree", "shared_memory")
    
    def _load_from_storage(self):
        """从存储加载记忆数据"""
        try:
            # 加载用户画像
            profile_file = os.path.join(self._storage_path, "profiles.json")
            if os.path.exists(profile_file):
                with open(profile_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for user_id, profile_data in data.items():
                        profile_data["created_at"] = datetime.fromisoformat(profile_data["created_at"])
                        profile_data["updated_at"] = datetime.fromisoformat(profile_data["updated_at"])
                        self._user_profiles[user_id] = UserProfile(**profile_data)
            
            # 加载项目上下文
            projects_file = os.path.join(self._storage_path, "projects.json")
            if os.path.exists(projects_file):
                with open(projects_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for project_id, project_data in data.items():
                        project_data["created_at"] = datetime.fromisoformat(project_data["created_at"])
                        project_data["updated_at"] = datetime.fromisoformat(project_data["updated_at"])
                        self._projects[project_id] = ProjectContext(**project_data)
            
            self._logger.info(f"加载了 {len(self._user_profiles)} 个用户画像和 {len(self._projects)} 个项目")
        except Exception as e:
            self._logger.error(f"加载记忆数据失败: {e}")
    
    def _save_to_storage(self):
        """保存记忆数据到存储"""
        try:
            # 保存用户画像
            profile_file = os.path.join(self._storage_path, "profiles.json")
            profiles_data = {}
            for user_id, profile in self._user_profiles.items():
                profiles_data[user_id] = {
                    "user_id": profile.user_id,
                    "name": profile.name,
                    "email": profile.email,
                    "preferences": profile.preferences,
                    "skills": profile.skills,
                    "history": profile.history,
                    "created_at": profile.created_at.isoformat(),
                    "updated_at": profile.updated_at.isoformat()
                }
            with open(profile_file, "w", encoding="utf-8") as f:
                json.dump(profiles_data, f, indent=2, ensure_ascii=False)
            
            # 保存项目上下文
            projects_file = os.path.join(self._storage_path, "projects.json")
            projects_data = {}
            for project_id, project in self._projects.items():
                projects_data[project_id] = {
                    "project_id": project.project_id,
                    "name": project.name,
                    "description": project.description,
                    "status": project.status,
                    "workspace_id": project.workspace_id,
                    "tools": project.tools,
                    "created_at": project.created_at.isoformat(),
                    "updated_at": project.updated_at.isoformat()
                }
            with open(projects_file, "w", encoding="utf-8") as f:
                json.dump(projects_data, f, indent=2, ensure_ascii=False)
            
        except Exception as e:
            self._logger.error(f"保存记忆数据失败: {e}")
    
    # === 用户画像管理 ===
    
    def create_user_profile(self, user_id: str, name: str = "", email: str = "") -> UserProfile:
        """创建用户画像"""
        if user_id in self._user_profiles:
            return self._user_profiles[user_id]
        
        profile = UserProfile(
            user_id=user_id,
            name=name,
            email=email
        )
        self._user_profiles[user_id] = profile
        self._save_to_storage()
        
        self._logger.info(f"创建用户画像: {user_id}")
        return profile
    
    def get_user_profile(self, user_id: str) -> Optional[UserProfile]:
        """获取用户画像"""
        return self._user_profiles.get(user_id)
    
    def update_user_profile(self, user_id: str, **kwargs):
        """更新用户画像"""
        profile = self._user_profiles.get(user_id)
        if not profile:
            return
        
        for key, value in kwargs.items():
            if hasattr(profile, key):
                setattr(profile, key, value)
        
        profile.updated_at = datetime.now()
        self._save_to_storage()
    
    def add_user_skill(self, user_id: str, skill: str):
        """添加用户技能"""
        profile = self._user_profiles.get(user_id)
        if profile and skill not in profile.skills:
            profile.skills.append(skill)
            profile.updated_at = datetime.now()
            self._save_to_storage()
    
    def add_user_preference(self, user_id: str, key: str, value: Any):
        """添加用户偏好"""
        profile = self._user_profiles.get(user_id)
        if profile:
            profile.preferences[key] = value
            profile.updated_at = datetime.now()
            self._save_to_storage()
    
    # === 项目上下文管理 ===
    
    def create_project(self, project_id: str, name: str = "", description: str = "") -> ProjectContext:
        """创建项目上下文"""
        if project_id in self._projects:
            return self._projects[project_id]
        
        project = ProjectContext(
            project_id=project_id,
            name=name,
            description=description
        )
        self._projects[project_id] = project
        self._save_to_storage()
        
        self._logger.info(f"创建项目: {project_id}")
        return project
    
    def get_project(self, project_id: str) -> Optional[ProjectContext]:
        """获取项目上下文"""
        return self._projects.get(project_id)
    
    def update_project(self, project_id: str, **kwargs):
        """更新项目上下文"""
        project = self._projects.get(project_id)
        if not project:
            return
        
        for key, value in kwargs.items():
            if hasattr(project, key):
                setattr(project, key, value)
        
        project.updated_at = datetime.now()
        self._save_to_storage()
    
    def add_project_tool(self, project_id: str, tool_name: str):
        """添加项目使用的工具"""
        project = self._projects.get(project_id)
        if project and tool_name not in project.tools:
            project.tools.append(tool_name)
            project.updated_at = datetime.now()
            self._save_to_storage()
    
    # === 对话历史管理 ===
    
    def create_conversation(self, conversation_id: str, user_id: str) -> ConversationHistory:
        """创建对话历史"""
        if conversation_id in self._conversations:
            return self._conversations[conversation_id]
        
        conversation = ConversationHistory(
            conversation_id=conversation_id,
            user_id=user_id
        )
        self._conversations[conversation_id] = conversation
        return conversation
    
    def get_conversation(self, conversation_id: str) -> Optional[ConversationHistory]:
        """获取对话历史"""
        return self._conversations.get(conversation_id)
    
    def add_message(self, conversation_id: str, role: str, content: str, **kwargs):
        """添加对话消息"""
        conversation = self._conversations.get(conversation_id)
        if not conversation:
            return
        
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            **kwargs
        }
        conversation.messages.append(message)
        conversation.updated_at = datetime.now()
    
    def set_conversation_summary(self, conversation_id: str, summary: str):
        """设置对话摘要"""
        conversation = self._conversations.get(conversation_id)
        if conversation:
            conversation.summary = summary
            conversation.updated_at = datetime.now()
    
    # === 工具使用记录 ===
    
    def record_tool_usage(self, tool_name: str, user_id: str, project_id: Optional[str] = None,
                          parameters: Optional[Dict[str, Any]] = None, result: Any = None,
                          success: bool = True, execution_time: float = 0.0):
        """记录工具使用"""
        record = ToolUsageRecord(
            tool_name=tool_name,
            user_id=user_id,
            project_id=project_id,
            parameters=parameters or {},
            result=result,
            success=success,
            execution_time=execution_time
        )
        self._tool_usage_records.append(record)
        
        # 限制记录数量
        if len(self._tool_usage_records) > 1000:
            self._tool_usage_records = self._tool_usage_records[-500:]
        
        self._logger.debug(f"记录工具使用: {tool_name} by {user_id}")
    
    def get_tool_usage_history(self, user_id: Optional[str] = None, tool_name: Optional[str] = None,
                               project_id: Optional[str] = None, limit: int = 100) -> List[ToolUsageRecord]:
        """获取工具使用历史"""
        records = self._tool_usage_records
        
        if user_id:
            records = [r for r in records if r.user_id == user_id]
        if tool_name:
            records = [r for r in records if r.tool_name == tool_name]
        if project_id:
            records = [r for r in records if r.project_id == project_id]
        
        return sorted(records, key=lambda r: r.timestamp, reverse=True)[:limit]
    
    # === 通用记忆操作 ===
    
    def set_memory(self, key: str, value: Any, memory_type: MemoryType,
                   user_id: Optional[str] = None, project_id: Optional[str] = None,
                   expires_at: Optional[datetime] = None, tags: Optional[List[str]] = None):
        """设置记忆"""
        entry = MemoryEntry(
            key=key,
            value=value,
            memory_type=memory_type,
            user_id=user_id,
            project_id=project_id,
            expires_at=expires_at,
            tags=tags or []
        )
        self._memories[key] = entry
        self._logger.debug(f"设置记忆: {key} ({memory_type.value})")
    
    def get_memory(self, key: str) -> Optional[Any]:
        """获取记忆"""
        entry = self._memories.get(key)
        
        # 检查是否过期
        if entry and entry.expires_at and entry.expires_at < datetime.now():
            del self._memories[key]
            return None
        
        return entry.value if entry else None
    
    def delete_memory(self, key: str):
        """删除记忆"""
        if key in self._memories:
            del self._memories[key]
    
    def search_memories(self, query: str, memory_type: Optional[MemoryType] = None,
                        user_id: Optional[str] = None, project_id: Optional[str] = None) -> List[MemoryEntry]:
        """搜索记忆"""
        results = []
        
        for entry in self._memories.values():
            # 过滤类型
            if memory_type and entry.memory_type != memory_type:
                continue
            
            # 过滤用户
            if user_id and entry.user_id != user_id:
                continue
            
            # 过滤项目
            if project_id and entry.project_id != project_id:
                continue
            
            # 搜索关键词
            key_str = str(entry.key).lower()
            value_str = str(entry.value).lower()
            query_str = query.lower()
            
            if query_str in key_str or query_str in value_str:
                results.append(entry)
        
        return sorted(results, key=lambda e: e.created_at, reverse=True)
    
    # === 跨智能体信息共享 ===
    
    def get_user_context(self, user_id: str) -> Dict[str, Any]:
        """获取用户完整上下文"""
        profile = self.get_user_profile(user_id)
        
        context = {
            "user_id": user_id,
            "profile": profile.__dict__ if profile else None,
            "recent_conversations": [],
            "tool_usage_summary": self._get_tool_usage_summary(user_id)
        }
        
        return context
    
    def get_project_context(self, project_id: str) -> Dict[str, Any]:
        """获取项目完整上下文"""
        project = self.get_project(project_id)
        
        context = {
            "project_id": project_id,
            "project": project.__dict__ if project else None,
            "tool_usage_summary": self._get_tool_usage_summary(project_id=project_id)
        }
        
        return context
    
    def _get_tool_usage_summary(self, user_id: str = None, project_id: str = None) -> Dict[str, Any]:
        """获取工具使用摘要"""
        records = self.get_tool_usage_history(user_id=user_id, project_id=project_id)
        
        tool_count = {}
        success_count = 0
        total_time = 0.0
        
        for record in records:
            tool_count[record.tool_name] = tool_count.get(record.tool_name, 0) + 1
            if record.success:
                success_count += 1
            total_time += record.execution_time
        
        return {
            "total_usage": len(records),
            "success_rate": success_count / len(records) if records else 0,
            "avg_execution_time": total_time / len(records) if records else 0,
            "tool_breakdown": tool_count
        }
    
    # === 清理过期记忆 ===
    
    def cleanup_expired_memories(self):
        """清理过期记忆"""
        now = datetime.now()
        expired_keys = []
        
        for key, entry in self._memories.items():
            if entry.expires_at and entry.expires_at < now:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self._memories[key]
        
        if expired_keys:
            self._logger.info(f"清理了 {len(expired_keys)} 条过期记忆")
    
    @classmethod
    def get_instance(cls) -> 'SharedMemoryManager':
        """获取单例实例"""
        if not cls._instance:
            cls._instance = SharedMemoryManager()
        return cls._instance