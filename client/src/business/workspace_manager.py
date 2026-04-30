"""
WorkspaceManager - 工作区管理器

实现多工作区隔离功能，支持：
1. 多项目切换
2. 每个工作区独立配置（模型、工具、技能）
3. 工作区状态持久化
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from loguru import logger
from datetime import datetime
import json
import os

from business.nanochat_config import config as nanochat_config


@dataclass
class WorkspaceConfig:
    """工作区配置"""
    name: str
    description: str = ""
    model_config: Dict[str, Any] = field(default_factory=dict)
    tools_config: Dict[str, Any] = field(default_factory=dict)
    skills_config: Dict[str, Any] = field(default_factory=dict)
    active: bool = False


@dataclass
class Workspace:
    """工作区"""
    workspace_id: str
    name: str
    description: str = ""
    config: WorkspaceConfig = field(default_factory=lambda: WorkspaceConfig(name=""))
    created_at: datetime = field(default_factory=datetime.now)
    last_used_at: Optional[datetime] = None
    is_active: bool = False


class WorkspaceManager:
    """
    工作区管理器
    
    核心功能：
    1. 创建和管理多个工作区
    2. 工作区切换
    3. 每个工作区独立配置
    4. 工作区状态持久化
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._logger = logger.bind(component="WorkspaceManager")
        self._workspaces: Dict[str, Workspace] = {}
        self._active_workspace_id: Optional[str] = None
        self._storage_path = self._get_storage_path()
        self._load_workspaces()
        self._initialized = True
    
    @classmethod
    def get_instance(cls):
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def _get_storage_path(self) -> str:
        """获取工作区存储路径"""
        path = os.path.join(os.path.expanduser("~"), ".livingtree", "workspaces")
        os.makedirs(path, exist_ok=True)
        return path
    
    def _load_workspaces(self):
        """加载工作区配置"""
        try:
            config_file = os.path.join(self._storage_path, "workspaces.json")
            if os.path.exists(config_file):
                with open(config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for workspace_id, workspace_data in data.items():
                        self._workspaces[workspace_id] = Workspace(
                            workspace_id=workspace_id,
                            name=workspace_data["name"],
                            description=workspace_data.get("description", ""),
                            config=WorkspaceConfig(
                                name=workspace_data.get("config", {}).get("name", ""),
                                description=workspace_data.get("config", {}).get("description", ""),
                                model_config=workspace_data.get("config", {}).get("model_config", {}),
                                tools_config=workspace_data.get("config", {}).get("tools_config", {}),
                                skills_config=workspace_data.get("config", {}).get("skills_config", {})
                            ),
                            created_at=datetime.fromisoformat(workspace_data["created_at"]),
                            last_used_at=datetime.fromisoformat(workspace_data["last_used_at"]) if workspace_data.get("last_used_at") else None,
                            is_active=workspace_data.get("is_active", False)
                        )
                        if workspace_data.get("is_active"):
                            self._active_workspace_id = workspace_id
            
            if not self._workspaces:
                self._create_default_workspace()
        except Exception as e:
            self._logger.error(f"加载工作区失败: {e}")
            self._create_default_workspace()
    
    def _create_default_workspace(self):
        """创建默认工作区"""
        default_workspace = Workspace(
            workspace_id="default",
            name="默认工作区",
            description="系统默认工作区",
            config=WorkspaceConfig(
                name="默认配置",
                model_config=self._get_default_model_config(),
                tools_config=self._get_default_tools_config(),
                skills_config=self._get_default_skills_config()
            ),
            is_active=True
        )
        self._workspaces["default"] = default_workspace
        self._active_workspace_id = "default"
        self._save_workspaces()
    
    def _get_default_model_config(self) -> Dict[str, Any]:
        """获取默认模型配置"""
        try:
            ollama_config = nanochat_config.ollama if hasattr(nanochat_config, 'ollama') else None
            return {
                "provider": getattr(ollama_config, 'provider', "ollama") if ollama_config else "ollama",
                "model": getattr(ollama_config, 'model', "llama3") if ollama_config else "llama3",
                "temperature": getattr(ollama_config, 'temperature', 0.7) if ollama_config else 0.7,
                "max_tokens": getattr(ollama_config, 'max_tokens', 4096) if ollama_config else 4096,
                "api_base": getattr(ollama_config, 'url', "http://localhost:11434") if ollama_config else "http://localhost:11434"
            }
        except Exception as e:
            self._logger.warning(f"获取默认模型配置失败: {e}")
            return {
                "provider": "ollama",
                "model": "llama3",
                "temperature": 0.7,
                "max_tokens": 4096,
                "api_base": "http://localhost:11434"
            }
    
    def _get_default_tools_config(self) -> Dict[str, Any]:
        """获取默认工具配置"""
        return {
            "enabled_tools": ["web_crawler", "deep_search", "vector_database", "knowledge_graph"],
            "disabled_tools": [],
            "tool_priority": ["web_crawler", "deep_search"]
        }
    
    def _get_default_skills_config(self) -> Dict[str, Any]:
        """获取默认技能配置"""
        return {
            "enabled_skills": [],
            "skill_recommendations": True,
            "auto_encapsulation": True
        }
    
    def _save_workspaces(self):
        """保存工作区配置"""
        try:
            data = {}
            for workspace_id, workspace in self._workspaces.items():
                data[workspace_id] = {
                    "name": workspace.name,
                    "description": workspace.description,
                    "config": {
                        "name": workspace.config.name,
                        "description": workspace.config.description,
                        "model_config": workspace.config.model_config,
                        "tools_config": workspace.config.tools_config,
                        "skills_config": workspace.config.skills_config
                    },
                    "created_at": workspace.created_at.isoformat(),
                    "last_used_at": workspace.last_used_at.isoformat() if workspace.last_used_at else None,
                    "is_active": workspace.is_active
                }
            
            config_file = os.path.join(self._storage_path, "workspaces.json")
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self._logger.error(f"保存工作区失败: {e}")
    
    def create_workspace(self, name: str, description: str = "", 
                        model_config: Optional[Dict[str, Any]] = None,
                        tools_config: Optional[Dict[str, Any]] = None,
                        skills_config: Optional[Dict[str, Any]] = None) -> Workspace:
        """
        创建新工作区
        
        Args:
            name: 工作区名称
            description: 工作区描述
            model_config: 模型配置（可选）
            tools_config: 工具配置（可选）
            skills_config: 技能配置（可选）
        
        Returns:
            创建的工作区
        """
        workspace_id = f"workspace_{int(datetime.now().timestamp())}"
        
        workspace = Workspace(
            workspace_id=workspace_id,
            name=name,
            description=description,
            config=WorkspaceConfig(
                name=name,
                description=description,
                model_config=model_config or self._get_default_model_config(),
                tools_config=tools_config or self._get_default_tools_config(),
                skills_config=skills_config or self._get_default_skills_config()
            )
        )
        
        self._workspaces[workspace_id] = workspace
        self._save_workspaces()
        self._logger.info(f"创建工作区: {name} ({workspace_id})")
        
        return workspace
    
    def delete_workspace(self, workspace_id: str) -> bool:
        """
        删除工作区
        
        Args:
            workspace_id: 工作区ID
        
        Returns:
            是否删除成功
        """
        if workspace_id == "default":
            self._logger.warning("不能删除默认工作区")
            return False
        
        if workspace_id not in self._workspaces:
            return False
        
        # 如果删除的是当前激活的工作区，切换到默认工作区
        if workspace_id == self._active_workspace_id:
            self.switch_workspace("default")
        
        del self._workspaces[workspace_id]
        self._save_workspaces()
        self._logger.info(f"删除工作区: {workspace_id}")
        
        return True
    
    def switch_workspace(self, workspace_id: str) -> bool:
        """
        切换工作区
        
        Args:
            workspace_id: 目标工作区ID
        
        Returns:
            是否切换成功
        """
        if workspace_id not in self._workspaces:
            return False
        
        # 更新当前工作区状态
        if self._active_workspace_id:
            self._workspaces[self._active_workspace_id].is_active = False
            self._workspaces[self._active_workspace_id].last_used_at = datetime.now()
        
        # 设置新工作区为激活状态
        self._workspaces[workspace_id].is_active = True
        self._workspaces[workspace_id].last_used_at = datetime.now()
        self._active_workspace_id = workspace_id
        
        self._save_workspaces()
        self._logger.info(f"切换工作区: {workspace_id}")
        
        # 应用工作区配置
        self._apply_workspace_config(self._workspaces[workspace_id])
        
        return True
    
    def _apply_workspace_config(self, workspace: Workspace):
        """应用工作区配置"""
        self._logger.debug(f"应用工作区配置: {workspace.name}")
        # 这里可以添加配置应用逻辑，如更新全局配置等
    
    def get_workspace(self, workspace_id: str) -> Optional[Workspace]:
        """获取工作区"""
        return self._workspaces.get(workspace_id)
    
    def get_active_workspace(self) -> Optional[Workspace]:
        """获取当前激活的工作区"""
        if not self._active_workspace_id:
            return None
        return self._workspaces.get(self._active_workspace_id)
    
    def list_workspaces(self) -> List[Workspace]:
        """获取所有工作区列表"""
        return list(self._workspaces.values())
    
    def update_workspace_config(self, workspace_id: str, config: Dict[str, Any]) -> bool:
        """
        更新工作区配置
        
        Args:
            workspace_id: 工作区ID
            config: 配置字典
        
        Returns:
            是否更新成功
        """
        if workspace_id not in self._workspaces:
            return False
        
        workspace = self._workspaces[workspace_id]
        
        if "model_config" in config:
            workspace.config.model_config.update(config["model_config"])
        
        if "tools_config" in config:
            workspace.config.tools_config.update(config["tools_config"])
        
        if "skills_config" in config:
            workspace.config.skills_config.update(config["skills_config"])
        
        self._save_workspaces()
        
        # 如果是当前工作区，应用新配置
        if workspace_id == self._active_workspace_id:
            self._apply_workspace_config(workspace)
        
        return True
    
    def get_workspace_model_config(self, workspace_id: Optional[str] = None) -> Dict[str, Any]:
        """获取工作区模型配置"""
        if not workspace_id:
            workspace_id = self._active_workspace_id
        
        if not workspace_id or workspace_id not in self._workspaces:
            return self._get_default_model_config()
        
        return self._workspaces[workspace_id].config.model_config
    
    def get_workspace_tools_config(self, workspace_id: Optional[str] = None) -> Dict[str, Any]:
        """获取工作区工具配置"""
        if not workspace_id:
            workspace_id = self._active_workspace_id
        
        if not workspace_id or workspace_id not in self._workspaces:
            return self._get_default_tools_config()
        
        return self._workspaces[workspace_id].config.tools_config
    
    def get_workspace_skills_config(self, workspace_id: Optional[str] = None) -> Dict[str, Any]:
        """获取工作区技能配置"""
        if not workspace_id:
            workspace_id = self._active_workspace_id
        
        if not workspace_id or workspace_id not in self._workspaces:
            return self._get_default_skills_config()
        
        return self._workspaces[workspace_id].config.skills_config
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        active_count = sum(1 for w in self._workspaces.values() if w.is_active)
        return {
            "total_workspaces": len(self._workspaces),
            "active_workspace": self._active_workspace_id,
            "active_count": active_count,
            "storage_path": self._storage_path
        }