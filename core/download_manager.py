"""
文件下载管理器
支持断点续传、进度跟踪、自动保存到项目目录
"""

import os
import time
import asyncio
import hashlib
from pathlib import Path
from typing import Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import traceback

import httpx


class DownloadStatus(Enum):
    """下载状态"""
    PENDING = "pending"
    DOWNLOADING = "downloading"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class DownloadTask:
    """下载任务"""
    id: str
    url: str
    filename: str
    save_path: Path
    file_type: str
    
    # 进度
    total_size: int = 0
    downloaded_size: int = 0
    progress: float = 0.0  # 0-100
    
    # 状态
    status: DownloadStatus = DownloadStatus.PENDING
    error: Optional[str] = None
    
    # 断点续传
    resume_offset: int = 0
    
    # 元数据
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    source: str = ""  # 来源网站
    
    # 速度统计
    speed: float = 0.0  # bytes/s
    start_time: float = 0.0
    last_update_time: float = 0.0


class DownloadManager:
    """
    文件下载管理器
    
    特性：
    - 断点续传
    - 多线程并发下载（可选）
    - 进度回调
    - 自动重试
    - 下载历史记录
    """
    
    # 默认下载目录
    DEFAULT_DOWNLOAD_DIR = Path.home() / ".hermes-desktop" / "downloads"
    
    # 支持的文件类型图标
    FILE_ICONS = {
        "pdf": "📄",
        "doc": "📝",
        "docx": "📝",
        "xlsx": "📊",
        "xls": "📊",
        "ppt": "📽️",
        "pptx": "📽️",
        "zip": "📦",
        "rar": "📦",
        "txt": "📃",
        "html": "🌐",
        "json": "📋",
        "csv": "📈",
        "file": "📁",
    }
    
    def __init__(
        self,
        download_dir: Optional[str] = None,
        max_concurrent: int = 3,
        chunk_size: int = 8192,
        timeout: int = 60,
        max_retries: int = 3,
    ):
        """
        初始化下载管理器
        
        Args:
            download_dir: 下载目录（默认 ~/.hermes-desktop/downloads）
            max_concurrent: 最大并发下载数
            chunk_size: 每次读取的块大小
            timeout: 超时时间（秒）
            max_retries: 最大重试次数
        """
        self.download_dir = Path(download_dir) if download_dir else self.DEFAULT_DOWNLOAD_DIR
        self.download_dir.mkdir(parents=True, exist_ok=True)
        
        self.max_concurrent = max_concurrent
        self.chunk_size = chunk_size
        self.timeout = timeout
        self.max_retries = max_retries
        
        # 下载任务存储
        self.tasks: dict[str, DownloadTask] = {}
        
        # 进度回调
        self._progress_callbacks: list[Callable[[DownloadTask], None]] = []
        
        # 信号量控制并发
        self._semaphore = asyncio.Semaphore(max_concurrent)
        
        # 正在下载的协程
        self._download_coroutines: dict[str, asyncio.Task] = {}
    
    def set_download_dir(self, path: str) -> None:
        """设置下载目录"""
        self.download_dir = Path(path)
        self.download_dir.mkdir(parents=True, exist_ok=True)
    
    def get_download_dir(self) -> Path:
        """获取下载目录"""
        return self.download_dir
    
    def generate_task_id(self, url: str) -> str:
        """生成任务ID"""
        return hashlib.md5(url.encode()).hexdigest()[:12]
    
    def guess_filename(self, url: str, content_disposition: Optional[str] = None) -> str:
        """
        从URL或Content-Disposition猜测文件名
        
        Args:
            url: 下载URL
            content_disposition: HTTP头中的文件名
            
        Returns:
            str: 文件名
        """
        # 优先从 Content-Disposition 获取
        if content_disposition:
            import re
            match = re.search(r'filename[^;=\n]*=(?:(\\?[\'"]?)([^\'\"]*)\1|[^;\n]*)', content_disposition)
            if match:
                return match.group(2) or "download"
        
        # 从URL提取
        url_path = url.split("?")[0].split("#")[0]
        filename = os.path.basename(url_path)
        
        if filename and "." in filename:
            return filename
        
        # 默认文件名
        return f"download_{int(time.time())}"
    
    def guess_file_type(self, filename: str) -> str:
        """从文件名猜测文件类型"""
        ext = os.path.splitext(filename)[1].lower().lstrip(".")
        
        type_map = {
            "pdf": "pdf",
            "doc": "doc",
            "docx": "docx",
            "xls": "xlsx",
            "xlsx": "xlsx",
            "ppt": "ppt",
            "pptx": "pptx",
            "zip": "zip",
            "rar": "rar",
            "7z": "7z",
            "tar": "tar",
            "gz": "gz",
            "txt": "txt",
            "html": "html",
            "htm": "html",
            "json": "json",
            "xml": "xml",
            "csv": "csv",
        }
        
        return type_map.get(ext, "file")
    
    def on_progress(self, callback: Callable[[DownloadTask], None]) -> None:
        """注册进度回调"""
        self._progress_callbacks.append(callback)
    
    def _notify_progress(self, task: DownloadTask) -> None:
        """通知进度更新"""
        for callback in self._progress_callbacks:
            try:
                callback(task)
            except Exception as e:
                logger.info(f"[DownloadManager] Progress callback error: {e}")
    
    async def download(
        self,
        url: str,
        filename: Optional[str] = None,
        save_dir: Optional[str] = None,
        resume: bool = True,
        source: str = "",
        **kwargs
    ) -> DownloadTask:
        """
        添加下载任务
        
        Args:
            url: 下载URL
            filename: 指定文件名（可选）
            save_dir: 保存目录（可选，默认使用配置的下载目录）
            resume: 是否支持断点续传
            source: 来源网站
            
        Returns:
            DownloadTask: 下载任务
        """
        # 生成任务ID
        task_id = self.generate_task_id(url)
        
        # 如果任务已存在且正在下载，返回现有任务
        if task_id in self.tasks:
            if self.tasks[task_id].status == DownloadStatus.DOWNLOADING:
                return self.tasks[task_id]
        
        # 确定保存路径
        if filename is None:
            filename = self.guess_filename(url)
        
        save_dir_path = Path(save_dir) if save_dir else self.download_dir
        save_dir_path.mkdir(parents=True, exist_ok=True)
        save_path = save_dir_path / filename
        
        # 创建任务
        task = DownloadTask(
            id=task_id,
            url=url,
            filename=filename,
            save_path=save_path,
            file_type=self.guess_file_type(filename),
            source=source,
        )
        
        # 检查已下载的大小（断点续传）
        if resume and save_path.exists():
            task.resume_offset = save_path.stat().st_size
            task.downloaded_size = task.resume_offset
        
        self.tasks[task_id] = task
        
        # 启动下载协程
        coro = self._run_download(task, resume)
        self._download_coroutines[task_id] = asyncio.create_task(coro)
        
        return task
    
    async def _run_download(self, task: DownloadTask, resume: bool) -> None:
        """执行下载"""
        async with self._semaphore:  # 控制并发
            await self._do_download(task, resume)
    
    async def _do_download(self, task: DownloadTask, resume: bool) -> None:
        """执行单次下载（可能重试）"""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        # 断点续传：添加 Range 头
        if resume and task.resume_offset > 0:
            headers["Range"] = f"bytes={task.resume_offset}-"
        
        for attempt in range(self.max_retries):
            try:
                task.status = DownloadStatus.DOWNLOADING
                task.start_time = time.time()
                self._notify_progress(task)
                
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    # 发起请求
                    if resume and task.resume_offset > 0:
                        r = await client.get(
                            task.url,
                            headers=headers,
                            follow_redirects=True
                        )
                        # 部分内容响应
                        if r.status_code not in (200, 206):
                            r = await client.get(task.url, follow_redirects=True)
                            task.resume_offset = 0  # 不支持续传，重新开始
                    else:
                        r = await client.get(task.url, headers=headers, follow_redirects=True)
                        r.raise_for_status()
                    
                    # 获取总大小
                    content_length = r.headers.get("content-length")
                    if content_length:
                        total_size = int(content_length)
                        if task.resume_offset > 0:
                            total_size += task.resume_offset
                        task.total_size = total_size
                    
                    # 更新文件名（如果服务器返回不同的文件名）
                    content_disp = r.headers.get("content-disposition")
                    if content_disp:
                        new_filename = self.guess_filename(task.url, content_disp)
                        if new_filename != task.filename:
                            task.filename = new_filename
                            task.save_path = task.save_path.parent / new_filename
                            task.file_type = self.guess_file_type(new_filename)
                    
                    # 打开文件（追加模式用于断点续传）
                    mode = "ab" if task.resume_offset > 0 else "wb"
                    
                    with open(task.save_path, mode) as f:
                        last_update = time.time()
                        chunk_count = 0
                        
                        async for chunk in r.aiter_bytes(chunk_size=self.chunk_size):
                            # 检查是否被取消
                            if task.id in self._download_coroutines:
                                if self._download_coroutines[task.id].cancelled():
                                    task.status = DownloadStatus.CANCELLED
                                    return
                            
                            f.write(chunk)
                            task.downloaded_size += len(chunk)
                            chunk_count += 1
                            
                            # 更新进度（每秒最多更新10次）
                            now = time.time()
                            if now - last_update >= 0.1 or chunk_count % 100 == 0:
                                if task.total_size > 0:
                                    task.progress = (task.downloaded_size / task.total_size) * 100
                                
                                # 计算速度
                                elapsed = now - task.start_time
                                if elapsed > 0:
                                    task.speed = task.downloaded_size / elapsed
                                
                                task.last_update_time = now
                                self._notify_progress(task)
                                last_update = now
                    
                    # 下载完成
                    task.status = DownloadStatus.COMPLETED
                    task.completed_at = datetime.now().isoformat()
                    task.progress = 100.0
                    task.speed = task.downloaded_size / (time.time() - task.start_time)
                    self._notify_progress(task)
                    
                    # 清理协程引用
                    if task.id in self._download_coroutines:
                        del self._download_coroutines[task.id]
                    
                    return
                    
            except asyncio.CancelledError:
                task.status = DownloadStatus.PAUSED
                self._notify_progress(task)
                raise
                
            except Exception as e:
                task.error = str(e)
                task.status = DownloadStatus.FAILED
                
                if attempt < self.max_retries - 1:
                    # 重试前等待
                    await asyncio.sleep(2 ** attempt)
                    task.status = DownloadStatus.PENDING
                else:
                    self._notify_progress(task)
                    # 清理协程引用
                    if task.id in self._download_coroutines:
                        del self._download_coroutines[task.id]
    
    def pause(self, task_id: str) -> bool:
        """暂停下载"""
        if task_id in self._download_coroutines:
            self._download_coroutines[task_id].cancel()
            if task_id in self.tasks:
                self.tasks[task_id].status = DownloadStatus.PAUSED
            return True
        return False
    
    def cancel(self, task_id: str) -> bool:
        """取消下载"""
        if task_id in self._download_coroutines:
            self._download_coroutines[task_id].cancel()
        
        if task_id in self.tasks:
            task = self.tasks[task_id]
            task.status = DownloadStatus.CANCELLED
            
            # 删除部分下载的文件
            if task.save_path.exists() and task.downloaded_size > 0:
                try:
                    task.save_path.unlink()
                except Exception:
                    pass
            
            return True
        return False
    
    def resume(self, task_id: str) -> bool:
        """恢复下载"""
        if task_id not in self.tasks:
            return False
        
        task = self.tasks[task_id]
        if task.status not in (DownloadStatus.PAUSED, DownloadStatus.FAILED):
            return False
        
        # 重新启动下载协程
        coro = self._run_download(task, resume=True)
        self._download_coroutines[task_id] = asyncio.create_task(coro)
        return True
    
    def retry(self, task_id: str) -> bool:
        """重试下载"""
        if task_id not in self.tasks:
            return False
        
        task = self.tasks[task_id]
        task.error = None
        task.status = DownloadStatus.PENDING
        task.resume_offset = 0
        task.downloaded_size = 0
        task.progress = 0
        
        # 删除旧文件
        if task.save_path.exists():
            try:
                task.save_path.unlink()
            except Exception:
                pass
        
        # 重新启动下载
        coro = self._run_download(task, resume=False)
        self._download_coroutines[task_id] = asyncio.create_task(coro)
        return True
    
    def get_task(self, task_id: str) -> Optional[DownloadTask]:
        """获取任务"""
        return self.tasks.get(task_id)
    
    def get_all_tasks(self) -> list[DownloadTask]:
        """获取所有任务"""
        return list(self.tasks.values())
    
    def get_tasks_by_status(self, status: DownloadStatus) -> list[DownloadTask]:
        """按状态筛选任务"""
        return [t for t in self.tasks.values() if t.status == status]
    
    def get_downloads_in_dir(self) -> list[Path]:
        """获取下载目录中的所有文件"""
        if not self.download_dir.exists():
            return []
        
        files = []
        for f in self.download_dir.iterdir():
            if f.is_file():
                files.append(f)
        
        return sorted(files, key=lambda x: x.stat().st_mtime, reverse=True)
    
    def open_download_dir(self) -> None:
        """打开下载目录"""
        import platform
        import subprocess
