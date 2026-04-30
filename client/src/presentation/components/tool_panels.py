"""工具调用面板 - 支持调用工具和显示结果"""

from PyQt6.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QListWidget, QListWidgetItem, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon

class ToolPanel(QFrame):
    """工具调用面板"""
    
    tool_selected = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
    
    def _init_ui(self):
        self.setStyleSheet("""
            QFrame {
                background: #ffffff;
                border-radius: 12px;
                border: 1px solid #e5e7eb;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        header = QHBoxLayout()
        icon_label = QLabel()
        icon_label.setPixmap(QIcon("icons/tools.png").pixmap(20, 20))
        header.addWidget(icon_label)
        header.addWidget(QLabel("可用工具"))
        header.addStretch()
        layout.addLayout(header)
        
        self._tool_list = QListWidget()
        self._tool_list.setStyleSheet("""
            QListWidget {
                border: none;
            }
            QListWidget::item {
                padding: 12px;
                border-radius: 8px;
                margin-bottom: 4px;
            }
            QListWidget::item:hover {
                background: #f3f4f6;
            }
            QListWidget::item:selected {
                background: #eff6ff;
                color: #1d4ed8;
            }
        """)
        self._tool_list.itemClicked.connect(lambda item: self.tool_selected.emit(item.text()))
        layout.addWidget(self._tool_list)
    
    def add_tool(self, tool_name, icon_name="tool"):
        """添加工具"""
        item = QListWidgetItem(tool_name)
        item.setIcon(QIcon(f"icons/{icon_name}.png"))
        self._tool_list.addItem(item)
    
    def clear_tools(self):
        """清空工具列表"""
        self._tool_list.clear()

class ToolResultPanel(QFrame):
    """工具结果展示面板"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
    
    def _init_ui(self):
        self.setStyleSheet("""
            QFrame {
                background: #ffffff;
                border-radius: 12px;
                border: 1px solid #e5e7eb;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        self._header = QHBoxLayout()
        self._tool_name = QLabel("工具名称")
        self._tool_name.setStyleSheet("""
            QLabel {
                color: #1f2937;
                font-size: 15px;
                font-weight: 600;
            }
        """)
        self._header.addWidget(self._tool_name)
        
        self._status = QLabel("运行中")
        self._status.setStyleSheet("""
            QLabel {
                color: #f59e0b;
                font-size: 12px;
            }
        """)
        self._header.addWidget(self._status)
        
        self._header.addStretch()
        layout.addLayout(self._header)
        
        self._result_area = QWidget()
        self._result_layout = QVBoxLayout(self._result_area)
        layout.addWidget(self._result_area)
    
    def set_tool_name(self, name):
        """设置工具名称"""
        self._tool_name.setText(name)
    
    def set_status(self, status, is_success=True):
        """设置状态"""
        self._status.setText(status)
        color = "#10b981" if is_success else "#ef4444"
        self._status.setStyleSheet(f"QLabel {{ color: {color}; font-size: 12px; }}")
    
    def add_result(self, content):
        """添加结果"""
        label = QLabel(content)
        label.setWordWrap(True)
        label.setStyleSheet("color: #374151; font-size: 14px;")
        self._result_layout.addWidget(label)
    
    def clear_results(self):
        """清空结果"""
        while self._result_layout.count():
            item = self._result_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

class DrawingCanvas(QWidget):
    """绘图画布"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
    
    def _init_ui(self):
        self.setStyleSheet("""
            QWidget {
                background: white;
                border: 1px solid #e5e7eb;
                border-radius: 8px;
            }
        """)
        
        layout = QVBoxLayout(self)
        
        toolbar = QHBoxLayout()
        
        tools = ["pen", "brush", "eraser", "rectangle", "circle", "line"]
        for tool in tools:
            btn = QPushButton()
            btn.setIcon(QIcon(f"icons/{tool}.png"))
            btn.setFixedSize(36, 36)
            btn.setStyleSheet("""
                QPushButton {
                    background: #f3f4f6;
                    border: none;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background: #e5e7eb;
                }
                QPushButton:pressed {
                    background: #6366f1;
                }
            """)
            toolbar.addWidget(btn)
        
        toolbar.addStretch()
        layout.addLayout(toolbar)
        
        self._canvas = QFrame()
        self._canvas.setStyleSheet("background: white;")
        layout.addWidget(self._canvas)
    
    def clear_canvas(self):
        """清空画布"""
        pass