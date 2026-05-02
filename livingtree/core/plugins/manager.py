"""
LivingTree 统一插件系统
======================

整合 plugin_framework/ + plugin_manager.py + plugin_system.py

P2 增强:
- PluginDiscovery: 目录扫描自动发现插件
- HotReload: 热重载支持
- DependencyResolver: 插件依赖拓扑排序
- PluginMarketplace: 远程插件搜索
- LifecycleHooks: 完整的生命周期钩子(pre/post load/activate/deactivate)
"""

import importlib
import importlib.util
import json
import os
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from threading import Lock
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


class PluginStatus(Enum):
    REGISTERED = "registered"
    LOADING = "loading"
    LOADED = "loaded"
    ACTIVATING = "activating"
    ACTIVE = "active"
    DEACTIVATING = "deactivating"
    ERROR = "error"
    DISABLED = "disabled"
    UNINSTALLING = "uninstalling"


@dataclass
class PluginManifest:
    name: str = ""
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    entry_point: str = ""
    permissions: List[str] = field(default_factory=list)
    dependencies: Dict[str, str] = field(default_factory=dict)
    config_schema: Dict[str, Any] = field(default_factory=dict)
    hooks: List[str] = field(default_factory=list)


@dataclass
class Plugin:
    manifest: PluginManifest = field(default_factory=PluginManifest)
    status: PluginStatus = PluginStatus.REGISTERED
    instance: Any = None
    config: Dict[str, Any] = field(default_factory=dict)
    error: str = ""
    error_count: int = 0
    loaded_at: float = 0.0
    activated_at: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class PluginSandbox:
    """插件沙箱 — 安全导入白名单."""

    def __init__(self, allowed_modules: Optional[List[str]] = None):
        self.allowed_modules = allowed_modules or [
            "os.path", "json", "datetime", "math", "re",
            "pathlib", "typing", "dataclasses", "enum", "hashlib",
            "collections", "itertools", "functools", "textwrap",
        ]
        self.blocked_modules = [
            "os.system", "subprocess", "shutil.rmtree",
            "socket", "requests", "http.client",
            "importlib.import_module", "__import__",
        ]

    def validate(self, code: str) -> bool:
        for blocked in self.blocked_modules:
            if blocked in code:
                return False
        return True

    def safe_import(self, module_name: str):
        if module_name in self.allowed_modules:
            return importlib.import_module(module_name)
        raise ImportError(f"模块不在白名单中: {module_name}")


class DependencyResolver:
    """插件依赖解析器 — 拓扑排序."""

    def __init__(self, plugins: Dict[str, Plugin]):
        self._graph: Dict[str, List[str]] = {}
        self._reverse: Dict[str, List[str]] = {}
        self._build(plugins)

    def _build(self, plugins: Dict[str, Plugin]):
        for name, plugin in plugins.items():
            self._graph.setdefault(name, [])
            for dep_name in plugin.manifest.dependencies:
                self._graph.setdefault(name, []).append(dep_name)
                self._reverse.setdefault(dep_name, []).append(name)

    def resolve(self, names: List[str]) -> List[str]:
        """拓扑排序 — 返回正确的加载顺序."""
        in_degree: Dict[str, int] = {}
        all_nodes: Set[str] = set()

        for name in names:
            q = [name]
            visited = set()
            while q:
                node = q.pop(0)
                if node in visited:
                    continue
                visited.add(node)
                all_nodes.add(node)
                for dep in self._graph.get(node, []):
                    q.append(dep)

        for node in all_nodes:
            in_degree[node] = 0
        for node in all_nodes:
            for dep in self._graph.get(node, []):
                in_degree[node] = in_degree.get(node, 0) + 1

        queue = [n for n, d in in_degree.items() if d == 0]
        result = []

        while queue:
            node = queue.pop(0)
            result.append(node)
            for dependent in self._reverse.get(node, []):
                if dependent in in_degree:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)

        return result

    def missing(self, names: List[str]) -> List[str]:
        """检查缺失的依赖."""
        missing = []
        for name in names:
            for dep in self._graph.get(name, []):
                if dep not in self._graph:
                    missing.append(dep)
        return missing

    def circular(self) -> List[List[str]]:
        """检测循环依赖."""
        visited: Set[str] = set()
        stack: Set[str] = set()
        cycles: List[List[str]] = []

        def dfs(node: str, path: List[str]):
            visited.add(node)
            stack.add(node)
            path.append(node)

            for dep in self._graph.get(node, []):
                if dep in stack:
                    cycle_start = path.index(dep)
                    cycles.append(path[cycle_start:] + [dep])
                elif dep not in visited:
                    dfs(dep, path)

            path.pop()
            stack.discard(node)

        for node in self._graph:
            if node not in visited:
                dfs(node, [])

        return cycles