from core.logger import get_logger
logger = get_logger('download_manager')

        
        path = str(self.download_dir)
        
        if platform.system() == "Windows":
            os.startfile(path)
        elif platform.system() == "Darwin":
            subprocess.run(["open", path])
        else:
            subprocess.run(["xdg-open", path])
    
    def format_speed(self, speed: float) -> str:
        """格式化速度显示"""
        if speed >= 1024 * 1024:
            return f"{speed / (1024 * 1024):.1f} MB/s"
        elif speed >= 1024:
            return f"{speed / 1024:.1f} KB/s"
        return f"{speed:.0f} B/s"
    
    def format_size(self, size: int) -> str:
        """格式化文件大小"""
        if size >= 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024 * 1024):.2f} GB"
        elif size >= 1024 * 1024:
            return f"{size / (1024 * 1024):.2f} MB"
        elif size >= 1024:
            return f"{size / 1024:.2f} KB"
        return f"{size} B"
    
    def get_file_icon(self, file_type: str) -> str:
        """获取文件类型图标"""
        return self.FILE_ICONS.get(file_type.lower(), self.FILE_ICONS["file"])


# ── 快捷函数 ─────────────────────────────────────────────────────────────────

_async_download_manager: Optional[DownloadManager] = None


def get_download_manager() -> DownloadManager:
    """获取全局下载管理器实例"""
    global _async_download_manager
    if _async_download_manager is None:
        _async_download_manager = DownloadManager()
    return _async_download_manager


# ── 导出 ─────────────────────────────────────────────────────────────────────

__all__ = [
    "DownloadManager",
    "DownloadTask",
    "DownloadStatus",
    "get_download_manager",
]
