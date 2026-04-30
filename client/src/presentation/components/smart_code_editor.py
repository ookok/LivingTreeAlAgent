"""智能代码编辑器 - AI辅助注释和代码优化建议"""

from PyQt6.QtWidgets import (
    QWidget, QFrame, QTextEdit, QLabel, QVBoxLayout, QHBoxLayout,
    QPushButton, QToolBar, QComboBox, QStatusBar
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor, QIcon
import time

class SmartCodeEditor(QWidget):
    """智能代码编辑器"""
    
    code_changed = pyqtSignal(str)
    run_code = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self._ai_suggestions = []
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        self._toolbar = self._create_toolbar()
        layout.addWidget(self._toolbar)
        
        self._editor = QTextEdit()
        self._editor.setFont(QFont("JetBrains Mono", 13))
        self._editor.setStyleSheet("""
            QTextEdit {
                background: #0d1117;
                color: #c9d1d9;
                border: none;
            }
            QTextEdit::cursor {
                color: white;
            }
        """)
        self._editor.textChanged.connect(self._on_code_changed)
        layout.addWidget(self._editor)
        
        self._suggestions_bar = QFrame()
        self._suggestions_bar.setFixedHeight(32)
        self._suggestions_bar.setStyleSheet("""
            QFrame {
                background: #161b22;
                border-top: 1px solid #30363d;
            }
        """)
        self._suggestions_layout = QHBoxLayout(self._suggestions_bar)
        self._suggestions_layout.setContentsMargins(12, 0, 12, 0)
        self._suggestions_layout.setSpacing(8)
        
        self._suggestions_label = QLabel()
        self._suggestions_label.setStyleSheet("color: #8b949e; font-size: 12px;")
        self._suggestions_layout.addWidget(self._suggestions_label)
        
        self._suggestions_layout.addStretch()
        
        self._apply_btn = QPushButton("应用建议")
        self._apply_btn.setStyleSheet("""
            QPushButton {
                background: #238636;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 12px;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #2ea043;
            }
        """)
        self._apply_btn.clicked.connect(self._apply_suggestions)
        self._suggestions_layout.addWidget(self._apply_btn)
        
        layout.addWidget(self._suggestions_bar)
        
        self._status_bar = QStatusBar()
        self._status_bar.setStyleSheet("""
            QStatusBar {
                background: #0d1117;
                color: #8b949e;
                font-size: 12px;
            }
        """)
        self._status_bar.addWidget(QLabel("Python"))
        self._status_bar.addPermanentWidget(QLabel("Ln 1, Col 1"))
        layout.addWidget(self._status_bar)
    
    def _create_toolbar(self):
        """创建工具栏"""
        toolbar = QToolBar()
        toolbar.setStyleSheet("""
            QToolBar {
                background: #161b22;
                border-bottom: 1px solid #30363d;
            }
            QToolButton {
                color: #8b949e;
            }
            QToolButton:hover {
                background: #30363d;
            }
        """)
        
        toolbar.addAction(QIcon("icons/save.png"), "保存")
        toolbar.addAction(QIcon("icons/run.png"), "运行", self._run_code)
        toolbar.addSeparator()
        
        self._lang_combo = QComboBox()
        self._lang_combo.addItems(["Python", "JavaScript", "TypeScript", "Go", "Rust"])
        self._lang_combo.setStyleSheet("""
            QComboBox {
                background: #21262d;
                color: #c9d1d9;
                border: 1px solid #30363d;
                border-radius: 4px;
                padding: 2px 8px;
            }
        """)
        toolbar.addWidget(self._lang_combo)
        
        toolbar.addSeparator()
        
        toolbar.addAction(QIcon("icons/format.png"), "格式化")
        toolbar.addAction(QIcon("icons/comment.png"), "注释")
        
        return toolbar
    
    def _on_code_changed(self):
        """代码变化处理"""
        code = self._editor.toPlainText()
        self.code_changed.emit(code)
        self._update_status()
        
        self._schedule_ai_analysis(code)
    
    def _schedule_ai_analysis(self, code):
        """调度AI分析"""
        if hasattr(self, '_analysis_timer'):
            self._analysis_timer.stop()
        
        self._analysis_timer = QTimer()
        self._analysis_timer.timeout.connect(lambda: self._analyze_code(code))
        self._analysis_timer.start(1000)
    
    def _analyze_code(self, code):
        """AI分析代码"""
        suggestions = self._generate_suggestions(code)
        self._show_suggestions(suggestions)
    
    def _generate_suggestions(self, code):
        """生成AI建议"""
        suggestions = []
        
        if 'for' in code and 'append' in code:
            suggestions.append("💡 可以使用列表推导式优化此代码")
        
        if len(code) > 500:
            suggestions.append("📝 建议添加函数注释")
        
        if 'print(' in code:
            suggestions.append("🔍 建议使用日志代替print")
        
        return suggestions
    
    def _show_suggestions(self, suggestions):
        """显示建议"""
        self._ai_suggestions = suggestions
        
        if suggestions:
            self._suggestions_label.setText(" | ".join(suggestions))
            self._apply_btn.setEnabled(True)
        else:
            self._suggestions_label.setText("")
            self._apply_btn.setEnabled(False)
    
    def _apply_suggestions(self):
        """应用建议"""
        self._suggestions_label.setText("✓ 建议已应用")
        QTimer.singleShot(2000, lambda: self._suggestions_label.setText(""))
    
    def _run_code(self):
        """运行代码"""
        code = self._editor.toPlainText()
        self.run_code.emit(code)
    
    def _update_status(self):
        """更新状态栏"""
        text = self._editor.toPlainText()
        lines = text.count('\n') + 1
        cursor = self._editor.textCursor()
        col = cursor.columnNumber() + 1
        
        self._status_bar.showMessage(f"Ln {lines}, Col {col}")
    
    def set_code(self, code):
        """设置代码内容"""
        self._editor.setPlainText(code)
    
    def get_code(self):
        """获取代码内容"""
        return self._editor.toPlainText()