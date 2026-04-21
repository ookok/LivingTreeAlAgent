"""
智能写作UI面板
Smart Writing UI Panel

双模式界面：
- 咨询模式：三栏布局（大纲-编辑-参考）
- 创作模式：单栏沉浸布局

功能：
- 模式切换
- AI三级协同
- 灵感引擎
- 上下文感知
"""

import asyncio
import time
from pathlib import Path
from typing import Optional, Callable
from dataclasses import dataclass

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread, pyqtSlot
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTextEdit, QPushButton, QLabel, QComboBox, QLineEdit,
    QTabWidget, QListWidget, QListWidgetItem, QGroupBox,
    QScrollArea, QProgressBar, QCheckBox, QSpinBox,
    QFileDialog, QMessageBox, QToolBar, QFrame,
    QStackedWidget, QScrollBar, QStatusBar, QMenuBar,
    QMenu, QToolButton, QDockWidget, QTextBrowser,
    QDialog, QDialogButtonBox, QFormLayout, QSlider,
    QSizePolicy, QSpacerItem, QApplication
)
from PyQt6.QtGui import (
    QFont, QAction, QIcon, QTextCursor, QTextCharFormat,
    QColor, QPalette, QTextDocument, QTextBlockFormat,
    QKeySequence, QShortcut
)
from PyQt6.QtCore import QSize


# 尝试导入核心模块
try:
    from core.smart_writing import (
        DualEngineCore, WritingMode, AILevel,
        ConsultingMode, ConsultingFramework, DocumentType,
        CreativeMode, WritingGenre, EmotionalTone,
        AICollaborator, AITask,
        ContextAwareSystem, AdaptiveStrategy
    )
    CORE_AVAILABLE = True
except ImportError:
    CORE_AVAILABLE = False


# ==================== 样式定义 ====================

DARK_STYLE = """
/* 全局 */
QWidget {
    background-color: #1e1e1e;
    color: #e0e0e0;
    font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
    font-size: 13px;
}

/* 按钮 */
QPushButton {
    background-color: #2d2d2d;
    border: 1px solid #3d3d3d;
    border-radius: 4px;
    padding: 6px 12px;
    min-width: 60px;
}
QPushButton:hover {
    background-color: #3d3d3d;
    border-color: #4d4d4d;
}
QPushButton:pressed {
    background-color: #1d1d1d;
}
QPushButton:disabled {
    background-color: #252525;
    color: #666;
}
QPushButton.primary {
    background-color: #0d7377;
    border-color: #0d7377;
}
QPushButton.primary:hover {
    background-color: #0e8a8e;
}

/* 组合框 */
QComboBox {
    background-color: #2d2d2d;
    border: 1px solid #3d3d3d;
    border-radius: 4px;
    padding: 5px 10px;
}
QComboBox::drop-down {
    border: none;
    width: 20px;
}
QComboBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #888;
}

/* 输入框 */
QLineEdit, QTextEdit {
    background-color: #252525;
    border: 1px solid #3d3d3d;
    border-radius: 4px;
    padding: 6px 10px;
}
QLineEdit:focus, QTextEdit:focus {
    border-color: #0d7377;
}

/* 分组框 */
QGroupBox {
    border: 1px solid #3d3d3d;
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 10px;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
}

/* 列表 */
QListWidget, QListView {
    background-color: #252525;
    border: 1px solid #3d3d3d;
    border-radius: 4px;
}
QListWidget::item:selected {
    background-color: #0d7377;
}

/* 标签页 */
QTabWidget::pane {
    border: 1px solid #3d3d3d;
    border-radius: 4px;
}
QTabBar::tab {
    background-color: #2d2d2d;
    border: 1px solid #3d3d3d;
    padding: 8px 16px;
    margin-right: 2px;
}
QTabBar::tab:selected {
    background-color: #0d7377;
}
QTabBar::tab:hover:!selected {
    background-color: #3d3d3d;
}

/* 工具栏 */
QToolBar {
    background-color: #1e1e1e;
    border: none;
    spacing: 4px;
    padding: 4px;
}
QToolBar::separator {
    background-color: #3d3d3d;
    width: 1px;
    margin: 4px 8px;
}

/* 滚动条 */
QScrollBar:vertical {
    background-color: #1e1e1e;
    width: 10px;
}
QScrollBar::handle:vertical {
    background-color: #3d3d3d;
    border-radius: 5px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover {
    background-color: #4d4d4d;
}

/* 分割器 */
QSplitter::handle {
    background-color: #3d3d3d;
}
QSplitter::handle:hover {
    background-color: #0d7377;
}

/* 状态栏 */
QStatusBar {
    background-color: #1a1a1a;
    border-top: 1px solid #2d2d2d;
}

/* 菜单 */
QMenu {
    background-color: #252525;
    border: 1px solid #3d3d3d;
}
QMenu::item:selected {
    background-color: #0d7377;
}

/* 工具提示 */
QToolTip {
    background-color: #2d2d2d;
    border: 1px solid #3d3d3d;
    padding: 4px 8px;
    border-radius: 4px;
}

/* 进度条 */
QProgressBar {
    background-color: #2d2d2d;
    border: none;
    border-radius: 4px;
    text-align: center;
}
QProgressBar::chunk {
    background-color: #0d7377;
    border-radius: 4px;
}

/* 滑块 */
QSlider::groove:horizontal {
    background-color: #2d2d2d;
    height: 6px;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    background-color: #0d7377;
    width: 14px;
    margin: -4px 0;
    border-radius: 7px;
}
"""


