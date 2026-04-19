# -*- coding: utf-8 -*-
"""
统一下载中心
Unified Download Center

核心理念：
1. 单一数据源：所有下载任务统一管理
2. 断点续传：基于 HTTP Range 头
3. 进度实时反馈：信号/回调机制
4. 暂停/恢复/取消：支持中途操作
5. 多源支持：HTTP、HuggingFace、ModelScope、GitHub

支持的文件类型：
- 模型文件 (.gguf, .bin, .safetensors)
- 工具安装包 (.exe, .msi, .deb, .rpm, .appimage)
- 文档 (.pdf, .docx, .xlsx)
- 压缩包 (.zip, .tar, .gz)
"""

import os
import json
import time
import asyncio
import hashlib
import traceback
import threading
from pathlib import Path
from typing import Optional, Callable, Dict, Any, List
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from functools import lru_cache
import logging

import httpx

logger = logging.getLogger(__name__)


class ConnectionStatus(Enum):
    """连接状态"""
    IDLE = "idle"                   # 空闲/未开始
    CONNECTING = "connecting"       # 正在连接
    CONNECTED = "connected"         # 已连接
    DOWNLOADING = "downloading"     # 下载中（已合并到DownloadStatus）
    DISCONNECTED = "disconnected"   # 断开
    ERROR = "error"                 # 连接错误


class DownloadStatus(Enum):
    """下载状态"""
    PENDING = "pending"          # 等待中
    DOWNLOADING = "downloading"  # 下载中
    PAUSED = "paused"            # 已暂停
    COMPLETED = "completed"       # 已完成
    FAILED = "failed"            # 失败
    CANCELLED = "cancelled"      # 已取消


class SourceType(Enum):
    """下载来源类型"""
    HTTP = "http"                 # 普通HTTP/HTTPS
    HUGGINGFACE = "huggingface"  # HuggingFace
    MODELSCOPE = "modelscope"    # ModelScope
    GITHUB = "github"            # GitHub Release


