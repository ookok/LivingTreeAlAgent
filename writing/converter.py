"""
文档转换器 - 基于 MarkItDown 的透明包装器
直接暴露 MarkItDown 功能，添加进度监控和事件系统
"""

import asyncio
import json
import time
from typing import Callable, Dict, List, Optional, Any, Union, AsyncGenerator
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
import logging

from PyQt6.QtCore import QObject, pyqtSignal

# 尝试导入 MarkItDown（可选依赖）
try:
    from markitdown import MarkItDown, DocumentConverterResult
    MARKITDOWN_AVAILABLE = True
except ImportError:
    MARKITDOWN_AVAILABLE = False
    MarkItDown = None
    DocumentConverterResult = None


logger = logging.getLogger(__name__)


class ConversionEvent(Enum):
    """转换事件类型"""
    START = "start"
    FILE_LOADED = "file_loaded"
    TRANSFORMER_START = "transformer_start"
    TRANSFORMER_PROGRESS = "transformer_progress"
    TRANSFORMER_END = "transformer_end"
    CHUNK_GENERATED = "chunk_generated"
    COMPLETE = "complete"
    ERROR = "error"


@dataclass
class ProgressInfo:
    """进度信息"""
    current: int = 0
    total: int = 100
    percentage: float = 0.0
    stage: str = ""
    transformer: str = ""
    file_path: str = ""
    file_size: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EventInfo:
    """事件信息"""
    event_type: ConversionEvent
    data: Any = None
    timestamp: float = field(default_factory=time.time)
    file_path: str = ""
    transformer: str = ""


class TransformerHook:
    """
    转换器钩子
    用于捕获 MarkItDown 内部转换过程
    """

    def __init__(self, callback: Callable[[EventInfo], None]):
        self.callback = callback
        self.original_transforms: Dict[str, Callable] = {}

    def wrap_transformer(self, transformer) -> Any:
        """包装转换器以添加钩子"""
        transformer_name = transformer.__class__.__name__

        # 保存原始 transform 方法
        original_transform = getattr(transformer, 'transform', None)
        if original_transform is None:
            return transformer

        @wraps(original_transform)
        def wrapped_transform(input_data, config, context):
            # 发送开始事件
            self.callback(EventInfo(
                event_type=ConversionEvent.TRANSFORMER_START,
                transformer=transformer_name,
                data={"input_type": type(input_data).__name__}
            ))

            try:
                # 执行转换
                result = original_transform(input_data, config, context)

                # 如果有进度信息，发送进度事件
                if hasattr(transformer, 'get_progress'):
                    progress = transformer.get_progress()
                    if progress:
                        self.callback(EventInfo(
                            event_type=ConversionEvent.TRANSFORMER_PROGRESS,
                            transformer=transformer_name,
                            data=progress
                        ))

                # 发送结束事件
                self.callback(EventInfo(
                    event_type=ConversionEvent.TRANSFORMER_END,
                    transformer=transformer_name,
                    data={"output_type": type(result).__name__}
                ))

                return result

            except Exception as e:
                self.callback(EventInfo(
                    event_type=ConversionEvent.ERROR,
                    transformer=transformer_name,
                    data=str(e)
                ))
                raise

        # 替换方法
        transformer.transform = wrapped_transform
        self.original_transforms[transformer_name] = original_transform

        return transformer


