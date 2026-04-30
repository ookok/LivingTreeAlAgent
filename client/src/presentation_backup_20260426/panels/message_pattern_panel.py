"""
消息模式与智能提示词系统 UI 面板
PyQt6 Integration Panel - 7 Tabs
"""

import sys
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
import threading

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QTabWidget, QLabel, QPushButton, QTextEdit, QLineEdit,
    QListWidget, QListWidgetItem, QComboBox, QCheckBox,
    QSpinBox, QDoubleSpinBox, QSlider, QGroupBox, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QScrollArea,
    QProgressBar, QDialog, QDialogButtonBox, QFormLayout,
    QColorDialog, QFontDialog, QSplitter, QStackedWidget,
    QTreeWidget, QTreeWidgetItem, QMenu, QToolButton, QStatusBar,
    QMessageBox, QInputDialog, QFileDialog, QRadioButton, QButtonGroup
)
from PyQt6.QtCore import (
    Qt, QSize, QTimer, QDateTime, pyqtSignal, pyqtSlot,
    QAbstractTableModel, QSortFilterProxyModel
)
from PyQt6.QtGui import (
    QFont, QColor, QPalette, QAction, QIcon, QTextCursor,
    QTextCharFormat, QSyntaxHighlighter, QTextDocument, QPainter, QPen
)

try:
    from PyQt6.QtCharts import QChartView, QChart, QPieSeries, QBarSeries, QBarSet, QLineSeries, QValueAxis, QCategoryAxis
    HAS_CHARTS = True
except ImportError:
    HAS_CHARTS = False
    QChartView = QChart = QPieSeries = QBarSeries = QBarSet = QLineSeries = QValueAxis = QCategoryAxis = None

try:
    from ..core.message_patterns import (
        MessagePattern, PatternManager, get_pattern_manager,
        VariableResolver, VariableDefinition, get_variable_resolver,
        PatternMatcher, MatchResult, get_pattern_matcher,
        PromptGenerator, GeneratedPrompt, get_prompt_generator,
        EffectivenessEvaluator, EvaluationMetrics, get_effectiveness_evaluator,
        ContextBuilder, ResolverContext,
        PatternCategory, TriggerType, ThinkingStyle, ThinkingDepth,
        OutputFormat, BuiltInPatterns, SystemVariables
    )
except ImportError:
    # 相对导入失败时的备用导入
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from .business.message_patterns import (
        MessagePattern, PatternManager, get_pattern_manager,
        VariableResolver, VariableDefinition, get_variable_resolver,
        PatternMatcher, MatchResult, get_pattern_matcher,
        PromptGenerator, GeneratedPrompt, get_prompt_generator,
        EffectivenessEvaluator, EvaluationMetrics, get_effectiveness_evaluator,
        ContextBuilder, ResolverContext,
        PatternCategory, TriggerType, ThinkingStyle, ThinkingDepth,
        OutputFormat, BuiltInPatterns, SystemVariables
    )


# ============ 样式表 ============

