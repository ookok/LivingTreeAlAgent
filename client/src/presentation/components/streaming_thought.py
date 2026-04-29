"""
流式思考动画组件 - 工具调用的动画效果

功能特性：
1. 展示AI思考过程的动画
2. 工具调用的视觉反馈
3. 数据流动画效果
4. 加载状态动画
5. 参考Trae的solo模式风格

设计目标：
- 提供流畅的动画体验
- 清晰展示工具调用过程
- 符合现代UI设计风格
"""

from typing import Optional, List, Dict, Any
from enum import Enum
from loguru import logger

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QProgressBar, QToolButton, QScrollArea,
    QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QColor, QFont


class ThoughtState(Enum):
    """思考状态枚举"""
    IDLE = "idle"
    THINKING = "thinking"
    CALLING_TOOL = "calling_tool"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"


class ToolCallInfo:
    """工具调用信息"""
    
    def __init__(self, tool_name: str, params: Dict[str, Any], status: str = "pending"):
        self.tool_name = tool_name
        self.params = params
        self.status = status
        self.result = None
        self.error = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "params": self.params,
            "status": self.status,
            "result": self.result,
            "error": self.error
        }


class ThinkingIndicator(QWidget):
    """
    思考指示器 - 显示AI正在思考的动画
    
    参考Trae solo模式的思考动画效果。
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._is_thinking = False
    
    def _setup_ui(self):
        """设置UI"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)
        
        # 三个点指示器
        self.dots = []
        for i in range(3):
            dot = QLabel()
            dot.setFixedSize(8, 8)
            dot.setStyleSheet("""
                QLabel {
                    background-color: #2563eb;
                    border-radius: 4px;
                }
            """)
            self.dots.append(dot)
            layout.addWidget(dot)
        
        # 思考文本
        self.text_label = QLabel("思考中...")
        self.text_label.setStyleSheet("color: #64748b; font-size: 14px;")
        layout.addWidget(self.text_label)
        
        layout.addStretch()
        
        # 设置固定高度
        self.setFixedHeight(32)
    
    def start(self):
        """开始思考动画"""
        self._is_thinking = True
        self._animate_dots()
    
    def stop(self):
        """停止思考动画"""
        self._is_thinking = False
        # 重置所有点的状态
        for dot in self.dots:
            dot.setStyleSheet("""
                QLabel {
                    background-color: #2563eb;
                    border-radius: 4px;
                }
            """)
    
    def _animate_dots(self):
        """动画效果：三个点依次闪烁"""
        if not self._is_thinking:
            return
        
        for i, dot in enumerate(self.dots):
            # 计算延迟
            delay = i * 150
            
            # 创建动画
            animation = QPropertyAnimation(dot, b"styleSheet")
            animation.setDuration(300)
            animation.setStartValue("""
                QLabel {
                    background-color: #2563eb;
                    border-radius: 4px;
                }
            """)
            animation.setEndValue("""
                QLabel {
                    background-color: #93c5fd;
                    border-radius: 4px;
                }
            """)
            animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
            animation.setLoopCount(1)
            
            QTimer.singleShot(delay, lambda anim=animation: anim.start())
        
        # 循环动画
        QTimer.singleShot(750, self._animate_dots)


