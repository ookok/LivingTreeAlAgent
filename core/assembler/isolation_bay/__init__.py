"""
隔离舱 (Isolation Bay)

目标：沙箱内构建/安装，不污染主系统。

目录隔离：./modules/ext/{lib_name}/
- 二进制/虚拟环境在此

语言适配：
- Go/Rust：编译为静态二进制
- Node/Python：独立 venv，仅装必要依赖

生成适配器：统一封装为 ToolContract 接口
"""

import os
import asyncio
import shutil
import subprocess
import venv
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Callable
from enum import Enum


class LanguageType(Enum):
    """语言类型"""
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    GO = "go"
    RUST = "rust"
    UNKNOWN = "unknown"


@dataclass
class InstallationResult:
    """安装结果"""
    success: bool
    module_name: str
    module_path: str
    entry_point: str = ""          # 入口文件/命令
    error_message: str = ""

    # 运行时信息
    runtime_version: str = ""
    dependencies: list[str] = []

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "module_name": self.module_name,
            "module_path": self.module_path,
            "entry_point": self.entry_point,
            "error_message": self.error_message,
            "runtime_version": self.runtime_version,
            "dependencies": self.dependencies,
        }


class BaseInstaller:
    """基础安装器"""

    def __init__(self, module_name: str, base_dir: Path):
        self.module_name = module_name
        self.base_dir = base_dir
        self.module_dir = base_dir / module_name

    async def install(self, repo_url: str) -> InstallationResult:
        """安装模块"""
        raise NotImplementedError

    def uninstall(self) -> bool:
        """卸载模块"""
        if self.module_dir.exists():
            shutil.rmtree(self.module_dir)
            return True
        return False

    def get_status(self) -> dict:
        """获取状态"""
        return {
            "installed": self.module_dir.exists(),
            "path": str(self.module_dir),
        }