STYLESHEET = """
QWidget {
    font-family: "Microsoft YaHei", "Segoe UI", Arial, sans-serif;
    font-size: 13px;
}

QLabel {
    color: #333;
}

QLabel#title {
    font-size: 18px;
    font-weight: bold;
    color: #1a73e8;
}

QLabel#subtitle {
    font-size: 14px;
    color: #666;
}

QPushButton {
    background-color: #1a73e8;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 8px 16px;
    min-width: 80px;
}

QPushButton:hover {
    background-color: #1557b0;
}

QPushButton:pressed {
    background-color: #0d47a1;
}

QPushButton#secondary {
    background-color: #f1f3f4;
    color: #333;
    border: 1px solid #dadce0;
}

QPushButton#secondary:hover {
    background-color: #e8eaed;
}

QPushButton#danger {
    background-color: #ea4335;
}

QPushButton#danger:hover {
    background-color: #d33426;
}

QPushButton#success {
    background-color: #34a853;
}

QPushButton#success:hover {
    background-color: #2d8f4e;
}

QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: white;
    border: 1px solid #dadce0;
    border-radius: 4px;
    padding: 6px 10px;
}

QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
    border: 2px solid #1a73e8;
}

QListWidget {
    border: 1px solid #dadce0;
    border-radius: 4px;
    background-color: white;
}

QListWidget::item {
    padding: 8px;
    border-bottom: 1px solid #f1f3f4;
}

QListWidget::item:selected {
    background-color: #e8f0fe;
    color: #1a73e8;
}

QListWidget::item:hover {
    background-color: #f8f9fa;
}

QTabWidget::pane {
    border: 1px solid #dadce0;
    border-radius: 4px;
    background-color: white;
}

QTabBar::tab {
    background-color: #f1f3f4;
    padding: 10px 20px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}

QTabBar::tab:selected {
    background-color: white;
    border-bottom: 2px solid #1a73e8;
    color: #1a73e8;
}

QTabBar::tab:hover {
    background-color: #e8eaed;
}

QGroupBox {
    border: 1px solid #dadce0;
    border-radius: 4px;
    margin-top: 10px;
    padding-top: 10px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 5px;
    color: #1a73e8;
}

QTableWidget {
    border: 1px solid #dadce0;
    border-radius: 4px;
    background-color: white;
}

QTableWidget::item {
    padding: 8px;
}

QTableWidget::item:selected {
    background-color: #e8f0fe;
}

QHeaderView::section {
    background-color: #f1f3f4;
    padding: 8px;
    border: none;
    border-bottom: 2px solid #dadce0;
    font-weight: bold;
}

QProgressBar {
    border: 1px solid #dadce0;
    border-radius: 4px;
    text-align: center;
    background-color: #f1f3f4;
}

QProgressBar::chunk {
    background-color: #1a73e8;
    border-radius: 3px;
}

QSlider::groove:horizontal {
    border: 1px solid #dadce0;
    height: 4px;
    background-color: #f1f3f4;
    border-radius: 2px;
}

QSlider::handle:horizontal {
    background-color: #1a73e8;
    width: 14px;
    margin: -5px 0;
    border-radius: 7px;
}

QMenu {
    background-color: white;
    border: 1px solid #dadce0;
    border-radius: 4px;
}

QMenu::item {
    padding: 8px 20px;
}

QMenu::item:selected {
    background-color: #e8f0fe;
}

QScrollBar:vertical {
    background-color: #f1f3f4;
    width: 10px;
    border-radius: 5px;
}

QScrollBar::handle:vertical {
    background-color: #dadce0;
    border-radius: 5px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background-color: #1a73e8;
}
"""


# ============ 模式编辑器对话框 ============

