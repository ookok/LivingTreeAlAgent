# mirror_accelerator.py — 多源镜像加速系统

import os
import re
import time
import asyncio
import logging
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from dataclasses import asdict, dataclass
from datetime import datetime
import json


logger = logging.getLogger(__name__)


# ============ 镜像源配置 ============

@dataclass
class MirrorEndpoint:
    """镜像端点"""
    name: str
    base_url: str
    source_type: str  # github / gitee / pypi / npm
    priority: int      # 优先级 (越小越高)
    timeout: float     # 超时秒数
    enabled: bool = True
    health_score: float = 1.0
    success_count: int = 0
    failure_count: int = 0
    last_check: Optional[int] = None
    last_success: Optional[int] = None


# ============ 下载任务 ============

@dataclass
class DownloadTask:
    """下载任务"""
    id: str
    source_url: str
    dest_path: Path
    status: str = "pending"  # pending/downloading/completed/failed
    progress: float = 0.0
    bytes_downloaded: int = 0
    total_bytes: int = 0
    started_at: Optional[int] = None
    completed_at: Optional[int] = None
    error_message: Optional[str] = None
    attempts: int = 0
    used_mirror: Optional[str] = None
    speed_bps: float = 0.0  # 字节/秒


# ============ 镜像配置管理器 ============

class MirrorConfigManager:
    """
    镜像配置管理器

    功能:
    1. 管理多个镜像源
    2. 健康度追踪
    3. 自动选择最佳镜像
    4. 故障自动切换
    """

    # 默认镜像配置
    DEFAULT_MIRRORS = {
        "github": MirrorEndpoint(
            name="GitHub",
            base_url="https://github.com",
            source_type="github",
            priority=1,
            timeout=8.0,
        ),
        "gitee": MirrorEndpoint(
            name="Gitee",
            base_url="https://gitee.com",
            source_type="github",  # 同类源
            priority=2,
            timeout=5.0,
        ),
        "aliyun_github": MirrorEndpoint(
            name="阿里云GitHub",
            base_url="https://hub.fastgit.xyz",
            source_type="github",
            priority=3,
            timeout=5.0,
        ),
        "ghproxy": MirrorEndpoint(
            name="GHProxy",
            base_url="https://ghproxy.com",
            source_type="github",
            priority=4,
            timeout=5.0,
        ),
        "tinghua_pypi": MirrorEndpoint(
            name="清华PyPI",
            base_url="https://pypi.tuna.tsinghua.edu.cn",
            source_type="pypi",
            priority=1,
            timeout=5.0,
        ),
        "aliyun_pypi": MirrorEndpoint(
            name="阿里云PyPI",
            base_url="https://mirrors.aliyun.com/pypi",
            source_type="pypi",
            priority=2,
            timeout=5.0,
        ),
        "tencent_pypi": MirrorEndpoint(
            name="腾讯云PyPI",
            base_url="https://mirrors.cloud.tencent.com/pypi",
            source_type="pypi",
            priority=3,
            timeout=5.0,
        ),
    }

    def __init__(
        self,
        config_dir: Path = None,
        config_file: Path = None,
    ):
        if config_dir is None:
            config_dir = Path.home() / ".hermes-desktop" / "upgrade_scanner"
        config_dir.mkdir(parents=True, exist_ok=True)

        if config_file is None:
            config_file = config_dir / "mirrors.json"

        self._config_file = config_file
        self._mirrors: Dict[str, MirrorEndpoint] = {}
        self._load_config()

    def _load_config(self):
        """加载配置"""
        if self._config_file.exists():
            try:
                data = json.loads(self._config_file.read_text(encoding="utf-8"))
                for k, v in data.items():
                    self._mirrors[k] = MirrorEndpoint(**v)
            except Exception:
                self._mirrors = self.DEFAULT_MIRRORS.copy()
        else:
            self._mirrors = self.DEFAULT_MIRRORS.copy()
            self._save_config()

    def _save_config(self):
        """保存配置"""
        try:
            data = {
                k: {
                    "name": v.name,
                    "base_url": v.base_url,
                    "source_type": v.source_type,
                    "priority": v.priority,
                    "timeout": v.timeout,
                    "enabled": v.enabled,
                    "health_score": v.health_score,
                    "success_count": v.success_count,
                    "failure_count": v.failure_count,
                    "last_check": v.last_check,
                    "last_success": v.last_success,
                }
                for k, v in self._mirrors.items()
            }
            self._config_file.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
        except Exception as e:
            logger.error(f"Failed to save mirror config: {e}")

    def get_mirrors(self, source_type: str = None, enabled_only: bool = True) -> List[MirrorEndpoint]:
        """获取镜像列表"""
        mirrors = []
        for m in self._mirrors.values():
            if enabled_only and not m.enabled:
                continue
            if source_type and m.source_type != source_type:
                continue
            mirrors.append(m)

        # 按优先级排序
        mirrors.sort(key=lambda x: x.priority)
        return mirrors

    def get_best_mirror(self, source_type: str = None) -> Optional[MirrorEndpoint]:
        """获取最佳镜像"""
        mirrors = self.get_mirrors(source_type)
        if not mirrors:
            return None

        # 按健康度和优先级综合排序
        def score(m: MirrorEndpoint) -> float:
            return m.health_score * (1.0 / m.priority)

        return max(mirrors, key=score)

    def record_success(self, mirror_key: str):
        """记录成功"""
        if mirror_key in self._mirrors:
            m = self._mirrors[mirror_key]
            m.success_count += 1
            m.last_success = int(time.time())
            m.health_score = self._calculate_health(m)
            self._save_config()

    def record_failure(self, mirror_key: str):
        """记录失败"""
        if mirror_key in self._mirrors:
            m = self._mirrors[mirror_key]
            m.failure_count += 1
            m.health_score = self._calculate_health(m)
            self._save_config()

    def _calculate_health(self, m: MirrorEndpoint) -> float:
        """计算健康评分"""
        total = m.success_count + m.failure_count
        if total == 0:
            return 1.0

        success_rate = m.success_count / total

        # 时间衰减
        time_factor = 1.0
        if m.last_check:
            age = time.time() - m.last_check
            if age > 3600:
                time_factor = 0.9
            elif age > 86400:
                time_factor = 0.7

        return success_rate * time_factor

    async def check_mirror_health(self, mirror_key: str) -> bool:
        """检查镜像健康状态"""
        if mirror_key not in self._mirrors:
            return False

        m = self._mirrors[mirror_key]
        m.last_check = int(time.time())

        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                start = time.time()
                async with session.get(
                    m.base_url,
                    timeout=aiohttp.ClientTimeout(total=m.timeout),
                ) as resp:
                    elapsed = time.time() - start
                    if resp.status == 200:
                        m.health_score = min(1.0, 1.0 / (elapsed / m.timeout + 0.1))
                        return True
                    else:
                        m.health_score *= 0.9
                        return False
        except Exception:
            m.health_score *= 0.8
            return False
        finally:
            self._save_config()

    async def check_all_mirrors(self) -> Dict[str, bool]:
        """检查所有镜像"""
        results = {}
        for key in self._mirrors:
            results[key] = await self.check_mirror_health(key)
        return results

    def add_mirror(
        self,
        key: str,
        name: str,
        base_url: str,
        source_type: str,
        priority: int = 10,
        timeout: float = 5.0,
    ) -> bool:
        """添加镜像"""
        try:
            self._mirrors[key] = MirrorEndpoint(
                name=name,
                base_url=base_url,
                source_type=source_type,
                priority=priority,
                timeout=timeout,
            )
            self._save_config()
            return True
        except Exception:
            return False

    def remove_mirror(self, key: str) -> bool:
        """移除镜像"""
        if key in self._mirrors:
            del self._mirrors[key]
            self._save_config()
            return True
        return False

    def enable_mirror(self, key: str):
        """启用镜像"""
        if key in self._mirrors:
            self._mirrors[key].enabled = True
            self._save_config()

    def disable_mirror(self, key: str):
        """禁用镜像"""
        if key in self._mirrors:
            self._mirrors[key].enabled = False
            self._save_config()


