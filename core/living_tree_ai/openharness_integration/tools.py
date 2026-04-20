"""OpenHarness 工具系统集成"""

import os
import subprocess
import asyncio
from typing import Dict, Any, Callable, List, Optional
from dataclasses import dataclass


@dataclass
class Tool:
    """工具定义"""
    name: str
    description: str
    func: Callable
    parameters: Dict[str, Any] = None


class ToolSystem:
    """OpenHarness 工具系统"""
    
    def __init__(self):
        """初始化工具系统"""
        self.tools: Dict[str, Tool] = {}
        self._register_builtin_tools()
    
    def _register_builtin_tools(self):
        """注册内置工具"""
        # 文件操作工具
        self.register_tool(
            name="read_file",
            description="读取文件内容",
            func=self._read_file,
            parameters={
                "file_path": "string",
                "description": "文件路径"
            }
        )
        
        self.register_tool(
            name="write_file",
            description="写入文件内容",
            func=self._write_file,
            parameters={
                "file_path": "string",
                "content": "string",
                "description": "文件路径和内容"
            }
        )
        
        # 系统操作工具
        self.register_tool(
            name="run_command",
            description="执行系统命令",
            func=self._run_command,
            parameters={
                "command": "string",
                "description": "要执行的命令"
            }
        )
        
        # 目录操作工具
        self.register_tool(
            name="list_directory",
            description="列出目录内容",
            func=self._list_directory,
            parameters={
                "directory": "string",
                "description": "目录路径"
            }
        )
    
    def register_tool(
        self,
        name: str,
        description: str,
        func: Callable,
        parameters: Dict[str, Any] = None
    ):
        """注册工具"""
        tool = Tool(
            name=name,
            description=description,
            func=func,
            parameters=parameters
        )
        self.tools[name] = tool
        print(f"[ToolSystem] 注册工具: {name} - {description}")
    
    async def execute_tool(self, tool_name: str, **kwargs) -> Any:
        """执行工具"""
        if tool_name not in self.tools:
            raise ValueError(f"Tool not found: {tool_name}")
        
        tool = self.tools[tool_name]
        try:
            result = await tool.func(**kwargs)
            print(f"[ToolSystem] 工具执行成功: {tool_name}")
            return result
        except Exception as e:
            print(f"[ToolSystem] 工具执行失败 {tool_name}: {e}")
            raise
    
    def get_tool(self, tool_name: str) -> Optional[Tool]:
        """获取工具"""
        return self.tools.get(tool_name)
    
    def get_all_tools(self) -> List[Dict[str, Any]]:
        """获取所有工具"""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters
            }
            for tool in self.tools.values()
        ]
    
    # 内置工具实现
    async def _read_file(self, file_path: str) -> str:
        """读取文件内容"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return content
    
    async def _write_file(self, file_path: str, content: str) -> str:
        """写入文件内容"""
        # 确保目录存在
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return f"文件写入成功: {file_path}"
    
    async def _run_command(self, command: str) -> str:
        """执行系统命令"""
        try:
            result = subprocess.run(
                command, 
                shell=True, 
                capture_output=True, 
                text=True, 
                timeout=30
            )
            
            if result.returncode == 0:
                return result.stdout
            else:
                raise Exception(f"命令执行失败: {result.stderr}")
        except Exception as e:
            raise Exception(f"命令执行出错: {str(e)}")
    
    async def _list_directory(self, directory: str) -> List[str]:
        """列出目录内容"""
        if not os.path.exists(directory):
            raise FileNotFoundError(f"目录不存在: {directory}")
        
        if not os.path.isdir(directory):
            raise ValueError(f"不是目录: {directory}")
        
        return os.listdir(directory)