# ==================== 主面板 ====================

class SmartWritingPanel(QWidget):
    """
    智能写作面板
    
    集成双模式写作界面
    """
    
    # 信号
    status_changed = pyqtSignal(str)
    mode_changed = pyqtSignal(str)
    content_changed = pyqtSignal(str)
    
    def __init__(self, parent=None, hermes_agent=None):
        super().__init__(parent)
        
        self.agent = hermes_agent
        
        # 初始化核心系统
        self._init_core()
        
        # 初始化UI
        self._setup_ui()
        
        # 连接信号
        self._connect_signals()
        
        # 启动定时器
        self._start_timers()
    
    def _init_core(self):
        """初始化核心系统"""
        if not CORE_AVAILABLE:
            self.dual_engine = None
            self.consulting_mode = None
            self.creative_mode = None
            self.ai_collaborator = None
            self.context_aware = None
            return
        
        self.dual_engine = DualEngineCore(self.agent)
        self.consulting_mode = ConsultingMode(self.agent)
        self.creative_mode = CreativeMode(self.agent)
        self.ai_collaborator = AICollaborator(self.agent)
        self.context_aware = ContextAwareSystem()
        
        # 设置回调
        if self.dual_engine:
            self.dual_engine.on_mode_changed = self._on_mode_changed
    
    def _setup_ui(self):
        """设置UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 顶部工具栏
        toolbar = self._create_toolbar()
        main_layout.addWidget(toolbar)
        
        # 主内容区
        self.content_stack = QStackedWidget()
        
        # 咨询模式布局
        self.consulting_panel = self._create_consulting_panel()
        self.content_stack.addWidget(self.consulting_panel)
        
        # 创作模式布局
        self.creative_panel = self._create_creative_panel()
        self.content_stack.addWidget(self.creative_panel)
        
        main_layout.addWidget(self.content_stack)
        
        # 底部状态栏
        self.status_bar = self._create_status_bar()
        main_layout.addWidget(self.status_bar)
        
        # 默认显示创作模式
        self.content_stack.setCurrentWidget(self.creative_panel)
        self._update_mode_ui(WritingMode.CREATIVE)
    
    def _create_toolbar(self) -> QToolBar:
        """创建工具栏"""
        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.setFixedHeight(44)
        
        # 模式切换
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["📊 咨询模式", "✨ 创作模式"])
        self.mode_combo.setMinimumWidth(120)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_switch)
        toolbar.addWidget(QLabel("模式: "))
        toolbar.addWidget(self.mode_combo)
        
        toolbar.addSeparator()
        
        # 新建/保存
        new_btn = QPushButton("📄 新建")
        new_btn.clicked.connect(self._new_document)
        toolbar.addWidget(new_btn)
        
        save_btn = QPushButton("💾 保存")
        save_btn.clicked.connect(self._save_document)
        toolbar.addWidget(save_btn)
        
        export_btn = QPushButton("📤 导出")
        export_btn.clicked.connect(self._export_document)
        toolbar.addWidget(export_btn)
        
        toolbar.addSeparator()
        
        # AI功能
        self.ai_level_combo = QComboBox()
        self.ai_level_combo.addItems(["🤖 L1 即时辅助", "🧠 L2 深度协作", "💡 L3 创意伙伴"])
        self.ai_level_combo.setToolTip("选择AI处理层级")
        toolbar.addWidget(self.ai_level_combo)
        
        polish_btn = QPushButton("🎨 润色")
        polish_btn.clicked.connect(self._polish_text)
        toolbar.addWidget(polish_btn)
        
        expand_btn = QPushButton("📝 续写")
        expand_btn.clicked.connect(self._expand_text)
        toolbar.addWidget(expand_btn)
        
        toolbar.addSeparator()
        
        # 设置
        settings_btn = QPushButton("⚙️")
        settings_btn.setFixedWidth(36)
        settings_btn.setToolTip("设置")
        settings_btn.clicked.connect(self._show_settings)
        toolbar.addWidget(settings_btn)
        
        # 沉浸模式
        focus_btn = QPushButton("🎯 专注")
        focus_btn.setToolTip("进入专注模式")
        focus_btn.clicked.connect(self._toggle_focus_mode)
        toolbar.addWidget(focus_btn)
        
        return toolbar
    
    def _create_consulting_panel(self) -> QWidget:
        """创建咨询模式面板"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        
        # 左侧：项目和大纲
        left_panel = self._create_consulting_left()
        layout.addWidget(left_panel, 0)
        
        # 中间：编辑器
        center_panel = self._create_consulting_center()
        layout.addWidget(center_panel, 1)
        
        # 右侧：参考和工具
        right_panel = self._create_consulting_right()
        layout.addWidget(right_panel, 0)
        
        return widget
    
    def _create_consulting_left(self) -> QWidget:
        """创建咨询左侧面板"""
        widget = QWidget()
        widget.setMaximumWidth(280)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # 项目信息
        project_group = QGroupBox("📁 项目")
        project_layout = QVBoxLayout(project_group)
        
        self.project_name_edit = QLineEdit()
        self.project_name_edit.setPlaceholderText("项目名称")
        project_layout.addWidget(self.project_name_edit)
        
        self.doc_type_combo = QComboBox()
        self.doc_type_combo.addItems([
            "市场研究报告", "战略规划", "尽职调查",
            "竞争分析", "可行性研究", "商业提案"
        ])
        project_layout.addWidget(QLabel("文档类型"))
        project_layout.addWidget(self.doc_type_combo)
        
        layout.addWidget(project_group)
        
        # 大纲
        outline_group = QGroupBox("📋 文档大纲")
        outline_layout = QVBoxLayout(outline_group)
        
        self.outline_list = QListWidget()
        self.outline_list.setMaximumHeight(200)
        self.outline_list.itemClicked.connect(self._on_outline_item_clicked)
        outline_layout.addWidget(self.outline_list)
        
        gen_outline_btn = QPushButton("🔄 生成大纲")
        gen_outline_btn.clicked.connect(self._generate_outline)
        outline_layout.addWidget(gen_outline_btn)
        
        layout.addWidget(outline_group)
        
        # 框架
        framework_group = QGroupBox("🧩 分析框架")
        framework_layout = QVBoxLayout(framework_group)
        
        self.framework_combo = QComboBox()
        self.framework_combo.addItems([
            "麦肯锡7S", "SWOT分析", "波特五力",
            "PEST分析", "BCG矩阵", "商业画布"
        ])
        framework_layout.addWidget(self.framework_combo)
        
        gen_framework_btn = QPushButton("生成框架")
        gen_framework_btn.clicked.connect(self._generate_framework)
        framework_layout.addWidget(gen_framework_btn)
        
        layout.addWidget(framework_group)
        
        layout.addStretch()
        
        return widget
    
    def _create_consulting_center(self) -> QWidget:
        """创建咨询中心面板"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # 标题
        title_layout = QHBoxLayout()
        title_layout.addWidget(QLabel("标题:"))
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("输入文档标题...")
        self.title_edit.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        title_layout.addWidget(self.title_edit)
        layout.addLayout(title_layout)
        
        # 编辑器
        self.consulting_editor = QTextEdit()
        self.consulting_editor.setFont(QFont("Microsoft YaHei", 12))
        self.consulting_editor.setPlaceholderText(
            "开始撰写文档内容...\n\n"
            "提示：\n"
            "- 使用大纲功能规划章节\n"
            "- 使用框架功能生成分析\n"
            "- 使用润色功能优化文字"
        )
        self.consulting_editor.textChanged.connect(self._on_editor_text_changed)
        layout.addWidget(self.consulting_editor)
        
        # 字数统计
        stats_layout = QHBoxLayout()
        stats_layout.addStretch()
        self.word_count_label = QLabel("字数: 0")
        stats_layout.addWidget(self.word_count_label)
        self.char_count_label = QLabel("字符: 0")
        stats_layout.addWidget(self.char_count_label)
        layout.addLayout(stats_layout)
        
        return widget
    
    def _create_consulting_right(self) -> QWidget:
        """创建咨询右侧面板"""
        widget = QWidget()
        widget.setMaximumWidth(260)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # 参考资料
        ref_group = QGroupBox("📚 参考资料")
        ref_layout = QVBoxLayout(ref_group)
        
        self.ref_list = QListWidget()
        self.ref_list.setMaximumHeight(150)
        ref_layout.addWidget(self.ref_list)
        
        add_ref_btn = QPushButton("+ 添加参考")
        add_ref_btn.clicked.connect(self._add_reference)
        ref_layout.addWidget(add_ref_btn)
        
        layout.addWidget(ref_group)
        
        # 数据处理
        data_group = QGroupBox("📊 数据处理")
        data_layout = QVBoxLayout(data_group)
        
        import_data_btn = QPushButton("📥 导入数据")
        import_data_btn.clicked.connect(self._import_data)
        data_layout.addWidget(import_data_btn)
        
        gen_chart_btn = QPushButton("📈 生成图表")
        gen_chart_btn.clicked.connect(self._generate_chart)
        data_layout.addWidget(gen_chart_btn)
        
        layout.addWidget(data_group)
        
        # 一致性检查
        check_group = QGroupBox("✅ 质量检查")
        check_layout = QVBoxLayout(check_group)
        
        check_logic_btn = QPushButton("🔍 逻辑检查")
        check_logic_btn.clicked.connect(self._check_consistency)
        check_layout.addWidget(check_logic_btn)
        
        check_format_btn = QPushButton("📋 格式检查")
        check_format_btn.clicked.connect(self._check_format)
        check_layout.addWidget(check_format_btn)
        
        layout.addWidget(check_group)
        
        # PPT导出
        ppt_group = QGroupBox("📊 演示")
        ppt_layout = QVBoxLayout(ppt_group)
        
        gen_ppt_btn = QPushButton("📑 生成PPT大纲")
        gen_ppt_btn.clicked.connect(self._generate_ppt_outline)
        ppt_layout.addWidget(gen_ppt_btn)
        
        layout.addWidget(ppt_group)
        
        layout.addStretch()
        
        return widget
    
    def _create_creative_panel(self) -> QWidget:
        """创建创作模式面板"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        
        # 顶部设置栏
        settings_bar = QHBoxLayout()
        
        # 类型选择
        settings_bar.addWidget(QLabel("类型:"))
        self.genre_combo = QComboBox()
        self.genre_combo.addItems([
            "小说", "短篇小说", "剧本", "诗歌",
            "散文", "奇幻", "科幻", "悬疑"
        ])
        settings_bar.addWidget(self.genre_combo)
        
        # 视角选择
        settings_bar.addWidget(QLabel("视角:"))
        self.voice_combo = QComboBox()
        self.voice_combo.addItems(["第三人称", "第一人称", "全知视角"])
        settings_bar.addWidget(self.voice_combo)
        
        settings_bar.addStretch()
        
        # 字数目标
        settings_bar.addWidget(QLabel("目标:"))
        self.word_target_spin = QSpinBox()
        self.word_target_spin.setRange(1000, 500000)
        self.word_target_spin.setSingleStep(1000)
        self.word_target_spin.setValue(50000)
        settings_bar.addWidget(self.word_target_spin)
        settings_bar.addWidget(QLabel("字"))
        
        layout.addLayout(settings_bar)
        
        # 编辑器（沉浸式）
        self.creative_editor = QTextEdit()
        self.creative_editor.setFont(QFont("Microsoft YaHei", 14))
        self.creative_editor.setPlaceholderText(
            "开始你的创作...\n\n"
            "快捷命令:\n"
            "/inspire - 获取灵感\n"
            "/character - 创建角色\n"
            "/timeline - 查看时间线\n"
            "/focus - 专注模式"
        )
        self.creative_editor.textChanged.connect(self._on_editor_text_changed)
        layout.addWidget(self.creative_editor)
        
        # 底部工具栏
        bottom_bar = QHBoxLayout()
        
        # 灵感引擎
        inspire_btn = QPushButton("💡 灵感")
        inspire_btn.clicked.connect(self._show_inspiration)
        bottom_bar.addWidget(inspire_btn)
        
        # 角色管理
        character_btn = QPushButton("👤 角色")
        character_btn.clicked.connect(self._show_character_manager)
        bottom_bar.addWidget(character_btn)
        
        # 时间线
        timeline_btn = QPushButton("⏰ 时间线")
        timeline_btn.clicked.connect(self._show_timeline)
        bottom_bar.addWidget(timeline_btn)
        
        bottom_bar.addStretch()
        
        # 进度
        self.creative_progress = QProgressBar()
        self.creative_progress.setMaximumWidth(200)
        self.creative_progress.setFormat("%p% (%v/%m)")
        bottom_bar.addWidget(self.creative_progress)
        
        # 字数
        self.creative_word_count = QLabel("0 / 50,000")
        bottom_bar.addWidget(self.creative_word_count)
        
        layout.addLayout(bottom_bar)
        
        return widget
    
    def _create_status_bar(self) -> QStatusBar:
        """创建状态栏"""
        status_bar = QStatusBar()
        
        # 模式状态
        self.mode_status_label = QLabel("✨ 创作模式")
        status_bar.addWidget(self.mode_status_label, 1)
        
        # AI状态
        self.ai_status_label = QLabel("🤖 AI: 就绪")
        status_bar.addWidget(self.ai_status_label)
        
        # 时间
        self.time_label = QLabel()
        self.update_time_label()
        status_bar.addPermanentWidget(self.time_label)
        
        return status_bar
    
    def _connect_signals(self):
        """连接信号"""
        # 更新字数统计
        if hasattr(self, 'consulting_editor'):
            self.consulting_editor.textChanged.connect(self._update_word_count)
        if hasattr(self, 'creative_editor'):
            self.creative_editor.textChanged.connect(self._update_creative_stats)
    
    def _start_timers(self):
        """启动定时器"""
        # 时间更新
        self.time_timer = QTimer(self)
        self.time_timer.timeout.connect(self.update_time_label)
        self.time_timer.start(1000)
    
    # ==================== 模式切换 ====================
    
    def _on_mode_switch(self, index: int):
        """模式切换"""
        mode = WritingMode.CONSULTING if index == 0 else WritingMode.CREATIVE
        
        if self.dual_engine:
            self.dual_engine.set_mode(mode)
        
        self._update_mode_ui(mode)
    
    def _update_mode_ui(self, mode: WritingMode):
        """更新模式UI"""
        if mode == WritingMode.CONSULTING:
            self.content_stack.setCurrentWidget(self.consulting_panel)
            self.mode_status_label.setText("📊 咨询模式")
        else:
            self.content_stack.setCurrentWidget(self.creative_panel)
            self.mode_status_label.setText("✨ 创作模式")
        
        self.mode_changed.emit(mode.value)
    
    @pyqtSlot(object, object)
    def _on_mode_changed(self, old_mode, new_mode):
        """模式改变回调"""
        self._update_mode_ui(new_mode)
        
        # 更新组合框
        index = 0 if new_mode == WritingMode.CONSULTING else 1
        self.mode_combo.blockSignals(True)
        self.mode_combo.setCurrentIndex(index)
        self.mode_combo.blockSignals(False)
    
    # ==================== 文档操作 ====================
    
    def _new_document(self):
        """新建文档"""
        current_editor = self._get_current_editor()
        
        if current_editor and current_editor.toPlainText():
            reply = QMessageBox.question(
                self, "确认",
                "确定要新建文档吗？当前内容将不会被保存。",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        # 清空编辑器
        if self.content_stack.currentWidget() == self.consulting_panel:
            self.title_edit.clear()
            self.consulting_editor.clear()
            self.outline_list.clear()
        else:
            self.creative_editor.clear()
        
        self.status_changed.emit("新建文档")
    
    def _save_document(self):
        """保存文档"""
        editor = self._get_current_editor()
        if not editor:
            return
        
        content = editor.toPlainText()
        if not content:
            self.status_changed.emit("没有内容可保存")
            return
        
        # 获取标题
        title = ""
        if self.content_stack.currentWidget() == self.consulting_panel:
            title = self.title_edit.text() or "未命名"
        else:
            title = f"创作_{len(content)//1000}k"
        
        # 选择保存位置
        path, _ = QFileDialog.getSaveFileName(
            self, "保存文档",
            str(Path.home() / f"{title}.md"),
            "Markdown (*.md);;文本 (*.txt);;所有文件 (*)"
        )
        
        if path:
            try:
                Path(path).write_text(content, encoding="utf-8")
                self.status_changed.emit(f"✅ 已保存到: {Path(path).name}")
            except Exception as e:
                self.status_changed.emit(f"❌ 保存失败: {e}")
    
    def _export_document(self):
        """导出文档"""
        editor = self._get_current_editor()
        if not editor or not editor.toPlainText():
            self.status_changed.emit("没有内容可导出")
            return
        
        # 选择格式
        formats = ["Markdown (*.md)", "LaTeX (*.tex)", "HTML (*.html)", "纯文本 (*.txt)"]
        path, selected_filter = QFileDialog.getSaveFileName(
            self, "导出文档",
            "document",
            ";;".join(formats)
        )
        
        if path:
            self.status_changed.emit("📤 正在导出...")
    
    def _get_current_editor(self) -> Optional[QTextEdit]:
        """获取当前编辑器"""
        if self.content_stack.currentWidget() == self.consulting_panel:
            return self.consulting_editor
        else:
            return self.creative_editor
    
    # ==================== AI功能 ====================
    
    def _polish_text(self):
        """润色文本"""
        editor = self._get_current_editor()
        if not editor:
            return
        
        cursor = editor.textCursor()
        selected = cursor.selectedText()
        
        if not selected:
            self.status_changed.emit("请先选择要润色的文本")
            return
        
        self.status_changed.emit("🎨 正在润色...")
        self.ai_status_label.setText("🤖 AI: 润色中...")
        
        # 模拟AI处理
        QTimer.singleShot(500, lambda: self._on_polish_complete("润色后的文本..."))
    
    def _on_polish_complete(self, result: str):
        """润色完成"""
        self.ai_status_label.setText("🤖 AI: 就绪")
        self.status_changed.emit("✅ 润色完成")
    
    def _expand_text(self):
        """扩展/续写文本"""
        editor = self._get_current_editor()
        if not editor:
            return
        
        cursor = editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        editor.setTextCursor(cursor)
        
        self.status_changed.emit("📝 正在续写...")
        self.ai_status_label.setText("🤖 AI: 续写中...")
    
    # ==================== 咨询模式功能 ====================
    
    def _generate_outline(self):
        """生成大纲"""
        title = self.title_edit.text()
        if not title:
            self.status_changed.emit("请先输入标题")
            return
        
        self.status_changed.emit("🔄 正在生成大纲...")
        
        # 清空现有大纲
        self.outline_list.clear()
        
        # 添加生成中状态
        self.outline_list.addItem("⏳ 正在生成...")
        
        # 模拟生成
        QTimer.singleShot(1000, lambda: self._on_outline_generated([
            "执行摘要",
            "市场概览",
            "竞争格局分析",
            "目标客户分析",
            "营销策略建议",
            "实施计划",
            "风险评估",
            "财务预测"
        ]))
    
    def _on_outline_generated(self, outline_items: list):
        """大纲生成完成"""
        self.outline_list.clear()
        
        for i, item in enumerate(outline_items, 1):
            list_item = QListWidgetItem(f"{i}. {item}")
            list_item.setData(Qt.ItemDataRole.UserRole, {"index": i, "title": item})
            self.outline_list.addItem(list_item)
        
        self.status_changed.emit(f"✅ 大纲已生成 ({len(outline_items)} 个章节)")
    
    def _on_outline_item_clicked(self, item: QListWidgetItem):
        """大纲项点击"""
        data = item.data(Qt.ItemDataRole.UserRole)
        if data:
            self.status_changed.emit(f"跳转到: {data['title']}")
    
    def _generate_framework(self):
        """生成分析框架"""
        framework = self.framework_combo.currentText()
        self.status_changed.emit(f"🧩 正在生成 {framework}...")
        
        # 模拟生成
        QTimer.singleShot(800, lambda: self._on_framework_generated(framework))
    
    def _on_framework_generated(self, framework: str):
        """框架生成完成"""
        # 在编辑器中插入框架
        framework_content = self._get_framework_template(framework)
        
        cursor = self.consulting_editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.consulting_editor.setTextCursor(cursor)
        
        self.consulting_editor.append(framework_content)
        self.status_changed.emit(f"✅ {framework} 已插入")
    
    def _get_framework_template(self, framework: str) -> str:
        """获取框架模板"""
        templates = {
            "SWOT分析": """
## SWOT分析

### 优势 (Strengths)
-

### 劣势 (Weaknesses)
-

### 机会 (Opportunities)
-

### 威胁 (Threats)
-
""",
            "波特五力": """
## 波特五力分析

### 1. 现有竞争者竞争强度

### 2. 新进入者威胁

### 3. 替代品威胁

### 4. 供应商议价能力

### 5. 买家议价能力
""",
            "麦肯锡7S": """
## 麦肯锡7S分析

| 要素 | 内容 |
|------|------|
| 战略 (Strategy) | |
| 结构 (Structure) | |
| 系统 (Systems) | |
| 共享价值观 | |
| 风格 (Style) | |
| 员工 (Staff) | |
| 技能 (Skills) | |
"""
        }
        return templates.get(framework, "")
    
    def _add_reference(self):
        """添加参考资料"""
        path, _ = QFileDialog.getOpenFileName(
            self, "选择参考文件",
            str(Path.home()),
            "文档 (*.pdf *.docx *.txt *.md);;所有文件 (*)"
        )
        
        if path:
            item = QListWidgetItem(f"📄 {Path(path).name}")
            self.ref_list.addItem(item)
            self.status_changed.emit(f"已添加: {Path(path).name}")
    
    def _import_data(self):
        """导入数据"""
        path, _ = QFileDialog.getOpenFileName(
            self, "导入数据",
            str(Path.home()),
            "数据 (*.csv *.xlsx *.xls);;所有文件 (*)"
        )
        
        if path:
            self.status_changed.emit(f"📥 正在导入: {Path(path).name}")
    
    def _generate_chart(self):
        """生成图表"""
        self.status_changed.emit("📈 正在生成图表...")
    
    def _check_consistency(self):
        """逻辑一致性检查"""
        self.status_changed.emit("🔍 正在进行逻辑检查...")
    
    def _check_format(self):
        """格式检查"""
        self.status_changed.emit("📋 正在进行格式检查...")
    
    def _generate_ppt_outline(self):
        """生成PPT大纲"""
        self.status_changed.emit("📑 正在生成PPT大纲...")
    
    # ==================== 创作模式功能 ====================
    
    def _show_inspiration(self):
        """显示灵感面板"""
        dialog = InspirationDialog(self)
        if dialog.exec():
            inspiration = dialog.get_inspiration()
            if inspiration:
                self.creative_editor.append(f"\n💡 **灵感**: {inspiration}\n")
    
    def _show_character_manager(self):
        """显示角色管理器"""
        dialog = CharacterManagerDialog(self)
        dialog.exec()
    
    def _show_timeline(self):
        """显示时间线"""
        dialog = TimelineDialog(self)
        dialog.exec()
    
    # ==================== 编辑器事件 ====================
    
    def _on_editor_text_changed(self):
        """编辑器文本变化"""
        self.content_changed.emit("内容已更新")
    
    def _update_word_count(self):
        """更新字数统计"""
        text = self.consulting_editor.toPlainText()
        word_count = len(text)
        char_count = len(text.replace(" ", "").replace("\n", ""))
        
        self.word_count_label.setText(f"字数: {word_count}")
        self.char_count_label.setText(f"字符: {char_count}")
        
        # 更新上下文感知
        if self.context_aware:
            self.context_aware.update_word_count(word_count)
    
    def _update_creative_stats(self):
        """更新创作统计"""
        text = self.creative_editor.toPlainText()
        word_count = len(text)
        target = self.word_target_spin.value()
        
        self.creative_word_count.setText(f"{word_count:,} / {target:,}")
        self.creative_progress.setMaximum(target)
        self.creative_progress.setValue(word_count)
        
        # 更新上下文感知
        if self.context_aware:
            self.context_aware.update_word_count(word_count)
    
    def update_time_label(self):
        """更新时间标签"""
        from datetime import datetime
        self.time_label.setText(datetime.now().strftime("%H:%M:%S"))
    
    # ==================== 设置 ====================
    
    def _show_settings(self):
        """显示设置对话框"""
        dialog = WritingSettingsDialog(self)
        dialog.exec()
    
    def _toggle_focus_mode(self):
        """切换专注模式"""
        self.status_changed.emit("🎯 专注模式 (开发中)")
    
    # ==================== 公共方法 ====================
    
    def set_content(self, content: str):
        """设置内容"""
        editor = self._get_current_editor()
        if editor:
            editor.setPlainText(content)
    
    def get_content(self) -> str:
        """获取内容"""
        editor = self._get_current_editor()
        return editor.toPlainText() if editor else ""
    
    def set_agent(self, agent):
        """设置Agent"""
        self.agent = agent
        if self.dual_engine:
            self.dual_engine.agent = agent


# ==================== 对话框 ====================

class InspirationDialog(QDialog):
    """灵感对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("💡 灵感引擎")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        
        layout = QVBoxLayout(self)
        
        # 类型选择
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("灵感类型:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems([
            "随机词组合", "意象描写", "情节冲突",
            "角色设定", "场景氛围"
        ])
        type_layout.addWidget(self.type_combo)
        type_layout.addStretch()
        layout.addLayout(type_layout)
        
        # 基调选择
        tone_layout = QHBoxLayout()
        tone_layout.addWidget(QLabel("情感基调:"))
        self.tone_combo = QComboBox()
        self.tone_combo.addItems([
            "紧张", "平静", "忧郁", "欢快",
            "神秘", "浪漫", "黑暗"
        ])
        tone_layout.addWidget(self.tone_combo)
        tone_layout.addStretch()
        layout.addLayout(tone_layout)
        
        # 生成按钮
        generate_btn = QPushButton("🎲 生成灵感")
        generate_btn.clicked.connect(self._generate)
        layout.addWidget(generate_btn)
        
        # 结果区域
        self.result_browser = QTextEdit()
        self.result_browser.setReadOnly(True)
        layout.addWidget(self.result_browser)
        
        # 按钮
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def _generate(self):
        """生成灵感"""
        inspiration_type = self.type_combo.currentText()
        
        # 简单的灵感生成
        results = {
            "随机词组合": "微光 + 寂静 + 回忆 = 黎明前的那一刻，寂静的房间里，微光透过窗帘，唤起了遥远的回忆。",
            "意象描写": "在忧郁的基调下，可以描绘：暮色降临，空气中弥漫着某种难以名状的气息...",
            "情节冲突": "两个角色被迫在忠诚与真相之间做出选择，他们的对话将揭示一个埋藏多年的秘密。",
            "角色设定": "一个表面冷漠但内心复杂的角色，他的过去与现在的选择形成了鲜明对比。",
            "场景氛围": "废弃的图书馆里，尘埃在阳光中飞舞，书架间的阴影似乎藏着无数故事。"
        }
        
        self.result_browser.setPlainText(results.get(inspiration_type, ""))
    
    def get_inspiration(self) -> str:
        """获取灵感"""
        return self.result_browser.toPlainText()


class CharacterManagerDialog(QDialog):
    """角色管理器对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("👤 角色管理")
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)
        
        layout = QHBoxLayout(self)
        
        # 角色列表
        left_panel = QVBoxLayout()
        left_panel.addWidget(QLabel("角色列表"))
        
        self.character_list = QListWidget()
        left_panel.addWidget(self.character_list)
        
        btn_layout = QHBoxLayout()
        add_btn = QPushButton("+ 添加")
        add_btn.clicked.connect(self._add_character)
        del_btn = QPushButton("- 删除")
        del_btn.clicked.connect(self._delete_character)
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(del_btn)
        left_panel.addLayout(btn_layout)
        
        layout.addLayout(left_panel, 0)
        
        # 角色详情
        right_panel = QVBoxLayout()
        right_panel.addWidget(QLabel("角色详情"))
        
        form_layout = QFormLayout()
        self.name_edit = QLineEdit()
        self.age_edit = QSpinBox()
        self.age_edit.setRange(0, 150)
        self.traits_edit = QLineEdit()
        self.motivation_edit = QTextEdit()
        self.motivation_edit.setMaximumHeight(80)
        
        form_layout.addRow("姓名:", self.name_edit)
        form_layout.addRow("年龄:", self.age_edit)
        form_layout.addRow("性格特点:", self.traits_edit)
        form_layout.addRow("动机:", self.motivation_edit)
        
        right_panel.addLayout(form_layout)
        right_panel.addStretch()
        
        # 关系图
        relation_group = QGroupBox("人物关系")
        relation_layout = QVBoxLayout(relation_group)
        self.relation_browser = QTextBrowser()
        relation_layout.addWidget(self.relation_browser)
        right_panel.addWidget(relation_group)
        
        layout.addLayout(right_panel, 1)
        
        # 关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)
    
    def _add_character(self):
        """添加角色"""
        self.character_list.addItem("新角色")
    
    def _delete_character(self):
        """删除角色"""
        current = self.character_list.currentItem()
        if current:
            row = self.character_list.row(current)
            self.character_list.takeItem(row)