# ============ 多源下载器 ============

class MultiSourceDownloader:
    """
    多源下载器

    功能:
    1. 多镜像并行尝试
    2. 断点续传
    3. 自动选择最快源
    4. 速度限制保护
    """

    def __init__(
        self,
        config_manager: MirrorConfigManager = None,
        max_concurrent: int = 3,
        max_speed_bps: float = 0,  # 0 = 无限制
    ):
        self._config_manager = config_manager or MirrorConfigManager()
        self._max_concurrent = max_concurrent
        self._max_speed_bps = max_speed_bps
        self._downloads: Dict[str, DownloadTask] = {}
        self._download_dir = Path.home() / ".hermes-desktop" / "upgrade_scanner" / "downloads"
        self._download_dir.mkdir(parents=True, exist_ok=True)

    def _generate_task_id(self, url: str) -> str:
        """生成任务ID"""
        raw = f"{url}:{time.time()}"
        return hashlib.md5(raw.encode()).hexdigest()[:12]

    async def download(
        self,
        url: str,
        dest_path: Path = None,
        progress_callback: Callable = None,
    ) -> Optional[Path]:
        """
        下载文件

        Args:
            url: 源URL
            dest_path: 目标路径
            progress_callback: 进度回调

        Returns:
            Path: 下载后的文件路径
        """
        task_id = self._generate_task_id(url)
        if dest_path is None:
            dest_path = self._download_dir / Path(url.split("/")[-1]).name

        dest_path = Path(dest_path)
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        task = DownloadTask(
            id=task_id,
            source_url=url,
            dest_path=dest_path,
            status="running",
            started_at=int(time.time()),
        )
        self._downloads[task_id] = task

        try:
            # 确定源类型
            source_type = self._detect_source_type(url)
            mirrors = self._config_manager.get_mirrors(source_type)

            if not mirrors:
                # 没有镜像，直接下载
                mirrors = [None]

            # 并行尝试多个源
            downloaded = False
            for mirror in mirrors[:self._max_concurrent]:
                if downloaded:
                    break

                try:
                    if mirror:
                        download_url = self._convert_url(url, mirror.base_url)
                        mirror_key = list(self._config_manager._mirrors.keys())[
                            list(self._config_manager._mirrors.values()).index(mirror)
                        ]
                    else:
                        download_url = url
                        mirror_key = "direct"

                    result = await self._download_with_retry(
                        download_url,
                        dest_path,
                        task,
                        progress_callback,
                    )

                    if result:
                        if mirror:
                            self._config_manager.record_success(mirror_key)
                        task.status = "completed"
                        task.used_mirror = mirror_key
                        downloaded = True

                except Exception as e:
                    if mirror:
                        self._config_manager.record_failure(mirror_key)
                    task.error_message = str(e)
                    logger.warning(f"Download failed with mirror {mirror}: {e}")
                    continue

            if not downloaded:
                task.status = "failed"
                return None

            task.completed_at = int(time.time())
            return dest_path

        except Exception as e:
            task.status = "failed"
            task.error_message = str(e)
            logger.error(f"Download failed: {e}")
            return None

    def _detect_source_type(self, url: str) -> str:
        """检测源类型"""
        url_lower = url.lower()
        if "github.com" in url_lower:
            return "github"
        elif "gitee.com" in url_lower:
            return "github"  # 同类
        elif "pypi" in url_lower:
            return "pypi"
        else:
            return "github"  # 默认

    def _convert_url(self, original_url: str, mirror_base: str) -> str:
        """转换URL为镜像地址"""
        original_lower = original_url.lower()

        if "github.com" in original_lower:
            # GitHub URL 转换为镜像
            # 例如: https://github.com/user/repo/archive/refs/tags/v1.0.zip
            # 转换为: https://mirror.base/user/repo/archive/refs/tags/v1.0.zip
            return original_url.replace("https://github.com", mirror_base)

        return original_url

    async def _download_with_retry(
        self,
        url: str,
        dest_path: Path,
        task: DownloadTask,
        progress_callback: Callable,
        max_retries: int = 2,
    ) -> bool:
        """带重试的下载"""
        for attempt in range(max_retries):
            task.attempts += 1
            try:
                return await self._do_download(url, dest_path, task, progress_callback)
            except Exception as e:
                if attempt == max_retries - 1:
                    raise e
                await asyncio.sleep(1 * (attempt + 1))  # 指数退避

        return False

    async def _do_download(
        self,
        url: str,
        dest_path: Path,
        task: DownloadTask,
        progress_callback: Callable,
    ) -> bool:
        """执行下载"""
        import aiohttp

        # 检查是否支持断点续传
        resume_header = {}
        temp_path = dest_path.with_suffix(dest_path.suffix + ".tmp")

        if temp_path.exists():
            task.bytes_downloaded = temp_path.stat().st_size
            resume_header["Range"] = f"bytes={task.bytes_downloaded}-"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers=resume_header if resume_header else None,
                    timeout=aiohttp.ClientTimeout(total=300),
                ) as resp:
                    if resp.status not in (200, 206):
                        raise Exception(f"HTTP {resp.status}")

                    # 获取总大小
                    if resp.headers.get("Content-Length"):
                        task.total_bytes = int(resp.headers["Content-Length"])
                        if resume_header:
                            task.total_bytes += task.bytes_downloaded

                    # 流式写入
                    mode = "ab" if resume_header else "wb"
                    with open(temp_path, mode) as f:
                        chunk_size = 8192
                        downloaded = task.bytes_downloaded
                        last_update = time.time()

                        async for chunk in resp.content.iter_chunked(chunk_size):
                            f.write(chunk)
                            downloaded += len(chunk)
                            task.bytes_downloaded = downloaded

                            # 更新进度
                            if task.total_bytes > 0:
                                task.progress = downloaded / task.total_bytes

                            # 计算速度
                            elapsed = time.time() - last_update
                            if elapsed > 0:
                                task.speed_bps = len(chunk) / elapsed

                            # 限速
                            if self._max_speed_bps > 0:
                                expected_time = len(chunk) / self._max_speed_bps
                                if elapsed < expected_time:
                                    await asyncio.sleep(expected_time - elapsed)

                            # 回调
                            if progress_callback:
                                progress_callback(task)

                    # 重命名
                    if temp_path.exists():
                        temp_path.rename(dest_path)

                    return True

        except Exception as e:
            # 清理临时文件
            if temp_path.exists() and task.bytes_downloaded == 0:
                temp_path.unlink()
            raise e

    def get_task(self, task_id: str) -> Optional[DownloadTask]:
        """获取任务"""
        return self._downloads.get(task_id)

    def get_all_tasks(self) -> List[DownloadTask]:
        """获取所有任务"""
        return list(self._downloads.values())

    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        if task_id in self._downloads:
            self._downloads[task_id].status = "cancelled"
            return True
        return False


