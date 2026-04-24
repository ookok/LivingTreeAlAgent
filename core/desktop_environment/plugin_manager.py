# plugin_manager.py — 插件管理器
# ============================================================================
#
# 负责插件的发现、安装、卸载和生命周期管理
# 支持从 P2P 网络发现和下载插件
#
# ============================================================================

import json
import hashlib
import asyncio
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from pathlib import Path
from enum import Enum
import aiohttp

# ============================================================================
# 配置与枚举
# ============================================================================

class PluginState(Enum):
    """插件状态"""
    DISCOVERED = "discovered"       # 已发现
    DOWNLOADING = "downloading"    # 下载中
    INSTALLED = "installed"         # 已安装
    LOADING = "loading"             # 加载中
    LOADED = "loaded"               # 已加载
    FAILED = "failed"              # 加载失败
    UPDATING = "updating"           # 更新中

@dataclass
class PluginInfo:
    """插件信息"""
    id: str                          # 插件 ID
    name: str                        # 插件名称
    version: str = "1.0.0"          # 版本
    author: str = ""                 # 作者
    description: str = ""             # 描述
    icon: str = ""                   # 图标
    category: str = "general"        # 分类
    tags: List[str] = field(default_factory=list)  # 标签
    size_bytes: int = 0             # 大小
    download_url: str = ""          # 下载地址
    checksum: str = ""               # 校验和
    signature: str = ""              # 签名
    dependencies: List[str] = field(default_factory=list)  # 依赖
    min_app_version: str = ""       # 最低应用版本
    platform: str = "all"           # 平台 (windows/linux/darwin/all)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "author": self.author,
            "description": self.description,
            "icon": self.icon,
            "category": self.category,
            "tags": self.tags,
            "size_bytes": self.size_bytes,
            "download_url": self.download_url,
            "checksum": self.checksum,
            "signature": self.signature,
            "dependencies": self.dependencies,
            "min_app_version": self.min_app_version,
            "platform": self.platform,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PluginInfo":
        return cls(**data)

class PluginSecurityError(Exception):
    """插件安全异常"""
    pass

# ============================================================================
# 插件管理器
# ============================================================================

