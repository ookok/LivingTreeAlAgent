"""
工具定义框架
============

定义 AI 可调用的工具接口，包括：
1. 工具元数据（名称、描述、参数）
2. 工具执行结果（成功/失败/需要确认）
3. 工具分类（文件/执行/搜索/Git）

设计原则：
- 声明式：工具定义与执行分离
- 类型安全：使用 dataclass 和 enum
- 可扩展：易于添加新工具
- 可追踪：每个调用都有唯一 ID

使用方式:
    from core.smart_writing.tool_definition import (
        Tool, ToolCall, ToolResult, ToolRegistry
    )

    # 定义工具
    @ToolRegistry.register
    def read_file(path: str, lines: int = 100) -> ToolResult:
        ...

    # 调用工具
    registry = ToolRegistry()
    result = registry.execute("read_file", path="/tmp/test.py")
"""

import os
import re
import json
import uuid
import time
import hashlib
from typing import Dict, List, Optional, Any, Callable, Set, Type
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod


# ============== 工具分类 ==============

class ToolCategory(Enum):
    """工具分类"""
    FILE = "file"              # 文件操作
    EXECUTION = "execution"    # 代码执行
    SEARCH = "search"          # 搜索替换
    GIT = "git"                # Git 操作
    SYSTEM = "system"          # 系统操作
    CUSTOM = "custom"          # 自定义


class ToolStatus(Enum):
    """工具执行状态"""
    PENDING = "pending"        # 待执行
    RUNNING = "running"        # 执行中
    SUCCESS = "success"       # 成功
    FAILED = "failed"         # 失败
    CONFIRM = "confirm"        # 需要确认
    CANCELLED = "cancelled"    # 已取消
    TIMEOUT = "timeout"        # 超时


# ============== 数据类 ==============

@dataclass
class ToolParameter:
    """工具参数定义"""
    name: str
    type: str  # "str", "int", "bool", "list", "dict"
    description: str
    required: bool = True
    default: Any = None
    pattern: Optional[str] = None  # 正则约束
    enum: Optional[List[str]] = None  # 枚举值


@dataclass
class Tool:
    """工具元数据"""
    name: str
    description: str
    category: ToolCategory
    parameters: List[ToolParameter] = field(default_factory=list)
    returns: str = ""  # 返回值描述
    examples: List[Dict[str, Any]] = field(default_factory=list)  # 使用示例
    danger: bool = False  # 危险操作标记
    confirm_required: bool = False  # 是否需要确认
    readonly: bool = False  # 只读操作
    tags: Set[str] = field(default_factory=set)  # 标签

    def to_openai_schema(self) -> Dict[str, Any]:
        """转换为 OpenAI Function Calling 格式"""
        properties = {}
        required = []

        for p in self.parameters:
            prop = {
                "type": p.type,
                "description": p.description,
            }
            if p.enum:
                prop["enum"] = p.enum
            if p.pattern:
                prop["pattern"] = p.pattern
            if p.default is not None:
                prop["default"] = p.default

            properties[p.name] = prop
            if p.required:
                required.append(p.name)

        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            }
        }