class PythonInstaller(BaseInstaller):
    """Python 安装器"""

    async def install(self, repo_url: str) -> InstallationResult:
        """安装 Python 模块"""
        try:
            # 创建隔离目录
            self.module_dir.mkdir(parents=True, exist_ok=True)
            venv_dir = self.module_dir / "venv"

            # 创建虚拟环境
            venv.create(venv_dir, with_pip=True)

            # 获取 pip 路径
            if os.name == 'nt':
                pip_path = venv_dir / "Scripts" / "pip.exe"
                python_path = venv_dir / "Scripts" / "python.exe"
            else:
                pip_path = venv_dir / "bin" / "pip"
                python_path = venv_dir / "bin" / "python"

            # 解析仓库 URL 获取包名
            package_name = self._extract_package_name(repo_url)

            # 安装依赖
            if package_name:
                cmd = [str(pip_path), "install", package_name]
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await proc.communicate()

                if proc.returncode != 0:
                    return InstallationResult(
                        success=False,
                        module_name=self.module_name,
                        module_path=str(self.module_dir),
                        error_message=stderr.decode() if stderr else "安装失败"
                    )

            # 获取版本
            version_proc = await asyncio.create_subprocess_exec(
                str(python_path), "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            ver_stdout, _ = await version_proc.communicate()
            version = ver_stdout.decode().strip()

            return InstallationResult(
                success=True,
                module_name=self.module_name,
                module_path=str(self.module_dir),
                entry_point=str(python_path),
                runtime_version=version,
            )

        except Exception as e:
            return InstallationResult(
                success=False,
                module_name=self.module_name,
                module_path=str(self.module_dir),
                error_message=str(e)
            )

    def _extract_package_name(self, url: str) -> Optional[str]:
        """从 URL 提取包名"""
        # GitHub: https://github.com/owner/repo -> pip install repo
        if "github.com" in url:
            parts = url.replace("https://github.com/", "").split("/")
            if len(parts) >= 2:
                return parts[1].replace(".git", "")

        # Gitee
        if "gitee.com" in url:
            parts = url.replace("https://gitee.com/", "").split("/")
            if len(parts) >= 2:
                return parts[1].replace(".git", "")

        # 直接是包名
        return url.strip()


class NodeInstaller(BaseInstaller):
    """Node.js 安装器"""

    async def install(self, repo_url: str) -> InstallationResult:
        """安装 Node 模块"""
        try:
            # 创建隔离目录
            self.module_dir.mkdir(parents=True, exist_ok=True)

            # 解析仓库
            package_name = self._extract_package_name(repo_url)

            if not package_name:
                return InstallationResult(
                    success=False,
                    module_name=self.module_name,
                    module_path=str(self.module_dir),
                    error_message="无法解析包名"
                )

            # 初始化 npm 项目
            init_proc = await asyncio.create_subprocess_exec(
                "npm", "init", "-y",
                cwd=str(self.module_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await init_proc.communicate()

            # 安装包
            install_proc = await asyncio.create_subprocess_exec(
                "npm", "install", package_name,
                cwd=str(self.module_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await install_proc.communicate()

            if install_proc.returncode != 0:
                return InstallationResult(
                    success=False,
                    module_name=self.module_name,
                    module_path=str(self.module_dir),
                    error_message=stderr.decode() if stderr else "安装失败"
                )

            # 获取版本
            version_proc = await asyncio.create_subprocess_exec(
                "node", "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            ver_stdout, _ = await version_proc.communicate()
            version = ver_stdout.decode().strip()

            return InstallationResult(
                success=True,
                module_name=self.module_name,
                module_path=str(self.module_dir),
                entry_point=str(self.module_dir / "node_modules" / package_name),
                runtime_version=f"node {version}",
            )

        except Exception as e:
            return InstallationResult(
                success=False,
                module_name=self.module_name,
                module_path=str(self.module_dir),
                error_message=str(e)
            )

    def _extract_package_name(self, url: str) -> Optional[str]:
        """从 URL 提取包名"""
        if "github.com" in url:
            parts = url.replace("https://github.com/", "").split("/")
            if len(parts) >= 2:
                return parts[1].replace(".git", "")

        if "gitee.com" in url:
            parts = url.replace("https://gitee.com/", "").split("/")
            if len(parts) >= 2:
                return parts[1].replace(".git", "")

        return url.strip()


class GoInstaller(BaseInstaller):
    """Go 安装器 - 编译为静态二进制"""

    async def install(self, repo_url: str) -> InstallationResult:
        """安装 Go 模块"""
        try:
            # 创建隔离目录
            self.module_dir.mkdir(parents=True, exist_ok=True)

            # 克隆仓库
            clone_proc = await asyncio.create_subprocess_exec(
                "git", "clone", "--depth", "1", repo_url, str(self.module_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await clone_proc.communicate()

            if clone_proc.returncode != 0:
                return InstallationResult(
                    success=False,
                    module_name=self.module_name,
                    module_path=str(self.module_dir),
                    error_message=stderr.decode() if stderr else "克隆失败"
                )

            # 尝试构建
            build_proc = await asyncio.create_subprocess_exec(
                "go", "build", "-o", self.module_name, ".",
                cwd=str(self.module_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await build_proc.communicate()

            # 获取 Go 版本
            version_proc = await asyncio.create_subprocess_exec(
                "go", "version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            ver_stdout, _ = await version_proc.communicate()
            version = ver_stdout.decode().strip()

            binary_path = self.module_dir / self.module_name
            if os.name == 'nt':
                binary_path = self.module_dir / f"{self.module_name}.exe"

            return InstallationResult(
                success=True,
                module_name=self.module_name,
                module_path=str(self.module_dir),
                entry_point=str(binary_path),
                runtime_version=version,
            )

        except Exception as e:
            return InstallationResult(
                success=False,
                module_name=self.module_name,
                module_path=str(self.module_dir),
                error_message=str(e)
            )


class IsolationBay:
    """隔离舱 - 沙箱安装管理"""

    def __init__(self, base_dir: Optional[Path] = None):
        if base_dir is None:
            base_dir = Path.home() / ".hermes-desktop" / "modules" / "ext"
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

        self._installers: dict[str, BaseInstaller] = {}

    def get_installer(self, module_name: str, language: LanguageType) -> BaseInstaller:
        """获取安装器"""
        if language == LanguageType.PYTHON:
            return PythonInstaller(module_name, self.base_dir)
        elif language in (LanguageType.JAVASCRIPT, LanguageType.TYPESCRIPT):
            return NodeInstaller(module_name, self.base_dir)
        elif language == LanguageType.GO:
            return GoInstaller(module_name, self.base_dir)
        else:
            # 默认 Python
            return PythonInstaller(module_name, self.base_dir)

    async def install(
        self,
        module_name: str,
        repo_url: str,
        language: LanguageType,
        progress_callback: Optional[Callable] = None
    ) -> InstallationResult:
        """
        安装模块到隔离舱

        Args:
            module_name: 模块名称
            repo_url: 仓库 URL
            language: 语言类型
            progress_callback: 进度回调

        Returns:
            InstallationResult: 安装结果
        """
        installer = self.get_installer(module_name, language)
        self._installers[module_name] = installer

        if progress_callback:
            await progress_callback(f"正在初始化隔离舱...")

        result = await installer.install(repo_url)

        if result.success:
            if progress_callback:
                await progress_callback(f"模块安装完成: {result.entry_point}")

        return result

    def uninstall(self, module_name: str) -> bool:
        """卸载模块"""
        if module_name in self._installers:
            return self._installers[module_name].uninstall()
        return False

    def list_installed(self) -> list[dict]:
        """列出已安装模块"""
        results = []
        for name, installer in self._installers.items():
            results.append({
                "name": name,
                **installer.get_status()
            })

        # 检查目录中的其他模块
        if self.base_dir.exists():
            for item in self.base_dir.iterdir():
                if item.is_dir() and item.name not in self._installers:
                    results.append({
                        "name": item.name,
                        "installed": True,
                        "path": str(item),
                    })

        return results

    def get_module_path(self, module_name: str) -> Optional[Path]:
        """获取模块路径"""
        module_path = self.base_dir / module_name
        return module_path if module_path.exists() else None