class ToolCallAnimation(QFrame):
    """
    工具调用动画组件
    
    展示工具调用的完整过程，包括：
    1. 工具名称和参数
    2. 调用状态动画
    3. 返回结果展示
    """
    
    tool_completed = pyqtSignal(dict)
    tool_failed = pyqtSignal(str)
    
    def __init__(self, tool_name: str, params: Dict[str, Any], parent=None):
        super().__init__(parent)
        self._tool_name = tool_name
        self._params = params
        self._status = "calling"
        self._setup_ui()
    
    def _setup_ui(self):
        """设置UI"""
        self.setStyleSheet("""
            ToolCallAnimation {
                background-color: #1e293b;
                border-radius: 8px;
                padding: 12px;
                margin: 8px 0;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # 标题栏
        title_layout = QHBoxLayout()
        
        # 工具图标
        self.icon_label = QLabel("🛠️")
        self.icon_label.setStyleSheet("font-size: 20px;")
        title_layout.addWidget(self.icon_label)
        
        # 工具名称
        self.name_label = QLabel(self._tool_name)
        self.name_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #e2e8f0;")
        title_layout.addWidget(self.name_label)
        
        # 状态指示器
        self.status_indicator = QLabel()
        self.status_indicator.setFixedSize(12, 12)
        self._update_status_indicator("calling")
        title_layout.addWidget(self.status_indicator)
        
        title_layout.addStretch()
        layout.addLayout(title_layout)
        
        # 参数区域
        params_frame = QFrame()
        params_frame.setStyleSheet("background-color: #0f172a; border-radius: 4px; padding: 8px;")
        params_layout = QVBoxLayout(params_frame)
        
        for key, value in self._params.items():
            row_layout = QHBoxLayout()
            
            key_label = QLabel(f"{key}:")
            key_label.setStyleSheet("color: #94a3b8; font-size: 12px;")
            row_layout.addWidget(key_label)
            
            value_label = QLabel(str(value))
            value_label.setStyleSheet("color: #e2e8f0; font-size: 12px;")
            row_layout.addWidget(value_label)
            
            params_layout.addLayout(row_layout)
        
        layout.addWidget(params_frame)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                height: 4px;
                border-radius: 2px;
                background-color: #334155;
            }
            QProgressBar::chunk {
                background-color: #2563eb;
                border-radius: 2px;
            }
        """)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        
        # 结果区域
        self.result_frame = QFrame()
        self.result_frame.setVisible(False)
        self.result_layout = QVBoxLayout(self.result_frame)
        layout.addWidget(self.result_frame)
    
    def _update_status_indicator(self, status: str):
        """更新状态指示器"""
        colors = {
            "calling": "#2563eb",
            "processing": "#f59e0b",
            "completed": "#10b981",
            "error": "#ef4444"
        }
        
        color = colors.get(status, "#64748b")
        self.status_indicator.setStyleSheet(f"""
            QLabel {{
                background-color: {color};
                border-radius: 6px;
            }}
        """)
    
    def start(self):
        """开始工具调用动画"""
        self._animate_progress()
    
    def _animate_progress(self):
        """进度动画"""
        animation = QPropertyAnimation(self.progress_bar, b"value")
        animation.setDuration(2000)
        animation.setStartValue(0)
        animation.setEndValue(100)
        animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        animation.start()
    
    def complete(self, result: Any):
        """完成工具调用"""
        self._status = "completed"
        self._update_status_indicator("completed")
        
        # 更新图标
        self.icon_label.setText("✅")
        
        # 显示结果
        self.result_frame.setVisible(True)
        
        # 添加结果标题
        result_label = QLabel("📋 结果")
        result_label.setStyleSheet("font-size: 12px; font-weight: bold; color: #10b981;")
        self.result_layout.addWidget(result_label)
        
        # 添加结果内容
        result_text = QLabel(str(result))
        result_text.setStyleSheet("color: #e2e8f0; font-size: 13px;")
        result_text.setWordWrap(True)
        self.result_layout.addWidget(result_text)
        
        self.tool_completed.emit({"tool_name": self._tool_name, "result": result})
    
    def fail(self, error: str):
        """工具调用失败"""
        self._status = "error"
        self._update_status_indicator("error")
        
        # 更新图标
        self.icon_label.setText("❌")
        
        # 显示错误
        self.result_frame.setVisible(True)
        
        error_label = QLabel(f"❌ 错误: {error}")
        error_label.setStyleSheet("color: #ef4444; font-size: 13px;")
        self.result_layout.addWidget(error_label)
        
        self.tool_failed.emit(error)