@dataclass
class ToolCall:
    """工具调用请求"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    tool_name: str = ""
    arguments: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    status: ToolStatus = ToolStatus.PENDING
    user_confirmed: bool = False  # 用户是否确认

    def __str__(self) -> str:
        args_str = ", ".join(f"{k}={repr(v)}" for k, v in self.arguments.items())
        return f"ToolCall({self.tool_name}, {args_str})"


@dataclass
class ToolResult:
    """工具执行结果"""
    call_id: str
    tool_name: str
    status: ToolStatus
    result: Any = None
    error: Optional[str] = None
    message: str = ""
    execution_time: float = 0.0
    timestamp: float = field(default_factory=time.time)
    output_preview: Optional[str] = None  # 输出预览（截断大输出）

    def __str__(self) -> str:
        if self.status == ToolStatus.SUCCESS:
            preview = self.output_preview or str(self.result)
            if len(preview) > 200:
                preview = preview[:200] + "..."
            return f"✓ {self.tool_name}: {preview}"
        else:
            return f"✗ {self.tool_name}: {self.error or self.message}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "call_id": self.call_id,
            "tool_name": self.tool_name,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "message": self.message,
            "execution_time": self.execution_time,
            "output_preview": self.output_preview,
        }

    @property
    def is_success(self) -> bool:
        return self.status == ToolStatus.SUCCESS

    @property
    def needs_confirmation(self) -> bool:
        return self.status == ToolStatus.CONFIRM


# ============== 工具注册表 ==============

class ToolRegistry:
    """
    工具注册表

    管理所有可用工具，支持注册、查找、执行。
    """

    def __init__(self):
        self._tools: Dict[str, Tool] = {}
        self._handlers: Dict[str, Callable] = {}
        self._categories: Dict[ToolCategory, List[str]] = {
            cat: [] for cat in ToolCategory
        }

    def register(
        self,
        name: str,
        description: str,
        category: ToolCategory,
        parameters: Optional[List[ToolParameter]] = None,
        returns: str = "",
        danger: bool = False,
        confirm_required: bool = False,
        readonly: bool = False,
        tags: Optional[Set[str]] = None,
    ) -> Callable:
        """
        装饰器注册工具

        Example:
            @registry.register(
                name="read_file",
                description="读取文件内容",
                category=ToolCategory.FILE,
            )
            def read_file(path: str, lines: int = 100):
                ...
        """
        def decorator(func: Callable) -> Callable:
            tool = Tool(
                name=name,
                description=description,
                category=category,
                parameters=parameters or [],
                returns=returns,
                danger=danger,
                confirm_required=confirm_required,
                readonly=readonly,
                tags=tags or set(),
            )
            self._tools[name] = tool
            self._handlers[name] = func
            self._categories[category].append(name)
            return func
        return decorator

    def register_tool(self, tool: Tool, handler: Callable):
        """手动注册工具"""
        self._tools[tool.name] = tool
        self._handlers[tool.name] = handler
        self._categories[tool.category].append(tool.name)

    def get_tool(self, name: str) -> Optional[Tool]:
        """获取工具元数据"""
        return self._tools.get(name)

    def list_tools(
        self,
        category: Optional[ToolCategory] = None,
        tags: Optional[Set[str]] = None,
        readonly_only: bool = False,
    ) -> List[Tool]:
        """列出工具"""
        tools = list(self._tools.values())

        if category:
            tools = [t for t in tools if t.category == category]

        if tags:
            tools = [t for t in tools if t.tags & tags]

        if readonly_only:
            tools = [t for t in tools if t.readonly]

        return tools

    def get_tools_for_llm(self) -> List[Dict[str, Any]]:
        """获取适合 LLM 的工具列表"""
        return [t.to_openai_schema() for t in self._tools.values()]

    def execute(
        self,
        name: str,
        arguments: Dict[str, Any],
        call_id: Optional[str] = None,
    ) -> ToolResult:
        """执行工具"""
        start_time = time.time()

        # 获取工具
        tool = self._tools.get(name)
        if not tool:
            return ToolResult(
                call_id=call_id or str(uuid.uuid4())[:8],
                tool_name=name,
                status=ToolStatus.FAILED,
                error=f"Tool '{name}' not found",
            )

        # 获取处理器
        handler = self._handlers.get(name)
        if not handler:
            return ToolResult(
                call_id=call_id or str(uuid.uuid4())[:8],
                tool_name=name,
                status=ToolStatus.FAILED,
                error=f"Handler for '{name}' not found",
            )

        # 验证参数
        for param in tool.parameters:
            if param.required and param.name not in arguments:
                return ToolResult(
                    call_id=call_id or str(uuid.uuid4())[:8],
                    tool_name=name,
                    status=ToolStatus.FAILED,
                    error=f"Missing required parameter: {param.name}",
                )

        # 执行
        try:
            result = handler(**arguments)
            execution_time = time.time() - start_time

            # 处理返回结果
            if isinstance(result, ToolResult):
                result.call_id = call_id or result.call_id
                result.execution_time = execution_time
                return result

            return ToolResult(
                call_id=call_id or str(uuid.uuid4())[:8],
                tool_name=name,
                status=ToolStatus.SUCCESS,
                result=result,
                execution_time=execution_time,
                output_preview=str(result)[:500] if result else None,
            )

        except Exception as e:
            return ToolResult(
                call_id=call_id or str(uuid.uuid4())[:8],
                tool_name=name,
                status=ToolStatus.FAILED,
                error=str(e),
                execution_time=time.time() - start_time,
            )

    def execute_call(self, call: ToolCall) -> ToolResult:
        """执行工具调用"""
        return self.execute(
            name=call.tool_name,
            arguments=call.arguments,
            call_id=call.id,
        )


# ============== 全局注册表 ==============

# 全局工具注册表
GLOBAL_REGISTRY = ToolRegistry()


def register_tool(
    name: str,
    description: str,
    category: ToolCategory,
    parameters: Optional[List[ToolParameter]] = None,
    **kwargs
) -> Callable:
    """全局注册装饰器"""
    return GLOBAL_REGISTRY.register(
        name=name,
        description=description,
        category=category,
        parameters=parameters,
        **kwargs
    )


# ============== 工具调用解析 ==============

class ToolCallParser:
    """
    工具调用解析器

    将 LLM 输出解析为 ToolCall。
    支持多种格式：JSON、Markdown 代码块、自然语言。
    """

    @staticmethod
    def parse_json(text: str) -> Optional[ToolCall]:
        """从 JSON 解析"""
        # 尝试提取 JSON
        patterns = [
            r'```json\s*({\s*"tool"\s*:\s*"([^"]+)".+?})\s*```',
            r'{\s*"tool"\s*:\s*"([^"]+)".+?"arguments"\s*:\s*({.+?})\s*}',
            r'```\s*({\s*"name"\s*:\s*"([^"]+)".+?})\s*```',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(1))
                    tool_name = data.get("tool") or data.get("name")
                    arguments = data.get("arguments") or data.get("args") or {}
                    return ToolCall(
                        tool_name=tool_name,
                        arguments=arguments,
                    )
                except json.JSONDecodeError:
                    continue
        return None

    @staticmethod
    def parse_natural_language(text: str) -> List[ToolCall]:
        """从自然语言解析（简单实现）"""
        calls = []

        # 读取文件
        read_pattern = r'读取\s*(?:文件\s*)?["\']?([^"\'()]+)["\']?|open\s+["\']?([^"\'()]+)["\']?|cat\s+(\S+)'
        for match in re.finditer(read_pattern, text):
            path = match.group(1) or match.group(2) or match.group(3)
            if path:
                calls.append(ToolCall(
                    tool_name="read_file",
                    arguments={"path": path.strip()},
                ))

        # 写入文件
        write_pattern = r'写入\s*["\']?([^"\'()]+)["\']?|write\s+["\']?([^"\'()]+)["\']?'
        for match in re.finditer(write_pattern, text):
            path = match.group(1) or match.group(2)
            if path:
                calls.append(ToolCall(
                    tool_name="write_file",
                    arguments={"path": path.strip()},
                ))

        # 执行命令
        exec_pattern = r'(?:运行|执行|run)\s+(?:命令\s*)?["\']?([^"\'()]+)["\']?'
        for match in re.finditer(exec_pattern, text):
            cmd = match.group(1)
            if cmd:
                calls.append(ToolCall(
                    tool_name="execute_command",
                    arguments={"command": cmd.strip()},
                ))

        return calls


# ============== 导出 ==============

__all__ = [
    # 枚举
    'ToolCategory',
    'ToolStatus',
    # 数据类
    'ToolParameter',
    'Tool',
    'ToolCall',
    'ToolResult',
    # 注册表
    'ToolRegistry',
    'GLOBAL_REGISTRY',
    'register_tool',
    # 解析器
    'ToolCallParser',
]