@dataclass
class DownloadTask:
    """下载任务"""
    id: str                      # 任务ID (MD5)
    url: str                     # 下载URL
    filename: str               # 文件名
    save_path: Path              # 保存路径

    # 来源信息
    source: SourceType = SourceType.HTTP
    source_info: str = ""        # 来源详情（如 repo_id）

    # 进度
    total_size: int = 0          # 总大小（字节）
    downloaded_size: int = 0      # 已下载（字节）
    progress: float = 0.0         # 进度百分比 0-100

    # 状态
    status: DownloadStatus = DownloadStatus.PENDING
    error: Optional[str] = None  # 错误信息

    # ═══════════════════════════════════════════════════════════
    # 连接状态信息（下载地址 + 连接状态）
    # ═══════════════════════════════════════════════════════════
    connection_status: ConnectionStatus = ConnectionStatus.IDLE  # 连接状态
    response_code: int = 0            # HTTP 响应码
    response_headers: Dict[str, str] = field(default_factory=dict)  # 响应头
    content_type: str = ""            # Content-Type
    content_disposition: str = ""     # Content-Disposition
    server: str = ""                  # Server 头
    accept_ranges: str = ""          # Accept-Ranges 头（是否支持断点续传）
    etag: str = ""                   # ETag
    last_modified: str = ""           # Last-Modified
    connection_error: Optional[str] = None  # 连接错误详情
    redirect_count: int = 0          # 重定向次数
    local_ip: str = ""                # 本地连接IP
    # ═══════════════════════════════════════════════════════════

    # 断点续传
    resume_offset: int = 0       # 断点偏移
    cache_file: Optional[Path] = None  # 缓存文件路径

    # 元数据
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    # 速度统计
    speed: float = 0.0            # bytes/s
    avg_speed: float = 0.0       # 平均速度
    start_time: float = 0.0
    last_update_time: float = 0.0
    chunk_count: int = 0          # 已下载块数

    # 校验
    expected_hash: str = ""       # 期望的 SHA256
    actual_hash: str = ""          # 实际 SHA256

    # 回调
    progress_callback: Optional[Callable] = None
    done_callback: Optional[Callable] = None

    @property
    def connection_status_text(self) -> str:
        """连接状态文本"""
        status_map = {
            ConnectionStatus.IDLE: "等待连接",
            ConnectionStatus.CONNECTING: "正在连接...",
            ConnectionStatus.CONNECTED: "已连接",
            ConnectionStatus.DISCONNECTED: "已断开",
            ConnectionStatus.ERROR: "连接错误",
        }
        return status_map.get(self.connection_status, "未知")

    @property
    def connection_info(self) -> str:
        """完整的连接信息（用于UI显示）"""
        parts = []
        if self.response_code:
            parts.append(f"HTTP {self.response_code}")
        if self.server:
            parts.append(f"Server: {self.server[:20]}")
        if self.accept_ranges:
            parts.append(f"Range: {self.accept_ranges}")
        return " | ".join(parts) if parts else self.connection_status_text

    @property
    def speed_str(self) -> str:
        """格式化速度"""
        if self.speed >= 1024 * 1024:
            return f"{self.speed / (1024 * 1024):.1f} MB/s"
        elif self.speed >= 1024:
            return f"{self.speed / 1024:.1f} KB/s"
        return f"{self.speed:.0f} B/s"

    @property
    def size_str(self) -> str:
        """格式化大小"""
        def fmt(size):
            if size >= 1024 * 1024 * 1024:
                return f"{size / (1024**3):.2f} GB"
            elif size >= 1024 * 1024:
                return f"{size / (1024**2):.2f} MB"
            elif size >= 1024:
                return f"{size / 1024:.2f} KB"
            return f"{size} B"
        downloaded = fmt(self.downloaded_size)
        total = fmt(self.total_size) if self.total_size else "?"
        return f"{downloaded} / {total}"

    @property
    def eta_str(self) -> str:
        """预估剩余时间"""
        if self.speed <= 0 or self.total_size == 0:
            return "计算中..."
        remaining = self.total_size - self.downloaded_size
        seconds = remaining / self.speed
        if seconds < 60:
            return f"约 {int(seconds)} 秒"
        elif seconds < 3600:
            return f"约 {int(seconds/60)} 分 {int(seconds%60)} 秒"
        return f"约 {int(seconds/3600)} 小时 {int((seconds%3600)/60)} 分"

    def to_dict(self) -> dict:
        """转为字典"""
        d = asdict(self)
        d['save_path'] = str(self.save_path)
        d['cache_file'] = str(self.cache_file) if self.cache_file else None
        d['status'] = self.status.value
        d['source'] = self.source.value
        d['connection_status'] = self.connection_status.value
        d['connection_status_text'] = self.connection_status_text
        d['connection_info'] = self.connection_info
        return d


