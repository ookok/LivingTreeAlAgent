"""
CommandPalette - 命令面板

支持斜杠命令快捷触发，提升用户体验。

功能：
1. 支持 /analyze、/report、/search 等快捷命令
2. 快速触发常用功能
3. 支持命令自动补全
4. 支持自定义命令注册
"""

from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from loguru import logger
from enum import Enum
import re


class CommandCategory(Enum):
    """命令类别"""
    ANALYSIS = "analysis"
    REPORTING = "reporting"
    SEARCH = "search"
    TOOLS = "tools"
    NAVIGATION = "navigation"
    SETTINGS = "settings"
    OTHER = "other"


@dataclass
class Command:
    """命令定义"""
    name: str
    description: str
    category: CommandCategory
    shortcut: str  # 斜杠命令，如 "/analyze"
    handler: Callable[..., Any]
    parameters: List[Dict[str, Any]] = field(default_factory=list)
    enabled: bool = True


class CommandPalette:
    """
    命令面板
    
    核心功能：
    1. 支持斜杠命令快捷触发
    2. 命令自动补全
    3. 自定义命令注册
    4. 命令执行和历史记录
    """
    
    def __init__(self):
        self._logger = logger.bind(component="CommandPalette")
        self._commands: Dict[str, Command] = {}
        self._command_history: List[str] = []
        self._max_history_size = 50
        self._load_default_commands()
    
    def _load_default_commands(self):
        """加载默认命令"""
        # 分析类命令
        self.register_command(Command(
            name="分析",
            description="分析当前任务或数据",
            category=CommandCategory.ANALYSIS,
            shortcut="/analyze",
            handler=self._default_handler,
            parameters=[
                {"name": "target", "description": "分析目标", "required": False}
            ]
        ))
        
        self.register_command(Command(
            name="深入分析",
            description="对数据进行深入分析",
            category=CommandCategory.ANALYSIS,
            shortcut="/deep_analyze",
            handler=self._default_handler
        ))
        
        # 报告类命令
        self.register_command(Command(
            name="生成报告",
            description="生成分析报告",
            category=CommandCategory.REPORTING,
            shortcut="/report",
            handler=self._default_handler,
            parameters=[
                {"name": "format", "description": "输出格式 (markdown/html)", "required": False}
            ]
        ))
        
        self.register_command(Command(
            name="摘要",
            description="生成内容摘要",
            category=CommandCategory.REPORTING,
            shortcut="/summarize",
            handler=self._default_handler
        ))
        
        # 搜索类命令
        self.register_command(Command(
            name="搜索",
            description="搜索知识或信息",
            category=CommandCategory.SEARCH,
            shortcut="/search",
            handler=self._default_handler,
            parameters=[
                {"name": "query", "description": "搜索关键词", "required": True}
            ]
        ))
        
        self.register_command(Command(
            name="网络搜索",
            description="在网络上搜索信息",
            category=CommandCategory.SEARCH,
            shortcut="/web_search",
            handler=self._default_handler,
            parameters=[
                {"name": "query", "description": "搜索关键词", "required": True}
            ]
        ))
        
        # 工具类命令
        self.register_command(Command(
            name="工具列表",
            description="列出可用工具",
            category=CommandCategory.TOOLS,
            shortcut="/tools",
            handler=self._default_handler
        ))
        
        self.register_command(Command(
            name="使用工具",
            description="使用指定工具",
            category=CommandCategory.TOOLS,
            shortcut="/use",
            handler=self._default_handler,
            parameters=[
                {"name": "tool_name", "description": "工具名称", "required": True}
            ]
        ))
        
        # 导航类命令
        self.register_command(Command(
            name="切换工作区",
            description="切换到指定工作区",
            category=CommandCategory.NAVIGATION,
            shortcut="/workspace",
            handler=self._default_handler,
            parameters=[
                {"name": "name", "description": "工作区名称", "required": True}
            ]
        ))
        
        self.register_command(Command(
            name="返回主页",
            description="返回主页面",
            category=CommandCategory.NAVIGATION,
            shortcut="/home",
            handler=self._default_handler
        ))
        
        # 设置类命令
        self.register_command(Command(
            name="设置",
            description="打开设置面板",
            category=CommandCategory.SETTINGS,
            shortcut="/settings",
            handler=self._default_handler
        ))
        
        self.register_command(Command(
            name="帮助",
            description="显示帮助信息",
            category=CommandCategory.SETTINGS,
            shortcut="/help",
            handler=self._default_handler
        ))
        
        # 其他命令
        self.register_command(Command(
            name="清除历史",
            description="清除对话历史",
            category=CommandCategory.OTHER,
            shortcut="/clear",
            handler=self._default_handler
        ))
        
        self.register_command(Command(
            name="重启",
            description="重启智能体",
            category=CommandCategory.OTHER,
            shortcut="/restart",
            handler=self._default_handler
        ))
    
    def _default_handler(self, **kwargs):
        """默认命令处理器"""
        command_name = kwargs.get("_command_name", "unknown")
        self._logger.info(f"执行命令: {command_name}")
        return {"command": command_name, "args": kwargs}
    
    def register_command(self, command: Command):
        """
        注册命令
        
        Args:
            command: 命令对象
        """
        self._commands[command.shortcut] = command
        self._logger.info(f"注册命令: {command.shortcut} -> {command.name}")
    
    def unregister_command(self, shortcut: str) -> bool:
        """
        注销命令
        
        Args:
            shortcut: 命令快捷方式
            
        Returns:
            是否成功
        """
        if shortcut in self._commands:
            del self._commands[shortcut]
            self._logger.info(f"注销命令: {shortcut}")
            return True
        return False
    
    def parse_command(self, input_text: str) -> Optional[Dict[str, Any]]:
        """
        解析输入文本中的命令
        
        Args:
            input_text: 输入文本
            
        Returns:
            命令解析结果，包含命令名、参数等
        """
        # 检查是否以斜杠开头
        if not input_text.startswith("/"):
            return None
        
        # 使用正则表达式解析命令
        pattern = r"/(\w+)(?:\s+(.+))?"
        match = re.match(pattern, input_text.strip())
        
        if not match:
            return None
        
        command_name = match.group(1)
        params_str = match.group(2)
        
        # 查找命令
        shortcut = f"/{command_name}"
        command = self._commands.get(shortcut)
        
        if not command or not command.enabled:
            return None
        
        # 解析参数
        params = self._parse_parameters(params_str, command.parameters)
        
        return {
            "command": command,
            "shortcut": shortcut,
            "parameters": params,
            "raw_input": input_text
        }
    
    def _parse_parameters(self, params_str: Optional[str], param_defs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        解析命令参数
        
        Args:
            params_str: 参数字符串
            param_defs: 参数定义
            
        Returns:
            解析后的参数字典
        """
        params = {}
        
        if not params_str:
            return params
        
        # 简单的空格分隔参数解析
        parts = params_str.split()
        
        # 如果只有一个参数且没有指定名称，使用第一个参数名
        if len(parts) == 1 and param_defs:
            params[param_defs[0]["name"]] = parts[0]
            return params
        
        # 解析命名参数（格式: key=value）
        for part in parts:
            if "=" in part:
                key, value = part.split("=", 1)
                params[key.strip()] = value.strip()
            else:
                # 位置参数
                params[part] = True
        
        return params
    
    def execute_command(self, input_text: str) -> Any:
        """
        执行命令
        
        Args:
            input_text: 输入文本
            
        Returns:
            命令执行结果
        """
        parsed = self.parse_command(input_text)
        
        if not parsed:
            return None
        
        command = parsed["command"]
        params = parsed["parameters"]
        
        # 添加命令名到参数
        params["_command_name"] = command.name
        params["_shortcut"] = command.shortcut
        
        # 记录命令历史
        self._record_history(input_text)
        
        # 执行命令
        try:
            result = command.handler(**params)
            self._logger.info(f"命令执行成功: {command.shortcut}")
            return result
        except Exception as e:
            self._logger.error(f"命令执行失败 {command.shortcut}: {e}")
            return {"error": str(e), "command": command.shortcut}
    
    def _record_history(self, command_text: str):
        """记录命令历史"""
        self._command_history.append(command_text)
        
        # 保持历史记录大小
        if len(self._command_history) > self._max_history_size:
            self._command_history.pop(0)
    
    def suggest_commands(self, input_text: str) -> List[Dict[str, Any]]:
        """
        根据输入文本建议命令
        
        Args:
            input_text: 输入文本
            
        Returns:
            匹配的命令列表
        """
        suggestions = []
        
        if not input_text.startswith("/"):
            return suggestions
        
        # 获取已输入的部分
        partial = input_text.lower()
        
        for shortcut, command in self._commands.items():
            if command.enabled and shortcut.lower().startswith(partial):
                suggestions.append({
                    "shortcut": shortcut,
                    "name": command.name,
                    "description": command.description,
                    "category": command.category.value,
                    "parameters": command.parameters
                })
        
        # 按匹配程度排序
        suggestions.sort(key=lambda x: len(x["shortcut"]))
        
        return suggestions
    
    def get_commands_by_category(self, category: CommandCategory) -> List[Command]:
        """
        获取指定类别的命令
        
        Args:
            category: 命令类别
            
        Returns:
            命令列表
        """
        return [cmd for cmd in self._commands.values() if cmd.category == category and cmd.enabled]
    
    def get_all_commands(self) -> List[Dict[str, Any]]:
        """获取所有命令"""
        commands = []
        
        for shortcut, command in self._commands.items():
            commands.append({
                "shortcut": shortcut,
                "name": command.name,
                "description": command.description,
                "category": command.category.value,
                "parameters": command.parameters,
                "enabled": command.enabled
            })
        
        return commands
    
    def get_command_history(self) -> List[str]:
        """获取命令历史"""
        return list(reversed(self._command_history))
    
    def clear_history(self):
        """清空命令历史"""
        self._command_history = []
        self._logger.info("命令历史已清空")
    
    def set_command_handler(self, shortcut: str, handler: Callable[..., Any]) -> bool:
        """
        设置命令处理器
        
        Args:
            shortcut: 命令快捷方式
            handler: 处理函数
            
        Returns:
            是否成功
        """
        if shortcut in self._commands:
            self._commands[shortcut].handler = handler
            self._logger.info(f"更新命令处理器: {shortcut}")
            return True
        return False