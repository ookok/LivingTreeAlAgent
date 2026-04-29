"""
工具注册表 & 分发器
参考 hermes-agent 的 toolsets.py + model_tools.py 架构
"""

import json
import re
from typing import Callable, Any
from dataclasses import dataclass, field


# ── 工具定义 ────────────────────────────────────────────────────────

@dataclass
class ToolDef:
    """工具定义（对应模型 API 的 tools schema）"""
    name: str
    description: str
    parameters: dict        # JSON Schema
    handler: Callable[..., Any] = field(repr=False)
    toolset: str = "core"   # 所属工具集


class ToolRegistry:
    """
    全局工具注册表
    所有工具通过 register() 自注册
    """

    _instance: "ToolRegistry | None" = None
    _tools: dict[str, ToolDef] = {}
    _toolsets: dict[str, set[str]] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def register(
        cls,
        name: str,
        description: str,
        parameters: dict,
        handler: Callable,
        toolset: str = "core",
    ):
        """注册工具"""
        cls._tools[name] = ToolDef(
            name=name,
            description=description,
            parameters=parameters,
            handler=handler,
            toolset=toolset,
        )
        cls._toolsets.setdefault(toolset, set()).add(name)

    @classmethod
    def get(cls, name: str) -> ToolDef | None:
        return cls._tools.get(name)

    @classmethod
    def get_all_names(cls) -> list[str]:
        return list(cls._tools.keys())

    @classmethod
    def get_by_toolset(cls, toolset: str) -> list[ToolDef]:
        names = cls._toolsets.get(toolset, set())
        return [cls._tools[n] for n in names if n in cls._tools]

    @classmethod
    def get_all_tools(cls, enabled: list[str] | None = None) -> list[ToolDef]:
        """获取所有工具（可选工具集过滤）"""
        if not enabled:
            return list(cls._tools.values())
        result = []
        for ts in enabled:
            result.extend(cls.get_by_toolset(ts))
        return result

    @classmethod
    def to_openai_schema(cls, tools: list[ToolDef]) -> list[dict]:
        """转换为 OpenAI tools schema"""
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                }
            }
            for t in tools
        ]


# ── 工具调用执行器 ─────────────────────────────────────────────────

class ToolDispatcher:
    """
    工具调用分发器
    参考 hermes-agent 的 handle_function_call 逻辑
    """

    def __init__(self, context: dict):
        self.context = context  # 执行上下文（消息、配置等）

    def dispatch(self, tool_name: str, arguments: dict) -> dict:
        """分发工具调用"""
        tool = ToolRegistry.get(tool_name)
        if not tool:
            return {"success": False, "error": f"未知工具: {tool_name}"}

        # 类型强制转换（参考 hermes-agent coerce_tool_args）
        args = self._coerce_args(tool_name, tool.parameters, arguments)

        try:
            result = tool.handler(self.context, **args)
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def _coerce_args(name: str, schema: dict, args: dict) -> dict:
        """强制转换参数类型（str→int/float/bool）"""
        props = schema.get("properties", {})
        required = schema.get("required", [])
        result = {}

        for key, value in args.items():
            prop = props.get(key, {})
            param_type = prop.get("type", "string")

            # 空值处理
            if value is None:
                continue

            # 强制转换
            if param_type == "integer" and isinstance(value, str):
                try:
                    value = int(value)
                except (ValueError, TypeError):
                    pass
            elif param_type == "number" and isinstance(value, str):
                try:
                    value = float(value)
                except (ValueError, TypeError):
                    pass
            elif param_type == "boolean" and isinstance(value, str):
                value = value.lower() in ("true", "1", "yes")
            elif param_type == "array" and isinstance(value, str):
                try:
                    value = json.loads(value)
                except Exception:
                    pass

            result[key] = value

        return result


# ── 工具注册装饰器 ─────────────────────────────────────────────────

def tool(
    name: str,
    description: str,
    parameters: dict,
    toolset: str = "core",
):
    """工具注册装饰器"""
    def decorator(func: Callable):
        ToolRegistry.register(name, description, parameters, func, toolset)
        return func
    return decorator


# ── 预定义工具 schemas ────────────────────────────────────────────

SCHEMA = {
    # 文件操作
    "read_file": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件路径"},
            "limit": {"type": "integer", "description": "最多读取行数"},
            "offset": {"type": "integer", "description": "从第几行开始"},
        },
        "required": ["path"],
    },
    "write_file": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件路径"},
            "content": {"type": "string", "description": "文件内容"},
        },
        "required": ["path", "content"],
    },
    "patch": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件路径"},
            "old_str": {"type": "string", "description": "待替换的文本"},
            "new_str": {"type": "string", "description": "替换后的文本"},
        },
        "required": ["path", "old_str", "new_str"],
    },
    "search_files": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "搜索目录"},
            "pattern": {"type": "string", "description": "正则或关键词"},
            "file_pattern": {"type": "string", "description": "文件通配符（如 *.py）"},
        },
        "required": ["path", "pattern"],
    },
    "list_dir": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "目录路径"},
        },
        "required": ["path"],
    },

    # 写作工具
    "create_document": {
        "type": "object",
        "properties": {
            "project_name": {"type": "string", "description": "项目名称"},
            "title": {"type": "string", "description": "文档标题"},
            "content": {"type": "string", "description": "文档内容（Markdown）"},
        },
        "required": ["project_name", "title", "content"],
    },
    "edit_document": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文档路径"},
            "old_str": {"type": "string", "description": "待替换文本"},
            "new_str": {"type": "string", "description": "替换后文本"},
        },
        "required": ["path", "old_str", "new_str"],
    },
    "list_documents": {
        "type": "object",
        "properties": {
            "project_name": {"type": "string", "description": "项目名称"},
        },
        "required": ["project_name"],
    },
    "read_document": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文档路径"},
        },
        "required": ["path"],
    },

    # 项目工具
    "list_projects": {
        "type": "object",
        "properties": {},
    },
    "create_project": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "项目名称"},
            "description": {"type": "string", "description": "项目描述"},
        },
        "required": ["name"],
    },
    "switch_project": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "项目名称"},
        },
        "required": ["name"],
    },

    # 模型工具
    "list_models": {
        "type": "object",
        "properties": {},
    },
    "load_model": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "模型名称"},
        },
        "required": ["name"],
    },
    "unload_model": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "模型名称"},
        },
        "required": ["name"],
    },

    # 系统工具
    "terminal": {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "终端命令"},
            "cwd": {"type": "string", "description": "工作目录"},
        },
        "required": ["command"],
    },
}