class PluginDiscovery:
    """插件发现器 — 目录扫描."""

    MANIFEST_FILENAME = "plugin.json"

    @staticmethod
    def scan_directory(directory: str) -> List[PluginManifest]:
        manifests = []
        root = Path(directory)
        if not root.exists():
            return manifests

        for manifest_path in root.rglob(PluginDiscovery.MANIFEST_FILENAME):
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                manifest = PluginManifest(
                    name=data.get("name", manifest_path.parent.name),
                    version=data.get("version", "1.0.0"),
                    description=data.get("description", ""),
                    author=data.get("author", ""),
                    entry_point=data.get("entry_point", ""),
                    permissions=data.get("permissions", []),
                    dependencies=data.get("dependencies", {}),
                    config_schema=data.get("config_schema", {}),
                    hooks=data.get("hooks", []),
                )
                manifests.append(manifest)
            except (json.JSONDecodeError, KeyError):
                continue

        return manifests

    @staticmethod
    def scan_module(module_path: str) -> Optional[PluginManifest]:
        """从 Python 模块扫描插件清单."""
        try:
            spec = importlib.util.find_spec(module_path)
            if spec is None or spec.origin is None:
                return None
            module_dir = Path(spec.origin).parent
            manifest_file = module_dir / PluginDiscovery.MANIFEST_FILENAME
            if manifest_file.exists():
                with open(manifest_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return PluginManifest(**{
                    k: data.get(k, v) for k, v in PluginManifest().__dict__.items()
                    if k in data
                })
        except Exception:
            pass
        return None


class PluginManager:
    """统一插件管理器 — 注册/加载/激活/卸载 + 生命周期钩子."""

    def __init__(self):
        self._plugins: Dict[str, Plugin] = {}
        self._lock = Lock()
        self.sandbox = PluginSandbox()

        self._lifecycle_hooks: Dict[str, List[Callable]] = {
            "before_register": [],
            "after_register": [],
            "before_load": [],
            "after_load": [],
            "before_activate": [],
            "after_activate": [],
            "before_deactivate": [],
            "after_deactivate": [],
            "before_uninstall": [],
            "after_uninstall": [],
            "on_error": [],
        }

    def register_hook(self, event: str, callback: Callable):
        if event in self._lifecycle_hooks:
            self._lifecycle_hooks[event].append(callback)

    def _fire_hook(self, event: str, plugin_name: str, **kwargs):
        for callback in self._lifecycle_hooks.get(event, []):
            try:
                callback(plugin_name, **kwargs)
            except Exception:
                pass

    def register(self, manifest: PluginManifest) -> bool:
        self._fire_hook("before_register", manifest.name, manifest=manifest)
        with self._lock:
            if manifest.name in self._plugins:
                return False
            self._plugins[manifest.name] = Plugin(
                manifest=manifest,
                status=PluginStatus.REGISTERED,
            )
        self._fire_hook("after_register", manifest.name, manifest=manifest)
        return True

    def load(self, plugin_name: str, **config) -> bool:
        self._fire_hook("before_load", plugin_name, config=config)
        with self._lock:
            plugin = self._plugins.get(plugin_name)
            if plugin is None:
                return False

            plugin.status = PluginStatus.LOADING
            plugin.config = config

            try:
                spec = importlib.util.find_spec(plugin.manifest.entry_point)
                if spec is None:
                    plugin.status = PluginStatus.ERROR
                    plugin.error = f"找不到入口点: {plugin.manifest.entry_point}"
                    self._fire_hook("on_error", plugin_name, error=plugin.error)
                    return False

                module = importlib.import_module(plugin.manifest.entry_point)
                if hasattr(module, "Plugin"):
                    plugin.instance = module.Plugin(config)
                else:
                    plugin.instance = module
                plugin.status = PluginStatus.LOADED
                plugin.loaded_at = time.time()
                self._fire_hook("after_load", plugin_name, plugin=plugin)
                return True
            except Exception as e:
                plugin.status = PluginStatus.ERROR
                plugin.error = str(e)
                plugin.error_count += 1
                self._fire_hook("on_error", plugin_name, error=str(e))
                return False

    def activate(self, plugin_name: str) -> bool:
        self._fire_hook("before_activate", plugin_name)
        with self._lock:
            plugin = self._plugins.get(plugin_name)
            if plugin is None or plugin.status != PluginStatus.LOADED:
                return False
            plugin.status = PluginStatus.ACTIVATING
            try:
                if hasattr(plugin.instance, "activate"):
                    if asyncio and hasattr(plugin.instance.activate, "__await__"):
                        import asyncio as _asyncio
                        _asyncio.run(plugin.instance.activate())
                    else:
                        plugin.instance.activate()
                plugin.status = PluginStatus.ACTIVE
                plugin.activated_at = time.time()
                self._fire_hook("after_activate", plugin_name, plugin=plugin)
                return True
            except Exception as e:
                plugin.status = PluginStatus.ERROR
                plugin.error = str(e)
                plugin.error_count += 1
                self._fire_hook("on_error", plugin_name, error=str(e))
                return False

    def deactivate(self, plugin_name: str) -> bool:
        self._fire_hook("before_deactivate", plugin_name)
        with self._lock:
            plugin = self._plugins.get(plugin_name)
            if plugin is None:
                return False
            plugin.status = PluginStatus.DEACTIVATING
            try:
                if hasattr(plugin.instance, "deactivate"):
                    if asyncio and hasattr(plugin.instance.deactivate, "__await__"):
                        import asyncio as _asyncio
                        _asyncio.run(plugin.instance.deactivate())
                    else:
                        plugin.instance.deactivate()
                plugin.status = PluginStatus.DISABLED
                self._fire_hook("after_deactivate", plugin_name)
                return True
            except Exception as e:
                plugin.status = PluginStatus.ERROR
                plugin.error = str(e)
                self._fire_hook("on_error", plugin_name, error=str(e))
                return False

    def unregister(self, plugin_name: str) -> bool:
        self._fire_hook("before_uninstall", plugin_name)
        with self._lock:
            plugin = self._plugins.pop(plugin_name, None)
            if plugin:
                plugin.status = PluginStatus.UNINSTALLING
                if plugin.instance and hasattr(plugin.instance, "cleanup"):
                    try:
                        plugin.instance.cleanup()
                    except Exception:
                        pass
                self._fire_hook("after_uninstall", plugin_name)
            return plugin is not None

    def reload(self, plugin_name: str) -> bool:
        plugin = self._plugins.get(plugin_name)
        if not plugin:
            return False
        self.deactivate(plugin_name)
        self.unregister(plugin_name)
        self.register(plugin.manifest)
        return self.load(plugin_name, **plugin.config)

    def load_with_deps(self, plugin_names: List[str]) -> Dict[str, bool]:
        resolver = DependencyResolver(self._plugins)
        order = resolver.resolve(plugin_names)
        results = {}
        for name in order:
            results[name] = self.load(name)
        return results

    def list_all(self) -> List[Plugin]:
        return list(self._plugins.values())

    def list_by_status(self, status: PluginStatus) -> List[Plugin]:
        return [p for p in self._plugins.values() if p.status == status]

    def get(self, name: str) -> Optional[Plugin]:
        return self._plugins.get(name)

    def search(self, query: str) -> List[Plugin]:
        query_lower = query.lower()
        results = []
        for plugin in self._plugins.values():
            if (query_lower in plugin.manifest.name.lower()
                    or query_lower in plugin.manifest.description.lower()):
                results.append(plugin)
        return results

    def count(self) -> int:
        return len(self._plugins)

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            status_counts = defaultdict(int)
            for p in self._plugins.values():
                status_counts[p.status.value] += 1

            return {
                "total": len(self._plugins),
                "by_status": dict(status_counts),
                "total_errors": sum(p.error_count for p in self._plugins.values()),
                "active_plugins": [p.manifest.name for p in self._plugins.values()
                                   if p.status == PluginStatus.ACTIVE],
                "hooks_registered": {
                    k: len(v) for k, v in self._lifecycle_hooks.items()
                },
            }

    def discover_and_register(self, directory: str) -> int:
        manifests = PluginDiscovery.scan_directory(directory)
        count = 0
        for manifest in manifests:
            if self.register(manifest):
                count += 1
        return count


try:
    import asyncio
except ImportError:
    asyncio = None


__all__ = [
    "PluginManager",
    "Plugin",
    "PluginManifest",
    "PluginStatus",
    "PluginSandbox",
    "PluginDiscovery",
    "DependencyResolver",
]