class PluginManager:
    """
    插件管理器

    职责:
    1. 从 P2P 网络发现插件
    2. 插件安装和卸载
    3. 插件签名验证
    4. 插件依赖管理
    5. 插件生命周期管理
    """

    def __init__(
        self,
        market_url: str = "https://plugins.mogoo.com/api",
        plugins_dir: Path = None
    ):
        self.market_url = market_url

        # 插件目录
        if plugins_dir is None:
            from . import _DATA_DIR
            plugins_dir = _DATA_DIR / "plugins"

        self.plugins_dir = Path(plugins_dir)
        self.plugins_dir.mkdir(parents=True, exist_ok=True)

        # 已发现插件
        self._discovered_plugins: Dict[str, PluginInfo] = {}

        # 已安装插件
        self._installed_plugins: Dict[str, PluginInfo] = {}

        # 加载的插件
        self._loaded_plugins: Dict[str, Any] = {}

        # 下载进度
        self._download_progress: Dict[str, float] = {}

        # 回调
        self._on_plugin_discovered: Optional[Callable] = None
        self._on_plugin_installed: Optional[Callable] = None
        self._on_plugin_uninstalled: Optional[Callable] = None
        self._on_download_progress: Optional[Callable] = None

        # 加载已安装插件
        self._load_installed_plugins()

    # --------------------------------------------------------------------------
    # 插件发现
    # --------------------------------------------------------------------------

    async def discover_plugins(self) -> List[PluginInfo]:
        """
        从 P2P 网络发现插件

        Returns:
            发现的插件列表
        """
        # 1. 扫描本地插件
        local_plugins = self._scan_local_plugins()

        # 2. 从 P2P 网络发现
        p2p_plugins = await self._query_p2p_market()

        # 3. 合并
        all_plugins = {**local_plugins, **p2p_plugins}
        self._discovered_plugins = all_plugins

        return list(all_plugins.values())

    async def _query_p2p_market(self) -> Dict[str, PluginInfo]:
        """查询 P2P 市场"""
        plugins = {}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.market_url}/discover",
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        for plugin_data in data.get("plugins", []):
                            plugin = PluginInfo.from_dict(plugin_data)
                            plugins[plugin.id] = plugin
        except Exception as e:
            logger.info(f"Failed to query P2P market: {e}")

        return plugins

    def _scan_local_plugins(self) -> Dict[str, PluginInfo]:
        """扫描本地插件"""
        plugins = {}

        # 扫描插件目录
        for plugin_dir in self.plugins_dir.iterdir():
            if not plugin_dir.is_dir():
                continue

            manifest_file = plugin_dir / "manifest.json"
            if manifest_file.exists():
                try:
                    with open(manifest_file, encoding="utf-8") as f:
                        data = json.load(f)
                        plugin = PluginInfo.from_dict(data)
                        plugins[plugin.id] = plugin
                except Exception:
                    continue

        return plugins

    def get_discovered_plugins(self) -> List[PluginInfo]:
        """获取已发现的插件"""
        return list(self._discovered_plugins.values())

    def get_installed_plugins(self) -> List[PluginInfo]:
        """获取已安装的插件"""
        return list(self._installed_plugins.values())

    def get_plugin(self, plugin_id: str) -> Optional[PluginInfo]:
        """获取插件信息"""
        return self._installed_plugins.get(plugin_id)

    # --------------------------------------------------------------------------
    # 插件安装
    # --------------------------------------------------------------------------

    async def install_plugin(
        self,
        plugin_id: str,
        verify_signature: bool = True
    ) -> bool:
        """
        安装插件

        Args:
            plugin_id: 插件 ID
            verify_signature: 是否验证签名

        Returns:
            是否安装成功
        """
        plugin = self._discovered_plugins.get(plugin_id)
        if not plugin:
            plugin = self._installed_plugins.get(plugin_id)
        if not plugin:
            return False

        # 检查依赖
        if not await self._check_dependencies(plugin):
            return False

        try:
            # 下载插件包
            plugin_dir = self.plugins_dir / plugin_id
            await self._download_plugin(plugin, plugin_dir)

            # 验证签名
            if verify_signature and plugin.signature:
                if not await self._verify_signature(plugin_dir, plugin):
                    raise PluginSecurityError("Plugin signature verification failed")

            # 安装
            manifest_file = plugin_dir / "manifest.json"
            with open(manifest_file, encoding="utf-8") as f:
                data = json.load(f)
                installed_plugin = PluginInfo.from_dict(data)

            self._installed_plugins[plugin_id] = installed_plugin
            self._save_installed_plugins()

            if self._on_plugin_installed:
                self._on_plugin_installed(installed_plugin)

            return True

        except Exception as e:
            logger.info(f"Failed to install plugin {plugin_id}: {e}")
            return False

    async def _download_plugin(
        self,
        plugin: PluginInfo,
        dest_dir: Path
    ):
        """下载插件"""
        dest_dir.mkdir(parents=True, exist_ok=True)
        self._download_progress[plugin.id] = 0

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    plugin.download_url,
                    timeout=aiohttp.ClientTimeout(total=300)
                ) as response:
                    if response.status != 200:
                        raise Exception(f"Download failed: {response.status}")

                    total_size = int(response.headers.get("Content-Length", 0))
                    downloaded = 0

                    with open(dest_dir / "plugin.zip", "wb") as f:
                        async for chunk in response.content.iter_chunked(8192):
                            f.write(chunk)
                            downloaded += len(chunk)

                            if total_size > 0:
                                progress = downloaded / total_size
                                self._download_progress[plugin.id] = progress

                                if self._on_download_progress:
                                    self._on_download_progress(plugin.id, progress)

            # 解压
            import zipfile
            with zipfile.ZipFile(dest_dir / "plugin.zip", "r") as zf:
                zf.extractall(dest_dir)

            # 删除 zip
            (dest_dir / "plugin.zip").unlink()

        finally:
            self._download_progress.pop(plugin.id, None)

    async def _verify_signature(
        self,
        plugin_dir: Path,
        plugin: PluginInfo
    ) -> bool:
        """验证插件签名"""
        # 读取插件包
        manifest_file = plugin_dir / "manifest.json"
        if not manifest_file.exists():
            return False

        with open(manifest_file, "rb") as f:
            content = f.read()
            content_hash = hashlib.sha256(content).hexdigest()

        # 验证哈希
        if plugin.checksum and content_hash != plugin.checksum:
            return False

        # 如果有签名，验证签名 (简化实现)
        # 实际应该用公钥验证
        if plugin.signature:
            # TODO: 实现签名验证
            pass

        return True

    async def _check_dependencies(self, plugin: PluginInfo) -> bool:
        """检查依赖"""
        for dep_id in plugin.dependencies:
            if dep_id not in self._installed_plugins:
                logger.info(f"Missing dependency: {dep_id}")
                return False
        return True

    # --------------------------------------------------------------------------
    # 插件卸载
    # --------------------------------------------------------------------------

    def uninstall_plugin(self, plugin_id: str) -> bool:
        """
        卸载插件

        Args:
            plugin_id: 插件 ID

        Returns:
            是否卸载成功
        """
        if plugin_id not in self._installed_plugins:
            return False

        # 如果插件已加载，先卸载
        if plugin_id in self._loaded_plugins:
            self.unload_plugin(plugin_id)

        # 删除插件目录
        plugin_dir = self.plugins_dir / plugin_id
        if plugin_dir.exists():
            import shutil
            shutil.rmtree(plugin_dir)

        # 从已安装列表移除
        plugin = self._installed_plugins.pop(plugin_id)
        self._save_installed_plugins()

        if self._on_plugin_uninstalled:
            self._on_plugin_uninstalled(plugin)

        return True

    # --------------------------------------------------------------------------
    # 插件加载
    # --------------------------------------------------------------------------

    def load_plugin(self, plugin_id: str) -> Optional[Any]:
        """
        加载插件

        Args:
            plugin_id: 插件 ID

        Returns:
            插件实例
        """
        if plugin_id in self._loaded_plugins:
            return self._loaded_plugins[plugin_id]

        plugin = self._installed_plugins.get(plugin_id)
        if not plugin:
            return None

        plugin_dir = self.plugins_dir / plugin_id

        # 查找入口文件
        entry_file = plugin_dir / "__init__.py"
        if not entry_file.exists():
            entry_file = plugin_dir / "main.py"

        if not entry_file.exists():
            return None

        try:
            import sys
            import importlib.util
