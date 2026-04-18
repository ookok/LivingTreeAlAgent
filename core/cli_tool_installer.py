"""
CLI-Tools 云端分发安装器
从远程清单自动下载并安装CLI工具
"""

import asyncio
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable
from urllib.parse import urljoin

import httpx


# ============= 数据模型 =============

@dataclass
class ToolPackage:
    """工具包信息"""
    id: str
    name: str
    description: str
    version: str
    origin: str  # cli-anything / manual / market
    platforms: dict  # {platform: {url, bin_name, sha256}}
    enabled_by_default: bool = True
    installed_path: str = ""
    installed_at: Optional[datetime] = None
    status: str = "available"  # available / downloading / installing / installed / error


@dataclass
class ManifestEntry:
    """清单条目"""
    id: str
    name: str
    desc: str
    origin: str
    version: str = "1.0.0"
    platforms: dict = None
    enabled_by_default: bool = True
    generated_by: str = ""
    generated_at: float = 0.0
    categories: list = None
    tags: list = None
    requires: list = None  # 依赖的其他工具 ID 列表
    internal: bool = False  # 内部工具，不在工具箱直接显示

    def __post_init__(self):
        if self.platforms is None:
            self.platforms = {}
        if self.categories is None:
            self.categories = []
        if self.tags is None:
            self.tags = []
        if self.requires is None:
            self.requires = []

    def to_tool_package(self) -> ToolPackage:
        return ToolPackage(
            id=self.id,
            name=self.name,
            description=self.desc,
            version=self.version,
            origin=self.origin,
            platforms=self.platforms,
            enabled_by_default=self.enabled_by_default,
        )

    @classmethod
    def from_dict(cls, data: dict) -> "ManifestEntry":
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            desc=data.get("desc", ""),
            origin=data.get("origin", "manual"),
            version=data.get("version", "1.0.0"),
            platforms=data.get("platforms", {}),
            enabled_by_default=data.get("enabled_by_default", True),
            generated_by=data.get("generated_by", ""),
            generated_at=data.get("generated_at", 0.0),
            categories=data.get("categories", []),
            tags=data.get("tags", []),
            requires=data.get("requires", []),
            internal=data.get("internal", False),
        )


# ============= 平台检测 =============

def get_current_platform() -> str:
    """获取当前平台标识"""
    import platform
    system = platform.system().lower()
    machine = platform.machine().lower()

    # 标准化机器名
    if machine in ["amd64", "x86_64"]:
        machine = "amd64"
    elif machine in ["arm64", "aarch64"]:
        machine = "arm64"
    elif machine in ["x86", "i386", "i686"]:
        machine = "386"
    else:
        machine = "amd64"  # 默认

    return f"{system}_{machine}"


PLATFORM_MAP = {
    ("windows", "amd64"): "windows_amd64",
    ("windows", "386"): "windows_386",
    ("windows", "arm64"): "windows_arm64",
    ("linux", "amd64"): "linux_amd64",
    ("linux", "386"): "linux_386",
    ("linux", "arm64"): "linux_arm64",
    ("darwin", "amd64"): "darwin_amd64",
    ("darwin", "arm64"): "darwin_arm64",
}


def detect_platform() -> str:
    """检测当前平台"""
    import platform
    system = platform.system().lower()
    machine = platform.machine().lower()

    # AMD64 标准化
    if machine == "x86_64":
        machine = "amd64"

    key = (system, machine)
    return PLATFORM_MAP.get(key, f"{system}_{machine}")


# ============= 清单管理器 =============

