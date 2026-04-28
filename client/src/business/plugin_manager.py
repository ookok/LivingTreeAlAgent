"""
PluginManager - 插件化能力层

参考 DeepTutor 的"6种学习模式"设计，实现"N种工作模式"。

核心功能：
1. 支持用户自由组合工具
2. 工具与工作流解耦
3. 定义多种工作模式（如：数据处理模式、报告生成模式、分析模式等）
4. 支持插件的动态加载和卸载
"""

from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from loguru import logger
from datetime import datetime
from enum import Enum
import importlib
import os
import json


class PluginType(Enum):
    """插件类型"""
    TOOL = "tool"              # 工具插件
    WORKFLOW = "workflow"      # 工作流插件
    MODE = "mode"              # 工作模式插件
    DATA_SOURCE = "data_source" # 数据源插件
    VISUALIZATION = "visualization" # 可视化插件


class PluginStatus(Enum):
    """插件状态"""
    LOADED = "loaded"
    ENABLED = "enabled"
    DISABLED = "disabled"
    ERROR = "error"


@dataclass
class Plugin:
    """插件定义"""
    id: str
    name: str
    description: str
    type: PluginType
    module_path: str
    class_name: str
    status: PluginStatus = PluginStatus.LOADED
    version: str = "1.0.0"
    author: str = "unknown"
    dependencies: List[str] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)
    instance: Any = None


@dataclass
class WorkMode:
    """工作模式定义"""
    id: str
    name: str
    description: str
    tools: List[str] = field(default_factory=list)
    workflows: List[str] = field(default_factory=list)
    preferred_models: List[str] = field(default_factory=list)
    icon: str = "📋"
    color: str = "#3366ff"


