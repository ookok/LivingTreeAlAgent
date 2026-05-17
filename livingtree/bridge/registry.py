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


# ═══════════════════════════════════════════════════════════════
# Pre-configured capability tool loaders
# These lazy-loaders replace direct `from ..capability.xxx import`
# ═══════════════════════════════════════════════════════════════

def _register_capability_tools():
    """Register all known capability tools as lazy loaders.

    This function is called once to populate the registry with
    capability tools. treellm modules then use registry.get(name)
    instead of direct imports.
    """
    reg = ToolRegistry.instance()

    # Browser tools
    reg.register("browser_agent", loader=lambda: _lazy_import("livingtree.capability.browser_agent", "get_browser_agent"))
    reg.register("browser_tools", loader=lambda: _lazy_import("livingtree.capability.browser_tools", "get_browser_tools"))

    # Search tools
    reg.register("web_search", loader=lambda: _lazy_import("livingtree.capability.llm_web_search", "web_search"))
    reg.register("bing_search", loader=lambda: _lazy_import("livingtree.capability.bing_search", "BingSearch"))

    # Document tools
    reg.register("doc_engine", loader=lambda: _lazy_import("livingtree.capability.doc_engine", "DocEngine"))
    reg.register("tool_market", loader=lambda: _lazy_import("livingtree.capability.tool_market", "get_tool_market"))

    # Task tools
    reg.register("overnight_task", loader=lambda: _lazy_import("livingtree.capability.overnight_task", "get_overnight_task"))
    reg.register("skill_factory", loader=lambda: _lazy_import("livingtree.capability.skill_factory", "get_skill_factory"))

    # Analysis tools
    reg.register("tabular_reasoner", loader=lambda: _lazy_import("livingtree.capability.tabular_reasoner", "get_tabular_reasoner"))
    reg.register("code_graph", loader=lambda: _lazy_import("livingtree.capability.code_graph", "CodeGraph"))
    reg.register("ast_parser", loader=lambda: _lazy_import("livingtree.capability.ast_parser", "ASTParser"))

    # Map tools
    reg.register("tianditu", loader=lambda: _lazy_import("livingtree.capability.tianditu", "TiandituAPI"))


    # LLM services (from treellm)
    reg.register("treellm_core", loader=lambda: _lazy_import("livingtree.treellm.core", "TreeLLM"))
    reg.register("eia_models", loader=lambda: _lazy_import("livingtree.treellm.eia_models", "EIAEngine"))
    reg.register("classifier", loader=lambda: _lazy_import("livingtree.treellm.classifier", "get_router"))
    reg.register("context_moe", loader=lambda: _lazy_import("livingtree.treellm.context_moe", "get_context_moe"))
    reg.register("living_store", loader=lambda: _lazy_import("livingtree.treellm.living_store", "get_living_store"))
    reg.register("cache_director", loader=lambda: _lazy_import("livingtree.treellm.cache_director", "get_cache_director"))

    return reg


def _lazy_import(module_path: str, attr_name: str):
    """Lazy import helper — imports only when first accessed."""
    import importlib
    mod = importlib.import_module(module_path)
    obj = getattr(mod, attr_name)
    if callable(obj) and not isinstance(obj, type):
        return obj()  # factory function
    return obj() if callable(obj) else obj


# Auto-register on first import of bridge.registry
_register_capability_tools()