from core.logger import get_logger
logger = get_logger('desktop_environment.plugin_manager')


            # 添加到 Python 路径
            if str(plugin_dir.parent) not in sys.path:
                sys.path.insert(0, str(plugin_dir.parent))

            # 动态导入
            spec = importlib.util.spec_from_file_location(
                f"plugins.{plugin_id}",
                entry_file
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # 获取插件实例
            if hasattr(module, "Plugin"):
                instance = module.Plugin()
            elif hasattr(module, "get_plugin"):
                instance = module.get_plugin()
            else:
                instance = module

            self._loaded_plugins[plugin_id] = instance

            return instance

        except Exception as e:
            logger.info(f"Failed to load plugin {plugin_id}: {e}")
            return None

    def unload_plugin(self, plugin_id: str) -> bool:
        """
        卸载插件

        Args:
            plugin_id: 插件 ID

        Returns:
            是否卸载成功
        """
        if plugin_id not in self._loaded_plugins:
            return True

        instance = self._loaded_plugins[plugin_id]

        # 调用清理方法
        if hasattr(instance, "cleanup"):
            instance.cleanup()
        elif hasattr(instance, "unload"):
            instance.unload()

        self._loaded_plugins.pop(plugin_id)
        return True

    def is_plugin_loaded(self, plugin_id: str) -> bool:
        """检查插件是否已加载"""
        return plugin_id in self._loaded_plugins

    def get_loaded_plugin(self, plugin_id: str) -> Optional[Any]:
        """获取已加载的插件实例"""
        return self._loaded_plugins.get(plugin_id)

    # --------------------------------------------------------------------------
    # 持久化
    # --------------------------------------------------------------------------

    def _get_installed_plugins_file(self) -> Path:
        """获取已安装插件文件"""
        return self.plugins_dir.parent / "installed_plugins.json"

    def _load_installed_plugins(self):
        """加载已安装插件"""
        file = self._get_installed_plugins_file()
        if file.exists():
            try:
                with open(file, encoding="utf-8") as f:
                    data = json.load(f)
                    for plugin_data in data.get("plugins", []):
                        plugin = PluginInfo.from_dict(plugin_data)
                        self._installed_plugins[plugin.id] = plugin
            except Exception as e:
                logger.info(f"Failed to load installed plugins: {e}")

    def _save_installed_plugins(self):
        """保存已安装插件"""
        file = self._get_installed_plugins_file()
        data = {
            "plugins": [p.to_dict() for p in self._installed_plugins.values()]
        }
        with open(file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # --------------------------------------------------------------------------
    # 事件回调
    # --------------------------------------------------------------------------

    def set_on_plugin_discovered(self, callback: Callable[[PluginInfo], None]):
        """设置插件发现回调"""
        self._on_plugin_discovered = callback

    def set_on_plugin_installed(self, callback: Callable[[PluginInfo], None]):
        """设置插件安装回调"""
        self._on_plugin_installed = callback

    def set_on_plugin_uninstalled(self, callback: Callable[[PluginInfo], None]):
        """设置插件卸载回调"""
        self._on_plugin_uninstalled = callback

    def set_on_download_progress(
        self,
        callback: Callable[[str, float], None]
    ):
        """设置下载进度回调"""
        self._on_download_progress = callback

# ============================================================================
# 全局访问器
# ============================================================================

_plugin_manager_instance: Optional[PluginManager] = None

def get_plugin_manager() -> PluginManager:
    """获取全局 PluginManager 实例"""
    global _plugin_manager_instance
    if _plugin_manager_instance is None:
        _plugin_manager_instance = PluginManager()
    return _plugin_manager_instance