# =================================================================
# 智能填表增强面板 - Form Filler Panel
# =================================================================
# PyQt6 集成面板
# =================================================================

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QListWidget, QStackedWidget, QProgressBar,
    QGroupBox, QFormLayout, QLineEdit, QCheckBox, QComboBox,
    QSpinBox, QDoubleSpinBox, QTabWidget, QTableWidget,
    QTableWidgetItem, QHeaderView, QSplitter, QFrame,
    QScrollArea, QProgressDialog
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QIcon, QAction


class FormFillerPanel(QWidget):
    """
    智能填表增强面板

    功能：
    1. 填表状态总览
    2. 字段映射配置
    3. 知识库管理
    4. 历史记录查看
    5. 格式设置
    """

    # 信号
    enabled_changed = pyqtSignal(bool)
    suggestion_selected = pyqtSignal(str, str)  # field_name, value
    fill_requested = pyqtSignal(str, str)      # field_name, value

    def __init__(self, parent=None):
        super().__init__(parent)
        self._enabled = True
        self._current_form = None
        self._suggestions = {}

        self._init_ui()

    def _init_ui(self):
        """初始化 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # 标题栏
        header = self._create_header()
        layout.addWidget(header)

        # Tab 页面
        tabs = QTabWidget()
        tabs.addTab(self._create_overview_tab(), "📊 总览")
        tabs.addTab(self._create_fields_tab(), "📝 字段")
        tabs.addTab(self._create_knowledge_tab(), "📚 知识库")
        tabs.addTab(self._create_history_tab(), "📜 历史")
        tabs.addTab(self._create_settings_tab(), "⚙️ 设置")

        layout.addWidget(tabs)

        # 状态栏
        status = self._create_status_bar()
        layout.addWidget(status)

    def _create_header(self) -> QWidget:
        """创建标题栏"""
        widget = QFrame()
        widget.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    from:#1a5f2a, to:#2e8b3d);
                border-radius: 8px;
                padding: 12px;
            }
        """)
        layout = QHBoxLayout(widget)

        # 标题
        title = QLabel("🌿 智能填表助手")
        title.setStyleSheet("color: white; font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        layout.addStretch()

        # 启用开关
        self._enable_btn = QPushButton("已启用")
        self._enable_btn.setCheckable(True)
        self._enable_btn.setChecked(True)
        self._enable_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.2);
                color: white;
                border: 1px solid rgba(255,255,255,0.3);
                border-radius: 4px;
                padding: 6px 16px;
            }
            QPushButton:checked {
                background: rgba(255,255,255,0.3);
            }
        """)
        self._enable_btn.clicked.connect(self._on_enable_changed)
        layout.addWidget(self._enable_btn)

        return widget

    def _create_overview_tab(self) -> QWidget:
        """创建总览页面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 进度卡片
        progress_card = self._create_progress_card()
        layout.addWidget(progress_card)

        # 当前表单信息
        form_info = self._create_form_info_card()
        layout.addWidget(form_info)

        layout.addStretch()

        return widget

    def _create_progress_card(self) -> QFrame:
        """创建进度卡片"""
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background: white;
                border-radius: 8px;
                padding: 16px;
                border: 1px solid #e0e0e0;
            }
        """)
        layout = QVBoxLayout(card)

        title = QLabel("填表进度")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #1a5f2a;")
        layout.addWidget(title)

        # 进度条
        self._progress_bar = QProgressBar()
        self._progress_bar.setStyleSheet("""
            QProgressBar {
                height: 20px;
                border-radius: 10px;
                background: #f0f0f0;
                text-align: center;
            }
            QProgressBar::chunk {
                border-radius: 10px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    from:#1a5f2a, to:#2e8b3d);
            }
        """)
        layout.addWidget(self._progress_bar)

        # 进度标签
        self._progress_label = QLabel("0 / 0 个字段已填充")
        self._progress_label.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(self._progress_label)

        return card

    def _create_form_info_card(self) -> QFrame:
        """创建表单信息卡片"""
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background: white;
                border-radius: 8px;
                padding: 16px;
                border: 1px solid #e0e0e0;
            }
        """)
        layout = QFormLayout(card)

        layout.addRow("页面 URL:", QLabel("-"))
        layout.addRow("表单类型:", QLabel("-"))
        layout.addRow("字段总数:", QLabel("0"))
        layout.addRow("必填字段:", QLabel("0"))

        return card

    def _create_fields_tab(self) -> QWidget:
        """创建字段映射页面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 工具栏
        toolbar = QHBoxLayout()
        toolbar.addWidget(QPushButton("🔄 刷新"))
        toolbar.addWidget(QPushButton("📋 全部填充"))
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # 字段列表
        self._fields_table = QTableWidget()
        self._fields_table.setColumnCount(5)
        self._fields_table.setHorizontalHeaderLabels([
            "字段名", "标签", "类型", "状态", "建议值"
        ])
        self._fields_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self._fields_table)

        return widget

    def _create_knowledge_tab(self) -> QWidget:
        """创建知识库页面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        info = QLabel("📚 从本地知识库获取填表数据")

        # 知识库分类
        categories = QListWidget()
        categories.addItems([
            "个人信息",
            "企业信息",
            "常用地址",
            "证件信息",
            "银行账户",
        ])

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(categories)

        detail = QTextEdit()
        detail.setPlaceholderText("选择分类查看详细数据")
        splitter.addWidget(detail)

        layout.addWidget(info)
        layout.addWidget(splitter)

        return widget

    def _create_history_tab(self) -> QWidget:
        """创建历史记录页面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 统计
        stats_layout = QHBoxLayout()
        stats_layout.addWidget(QLabel("总记录数: 0"))
        stats_layout.addWidget(QLabel("成功率: 0%"))
        stats_layout.addStretch()
        layout.addLayout(stats_layout)

        # 历史列表
        self._history_list = QListWidget()
        self._history_list.setStyleSheet("""
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #f0f0f0;
            }
        """)
        layout.addWidget(self._history_list)

        return widget

    def _create_settings_tab(self) -> QWidget:
        """创建设置页面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 自动填充设置
        auto_group = QGroupBox("自动填充")
        auto_layout = QVBoxLayout(auto_group)

        auto_layout.addWidget(QCheckBox("启用智能填表"))
        auto_layout.addWidget(QCheckBox("自动填充高置信度字段"))
        auto_layout.addWidget(QCheckBox("自动跳过验证码"))

        # 置信度阈值
        threshold_layout = QHBoxLayout()
        threshold_layout.addWidget(QLabel("自动填充阈值:"))
        threshold_spin = QSpinBox()
        threshold_spin.setRange(50, 100)
        threshold_spin.setValue(90)
        threshold_spin.setSuffix("%")
        threshold_layout.addWidget(threshold_spin)
        threshold_layout.addStretch()
        auto_layout.addLayout(threshold_layout)

        layout.addWidget(auto_group)

        # 格式设置
        format_group = QGroupBox("格式设置")
        format_layout = QVBoxLayout(format_group)

        format_layout.addWidget(QCheckBox("自动格式化手机号"))
        format_layout.addWidget(QCheckBox("自动格式化日期"))
        format_layout.addWidget(QCheckBox("自动格式化金额"))

        layout.addWidget(format_group)

        # 隐私设置
        privacy_group = QGroupBox("隐私")
        privacy_layout = QVBoxLayout(privacy_group)

        privacy_layout.addWidget(QCheckBox("记住填表历史"))
        privacy_layout.addWidget(QCheckBox("同步到知识库"))
        privacy_layout.addWidget(QCheckBox("匿名统计使用情况"))

        layout.addWidget(privacy_group)

        layout.addStretch()

        return widget

    def _create_status_bar(self) -> QWidget:
        """创建状态栏"""
        bar = QFrame()
        bar.setStyleSheet("""
            QFrame {
                background: #f5f5f5;
                border-radius: 4px;
                padding: 6px 12px;
            }
        """)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(0, 0, 0, 0)

        self._status_label = QLabel("🌿 智能填表助手已就绪")
        self._status_label.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(self._status_label)

        layout.addStretch()

        # 快捷操作
        quick_actions = QHBoxLayout()
        quick_actions.addWidget(QPushButton("🎯 聚焦下一个"))
        quick_actions.addWidget(QPushButton("✅ 采纳建议"))
        layout.addLayout(quick_actions)

        return bar

    # ========== 公共接口 ==========

    def set_enabled(self, enabled: bool):
        """设置启用状态"""
        self._enabled = enabled
        self._enable_btn.setText("已启用" if enabled else "已禁用")
        self._enable_btn.setChecked(enabled)
        self.enabled_changed.emit(enabled)

    def update_form(self, form_data: dict):
        """更新表单信息"""
        self._current_form = form_data
        self._update_fields_table(form_data.get("fields", []))

    def update_suggestions(self, field_name: str, suggestions: list):
        """更新字段建议"""
        self._suggestions[field_name] = suggestions
        self._update_fields_table(self._current_form.get("fields", []) if self._current_form else [])

    def set_progress(self, current: int, total: int):
        """设置进度"""
        if total > 0:
            percent = int(current / total * 100)
            self._progress_bar.setValue(percent)
            self._progress_label.setText(f"{current} / {total} 个字段已填充")
        else:
            self._progress_bar.setValue(0)
            self._progress_label.setText("0 / 0 个字段已填充")

    def show_notification(self, message: str, duration: int = 3000):
        """显示通知"""
        self._status_label.setText(f"🌿 {message}")
        if duration > 0:
            QTimer.singleShot(duration, lambda: self._status_label.setText("🌿 智能填表助手已就绪"))

    # ========== 事件处理 ==========

    def _on_enable_changed(self, checked: bool):
        """启用状态改变"""
        self.set_enabled(checked)

    def _update_fields_table(self, fields: list):
        """更新字段表格"""
        self._fields_table.setRowCount(len(fields))

        for i, field in enumerate(fields):
            self._fields_table.setItem(i, 0, QTableWidgetItem(field.get("name", "")))
            self._fields_table.setItem(i, 1, QTableWidgetItem(field.get("label", "")))
            self._fields_table.setItem(i, 2, QTableWidgetItem(field.get("semantic_type", "")))

            status = "已填充" if field.get("filled") else "未填充"
            status_item = QTableWidgetItem(status)
            status_item.setForeground(Qt.GlobalColor.green if field.get("filled") else Qt.GlobalColor.gray)
            self._fields_table.setItem(i, 3, status_item)

            # 建议值
            suggestions = self._suggestions.get(field.get("name", ""), [])
            if suggestions:
                suggestion_text = ", ".join([str(s.get("value", "")) for s in suggestions[:2]])
                self._fields_table.setItem(i, 4, QTableWidgetItem(suggestion_text))
            else:
                self._fields_table.setItem(i, 4, QTableWidgetItem("-"))
