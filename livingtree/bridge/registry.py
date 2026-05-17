"""Tool registry — single source of truth for tool discovery.

Both treellm and capability use this registry instead of importing each other.
"""

from __future__ import annotations

from typing import Any


class ToolRegistry:
    """Central tool registry with lazy loading."""

    _instance: ToolRegistry | None = None

    @classmethod
    def instance(cls) -> ToolRegistry:
        if cls._instance is None:
            cls._instance = ToolRegistry()
        return cls._instance

    def __init__(self):
        self._tools: dict[str, Any] = {}
        self._tool_descriptions: dict[str, str] = {}
        self._lazy_loaders: dict[str, callable] = {}

    def register(self, name: str, tool: Any = None, description: str = "",
                 loader: callable = None) -> None:
        """Register a tool or a lazy loader."""
        if tool is not None:
            self._tools[name] = tool
        if description:
            self._tool_descriptions[name] = description
        if loader is not None:
            self._lazy_loaders[name] = loader

    def get(self, name: str) -> Any | None:
        """Get a tool, loading lazily if needed."""
        if name in self._tools:
            return self._tools[name]
        if name in self._lazy_loaders:
            tool = self._lazy_loaders[name]()
            self._tools[name] = tool
            return tool
        return None

    def list_tools(self) -> list[str]:
        return list(self._tools.keys()) + list(self._lazy_loaders.keys())

    def get_descriptions(self) -> dict[str, str]:
        return dict(self._tool_descriptions)

    def stats(self) -> dict:
        return {
            "loaded": len(self._tools),
            "lazy": len(self._lazy_loaders),
            "total": len(self._tools) + len(self._lazy_loaders),
        }


def get_tool_registry() -> ToolRegistry:
    return ToolRegistry.instance()


__all__ = ["ToolRegistry", "get_tool_registry"]
