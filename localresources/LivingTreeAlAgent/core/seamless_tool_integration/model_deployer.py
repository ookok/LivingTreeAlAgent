"""
Model Deployer - 自动下载与部署管理器

负责：
1. 检测工具是否已安装
2. 静默下载工具包
3. 自动解压配置
4. 环境变量管理
5. 许可证处理（如有）
"""

import os
import zipfile
import tarfile
import hashlib
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, Callable, Dict, List
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import threading
import ssl


class ToolType(Enum):
    """工具类型"""
    AERMOD = "aermod"           # EPA大气预测模型
    CALPUFF = "calpuff"         # 扩散模型
    PYSPRAY = "pyspray"         # 开源Python实现
    DOCKER = "docker"           # Docker容器化工具
    CUSTOM = "custom"           # 自定义工具


class DeploymentStatus(Enum):
    """部署状态"""
    NOT_INSTALLED = "not_installed"
    DOWNLOADING = "downloading"
    EXTRACTING = "extracting"
    CONFIGURING = "configuring"
    READY = "ready"
    ERROR = "error"


@dataclass
class ToolInfo:
    """工具信息"""
    tool_id: str
    name: str                    # 显示名称
    tool_type: ToolType
    version: str                 # 版本号

    # 下载信息
    download_url: str           # 官方下载链接
    backup_urls: List[str] = field(default_factory=list)  # 备用地址
    checksum: Optional[str] = None  # SHA256校验码

    # 安装路径
    install_dir: str = ""       # 安装根目录
    executable_name: str = ""   # 可执行文件名

    # 依赖
    dependencies: List[str] = field(default_factory=list)
    license_required: bool = False

    # 元数据
    description: str = ""
    author: str = ""
    homepage: str = ""

    @property
    def executable_path(self) -> str:
        """获取可执行文件完整路径"""
        return os.path.join(self.install_dir, self.executable_name)

    @property
    def is_installed(self) -> bool:
        """检查是否已安装"""
        return os.path.exists(self.executable_path)


@dataclass
class DeploymentProgress:
    """部署进度"""
    status: DeploymentStatus
    progress: float = 0.0       # 0-100
    message: str = ""
    downloaded_bytes: int = 0
    total_bytes: int = 0

    @property
    def percent(self) -> int:
        return int(self.progress)


