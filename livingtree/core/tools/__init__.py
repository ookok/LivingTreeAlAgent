from .registry import (
    ToolRegistry,
    ToolDispatcher,
    ToolDef,
    SCHEMA,
    register_all_tools,
)
from .builtin import register_all_builtin_tools


class ToolCategory:
    FILE = "file"
    TERMINAL = "core"
    WEB = "web"
    CODE = "code"
    GIT = "git"


ToolInfo = ToolDef
ToolResult = ToolDef


def register_builtin_tools():
    register_all_tools()
    register_all_builtin_tools()
