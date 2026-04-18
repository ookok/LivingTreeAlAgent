"""
文档转换事件处理器
将转换器事件转换为 PyQt 信号
"""

from PyQt6.QtCore import QObject, pyqtSignal
from typing import Dict, Any
import logging

from .converter import EventInfo, ConversionEvent


class ConverterEventHandler(QObject):
    """
    转换器事件处理器
    将底层事件转换为界面友好的信号
    """

    # 进度信号
    file_started = pyqtSignal(str)  # file_path
    file_progress = pyqtSignal(str, int, str)  # file_path, progress, message
    file_completed = pyqtSignal(str, dict)  # file_path, result_info
    file_failed = pyqtSignal(str, str)  # file_path, error
    transformer_progress = pyqtSignal(str, str, int)  # file_path, transformer, progress
    chunk_ready = pyqtSignal(str, int, int)  # file_path, chunk_number, chunk_size
    status_changed = pyqtSignal(str, str)  # task_id, status

    def __init__(self, converter):
        super().__init__()
        self.converter = converter
        self.logger = logging.getLogger(__name__)

        # 连接事件
        if hasattr(converter, 'event_occurred'):
            converter.event_occurred.connect(self._handle_event)

        # 进度跟踪
        self._file_progress: Dict[str, Dict[str, Any]] = {}

    def _handle_event(self, event: EventInfo):
        """处理转换器事件"""
        try:
            file_path = event.file_path

            if event.event_type == ConversionEvent.START:
                self._on_start(event)

            elif event.event_type == ConversionEvent.TRANSFORMER_START:
                self._on_transformer_start(event)

            elif event.event_type == ConversionEvent.TRANSFORMER_PROGRESS:
                self._on_transformer_progress(event)

            elif event.event_type == ConversionEvent.TRANSFORMER_END:
                self._on_transformer_end(event)

            elif event.event_type == ConversionEvent.CHUNK_GENERATED:
                self._on_chunk_generated(event)

            elif event.event_type == ConversionEvent.COMPLETE:
                self._on_complete(event)

            elif event.event_type == ConversionEvent.ERROR:
                self._on_error(event)

        except Exception as e:
            self.logger.error(f"事件处理失败: {e}")

    def _on_start(self, event: EventInfo):
        """处理开始事件"""
        file_path = event.file_path
        data = event.data or {}

        # 初始化进度
        self._file_progress[file_path] = {
            "transformers": {},
            "current_transformer": None,
            "start_time": event.timestamp
        }

        # 发送信号
        self.file_started.emit(file_path)
        self.file_progress.emit(file_path, 0, "开始转换...")

    def _on_transformer_start(self, event: EventInfo):
        """处理转换器开始"""
        file_path = event.file_path
        transformer = event.transformer

        if file_path in self._file_progress:
            self._file_progress[file_path]["current_transformer"] = transformer
            self._file_progress[file_path]["transformers"][transformer] = {
                "start_time": event.timestamp,
                "progress": 0
            }

            # 发送信号
            self.file_progress.emit(file_path, 0, f"正在处理: {transformer}")

    def _on_transformer_progress(self, event: EventInfo):
        """处理转换器进度"""
        file_path = event.file_path
        transformer = event.transformer
        data = event.data or {}

        if (file_path in self._file_progress and
            transformer in self._file_progress[file_path]["transformers"]):

            progress = data.get("progress", 0) if isinstance(data, dict) else 0
            self._file_progress[file_path]["transformers"][transformer]["progress"] = progress

            # 发送信号
            self.transformer_progress.emit(file_path, transformer, int(progress * 100))

    def _on_transformer_end(self, event: EventInfo):
        """处理转换器结束"""
        file_path = event.file_path
        transformer = event.transformer

        if (file_path in self._file_progress and
            transformer in self._file_progress[file_path]["transformers"]):

            # 更新进度
            self._file_progress[file_path]["transformers"][transformer]["end_time"] = event.timestamp

            # 计算总体进度
            transformers = self._file_progress[file_path]["transformers"]
            completed = sum(1 for t in transformers.values() if "end_time" in t)
            total = len(transformers)

            if total > 0:
                overall_progress = int((completed / total) * 100)
                self.file_progress.emit(file_path, overall_progress, f"完成: {transformer}")

    def _on_chunk_generated(self, event: EventInfo):
        """处理分块生成"""
        file_path = event.file_path
        data = event.data or {}

        chunk_number = data.get("chunk_number", 0) if isinstance(data, dict) else 0
        chunk_size = data.get("chunk_size", 0) if isinstance(data, dict) else 0

        self.chunk_ready.emit(file_path, chunk_number, chunk_size)

    def _on_complete(self, event: EventInfo):
        """处理完成事件"""
        file_path = event.file_path
        data = event.data or {}

        # 清理进度
        if file_path in self._file_progress:
            del self._file_progress[file_path]

        # 发送完成信号
        result_info = {
            "task_id": data.get("task_id", "") if isinstance(data, dict) else "",
            "result_size": data.get("result_size", 0) if isinstance(data, dict) else 0,
            "metadata": data.get("metadata", {}) if isinstance(data, dict) else {},
            "streaming": data.get("streaming", False) if isinstance(data, dict) else False
        }

        self.file_completed.emit(file_path, result_info)
        self.file_progress.emit(file_path, 100, "转换完成")

    def _on_error(self, event: EventInfo):
        """处理错误事件"""
        file_path = event.file_path
        data = event.data or {}
        error = data.get("error", "未知错误") if isinstance(data, dict) else str(data)

        # 清理进度
        if file_path in self._file_progress:
            del self._file_progress[file_path]

        # 发送错误信号
        self.file_failed.emit(file_path, error)
        self.file_progress.emit(file_path, 0, f"错误: {error}")

    def get_file_progress(self, file_path: str) -> Dict[str, Any]:
        """获取文件进度信息"""
        return self._file_progress.get(file_path, {})
