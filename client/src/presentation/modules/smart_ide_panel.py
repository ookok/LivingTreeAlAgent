"""
智能IDE模块面板
意图驱动的代码生成界面
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton,
    QTextEdit, QScrollArea, QFrame,
    QComboBox, QSplitter,
    QToolButton, QMenu,
    QPlainTextEdit,
)
from PyQt6.QtGui import QFont, QSyntaxHighlighter, QTextCharFormat, QColor


class SmartIDEPanel(QWidget):
    """智能IDE面板"""
    
    execute_requested = pyqtSignal(str)  # intent
    apply_code_requested = pyqtSignal(str)  # code
    save_to_workspace_requested = pyqtSignal(str)  # file_path
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        self.setStyleSheet("""
            SmartIDEPanel {
                background: #0D0D0D;
            }
            QLabel {
                color: #FFFFFF;
                font-family: "Microsoft YaHei", sans-serif;
            }
            QPushButton {
                background: #252525;
                border: none;
                border-radius: 8px;
                color: #FFFFFF;
                padding: 8px 16px;
                font-family: "Consolas", "Microsoft YaHei", sans-serif;
            }
            QPushButton:hover {
                background: #333333;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        # 标题栏
        header_layout = QHBoxLayout()
        
        title = QLabel("💻 智能IDE")
        title.setStyleSheet("""
            font-size: 20px;
            font-weight: bold;
            color: #00D4AA;
        """)
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        # 历史按钮
        history_btn = QPushButton("📋 历史")
        history_btn.clicked.connect(self._on_show_history)
        header_layout.addWidget(history_btn)
        
        layout.addLayout(header_layout)
        
        # 意图输入区
        intent_card = QFrame()
        intent_card.setStyleSheet("""
            QFrame {
                background: #1A1A1A;
                border-radius: 12px;
                padding: 16px;
            }
        """)
        intent_layout = QVBoxLayout(intent_card)
        intent_layout.setSpacing(12)
        
        intent_header = QLabel("🎯 意图工作台")
        intent_header.setStyleSheet("color: #00D4AA; font-weight: bold;")
        intent_layout.addWidget(intent_header)
        
        intent_input_layout = QHBoxLayout()
        intent_input_layout.setSpacing(12)
        
        self.intent_input = QLineEdit()
        self.intent_input.setPlaceholderText("输入你想实现的功能... 例如：帮我创建一个用户登录页面")
        self.intent_input.setMinimumHeight(48)
        self.intent_input.setStyleSheet("""
            QLineEdit {
                background: #252525;
                border: 1px solid #333333;
                border-radius: 8px;
                padding: 0 16px;
                color: #FFFFFF;
                font-size: 14px;
            }
            QLineEdit:focus {
                border-color: #00D4AA;
            }
        """)
        intent_input_layout.addWidget(self.intent_input, 1)
        
        execute_btn = QPushButton("🚀 执行")
        execute_btn.setMinimumWidth(100)
        execute_btn.setStyleSheet("""
            QPushButton {
                background: #00D4AA;
                color: #0D0D0D;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background: #00E8BB;
            }
        """)
        execute_btn.clicked.connect(self._on_execute)
        intent_input_layout.addWidget(execute_btn)
        
        intent_layout.addLayout(intent_input_layout)
        
        # 快捷意图
        quick_layout = QHBoxLayout()
        quick_layout.setSpacing(8)
        
        quick_label = QLabel("快捷意图:")
        quick_label.setStyleSheet("color: #888888; font-size: 12px;")
        quick_layout.addWidget(quick_label)
        
        quick_intents = ["创建API接口", "添加数据库模型", "写单元测试", "重构代码", "添加注释"]
        for intent in quick_intents:
            btn = QPushButton(intent)
            btn.setStyleSheet("""
                QPushButton {
                    background: #333333;
                    border: none;
                    border-radius: 6px;
                    padding: 4px 12px;
                    color: #A0A0A0;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background: #444444;
                    color: #FFFFFF;
                }
            """)
            btn.clicked.connect(lambda c, i=intent: self.intent_input.setText(i))
            quick_layout.addWidget(btn)
        
        quick_layout.addStretch()
        intent_layout.addLayout(quick_layout)
        
        layout.addWidget(intent_card)
        
        # 代码预览区
        code_card = QFrame()
        code_card.setStyleSheet("""
            QFrame {
                background: #1A1A1A;
                border-radius: 12px;
            }
        """)
        code_layout = QVBoxLayout(code_card)
        code_layout.setContentsMargins(0, 0, 0, 0)
        
        # 代码工具栏
        code_toolbar = QFrame()
        code_toolbar.setStyleSheet("background: #1F1F1F; border-top-left-radius: 12px; border-top-right-radius: 12px;")
        toolbar_layout = QHBoxLayout(code_toolbar)
        toolbar_layout.setContentsMargins(12, 8, 12, 8)
        
        self.file_tab = QLabel("📄 main.py")
        self.file_tab.setStyleSheet("""
            color: #FFFFFF;
            font-size: 13px;
            padding: 4px 12px;
            background: #252525;
            border-radius: 4px;
        """)
        toolbar_layout.addWidget(self.file_tab)
        
        toolbar_layout.addStretch()
        
        lang_label = QLabel("语言:")
        lang_label.setStyleSheet("color: #888888; font-size: 12px;")
        toolbar_layout.addWidget(lang_label)
        
        self.lang_combo = QComboBox()
        self.lang_combo.addItems(["Python", "JavaScript", "TypeScript", "Java", "Go", "Rust", "C++"])
        self.lang_combo.setCurrentText("Python")
        self.lang_combo.setFixedWidth(120)
        self.lang_combo.setStyleSheet("""
            QComboBox {
                background: #252525;
                border: none;
                border-radius: 4px;
                padding: 4px 8px;
                color: #FFFFFF;
                font-size: 12px;
            }
        """)
        toolbar_layout.addWidget(self.lang_combo)
        
        code_layout.addWidget(code_toolbar)
        
        # 代码编辑器
        self.code_editor = QPlainTextEdit()
        self.code_editor.setMinimumHeight(300)
        self.code_editor.setStyleSheet("""
            QPlainTextEdit {
                background: #1E1E1E;
                border: none;
                border-bottom-left-radius: 12px;
                border-bottom-right-radius: 12px;
                padding: 12px;
                color: #D4D4D4;
                font-family: "Consolas", "Fira Code", monospace;
                font-size: 14px;
                line-height: 1.5;
            }
        """)
        self.code_editor.setPlaceholderText("# 代码预览区\n# AI生成的代码将显示在这里...")
        code_layout.addWidget(self.code_editor, 1)
        
        layout.addWidget(code_card, 1)
        
        # 操作按钮
        action_layout = QHBoxLayout()
        action_layout.setSpacing(12)
        
        apply_btn = QPushButton("✅ 应用")
        apply_btn.setStyleSheet("""
            QPushButton {
                background: #00D4AA;
                color: #0D0D0D;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #00E8BB;
            }
        """)
        apply_btn.clicked.connect(self._on_apply)
        action_layout.addWidget(apply_btn)
        
        undo_btn = QPushButton("❌ 撤销")
        undo_btn.clicked.connect(self._on_undo)
        action_layout.addWidget(undo_btn)
        
        save_btn = QPushButton("📁 保存到工作区")
        save_btn.clicked.connect(self._on_save)
        action_layout.addWidget(save_btn)
        
        action_layout.addStretch()
        
        copy_btn = QPushButton("📋 复制")
        copy_btn.clicked.connect(self._on_copy)
        action_layout.addWidget(copy_btn)
        
        layout.addLayout(action_layout)
    
    def _on_execute(self):
        intent = self.intent_input.text().strip()
        if intent:
            self.execute_requested.emit(intent)
    
    def _on_show_history(self):
        pass  # TODO: 显示历史
    
    def _on_apply(self):
        code = self.code_editor.toPlainText()
        if code:
            self.apply_code_requested.emit(code)
    
    def _on_undo(self):
        self.code_editor.clear()
    
    def _on_save(self):
        pass  # TODO: 保存到工作区
    
    def _on_copy(self):
        self.code_editor.selectAll()
        self.code_editor.copy()
    
    def show_generated_code(self, code: str, filename: str = "main.py"):
        """显示生成的代码"""
        self.code_editor.setPlainText(code)
        self.file_tab.setText(f"📄 {filename}")
        lang_map = {
            ".py": "Python",
            ".js": "JavaScript",
            ".ts": "TypeScript",
            ".java": "Java",
            ".go": "Go",
            ".rs": "Rust",
            ".cpp": "C++",
        }
        ext = "." + filename.split(".")[-1] if "." in filename else ""
        lang = lang_map.get(ext, "Python")
        self.lang_combo.setCurrentText(lang)
    
    def set_generating(self, generating: bool):
        """设置生成状态"""
        self.intent_input.setEnabled(not generating)
        if generating:
            self.code_editor.setPlaceholderText("⏳ AI 正在思考和生成代码...")
        else:
            self.code_editor.setPlaceholderText("# 代码预览区\n# AI生成的代码将显示在这里...")


__all__ = ["SmartIDEPanel"]
