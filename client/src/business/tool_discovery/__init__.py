"""
工具发现引擎 (Tool Discovery Engine)

核心功能：
1. 搜索外部工具 - PyPI/GitHub搜索
2. 自动封装 - 生成wrapper
3. 代码编译 - 创建高性能模块
4. 工具注册 - 注册为Skill

实现Tool Morphogenesis（工具形态发生）能力。
"""
from .tool_discovery import ToolDiscoveryEngine, ToolInfo, ToolSearchResult

__all__ = [
    "ToolDiscoveryEngine",
    "ToolInfo",
    "ToolSearchResult",
]