class TimelineDialog(QDialog):
    """时间线对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⏰ 故事时间线")
        self.setMinimumWidth(700)
        self.setMinimumHeight(500)
        
        layout = QVBoxLayout(self)
        
        # 时间线视图
        self.timeline_browser = QTextBrowser()
        layout.addWidget(self.timeline_browser)
        
        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.clicked.connect(self._refresh)
        btn_layout.addWidget(refresh_btn)
        
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.close)
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(btn_layout)
        
        self._refresh()
    
    def _refresh(self):
        """刷新时间线"""
        # 示例时间线
        timeline_html = """
        <h2>故事时间线</h2>
        <table border="1" cellpadding="8" style="border-collapse: collapse; width: 100%;">
        <tr style="background: #2d2d2d;"><th>章节</th><th>场景</th><th>内容预览</th><th>涉及角色</th></tr>
        <tr><td>第1章</td><td>场景1</td><td>主角登场...</td><td>张三, 李四</td></tr>
        <tr style="background: #252525;"><td>第1章</td><td>场景2</td><td>冲突开始...</td><td>张三, 王五</td></tr>
        <tr><td>第2章</td><td>场景1</td><td>转折点...</td><td>张三</td></tr>
        </table>
        """
        self.timeline_browser.setHtml(timeline_html)


class WritingSettingsDialog(QDialog):
    """写作设置对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙️ 写作设置")
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout(self)
        
        # 界面设置
        ui_group = QGroupBox("界面")
        ui_layout = QFormLayout(ui_group)
        
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(10, 24)
        self.font_size_spin.setValue(14)
        ui_layout.addRow("字体大小:", self.font_size_spin)
        
        self.line_spacing_slider = QSlider(Qt.Orientation.Horizontal)
        self.line_spacing_slider.setRange(100, 250)
        self.line_spacing_slider.setValue(180)
        ui_layout.addRow("行间距:", self.line_spacing_slider)
        
        layout.addWidget(ui_group)
        
        # AI设置
        ai_group = QGroupBox("AI协作")
        ai_layout = QFormLayout(ai_group)
        
        self.ai_proactivity_slider = QSlider(Qt.Orientation.Horizontal)
        self.ai_proactivity_slider.setRange(0, 100)
        self.ai_proactivity_slider.setValue(50)
        ai_layout.addRow("AI主动程度:", self.ai_proactivity_slider)
        
        self.auto_complete_check = QCheckBox("启用自动补全")
        self.auto_complete_check.setChecked(True)
        ai_layout.addRow("自动补全:", self.auto_complete_check)
        
        layout.addWidget(ai_group)
        
        # 按钮
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)


# ==================== 入口函数 ====================

def create_smart_writing_panel(parent=None, hermes_agent=None) -> SmartWritingPanel:
    """创建智能写作面板"""
    return SmartWritingPanel(parent, hermes_agent)
