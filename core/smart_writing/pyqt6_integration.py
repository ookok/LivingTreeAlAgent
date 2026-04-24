# -*- coding: utf-8 -*-
"""
PyQt6 集成模块 - PyQt6 Integration
===================================

将流式输出、进度可视化集成到 PyQt6 GUI

功能：
1. 流式文本到 QTextEdit
2. 进度条到 QProgressBar
3. 错误提示到 QMessageBox
4. 状态栏集成
5. 通知系统

Author: Hermes Desktop Team
"""

import sys
from typing import Optional, Callable, Any
from PyQt6.QtCore import QObject, pyqtSignal, QTimer, Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QProgressBar,
    QLabel, QPushButton, QMessageBox, QStatusBar, QFrame,
    QGraphicsOpacityEffect, QApplication
)
from PyQt6.QtGui import QTextCursor, QFont, QColor, QTextCharFormat

try:
    from .streaming_output import StreamingOutput, StreamingConfig
    from .progress_visualizer import ProgressManager
    from .error_recovery import RecoveryExecutor, RetryPolicy
    from .multimodal_output import MultimodalOutputManager, OutputMode, OutputEvent
except ImportError:
    # 同级导入
    from streaming_output import StreamingOutput, StreamingConfig
    from progress_visualizer import ProgressManager
    from error_recovery import RecoveryExecutor, RetryPolicy
    from multimodal_output import MultimodalOutputManager, OutputMode, OutputEvent


# =============================================================================
# PyQt6 信号桥接器
# =============================================================================

class PyQtSignalBridge(QObject):
    """
    PyQt 信号桥接器
    
    用于连接异步输出系统和 PyQt6 GUI
    
    Signals:
        text_updated: 文本更新信号 (str)
        progress_updated: 进度更新信号 (stage, progress, message)
        error_occurred: 错误信号 (error_message)
        completed: 完成信号 (message)
    """
    
    text_updated = pyqtSignal(str)
    progress_updated = pyqtSignal(str, float, str)
    error_occurred = pyqtSignal(str)
    completed = pyqtSignal(str)
    warning_occurred = pyqtSignal(str)
    info_occurred = pyqtSignal(str)


# =============================================================================
# 流式文本组件
# =============================================================================

class StreamingTextWidget(QFrame):
    """
    流式文本显示组件
    
    支持打字机效果的文本显示
    
    Example:
        widget = StreamingTextWidget()
        widget.stream_text("你好，这是一段长文本...")
        widget.append_text(" 追加文本")
    """
    
    def __init__(
        self,
        parent: Optional[QWidget] = None,
        font_size: int = 12,
        font_family: str = "Microsoft YaHei",
        text_color: QColor = None,
        bg_color: QColor = None,
        readonly: bool = True,
    ):
        super().__init__(parent)
        
        self._text_edit = QTextEdit(self)
        self._text_edit.setReadOnly(readonly)
        
        # 设置字体
        font = QFont(font_family, font_size)
        self._text_edit.setFont(font)
        
        # 设置颜色
        if text_color:
            self._text_color = text_color
        else:
            palette = self._text_edit.palette()
            self._text_color = palette.text().color()
        
        if bg_color:
            self._text_edit.setStyleSheet(f"background-color: {bg_color.name()};")
        
        # 布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._text_edit)
        
        # 流式输出状态
        self._is_streaming = False
        self._full_text = ""
        self._char_index = 0
        self._char_delay = 0.02
        
        # 定时器
        self._stream_timer = QTimer(self)
        self._stream_timer.timeout.connect(self._stream_step)
    
    def stream_text(self, text: str, delay: float = 0.02) -> None:
        """
        流式输出文本
        
        Args:
            text: 要输出的文本
            delay: 每个字符的延迟（秒）
        """
        self._full_text += text
        self._char_index = 0
        self._char_delay = delay
        self._is_streaming = True
        self._stream_timer.start(int(delay * 1000))
    
    def _stream_step(self) -> None:
        """流式输出步骤"""
        if self._char_index < len(self._full_text):
            char = self._full_text[self._char_index]
            self.append_text(char, stream=True)
            self._char_index += 1
        else:
            self._stream_timer.stop()
            self._is_streaming = False
    
    def append_text(self, text: str, stream: bool = False) -> None:
        """
        追加文本
        
        Args:
            text: 要追加的文本
            stream: 是否流式追加（True=不换行，False=自动换行）
        """
        if stream:
            self._text_edit.moveCursor(QTextCursor.MoveOperation.End)
            self._text_edit.insertPlainText(text)
            self._text_edit.moveCursor(QTextCursor.MoveOperation.End)
        else:
            self._text_edit.append(text)
    
    def set_text(self, text: str) -> None:
        """设置文本"""
        self._text_edit.setPlainText(text)
    
    def clear(self) -> None:
        """清除文本"""
        self._text_edit.clear()
        self._full_text = ""
        self._char_index = 0
    
    @property
    def text(self) -> str:
        """获取当前文本"""
        return self._text_edit.toPlainText()
    
    def is_streaming(self) -> bool:
        """是否正在流式输出"""
        return self._is_streaming
    
    def stop_streaming(self) -> None:
        """停止流式输出"""
        self._stream_timer.stop()
        self._is_streaming = False
        # 显示剩余文本
        if self._char_index < len(self._full_text):
            remaining = self._full_text[self._char_index:]
            self.append_text(remaining)


