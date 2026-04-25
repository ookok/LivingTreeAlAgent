"""
斜杠命令系统
===========

实现类似 /spec, /test, /review 的快捷命令
"""

import logging
import re
from typing import Dict, List, Optional, Any, Callable

logger = logging.getLogger(__name__)


class SlashCommand:
    """斜杠命令定义"""
    
    def __init__(
        self,
        command: str,
        description: str,
        handler: Callable,
        skill_id: Optional[str] = None,
        args_schema: Optional[Dict] = None,
        category: str = "general",
    ):
        self.command = command
        self.description = description
        self.handler = handler
        self.skill_id = skill_id
        self.args_schema = args_schema or {}
        self.category = category


class SlashCommandRegistry:
    """
    斜杠命令注册中心
    
    管理和执行斜杠命令
    """
    
    def __init__(self):
        self._commands: Dict[str, SlashCommand] = {}
        
    def register(self, command: SlashCommand):
        """注册斜杠命令"""
        self._commands[command.command] = command
        logger.info(f"[SlashCommand] 注册命令: /{command.command}")
        
    def execute(self, input_text: str) -> Optional[Any]:
        """
        执行斜杠命令
        
        Args:
            input_text: 用户输入（可能包含斜杠命令）
            
        Returns:
            命令执行结果，如果不是命令则返回 None
        """
        # 匹配斜杠命令格式: /command [args]
        match = re.match(r'^/(\w+)\s*(.*)', input_text.strip())
        if not match:
            return None
            
        cmd_name = match.group(1)
        args_str = match.group(2)
        
        command = self._commands.get(cmd_name)
        if not command:
            return {"error": f"未知命令: /{cmd_name}"}
            
        try:
            # 解析参数
            args = self._parse_args(args_str, command.args_schema)
            
            # 执行命令
            result = command.handler(args)
            return result
            
        except Exception as e:
            logger.error(f"[SlashCommand] 命令执行失败 /{cmd_name}: {e}")
            return {"error": str(e)}
    
    def _parse_args(self, args_str: str, schema: Dict) -> Dict[str, Any]:
        """解析命令参数"""
        args = {}
        if not args_str:
            return args
            
        # 简单参数解析（空格分隔）
        parts = args_str.split()
        for i, (key, type_hint) in enumerate(schema.items()):
            if i < len(parts):
                try:
                    args[key] = type_hint(parts[i])
                except (ValueError, TypeError):
                    args[key] = parts[i]
                    
        return args
    
    def list_commands(self, category: Optional[str] = None) -> List[Dict[str, str]]:
        """列出所有命令（可按类别过滤）"""
        commands = []
        for cmd in self._commands.values():
            if category and cmd.category != category:
                continue
            commands.append({
                "command": f"/{cmd.command}",
                "description": cmd.description,
                "category": cmd.category,
            })
        return commands
    
    def is_slash_command(self, text: str) -> bool:
        """检查输入是否是斜杠命令"""
        return bool(re.match(r'^/\w+', text.strip()))