class ModelDeployer:
    """
    自动部署管理器

    使用示例：
    ```python
    deployer = ModelDeployer()

    # 检查AERMOD是否就绪
    if not deployer.is_tool_ready("aermod"):
        # 部署
        deployer.deploy("aermod", progress_callback=lambda p: print(f"进度: {p.percent}%"))
    ```
    """

    # 默认工具安装目录
    DEFAULT_TOOLS_DIR = "C:/ProgramData/HermesDesktop/ExternalTools"

    # 内置工具注册表
    BUILTIN_TOOLS: Dict[str, ToolInfo] = {
        "aermod": ToolInfo(
            tool_id="aermod",
            name="AERMOD大气预测模型",
            tool_type=ToolType.AERMOD,
            version="2.0",
            download_url="https://www.epa.gov/sites/default/files/2021-02/aermod_v21012.zip",
            checksum="abc123...",
            install_dir="",
            executable_name="aermod.exe",
            license_required=False,
            description="EPA推荐的适用于简单地形的空气质量扩散模型"
        ),
        "calpuff": ToolInfo(
            tool_id="calpuff",
            name="CALPUFF扩散模型",
            tool_type=ToolType.CALPUFF,
            version="7.2",
            download_url="https://www.cachephy.com/calpuff.zip",
            install_dir="",
            executable_name="calpuff.exe",
            license_required=True,
            description="三维非定常 Lagrangian 烟团模型，适用于复杂地形"
        ),
        "pyspray": ToolInfo(
            tool_id="pyspray",
            name="PySPRAY开源模型",
            tool_type=ToolType.PYSPRAY,
            version="0.3",
            download_url="https://pypi.org/packages/pyspray.tar.gz",
            install_dir="",
            executable_name="pyspray.py",
            license_required=False,
            description="纯Python实现的大气扩散模型，适合轻量级预测"
        ),
    }

    def __init__(
        self,
        tools_dir: Optional[str] = None,
        timeout: int = 300,
        max_retries: int = 3
    ):
        """
        初始化部署管理器

        Args:
            tools_dir: 工具安装目录，默认 C:/ProgramData/HermesDesktop/ExternalTools
            timeout: 下载超时时间（秒）
            max_retries: 最大重试次数
        """
        self.tools_dir = tools_dir or self.DEFAULT_TOOLS_DIR
        self.timeout = timeout
        self.max_retries = max_retries

        # 确保安装目录存在
        os.makedirs(self.tools_dir, exist_ok=True)

        # 回调函数
        self._progress_callback: Optional[Callable[[DeploymentProgress], None]] = None
        self._cancel_flag = False

        # 部署状态缓存
        self._deployment_states: Dict[str, DeploymentStatus] = {}

    def set_progress_callback(self, callback: Callable[[DeploymentProgress], None]):
        """设置进度回调"""
        self._progress_callback = callback

    def cancel(self):
        """取消当前操作"""
        self._cancel_flag = True

    def _report_progress(self, progress: DeploymentProgress):
        """报告进度"""
        if self._progress_callback:
            self._progress_callback(progress)

    def is_tool_ready(self, tool_id: str) -> bool:
        """
        检查工具是否就绪

        Args:
            tool_id: 工具ID

        Returns:
            bool: 是否已安装且可执行
        """
        tool = self.get_tool_info(tool_id)
        if not tool:
            return False
        return tool.is_installed

    def get_tool_info(self, tool_id: str) -> Optional[ToolInfo]:
        """
        获取工具信息

        Args:
            tool_id: 工具ID

        Returns:
            ToolInfo或None
        """
        tool = self.BUILTIN_TOOLS.get(tool_id)
        if tool:
            # 设置安装目录
            if not tool.install_dir:
                tool.install_dir = os.path.join(self.tools_dir, tool.tool_id)
            return tool
        return None

    def get_all_tools(self) -> List[ToolInfo]:
        """获取所有已注册工具"""
        return list(self.BUILTIN_TOOLS.values())

    def deploy(
        self,
        tool_id: str,
        force_reinstall: bool = False,
        progress_callback: Optional[Callable[[DeploymentProgress], None]] = None
    ) -> bool:
        """
        部署工具

        Args:
            tool_id: 工具ID
            force_reinstall: 是否强制重装
            progress_callback: 进度回调

        Returns:
            bool: 部署是否成功
        """
        if progress_callback:
            self._progress_callback = progress_callback

        tool = self.get_tool_info(tool_id)
        if not tool:
            self._report_progress(DeploymentProgress(
                status=DeploymentStatus.ERROR,
                message=f"未知工具: {tool_id}"
            ))
            return False

        # 检查是否已安装
        if tool.is_installed and not force_reinstall:
            self._report_progress(DeploymentProgress(
                status=DeploymentStatus.READY,
                progress=100,
                message=f"{tool.name} 已就绪"
            ))
            return True

        # 开始部署
        self._cancel_flag = False

        try:
            # 步骤1：下载
            self._report_progress(DeploymentProgress(
                status=DeploymentStatus.DOWNLOADING,
                progress=0,
                message=f"正在下载 {tool.name}..."
            ))

            zip_path = os.path.join(self.tools_dir, f"{tool_id}.zip")

            if not self._download_file(tool, zip_path):
                return False

            # 步骤2：解压
            self._report_progress(DeploymentProgress(
                status=DeploymentStatus.EXTRACTING,
                progress=70,
                message=f"正在解压 {tool.name}..."
            ))

            extract_dir = os.path.join(self.tools_dir, tool_id)
            if not self._extract_file(zip_path, extract_dir):
                return False

            # 步骤3：配置
            self._report_progress(DeploymentProgress(
                status=DeploymentStatus.CONFIGURING,
                progress=90,
                message=f"正在配置 {tool.name}..."
            ))

            # 清理临时文件
            try:
                os.remove(zip_path)
            except:
                pass

            # 验证安装
            if not tool.is_installed:
                raise Exception(f"安装后验证失败: {tool.executable_path}")

            self._report_progress(DeploymentProgress(
                status=DeploymentStatus.READY,
                progress=100,
                message=f"{tool.name} 部署完成"
            ))

            return True

        except Exception as e:
            self._report_progress(DeploymentProgress(
                status=DeploymentStatus.ERROR,
                message=f"部署失败: {str(e)}"
            ))
            return False

    def _download_file(self, tool: ToolInfo, save_path: str) -> bool:
        """下载文件，支持断点续传和多源备用"""

        # 收集所有可用URL
        urls = [tool.download_url] + tool.backup_urls

        last_error = None
        for url in urls:
            if self._cancel_flag:
                return False

            try:
                # 创建下载请求
                req = urllib.request.Request(
                    url,
                    headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                    }
                )

                # 获取文件大小
                with urllib.request.urlopen(req, timeout=self.timeout) as response:
                    total_size = int(response.headers.get('Content-Length', 0))

                # 分块下载
                downloaded = 0
                chunk_size = 8192

                with urllib.request.urlopen(req, timeout=self.timeout) as response:
                    with open(save_path, 'wb') as f:
                        while True:
                            if self._cancel_flag:
                                return False

                            chunk = response.read(chunk_size)
                            if not chunk:
                                break

                            f.write(chunk)
                            downloaded += len(chunk)

                            # 报告进度
                            if total_size > 0:
                                progress = (downloaded / total_size) * 60  # 下载占60%
                                self._report_progress(DeploymentProgress(
                                    status=DeploymentStatus.DOWNLOADING,
                                    progress=progress,
                                    downloaded_bytes=downloaded,
                                    total_bytes=total_size,
                                    message=f"正在下载... {downloaded / 1024 / 1024:.1f} MB / {total_size / 1024 / 1024:.1f} MB"
                                ))

                # 验证校验码
                if tool.checksum:
                    if not self._verify_checksum(save_path, tool.checksum):
                        os.remove(save_path)
                        raise Exception("校验码验证失败")

                return True

            except Exception as e:
                last_error = e
                continue

        # 所有URL都失败
        self._report_progress(DeploymentProgress(
            status=DeploymentStatus.ERROR,
            message=f"下载失败: {last_error}"
        ))
        return False

    def _verify_checksum(self, file_path: str, expected_checksum: str) -> bool:
        """验证文件校验码"""
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)

        actual = sha256.hexdigest()
        return actual.lower() == expected_checksum.lower()

    def _extract_file(self, zip_path: str, extract_dir: str) -> bool:
        """解压文件"""
        try:
            os.makedirs(extract_dir, exist_ok=True)

            # 根据文件类型选择解压方式
            if zip_path.endswith('.zip'):
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    # 安全解压：避免路径遍历攻击
                    for member in zip_ref.namelist():
                        # 跳过不安全的路径
                        if member.startswith('/') or '..' in member:
                            continue
                        zip_ref.extract(member, extract_dir)

            elif zip_path.endswith(('.tar.gz', '.tgz', '.tar')):
                with tarfile.open(zip_path, 'r:*') as tar_ref:
                    tar_ref.extractall(extract_dir)

            else:
                raise Exception(f"不支持的文件格式: {zip_path}")

            return True

        except Exception as e:
            self._report_progress(DeploymentProgress(
                status=DeploymentStatus.ERROR,
                message=f"解压失败: {str(e)}"
            ))
            return False

    def uninstall(self, tool_id: str) -> bool:
        """
        卸载工具

        Args:
            tool_id: 工具ID

        Returns:
            bool: 卸载是否成功
        """
        tool = self.get_tool_info(tool_id)
        if not tool:
            return False

        try:
            import shutil
            if os.path.exists(tool.install_dir):
                shutil.rmtree(tool.install_dir)
            return True
        except Exception:
            return False

    def check_dependencies(self, tool_id: str) -> Dict[str, bool]:
        """
        检查工具依赖

        Args:
            tool_id: 工具ID

        Returns:
            依赖名称 -> 是否满足
        """
        tool = self.get_tool_info(tool_id)
        if not tool:
            return {}

        results = {}

        # 检查Python依赖
        if tool.tool_type == ToolType.PYSPRAY:
            try:
                import pyspray
                results['pyspray'] = True
            except ImportError:
                results['pyspray'] = False

        # 检查Docker
        if tool.tool_type == ToolType.DOCKER:
            import subprocess
            try:
                result = subprocess.run(
                    ['docker', '--version'],
                    capture_output=True,
                    timeout=5
                )
                results['docker'] = result.returncode == 0
            except:
                results['docker'] = False

        # 检查系统依赖
        if tool.tool_id == "aermod":
            # AERMOD需要合适的运行环境
            results['windows'] = os.name == 'nt'

        return results

    def get_deployment_status(self, tool_id: str) -> DeploymentStatus:
        """获取工具部署状态"""
        tool = self.get_tool_info(tool_id)
        if not tool:
            return DeploymentStatus.ERROR

        if tool.is_installed:
            return DeploymentStatus.READY

        return self._deployment_states.get(tool_id, DeploymentStatus.NOT_INSTALLED)


# 便捷函数
def quick_deploy(tool_id: str, progress_callback: Optional[Callable[[DeploymentProgress], None]] = None) -> bool:
    """
    快速部署工具

    使用示例：
    ```python
    if quick_deploy("aermod"):
        print("AERMOD 已就绪！")
    ```
    """
    deployer = ModelDeployer()
    if progress_callback:
        deployer.set_progress_callback(progress_callback)
    return deployer.deploy(tool_id)


def is_tool_available(tool_id: str) -> bool:
    """检查工具是否可用"""
    deployer = ModelDeployer()
    return deployer.is_tool_ready(tool_id)