# =============================================================================
# 进度条组件
# =============================================================================

class ProgressWidget(QFrame):
    """
    进度显示组件
    
    包含标签、进度条、百分比显示
    
    Example:
        widget = ProgressWidget()
        widget.set_stage("下载文件")
        widget.set_progress(0.5, "5/10")
        widget.set_progress(1.0, "完成")
    """
    
    def __init__(
        self,
        parent: Optional[QWidget] = None,
        show_percentage: bool = True,
        show_stage: bool = True,
    ):
        super().__init__(parent)
        
        self._show_percentage = show_percentage
        self._show_stage = show_stage
        
        # 创建布局
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        
        # 阶段标签
        if show_stage:
            self._stage_label = QLabel(self)
            self._stage_label.setStyleSheet("""
                QLabel {
                    color: #666;
                    font-size: 12px;
                    font-weight: bold;
                }
            """)
            self._main_layout.addWidget(self._stage_label)
        
        # 进度条布局
        progress_layout = QHBoxLayout()
        
        self._progress_bar = QProgressBar(self)
        self._progress_bar.setMinimum(0)
        self._progress_bar.setMaximum(100)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: #f5f5f5;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 3px;
            }
        """)
        progress_layout.addWidget(self._progress_bar)
        
        # 百分比标签
        if show_percentage:
            self._percentage_label = QLabel("0%", self)
            self._percentage_label.setFixedWidth(50)
            self._percentage_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._percentage_label.setStyleSheet("""
                QLabel {
                    color: #333;
                    font-size: 12px;
                    font-weight: bold;
                }
            """)
            progress_layout.addWidget(self._percentage_label)
        
        self._main_layout.addLayout(progress_layout)
        
        # 消息标签
        self._message_label = QLabel(self)
        self._message_label.setStyleSheet("""
            QLabel {
                color: #888;
                font-size: 11px;
            }
        """)
        self._main_layout.addWidget(self._message_label)
    
    def set_stage(self, stage: str) -> None:
        """设置阶段名称"""
        if self._show_stage and hasattr(self, "_stage_label"):
            self._stage_label.setText(stage)
    
    def set_progress(self, progress: float, message: str = "") -> None:
        """
        设置进度
        
        Args:
            progress: 进度值 0.0-1.0
            message: 附加消息
        """
        pct = int(min(1.0, max(0.0, progress)) * 100)
        self._progress_bar.setValue(pct)
        
        if self._show_percentage and hasattr(self, "_percentage_label"):
            self._percentage_label.setText(f"{pct}%")
        
        if message:
            self._message_label.setText(message)
    
    def set_indeterminate(self, indeterminate: bool = True) -> None:
        """设置不确定进度模式"""
        if indeterminate:
            self._progress_bar.setRange(0, 0)
        else:
            self._progress_bar.setRange(0, 100)
    
    def reset(self) -> None:
        """重置进度"""
        self._progress_bar.setValue(0)
        if self._show_percentage and hasattr(self, "_percentage_label"):
            self._percentage_label.setText("0%")
        self._message_label.clear()
        if self._show_stage and hasattr(self, "_stage_label"):
            self._stage_label.clear()
    
    def complete(self, message: str = "完成") -> None:
        """完成进度"""
        self.set_progress(1.0, message)
        self.setStyleSheet("""
            QFrame {
                background-color: #e8f5e9;
                border-radius: 4px;
                padding: 4px;
            }
        """)


# =============================================================================
# PyQt6 多模态输出管理器
# =============================================================================

class PyQt6OutputManager(QObject):
    """
    PyQt6 多模态输出管理器
    
    集成到 PyQt6 应用的多模态输出系统
    
    Example:
        class MainWindow(QMainWindow):
            def __init__(self):
                super().__init__()
                self.output_manager = PyQt6OutputManager()
                
                # 连接到 UI
                self.output_manager.attach_text_widget(self.text_widget)
                self.output_manager.attach_progress_widget(self.progress_widget)
                
            def on_button_clicked(self):
                self.output_manager.output_stream("开始处理...")
    """
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        self._bridge = PyQtSignalBridge()
        self._inner_manager = MultimodalOutputManager()
        
        # 连接的组件
        self._text_widget: Optional[StreamingTextWidget] = None
        self._progress_widget: Optional[ProgressWidget] = None
        self._status_bar: Optional[QStatusBar] = None
        
        # 连接信号
        self._bridge.text_updated.connect(self._on_text_updated)
        self._bridge.progress_updated.connect(self._on_progress_updated)
        self._bridge.error_occurred.connect(self._on_error)
        self._bridge.completed.connect(self._on_completed)
        
        # 设置内部管理器回调
        self._inner_manager.set_text_callback(
            lambda text: self._bridge.text_updated.emit(text)
        )
        self._inner_manager.set_progress_callback(
            lambda stage, pct, msg: self._bridge.progress_updated.emit(stage, pct, msg)
        )
        self._inner_manager.set_error_callback(
            lambda err: self._bridge.error_occurred.emit(err)
        )
        self._inner_manager.set_complete_callback(
            lambda msg: self._bridge.completed.emit(msg)
        )
    
    # -------------------------------------------------------------------------
    # UI 连接方法
    # -------------------------------------------------------------------------
    
    def attach_text_widget(self, widget: StreamingTextWidget) -> None:
        """连接文本组件"""
        self._text_widget = widget
    
    def attach_progress_widget(self, widget: ProgressWidget) -> None:
        """连接进度组件"""
        self._progress_widget = widget
    
    def attach_status_bar(self, status_bar: QStatusBar) -> None:
        """连接状态栏"""
        self._status_bar = status_bar
    
    def detach_all(self) -> None:
        """断开所有连接"""
        self._text_widget = None
        self._progress_widget = None
        self._status_bar = None
    
    # -------------------------------------------------------------------------
    # PyQt 信号处理
    # -------------------------------------------------------------------------
    
    def _on_text_updated(self, text: str) -> None:
        """文本更新处理"""
        if self._text_widget:
            self._text_widget.append_text(text, stream=True)
    
    def _on_progress_updated(self, stage: str, progress: float, message: str) -> None:
        """进度更新处理"""
        if self._progress_widget:
            self._progress_widget.set_stage(stage)
            self._progress_widget.set_progress(progress, message)
        
        if self._status_bar:
            pct = int(progress * 100)
            self._status_bar.showMessage(f"{stage}: {pct}% {message}")
    
    def _on_error(self, error_message: str) -> None:
        """错误处理"""
        if self._text_widget:
            self._text_widget.append_text(f"\n❌ 错误: {error_message}\n")
    
    def _on_completed(self, message: str) -> None:
        """完成处理"""
        if self._progress_widget:
            self._progress_widget.complete(message)
        
        if self._status_bar:
            self._status_bar.showMessage(f"✅ {message}", 3000)
    
    # -------------------------------------------------------------------------
    # 输出方法
    # -------------------------------------------------------------------------
    
    def set_mode(self, mode: OutputMode) -> None:
        """设置输出模式"""
        self._inner_manager.set_mode(mode)
    
    def output_stream(self, text: str, delay: float = 0.02) -> None:
        """
        流式输出文本
        
        Args:
            text: 文本内容
            delay: 字符延迟
        """
        if self._text_widget:
            self._text_widget.stream_text(text, delay)
        else:
            self._inner_manager.output_text(text)
    
    def append_text(self, text: str) -> None:
        """追加文本（不流式）"""
        self._inner_manager.output_text(text)
        if self._text_widget:
            self._text_widget.append_text(text)
    
    def set_progress(self, stage: str, progress: float, message: str = "") -> None:
        """设置进度"""
        self._inner_manager.output_progress_update(stage, progress, message)
    
    def start_progress(self, stage: str, total_steps: int) -> None:
        """开始进度追踪"""
        self._inner_manager.output_progress_start(stage, total_steps)
        if self._progress_widget:
            self._progress_widget.set_stage(stage)
            self._progress_widget.set_progress(0)
    
    def step_progress(self, message: str = "") -> None:
        """进度步进"""
        # 需要维护步进计数，这里简化处理
        pass
    
    def complete_progress(self, message: str = "完成") -> None:
        """完成进度"""
        self._inner_manager.output_progress_complete("任务", message)
    
    def show_error(self, error: str, recoverable: bool = True) -> None:
        """显示错误"""
        self._inner_manager.output_error(error, recoverable)
    
    def show_warning(self, message: str) -> None:
        """显示警告"""
        self._inner_manager.output_warning(message)
    
    def show_message(self, message: str) -> None:
        """显示消息"""
        self._inner_manager.output_info(message)
    
    def complete(self, message: str = "完成") -> None:
        """完成"""
        self._inner_manager.output_complete(message)
    
    def clear_text(self) -> None:
        """清除文本"""
        if self._text_widget:
            self._text_widget.clear()
        self._inner_manager.clear_text_buffer()
    
    def pause(self) -> None:
        """暂停"""
        self._inner_manager.pause()
        if self._text_widget:
            self._text_widget.stop_streaming()
    
    def resume(self) -> None:
        """恢复"""
        self._inner_manager.resume()
    
    # -------------------------------------------------------------------------
    # 错误恢复集成
    # -------------------------------------------------------------------------
    
    def execute_with_retry(
        self,
        func: Callable,
        *args,
        task_id: str = "default",
        operation_name: str = "操作",
        **kwargs,
    ) -> Any:
        """
        执行带重试的操作
        
        Args:
            func: 要执行的函数
            task_id: 任务 ID
            operation_name: 操作名称
            **kwargs: 额外参数
        """
        self.start_progress(operation_name, 3)
        
        executor = RecoveryExecutor()
        
        def on_retry(error, attempt):
            self.append_text(f"\n⚠️ 重试 {attempt}: {error}\n")
        
        try:
            result = executor.execute(
                func, *args,
                task_id=task_id,
                operation_name=operation_name,
                on_retry=on_retry,
                **kwargs,
            )
            self.complete_progress("成功")
            return result
        except Exception as e:
            self.complete_progress(f"失败: {e}")
            raise
    
    # -------------------------------------------------------------------------
    # 上下文管理器
    # -------------------------------------------------------------------------
    
    def progress_context(self, stage: str, total_steps: int = 5):
        """进度追踪上下文"""
        return ProgressContext(self, stage, total_steps)


class ProgressContext:
    """进度追踪上下文"""
    
    def __init__(self, manager: PyQt6OutputManager, stage: str, total_steps: int):
        self._manager = manager
        self._stage = stage
        self._total_steps = total_steps
        self._current_step = 0
    
    def __enter__(self):
        self._manager.start_progress(self._stage, self._total_steps)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self._manager.complete_progress("完成")
        else:
            self._manager.complete_progress(f"失败: {exc_val}")
    
    def step(self, message: str = "") -> None:
        """步进"""
        self._current_step += 1
        progress = self._current_step / self._total_steps
        self._manager.set_progress(self._stage, progress, message)
    
    def update(self, progress: float, message: str = "") -> None:
        """更新进度"""
        self._manager.set_progress(self._stage, progress, message)


# =============================================================================
# 便捷函数
# =============================================================================

def create_output_manager(parent: Optional[QWidget] = None) -> PyQt6OutputManager:
    """创建 PyQt6 输出管理器"""
    return PyQt6OutputManager(parent)


# =============================================================================
# 测试
# =============================================================================

if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton
    
    app = QApplication(sys.argv)
    
    window = QMainWindow()
    window.setWindowTitle("多模态输出测试")
    window.setGeometry(100, 100, 600, 400)
    
    central_widget = QWidget()
    window.setCentralWidget(central_widget)
    layout = QVBoxLayout(central_widget)
    
    # 创建流式文本组件
    text_widget = StreamingTextWidget()
    layout.addWidget(text_widget, stretch=3)
    
    # 创建进度组件
    progress_widget = ProgressWidget()
    layout.addWidget(progress_widget, stretch=1)
    
    # 创建输出管理器
    output_manager = PyQt6OutputManager()
    output_manager.attach_text_widget(text_widget)
    output_manager.attach_progress_widget(progress_widget)
    output_manager.attach_status_bar(window.statusBar())
    
    # 测试按钮
    def on_stream_clicked():
        output_manager.output_stream("你好，这是一个流式输出测试...\n", delay=0.03)
    
    def on_progress_clicked():
        import threading
        def run_progress():
            for i in range(11):
                output_manager.set_progress("测试进度", i / 10, f"{i*10}%")
                import time
                time.sleep(0.2)
            output_manager.complete("测试完成!")
        
        thread = threading.Thread(target=run_progress)
        thread.start()
    
    btn_layout = QHBoxLayout()
    layout.addLayout(btn_layout)
    
    stream_btn = QPushButton("流式输出")
    stream_btn.clicked.connect(on_stream_clicked)
    btn_layout.addWidget(stream_btn)
    
    progress_btn = QPushButton("进度测试")
    progress_btn.clicked.connect(on_progress_clicked)
    btn_layout.addWidget(progress_btn)
    
    window.show()
    sys.exit(app.exec())