class StreamingThoughtWidget(QFrame):
    """
    流式思考主组件
    
    展示AI思考和工具调用的完整过程，参考Trae solo模式。
    """
    
    thought_complete = pyqtSignal()
    tool_called = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._thoughts: List[str] = []
        self._tool_calls: List[ToolCallAnimation] = []
        self._setup_ui()
    
    def _setup_ui(self):
        """设置UI"""
        self.setStyleSheet("""
            StreamingThoughtWidget {
                background-color: #0f172a;
                border-radius: 12px;
                padding: 16px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        
        # 头部
        header_layout = QHBoxLayout()
        
        self.avatar_label = QLabel("🤖")
        self.avatar_label.setStyleSheet("font-size: 24px;")
        header_layout.addWidget(self.avatar_label)
        
        self.title_label = QLabel("正在分析...")
        self.title_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #e2e8f0;")
        header_layout.addWidget(self.title_label)
        
        self.close_button = QToolButton()
        self.close_button.setText("✕")
        self.close_button.setStyleSheet("""
            QToolButton {
                color: #64748b;
                border: none;
                padding: 4px;
            }
            QToolButton:hover {
                color: #e2e8f0;
            }
        """)
        self.close_button.clicked.connect(self.hide)
        header_layout.addWidget(self.close_button)
        
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        # 思考区域
        self.thoughts_frame = QFrame()
        self.thoughts_layout = QVBoxLayout(self.thoughts_frame)
        self.thoughts_layout.setContentsMargins(0, 0, 0, 0)
        self.thoughts_layout.setSpacing(8)
        layout.addWidget(self.thoughts_frame)
        
        # 工具调用区域
        self.tool_calls_frame = QFrame()
        self.tool_calls_layout = QVBoxLayout(self.tool_calls_frame)
        self.tool_calls_layout.setContentsMargins(0, 0, 0, 0)
        self.tool_calls_layout.setSpacing(8)
        layout.addWidget(self.tool_calls_frame)
        
        # 底部操作区
        self.bottom_layout = QHBoxLayout()
        
        self.cancel_button = QPushButton("取消")
        self.cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #334155;
                color: #e2e8f0;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #475569;
            }
        """)
        self.cancel_button.clicked.connect(self._cancel)
        self.bottom_layout.addWidget(self.cancel_button)
        
        self.bottom_layout.addStretch()
        layout.addLayout(self.bottom_layout)
    
    def add_thought(self, thought: str):
        """添加思考步骤"""
        self._thoughts.append(thought)
        
        # 创建思考条目
        thought_item = QFrame()
        thought_item.setStyleSheet("background-color: #1e293b; border-radius: 6px; padding: 8px 12px;")
        
        thought_layout = QHBoxLayout(thought_item)
        
        # 序号
        index_label = QLabel(f"{len(self._thoughts)}.")
        index_label.setStyleSheet("color: #2563eb; font-weight: bold; font-size: 13px;")
        thought_layout.addWidget(index_label)
        
        # 内容
        content_label = QLabel(thought)
        content_label.setStyleSheet("color: #e2e8f0; font-size: 13px;")
        content_label.setWordWrap(True)
        thought_layout.addWidget(content_label)
        
        self.thoughts_layout.addWidget(thought_item)
        
        # 触发动画
        self._animate_thought(thought_item)
    
    def _animate_thought(self, widget: QWidget):
        """思考条目动画"""
        widget.setOpacity(0)
        
        animation = QPropertyAnimation(widget, b"opacity")
        animation.setDuration(300)
        animation.setStartValue(0)
        animation.setEndValue(1)
        animation.start()
    
    def add_tool_call(self, tool_name: str, params: Dict[str, Any]) -> ToolCallAnimation:
        """添加工具调用"""
        tool_animation = ToolCallAnimation(tool_name, params, self)
        self._tool_calls.append(tool_animation)
        self.tool_calls_layout.addWidget(tool_animation)
        
        # 开始动画
        tool_animation.start()
        
        # 连接信号
        tool_animation.tool_completed.connect(self._on_tool_completed)
        tool_animation.tool_failed.connect(self._on_tool_failed)
        
        self.tool_called.emit({"tool_name": tool_name, "params": params})
        
        return tool_animation
    
    def _on_tool_completed(self, result: Dict):
        """工具调用完成"""
        logger.info(f"工具调用完成: {result}")
    
    def _on_tool_failed(self, error: str):
        """工具调用失败"""
        logger.error(f"工具调用失败: {error}")
    
    def complete(self):
        """完成思考"""
        self.title_label.setText("分析完成")
        self.thought_complete.emit()
    
    def _cancel(self):
        """取消思考"""
        self.hide()
        self._thoughts.clear()
        self._tool_calls.clear()
        
        # 清空布局
        while self.thoughts_layout.count() > 0:
            item = self.thoughts_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        while self.tool_calls_layout.count() > 0:
            item = self.tool_calls_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()