# ============ GitHub下载加速器 ============

class GitHubAccelerator:
    """
    GitHub下载加速器

    功能:
    1. 自动选择最优GitHub镜像
    2. 支持 releases / archives / raw 下载
    """

    RELEASE_MIRRORS = [
        "https://github.com",
        "https://hub.fastgit.xyz",
        "https://ghproxy.com/https://github.com",
        "https://mirror.ghproxy.com/https://github.com",
    ]

    def __init__(
        self,
        config_manager: MirrorConfigManager = None,
    ):
        self._config_manager = config_manager or MirrorConfigManager()
        self._downloader = MultiSourceDownloader(config_manager)

    def get_fastest_url(self, original_url: str) -> str:
        """
        获取最快访问URL

        Args:
            original_url: 原始GitHub URL

        Returns:
            str: 加速后的URL
        """
        # 获取最佳镜像
        mirror = self._config_manager.get_best_mirror("github")
        if not mirror:
            return original_url

        # 转换为镜像URL
        if "github.com" in original_url:
            return original_url.replace("https://github.com", mirror.base_url)

        return original_url

    async def download_release(
        self,
        repo: str,  # "owner/repo"
        tag: str,
        filename: str,
        dest_dir: Path = None,
    ) -> Optional[Path]:
        """
        下载Release文件

        Args:
            repo: 仓库 (owner/repo)
            tag: 版本标签
            filename: 文件名
            dest_dir: 目标目录

        Returns:
            Path: 下载后的文件路径
        """
        url = f"https://github.com/{repo}/releases/download/{tag}/{filename}"

        if dest_dir is None:
            dest_dir = self._download_dir

        return await self._downloader.download(url, dest_dir / filename)

    async def download_archive(
        self,
        repo: str,
        ref: str = "main",
        format: str = "zip",
        dest_path: Path = None,
    ) -> Optional[Path]:
        """
        下载仓库归档

        Args:
            repo: 仓库
            ref: 分支或tag
            format: zip 或 tarball
            dest_path: 目标路径

        Returns:
            Path: 下载后的文件路径
        """
        if format == "zip":
            url = f"https://github.com/{repo}/archive/refs/heads/{ref}.zip"
        else:
            url = f"https://github.com/{repo}/archive/refs/heads/{ref}.tar.gz"

        if dest_path is None:
            dest_path = self._download_dir / f"{repo.replace('/', '_')}_{ref}.{format}"

        return await self._downloader.download(url, dest_path)

    async def download_raw(
        self,
        repo: str,
        path: str,
        ref: str = "main",
        dest_path: Path = None,
    ) -> Optional[Path]:
        """
        下载原始文件

        Args:
            repo: 仓库
            path: 文件路径
            ref: 分支或tag
            dest_path: 目标路径

        Returns:
            Path: 下载后的文件路径
        """
        url = f"https://raw.githubusercontent.com/{repo}/{ref}/{path}"

        if dest_path is None:
            dest_path = self._download_dir / Path(path).name

        return await self._downloader.download(url, dest_path)


# ============ 全局实例 ============

_config_manager: Optional[MirrorConfigManager] = None
_downloader: Optional[MultiSourceDownloader] = None
_github_accelerator: Optional[GitHubAccelerator] = None


def get_mirror_config_manager() -> MirrorConfigManager:
    """获取镜像配置管理器"""
    global _config_manager
    if _config_manager is None:
        _config_manager = MirrorConfigManager()
    return _config_manager


def get_downloader() -> MultiSourceDownloader:
    """获取下载器"""
    global _downloader
    if _downloader is None:
        _downloader = MultiSourceDownloader(get_mirror_config_manager())
    return _downloader


def get_github_accelerator() -> GitHubAccelerator:
    """获取GitHub加速器"""
    global _github_accelerator
    if _github_accelerator is None:
        _github_accelerator = GitHubAccelerator(get_mirror_config_manager())
    return _github_accelerator