class DownloadCenter:
    """
    统一下载中心

    特性：
    - 单例模式，全局唯一
    - 断点续传（HTTP Range）
    - 多线程并发控制
    - 实时进度回调
    - 暂停/恢复/取消
    - SHA256 校验
    - 任务持久化

    使用示例：
    >>> center = DownloadCenter()
    >>> task = center.create_task(url, save_path)
    >>> center.start(task.id)
    >>> # 或使用快捷函数
    >>> from core.unified_downloader import download_file
    >>> download_file(url, save_path, on_progress=callback)
    """

    _instance: Optional['DownloadCenter'] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    # 不设置 _initialized 标志，让 __init__ 每次都执行
        return cls._instance

    def __init__(
        self,
        download_dir: Optional[str] = None,
        max_concurrent: int = 3,
        chunk_size: int = 64 * 1024,  # 64KB 块
        timeout: int = 300,
        max_retries: int = 3,
    ):
        # 配置
        self.download_dir = Path(download_dir) if download_dir else Path.home() / ".hermes-desktop" / "downloads"
        self.download_dir.mkdir(parents=True, exist_ok=True)

        self.max_concurrent = max_concurrent
        self.chunk_size = chunk_size
        self.timeout = timeout
        self.max_retries = max_retries

        # 任务存储
        if not hasattr(self, '_tasks'):
            self._tasks: Dict[str, DownloadTask] = {}
        if not hasattr(self, '_threads'):
            self._threads: Dict[str, threading.Thread] = {}
        if not hasattr(self, '_stop_events'):
            self._stop_events: Dict[str, threading.Event] = {}
        if not hasattr(self, '_paused_events'):
            self._paused_events: Dict[str, threading.Event] = {}

        # 并发控制
        if not hasattr(self, '_semaphore'):
            self._semaphore = threading.Semaphore(max_concurrent)
        if not hasattr(self, '_task_lock'):
            self._task_lock = threading.Lock()

        # 进度回调
        if not hasattr(self, '_global_progress_callbacks'):
            self._global_progress_callbacks: List[Callable[[DownloadTask], None]] = []

        logger.info(f"DownloadCenter 初始化完成 | 下载目录: {self.download_dir}")

    # ── 任务管理 ────────────────────────────────────────────────────────

    def create_task(
        self,
        url: str,
        save_path: str | Path,
        source: SourceType = SourceType.HTTP,
        source_info: str = "",
        filename: Optional[str] = None,
        expected_size: int = 0,
        expected_hash: str = "",
        progress_callback: Optional[Callable[[DownloadTask], None]] = None,
        done_callback: Optional[Callable[[DownloadTask], None]] = None,
        resume: bool = True,
    ) -> DownloadTask:
        """
        创建下载任务

        Args:
            url: 下载URL
            save_path: 保存路径（目录或完整文件路径）
            source: 来源类型
            source_info: 来源详情（如 repo_id）
            filename: 指定文件名（可选，从URL推断）
            expected_size: 期望的文件大小
            expected_hash: 期望的 SHA256
            progress_callback: 进度回调
            done_callback: 完成回调
            resume: 是否支持断点续传

        Returns:
            DownloadTask: 创建的任务
        """
        save_path = Path(save_path)

        # 如果是目录，拼接文件名
        if save_path.is_dir():
            name = filename or self._guess_filename(url)
            save_path = save_path / name

        # 生成任务ID（基于URL）
        task_id = self._generate_task_id(url)

        # 检查是否已存在
        if task_id in self._tasks and resume:
            existing = self._tasks[task_id]
            # 如果已完成或正在下载，返回现有任务
            if existing.status in (DownloadStatus.COMPLETED, DownloadStatus.DOWNLOADING):
                return existing
            # 否则重新开始
            existing.status = DownloadStatus.PENDING
            existing.error = None
            return existing

        # 创建缓存文件
        cache_dir = self.download_dir / ".cache"
        cache_dir.mkdir(exist_ok=True)
        cache_file = cache_dir / f"{task_id}.cache"

        # 检查断点
        resume_offset = 0
        if resume and save_path.exists():
            if cache_file.exists():
                try:
                    data = json.loads(cache_file.read_text(encoding="utf-8"))
                    resume_offset = data.get("downloaded", 0)
                    if resume_offset >= save_path.stat().st_size:
                        resume_offset = 0  # 文件可能已损坏，重新开始
                except Exception:
                    pass
            else:
                resume_offset = save_path.stat().st_size

        # 创建任务
        task = DownloadTask(
            id=task_id,
            url=url,
            filename=save_path.name,
            save_path=save_path,
            source=source,
            source_info=source_info,
            total_size=expected_size,
            resume_offset=resume_offset,
            cache_file=cache_file,
            expected_hash=expected_hash,
            progress_callback=progress_callback,
            done_callback=done_callback,
            status=DownloadStatus.PENDING,
        )

        if resume_offset > 0:
            task.downloaded_size = resume_offset
            if task.total_size > 0:
                task.progress = (resume_offset / task.total_size) * 100

        self._tasks[task_id] = task
        logger.info(f"创建下载任务: {task.filename} ({task.size_str})")

        return task

    def start(self, task_id: str, blocking: bool = False) -> bool:
        """
        启动下载任务

        Args:
            task_id: 任务ID
            blocking: 是否阻塞等待

        Returns:
            bool: 是否成功启动
        """
        if task_id not in self._tasks:
            logger.warning(f"任务不存在: {task_id}")
            return False

        task = self._tasks[task_id]

        if task.status == DownloadStatus.DOWNLOADING:
            logger.info(f"任务已在下载中: {task_id}")
            return True

        # 创建停止事件
        self._stop_events[task_id] = threading.Event()
        self._paused_events[task_id] = threading.Event()

        # 启动下载线程
        thread = threading.Thread(
            target=self._download_worker,
            args=(task_id,),
            daemon=True,
            name=f"Download-{task.filename[:20]}",
        )
        self._threads[task_id] = thread
        thread.start()

        if blocking:
            thread.join()

        return True

    def pause(self, task_id: str) -> bool:
        """暂停下载"""
        if task_id not in self._paused_events:
            return False

        self._paused_events[task_id].set()
        if task_id in self._tasks:
            self._tasks[task_id].status = DownloadStatus.PAUSED
            self._notify_progress(self._tasks[task_id])
        logger.info(f"暂停下载: {task_id}")
        return True

    def resume(self, task_id: str) -> bool:
        """恢复下载"""
        if task_id not in self._paused_events:
            return False

        self._paused_events[task_id].clear()
        if task_id in self._tasks:
            self._tasks[task_id].status = DownloadStatus.DOWNLOADING
            self._notify_progress(self._tasks[task_id])
        logger.info(f"恢复下载: {task_id}")
        return True

    def cancel(self, task_id: str) -> bool:
        """取消下载"""
        if task_id in self._stop_events:
            self._stop_events[task_id].set()

        if task_id in self._threads:
            try:
                self._threads[task_id].join(timeout=2)
            except Exception:
                pass
            del self._threads[task_id]

        if task_id in self._tasks:
            task = self._tasks[task_id]
            task.status = DownloadStatus.CANCELLED

            # 删除部分下载的文件
            if task.save_path.exists() and task.downloaded_size > 0:
                try:
                    task.save_path.unlink()
                except Exception:
                    pass

            # 删除缓存
            if task.cache_file and task.cache_file.exists():
                try:
                    task.cache_file.unlink()
                except Exception:
                    pass

            self._notify_progress(task)
            logger.info(f"取消下载: {task_id}")

        return True

    def retry(self, task_id: str) -> bool:
        """重试下载"""
        if task_id not in self._tasks:
            return False

        task = self._tasks[task_id]
        task.error = None
        task.status = DownloadStatus.PENDING
        task.resume_offset = 0
        task.downloaded_size = 0
        task.progress = 0
        task.speed = 0

        # 删除旧文件
        if task.save_path.exists():
            try:
                task.save_path.unlink()
            except Exception:
                pass

        return self.start(task_id)

    def remove(self, task_id: str) -> bool:
        """移除任务（从列表中删除）"""
        if task_id in self._tasks:
            self.cancel(task_id)
            del self._tasks[task_id]
        return True

    def get_task(self, task_id: str) -> Optional[DownloadTask]:
        """获取任务"""
        return self._tasks.get(task_id)

    def get_all_tasks(self) -> List[DownloadTask]:
        """获取所有任务"""
        return list(self._tasks.values())

    def get_tasks_by_status(self, status: DownloadStatus) -> List[DownloadTask]:
        """按状态筛选任务"""
        return [t for t in self._tasks.values() if t.status == status]

    def get_tasks_by_source(self, source: SourceType) -> List[DownloadTask]:
        """按来源筛选任务"""
        return [t for t in self._tasks.values() if t.source == source]

    # ── 全局回调 ────────────────────────────────────────────────────────

    def on_progress(self, callback: Callable[[DownloadTask], None]) -> None:
        """注册全局进度回调"""
        self._global_progress_callbacks.append(callback)

    def _notify_progress(self, task: DownloadTask) -> None:
        """通知进度更新"""
        # 调用任务自己的回调
        if task.progress_callback:
            try:
                task.progress_callback(task)
            except Exception as e:
                logger.error(f"进度回调错误: {e}")

        # 调用全局回调
        for callback in self._global_progress_callbacks:
            try:
                callback(task)
            except Exception as e:
                logger.error(f"全局进度回调错误: {e}")

    def _notify_done(self, task: DownloadTask) -> None:
        """通知完成"""
        if task.done_callback:
            try:
                task.done_callback(task)
            except Exception as e:
                logger.error(f"完成回调错误: {e}")

    # ── 核心下载逻辑 ────────────────────────────────────────────────────

    def _download_worker(self, task_id: str) -> None:
        """下载工作线程"""
        self._semaphore.acquire()
        try:
            self._do_download(task_id)
        finally:
            self._semaphore.release()
            # 清理
            if task_id in self._threads:
                del self._threads[task_id]

    def _do_download(self, task_id: str) -> None:
        """执行下载"""
        task = self._tasks.get(task_id)
        if not task:
            return

        stop_event = self._stop_events.get(task_id)
        paused_event = self._paused_events.get(task_id)

        if not stop_event or not paused_event:
            return

        task.status = DownloadStatus.DOWNLOADING
        task.started_at = datetime.now().isoformat()
        task.start_time = time.time()
        task.connection_status = ConnectionStatus.CONNECTING
        task.connection_error = None
        self._notify_progress(task)

        try:
            # 确定请求头
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }

            # 断点续传
            if task.resume_offset > 0:
                headers["Range"] = f"bytes={task.resume_offset}-"

            with httpx.Client(timeout=self.timeout) as client:
                # ═══════════════════════════════════════════════════════════
                # 阶段1：建立连接，获取响应头
                # ═══════════════════════════════════════════════════════════
                task.connection_status = ConnectionStatus.CONNECTING
                self._notify_progress(task)

                response = client.get(task.url, headers=headers, follow_redirects=True)
                response.raise_for_status()

                # ═══════════════════════════════════════════════════════════
                # 阶段2：解析连接状态和响应头
                # ═══════════════════════════════════════════════════════════
                task.connection_status = ConnectionStatus.CONNECTED
                task.response_code = response.status_code

                # 解析响应头
                task.response_headers = dict(response.headers)
                task.content_type = response.headers.get("content-type", "")
                task.content_disposition = response.headers.get("content-disposition", "")
                task.server = response.headers.get("server", "")
                task.accept_ranges = response.headers.get("accept-ranges", "none")
                task.etag = response.headers.get("etag", "")
                task.last_modified = response.headers.get("last-modified", "")

                # 获取最终URL（跟随重定向后）
                final_url = str(response.url)
                if final_url != task.url:
                    task.url = final_url

                self._notify_progress(task)

                # ═══════════════════════════════════════════════════════════
                # 阶段3：获取总大小
                # ═══════════════════════════════════════════════════════════
                content_length = response.headers.get("content-length")
                if content_length:
                    total = int(content_length)
                    if task.resume_offset > 0:
                        total += task.resume_offset
                    task.total_size = total

                # 更新文件名（如果服务器返回不同的文件名）
                content_disp = response.headers.get("content-disposition")
                if content_disp:
                    new_name = self._parse_content_disposition(content_disp)
                    if new_name and new_name != task.filename:
                        task.filename = new_name
                        task.save_path = task.save_path.parent / new_name

                # 打开文件
                mode = "ab" if task.resume_offset > 0 else "wb"
                task.save_path.parent.mkdir(parents=True, exist_ok=True)

                with open(task.save_path, mode) as f:
                    last_update = time.time()
                    last_downloaded = task.downloaded_size

                    for chunk in response.iter_bytes(chunk_size=self.chunk_size):
                        # 检查停止
                        if stop_event.is_set():
                            task.status = DownloadStatus.CANCELLED
                            return

                        # 检查暂停
                        if paused_event.is_set():
                            task.status = DownloadStatus.PAUSED
                            paused_event.wait()  # 等待恢复
                            if stop_event.is_set():
                                task.status = DownloadStatus.CANCELLED
                                return
                            task.status = DownloadStatus.DOWNLOADING

                        if chunk:
                            f.write(chunk)
                            task.downloaded_size += len(chunk)
                            task.chunk_count += 1

                            # 更新进度（每秒最多更新10次）
                            now = time.time()
                            if now - last_update >= 0.1 or task.chunk_count % 100 == 0:
                                if task.total_size > 0:
                                    task.progress = (task.downloaded_size / task.total_size) * 100

                                # 计算速度
                                elapsed = now - task.start_time
                                if elapsed > 0:
                                    task.speed = (task.downloaded_size - task.resume_offset) / elapsed
                                    task.avg_speed = task.downloaded_size / elapsed

                                task.last_update_time = now
                                self._notify_progress(task)
                                last_update = now
                                last_downloaded = task.downloaded_size

                                # 保存断点
                                self._save_cache(task)

                # 下载完成
                task.status = DownloadStatus.COMPLETED
                task.completed_at = datetime.now().isoformat()
                task.progress = 100.0
                task.speed = 0

                # SHA256 校验
                if task.expected_hash:
                    task.actual_hash = self._sha256(task.save_path)
                    if task.actual_hash != task.expected_hash:
                        task.status = DownloadStatus.FAILED
                        task.error = f"SHA256 校验失败: 期望 {task.expected_hash}, 实际 {task.actual_hash}"
                        logger.error(f"下载校验失败: {task.filename}")
                        return

                # 删除缓存文件
                if task.cache_file and task.cache_file.exists():
                    try:
                        task.cache_file.unlink()
                    except Exception:
                        pass

                self._notify_progress(task)
                self._notify_done(task)
                task.connection_status = ConnectionStatus.IDLE
                logger.info(f"下载完成: {task.filename}")

        except httpx.HTTPStatusError as e:
            task.status = DownloadStatus.FAILED
            task.error = f"HTTP错误: {e.response.status_code} {e.response.reason_phrase}"
            task.connection_status = ConnectionStatus.ERROR
            task.connection_error = f"{e.response.status_code} {e.response.reason_phrase}"
            logger.error(f"下载失败: {task.filename} - {task.error}")
            self._notify_progress(task)

        except httpx.ConnectError as e:
            task.status = DownloadStatus.FAILED
            task.error = f"连接错误: {str(e)}"
            task.connection_status = ConnectionStatus.ERROR
            task.connection_error = str(e)
            logger.error(f"连接失败: {task.filename} - {e}")
            self._notify_progress(task)

        except httpx.TimeoutException as e:
            task.status = DownloadStatus.FAILED
            task.error = f"连接超时: {str(e)}"
            task.connection_status = ConnectionStatus.ERROR
            task.connection_error = "连接超时"
            logger.error(f"连接超时: {task.filename} - {e}")
            self._notify_progress(task)

        except Exception as e:
            task.status = DownloadStatus.FAILED
            task.error = str(e)
            task.connection_status = ConnectionStatus.ERROR
            task.connection_error = str(e)
            logger.error(f"下载异常: {task.filename} - {e}\n{traceback.format_exc()}")
            self._notify_progress(task)

    def _save_cache(self, task: DownloadTask) -> None:
        """保存断点缓存"""
        if not task.cache_file:
            return
        try:
            task.cache_file.write_text(
                json.dumps({
                    "downloaded": task.downloaded_size,
                    "url": task.url,
                    "filename": task.filename,
                }, ensure_ascii=False),
                encoding="utf-8"
            )
        except Exception as e:
            logger.warning(f"保存缓存失败: {e}")

    @staticmethod
    def _sha256(path: Path) -> str:
        """计算 SHA256"""
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def _generate_task_id(url: str) -> str:
        """生成任务ID"""
        return hashlib.md5(url.encode()).hexdigest()[:16]

    @staticmethod
    def _guess_filename(url: str) -> str:
        """猜测文件名"""
        url_path = url.split("?")[0].split("#")[0]
        name = os.path.basename(url_path)
        if name and "." in name:
            return name
        return f"download_{int(time.time())}"

    @staticmethod
    def _parse_content_disposition(header: str) -> Optional[str]:
        """解析 Content-Disposition 头"""
        import re
        match = re.search(r'filename[^;=\n]*=(?:(\\?[\'"]?)([^\'\"]*)\1|[^;\n]*)', header)
        if match:
            return match.group(2)
        return None

    # ── 快捷方法 ────────────────────────────────────────────────────────

    def download_file(
        self,
        url: str,
        save_path: str | Path,
        **kwargs
    ) -> str:
        """
        快捷下载方法（同步阻塞）

        Args:
            url: 下载URL
            save_path: 保存路径
            **kwargs: create_task 的其他参数

        Returns:
            str: 任务ID
        """
        task = self.create_task(url, save_path, **kwargs)
        self.start(task.id)
        return task.id

    def download_model_huggingface(
        self,
        repo_id: str,
        filename: str,
        save_dir: Optional[str] = None,
        token: Optional[str] = None,
        **kwargs
    ) -> DownloadTask:
        """
        下载 HuggingFace 模型文件

        Args:
            repo_id: 仓库ID（如 "second-state/SmolLM2-135M-Instruct-GGUF"）
            filename: 文件名（如 "smollm2-135m-instruct-q4_k_m.gguf"）
            save_dir: 保存目录
            token: HuggingFace token
            **kwargs: 其他参数
        """
        from huggingface_hub import hf_hub_url

        url = hf_hub_url(repo_id=repo_id, filename=filename, repo_type="model")
        if token:
            url = f"{url}?Token={token}"

        save_dir = Path(save_dir) if save_dir else (self.download_dir / "huggingface" / repo_id.replace("/", "_"))
        save_dir.mkdir(parents=True, exist_ok=True)

        task = self.create_task(
            url=url,
            save_path=save_dir,
            source=SourceType.HUGGINGFACE,
            source_info=repo_id,
            filename=filename,
            **kwargs
        )
        self.start(task.id)
        return task

    def download_model_modelscope(
        self,
        repo_id: str,
        filename: str,
        save_dir: Optional[str] = None,
        **kwargs
    ) -> DownloadTask:
        """
        下载 ModelScope 模型文件

        Args:
            repo_id: 仓库ID（如 "LLM-Research/Qwen2.5-7B-Instruct-GGUF"）
            filename: 文件名
            save_dir: 保存目录
            **kwargs: 其他参数
        """
        # ModelScope URL 格式
        url = f"https://modelscope.cn/models/{repo_id}/resolve/master/{filename}"

        save_dir = Path(save_dir) if save_dir else (self.download_dir / "modelscope" / repo_id.replace("/", "_"))
        save_dir.mkdir(parents=True, exist_ok=True)

        task = self.create_task(
            url=url,
            save_path=save_dir,
            source=SourceType.MODELSCOPE,
            source_info=repo_id,
            filename=filename,
            **kwargs
        )
        self.start(task.id)
        return task