class ManifestManager:
    """
    工具清单管理器

    负责:
    - 加载远程/本地清单
    - 增量更新检测
    - 缓存管理
    """

    def __init__(
        self,
        manifest_url: str = "https://market.hermes-ai.cn/tools/manifest.json",
        cache_dir: str = None
    ):
        self.manifest_url = manifest_url
        self.cache_dir = Path(cache_dir or "./.hermes/tools_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self._local_cache = self.cache_dir / "manifest_cache.json"
        self._last_etag = None
        self._last_modified = None

    async def fetch_manifest(
        self,
        force_refresh: bool = False,
        timeout: float = 30.0
    ) -> dict:
        """
        获取工具清单

        Args:
            force_refresh: 强制从远程刷新
            timeout: 超时时间

        Returns:
            清单字典
        """
        # 检查本地缓存
        if not force_refresh and self._local_cache.exists():
            cache_age = datetime.now() - datetime.fromtimestamp(
                self._local_cache.stat().st_mtime
            )
            if cache_age.total_seconds() < 3600:  # 1小时内使用缓存
                return self._load_local_cache()

        # 从远程获取
        try:
            headers = {}
            if self._last_etag:
                headers["If-None-Match"] = self._last_etag
            if self._last_modified:
                headers["If-Modified-Since"] = self._last_modified

            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(
                    self.manifest_url,
                    headers=headers
                )

                if response.status_code == 304:
                    # 未修改，使用缓存
                    return self._load_local_cache()

                if response.status_code == 200:
                    manifest = response.json()

                    # 更新缓存
                    self._save_local_cache(manifest)

                    # 更新ETag
                    self._last_etag = response.headers.get("etag")
                    self._last_modified = response.headers.get("last-modified")

                    return manifest

        except Exception as e:
            # 获取失败，返回本地缓存
            if self._local_cache.exists():
                return self._load_local_cache()

        return {"version": "", "tools": []}

    def _load_local_cache(self) -> dict:
        """加载本地缓存"""
        try:
            with open(self._local_cache, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"version": "", "tools": []}

    def _save_local_cache(self, manifest: dict):
        """保存本地缓存"""
        with open(self._local_cache, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)


# ============= CLI工具安装器 =============

class CLIToolInstaller:
    """
    CLI工具安装器

    功能:
    - 从URL/文件安装
    - 平台适配
    - 完整性校验
    - 依赖安装
    """

    def __init__(
        self,
        tools_dir: str = None,
        cache_dir: str = None
    ):
        self.tools_dir = Path(tools_dir or "./bin/tools")
        self.tools_dir.mkdir(parents=True, exist_ok=True)

        self.cache_dir = Path(cache_dir or "./.hermes/tools_cache/downloads")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self._installed_db = self.tools_dir / "installed.json"
        self._installed: dict[str, ToolPackage] = {}
        self._load_installed_db()

    def _load_installed_db(self):
        """加载已安装数据库"""
        if self._installed_db.exists():
            try:
                with open(self._installed_db, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for tool_data in data.get("tools", []):
                        pkg = ToolPackage(**tool_data)
                        pkg.status = "installed"
                        self._installed[pkg.id] = pkg
            except Exception:
                pass

    def _save_installed_db(self):
        """保存已安装数据库"""
        data = {
            "updated_at": datetime.now().isoformat(),
            "tools": [
                {
                    "id": pkg.id,
                    "name": pkg.name,
                    "description": pkg.description,
                    "version": pkg.version,
                    "origin": pkg.origin,
                    "platforms": pkg.platforms,
                    "enabled_by_default": pkg.enabled_by_default,
                    "installed_path": pkg.installed_path,
                    "installed_at": pkg.installed_at.isoformat() if pkg.installed_at else None,
                }
                for pkg in self._installed.values()
            ]
        }
        with open(self._installed_db, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_installed(self) -> list[ToolPackage]:
        """获取已安装的工具"""
        return list(self._installed.values())

    def is_installed(self, tool_id: str) -> bool:
        """检查工具是否已安装"""
        return tool_id in self._installed

    async def install_from_manifest_entry(
        self,
        entry: ManifestEntry,
        progress_callback: Callable[[float, str], None] = None,
        timeout: float = 120.0
    ) -> ToolPackage:
        """
        从清单条目安装

        Args:
            entry: 清单条目
            progress_callback: 进度回调
            timeout: 超时时间

        Returns:
            安装后的工具包
        """
        pkg = entry.to_tool_package()
        platform = detect_platform()

        if progress_callback:
            progress_callback(0.1, f"准备安装 {pkg.name}...")

        # 获取平台对应的下载链接
        platform_info = pkg.platforms.get(platform)
        if not platform_info:
            # 尝试windows_amd64作为fallback
            platform_info = pkg.platforms.get("windows_amd64")

        if not platform_info:
            raise ValueError(f"不支持当前平台: {platform}")

        url = platform_info.get("url")
        expected_sha256 = platform_info.get("sha256")
        bin_name = platform_info.get("bin_name", pkg.id)

        if not url:
            raise ValueError(f"工具 {pkg.id} 没有可用的下载链接")

        # 创建临时目录
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            if progress_callback:
                progress_callback(0.2, "下载中...")

            # 下载文件
            zip_path = temp_path / f"{pkg.id}.zip"
            await self._download_file(url, zip_path, timeout)

            if progress_callback:
                progress_callback(0.7, "验证文件完整性...")

            # 验证SHA256
            if expected_sha256:
                actual_sha256 = self._calculate_sha256(zip_path)
                if actual_sha256 != expected_sha256:
                    raise ValueError(
                        f"SHA256校验失败: 期望 {expected_sha256[:8]}, "
                        f"实际 {actual_sha256[:8]}"
                    )

            if progress_callback:
                progress_callback(0.8, "解压安装...")

            # 解压
            install_dir = self.tools_dir / pkg.id
            install_dir.mkdir(parents=True, exist_ok=True)

            # 检查是否为 Node.js 特殊格式
            nested_bin = platform_info.get("nested_bin", False)
            strip_components = platform_info.get("strip_components", 0)

            if nested_bin:
                # Node.js 特殊处理：处理嵌套目录结构
                await self._extract_nodejs_package(zip_path, install_dir, bin_name, strip_components)
            else:
                # 标准处理
                with zipfile.ZipFile(zip_path, 'r') as zf:
                    zf.extractall(install_dir)

                # 处理bin目录
                bin_dir = install_dir / "bin"
                bin_dir.mkdir(exist_ok=True)

                # 查找并移动可执行文件
                for ext in ["", ".exe", ".bat", ".cmd"]:
                    for pattern in [f"*{ext}", f"*/{bin_name}{ext}"]:
                        for f in install_dir.rglob(pattern):
                            if f.is_file() and not f.name.startswith("."):
                                dest = bin_dir / f.name
                                shutil.copy2(f, dest)
                                # Windows下创建快捷方式
                                if ext == "" and os.name == "nt":
                                    self._create_shortcut(dest)

            if progress_callback:
                progress_callback(0.9, "安装依赖...")

            # 安装Python依赖（如果有）
            requirements = install_dir / "requirements.txt"
            if requirements.exists():
                await self._install_python_deps(requirements)

            # 为 Node.js 创建 npm/yarn 包装器
            if pkg.id == "nodejs_runtime":
                self._create_node_wrappers(install_dir)

            # 更新状态
            pkg.installed_path = str(install_dir)
            pkg.installed_at = datetime.now()
            pkg.status = "installed"

            self._installed[pkg.id] = pkg
            self._save_installed_db()

            if progress_callback:
                progress_callback(1.0, f"安装完成: {pkg.name}")

        return pkg

    async def _download_file(
        self,
        url: str,
        dest: Path,
        timeout: float = 120.0
    ) -> Path:
        """下载文件"""
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                total_size = int(response.headers.get("content-length", 0))

                downloaded = 0
                with open(dest, "wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        f.write(chunk)
                        downloaded += len(chunk)

        return dest

    def _calculate_sha256(self, path: Path) -> str:
        """计算SHA256"""
        sha256 = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    async def _install_python_deps(self, requirements: Path):
        """安装Python依赖"""
        proc = await asyncio.create_subprocess_exec(
            "pip", "install", "-r", str(requirements),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await proc.communicate()

    def _create_shortcut(self, target: Path):
        """创建Windows快捷方式"""
        # 简单的batch脚本作为替代
        shortcut_path = target.parent / f"{target.stem}.bat"
        with open(shortcut_path, "w") as f:
            f.write(f'@echo off\n"{target.absolute()}" %*\n')
        return shortcut_path

    async def _extract_nodejs_package(
        self,
        archive_path: Path,
        install_dir: Path,
        bin_name: str,
        strip_components: int = 1
    ):
        """
        Node.js 特殊解压处理

        Node.js 官方二进制打包结构：
        - Windows: node-v24.12.1-win-x64/
          - node-v24.12.1-win-x64/
          - node.exe
          - ...
        - macOS/Linux: node-v24.12.1-darwin-arm64/
          - bin/
            - node
            - npm
            - npx
          - lib/
            - node_modules/...
          - ...

        Args:
            archive_path: 下载的压缩包路径
            install_dir: 安装目标目录
            bin_name: 二进制名称 (如 bin/node 或 node.exe)
            strip_components: 剥去的目录层级数
        """
        import platform as sys_platform

        system = sys_platform.system()

        # 先解压到临时目录
        temp_extract = install_dir / "_temp_extract"
        temp_extract.mkdir(parents=True, exist_ok=True)

        if str(archive_path).endswith('.zip'):
            with zipfile.ZipFile(archive_path, 'r') as zf:
                zf.extractall(temp_extract)
        elif str(archive_path).endswith('.tar.gz') or str(archive_path).endswith('.tgz'):
            import tarfile
            with tarfile.open(archive_path, 'r:gz') as tf:
                tf.extractall(temp_extract)
        elif str(archive_path).endswith('.tar.xz'):
            import tarfile
            with tarfile.open(archive_path, 'r:xz') as tf:
                tf.extractall(temp_extract)
        else:
            # 尝试自动检测格式
            try:
                with zipfile.ZipFile(archive_path, 'r') as zf:
                    zf.extractall(temp_extract)
            except Exception:
                import tarfile
                with tarfile.open(archive_path, 'r:*') as tf:
                    tf.extractall(temp_extract)

        # 剥去嵌套目录层级
        extracted_root = temp_extract
        for _ in range(strip_components):
            # 找到第一个目录（通常是以 node-vxxx 开头的目录）
            dirs = [d for d in extracted_root.iterdir() if d.is_dir()]
            if dirs:
                # 把内容移到上一层
                first_dir = dirs[0]
                for item in first_dir.iterdir():
                    shutil.move(str(item), str(extracted_root / item.name))
                first_dir.rmdir()

        # 创建 bin 目录
        bin_dir = install_dir / "bin"
        bin_dir.mkdir(exist_ok=True)

        # 查找并移动 Node.js 二进制文件
        if system == "Windows":
            # Windows: node.exe 在根目录
            for node_exe in extracted_root.glob("node*.exe"):
                shutil.copy2(node_exe, bin_dir / "node.exe")
            # 也复制 npx.exe（如果有）
            for npx_exe in extracted_root.glob("npx*.exe"):
                shutil.copy2(npx_exe, bin_dir / "npx.exe")
        else:
            # macOS/Linux: node 在 bin/ 目录
            node_bin = extracted_root / "bin" / "node"
            if node_bin.exists():
                shutil.copy2(node_bin, bin_dir / "node")
                os.chmod(bin_dir / "node", 0o755)

            # 复制 npm 和 npx
            for script in ["npm", "npx"]:
                src_script = extracted_root / "bin" / script
                if src_script.exists():
                    shutil.copy2(src_script, bin_dir / script)
                    os.chmod(bin_dir / script, 0o755)

            # 复制 node_modules（如果存在）
            src_node_modules = extracted_root / "lib" / "node_modules"
            if src_node_modules.exists():
                lib_dir = install_dir / "lib"
                shutil.copytree(src_node_modules, lib_dir / "node_modules", dirs_exist_ok=True)

        # 清理临时目录
        shutil.rmtree(temp_extract, ignore_errors=True)

    def _create_node_wrappers(self, install_dir: Path):
        """
        为 Node.js 创建 npm/yarn 包装器脚本

        这些包装器确保 npm/yarn 使用沙盒内的 Node.js 而不是系统 Node

        Args:
            install_dir: Node.js 安装目录
        """
        import platform as sys_platform

        system = sys_platform.system()
        bin_dir = install_dir / "bin"

        if system == "Windows":
            # Windows: 创建 .cmd 脚本
            npm_cmd = bin_dir / "npm.cmd"
            npm_content = f'''@echo off
"{bin_dir / "node.exe"}" "{install_dir / "lib" / "node_modules" / "npm" / "bin" / "npm-cli.js"}" %*
'''
            npm_cmd.write_text(npm_content, encoding='utf-8')

            npx_cmd = bin_dir / "npx.cmd"
            npx_content = f'''@echo off
"{bin_dir / "node.exe"}" "{install_dir / "lib" / "node_modules" / "npm" / "bin" / "npx-cli.js"}" %*
'''
            npx_cmd.write_text(npx_content, encoding='utf-8')

        else:
            # Unix: 创建 shell 脚本
            npm_shim = bin_dir / "npm"
            npm_content = f'''#!/bin/sh
"{bin_dir / "node"}" "{install_dir / "lib" / "node_modules" / "npm" / "bin" / "npm-cli.js"}" "$@"
'''
            npm_shim.write_text(npm_content, encoding='utf-8')
            os.chmod(npm_shim, 0o755)

            npx_shim = bin_dir / "npx"
            npx_content = f'''#!/bin/sh
"{bin_dir / "node"}" "{install_dir / "lib" / "node_modules" / "npm" / "bin" / "npx-cli.js"}" "$@"
'''
            npx_shim.write_text(npx_content, encoding='utf-8')
            os.chmod(npx_shim, 0o755)

        # 创建 yarn shim（如果需要）
        self._create_yarn_shim(install_dir, bin_dir, system)

    def _create_yarn_shim(self, install_dir: Path, bin_dir: Path, system: str):
        """
        创建 Yarn 包装器

        Yarn 通常通过 npm 全局安装，这里提供一个基础包装器
        如果需要更完整的 yarn 支持，可以通过 npm install -g yarn 安装
        """
        yarn_src = install_dir / "lib" / "node_modules" / "yarn" / "bin" / "yarn.js"
        yarn_src_cli = install_dir / "lib" / "node_modules" / "yarn" / "bin" / "yarn-cli.js"

        if yarn_src.exists():
            src = yarn_src_cli if yarn_src_cli.exists() else yarn_src
        else:
            # Yarn 不存在，创建指向 npm 的包装（npm 也有基本的 package 管理功能）
            return

        if system == "Windows":
            yarn_cmd = bin_dir / "yarn.cmd"
            yarn_content = f'''@echo off
"{bin_dir / "node.exe"}" "{src}" %*
'''
            yarn_cmd.write_text(yarn_content, encoding='utf-8')
        else:
            yarn_shim = bin_dir / "yarn"
            yarn_content = f'''#!/bin/sh
"{bin_dir / "node"}" "{src}" "$@"
'''
            yarn_shim.write_text(yarn_content, encoding='utf-8')
            os.chmod(yarn_shim, 0o755)

    async def _resolve_and_install_dependencies(
        self,
        entry: ManifestEntry,
        progress_callback: Callable[[float, str], None] = None,
        timeout: float = 120.0,
        visited: set = None
    ) -> list[ToolPackage]:
        """
        递归解析并安装依赖项

        Args:
            entry: 清单条目
            progress_callback: 进度回调
            timeout: 超时时间
            visited: 已访问的依赖项集合（防止循环依赖）

        Returns:
            安装成功的依赖包列表
        """
        if visited is None:
            visited = set()

        installed_deps = []

        # 检查循环依赖
        if entry.id in visited:
            return installed_deps
        visited.add(entry.id)

        # 获取依赖项
        requires = entry.requires or []
        if not requires:
            return installed_deps

        # 加载完整的清单（包含所有工具定义）
        manifest_tools = self._load_all_manifests()

        for dep_id in requires:
            # 检查是否已安装
            if self.is_installed(dep_id):
                continue

            # 查找依赖项的定义
            dep_entry = None
            for tool_id, tool_entry in manifest_tools.items():
                if tool_id == dep_id:
                    dep_entry = tool_entry
                    break

            if not dep_entry:
                # 尝试从本地清单目录加载
                local_manifest = self._load_local_manifest(dep_id)
                if local_manifest:
                    dep_entry = ManifestEntry.from_dict(local_manifest)

            if not dep_entry:
                raise ValueError(f"找不到依赖项: {dep_id}")

            # 递归安装依赖
            if progress_callback:
                progress_callback(0.05, f"安装依赖: {dep_id}...")

            # 先安装依赖的依赖
            dep_deps = await self._resolve_and_install_dependencies(
                dep_entry, progress_callback, timeout, visited
            )
            installed_deps.extend(dep_deps)

            # 安装当前依赖
            try:
                dep_pkg = await self.install_from_manifest_entry(
                    dep_entry, progress_callback, timeout
                )
                installed_deps.append(dep_pkg)
            except Exception as e:
                raise ValueError(f"安装依赖失败 {dep_id}: {e}")

        return installed_deps

    def _load_all_manifests(self) -> dict:
        """加载所有本地清单文件"""
        manifests = {}
        manifest_dir = Path(__file__).parent.parent / "resources" / "tools_manifest"
        if not manifest_dir.exists():
            return manifests

        for manifest_file in manifest_dir.glob("*.json"):
            try:
                with open(manifest_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if "id" in data:
                        manifests[data["id"]] = ManifestEntry.from_dict(data)
            except Exception:
                pass

        return manifests

    def _load_local_manifest(self, tool_id: str) -> dict:
        """从本地清单目录加载指定工具的定义"""
        manifest_path = Path(__file__).parent.parent / "resources" / "tools_manifest" / f"{tool_id}.json"
        if manifest_path.exists():
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return None

    def uninstall(self, tool_id: str) -> bool:
        """卸载工具"""
        if tool_id not in self._installed:
            return False

        pkg = self._installed[tool_id]
        install_dir = Path(pkg.installed_path)

        # 删除安装目录
        if install_dir.exists():
            shutil.rmtree(install_dir, ignore_errors=True)

        # 从数据库移除
        del self._installed[tool_id]
        self._save_installed_db()

        return True


# ============= 同步管理器 =============

class ToolSyncManager:
    """
    工具同步管理器

    功能:
    - 检测新工具
    - 自动下载
    - 增量同步
    """

    def __init__(
        self,
        manifest_url: str = "https://market.hermes-ai.cn/tools/manifest.json",
        tools_dir: str = None,
        auto_install: bool = False
    ):
        self.manifest_manager = ManifestManager(manifest_url)
        self.installer = CLIToolInstaller(tools_dir=tools_dir)
        self.auto_install = auto_install

        self._last_sync: Optional[datetime] = None
        self._new_tools: list[ManifestEntry] = []

    @property
    def new_tools(self) -> list[ManifestEntry]:
        """获取新增工具列表"""
        return self._new_tools

    async def check_updates(
        self,
        progress_callback: Callable[[float, str], None] = None
    ) -> dict:
        """
        检查更新

        Returns:
            {"has_updates": bool, "new": [], "updated": [], "removed": []}
        """
        if progress_callback:
            progress_callback(0.1, "获取远程清单...")

        manifest = await self.manifest_manager.fetch_manifest()

        if progress_callback:
            progress_callback(0.5, "分析变更...")

        remote_tools = {
            entry["id"]: ManifestEntry.from_dict(entry)
            for entry in manifest.get("tools", [])
        }

        local_tools = self.installer.get_installed()
        local_ids = {pkg.id for pkg in local_tools}

        # 检测新增
        new_ids = set(remote_tools.keys()) - local_ids
        new_tools = [remote_tools[tid] for tid in new_ids]

        # 检测更新
        updated_tools = []
        for pkg in local_tools:
            if pkg.id in remote_tools:
                remote = remote_tools[pkg.id]
                if self._is_newer(remote.version, pkg.version):
                    updated_tools.append(remote)

        # 检测卸载
        removed_ids = local_ids - set(remote_tools.keys())

        self._new_tools = new_tools
        self._last_sync = datetime.now()

        result = {
            "has_updates": len(new_tools) > 0 or len(updated_tools) > 0,
            "new": new_tools,
            "updated": updated_tools,
            "removed": list(removed_ids),
        }

        if progress_callback:
            progress_callback(1.0, "检查完成")

        return result

    def _is_newer(self, remote_version: str, local_version: str) -> bool:
        """比较版本号"""
        from packaging import version
        try:
            return version.parse(remote_version) > version.parse(local_version)
        except Exception:
            return remote_version != local_version

    async def sync(
        self,
        progress_callback: Callable[[float, str], None] = None
    ) -> dict:
        """
        执行同步

        Args:
            progress_callback: 进度回调

        Returns:
            {"installed": [], "updated": [], "failed": []}
        """
        result = {"installed": [], "updated": [], "failed": []}

        # 检查更新
        updates = await self.check_updates(progress_callback)

        # 自动安装新增工具
        if self.auto_install:
            for entry in updates.get("new", []):
                if entry.enabled_by_default:
                    try:
                        pkg = await self.installer.install_from_manifest_entry(
                            entry, progress_callback
                        )
                        result["installed"].append(pkg.id)
                    except Exception as e:
                        result["failed"].append({"id": entry.id, "error": str(e)})

        return result

    def get_tools_summary(self) -> dict:
        """获取工具摘要"""
        installed = self.installer.get_installed()

        summary = {
            "total_installed": len(installed),
            "by_origin": {},
            "by_platform": {},
        }

        for pkg in installed:
            # 按来源统计
            summary["by_origin"][pkg.origin] = \
                summary["by_origin"].get(pkg.origin, 0) + 1

            # 按平台统计
            for plat in pkg.platforms.keys():
                summary["by_platform"][plat] = \
                    summary["by_platform"].get(plat, 0) + 1

        return summary


# 单例
_sync_manager: Optional[ToolSyncManager] = None
_installer: Optional[CLIToolInstaller] = None


def get_sync_manager() -> ToolSyncManager:
    """获取同步管理器单例"""
    global _sync_manager
    if _sync_manager is None:
        _sync_manager = ToolSyncManager()
    return _sync_manager


def get_installer() -> CLIToolInstaller:
    """获取安装器单例"""
    global _installer
    if _installer is None:
        _installer = CLIToolInstaller()
    return _installer
