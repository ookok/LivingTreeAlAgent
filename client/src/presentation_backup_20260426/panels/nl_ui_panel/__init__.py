"""
NL UI Panel - 自然语言UI生成器面板
===================================

基于PyQt6的自然语言UI生成器界面。
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTextEdit, QPushButton, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QTabWidget,
    QGroupBox, QComboBox, QSpinBox, QCheckBox,
    QScrollArea, QFrame, QProgressBar, QToolButton,
    QMenu, QDialog, QSizePolicy, QSpacerItem,
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, pyqtSlot, QThread
from PyQt6.QtGui import QFont, QIcon, QAction, QTextCursor, QColor, QTextCharFormat


class NLUIPanel(QWidget):
    """自然语言UI生成器面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.driver = None
        self._init_ui()

    def _init_ui(self):
        """初始化UI"""
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        # 标题栏
        header = self._create_header()
        main_layout.addWidget(header)

        # 主内容区（左右分栏）
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧：输入和历史
        left_panel = self._create_left_panel()
        splitter.addWidget(left_panel)

        # 中间：预览
        center_panel = self._create_center_panel()
        splitter.addWidget(center_panel)

        # 右侧：组件库
        right_panel = self._create_right_panel()
        splitter.addWidget(right_panel)

        # 设置初始比例
        splitter.setSizes([300, 400, 250])
        main_layout.addWidget(splitter)

        # 状态栏
        self.status_bar = self._create_status_bar()
        main_layout.addWidget(self.status_bar)

    def _create_header(self) -> QWidget:
        """创建标题栏"""
        header = QFrame()
        header.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #1a1a2e, stop:1 #16213e);
                border-radius: 8px;
                padding: 8px;
            }
        """)

        layout = QHBoxLayout(header)
        layout.setContentsMargins(16, 8, 16, 8)

        # 标题
        title = QLabel("🎨 自然语言UI生成器")
        title.setStyleSheet("color: white; font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        layout.addStretch()

        # 示例按钮
        examples_btn = QPushButton("📝 示例")
        examples_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        examples_btn.clicked.connect(self._show_examples)
        layout.addWidget(examples_btn)

        # 帮助按钮
        help_btn = QPushButton("❓ 帮助")
        help_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        help_btn.clicked.connect(self._show_help)
        layout.addWidget(help_btn)

        return header

    def _create_left_panel(self) -> QWidget:
        """创建左侧面板"""
        panel = QFrame()
        panel.setStyleSheet("""
            QFrame {
                background: #1e1e1e;
                border-radius: 8px;
            }
        """)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)

        # 输入区域
        input_group = QGroupBox("📝 输入自然语言命令")
        input_group.setStyleSheet("""
            QGroupBox {
                color: #ffffff;
                background: #252526;
                border-radius: 6px;
                padding: 8px;
                margin-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        input_layout = QVBoxLayout()

        # 输入框
        self.input_edit = QTextEdit()
        self.input_edit.setPlaceholderText("例如：在主页添加一个「清理缓存」按钮，点击时清理临时文件")
        self.input_edit.setMaximumHeight(120)
        self.input_edit.setStyleSheet("""
            QTextEdit {
                background: #2d2d2d;
                color: #d4d4d4;
                border: 1px solid #3e3e42;
                border-radius: 4px;
                padding: 8px;
                font-family: 'Microsoft YaHei';
            }
        """)
        input_layout.addWidget(self.input_edit)

        # 按钮行
        btn_layout = QHBoxLayout()

        self.execute_btn = QPushButton("🚀 执行")
        self.execute_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.execute_btn.setStyleSheet("""
            QPushButton {
                background: #0e639c;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #1177bb;
            }
        """)
        self.execute_btn.clicked.connect(self._execute_command)
        btn_layout.addWidget(self.execute_btn)

        self.clear_btn = QPushButton("🗑️ 清空")
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.clicked.connect(lambda: self.input_edit.clear())
        btn_layout.addWidget(self.clear_btn)

        input_layout.addLayout(btn_layout)
        input_group.setLayout(input_layout)
        layout.addWidget(input_group)

        # 意图识别结果
        intent_group = QGroupBox("🧠 意图识别")
        intent_group.setStyleSheet(input_group.styleSheet())
        intent_layout = QVBoxLayout()

        self.intent_label = QLabel("等待输入...")
        self.intent_label.setWordWrap(True)
        self.intent_label.setStyleSheet("color: #d4d4d4; padding: 4px;")
        intent_layout.addWidget(self.intent_label)

        # 置信度
        self.confidence_bar = QProgressBar()
        self.confidence_bar.setRange(0, 100)
        self.confidence_bar.setValue(0)
        self.confidence_bar.setTextVisible(False)
        self.confidence_bar.setMaximumHeight(4)
        self.confidence_bar.setStyleSheet("""
            QProgressBar {
                background: #3e3e42;
                border: none;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background: #4ec9b0;
                border-radius: 2px;
            }
        """)
        intent_layout.addWidget(self.confidence_bar)

        intent_group.setLayout(intent_layout)
        layout.addWidget(intent_group)

        # 建议操作
        suggest_group = QGroupBox("💡 建议操作")
        suggest_group.setStyleSheet(input_group.styleSheet())
        suggest_layout = QVBoxLayout()

        self.suggest_list = QListWidget()
        self.suggest_list.setStyleSheet("""
            QListWidget {
                background: #2d2d2d;
                color: #d4d4d4;
                border: none;
                border-radius: 4px;
            }
            QListWidget::item {
                padding: 6px;
                border-bottom: 1px solid #3e3e42;
            }
            QListWidget::item:selected {
                background: #094771;
            }
        """)
        suggest_layout.addWidget(self.suggest_list)

        suggest_group.setLayout(suggest_layout)
        layout.addWidget(suggest_group)

        # 历史记录
        history_group = QGroupBox("📜 历史记录")
        history_group.setStyleSheet(input_group.styleSheet())
        history_layout = QVBoxLayout()

        self.history_list = QListWidget()
        self.history_list.setStyleSheet(self.suggest_list.styleSheet())
        self.history_list.itemClicked.connect(self._on_history_item_clicked)
        history_layout.addWidget(self.history_list)

        history_group.setLayout(history_layout)
        layout.addWidget(history_group)

        return panel

    def _create_center_panel(self) -> QWidget:
        """创建中间预览面板"""
        panel = QFrame()
        panel.setStyleSheet("""
            QFrame {
                background: #252526;
                border-radius: 8px;
            }
        """)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)

        # 标签页
        self.center_tabs = QTabWidget()
        self.center_tabs.setStyleSheet("""
            QTabWidget::pane {
                background: #1e1e1e;
                border-radius: 4px;
            }
            QTabBar::tab {
                background: #2d2d2d;
                color: #d4d4d4;
                padding: 8px 16px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background: #1e1e1e;
                color: #4ec9b0;
            }
        """)

        # 预览标签
        preview_tab = self._create_preview_tab()
        self.center_tabs.addTab(preview_tab, "👁️ 预览")

        # 代码标签
        code_tab = self._create_code_tab()
        self.center_tabs.addTab(code_tab, "📄 代码")

        # 安全标签
        security_tab = self._create_security_tab()
        self.center_tabs.addTab(security_tab, "🔒 安全")

        layout.addWidget(self.center_tabs)

        return panel

    def _create_preview_tab(self) -> QWidget:
        """创建预览标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(4, 4, 4, 4)

        # 预览工具栏
        toolbar = QHBoxLayout()
        self.preview_scale = QComboBox()
        self.preview_scale.addItems(["50%", "75%", "100%", "150%", "200%"])
        self.preview_scale.setCurrentText("100%")
        toolbar.addWidget(QLabel("缩放:"))
        toolbar.addWidget(self.preview_scale)
        toolbar.addStretch()

        self.preview_refresh_btn = QPushButton("🔄 刷新")
        toolbar.addWidget(self.preview_refresh_btn)

        layout.addLayout(toolbar)

        # 预览区域
        self.preview_area = QScrollArea()
        self.preview_area.setWidgetResizable(True)
        self.preview_area.setStyleSheet("""
            QScrollArea {
                background: #1e1e1e;
                border: 1px solid #3e3e42;
                border-radius: 4px;
            }
        """)

        self.preview_widget = QLabel("预览区域\n\n输入命令后将在这里显示UI预览...")
        self.preview_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_widget.setStyleSheet("""
            color: #6a6a6a;
            font-size: 14px;
            padding: 40px;
        """)
        self.preview_widget.setMinimumHeight(300)

        self.preview_area.setWidget(self.preview_widget)
        layout.addWidget(self.preview_area)

        # 预览操作
        actions = QHBoxLayout()
        self.apply_btn = QPushButton("✅ 应用变更")
        self.apply_btn.setEnabled(False)
        self.apply_btn.setStyleSheet("""
            QPushButton {
                background: #4ec9b0;
                color: #1e1e1e;
                border: none;
                border-radius: 4px;
                padding: 10px 20px;
                font-weight: bold;
            }
            QPushButton:disabled {
                background: #3e3e42;
                color: #6a6a6a;
            }
            QPushButton:hover:!disabled {
                background: #5dd9c0;
            }
        """)
        actions.addWidget(self.apply_btn)

        self.discard_btn = QPushButton("❌ 放弃")
        self.discard_btn.setEnabled(False)
        actions.addWidget(self.discard_btn)

        layout.addLayout(actions)

        return tab

    def _create_code_tab(self) -> QWidget:
        """创建代码标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(4, 4, 4, 4)

        # 代码工具栏
        toolbar = QHBoxLayout()

        self.code_language = QComboBox()
        self.code_language.addItems(["Python", "JavaScript", "JSON", "YAML"])
        toolbar.addWidget(QLabel("语言:"))
        toolbar.addWidget(self.code_language)

        toolbar.addStretch()

        self.copy_code_btn = QPushButton("📋 复制")
        toolbar.addWidget(self.copy_code_btn)

        layout.addLayout(toolbar)

        # 代码显示区
        self.code_edit = QTextEdit()
        self.code_edit.setReadOnly(True)
        self.code_edit.setStyleSheet("""
            QTextEdit {
                background: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3e3e42;
                border-radius: 4px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 13px;
            }
        """)
        layout.addWidget(self.code_edit)

        return tab

    def _create_security_tab(self) -> QWidget:
        """创建安全标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(4, 4, 4, 4)

        # 风险评分
        risk_group = QGroupBox("⚠️ 风险评分")
        risk_layout = QHBoxLayout()

        self.risk_score = QLabel("0")
        self.risk_score.setStyleSheet("""
            color: #4ec9b0;
            font-size: 32px;
            font-weight: bold;
        """)
        risk_layout.addWidget(self.risk_score)

        risk_layout.addWidget(QLabel("/ 100"))

        self.risk_level = QLabel("安全")
        self.risk_level.setStyleSheet("""
            color: #4ec9b0;
            font-size: 16px;
            font-weight: bold;
            padding: 4px 12px;
            background: #2d4a3e;
            border-radius: 4px;
        """)
        risk_layout.addWidget(self.risk_level)

        risk_layout.addStretch()
        risk_group.setLayout(risk_layout)
        layout.addWidget(risk_group)

        # 违规列表
        violations_group = QGroupBox("🚫 违规项")
        violations_layout = QVBoxLayout()

        self.violations_list = QListWidget()
        self.violations_list.setStyleSheet("""
            QListWidget {
                background: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3e3e42;
                border-radius: 4px;
            }
        """)
        violations_layout.addWidget(self.violations_list)

        violations_group.setLayout(violations_layout)
        layout.addWidget(violations_group)

        # 建议
        suggest_group = QGroupBox("💡 修复建议")
        suggest_layout = QVBoxLayout()

        self.suggest_text = QTextEdit()
        self.suggest_text.setReadOnly(True)
        self.suggest_text.setMaximumHeight(100)
        self.suggest_text.setStyleSheet("""
            QTextEdit {
                background: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3e3e42;
                border-radius: 4px;
            }
        """)
        suggest_layout.addWidget(self.suggest_text)

        suggest_group.setLayout(suggest_layout)
        layout.addWidget(suggest_group)

        return tab

    def _create_right_panel(self) -> QWidget:
        """创建右侧组件库面板"""
        panel = QFrame()
        panel.setStyleSheet("""
            QFrame {
                background: #1e1e1e;
                border-radius: 8px;
            }
        """)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)

        # 标题
        title = QLabel("🧩 组件库")
        title.setStyleSheet("color: white; font-size: 14px; font-weight: bold;")
        layout.addWidget(title)

        # 搜索
        self.component_search = QLineEdit()
        self.component_search.setPlaceholderText("搜索组件...")
        self.component_search.setStyleSheet("""
            QLineEdit {
                background: #2d2d2d;
                color: #d4d4d4;
                border: 1px solid #3e3e42;
                border-radius: 4px;
                padding: 6px;
            }
        """)
        layout.addWidget(self.component_search)

        # 组件分类
        self.component_tabs = QTabWidget()
        self.component_tabs.setStyleSheet("""
            QTabWidget::pane {
                background: #252526;
                border-radius: 4px;
            }
            QTabBar::tab {
                background: #2d2d2d;
                color: #d4d4d4;
                padding: 4px 8px;
                font-size: 12px;
            }
            QTabBar::tab:selected {
                background: #1e1e1e;
                color: #4ec9b0;
            }
        """)

        # 基础组件
        basic_tab = self._create_component_list(["按钮", "输入框", "文本", "图片"])
        self.component_tabs.addTab(basic_tab, "基础")

        # 容器组件
        container_tab = self._create_component_list(["卡片", "容器", "面板", "弹窗"])
        self.component_tabs.addTab(container_tab, "容器")

        # 业务组件
        biz_tab = self._create_component_list(["表格", "列表", "表单", "图表"])
        self.component_tabs.addTab(biz_tab, "业务")

        # 自定义组件
        custom_tab = self._create_component_list([])
        self.component_tabs.addTab(custom_tab, "自定义")

        layout.addWidget(self.component_tabs)

        # 组件属性
        props_group = QGroupBox("⚙️ 组件属性")
        props_layout = QVBoxLayout()

        self.props_list = QListWidget()
        self.props_list.setStyleSheet("""
            QListWidget {
                background: #252526;
                color: #d4d4d4;
                border: none;
                font-size: 12px;
            }
        """)
        props_layout.addWidget(self.props_list)

        props_group.setLayout(props_layout)
        layout.addWidget(props_group)

        return panel

    def _create_component_list(self, components: list) -> QWidget:
        """创建组件列表"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 4, 0, 4)

        list_widget = QListWidget()
        list_widget.setStyleSheet("""
            QListWidget {
                background: transparent;
                color: #d4d4d4;
                border: none;
            }
            QListWidget::item {
                background: #2d2d2d;
                padding: 8px;
                margin: 2px 0;
                border-radius: 4px;
            }
            QListWidget::item:hover {
                background: #3e3e42;
            }
        """)

        for comp in components:
            item = QListWidgetItem(f"📦 {comp}")
            list_widget.addItem(item)

        layout.addWidget(list_widget)
        return widget

    def _create_status_bar(self) -> QWidget:
        """创建状态栏"""
        bar = QFrame()
        bar.setStyleSheet("""
            QFrame {
                background: #007acc;
                border-radius: 4px;
                padding: 4px 8px;
            }
        """)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(8, 2, 8, 2)

        self.status_icon = QLabel("●")
        self.status_icon.setStyleSheet("color: #4ec9b0;")
        layout.addWidget(self.status_icon)

        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("color: white; font-size: 12px;")
        layout.addWidget(self.status_label)

        layout.addStretch()

        self.history_count = QLabel("历史: 0")
        self.history_count.setStyleSheet("color: rgba(255,255,255,0.7); font-size: 12px;")
        layout.addWidget(self.history_count)

        self.undo_btn = QPushButton("↩️ 撤销")
        self.undo_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.undo_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: white;
                border: none;
                padding: 2px 8px;
                font-size: 12px;
            }
            QPushButton:hover {
                background: rgba(255,255,255,0.1);
                border-radius: 4px;
            }
        """)
        self.undo_btn.clicked.connect(self._on_undo)
        layout.addWidget(self.undo_btn)

        self.redo_btn = QPushButton("↪️ 重做")
        self.redo_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.redo_btn.setStyleSheet(self.undo_btn.styleSheet())
        self.redo_btn.clicked.connect(self._on_redo)
        layout.addWidget(self.redo_btn)

        return bar

    def set_driver(self, driver):
        """设置NL UI驱动"""
        self.driver = driver

    @pyqtSlot()
    def _execute_command(self):
        """执行命令"""
        text = self.input_edit.toPlainText().strip()
        if not text:
            return

        # 添加到历史
        self.history_list.insertItem(0, text)
        self.history_count.setText(f"历史: {self.history_list.count()}")

        # 更新状态
        self.status_label.setText("正在处理...")
        self.status_bar.setStyleSheet("""
            QFrame {
                background: #f0a500;
                border-radius: 4px;
                padding: 4px 8px;
            }
        """)

        # 模拟处理
        self._process_command(text)

    def _process_command(self, text: str):
        """处理命令"""
        # 模拟意图识别
        self.intent_label.setText(f"识别到意图: 添加元素\n目标: 主页\n元素: 清理缓存按钮")
        self.confidence_bar.setValue(85)

        # 模拟代码生成
        code = '''def handle_clean_cache_click(event):
    """
    处理清理缓存按钮点击事件

    Args:
        event: 点击事件对象
    """
    import tempfile
    import shutil
    import os

    try:
        # 清理临时文件
        temp_dir = tempfile.gettempdir()
        count = 0
        for item in os.listdir(temp_dir):
            path = os.path.join(temp_dir, item)
            try:
                if os.path.isfile(path):
                    os.remove(path)
                    count += 1
                elif os.path.isdir(path):
                    shutil.rmtree(path)
                    count += 1
            except Exception:
                pass

        return {"status": "success", "cleaned": count}
    except Exception as e:
        return {"status": "error", "message": str(e)}
'''
        self.code_edit.setPlainText(code)

        # 更新预览
        self.preview_widget.setText(
            "┌─────────────────────────────────────┐\n"
            "│  🏠 主页                              │\n"
            "├─────────────────────────────────────┤\n"
            "│                                     │\n"
            "│   [🚀 快速路由]  [🔄 刷新]           │\n"
            "│                                     │\n"
            "│   ┌───────────────────────────┐     │\n"
            "│   │  🗑️ 清理缓存 (新添加)    │     │\n"
            "│   └───────────────────────────┘     │\n"
            "│                                     │\n"
            "└─────────────────────────────────────┘"
        )
        self.preview_widget.setStyleSheet("""
            color: #d4d4d4;
            font-family: 'Consolas', monospace;
            font-size: 12px;
            padding: 20px;
            background: #1e1e1e;
            border-radius: 4px;
        """)

        # 启用按钮
        self.apply_btn.setEnabled(True)
        self.discard_btn.setEnabled(True)

        # 恢复状态
        self.status_label.setText("处理完成")
        self.status_bar.setStyleSheet("""
            QFrame {
                background: #4ec9b0;
                border-radius: 4px;
                padding: 4px 8px;
            }
        """)

    def _on_history_item_clicked(self, item: QListWidgetItem):
        """历史项点击"""
        self.input_edit.setPlainText(item.text())

    @pyqtSlot()
    def _on_undo(self):
        """撤销"""
        self.status_label.setText("撤销...")

    @pyqtSlot()
    def _on_redo(self):
        """重做"""
        self.status_label.setText("重做...")

    @pyqtSlot()
    def _show_examples(self):
        """显示示例"""
        examples = [
            "在主页添加一个「测试连接」按钮",
            "给路由面板添加一个「刷新」按钮，点击时刷新状态",
            "创建一个新的面板，包含输入框和提交按钮",
            "把「清理缓存」按钮移动到右上角",
        ]
        self.input_edit.setPlainText("\n".join(examples))

    @pyqtSlot()
    def _show_help(self):
        """显示帮助"""
        help_text = """
╔══════════════════════════════════════════════════════════════╗
║           🎨 自然语言UI生成器 - 使用帮助                    ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  📝 输入格式示例：                                           ║
║     • 在主页添加一个「清理缓存」按钮                         ║
║     • 给路由面板添加一个「刷新」按钮，点击时刷新状态         ║
║     • 创建一个新的面板，包含输入框和提交按钮                 ║
║     • 把按钮移动到右上角                                    ║
║                                                              ║
║  🔧 支持的操作：                                            ║
║     • 添加组件（按钮、输入框、文本等）                      ║
║     • 绑定动作（点击事件、自定义功能）                      ║
║     • 移动/调整组件                                         ║
║     • 修改样式（颜色、尺寸）                                ║
║                                                              ║
║  🔒 安全特性：                                              ║
║     • 自动代码审计                                          ║
║     • 沙箱执行环境                                          ║
║     • 实时预览确认                                          ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
        """
        self.preview_widget.setText(help_text)
        self.preview_widget.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.preview_widget.setStyleSheet("""
            color: #d4d4d4;
            font-family: 'Microsoft YaHei';
            font-size: 13px;
            padding: 20px;
            background: #1e1e1e;
            border-radius: 4px;
            white-space: pre;
        """)