# ── 单例访问 ─────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def get_download_center() -> DownloadCenter:
    """获取下载中心单例"""
    return DownloadCenter()


# ── 快捷函数 ─────────────────────────────────────────────────────────────

def download_file(
    url: str,
    save_path: str | Path,
    on_progress: Optional[Callable[[DownloadTask], None]] = None,
    on_done: Optional[Callable[[DownloadTask], None]] = None,
    **kwargs
) -> str:
    """
    快捷下载函数

    示例：
    >>> download_file(
    ...     url="https://example.com/file.zip",
    ...     save_path="./downloads/file.zip",
    ...     on_progress=lambda t: print(f"{t.progress:.1f}%"),
    ... )
    """
    center = get_download_center()
    return center.download_file(
        url=url,
        save_path=save_path,
        progress_callback=on_progress,
        done_callback=on_done,
        **kwargs
    )


def download_model(
    url: str,
    model_id: str,
    save_dir: Optional[str] = None,
    source: str = "http",
    **kwargs
) -> DownloadTask:
    """
    下载模型（统一接口）

    Args:
        url: 下载URL
        model_id: 模型标识
        save_dir: 保存目录
        source: 来源 ("huggingface", "modelscope", "http")
        **kwargs: 其他参数
    """
    center = get_download_center()

    if save_dir is None:
        save_dir = center.download_dir / "models"

    save_dir = Path(save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)

    source_type = SourceType.HTTP
    if source == "huggingface":
        source_type = SourceType.HUGGINGFACE
    elif source == "modelscope":
        source_type = SourceType.MODELSCOPE
    elif source == "github":
        source_type = SourceType.GITHUB

    task = center.create_task(
        url=url,
        save_path=save_dir,
        source=source_type,
        source_info=model_id,
        **kwargs
    )
    center.start(task.id)
    return task


__all__ = [
    "DownloadCenter",
    "DownloadTask",
    "DownloadStatus",
    "SourceType",
    "get_download_center",
    "download_file",
    "download_model",
]
