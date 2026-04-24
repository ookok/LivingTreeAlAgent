"""
智能写作模块面板
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton,
    QTextEdit, QScrollArea, QFrame,
    QComboBox, QRadioButton, QButtonGroup,
    QMenu, QToolButton,
)
from PyQt6.QtGui import QFont


class SmartWritingPanel(QWidget):
    """智能写作面板"""
    
    write_requested = pyqtSignal(str, str)  # topic, mode
    continue_requested = pyqtSignal()
    translate_requested = pyqtSignal(str)  # target_lang
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_mode = "article"
        self._setup_ui()
    
    def _setup_ui(self):
        self.setStyleSheet("""
            SmartWritingPanel {
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
                font-family: "Microsoft YaHei", sans-serif;
            }
            QPushButton:hover {
                background: #333333;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        # 标题
        title = QLabel("✍️ 智能写作")
        title.setStyleSheet("""
            font-size: 20px;
            font-weight: bold;
            color: #00D4AA;
        """)
        layout.addWidget(title)
        
        # 写作模式选择
        mode_layout = QHBoxLayout()
        mode_layout.setSpacing(12)
        
        mode_label = QLabel("写作模式:")
        mode_label.setStyleSheet("color: #A0A0A0;")
        mode_layout.addWidget(mode_label)
        
        self.mode_group = QButtonGroup()
        
        modes = [
            ("📝 文章", "article"),
            ("📧 邮件", "email"),
            ("📊 报告", "report"),
            ("💬 文案", "copy"),
            ("🌐 翻译", "translate"),
        ]
        
        for name, mode_id in modes:
            btn = QRadioButton(name)
            btn.setChecked(mode_id == "article")
            btn.clicked.connect(lambda c, m=mode_id: self._on_mode_change(m))
            self.mode_group.addButton(btn)
            mode_layout.addWidget(btn)
        
        mode_layout.addStretch()
        layout.addLayout(mode_layout)
        
        # 输入区
        input_card = QFrame()
        input_card.setStyleSheet("""
            QFrame {
                background: #1A1A1A;
                border-radius: 12px;
                padding: 16px;
            }
        """)
        input_layout = QVBoxLayout(input_card)
        input_layout.setSpacing(12)
        
        input_label = QLabel("📝 输入主题或要求")
        input_label.setStyleSheet("color: #00D4AA; font-weight: bold;")
        input_layout.addWidget(input_label)
        
        self.topic_input = QTextEdit()
        self.topic_input.setPlaceholderText("输入写作主题或具体要求...\n例如：帮我写一篇关于人工智能发展趋势的文章，约2000字")
        self.topic_input.setMinimumHeight(100)
        self.topic_input.setMaximumHeight(150)
        self.topic_input.setStyleSheet("""
            QTextEdit {
                background: #252525;
                border: none;
                border-radius: 8px;
                padding: 12px;
                color: #FFFFFF;
                font-size: 14px;
                line-height: 1.6;
            }
            QTextEdit::placeholder {
                color: #666666;
            }
        """)
        input_layout.addWidget(self.topic_input)
        
        # 操作按钮
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        
        write_btn = QPushButton("✨ 开始写作")
        write_btn.setStyleSheet("""
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
        write_btn.clicked.connect(self._on_write)
        btn_layout.addWidget(write_btn)
        
        continue_btn = QPushButton("🔄 续写")
        continue_btn.clicked.connect(self._on_continue)
        btn_layout.addWidget(continue_btn)
        
        # 翻译下拉菜单
        translate_menu = QMenu(self)
        translate_menu.addAction("🇨🇳 中文", lambda: self._on_translate("zh"))
        translate_menu.addAction("🇺🇸 English", lambda: self._on_translate("en"))
        translate_menu.addAction("🇯🇵 日本語", lambda: self._on_translate("ja"))
        translate_menu.addAction("🇰🇷 한국어", lambda: self._on_translate("ko"))
        
        translate_btn = QPushButton("🌐 翻译")
        translate_btn.setMenu(translate_menu)
        btn_layout.addWidget(translate_btn)
        
        btn_layout.addStretch()
        
        input_layout.addLayout(btn_layout)
        layout.addWidget(input_card)
        
        # 写作结果区
        result_card = QFrame()
        result_card.setStyleSheet("""
            QFrame {
                background: #1A1A1A;
                border-radius: 12px;
            }
        """)
        result_layout = QVBoxLayout(result_card)
        result_layout.setContentsMargins(0, 0, 0, 0)
        
        # 结果工具栏
        result_toolbar = QFrame()
        result_toolbar.setStyleSheet("background: #1F1F1F; border-top-left-radius: 12px; border-top-right-radius: 12px;")
        toolbar_layout = QHBoxLayout(result_toolbar)
        toolbar_layout.setContentsMargins(12, 8, 12, 8)
        
        result_label = QLabel("📄 写作结果")
        result_label.setStyleSheet("color: #00D4AA; font-weight: bold;")
        toolbar_layout.addWidget(result_label)
        
        toolbar_layout.addStretch()
        
        word_count_label = QLabel("字数: 0")
        word_count_label.setStyleSheet("color: #888888; font-size: 12px;")
        self.word_count_label = word_count_label
        toolbar_layout.addWidget(word_count_label)
        
        result_layout.addWidget(result_toolbar)
        
        # 结果文本区
        self.result_text = QTextEdit()
        self.result_text.setMinimumHeight(300)
        self.result_text.setStyleSheet("""
            QTextEdit {
                background: #1E1E1E;
                border: none;
                border-bottom-left-radius: 12px;
                border-bottom-right-radius: 12px;
                padding: 16px;
                color: #D4D4D4;
                font-size: 14px;
                line-height: 1.8;
            }
        """)
        self.result_text.setPlaceholderText("写作结果将显示在这里...")
        result_layout.addWidget(self.result_text, 1)
        
        layout.addWidget(result_card, 1)
        
        # 底部操作按钮
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(12)
        
        copy_btn = QPushButton("📋 复制")
        copy_btn.clicked.connect(self._on_copy)
        bottom_layout.addWidget(copy_btn)
        
        save_btn = QPushButton("💾 保存")
        save_btn.clicked.connect(self._on_save)
        bottom_layout.addWidget(save_btn)
        
        export_btn = QPushButton("📤 导出")
        export_btn.clicked.connect(self._on_export)
        bottom_layout.addWidget(export_btn)
        
        bottom_layout.addStretch()
        
        bottom_layout.addWidget(QLabel())  # spacer
        layout.addLayout(bottom_layout)
    
    def _on_mode_change(self, mode: str):
        self._current_mode = mode
    
    def _on_write(self):
        topic = self.topic_input.toPlainText().strip()
        if topic:
            self.write_requested.emit(topic, self._current_mode)
    
    def _on_continue(self):
        self.continue_requested.emit()
    
    def _on_translate(self, target_lang: str):
        self.translate_requested.emit(target_lang)
    
    def _on_copy(self):
        self.result_text.selectAll()
        self.result_text.copy()
    
    def _on_save(self):
        pass  # TODO: 保存
    
    def _on_export(self):
        pass  # TODO: 导出
    
    def show_result(self, content: str):
        """显示写作结果"""
        self.result_text.setPlainText(content)
        word_count = len(content.replace(" ", "").replace("\n", ""))
        self.word_count_label.setText(f"字数: {word_count}")
    
    def set_generating(self, generating: bool):
        """设置生成状态"""
        self.topic_input.setEnabled(not generating)
        if generating:
            self.result_text.setPlaceholderText("⏳ AI 正在写作中...")
        else:
            self.result_text.setPlaceholderText("写作结果将显示在这里...")


__all__ = ["SmartWritingPanel"]
