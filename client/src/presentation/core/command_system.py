"""
命令系统 - Command System

功能：
1. 命令注册与执行
2. 快捷键绑定
3. 命令面板
4. 命令历史
"""

import logging
import json
import os
from typing import Dict, Any, Callable, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Command:
    """命令定义"""
    id: str
    name: str
    description: str
    handler: Callable
    shortcut: Optional[str] = None
    category: str = "general"


class CommandSystem:
    """
    命令系统 - 管理应用命令
    
    核心功能：
    1. 命令注册
    2. 快捷键绑定
    3. 命令搜索
    4. 命令历史
    """
    
    def __init__(self):
        self._commands: Dict[str, Command] = {}
        self._shortcuts: Dict[str, str] = {}
        self._command_history: List[str] = []
        self._max_history = 100
        
        # 加载快捷键配置
        self._load_keybindings()
    
    def register_command(self, command: Command):
        """注册命令"""
        self._commands[command.id] = command
        
        # 注册快捷键
        if command.shortcut:
            self._shortcuts[command.shortcut.lower()] = command.id
        
        logger.info(f"命令注册成功: {command.id}")
    
    def register_commands(self, commands: List[Command]):
        """批量注册命令"""
        for cmd in commands:
            self.register_command(cmd)
    
    def execute_command(self, command_id: str, **kwargs) -> Any:
        """执行命令"""
        if command_id not in self._commands:
            logger.error(f"命令不存在: {command_id}")
            return None
        
        try:
            command = self._commands[command_id]
            result = command.handler(**kwargs)
            
            # 记录历史
            self._record_history(command_id)
            
            logger.debug(f"命令执行成功: {command_id}")
            return result
        
        except Exception as e:
            logger.error(f"命令执行失败 {command_id}: {e}")
            return None
    
    def execute_by_shortcut(self, shortcut: str) -> Any:
        """通过快捷键执行命令"""
        shortcut_key = shortcut.lower()
        
        if shortcut_key not in self._shortcuts:
            logger.debug(f"未找到快捷键绑定: {shortcut}")
            return None
        
        command_id = self._shortcuts[shortcut_key]
        return self.execute_command(command_id)
    
    def search_commands(self, query: str) -> List[Command]:
        """搜索命令"""
        query_lower = query.lower()
        results = []
        
        for command in self._commands.values():
            if (query_lower in command.id.lower() or
                query_lower in command.name.lower() or
                query_lower in command.description.lower()):
                results.append(command)
        
        # 按匹配度排序
        results.sort(key=lambda c: (
            query_lower in c.name.lower(),
            query_lower in c.id.lower()
        ), reverse=True)
        
        return results
    
    def get_command(self, command_id: str) -> Optional[Command]:
        """获取命令"""
        return self._commands.get(command_id)
    
    def get_all_commands(self) -> List[Command]:
        """获取所有命令"""
        return list(self._commands.values())
    
    def get_commands_by_category(self, category: str) -> List[Command]:
        """按类别获取命令"""
        return [cmd for cmd in self._commands.values() if cmd.category == category]
    
    def _record_history(self, command_id: str):
        """记录命令历史"""
        # 移除重复
        if command_id in self._command_history:
            self._command_history.remove(command_id)
        
        # 添加到开头
        self._command_history.insert(0, command_id)
        
        # 限制长度
        if len(self._command_history) > self._max_history:
            self._command_history = self._command_history[:self._max_history]
    
    def get_command_history(self, limit: int = 20) -> List[str]:
        """获取命令历史"""
        return self._command_history[:limit]
    
    def clear_history(self):
        """清空命令历史"""
        self._command_history.clear()
    
    def _load_keybindings(self):
        """加载快捷键配置"""
        keybindings_path = os.path.join(os.path.expanduser("~"), ".hermes", "keybindings.json")
        
        if os.path.exists(keybindings_path):
            try:
                with open(keybindings_path, 'r') as f:
                    keybindings = json.load(f)
                
                for command_id, shortcut in keybindings.items():
                    if command_id in self._commands:
                        self._commands[command_id].shortcut = shortcut
                        self._shortcuts[shortcut.lower()] = command_id
                
                logger.info("快捷键配置已加载")
            except Exception as e:
                logger.error(f"加载快捷键配置失败: {e}")
    
    def save_keybindings(self):
        """保存快捷键配置"""
        keybindings = {
            cmd.id: cmd.shortcut
            for cmd in self._commands.values()
            if cmd.shortcut
        }
        
        keybindings_path = os.path.join(os.path.expanduser("~"), ".hermes", "keybindings.json")
        os.makedirs(os.path.dirname(keybindings_path), exist_ok=True)
        
        with open(keybindings_path, 'w') as f:
            json.dump(keybindings, f, indent=2)
        
        logger.info("快捷键配置已保存")
    
    def set_shortcut(self, command_id: str, shortcut: str):
        """设置命令快捷键"""
        if command_id not in self._commands:
            logger.error(f"命令不存在: {command_id}")
            return
        
        # 移除旧的快捷键绑定
        old_shortcut = self._commands[command_id].shortcut
        if old_shortcut:
            if old_shortcut.lower() in self._shortcuts:
                del self._shortcuts[old_shortcut.lower()]
        
        # 设置新快捷键
        self._commands[command_id].shortcut = shortcut
        self._shortcuts[shortcut.lower()] = command_id
        
        # 保存配置
        self.save_keybindings()


# 全局命令系统实例
_command_system_instance = None

def get_command_system() -> CommandSystem:
    """获取全局命令系统"""
    global _command_system_instance
    
    if _command_system_instance is None:
        _command_system_instance = CommandSystem()
    
    return _command_system_instance