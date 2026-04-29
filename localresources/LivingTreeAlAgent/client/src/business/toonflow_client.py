"""
Toonflow API Client - AI 短剧生成引擎客户端

与 Toonflow 后端 API 通信，实现任务下发、状态轮询、结果下载
"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Callable, Any

import httpx

logger = logging.getLogger(__name__)


# ============= 常量定义 =============

DEFAULT_HOST = "http://localhost:60001"
DEFAULT_TIMEOUT = 30.0


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PipelineStep(Enum):
    """流水线步骤"""
    NOVEL_IMPORT = "novel_import"
    CHARACTER_EXTRACT = "character_extract"
    SCRIPT_CONVERT = "script_convert"
    STORYBOARD_GEN = "storyboard_gen"
    IMAGE_GEN = "image_gen"
    VIDEO_COMPOSE = "video_compose"


# ============= 数据模型 =============

@dataclass
class ToonflowProject:
    """Toonflow 项目"""
    project_id: str
    title: str
    description: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    status: str = "idle"
    task_count: int = 0


@dataclass
class ToonflowTask:
    """Toonflow 生成任务"""
    task_id: str
    project_id: str
    status: TaskStatus = TaskStatus.PENDING
    current_step: Optional[PipelineStep] = None
    progress: float = 0.0  # 0.0 ~ 1.0
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    result: Optional[dict] = None  # 包含视频下载链接等


@dataclass
class ToonflowConfig:
    """Toonflow 配置"""
    host: str = DEFAULT_HOST
    port: int = 60001
    video_model: str = "seedance2"
    image_model: str = "sd15"
    llm_endpoint: str = "http://localhost:8080/v1"
    timeout: float = DEFAULT_TIMEOUT
    poll_interval: int = 5  # 秒


@dataclass
class NovelContent:
    """小说/剧本内容"""
    title: str
    content: str
    genre: str = "short_drama"  # short_drama / web_novel / marketing
    target_duration: int = 60  # 秒
    style: str = "modern"  # modern / ancient / sci-fi / cartoon


# ============= API 客户端 =============

class ToonflowClient:
    """
    Toonflow API 客户端

    用法:
        client = ToonflowClient(config)
        await client.connect()

        # 创建项目
        project = await client.create_project("我的短剧")

        # 导入小说
        await client.import_novel(project.project_id, novel)

        # 触发生成
        task = await client.start_production(project.project_id)

        # 轮询结果
        result = await client.wait_for_completion(task.task_id)
    """

    def __init__(self, config: Optional[ToonflowConfig] = None):
        self.config = config or ToonflowConfig()
        self._client: Optional[httpx.AsyncClient] = None
        self._connected: bool = False
        self._tasks: dict[str, ToonflowTask] = {}
        self._projects: dict[str, ToonflowProject] = {}
        self._progress_callback: Optional[Callable[[str, float, PipelineStep], None]] = None

    @property
    def base_url(self) -> str:
        return f"http://localhost:{self.config.port}"

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ── 连接管理 ─────────────────────────────────────────────────────

    async def connect(self, timeout: float = 5.0) -> bool:
        """测试连接"""
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(f"{self.base_url}/api/health")
                self._connected = resp.status_code == 200
                if self._connected:
                    logger.info(f"Toonflow connected at {self.base_url}")
                return self._connected
        except Exception as e:
            logger.warning(f"Toonflow connection failed: {e}")
            self._connected = False
            return False

    async def close(self):
        """关闭客户端"""
        if self._client:
            await self._client.aclose()
            self._client = None
        self._connected = False

    @property
    def client(self) -> httpx.AsyncClient:
        """获取 HTTP 客户端"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.config.timeout,
                follow_redirects=True,
            )
        return self._client

    # ── 项目管理 ─────────────────────────────────────────────────────

    async def create_project(
        self,
        title: str,
        description: str = "",
        settings: Optional[dict] = None
    ) -> ToonflowProject:
        """
        创建新项目

        Args:
            title: 项目标题
            description: 项目描述
            settings: 可选的项目设置

        Returns:
            ToonflowProject: 创建的项目
        """
        payload = {
            "title": title,
            "description": description,
        }
        if settings:
            payload["settings"] = settings

        resp = await self.client.post("/api/project", json=payload)
        resp.raise_for_status()
        data = resp.json()

        project = ToonflowProject(
            project_id=data.get("id", data.get("projectId", "")),
            title=title,
            description=description,
            status=data.get("status", "idle"),
        )
        self._projects[project.project_id] = project
        return project

    async def list_projects(self) -> list[ToonflowProject]:
        """列出所有项目"""
        resp = await self.client.get("/api/projects")
        resp.raise_for_status()
        data = resp.json()

        projects = []
        for item in data.get("projects", data if isinstance(data, list) else []):
            project = ToonflowProject(
                project_id=item.get("id", item.get("projectId", "")),
                title=item.get("title", ""),
                description=item.get("description", ""),
                status=item.get("status", "idle"),
                task_count=item.get("taskCount", 0),
            )
            projects.append(project)
            self._projects[project.project_id] = project

        return projects

    async def get_project(self, project_id: str) -> Optional[ToonflowProject]:
        """获取项目详情"""
        resp = await self.client.get(f"/api/project/{project_id}")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        data = resp.json()

        return ToonflowProject(
            project_id=data.get("id", data.get("projectId", "")),
            title=data.get("title", ""),
            description=data.get("description", ""),
            status=data.get("status", "idle"),
            task_count=data.get("taskCount", 0),
        )

    async def delete_project(self, project_id: str) -> bool:
        """删除项目"""
        resp = await self.client.delete(f"/api/project/{project_id}")
        if project_id in self._projects:
            del self._projects[project_id]
        return resp.status_code in (200, 204, 404)

    # ── 小说导入 ─────────────────────────────────────────────────────

    async def import_novel(
        self,
        project_id: str,
        novel: NovelContent
    ) -> dict:
        """
        导入小说/剧本内容

        Args:
            project_id: 项目ID
            novel: 小说内容

        Returns:
            dict: 导入结果
        """
        payload = {
            "projectId": project_id,
            "title": novel.title,
            "content": novel.content,
            "genre": novel.genre,
            "targetDuration": novel.target_duration,
            "style": novel.style,
        }

        resp = await self.client.post("/api/novel", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def update_novel(
        self,
        project_id: str,
        novel_id: str,
        content: str
    ) -> bool:
        """更新小说内容"""
        payload = {
            "content": content,
        }
        resp = await self.client.put(
            f"/api/novel/{novel_id}",
            json=payload
        )
        return resp.status_code == 200

    # ── 生产流水线 ─────────────────────────────────────────────────

    async def start_production(
        self,
        project_id: str,
        model_settings: Optional[dict] = None
    ) -> ToonflowTask:
        """
        启动短剧生成流水线

        Args:
            project_id: 项目ID
            model_settings: 模型设置 (video_model, image_model 等)

        Returns:
            ToonflowTask: 生成任务
        """
        payload = model_settings or {
            "videoModel": self.config.video_model,
            "imageModel": self.config.image_model,
            "llmEndpoint": self.config.llm_endpoint,
        }

        resp = await self.client.post(
            f"/api/project/{project_id}/start-production",
            json=payload
        )
        resp.raise_for_status()
        data = resp.json()

        task = ToonflowTask(
            task_id=data.get("taskId", data.get("id", "")),
            project_id=project_id,
            status=TaskStatus(data.get("status", "pending")),
        )
        task.started_at = datetime.now()
        self._tasks[task.task_id] = task
        return task

    async def get_task_status(self, task_id: str) -> ToonflowTask:
        """
        获取任务状态

        Args:
            task_id: 任务ID

        Returns:
            ToonflowTask: 任务状态
        """
        resp = await self.client.get(f"/api/task/{task_id}")
        resp.raise_for_status()
        data = resp.json()

        task = ToonflowTask(
            task_id=task_id,
            project_id=data.get("projectId", ""),
            status=TaskStatus(data.get("status", "pending")),
            progress=data.get("progress", 0.0) / 100.0,  # API 可能返回百分比
            error=data.get("error"),
            result=data.get("result"),
        )

        # 解析当前步骤
        step_str = data.get("currentStep", "")
        if step_str:
            try:
                task.current_step = PipelineStep(step_str)
            except ValueError:
                pass

        # 更新时间
        started = data.get("startedAt")
        if started:
            task.started_at = datetime.fromisoformat(started.replace("Z", "+00:00"))
        completed = data.get("completedAt")
        if completed:
            task.completed_at = datetime.fromisoformat(completed.replace("Z", "+00:00"))

        # 更新缓存
        if task.task_id in self._tasks:
            self._tasks[task.task_id].status = task.status
            self._tasks[task.task_id].progress = task.progress
            self._tasks[task.task_id].current_step = task.current_step

        return task

    async def wait_for_completion(
        self,
        task_id: str,
        timeout: int = 3600,  # 默认超时 1 小时
        poll_interval: int = None
    ) -> ToonflowTask:
        """
        等待任务完成

        Args:
            task_id: 任务ID
            timeout: 超时秒数
            poll_interval: 轮询间隔秒数

        Returns:
            ToonflowTask: 完成的任务

        Raises:
            TimeoutError: 任务超时
            RuntimeError: 任务失败
        """
        if poll_interval is None:
            poll_interval = self.config.poll_interval

        start_time = asyncio.get_event_loop().time()

        while True:
            # 检查超时
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > timeout:
                raise TimeoutError(f"Task {task_id} timed out after {timeout}s")

            # 获取状态
            task = await self.get_task_status(task_id)

            # 回调进度
            if self._progress_callback:
                self._progress_callback(task_id, task.progress, task.current_step)

            # 检查状态
            if task.status == TaskStatus.COMPLETED:
                return task
            elif task.status == TaskStatus.FAILED:
                raise RuntimeError(f"Toonflow task failed: {task.error or 'Unknown error'}")
            elif task.status == TaskStatus.CANCELLED:
                raise RuntimeError(f"Toonflow task was cancelled")

            # 等待
            await asyncio.sleep(poll_interval)

    async def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        resp = await self.client.post(f"/api/task/{task_id}/cancel")
        if resp.status_code == 200:
            if task_id in self._tasks:
                self._tasks[task_id].status = TaskStatus.CANCELLED
            return True
        return False

    # ── 结果下载 ─────────────────────────────────────────────────────

    async def download_result(
        self,
        task_id: str,
        save_dir: str,
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> str:
        """
        下载任务结果

        Args:
            task_id: 任务ID
            save_dir: 保存目录
            progress_callback: 下载进度回调

        Returns:
            str: 保存的文件路径
        """
        task = await self.get_task_status(task_id)
        if task.status != TaskStatus.COMPLETED:
            raise RuntimeError(f"Task {task_id} is not completed: {task.status}")

        result = task.result or {}
        video_url = result.get("videoDownloadUrl") or result.get("url")

        if not video_url:
            raise ValueError(f"No download URL in task result")

        # 确保保存目录存在
        save_path = Path(save_dir)
        save_path.mkdir(parents=True, exist_ok=True)

        # 下载文件
        filename = result.get("filename", f"toonflow_{task_id}.mp4")
        save_file = save_path / filename

        async with httpx.AsyncClient(timeout=300.0) as download_client:
            async with download_client.stream("GET", video_url) as resp:
                resp.raise_for_status()
                total_size = int(resp.headers.get("content-length", 0))
                downloaded = 0

                with open(save_file, "wb") as f:
                    async for chunk in resp.aiter_bytes(chunk_size=8192):
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback and total_size > 0:
                            progress_callback(downloaded / total_size)

        return str(save_file)

    # ── 快捷方法 ─────────────────────────────────────────────────────

    async def create_and_produce(
        self,
        novel: NovelContent,
        project_title: Optional[str] = None,
        progress_callback: Optional[Callable[[str, float, PipelineStep], None]] = None
    ) -> tuple[ToonflowProject, ToonflowTask]:
        """
        一站式创建项目并启动生产

        Args:
            novel: 小说内容
            project_title: 项目标题 (默认使用小说标题)
            progress_callback: 进度回调

        Returns:
            tuple: (项目, 任务)
        """
        self._progress_callback = progress_callback

        # 1. 创建项目
        title = project_title or novel.title
        project = await self.create_project(title, f"Auto-generated: {title}")

        # 2. 导入小说
        await self.import_novel(project.project_id, novel)

        # 3. 启动生产
        task = await self.start_production(project.project_id)

        return project, task

    # ── 辅助方法 ─────────────────────────────────────────────────────

    def get_task(self, task_id: str) -> Optional[ToonflowTask]:
        """获取缓存的任务"""
        return self._tasks.get(task_id)

    def set_progress_callback(
        self,
        callback: Callable[[str, float, PipelineStep], None]
    ):
        """设置进度回调"""
        self._progress_callback = callback


# ============= 便捷函数 =============

_toonflow_client: Optional[ToonflowClient] = None


def get_toonflow_client(config: Optional[ToonflowConfig] = None) -> ToonflowClient:
    """获取全局 ToonflowClient 实例"""
    global _toonflow_client
    if _toonflow_client is None:
        _toonflow_client = ToonflowClient(config)
    return _toonflow_client


async def init_toonflow_client(config: Optional[ToonflowConfig] = None) -> ToonflowClient:
    """初始化并返回 ToonflowClient"""
    client = get_toonflow_client(config)
    await client.connect()
    return client