class PluginManager:
    """
    插件管理器
    
    核心功能：
    1. 插件的动态加载和卸载
    2. 工作模式管理（支持多种工作模式）
    3. 工具与工作流解耦
    4. 插件配置和状态管理
    """
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls, *args, **kwargs)
        return cls._instance
    
    def __init__(self, plugins_dir: str = None):
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self._logger = logger.bind(component="PluginManager")
        self._plugins: Dict[str, Plugin] = {}
        self._work_modes: Dict[str, WorkMode] = {}
        self._plugins_dir = plugins_dir or self._get_default_plugins_dir()
        self._tool_registry = None
        
        os.makedirs(self._plugins_dir, exist_ok=True)
        self._load_plugins()
        self._load_default_work_modes()
        self._initialized = True
    
    def _get_default_plugins_dir(self) -> str:
        """获取默认插件目录"""
        return os.path.join(os.path.expanduser("~"), ".livingtree", "plugins")
    
    def _load_plugins(self):
        """加载插件"""
        try:
            for filename in os.listdir(self._plugins_dir):
                if filename.endswith(".json"):
                    filepath = os.path.join(self._plugins_dir, filename)
                    self._load_plugin_from_file(filepath)
        except Exception as e:
            self._logger.error(f"加载插件失败: {e}")
    
    def _load_plugin_from_file(self, filepath: str):
        """从文件加载插件配置"""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                config = json.load(f)
            
            plugin = Plugin(
                id=config.get("id", ""),
                name=config.get("name", ""),
                description=config.get("description", ""),
                type=PluginType(config.get("type", "tool")),
                module_path=config.get("module_path", ""),
                class_name=config.get("class_name", ""),
                version=config.get("version", "1.0.0"),
                author=config.get("author", "unknown"),
                dependencies=config.get("dependencies", []),
                config=config.get("config", {})
            )
            
            self._plugins[plugin.id] = plugin
            self._logger.info(f"加载插件: {plugin.name} ({plugin.id})")
        except Exception as e:
            self._logger.error(f"加载插件文件失败 {filepath}: {e}")
    
    def _load_default_work_modes(self):
        """加载默认工作模式"""
        # 数据处理模式
        self._work_modes["data_processing"] = WorkMode(
            id="data_processing",
            name="数据处理",
            description="数据采集、清洗、转换和存储",
            tools=["data_fetcher", "data_cleaner", "data_transformer", "database_writer"],
            icon="📊",
            color="#3366ff"
        )
        
        # 报告生成模式
        self._work_modes["report_generation"] = WorkMode(
            id="report_generation",
            name="报告生成",
            description="数据收集 → 分析 → 可视化 → 报告生成",
            tools=["data_fetcher", "analyzer", "visualizer", "report_writer"],
            workflows=["environment_report"],
            icon="📝",
            color="#00cc66"
        )
        
        # 分析模式
        self._work_modes["analysis"] = WorkMode(
            id="analysis",
            name="深度分析",
            description="使用 AI 进行深度数据分析和洞察发现",
            tools=["ai_analyzer", "pattern_detector", "insight_generator", "forecaster"],
            preferred_models=["gpt-4", "claude-3"],
            icon="🔍",
            color="#ff6600"
        )
        
        # 开发模式
        self._work_modes["development"] = WorkMode(
            id="development",
            name="开发模式",
            description="代码编写、测试和部署",
            tools=["code_generator", "test_runner", "deployer", "code_analyzer"],
            icon="💻",
            color="#6633cc"
        )
        
        # 研究模式
        self._work_modes["research"] = WorkMode(
            id="research",
            name="研究模式",
            description="文献检索、知识整合、假设验证",
            tools=["web_search", "paper_finder", "knowledge_graph", "hypothesis_tester"],
            icon="🔬",
            color="#cc3366"
        )
        
        # 日常办公模式
        self._work_modes["office"] = WorkMode(
            id="office",
            name="日常办公",
            description="文档处理、日程管理、邮件处理",
            tools=["document_processor", "calendar_manager", "email_handler", "note_taker"],
            icon="📋",
            color="#33cccc"
        )
        
        self._logger.info(f"加载了 {len(self._work_modes)} 种工作模式")
    
    def set_tool_registry(self, tool_registry):
        """设置工具注册中心"""
        self._tool_registry = tool_registry
    
    def register_plugin(self, plugin: Plugin):
        """注册插件"""
        self._plugins[plugin.id] = plugin
        self._logger.info(f"注册插件: {plugin.name}")
    
    def load_plugin(self, plugin_id: str) -> bool:
        """加载插件实例"""
        plugin = self._plugins.get(plugin_id)
        if not plugin:
            return False
        
        try:
            # 动态导入模块
            module = importlib.import_module(plugin.module_path)
            class_ = getattr(module, plugin.class_name)
            
            # 创建实例
            plugin.instance = class_(**plugin.config)
            plugin.status = PluginStatus.LOADED
            
            # 如果是工具插件，注册到工具注册表
            if plugin.type == PluginType.TOOL and self._tool_registry:
                self._tool_registry.register_tool(plugin.instance)
            
            self._logger.info(f"加载插件实例: {plugin.name}")
            return True
        except Exception as e:
            plugin.status = PluginStatus.ERROR
            self._logger.error(f"加载插件失败 {plugin_id}: {e}")
            return False
    
    def unload_plugin(self, plugin_id: str):
        """卸载插件"""
        plugin = self._plugins.get(plugin_id)
        if plugin:
            plugin.instance = None
            plugin.status = PluginStatus.DISABLED
            self._logger.info(f"卸载插件: {plugin.name}")
    
    def enable_plugin(self, plugin_id: str):
        """启用插件"""
        plugin = self._plugins.get(plugin_id)
        if plugin:
            plugin.status = PluginStatus.ENABLED
            self._logger.info(f"启用插件: {plugin.name}")
    
    def disable_plugin(self, plugin_id: str):
        """禁用插件"""
        plugin = self._plugins.get(plugin_id)
        if plugin:
            plugin.status = PluginStatus.DISABLED
            self._logger.info(f"禁用插件: {plugin.name}")
    
    def get_plugin(self, plugin_id: str) -> Optional[Plugin]:
        """获取插件"""
        return self._plugins.get(plugin_id)
    
    def list_plugins(self, plugin_type: Optional[PluginType] = None) -> List[Plugin]:
        """列出插件"""
        result = []
        for plugin in self._plugins.values():
            if plugin_type and plugin.type != plugin_type:
                continue
            result.append(plugin)
        return result
    
    def add_work_mode(self, work_mode: WorkMode):
        """添加工作模式"""
        self._work_modes[work_mode.id] = work_mode
        self._logger.info(f"添加工作模式: {work_mode.name}")
    
    def get_work_mode(self, mode_id: str) -> Optional[WorkMode]:
        """获取工作模式"""
        return self._work_modes.get(mode_id)
    
    def list_work_modes(self) -> List[WorkMode]:
        """列出所有工作模式"""
        return list(self._work_modes.values())
    
    def activate_work_mode(self, mode_id: str) -> Dict[str, Any]:
        """
        激活工作模式
        
        Args:
            mode_id: 工作模式 ID
            
        Returns:
            激活结果，包含可用工具和工作流
        """
        mode = self._work_modes.get(mode_id)
        if not mode:
            return {"error": f"工作模式不存在: {mode_id}"}
        
        self._logger.info(f"激活工作模式: {mode.name}")
        
        return {
            "success": True,
            "mode_id": mode.id,
            "mode_name": mode.name,
            "description": mode.description,
            "tools": mode.tools,
            "workflows": mode.workflows,
            "preferred_models": mode.preferred_models,
            "icon": mode.icon,
            "color": mode.color
        }
    
    def create_custom_work_mode(self, name: str, description: str, 
                               tools: List[str], workflows: List[str] = None,
                               preferred_models: List[str] = None,
                               icon: str = "📋", color: str = "#3366ff") -> WorkMode:
        """
        创建自定义工作模式
        
        Args:
            name: 模式名称
            description: 描述
            tools: 工具列表
            workflows: 工作流列表（可选）
            preferred_models: 推荐模型列表（可选）
            icon: 图标（可选）
            color: 颜色（可选）
            
        Returns:
            创建的工作模式
        """
        mode_id = name.lower().replace(" ", "_")
        
        mode = WorkMode(
            id=mode_id,
            name=name,
            description=description,
            tools=tools,
            workflows=workflows or [],
            preferred_models=preferred_models or [],
            icon=icon,
            color=color
        )
        
        self._work_modes[mode_id] = mode
        self._logger.info(f"创建自定义工作模式: {name}")
        
        return mode
    
    def compose_tools(self, tool_ids: List[str]) -> List[Dict[str, Any]]:
        """
        组合工具
        
        Args:
            tool_ids: 工具 ID 列表
            
        Returns:
            工具信息列表
        """
        result = []
        
        for tool_id in tool_ids:
            if self._tool_registry:
                tool_info = self._tool_registry.get_tool_info(tool_id)
                if tool_info:
                    result.append(tool_info)
        
        return result
    
    def save_plugin_config(self, plugin_id: str, config: Dict[str, Any]):
        """保存插件配置"""
        plugin = self._plugins.get(plugin_id)
        if plugin:
            plugin.config = config
            # 保存到文件
            filepath = os.path.join(self._plugins_dir, f"{plugin_id}.json")
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump({
                    "id": plugin.id,
                    "name": plugin.name,
                    "description": plugin.description,
                    "type": plugin.type.value,
                    "module_path": plugin.module_path,
                    "class_name": plugin.class_name,
                    "version": plugin.version,
                    "author": plugin.author,
                    "dependencies": plugin.dependencies,
                    "config": config
                }, f, indent=2, ensure_ascii=False)
    
    @classmethod
    def get_instance(cls) -> 'PluginManager':
        """获取单例实例"""
        if not cls._instance:
            cls._instance = PluginManager()
        return cls._instance