class PatternEditorDialog(QDialog):
    """模式编辑器对话框"""

    def __init__(self, pattern: MessagePattern = None, parent=None):
        super().__init__(parent)
        self.pattern = pattern or MessagePattern()
        self.is_new = pattern is None
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("模式编辑器" if self.is_new else "编辑模式")
        self.setMinimumSize(900, 700)

        layout = QVBoxLayout(self)

        # 创建标签页
        tabs = QTabWidget()

        # 基本信息页
        tabs.addTab(self._create_basic_tab(), "基本信息")
        # 触发条件页
        tabs.addTab(self._create_trigger_tab(), "触发条件")
        # 模板编辑页
        tabs.addTab(self._create_template_tab(), "模板编辑")
        # 变量管理页
        tabs.addTab(self._create_variables_tab(), "变量管理")
        # 思考配置页
        tabs.addTab(self._create_thinking_tab(), "思考配置")
        # 输出配置页
        tabs.addTab(self._create_output_tab(), "输出配置")

        layout.addWidget(tabs)

        # 按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.setObjectName("secondary")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self.save)
        button_layout.addWidget(save_btn)

        if self.is_new:
            create_btn = QPushButton("创建")
            create_btn.setObjectName("success")
            create_btn.clicked.connect(self.create_pattern)
            button_layout.addWidget(create_btn)

        layout.addLayout(button_layout)

    def _create_basic_tab(self) -> QWidget:
        """基本信息页"""
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # 名称
        self.name_edit = QLineEdit(self.pattern.name)
        layout.addRow("名称:", self.name_edit)

        # 描述
        self.desc_edit = QTextEdit()
        self.desc_edit.setPlainText(self.pattern.description)
        self.desc_edit.setMaximumHeight(80)
        layout.addRow("描述:", self.desc_edit)

        # 分类
        self.category_combo = QComboBox()
        for cat in PatternCategory:
            self.category_combo.addItem(cat.value, cat)
        layout.addRow("分类:", self.category_combo)

        # 图标
        icon_layout = QHBoxLayout()
        self.icon_edit = QLineEdit(self.pattern.icon)
        self.icon_btn = QPushButton("选择图标")
        self.icon_btn.clicked.connect(self.select_icon)
        icon_layout.addWidget(self.icon_edit)
        icon_layout.addWidget(self.icon_btn)
        layout.addRow("图标:", icon_layout)

        # 标签
        self.tags_edit = QLineEdit(", ".join(self.pattern.tags))
        layout.addRow("标签:", self.tags_edit)

        return widget

    def _create_trigger_tab(self) -> QWidget:
        """触发条件页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 触发类型
        type_group = QGroupBox("触发类型")
        type_layout = QVBoxLayout()

        self.trigger_group = QButtonGroup()
        for trigger_type in TriggerType:
            radio = QRadioButton(trigger_type.value)
            radio.setChecked(self.pattern.trigger.type == trigger_type)
            self.trigger_group.addButton(radio, trigger_type)
            type_layout.addWidget(radio)

        type_group.setLayout(type_layout)
        layout.addWidget(type_group)

        # 关键词
        kw_group = QGroupBox("关键词 (用逗号分隔)")
        kw_layout = QVBoxLayout()
        self.keywords_edit = QTextEdit()
        self.keywords_edit.setPlainText(", ".join(self.pattern.trigger.keywords))
        self.keywords_edit.setMaximumHeight(100)
        kw_layout.addWidget(self.keywords_edit)
        kw_group.setLayout(kw_layout)
        layout.addWidget(kw_group)

        # 置信度
        conf_layout = QHBoxLayout()
        conf_layout.addWidget(QLabel("触发置信度:"))
        self.confidence_slider = QSlider(Qt.Orientation.Horizontal)
        self.confidence_slider.setRange(0, 100)
        self.confidence_slider.setValue(int(self.pattern.trigger.confidence_threshold * 100))
        self.confidence_value = QLabel(f"{int(self.pattern.trigger.confidence_threshold * 100)}%")
        self.confidence_slider.valueChanged.connect(
            lambda v: self.confidence_value.setText(f"{v}%")
        )
        conf_layout.addWidget(self.confidence_slider)
        conf_layout.addWidget(self.confidence_value)
        layout.addLayout(conf_layout)

        layout.addStretch()
        return widget

    def _create_template_tab(self) -> QWidget:
        """模板编辑页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 模板内容
        template_group = QGroupBox("模板内容")
        template_layout = QVBoxLayout()

        self.template_edit = QTextEdit()
        self.template_edit.setPlainText(self.pattern.template.content)
        self.template_edit.setPlaceholderText("在此输入模板内容，使用 {变量名} 占位...")
        template_layout.addWidget(self.template_edit)

        template_group.setLayout(template_layout)
        layout.addWidget(template_group)

        # 变量提示
        hint = QLabel("💡 使用 {变量名} 插入变量，例如: {user_input}, {context}")
        hint.setStyleSheet("color: #666; padding: 5px;")
        layout.addWidget(hint)

        return widget

    def _create_variables_tab(self) -> QWidget:
        """变量管理页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 系统变量
        sys_group = QGroupBox("系统预定义变量")
        sys_layout = QVBoxLayout()

        sys_vars = SystemVariables.get_all_system_variables()
        for name, var in sys_vars.items():
            var_label = QLabel(f"  {var.display_name} ({var.name})")
            var_label.setStyleSheet("color: #666; font-size: 12px;")
            sys_layout.addWidget(var_label)

        sys_group.setLayout(sys_layout)
        layout.addWidget(sys_group)

        # 自定义变量提示
        custom_hint = QLabel("💡 在模板编辑页使用 {变量名} 格式即可自动创建变量定义")
        custom_hint.setStyleSheet("color: #666; padding: 5px;")
        layout.addWidget(custom_hint)

        layout.addStretch()
        return widget

    def _create_thinking_tab(self) -> QWidget:
        """思考配置页"""
        widget = QWidget()
        layout = QFormLayout(widget)

        # 启用思考过程
        self.thinking_enabled = QCheckBox("启用思考过程")
        self.thinking_enabled.setChecked(self.pattern.enhancement.thinking.enabled)
        layout.addRow("", self.thinking_enabled)

        # 思考风格
        self.thinking_style = QComboBox()
        for style in ThinkingStyle:
            self.thinking_style.addItem(style.value, style)
        layout.addRow("思考风格:", self.thinking_style)

        # 思考深度
        self.thinking_depth = QComboBox()
        for depth in ThinkingDepth:
            self.thinking_depth.addItem(depth.value, depth)
        layout.addRow("思考深度:", self.thinking_depth)

        # 显示选项
        self.show_steps = QCheckBox("显示推理步骤")
        self.show_steps.setChecked(self.pattern.enhancement.thinking.show_steps)
        layout.addRow("", self.show_steps)

        self.show_assumptions = QCheckBox("显示假设条件")
        self.show_assumptions.setChecked(self.pattern.enhancement.thinking.show_assumptions)
        layout.addRow("", self.show_assumptions)

        self.show_alternatives = QCheckBox("显示备选方案")
        self.show_alternatives.setChecked(self.pattern.enhancement.thinking.show_alternatives)
        layout.addRow("", self.show_alternatives)

        return widget

    def _create_output_tab(self) -> QWidget:
        """输出配置页"""
        widget = QWidget()
        layout = QFormLayout(widget)

        # 输出格式
        self.output_format = QComboBox()
        for fmt in OutputFormat:
            self.output_format.addItem(fmt.value, fmt)
        layout.addRow("输出格式:", self.output_format)

        # 长度限制
        self.length_limit = QSpinBox()
        self.length_limit.setRange(100, 50000)
        self.length_limit.setValue(self.pattern.output.length_limit)
        self.length_limit.setSuffix(" 字符")
        layout.addRow("长度限制:", self.length_limit)

        # 显示选项
        self.show_confidence = QCheckBox("显示置信度")
        self.show_confidence.setChecked(self.pattern.output.show_confidence)
        layout.addRow("", self.show_confidence)

        self.show_reasoning = QCheckBox("显示推理过程")
        self.show_reasoning.setChecked(self.pattern.output.show_reasoning)
        layout.addRow("", self.show_reasoning)

        return widget

    def select_icon(self):
        """选择图标"""
        icons = ["📝", "🔍", "💡", "🎯", "📊", "📚", "💻", "🎨", "✍️", "🔧", "⚖️", "🚀", "🎯", "💡", "🔮"]
        icon, ok = QInputDialog.getItem(self, "选择图标", "选择模式图标:", icons)
        if ok:
            self.icon_edit.setText(icon)

    def update_pattern_from_ui(self):
        """从UI更新模式"""
        self.pattern.name = self.name_edit.text()
        self.pattern.description = self.desc_edit.toPlainText()
        self.pattern.category = self.category_combo.currentData()
        self.pattern.icon = self.icon_edit.text()
        self.pattern.tags = [t.strip() for t in self.tags_edit.text().split(",") if t.strip()]

        # 触发配置
        selected = self.trigger_group.checkedButton()
        if selected:
            self.pattern.trigger.type = self.trigger_group.id(selected)
        self.pattern.trigger.keywords = [k.strip() for k in self.keywords_edit.toPlainText().split(",") if k.strip()]
        self.pattern.trigger.confidence_threshold = self.confidence_slider.value() / 100.0

        # 模板配置
        self.pattern.template.content = self.template_edit.toPlainText()

        # 思考配置
        self.pattern.enhancement.thinking.enabled = self.thinking_enabled.isChecked()
        self.pattern.enhancement.thinking.style = self.thinking_style.currentData()
        self.pattern.enhancement.thinking.depth = self.thinking_depth.currentData()
        self.pattern.enhancement.thinking.show_steps = self.show_steps.isChecked()
        self.pattern.enhancement.thinking.show_assumptions = self.show_assumptions.isChecked()
        self.pattern.enhancement.thinking.show_alternatives = self.show_alternatives.isChecked()

        # 输出配置
        self.pattern.output.format = self.output_format.currentData()
        self.pattern.output.length_limit = self.length_limit.value()
        self.pattern.output.show_confidence = self.show_confidence.isChecked()
        self.pattern.output.show_reasoning = self.show_reasoning.isChecked()

    def save(self):
        """保存"""
        self.update_pattern_from_ui()
        self.accept()

    def create_pattern(self):
        """创建"""
        self.update_pattern_from_ui()
        self.accept()


# ============ 预览对话框 ============

class PreviewDialog(QDialog):
    """预览对话框"""

    def __init__(self, pattern: MessagePattern, generator: PromptGenerator, parent=None):
        super().__init__(parent)
        self.pattern = pattern
        self.generator = generator
        self.init_ui()
        self.load_preview()

    def init_ui(self):
        self.setWindowTitle(f"预览: {self.pattern.name}")
        self.setMinimumSize(800, 600)

        layout = QVBoxLayout(self)

        # 模式信息
        info_label = QLabel(f"{self.pattern.icon} {self.pattern.name}")
        info_label.setObjectName("title")
        layout.addWidget(info_label)

        # 输入测试
        input_group = QGroupBox("测试输入")
        input_layout = QVBoxLayout()
        self.input_edit = QTextEdit()
        self.input_edit.setPlaceholderText("输入测试内容...")
        self.input_edit.textChanged.connect(self.update_preview)
        input_layout.addWidget(self.input_edit)
        input_group.setLayout(input_layout)
        layout.addWidget(input_group)

        # 预览结果
        preview_group = QGroupBox("生成的提示词")
        preview_layout = QVBoxLayout()

        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setStyleSheet("background-color: #f8f9fa;")
        preview_layout.addWidget(self.preview_text)
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)

        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        close_btn = QPushButton("关闭")
        close_btn.setObjectName("secondary")
        close_btn.clicked.connect(self.close)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def load_preview(self):
        """加载预览"""
        context = ResolverContext(
            user_input=self.input_edit.toPlainText() or "示例输入",
            user_profile={"name": "测试用户"}
        )
        prompt = self.generator.generate(self.pattern, context)
        self.preview_text.setPlainText(prompt.content)

    def update_preview(self):
        """更新预览"""
        self.load_preview()


# ============ 主面板 ============

class MessagePatternPanel(QWidget):
    """消息模式面板 - 主界面"""

    # 信号
    pattern_selected = pyqtSignal(str)  # pattern_id
    pattern_applied = pyqtSignal(str)  # pattern_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self.manager = get_pattern_manager()
        self.generator = get_prompt_generator()
        self.matcher = get_pattern_matcher()
        self.evaluator = get_effectiveness_evaluator()
        self.resolver = get_variable_resolver()

        self.current_pattern = None
        self.init_ui()
        self.load_patterns()

    def init_ui(self):
        """初始化UI"""
        self.setStyleSheet(STYLESHEET)

        main_layout = QVBoxLayout(self)

        # 标题栏
        header = QHBoxLayout()
        title = QLabel("📝 消息模式与智能提示词系统")
        title.setObjectName("title")
        header.addWidget(title)
        header.addStretch()

        # 操作按钮
        self.new_btn = QPushButton("✏️ 新建")
        self.new_btn.clicked.connect(self.create_pattern)
        header.addWidget(self.new_btn)

        self.import_btn = QPushButton("📥 导入")
        self.import_btn.setObjectName("secondary")
        self.import_btn.clicked.connect(self.import_pattern)
        header.addWidget(self.import_btn)

        self.export_btn = QPushButton("📤 导出")
        self.export_btn.setObjectName("secondary")
        self.export_btn.clicked.connect(self.export_pattern)
        header.addWidget(self.export_btn)

        main_layout.addLayout(header)

        # 主内容区
        content = QHBoxLayout()

        # 左侧：模式列表
        left_panel = QFrame()
        left_panel.setFrameShape(QFrame.Shape.StyledPanel)
        left_layout = QVBoxLayout(left_panel)

        # 搜索框
        search_layout = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索模式...")
        self.search_edit.textChanged.connect(self.filter_patterns)
        search_layout.addWidget(self.search_edit)
        left_layout.addLayout(search_layout)

        # 分类筛选
        filter_layout = QHBoxLayout()
        self.filter_combo = QComboBox()
        self.filter_combo.addItem("全部", None)
        for cat in PatternCategory:
            self.filter_combo.addItem(cat.value, cat)
        self.filter_combo.currentIndexChanged.connect(self.filter_patterns)
        filter_layout.addWidget(QLabel("分类:"))
        filter_layout.addWidget(self.filter_combo)
        left_layout.addLayout(filter_layout)

        # 模式列表
        self.pattern_list = QListWidget()
        self.pattern_list.itemClicked.connect(self.select_pattern)
        self.pattern_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.pattern_list.customContextMenuRequested.connect(self.show_context_menu)
        left_layout.addWidget(self.pattern_list)

        # 列表统计
        self.stats_label = QLabel("共 0 个模式")
        self.stats_label.setStyleSheet("color: #666; font-size: 12px;")
        left_layout.addWidget(self.stats_label)

        content.addWidget(left_panel, 1)

        # 右侧：详情区
        right_panel = QFrame()
        right_panel.setFrameShape(QFrame.Shape.StyledPanel)
        right_layout = QVBoxLayout(right_panel)

        # 详情标签页
        self.detail_tabs = QTabWidget()

        # 概览页
        self.detail_tabs.addTab(self._create_overview_tab(), "📊 概览")
        # 编辑页
        self.detail_tabs.addTab(self._create_detail_tab(), "✏️ 编辑")
        # 预览页
        self.detail_tabs.addTab(self._create_preview_tab(), "👁️ 预览")
        # 统计页
        self.detail_tabs.addTab(self._create_stats_tab(), "📈 统计")
        # 测试页
        self.detail_tabs.addTab(self._create_test_tab(), "🧪 测试")

        right_layout.addWidget(self.detail_tabs)

        content.addWidget(right_panel, 2)

        main_layout.addLayout(content)

        # 状态栏
        self.status_bar = QStatusBar()
        main_layout.addWidget(self.status_bar)

    def _create_overview_tab(self) -> QWidget:
        """概览页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 模式信息
        self.overview_info = QTextEdit()
        self.overview_info.setReadOnly(True)
        self.overview_info.setMaximumHeight(200)
        layout.addWidget(self.overview_info)

        # 触发条件
        trigger_group = QGroupBox("触发条件")
        trigger_layout = QVBoxLayout()
        self.trigger_info = QLabel("无")
        trigger_layout.addWidget(self.trigger_info)
        trigger_group.setLayout(trigger_layout)
        layout.addWidget(trigger_group)

        # 模板预览
        template_group = QGroupBox("模板预览")
        template_layout = QVBoxLayout()
        self.template_preview = QTextEdit()
        self.template_preview.setReadOnly(True)
        self.template_preview.setStyleSheet("background-color: #f8f9fa; font-family: monospace;")
        template_layout.addWidget(self.template_preview)
        template_group.setLayout(template_layout)
        layout.addWidget(template_group)

        layout.addStretch()
        return widget

    def _create_detail_tab(self) -> QWidget:
        """编辑页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        info = QLabel("选择左侧列表中的模式进行编辑")
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info.setStyleSheet("color: #666;")
        layout.addWidget(info)

        self.detail_edit_btn = QPushButton("编辑模式")
        self.detail_edit_btn.setEnabled(False)
        self.detail_edit_btn.clicked.connect(self.edit_pattern)
        layout.addWidget(self.detail_edit_btn)

        layout.addStretch()
        return widget

    def _create_preview_tab(self) -> QWidget:
        """预览页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 预览按钮
        btn_layout = QHBoxLayout()
        self.preview_btn = QPushButton("🔄 刷新预览")
        self.preview_btn.setObjectName("secondary")
        self.preview_btn.clicked.connect(self.refresh_preview)
        self.preview_btn.setEnabled(False)
        btn_layout.addWidget(self.preview_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # 预览内容
        self.preview_content = QTextEdit()
        self.preview_content.setReadOnly(True)
        self.preview_content.setStyleSheet("background-color: #f8f9fa;")
        layout.addWidget(self.preview_content)

        return widget

    def _create_stats_tab(self) -> QWidget:
        """统计页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 统计卡片
        stats_layout = QGridLayout()

        self.stat_usage = self._create_stat_card("使用次数", "0")
        self.stat_success = self._create_stat_card("成功率", "0%")
        self.stat_rating = self._create_stat_card("用户评分", "0.0")
        self.stat_quality = self._create_stat_card("质量评分", "0.0")

        stats_layout.addWidget(self.stat_usage, 0, 0)
        stats_layout.addWidget(self.stat_success, 0, 1)
        stats_layout.addWidget(self.stat_rating, 0, 2)
        stats_layout.addWidget(self.stat_quality, 0, 3)

        layout.addLayout(stats_layout)

        # 历史记录
        history_group = QGroupBox("最近使用记录")
        history_layout = QVBoxLayout()
        self.history_list = QListWidget()
        history_layout.addWidget(self.history_list)
        history_group.setLayout(history_layout)
        layout.addWidget(history_group)

        return widget

    def _create_stat_card(self, title: str, value: str) -> QWidget:
        """创建统计卡片"""
        card = QFrame()
        card.setFrameShape(QFrame.Shape.StyledPanel)
        card.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border-radius: 8px;
                padding: 15px;
            }
        """)
        layout = QVBoxLayout(card)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        value_label = QLabel(value)
        value_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #1a73e8;")
        layout.addWidget(value_label)

        title_label = QLabel(title)
        title_label.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(title_label)

        return card

    def _create_test_tab(self) -> QWidget:
        """测试页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 测试输入
        input_group = QGroupBox("测试输入")
        input_layout = QVBoxLayout()
        self.test_input = QTextEdit()
        self.test_input.setPlaceholderText("在此输入测试内容...")
        input_layout.addWidget(self.test_input)
        input_group.setLayout(input_layout)
        layout.addWidget(input_group)

        # 生成按钮
        btn_layout = QHBoxLayout()
        self.generate_btn = QPushButton("🚀 生成提示词")
        self.generate_btn.setEnabled(False)
        self.generate_btn.clicked.connect(self.generate_prompt)
        btn_layout.addWidget(self.generate_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # 输出
        output_group = QGroupBox("生成的提示词")
        output_layout = QVBoxLayout()
        self.test_output = QTextEdit()
        self.test_output.setReadOnly(True)
        self.test_output.setStyleSheet("background-color: #f8f9fa;")
        output_layout.addWidget(self.test_output)
        output_group.setLayout(output_layout)
        layout.addWidget(output_group)

        return widget

    def load_patterns(self):
        """加载模式列表"""
        self.pattern_list.clear()
        patterns = self.manager.get_all_patterns()

        for pattern in patterns:
            item = QListWidgetItem()
            item.setText(f"{pattern.icon} {pattern.name}")
            item.setData(Qt.ItemDataRole.UserRole, pattern.id)
            item.setToolTip(pattern.description)
            self.pattern_list.addItem(item)

        self.stats_label.setText(f"共 {len(patterns)} 个模式")

    def filter_patterns(self):
        """筛选模式"""
        search = self.search_edit.text().lower()
        category = self.filter_combo.currentData()

        patterns = self.manager.get_all_patterns()

        self.pattern_list.clear()
        for pattern in patterns:
            # 分类筛选
            if category and pattern.category != category:
                continue

            # 搜索筛选
            if search:
                if (search not in pattern.name.lower() and
                    search not in pattern.description.lower() and
                    not any(search in tag.lower() for tag in pattern.tags)):
                    continue

            item = QListWidgetItem()
            item.setText(f"{pattern.icon} {pattern.name}")
            item.setData(Qt.ItemDataRole.UserRole, pattern.id)
            item.setToolTip(pattern.description)
            self.pattern_list.addItem(item)

    def select_pattern(self, item: QListWidgetItem):
        """选择模式"""
        pattern_id = item.data(Qt.ItemDataRole.UserRole)
        self.current_pattern = self.manager.get_pattern(pattern_id)

        if self.current_pattern:
            self.pattern_selected.emit(pattern_id)
            self.update_overview()
            self.update_stats()
            self.detail_edit_btn.setEnabled(True)
            self.preview_btn.setEnabled(True)
            self.generate_btn.setEnabled(True)
            self.status_bar.showMessage(f"已选择: {self.current_pattern.name}")

    def update_overview(self):
        """更新概览"""
        if not self.current_pattern:
            return

        p = self.current_pattern

        # 模式信息
        info = f"""<h3>{p.icon} {p.name}</h3>
