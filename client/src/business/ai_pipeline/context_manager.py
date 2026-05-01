"""
上下文管理器 - 统一上下文管理

核心功能：
1. 工作流上下文管理
2. 代码库上下文感知
3. 用户会话管理
4. 任务状态追踪
5. 上下文增强与优化
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json
import os
from pathlib import Path
from uuid import uuid4


@dataclass
class TaskContext:
    """任务上下文"""
    task_id: str
    workflow_id: str
    user_id: Optional[str] = None
    variables: Dict[str, Any] = field(default_factory=dict)
    history: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "pending"
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class CodebaseContext:
    """代码库上下文"""
    project_name: str
    root_path: str
    structure: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    coding_style: Dict[str, Any] = field(default_factory=dict)
    last_analyzed: Optional[datetime] = None


@dataclass
class UserSession:
    """用户会话"""
    session_id: str
    user_id: str
    context: Dict[str, Any] = field(default_factory=dict)
    preferences: Dict[str, Any] = field(default_factory=dict)
    history: List[Dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)


class ContextManager:
    """
    上下文管理器
    
    核心特性：
    1. 统一的上下文存储和管理
    2. 代码库上下文感知
    3. 用户会话管理
    4. 任务状态追踪
    5. 上下文增强
    """

    def __init__(self, storage_path: Optional[str] = None):
        self._storage_path = Path(storage_path or os.path.expanduser("~/.livingtree/contexts"))
        self._storage_path.mkdir(parents=True, exist_ok=True)
        
        self._task_contexts: Dict[str, TaskContext] = {}
        self._codebase_contexts: Dict[str, CodebaseContext] = {}
        self._user_sessions: Dict[str, UserSession] = {}
        
        self._load_contexts()

    def _load_contexts(self):
        """加载所有上下文"""
        self._task_contexts = self._load_task_contexts()
        self._codebase_contexts = self._load_codebase_contexts()
        self._user_sessions = self._load_user_sessions()

    def _load_task_contexts(self) -> Dict[str, TaskContext]:
        """加载任务上下文"""
        return self._load_objects("tasks", TaskContext)

    def _load_codebase_contexts(self) -> Dict[str, CodebaseContext]:
        """加载代码库上下文"""
        return self._load_objects("codebases", CodebaseContext)

    def _load_user_sessions(self) -> Dict[str, UserSession]:
        """加载用户会话"""
        return self._load_objects("sessions", UserSession)

    def _load_objects(self, dir_name: str, cls):
        """从目录加载对象"""
        obj_dir = self._storage_path / dir_name
        obj_dir.mkdir(exist_ok=True)
        
        objects = {}
        for filepath in obj_dir.glob("*.json"):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    obj = self._deserialize_object(data, cls)
                    objects[obj.task_id if hasattr(obj, 'task_id') else obj.session_id if hasattr(obj, 'session_id') else obj.project_name] = obj
            except Exception as e:
                print(f"加载 {dir_name} 失败 {filepath}: {e}")
        
        return objects

    def _save_objects(self, dir_name: str, objects: Dict[str, Any], key_attr: str):
        """保存对象到目录"""
        obj_dir = self._storage_path / dir_name
        obj_dir.mkdir(exist_ok=True)
        
        for obj in objects.values():
            obj_id = getattr(obj, key_attr)
            filepath = obj_dir / f"{obj_id}.json"
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self._serialize_object(obj), f, ensure_ascii=False, indent=2)

    def _serialize_object(self, obj) -> Dict[str, Any]:
        """序列化对象"""
        data = obj.__dict__.copy()
        
        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()
        
        return data

    def _deserialize_object(self, data: Dict[str, Any], cls):
        """反序列化对象"""
        for key, value in data.items():
            if key in ["created_at", "updated_at", "last_analyzed", "last_activity"] and isinstance(value, str):
                data[key] = datetime.fromisoformat(value)
        
        return cls(**data)

    def create_task_context(self, workflow_id: str, user_id: Optional[str] = None, 
                           variables: Optional[Dict[str, Any]] = None) -> str:
        """
        创建任务上下文
        
        Args:
            workflow_id: 工作流ID
            user_id: 用户ID
            variables: 初始变量
            
        Returns:
            任务上下文ID
        """
        task_id = str(uuid4())
        
        context = TaskContext(
            task_id=task_id,
            workflow_id=workflow_id,
            user_id=user_id,
            variables=variables or {}
        )
        
        self._task_contexts[task_id] = context
        self._save_objects("tasks", self._task_contexts, "task_id")
        
        return task_id

    def get_task_context(self, task_id: str) -> Optional[TaskContext]:
        """获取任务上下文"""
        return self._task_contexts.get(task_id)

    def update_task_context(self, task_id: str, variables: Dict[str, Any], status: Optional[str] = None):
        """更新任务上下文"""
        context = self._task_contexts.get(task_id)
        if context:
            context.variables.update(variables)
            if status:
                context.status = status
            context.updated_at = datetime.now()
            
            context.history.append({
                "timestamp": datetime.now().isoformat(),
                "variables": dict(variables)
            })
            
            self._save_objects("tasks", self._task_contexts, "task_id")

    def delete_task_context(self, task_id: str):
        """删除任务上下文"""
        if task_id in self._task_contexts:
            del self._task_contexts[task_id]
            self._save_objects("tasks", self._task_contexts, "task_id")

    async def analyze_codebase(self, root_path: str) -> CodebaseContext:
        """
        分析代码库生成上下文
        
        Args:
            root_path: 代码库根路径
            
        Returns:
            代码库上下文
        """
        print(f"🔍 分析代码库: {root_path}")
        
        project_name = os.path.basename(root_path)
        
        context = CodebaseContext(
            project_name=project_name,
            root_path=root_path,
            structure=await self._scan_project_structure(root_path),
            dependencies=await self._extract_dependencies(root_path),
            coding_style=await self._detect_coding_style(root_path),
            last_analyzed=datetime.now()
        )
        
        self._codebase_contexts[project_name] = context
        self._save_objects("codebases", self._codebase_contexts, "project_name")
        
        return context

    async def _scan_project_structure(self, root_path: str) -> Dict[str, Any]:
        """扫描项目结构"""
        structure = {}
        
        try:
            for item in os.listdir(root_path):
                item_path = os.path.join(root_path, item)
                if os.path.isdir(item_path):
                    structure[item] = {"type": "directory", "children": {}}
                else:
                    structure[item] = {"type": "file", "extension": os.path.splitext(item)[1]}
        except Exception as e:
            print(f"扫描项目结构失败: {e}")
        
        return structure

    async def _extract_dependencies(self, root_path: str) -> List[str]:
        """提取依赖"""
        dependencies = []
        
        requirements_file = os.path.join(root_path, "requirements.txt")
        if os.path.exists(requirements_file):
            try:
                with open(requirements_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            dependencies.append(line.split('=')[0] if '=' in line else line)
            except Exception as e:
                print(f"提取依赖失败: {e}")
        
        return dependencies

    async def _detect_coding_style(self, root_path: str) -> Dict[str, Any]:
        """检测编码风格"""
        style = {
            "indentation": "spaces",
            "indent_size": 4,
            "line_length": 88,
            "docstring_style": "google"
        }
        
        return style

    def get_codebase_context(self, project_name: str) -> Optional[CodebaseContext]:
        """获取代码库上下文"""
        return self._codebase_contexts.get(project_name)

    def create_user_session(self, user_id: str) -> str:
        """
        创建用户会话
        
        Args:
            user_id: 用户ID
            
        Returns:
            会话ID
        """
        session_id = str(uuid4())
        
        session = UserSession(
            session_id=session_id,
            user_id=user_id
        )
        
        self._user_sessions[session_id] = session
        self._save_objects("sessions", self._user_sessions, "session_id")
        
        return session_id

    def get_user_session(self, session_id: str) -> Optional[UserSession]:
        """获取用户会话"""
        return self._user_sessions.get(session_id)

    def update_user_session(self, session_id: str, context: Dict[str, Any], 
                           preferences: Optional[Dict[str, Any]] = None):
        """更新用户会话"""
        session = self._user_sessions.get(session_id)
        if session:
            session.context.update(context)
            if preferences:
                session.preferences.update(preferences)
            session.last_activity = datetime.now()
            
            session.history.append({
                "timestamp": datetime.now().isoformat(),
                "context": dict(context)
            })
            
            self._save_objects("sessions", self._user_sessions, "session_id")

    def close_user_session(self, session_id: str):
        """关闭用户会话"""
        if session_id in self._user_sessions:
            del self._user_sessions[session_id]
            self._save_objects("sessions", self._user_sessions, "session_id")

    def enhance_context(self, task_id: str, additional_info: Dict[str, Any]):
        """增强任务上下文"""
        context = self._task_contexts.get(task_id)
        if context:
            context.variables.update(additional_info)
            context.updated_at = datetime.now()
            self._save_objects("tasks", self._task_contexts, "task_id")

    def get_all_task_contexts(self) -> List[TaskContext]:
        """获取所有任务上下文"""
        return list(self._task_contexts.values())

    def get_all_user_sessions(self) -> List[UserSession]:
        """获取所有用户会话"""
        return list(self._user_sessions.values())

    def get_context_stats(self) -> Dict[str, Any]:
        """获取上下文统计"""
        return {
            "task_contexts": len(self._task_contexts),
            "codebase_contexts": len(self._codebase_contexts),
            "user_sessions": len(self._user_sessions)
        }


def get_context_manager() -> ContextManager:
    """获取上下文管理器单例"""
    global _context_manager_instance
    if _context_manager_instance is None:
        _context_manager_instance = ContextManager()
    return _context_manager_instance


_context_manager_instance = None