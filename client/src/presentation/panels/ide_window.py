"""IDE窗口面板 - 整合代码编辑器和预览功能"""

from PyQt6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QSplitter,
    QTabWidget, QTextEdit, QLabel
)
from PyQt6.QtCore import Qt, pyqtSignal
from .components.smart_code_editor import SmartCodeEditor

class IDEWindow(QFrame):
    """IDE窗口面板"""
    
    run_code = pyqtSignal(str)
    save_file = pyqtSignal(str, str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
    
    def _init_ui(self):
        self.setStyleSheet("""
            QFrame {
                background: #0d1117;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        self._tab_widget = QTabWidget()
        self._tab_widget.setStyleSheet("""
            QTabWidget::tab-bar {
                alignment: left;
            }
            QTabBar::tab {
                background: #161b22;
                color: #8b949e;
                padding: 8px 16px;
                margin-right: 4px;
                border-radius: 4px 4px 0 0;
            }
            QTabBar::tab:selected {
                background: #0d1117;
                color: #e6edf3;
            }
        """)
        
        self._code_editor = SmartCodeEditor()
        self._code_editor.run_code.connect(self.run_code)
        self._tab_widget.addTab(self._code_editor, "main.py")
        
        self._output_panel = QTextEdit()
        self._output_panel.setReadOnly(True)
        self._output_panel.setStyleSheet("""
            QTextEdit {
                background: #0d1117;
                color: #8b949e;
                font-family: 'JetBrains Mono', monospace;
                font-size: 12px;
                border: none;
            }
        """)
        self._tab_widget.addTab(self._output_panel, "Output")
        
        layout.addWidget(self._tab_widget)
    
    def set_code(self, code):
        """设置代码"""
        self._code_editor.set_code(code)
    
    def get_code(self):
        """获取代码"""
        return self._code_editor.get_code()
    
    def add_output(self, text):
        """添加输出"""
        current = self._output_panel.toPlainText()
        self._output_panel.setPlainText(current + text + "\n")
        
        scroll_bar = self._output_panel.verticalScrollBar()
        scroll_bar.setValue(scroll_bar.maximum())
    
    def clear_output(self):
        """清空输出"""
        self._output_panel.clear()
    
    def add_file_tab(self, filename, content=""):
        """添加文件标签页"""
        editor = SmartCodeEditor()
        editor.set_code(content)
        self._tab_widget.addTab(editor, filename)
    
    def get_active_tab(self):
        """获取活动标签页"""
        return self._tab_widget.currentWidget()

class PreviewPanel(QFrame):
    """预览面板"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
    
    def _init_ui(self):
        self.setStyleSheet("""
            QFrame {
                background: #ffffff;
                border-left: 1px solid #e5e7eb;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        
        header = QHBoxLayout()
        header.addWidget(QLabel("预览"))
        header.addStretch()
        layout.addLayout(header)
        
        self._preview_label = QLabel()
        self._preview_label.setStyleSheet("""
            QLabel {
                border: 1px dashed #d1d5db;
                border-radius: 8px;
                padding: 16px;
                text-align: center;
                color: #9ca3af;
            }
        """)
        self._preview_label.setText("预览区域")
        layout.addWidget(self._preview_label)
    
    def set_content(self, content):
        """设置预览内容"""
        self._preview_label.setText(content)