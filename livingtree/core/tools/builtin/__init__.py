"""
LivingTree Built-in Tools
=========================

内置工具注册 — 文件操作、搜索、Web抓取、Git操作等。
"""

from .file_tools import register_file_tools
from .web_tools import register_web_tools
from .git_tools import register_git_tools


def register_all_builtin_tools():
    register_file_tools()
    register_web_tools()
    register_git_tools()


__all__ = ["register_all_builtin_tools", "register_file_tools", "register_web_tools", "register_git_tools"]
