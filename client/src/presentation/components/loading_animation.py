"""
等待动画和进度条组件

提供各种等待动画效果和进度条实现：
1. 旋转加载动画
2. 脉冲动画
3. 进度条
4. 步骤指示器
5. 上传进度
"""

from typing import Optional, List, Callable
from enum import Enum

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QProgressBar
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QRectF
from PyQt6.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont, QPainterPath
)

from .minimal_ui_framework import ColorScheme, Spacing, UIComponentFactory


class AnimationType(Enum):
    """动画类型"""
    SPINNER = "spinner"
    PULSE = "pulse"
    DOTS = "dots"
    RING = "ring"
    WAVE = "wave"


class LoadingSpinner(QWidget):
    """加载旋转器"""
    
    def __init__(self, parent=None, size: int = 40, animation_type: AnimationType = AnimationType.SPINNER):
        super().__init__(parent)
        self._size = size
        self._animation_type = animation_type
        self._angle = 0
        self._phase = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_animation)
        self._timer.start(30)
        self.setFixedSize(size, size)
    
    def set_size(self, size: int):
        """设置尺寸"""
        self._size = size
        self.setFixedSize(size, size)
    
    def set_animation_type(self, animation_type: AnimationType):
        """设置动画类型"""
        self._animation_type = animation_type
    
    def stop(self):
        """停止动画"""
        self._timer.stop()
    
    def start(self):
        """启动动画"""
        self._timer.start(30)
    
    def _update_animation(self):
        """更新动画状态"""
        self._angle += 5
        self._phase += 0.1
        self.update()
    
    def paintEvent(self, event):
        """绘制动画"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        center = self._size // 2
        radius = self._size // 2 - 4
        
        if self._animation_type == AnimationType.SPINNER:
            self._draw_spinner(painter, center, radius)
        elif self._animation_type == AnimationType.PULSE:
            self._draw_pulse(painter, center, radius)
        elif self._animation_type == AnimationType.DOTS:
            self._draw_dots(painter, center, radius)
        elif self._animation_type == AnimationType.RING:
            self._draw_ring(painter, center, radius)
        elif self._animation_type == AnimationType.WAVE:
            self._draw_wave(painter, center, radius)
    
    def _draw_spinner(self, painter: QPainter, center: int, radius: int):
        """绘制旋转器"""
        painter.setPen(QPen(QColor(ColorScheme.PRIMARY.value), 3, cap=Qt.PenCapStyle.RoundCap))
        
        start_angle = self._angle * 16
        arc_length = 270 * 16
        
        painter.drawArc(
            center - radius,
            center - radius,
            radius * 2,
            radius * 2,
            start_angle,
            arc_length
        )
    
    def _draw_pulse(self, painter: QPainter, center: int, radius: int):
        """绘制脉冲动画"""
        scale = 0.6 + 0.4 * abs(self._phase % (3.1416 * 2)) / (3.1416 * 2)
        
        painter.setBrush(QBrush(QColor(ColorScheme.PRIMARY.value)))
        painter.setPen(Qt.PenStyle.NoPen)
        
        painter.drawEllipse(
            center - radius * scale,
            center - radius * scale,
            radius * 2 * scale,
            radius * 2 * scale
        )
    
    def _draw_dots(self, painter: QPainter, center: int, radius: int):
        """绘制跳动圆点"""
        dot_count = 3
        dot_radius = 4
        
        for i in range(dot_count):
            angle = (i * 120 + self._angle) * 3.1416 / 180
            offset = (self._phase + i * 0.3) % (3.1416 * 2)
            bounce = 5 * abs(offset - 3.1416) / 3.1416
            
            x = center + (radius - 8) * 2**0.5 * (angle - 3.1416 / 4)
            y = center - bounce
            
            painter.setBrush(QBrush(QColor(ColorScheme.PRIMARY.value)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(x - dot_radius, y - dot_radius, dot_radius * 2, dot_radius * 2)
    
    def _draw_ring(self, painter: QPainter, center: int, radius: int):
        """绘制环形动画"""
        # 外圆环
        painter.setPen(QPen(QColor(ColorScheme.BORDER.value), 3))
        painter.drawEllipse(center - radius, center - radius, radius * 2, radius * 2)
        
        # 旋转的内圆
        angle = self._angle * 3.1416 / 180
        inner_radius = radius - 8
        
        x = center + inner_radius * (angle - 3.1416 / 2)
        y = center + inner_radius * 1
        
        painter.setBrush(QBrush(QColor(ColorScheme.PRIMARY.value)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(x - 6, y - 6, 12, 12)
    
    def _draw_wave(self, painter: QPainter, center: int, radius: int):
        """绘制波浪动画"""
        wave_count = 5
        wave_width = 8
        
        for i in range(wave_count):
            offset = (self._phase + i * 0.4) % (3.1416 * 2)
            height = 10 + 15 * abs(offset - 3.1416) / 3.1416
            
            x = center - (wave_count - 1) * wave_width / 2 + i * wave_width
            
            painter.setBrush(QBrush(QColor(ColorScheme.PRIMARY.value)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(x - wave_width / 2, center + radius / 2 - height, wave_width, height)


class ProgressIndicator(QWidget):
    """进度指示器"""
    
    progress_updated = pyqtSignal(int)
    completed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._progress = 0
        self._max_progress = 100
        self._label = ""
        self._show_percentage = True
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(Spacing.SM)
        
        self._setup_ui()
    
    def _setup_ui(self):
        """设置UI"""
        # 进度条
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, self._max_progress)
        self._progress_bar.setValue(self._progress)
        self._progress_bar.setStyleSheet(self._get_progress_style())
        self._layout.addWidget(self._progress_bar)
        
        # 标签
        self._label_widget = QLabel()
        self._label_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label_widget.setStyleSheet(f"font-size: 12px; color: {ColorScheme.TEXT_SECONDARY.value};")
        self._update_label()
        self._layout.addWidget(self._label_widget)
    
    def _get_progress_style(self) -> str:
        """获取进度条样式"""
        return f"""
            QProgressBar {{
                background-color: {ColorScheme.BORDER.value};
                border-radius: 4px;
                height: 8px;
            }}
            QProgressBar::chunk {{
                background-color: {ColorScheme.PRIMARY.value};
                border-radius: 4px;
            }}
        """
    
    def set_progress(self, progress: int):
        """设置进度"""
        self._progress = max(0, min(self._max_progress, progress))
        self._progress_bar.setValue(self._progress)
        self._update_label()
        self.progress_updated.emit(self._progress)
        
        if self._progress >= self._max_progress:
            self.completed.emit()
    
    def set_label(self, label: str):
        """设置标签"""
        self._label = label
        self._update_label()
    
    def set_max_progress(self, max_progress: int):
        """设置最大进度"""
        self._max_progress = max_progress
        self._progress_bar.setRange(0, max_progress)
    
    def set_show_percentage(self, show: bool):
        """设置是否显示百分比"""
        self._show_percentage = show
        self._update_label()
    
    def _update_label(self):
        """更新标签"""
        percentage = f"{self._progress}/{self._max_progress}" if self._show_percentage else ""
        
        if self._label:
            text = f"{self._label} {percentage}"
        else:
            text = percentage
        
        self._label_widget.setText(text)
    
    def reset(self):
        """重置进度"""
        self._progress = 0
        self._progress_bar.setValue(0)
        self._update_label()


class StepProgressWidget(QWidget):
    """步骤进度控件"""
    
    step_changed = pyqtSignal(int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._steps = []
        self._current_step = 0
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
    
    def add_step(self, title: str):
        """添加步骤"""
        self._steps.append(title)
        self._update_ui()
    
    def set_steps(self, steps: List[str]):
        """设置步骤列表"""
        self._steps = steps
        self._current_step = 0
        self._update_ui()
    
    def set_current_step(self, step_index: int):
        """设置当前步骤"""
        if 0 <= step_index < len(self._steps):
            self._current_step = step_index
            self.step_changed.emit(step_index)
            self._update_ui()
    
    def _update_ui(self):
        """更新UI"""
        # 清空布局
        while self._layout.count() > 0:
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        for i, step in enumerate(self._steps):
            # 创建步骤节点
            node = QWidget()
            node_layout = QVBoxLayout(node)
            node_layout.setContentsMargins(0, 0, 0, 0)
            node_layout.setSpacing(4)
            
            # 圆形指示器
            circle = QFrame()
            circle.setFixedSize(28, 28)
            
            is_completed = i < self._current_step
            is_current = i == self._current_step
            
            if is_completed:
                circle.setStyleSheet(f"""
                    QFrame {{
                        background-color: {ColorScheme.SUCCESS.value};
                        border-radius: 14px;
                    }}
                """)
                icon_label = QLabel("✓")
                icon_label.setStyleSheet("color: white; font-weight: bold; font-size: 14px;")
                icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                circle_layout = QVBoxLayout(circle)
                circle_layout.addWidget(icon_label)
            elif is_current:
                circle.setStyleSheet(f"""
                    QFrame {{
                        background-color: {ColorScheme.PRIMARY.value};
                        border-radius: 14px;
                    }}
                """)
                num_label = QLabel(str(i + 1))
                num_label.setStyleSheet("color: white; font-weight: bold; font-size: 12px;")
                num_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                circle_layout = QVBoxLayout(circle)
                circle_layout.addWidget(num_label)
            else:
                circle.setStyleSheet(f"""
                    QFrame {{
                        background-color: {ColorScheme.BORDER.value};
                        border-radius: 14px;
                    }}
                """)
                num_label = QLabel(str(i + 1))
                num_label.setStyleSheet(f"color: {ColorScheme.TEXT_SECONDARY.value}; font-size: 12px;")
                num_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                circle_layout = QVBoxLayout(circle)
                circle_layout.addWidget(num_label)
            
            node_layout.addWidget(circle)
            
            # 步骤标签
            label = QLabel(step)
            label.setStyleSheet(f"""
                font-size: 11px;
                color: {'#1F2937' if is_completed or is_current else '#9CA3AF'};
                font-weight: {'bold' if is_current else 'normal'};
            """)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            node_layout.addWidget(label)
            
            self._layout.addWidget(node)
            
            # 添加连接线（最后一个步骤不加）
            if i < len(self._steps) - 1:
                line = QFrame()
                line.setFixedSize(30, 2)
                line.setFrameShape(QFrame.Shape.HLine)
                
                if i < self._current_step:
                    line.setStyleSheet(f"background-color: {ColorScheme.SUCCESS.value};")
                else:
                    line.setStyleSheet(f"background-color: {ColorScheme.BORDER.value};")
                
                line.setStyleSheet(f"""
                    QFrame {{
                        background-color: {'{ColorScheme.SUCCESS.value}' if i < self._current_step else '{ColorScheme.BORDER.value}'};
                    }}
                """)
                self._layout.addWidget(line)


class UploadProgressWidget(QWidget):
    """上传进度控件"""
    
    upload_completed = pyqtSignal(str)
    upload_failed = pyqtSignal(str, str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._files = []
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(Spacing.SM)
    
    def add_file(self, filename: str, size: int = 0):
        """添加文件"""
        file_id = len(self._files)
        self._files.append({
            "id": file_id,
            "filename": filename,
            "size": size,
            "progress": 0,
            "status": "uploading"  # uploading, completed, failed
        })
        self._update_ui()
    
    def update_progress(self, file_id: int, progress: int):
        """更新进度"""
        for file in self._files:
            if file["id"] == file_id:
                file["progress"] = progress
                if progress >= 100:
                    file["status"] = "completed"
                    self.upload_completed.emit(file["filename"])
                break
        self._update_ui()
    
    def set_failed(self, file_id: int, error: str):
        """设置失败状态"""
        for file in self._files:
            if file["id"] == file_id:
                file["status"] = "failed"
                self.upload_failed.emit(file["filename"], error)
                break
        self._update_ui()
    
    def _update_ui(self):
        """更新UI"""
        # 清空布局
        while self._layout.count() > 0:
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        for file in self._files:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(Spacing.SM)
            
            # 图标
            icon_label = QLabel()
            if file["status"] == "completed":
                icon_label.setText("✓")
                icon_label.setStyleSheet("color: #22C55E; font-size: 16px;")
            elif file["status"] == "failed":
                icon_label.setText("✗")
                icon_label.setStyleSheet("color: #EF4444; font-size: 16px;")
            else:
                icon_label.setText("📄")
                icon_label.setStyleSheet("font-size: 16px;")
            
            row_layout.addWidget(icon_label)
            
            # 文件名
            name_label = QLabel(file["filename"])
            name_label.setStyleSheet(f"""
                font-size: 13px;
                color: {'#1F2937' if file['status'] == 'completed' else '#EF4444' if file['status'] == 'failed' else '#6B7280'};
            """)
            row_layout.addWidget(name_label)
            
            # 进度条
            if file["status"] != "failed":
                progress_bar = QProgressBar()
                progress_bar.setRange(0, 100)
                progress_bar.setValue(file["progress"])
                progress_bar.setFixedWidth(100)
                progress_bar.setStyleSheet("""
                    QProgressBar {
                        background-color: #E5E7EB;
                        border-radius: 4px;
                        height: 6px;
                    }
                    QProgressBar::chunk {
                        background-color: #3B82F6;
                        border-radius: 4px;
                    }
                """)
                row_layout.addWidget(progress_bar)
            
            # 状态文字
            status_label = QLabel()
            if file["status"] == "completed":
                status_label.setText("完成")
                status_label.setStyleSheet("color: #22C55E; font-size: 12px;")
            elif file["status"] == "failed":
                status_label.setText("失败")
                status_label.setStyleSheet("color: #EF4444; font-size: 12px;")
            else:
                status_label.setText(f"{file['progress']}%")
                status_label.setStyleSheet("color: #6B7280; font-size: 12px;")
            
            row_layout.addWidget(status_label)
            
            self._layout.addWidget(row)


class LoadingOverlay(QWidget):
    """加载遮罩层"""
    
    def __init__(self, parent=None, text: str = "加载中..."):
        super().__init__(parent)
        self._text = text
        self._visible = False
        
        if parent:
            self.setGeometry(parent.rect())
            self.hide()
    
    def set_text(self, text: str):
        """设置加载文字"""
        self._text = text
        self.update()
    
    def show_overlay(self):
        """显示遮罩"""
        if self.parent():
            self.setGeometry(self.parent().rect())
        self._visible = True
        self.show()
    
    def hide_overlay(self):
        """隐藏遮罩"""
        self._visible = False
        self.hide()
    
    def paintEvent(self, event):
        """绘制遮罩"""
        painter = QPainter(self)
        
        # 半透明背景
        painter.setBrush(QBrush(QColor(0, 0, 0, 128)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(self.rect())
        
        # 居中绘制加载动画
        center_x = self.width() // 2
        center_y = self.height() // 2
        
        # 绘制加载动画
        spinner = LoadingSpinner()
        spinner.set_size(48)
        
        # 绘制文字
        painter.setPen(QPen(Qt.GlobalColor.white))
        font = QFont()
        font.setPointSize(14)
        painter.setFont(font)
        painter.drawText(
            QRectF(center_x - 100, center_y + 30, 200, 30),
            Qt.AlignmentFlag.AlignCenter,
            self._text
        )


# 导出接口
__all__ = [
    "AnimationType",
    "LoadingSpinner",
    "ProgressIndicator",
    "StepProgressWidget",
    "UploadProgressWidget",
    "LoadingOverlay"
]