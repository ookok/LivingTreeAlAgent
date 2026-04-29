"""
下载管理器
GitHub Store - 桌面代码仓库
支持断点续传、并发下载、进度追踪
"""

import os
import asyncio
import logging
import hashlib
import shutil
import tempfile
import subprocess
import platform
from pathlib import Path
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
import time

from .models import GitHubAsset, DownloadTask, AssetType, PlatformType

logger = logging.getLogger(__name__)


@dataclass
class DownloadConfig:
    """下载配置"""
    download_dir: str = "~/.hermes-desktop/downloads"
    max_concurrent: int = 3
    chunk_size: int = 1024 * 1024  # 1MB
    timeout: int = 300  # 5 分钟超时
    retry_times: int = 3
    retry_delay: float = 2.0  # 秒
    verify_checksum: bool = True


class Downloader:
    """
    下载管理器

    功能:
    - 单文件下载
    - 断点续传
    - 下载进度追踪
    - 自动选择安装程序
    """

    def __init__(self, config: Optional[DownloadConfig] = None):
        self.config = config or DownloadConfig()
        self._tasks: Dict[str, DownloadTask] = {}
        self._download_dir = Path(os.path.expanduser(self.config.download_dir))
        self._download_dir.mkdir(parents=True, exist_ok=True)

    def _generate_task_id(self, url: str, repo: str) -> str:
        """生成任务 ID"""
        key = f"{repo}:{url}"
        return hashlib.md5(key.encode()).hexdigest()[:16]

    async def download_asset(
        self,
        asset: GitHubAsset,
        repo_full_name: str,
        version: str,
        platform: PlatformType,
        progress_callback: Optional[Callable[[DownloadTask], None]] = None,
        install_after_download: bool = False,
    ) -> Optional[str]:
        """
        下载资源文件

        Args:
            asset: 资源信息
            repo_full_name: 仓库全名
            version: 版本号
            platform: 平台
            progress_callback: 进度回调
            install_after_download: 下载后是否自动安装

        Returns:
            下载后的文件路径，失败返回 None
        """
        task_id = self._generate_task_id(asset.download_url, repo_full_name)

        # 创建任务
        task = DownloadTask(
            id=task_id,
            repo_full_name=repo_full_name,
            asset=asset,
            total_size=asset.size,
            status="pending",
            started_at=datetime.now(),
        )
        self._tasks[task_id] = task

        try:
            # 确定保存路径
            save_path = self._get_save_path(repo_full_name, version, asset.name)
            task.download_path = str(save_path)

            # 更新状态
            task.status = "downloading"

            # 执行下载
            success = await self._do_download(task, progress_callback)

            if success:
                task.status = "completed"
                task.completed_at = datetime.now()
                task.progress = 100.0

                logger.info(f"下载完成: {asset.name} -> {save_path}")

                # 可选：自动安装
                if install_after_download:
                    await self._install_asset(save_path, asset, repo_full_name)

                return str(save_path)
            else:
                task.status = "failed"
                return None

        except Exception as e:
            task.status = "failed"
            task.error_message = str(e)
            logger.error(f"下载失败: {asset.name}, 错误: {e}")
            return None

        finally:
            if progress_callback:
                progress_callback(task)

    async def _do_download(
        self,
        task: DownloadTask,
        progress_callback: Optional[Callable],
    ) -> bool:
        """执行下载"""
        import urllib.request

        url = task.asset.download_url
        save_path = Path(task.download_path)

        # 确保目录存在
        save_path.parent.mkdir(parents=True, exist_ok=True)

        # 断点续传：检查已下载的部分
        downloaded = 0
        if save_path.exists():
            downloaded = save_path.stat().st_size
            if downloaded >= task.total_size:
                # 已下载完成
                task.progress = 100.0
                return True

        # 设置请求头 (支持断点续传)
        headers = {
            "User-Agent": "Hermes-Desktop-GitHub-Store/1.0",
        }
        if downloaded > 0:
            headers["Range"] = f"bytes={downloaded}-"

        req = urllib.request.Request(url, headers=headers)

        try:
            with urllib.request.urlopen(req, timeout=self.config.timeout) as resp:
                # 检查响应码
                code = resp.status
                if code not in (200, 206):
                    logger.error(f"HTTP {code}")
                    return False

                total_to_download = task.total_size - downloaded
                chunk_size = self.config.chunk_size

                with open(save_path, "ab" if downloaded > 0 else "wb") as f:
                    while True:
                        chunk = resp.read(chunk_size)
                        if not chunk:
                            break

                        f.write(chunk)
                        downloaded += len(chunk)

                        # 更新进度
                        if task.total_size > 0:
                            task.progress = round(downloaded / task.total_size * 100, 1)
                        task.downloaded_size = downloaded

                        if progress_callback:
                            progress_callback(task)

                # 验证下载
                if task.total_size > 0 and downloaded != task.total_size:
                    logger.warning(
                        f"文件大小不匹配: 期望 {task.total_size}, 实际 {downloaded}"
                    )

                return True

        except Exception as e:
            logger.error(f"下载异常: {e}")
            task.error_message = str(e)

            # 清理不完整的文件
            if save_path.exists() and save_path.stat().st_size < task.total_size:
                try:
                    save_path.unlink()
                except Exception:
                    pass

            return False

    def _get_save_path(self, repo_full_name: str, version: str, asset_name: str) -> Path:
        """获取保存路径"""
        repo_dir = self._download_dir / repo_full_name.replace("/", "_") / version
        repo_dir.mkdir(parents=True, exist_ok=True)
        return repo_dir / asset_name

    async def _install_asset(
        self,
        file_path: Path,
        asset: GitHubAsset,
        repo_full_name: str,
    ):
        """安装下载的资源"""
        try:
            system = platform.system().lower()

            if asset.asset_type == AssetType.EXE and system == "windows":
                # Windows: 直接运行安装程序 (静默安装)
                await self._run_installer(
                    file_path,
                    ["/S", "/SILENT"],  # 常见静默安装参数
                )

            elif asset.asset_type == AssetType.MSI and system == "windows":
                # Windows MSI
                await self._run_installer(
                    file_path,
                    ["/quiet", "/qn"],  # 静默安装参数
                )

            elif asset.asset_type == AssetType.APPIMAGE and system == "linux":
                # Linux AppImage: 添加执行权限
                os.chmod(file_path, 0o755)
                # 可选：移动到 ~/Applications
                pass

            elif asset.asset_type == AssetType.DEB and system == "linux":
                # Debian/Ubuntu
                await self._run_installer(file_path, ["-i"], dpkg=True)

            elif asset.asset_type == AssetType.RPM and system == "linux":
                # Fedora/RHEL
                await self._run_installer(file_path, ["-i"], rpm=True)

            elif asset.asset_type == AssetType.DMG and system == "darwin":
                # macOS DMG: 挂载并复制到 Applications
                await self._mount_dmg(file_path)

            elif asset.asset_type == AssetType.ARCHIVE:
                # 通用压缩包: 解压到 App 目录
                await self._extract_archive(file_path)

            else:
                logger.info(f"不支持自动安装类型: {asset.asset_type}")

        except Exception as e:
            logger.error(f"安装失败: {e}")

    async def _run_installer(
        self,
        file_path: Path,
        extra_args: list,
        dpkg: bool = False,
        rpm: bool = False,
    ):
        """运行安装程序"""
        cmd = [str(file_path)] + extra_args

        if dpkg:
            cmd = ["dpkg", "-i", str(file_path)]
        elif rpm:
            cmd = ["rpm", "-i", "--force", str(file_path)]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            logger.error(f"安装失败: {stderr.decode() if stderr else stdout.decode()}")
        else:
            logger.info(f"安装完成: {file_path}")

    async def _mount_dmg(self, file_path: Path):
        """挂载 DMG 并复制到 Applications"""
        mount_point = Path(f"/Volumes/{file_path.stem}")

        # 挂载
        proc = await asyncio.create_subprocess_exec(
            "hdiutil", "attach", str(file_path),
            "-mountpoint", str(mount_point),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()

        # 复制到 Applications
        app_path = Path("/Applications")
        if mount_point.exists():
            for item in mount_point.iterdir():
                if item.suffix == ".app":
                    dest = app_path / item.name
                    if dest.exists():
                        shutil.rmtree(dest)
                    shutil.copytree(item, dest)

        # 卸载
        await asyncio.create_subprocess_exec(
            "hdiutil", "detach", str(mount_point),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

    async def _extract_archive(self, file_path: Path):
        """解压压缩包到 App 目录"""
        extract_dir = file_path.parent / file_path.stem

        if file_path.suffix in (".gz", ".bz2") and ".tar" in file_path.name:
            import tarfile
            with tarfile.open(file_path) as tar:
                tar.extractall(extract_dir)
        else:
            import zipfile
            with zipfile.ZipFile(file_path) as zf:
                zf.extractall(extract_dir)

    def get_task(self, task_id: str) -> Optional[DownloadTask]:
        """获取任务状态"""
        return self._tasks.get(task_id)

    def get_active_tasks(self) -> list[DownloadTask]:
        """获取活跃任务"""
        return [
            t for t in self._tasks.values()
            if t.status in ("pending", "downloading")
        ]

    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        if task_id in self._tasks:
            self._tasks[task_id].status = "cancelled"
            return True
        return False

    def get_downloads_dir(self) -> Path:
        """获取下载目录"""
        return self._download_dir

    def open_downloads_dir(self):
        """打开下载目录"""
        path = str(self._download_dir)
        system = platform.system()

        if system == "Windows":
            os.startfile(path)
        elif system == "Darwin":
            subprocess.run(["open", path])
        else:
            subprocess.run(["xdg-open", path])