class DataFlowAnimation(QFrame):
    """
    数据流动画组件
    
    展示数据在工具之间流动的效果，参考Trae的数据流动画。
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        """设置UI"""
        self.setStyleSheet("background-color: transparent;")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 数据流容器
        self.flow_container = QFrame()
        self.flow_container.setStyleSheet("""
            QFrame {
                background: linear-gradient(180deg, #1e3a5f 0%, #0f172a 100%);
                border-radius: 8px;
                padding: 16px;
                min-height: 100px;
            }
        """)
        layout.addWidget(self.flow_container)
        
        self.flow_layout = QVBoxLayout(self.flow_container)
        self.flow_layout.setContentsMargins(0, 0, 0, 0)
        self.flow_layout.setSpacing(8)
    
    def add_data_point(self, label: str, value: str):
        """添加数据点"""
        data_item = QFrame()
        data_item.setStyleSheet("background-color: rgba(37, 99, 235, 0.2); border-radius: 4px; padding: 8px;")
        
        layout = QHBoxLayout(data_item)
        
        label_label = QLabel(label)
        label_label.setStyleSheet("color: #93c5fd; font-size: 12px;")
        layout.addWidget(label_label)
        
        value_label = QLabel(value)
        value_label.setStyleSheet("color: #e2e8f0; font-size: 13px; font-weight: 500;")
        layout.addWidget(value_label)
        
        layout.addStretch()
        
        self.flow_layout.addWidget(data_item)
        
        # 添加动画
        self._animate_data_point(data_item)
    
    def _animate_data_point(self, widget: QWidget):
        """数据点动画"""
        widget.setOpacity(0)
        widget.setGeometry(widget.x() - 20, widget.y(), widget.width(), widget.height())
        
        opacity_anim = QPropertyAnimation(widget, b"opacity")
        opacity_anim.setDuration(400)
        opacity_anim.setStartValue(0)
        opacity_anim.setEndValue(1)
        
        pos_anim = QPropertyAnimation(widget, b"geometry")
        pos_anim.setDuration(400)
        pos_anim.setStartValue(widget.geometry().adjusted(-20, 0, -20, 0))
        pos_anim.setEndValue(widget.geometry())
        
        opacity_anim.start()
        pos_anim.start()


class ProgressRing(QWidget):
    """
    环形进度指示器
    
    用于显示工具调用的进度状态。
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._progress = 0
        self._setup_ui()
    
    def _setup_ui(self):
        """设置UI"""
        self.setFixedSize(40, 40)
        
        self.label = QLabel()
        self.label.setStyleSheet("font-size: 10px; color: #64748b;")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.label)
    
    def set_progress(self, progress: int):
        """设置进度"""
        self._progress = progress
        self.label.setText(f"{progress}%")
        
        # 更新样式
        color = "#2563eb" if progress < 100 else "#10b981"
        self.setStyleSheet(f"""
            ProgressRing {{
                border: 3px solid {color};
                border-radius: 20px;
            }}
        """)
    
    def start_spinning(self):
        """开始旋转动画"""
        # 简化实现：循环更新进度
        self._spin_progress = 0
        
        def update():
            self._spin_progress = (self._spin_progress + 5) % 100
            self.set_progress(self._spin_progress)
            
            if hasattr(self, '_spin_timer'):
                self._spin_timer.start(50)
        
        self._spin_timer = QTimer()
        self._spin_timer.timeout.connect(update)
        self._spin_timer.start(50)
    
    def stop_spinning(self):
        """停止旋转动画"""
        if hasattr(self, '_spin_timer'):
            self._spin_timer.stop()
            delattr(self, '_spin_timer')


# 全局函数
def create_thinking_bubble(parent=None) -> StreamingThoughtWidget:
    """创建思考气泡组件"""
    return StreamingThoughtWidget(parent)


def create_tool_call_animation(tool_name: str, params: Dict[str, Any], parent=None) -> ToolCallAnimation:
    """创建工具调用动画组件"""
    return ToolCallAnimation(tool_name, params, parent)