class TransparentConverter(QObject):
    """
    透明转换器
    直接使用 MarkItDown 的功能，只添加必要的事件系统
    """

    # PyQt 信号
    event_occurred = pyqtSignal(EventInfo)
    progress_updated = pyqtSignal(ProgressInfo)
    result_ready = pyqtSignal(str, object)  # task_id, result
    status_changed = pyqtSignal(str, str)  # task_id, status

    def __init__(self, markitdown_kwargs: Dict[str, Any] = None):
        super().__init__()
        self.logger = logger

        if not MARKITDOWN_AVAILABLE:
            self.logger.warning("MarkItDown 未安装，文档转换功能不可用")
            self.markitdown = None
            self._available = False
            return

        # 创建 MarkItDown 实例
        kwargs = markitdown_kwargs or {}
        try:
            self.markitdown = MarkItDown(**kwargs)
            self._available = True
        except Exception as e:
            self.logger.error(f"MarkItDown 初始化失败: {e}")
            self.markitdown = None
            self._available = False
            return

        # 事件订阅者
        self.subscribers: List[Callable[[EventInfo], None]] = []

        # 转换器钩子
        self.hook = TransformerHook(self._dispatch_event)

        # 包装管道
        self._wrap_pipeline()

        # 任务状态
        self.active_tasks: Dict[str, Dict] = {}

    def _wrap_pipeline(self):
        """包装转换管道"""
        if hasattr(self.markitdown, 'pipeline') and self.markitdown.pipeline:
            wrapped_pipeline = []
            for transformer in self.markitdown.pipeline:
                try:
                    wrapped = self.hook.wrap_transformer(transformer)
                    wrapped_pipeline.append(wrapped)
                except Exception as e:
                    self.logger.warning(f"无法包装转换器 {transformer.__class__.__name__}: {e}")
                    wrapped_pipeline.append(transformer)
            self.markitdown.pipeline = wrapped_pipeline

    def _dispatch_event(self, event: EventInfo):
        """分发事件"""
        # 发送 PyQt 信号
        self.event_occurred.emit(event)

        # 调用订阅者
        for subscriber in self.subscribers:
            try:
                subscriber(event)
            except Exception as e:
                self.logger.error(f"事件订阅者错误: {e}")

    def subscribe(self, callback: Callable[[EventInfo], None]):
        """订阅事件"""
        self.subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[EventInfo], None]):
        """取消订阅"""
        if callback in self.subscribers:
            self.subscribers.remove(callback)

    def is_available(self) -> bool:
        """检查是否可用"""
        return self._available and self.markitdown is not None

    def convert_file(
        self,
        file_path: Union[str, Path],
        task_id: Optional[str] = None
    ) -> Optional[Any]:
        """
        转换文件（同步）

        Returns:
            DocumentConverterResult 或 None（如果失败）
        """
        if not self.is_available():
            self.logger.error("MarkItDown 不可用")
            return None

        file_path = Path(file_path)
        if not file_path.exists():
            self.logger.error(f"文件不存在: {file_path}")
            return None

        task_id = task_id or f"task_{file_path.stem}_{int(time.time())}"

        # 注册任务
        self.active_tasks[task_id] = {
            "file_path": str(file_path),
            "start_time": time.time(),
            "status": "processing"
        }

        # 发送开始事件
        try:
            file_size = file_path.stat().st_size
        except Exception:
            file_size = 0

        self._dispatch_event(EventInfo(
            event_type=ConversionEvent.START,
            file_path=str(file_path),
            data={"task_id": task_id, "file_size": file_size}
        ))
        self.status_changed.emit(task_id, "processing")

        try:
            # 直接调用 MarkItDown
            result = self.markitdown.convert(str(file_path))

            # 发送完成事件
            self._dispatch_event(EventInfo(
                event_type=ConversionEvent.COMPLETE,
                file_path=str(file_path),
                data={
                    "task_id": task_id,
                    "result_size": len(result.text_content) if result.text_content else 0,
                    "metadata": result.metadata if hasattr(result, 'metadata') else {}
                }
            ))

            # 发送结果信号
            self.result_ready.emit(task_id, result)

            # 更新任务状态
            self.active_tasks[task_id]["status"] = "completed"
            self.active_tasks[task_id]["end_time"] = time.time()
            self.status_changed.emit(task_id, "completed")

            return result

        except Exception as e:
            self.logger.error(f"转换失败 {task_id}: {e}")

            # 发送错误事件
            self._dispatch_event(EventInfo(
                event_type=ConversionEvent.ERROR,
                file_path=str(file_path),
                data={"task_id": task_id, "error": str(e)}
            ))

            # 更新任务状态
            self.active_tasks[task_id]["status"] = "failed"
            self.active_tasks[task_id]["error"] = str(e)
            self.status_changed.emit(task_id, "failed")

            return None

    def convert_text(
        self,
        content: str,
        source_type: str = "md",
        task_id: Optional[str] = None
    ) -> Optional[Any]:
        """
        转换文本内容

        Args:
            content: 文本内容
            source_type: 源类型（如 "pdf", "docx", "html" 等）
            task_id: 任务ID
        """
        if not self.is_available():
            return None

        task_id = task_id or f"text_{int(time.time())}"

        self.active_tasks[task_id] = {
            "file_path": "<text>",
            "start_time": time.time(),
            "status": "processing"
        }

        self._dispatch_event(EventInfo(
            event_type=ConversionEvent.START,
            file_path="<text>",
            data={"task_id": task_id, "source_type": source_type}
        ))

        try:
            # MarkItDown 主要用于文件，对于文本直接返回
            # 这里我们可以包装成类文件对象或直接处理
            result = self.markitdown.convert_text(content, source_type)

            self._dispatch_event(EventInfo(
                event_type=ConversionEvent.COMPLETE,
                file_path="<text>",
                data={
                    "task_id": task_id,
                    "result_size": len(result.text_content) if result.text_content else 0
                }
            ))

            self.result_ready.emit(task_id, result)
            self.active_tasks[task_id]["status"] = "completed"
            self.active_tasks[task_id]["end_time"] = time.time()
            self.status_changed.emit(task_id, "completed")

            return result

        except Exception as e:
            self.logger.error(f"文本转换失败 {task_id}: {e}")
            self._dispatch_event(EventInfo(
                event_type=ConversionEvent.ERROR,
                file_path="<text>",
                data={"task_id": task_id, "error": str(e)}
            ))
            self.active_tasks[task_id]["status"] = "failed"
            self.active_tasks[task_id]["error"] = str(e)
            self.status_changed.emit(task_id, "failed")
            return None

    async def convert_file_async(
        self,
        file_path: Union[str, Path],
        task_id: Optional[str] = None
    ) -> Optional[Any]:
        """异步转换文件"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.convert_file(file_path, task_id)
        )

    def convert_batch(
        self,
        file_paths: List[Union[str, Path]],
        max_workers: int = 3
    ) -> Dict[str, Optional[Any]]:
        """批量转换"""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        if not self.is_available():
            return {}

        results = {}
        task_ids = []

        # 为每个文件创建任务ID
        for file_path in file_paths:
            task_id = f"batch_{Path(file_path).stem}_{int(time.time())}"
            task_ids.append((task_id, file_path))

        # 使用线程池
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_task = {}
            for task_id, file_path in task_ids:
                future = executor.submit(self.convert_file, file_path, task_id)
                future_to_task[future] = (task_id, file_path)

            for future in as_completed(future_to_task):
                task_id, file_path = future_to_task[future]
                try:
                    result = future.result()
                    results[str(file_path)] = result
                except Exception as e:
                    self.logger.error(f"批量转换失败 {task_id}: {e}")
                    results[str(file_path)] = None

        return results

    def get_markitdown_instance(self) -> Optional[Any]:
        """获取原始的 MarkItDown 实例"""
        return self.markitdown

    def get_supported_formats(self) -> List[str]:
        """获取支持的格式"""
        if not self.is_available():
            return []
        if hasattr(self.markitdown, 'supported_extensions'):
            return self.markitdown.supported_extensions
        # 常见的 MarkItDown 支持格式
        return [".pdf", ".docx", ".pptx", ".xlsx", ".html", ".rst", ".epub", ".odt"]

    def get_pipeline_info(self) -> List[Dict]:
        """获取管道信息"""
        if not self.is_available():
            return []
        if hasattr(self.markitdown, 'pipeline') and self.markitdown.pipeline:
            return [
                {
                    "name": transformer.__class__.__name__,
                    "module": transformer.__class__.__module__,
                    "description": getattr(transformer, '__doc__', '') or ""
                }
                for transformer in self.markitdown.pipeline
            ]
        return []

    def get_active_tasks(self) -> Dict[str, Dict]:
        """获取活跃任务"""
        return self.active_tasks.copy()

    def get_task_result(self, task_id: str) -> Optional[Any]:
        """获取任务结果"""
        task = self.active_tasks.get(task_id)
        if task and task.get("status") == "completed":
            return task.get("result")
        return None
