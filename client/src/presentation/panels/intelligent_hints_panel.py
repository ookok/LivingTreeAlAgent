"""
智能提示系统 — UI面板
=====================
PyQt6 集成的提示系统管理面板

功能：
- 提示开关
- 层级配置
- 提示历史
- 模板管理
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSwitch, QTabWidget, QListWidget, QListWidgetItem,
    QScrollArea, QTextEdit, QGroupBox, QFormLayout,
    QSlider, QSpinBox, QCheckBox, QComboBox
)
from PyQt6.QtGui import QFont

from client.src.business.intelligent_hints import (
    get_hints_system,
    HintConfig,
    HintLevel,
    GeneratedHint,
)


class HintHistoryItem(QWidget):
    """提示历史条目"""

    def __init__(self, hint: GeneratedHint):
        super().__init__()
        self.hint = hint
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        # 头部
        header = QHBoxLayout()
        header.setSpacing(6)

        emoji = QLabel(self.hint.emoji)
        emoji.setFont(QFont("", 14))
        header.addWidget(emoji)

        level_label = QLabel(f"[{self.hint.hint_level.value}]")
        level_label.setFont(QFont("", 8))
        level_label.setStyleSheet("color: #888;")
        header.addWidget(level_label)

        header.addStretch()

        time_label = QLabel(self.hint.generated_at.strftime("%H:%M:%S"))
        time_label.setFont(QFont("", 8))
        time_label.setStyleSheet("color: #aaa;")
        header.addWidget(time_label)

        layout.addLayout(header)

        # 内容
        content = QLabel(self.hint.content)
        content.setWordWrap(True)
        content.setFont(QFont("", 9))
        layout.addWidget(content)

        # 状态
        if self.hint.is_dismissed:
            status = QLabel("已忽略")
            status.setStyleSheet("color: #999; font-size: 8px;")
            layout.addWidget(status)


class IntelligentHintsPanel(QWidget):
    """
    智能提示系统面板

    标签页：
    1. 总览 — 开关和状态
    2. 层级设置 — 各层级配置
    3. 提示历史 — 最近提示
    4. 场景测试 — 测试各场景提示
    """

    def __init__(self):
        super().__init__()
        self._system = get_hints_system()
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # 标题
        title = QLabel("🌿 智能提示系统")
        title.setFont(QFont("", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        # Tab 容器
        tabs = QTabWidget()
        tabs.setTabPosition(QTabWidget.TabPosition.North)

        # 1. 总览标签页
        tabs.addTab(self._create_overview_tab(), "总览")
        # 2. 层级设置标签页
        tabs.addTab(self._create_levels_tab(), "层级设置")
        # 3. 提示历史标签页
        tabs.addTab(self._create_history_tab(), "提示历史")
        # 4. 场景测试标签页
        tabs.addTab(self._create_test_tab(), "场景测试")

        layout.addWidget(tabs)

    def _create_overview_tab(self) -> QWidget:
        """创建总览标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(16)

        # 开关组
        switch_group = QGroupBox("开关设置")
        switch_layout = QFormLayout()

        self.enabled_switch = QSwitch()
        self.enabled_switch.setChecked(self._system.is_enabled())
        switch_layout.addRow("启用提示系统", self.enabled_switch)

        self.air_icon_switch = QSwitch()
        self.air_icon_switch.setChecked(self._system.config.show_air_icon)
        switch_layout.addRow("显示空气图标", self.air_icon_switch)

        self.breath_switch = QSwitch()
        self.breath_switch.setChecked(self._system.config.breath_animation)
        switch_layout.addRow("呼吸动画", self.breath_switch)

        self.learn_switch = QSwitch()
        self.learn_switch.setChecked(self._system.config.learn_from_user)
        switch_layout.addRow("学习用户习惯", self.learn_switch)

        switch_group.setLayout(switch_layout)
        layout.addWidget(switch_group)

        # 显示设置
        display_group = QGroupBox("显示设置")
        display_layout = QFormLayout()

        self.max_hints_spin = QSpinBox()
        self.max_hints_spin.setRange(1, 10)
        self.max_hints_spin.setValue(self._system.config.max_visible_hints)
        self.max_hints_spin.setSuffix(" 条")
        display_layout.addRow("最多显示", self.max_hints_spin)

        self.auto_hide_spin = QSpinBox()
        self.auto_hide_spin.setRange(0, 60)
        self.auto_hide_spin.setValue(self._system.config.auto_hide_delay // 1000)
        self.auto_hide_spin.setSuffix(" 秒")
        display_layout.addRow("自动隐藏", self.auto_hide_spin)

        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 60)
        self.interval_spin.setValue(self._system.config.generate_interval // 1000)
        self.interval_spin.setSuffix(" 秒")
        display_layout.addRow("检查间隔", self.interval_spin)

        display_group.setLayout(display_layout)
        layout.addWidget(display_group)

        layout.addStretch()
        return widget

    def _create_levels_tab(self) -> QWidget:
        """创建层级设置标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        # 层级说明
        info = QLabel(
            "提示层级说明：\n"
            "• 透明 — 完全不打扰，仅记录\n"
            "• 微光 — 安静存在，悬停可见\n"
            "• 轻柔 — 右下角小卡片，不遮挡\n"
            "• 重要 — 明确提示，需要关注\n"
            "• 紧急 — 立即处理，不容忽视"
        )
        info.setStyleSheet("color: #666; font-size: 11px; background: #f5f5f5; padding: 10px; border-radius: 6px;")
        layout.addWidget(info)

        # 自动显示层级
        auto_group = QGroupBox("自动显示设置")
        auto_layout = QFormLayout()

        self.auto_level_combo = QComboBox()
        for level in HintLevel:
            self.auto_level_combo.addItem(level.value, level)
        current_idx = self.auto_level_combo.findData(self._system.config.auto_show_level)
        if current_idx >= 0:
            self.auto_level_combo.setCurrentIndex(current_idx)
        auto_layout.addRow("自动显示层级", self.auto_level_combo)

        auto_group.setLayout(auto_layout)
        layout.addWidget(auto_group)

        layout.addStretch()
        return widget

    def _create_history_tab(self) -> QWidget:
        """创建提示历史标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 工具栏
        toolbar = QHBoxLayout()
        self.refresh_history_btn = QPushButton("刷新")
        self.clear_history_btn = QPushButton("清空历史")
        self.clear_history_btn.setStyleSheet("color: #F44336;")
        toolbar.addWidget(self.refresh_history_btn)
        toolbar.addWidget(self.clear_history_btn)
        toolbar.addStretch()

        layout.addLayout(toolbar)

        # 历史列表
        self.history_list = QListWidget()
        self.history_list.setAlternatingRowColors(True)
        layout.addWidget(self.history_list)

        # 加载历史
        self._load_history()
        return widget

    def _create_test_tab(self) -> QWidget:
        """创建场景测试标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        # 场景选择
        scene_group = QGroupBox("选择测试场景")
        scene_layout = QFormLayout()

        self.scene_combo = QComboBox()
        scenes = [
            ("model_select", "模型选择"),
            ("chat", "聊天"),
            ("writing", "写作"),
            ("settings", "设置"),
            ("network_issue", "网络问题"),
            ("low_performance", "性能问题"),
            ("file_operation", "文件操作"),
        ]
        for scene_id, scene_name in scenes:
            self.scene_combo.addItem(scene_name, scene_id)
        scene_layout.addRow("场景", self.scene_combo)

        scene_group.setLayout(scene_layout)
        layout.addWidget(scene_group)

        # 测试参数
        param_group = QGroupBox("测试参数")
        param_layout = QFormLayout()

        self.test_action = QTextEdit()
        self.test_action.setMaximumHeight(60)
        self.test_action.setPlaceholderText("输入用户动作描述...")
        param_layout.addRow("用户动作", self.test_action)

        self.test_options = QTextEdit()
        self.test_options.setMaximumHeight(60)
        self.test_options.setPlaceholderText("输入选项，逗号分隔...")
        param_layout.addRow("可用选项", self.test_options)

        self.test_device = QComboBox()
        self.test_device.addItems(["正常", "网络差", "内存高", "CPU高"])
        param_layout.addRow("设备状态", self.test_device)

        param_group.setLayout(param_layout)
        layout.addWidget(param_group)

        # 发送测试按钮
        self.send_test_btn = QPushButton("发送测试提示")
        self.send_test_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        layout.addWidget(self.send_test_btn)

        layout.addStretch()
        return widget

    def _connect_signals(self):
        """连接信号"""
        # 开关
        self.enabled_switch.toggled.connect(self._on_enabled_changed)
        self.air_icon_switch.toggled.connect(self._on_air_icon_changed)
        self.breath_switch.toggled.connect(self._on_breath_changed)
        self.learn_switch.toggled.connect(self._on_learn_changed)

        # 数值
        self.max_hints_spin.valueChanged.connect(self._on_max_hints_changed)
        self.auto_hide_spin.valueChanged.connect(self._on_auto_hide_changed)
        self.interval_spin.valueChanged.connect(self._on_interval_changed)

        # 历史
        self.refresh_history_btn.clicked.connect(self._load_history)
        self.clear_history_btn.clicked.connect(self._on_clear_history)

        # 测试
        self.send_test_btn.clicked.connect(self._on_send_test)

        # 系统信号
        self._system.hint_generated.connect(self._on_hint_generated)

    def _on_enabled_changed(self, checked: bool):
        self._system.set_enabled(checked)

    def _on_air_icon_changed(self, checked: bool):
        self._system.show_air_icon(checked)

    def _on_breath_changed(self, checked: bool):
        self._system.config.breath_animation = checked
        self._system.save_config()

    def _on_learn_changed(self, checked: bool):
        self._system.config.learn_from_user = checked
        self._system.save_config()

    def _on_max_hints_changed(self, value: int):
        self._system.config.max_visible_hints = value
        self._system.save_config()

    def _on_auto_hide_changed(self, value: int):
        self._system.config.auto_hide_delay = value * 1000
        self._system.save_config()

    def _on_interval_changed(self, value: int):
        self._system.config.generate_interval = value * 1000
        self._system.save_config()

    def _load_history(self):
        """加载历史"""
        self.history_list.clear()
        history = self._system.get_hint_history(50)
        for hint in reversed(history):
            item = QListWidgetItem()
            item.setSizeHint(HintHistoryItem(hint).sizeHint())
            self.history_list.addItem(item)
            self.history_list.setItemWidget(item, HintHistoryItem(hint))

    def _on_clear_history(self):
        self._system.clear_hints()
        self._load_history()

    def _on_send_test(self):
        """发送测试提示"""
        scene_id = self.scene_combo.currentData()
        action = self.test_action.toPlainText().strip()
        options_text = self.test_options.toPlainText().strip()
        options = [o.strip() for o in options_text.split(",")] if options_text else []

        device_status = self.test_device.currentText()
        device_info = {}
        if device_status == "网络差":
            device_info["network"] = "poor"
        elif device_status == "内存高":
            device_info["memory"] = 90
        elif device_status == "CPU高":
            device_info["cpu"] = 90

        self._system.emit_context(
            scene_id=scene_id,
            user_action=action or scene_id,
            options=options,
            device_info=device_info
        )

    def _on_hint_generated(self, hint: GeneratedHint):
        """新提示生成"""
        # 自动刷新历史
        if hasattr(self, 'history_list'):
            self._load_history()