<p><b>描述:</b> {p.description}</p>
<p><b>分类:</b> {p.category.value}</p>
<p><b>标签:</b> {', '.join(p.tags) if p.tags else '无'}</p>
<p><b>版本:</b> {p.version}</p>
<p><b>状态:</b> {'启用' if p.enabled else '禁用'}</p>
<p><b>类型:</b> {'系统内置' if p.is_system else '用户自定义'}</p>"""
        self.overview_info.setHtml(info)

        # 触发条件
        trigger_text = f"""类型: {p.trigger.type.value}
关键词: {', '.join(p.trigger.keywords) if p.trigger.keywords else '无'}
置信度阈值: {int(p.trigger.confidence_threshold * 100)}%"""
        self.trigger_info.setText(trigger_text)

        # 模板预览
        self.template_preview.setPlainText(p.template.content)

    def update_stats(self):
        """更新统计"""
        if not self.current_pattern:
            return

        p = self.current_pattern

        # 更新统计卡片
        self._update_stat_value(self.stat_usage, str(p.metadata.usage_count))
        self._update_stat_value(self.stat_success, f"{int(p.metadata.success_rate * 100)}%")
        self._update_stat_value(self.stat_rating, f"{p.metadata.user_rating:.1f}")
        self._update_stat_value(self.stat_quality, f"{p.metadata.effectiveness:.2f}")

        # 最近使用记录
        records = self.manager.get_usage_records(p.id, 10)
        self.history_list.clear()
        for record in records:
            text = f"{record.created_at[:10]} - {'✅' if record.success else '❌'} {record.input_content[:30]}..."
            self.history_list.addItem(text)

    def _update_stat_value(self, card: QWidget, value: str):
        """更新统计卡片值"""
        for child in card.findChildren(QLabel):
            if "font-size: 24px" in child.styleSheet():
                child.setText(value)
                break

    def create_pattern(self):
        """创建新模式"""
        dialog = PatternEditorDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            pattern = dialog.pattern
            if self.manager.create_pattern(pattern):
                self.load_patterns()
                self.status_bar.showMessage(f"已创建模式: {pattern.name}")
            else:
                QMessageBox.warning(self, "错误", "创建模式失败")

    def edit_pattern(self):
        """编辑模式"""
        if not self.current_pattern:
            return

        dialog = PatternEditorDialog(self.current_pattern, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            if self.manager.update_pattern(dialog.pattern):
                self.load_patterns()
                self.status_bar.showMessage(f"已更新模式: {dialog.pattern.name}")
            else:
                QMessageBox.warning(self, "错误", "更新模式失败")

    def delete_pattern(self):
        """删除模式"""
        if not self.current_pattern:
            return

        if self.current_pattern.is_system:
            QMessageBox.warning(self, "提示", "系统内置模式不能删除")
            return

        reply = QMessageBox.question(
            self, "确认", f"确定要删除模式 '{self.current_pattern.name}' 吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            if self.manager.delete_pattern(self.current_pattern.id):
                self.current_pattern = None
                self.load_patterns()
                self.status_bar.showMessage("模式已删除")
            else:
                QMessageBox.warning(self, "错误", "删除模式失败")

    def duplicate_pattern(self):
        """复制模式"""
        if not self.current_pattern:
            return

        new_pattern = self.manager.duplicate_pattern(self.current_pattern.id)
        if new_pattern:
            self.load_patterns()
            self.status_bar.showMessage(f"已复制为: {new_pattern.name}")
        else:
            QMessageBox.warning(self, "错误", "复制模式失败")

    def toggle_enabled(self):
        """切换启用状态"""
        if not self.current_pattern:
            return

        enabled = not self.current_pattern.enabled
        if self.manager.toggle_enabled(self.current_pattern.id, enabled):
            self.load_patterns()
            self.status_bar.showMessage(f"模式已{'启用' if enabled else '禁用'}")
        else:
            QMessageBox.warning(self, "错误", "操作失败")

    def toggle_favorite(self):
        """切换收藏"""
        if not self.current_pattern:
            return

        favorite = not self.current_pattern.favorite
        if self.manager.toggle_favorite(self.current_pattern.id, favorite):
            self.current_pattern.favorite = favorite
            self.status_bar.showMessage(f"已{'收藏' if favorite else '取消收藏'}")
        else:
            QMessageBox.warning(self, "错误", "操作失败")

    def show_context_menu(self, pos):
        """显示右键菜单"""
        if not self.current_pattern:
            return

        menu = QMenu()

        edit_action = QAction("✏️ 编辑", self)
        edit_action.triggered.connect(self.edit_pattern)
        menu.addAction(edit_action)

        menu.addSeparator()

        enable_action = QAction("✅ 启用" if not self.current_pattern.enabled else "⛔ 禁用", self)
        enable_action.triggered.connect(self.toggle_enabled)
        menu.addAction(enable_action)

        favorite_action = QAction("⭐ 收藏" if not self.current_pattern.favorite else "☆ 取消收藏", self)
        favorite_action.triggered.connect(self.toggle_favorite)
        menu.addAction(favorite_action)

        menu.addSeparator()

        duplicate_action = QAction("📋 复制", self)
        duplicate_action.triggered.connect(self.duplicate_pattern)
        menu.addAction(duplicate_action)

        if not self.current_pattern.is_system:
            export_action = QAction("📤 导出", self)
            export_action.triggered.connect(self.export_pattern)
            menu.addAction(export_action)

            menu.addSeparator()

            delete_action = QAction("🗑️ 删除", self)
            delete_action.setObjectName("danger")
            delete_action.triggered.connect(self.delete_pattern)
            menu.addAction(delete_action)

        menu.exec(self.pattern_list.mapToGlobal(pos))

    def import_pattern(self):
        """导入模式"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "导入模式", "", "JSON Files (*.json *.mp.json);;All Files (*)"
        )

        if file_path:
            pattern = self.manager.import_pattern(file_path)
            if pattern:
                self.load_patterns()
                self.status_bar.showMessage(f"已导入模式: {pattern.name}")
            else:
                QMessageBox.warning(self, "错误", "导入模式失败")

    def export_pattern(self):
        """导出模式"""
        if not self.current_pattern:
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出模式", f"{self.current_pattern.name}.json",
            "JSON Files (*.json);;All Files (*)"
        )

        if file_path:
            result = self.manager.export_pattern(self.current_pattern.id, file_path)
            if result:
                self.status_bar.showMessage(f"已导出到: {result}")
            else:
                QMessageBox.warning(self, "错误", "导出模式失败")

    def refresh_preview(self):
        """刷新预览"""
        if not self.current_pattern:
            return

        dialog = PreviewDialog(self.current_pattern, self.generator, self)
        dialog.exec()

    def generate_prompt(self):
        """生成提示词"""
        if not self.current_pattern:
            return

        user_input = self.test_input.toPlainText()
        if not user_input:
            QMessageBox.warning(self, "提示", "请输入测试内容")
            return

        context = ResolverContext(
            user_input=user_input,
            conversation_history=[],
            user_profile={"name": "测试用户"}
        )

        prompt = self.generator.generate(self.current_pattern, context)
        self.test_output.setPlainText(prompt.content)

        self.pattern_applied.emit(self.current_pattern.id)
