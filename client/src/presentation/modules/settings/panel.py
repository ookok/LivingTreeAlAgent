"""
设置模块 - 系统设置面板

包含功能：
- 一键切换模型
- 模型状态监控
- 模型管理
- 配置管理

Author: LivingTreeAI Agent
Date: 2026-04-30
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QGroupBox, QGridLayout,
    QLineEdit, QComboBox, QCheckBox, QFrame, QSpacerItem,
    QSizePolicy, QProgressBar, QMessageBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QIcon, QFont, QPalette, QColor

from ...theme import theme_manager
from business.model_switcher import ModelSwitcher, ModelConfig, SwitchResult


class ModelSwitchWorker(QThread):
    """模型切换工作线程"""
    switch_done = pyqtSignal(SwitchResult)
    
    def __init__(self, switcher: ModelSwitcher, model_name: str):
        super().__init__()
        self._switcher = switcher
        self._model_name = model_name
    
    def run(self):
        result = self._switcher.switch_to(self._model_name)
        self.switch_done.emit(result)


class Panel(QWidget):
    """设置面板 - 包含一键切换模型功能"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._switcher = ModelSwitcher.get_instance()
        self._setup_ui()
        self._update_model_list()
        
        # 定时刷新状态
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_status)
        self._timer.start(5000)  # 每5秒刷新

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # 标题
        title_label = QLabel("⚙️ 系统设置")
        title_label.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        title_label.setStyleSheet(f"color: {theme_manager.colors.TEXT_PRIMARY};")
        layout.addWidget(title_label)

        # 当前模型信息卡片
        self._current_model_card = self._create_current_model_card()
        layout.addWidget(self._current_model_card)

        # 模型切换区域
        self._model_switch_group = self._create_model_switch_group()
        layout.addWidget(self._model_switch_group)

        # 快速切换按钮
        self._quick_switch_buttons = self._create_quick_switch_buttons()
        layout.addWidget(self._quick_switch_buttons)

        # 模型管理区域
        self._model_manage_group = self._create_model_manage_group()
        layout.addWidget(self._model_manage_group)

        # 底部提示
        tip_label = QLabel("💡 提示：模型切换会立即生效，当前会话不受影响")
        tip_label.setStyleSheet(f"color: {theme_manager.colors.TEXT_TERTIARY}; font-size: 12px;")
        layout.addWidget(tip_label)

        layout.addStretch()

    def _create_current_model_card(self):
        """创建当前模型信息卡片"""
        card = QGroupBox("当前模型")
        card.setStyleSheet(self._get_card_style())
        
        layout = QGridLayout(card)
        layout.setSpacing(12)

        # 当前模型名称
        self._current_model_label = QLabel("未设置")
        self._current_model_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        self._current_model_label.setStyleSheet(f"color: {theme_manager.colors.ACCENT_PRIMARY};")
        layout.addWidget(self._current_model_label, 0, 0, 1, 2)

        # 提供者信息
        self._provider_label = QLabel("提供者: -")
        self._provider_label.setStyleSheet(f"color: {theme_manager.colors.TEXT_SECONDARY};")
        layout.addWidget(self._provider_label, 1, 0)

        # Model ID
        self._model_id_label = QLabel("Model ID: -")
        self._model_id_label.setStyleSheet(f"color: {theme_manager.colors.TEXT_SECONDARY};")
        layout.addWidget(self._model_id_label, 1, 1)

        # 状态指示器
        self._status_indicator = QLabel("●")
        self._status_indicator.setFont(QFont("Segoe UI", 14))
        self._status_indicator.setStyleSheet("color: #4CAF50;")
        layout.addWidget(self._status_indicator, 0, 2)

        return card

    def _create_model_switch_group(self):
        """创建模型切换区域"""
        group = QGroupBox("模型列表")
        group.setStyleSheet(self._get_group_style())

        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        # 模型列表
        self._model_list = QListWidget()
        self._model_list.setStyleSheet(self._get_list_style())
        self._model_list.itemClicked.connect(self._on_model_clicked)
        self._model_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        layout.addWidget(self._model_list)

        # 切换按钮
        self._switch_button = QPushButton("切换到此模型")
        self._switch_button.setStyleSheet(self._get_button_style())
        self._switch_button.clicked.connect(self._on_switch_clicked)
        self._switch_button.setEnabled(False)
        layout.addWidget(self._switch_button)

        # 加载状态
        self._loading_bar = QProgressBar()
        self._loading_bar.setVisible(False)
        self._loading_bar.setRange(0, 0)  # 不确定进度
        layout.addWidget(self._loading_bar)

        return group

    def _create_quick_switch_buttons(self):
        """创建快速切换按钮组"""
        group = QGroupBox("快速切换")
        group.setStyleSheet(self._get_group_style())

        layout = QHBoxLayout(group)
        layout.setSpacing(10)

        # 上一个按钮
        self._prev_button = QPushButton("⬅ 上一个")
        self._prev_button.setStyleSheet(self._get_small_button_style())
        self._prev_button.clicked.connect(self._on_prev_clicked)
        layout.addWidget(self._prev_button)

        # 下一个按钮
        self._next_button = QPushButton("下一个 ➡")
        self._next_button.setStyleSheet(self._get_small_button_style())
        self._next_button.clicked.connect(self._on_next_clicked)
        layout.addWidget(self._next_button)

        layout.addStretch()

        return group

    def _create_model_manage_group(self):
        """创建模型管理区域"""
        group = QGroupBox("模型管理")
        group.setStyleSheet(self._get_group_style())

        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        # 添加模型表单
        add_layout = QGridLayout()
        
        add_layout.addWidget(QLabel("模型名称:"), 0, 0)
        self._new_model_name = QLineEdit()
        self._new_model_name.setPlaceholderText("输入模型名称")
        add_layout.addWidget(self._new_model_name, 0, 1)

        add_layout.addWidget(QLabel("提供者:"), 1, 0)
        self._new_model_provider = QComboBox()
        self._new_model_provider.addItems(["anthropic", "openai", "google", "ollama", "deepseek", "minimax"])
        add_layout.addWidget(self._new_model_provider, 1, 1)

        add_layout.addWidget(QLabel("Model ID:"), 2, 0)
        self._new_model_id = QLineEdit()
        self._new_model_id.setPlaceholderText("输入模型 ID")
        add_layout.addWidget(self._new_model_id, 2, 1)

        add_button = QPushButton("添加模型")
        add_button.setStyleSheet(self._get_small_button_style())
        add_button.clicked.connect(self._on_add_model)
        add_layout.addWidget(add_button, 3, 0, 1, 2)

        layout.addLayout(add_layout)

        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"color: {theme_manager.colors.BORDER};")
        layout.addWidget(line)

        # 测试按钮
        test_button = QPushButton("测试当前模型连接")
        test_button.setStyleSheet(self._get_small_button_style())
        test_button.clicked.connect(self._on_test_model)
        layout.addWidget(test_button)

        # 刷新按钮
        refresh_button = QPushButton("刷新模型列表")
        refresh_button.setStyleSheet(self._get_small_button_style())
        refresh_button.clicked.connect(self._update_model_list)
        layout.addWidget(refresh_button)

        return group

    def _update_model_list(self):
        """更新模型列表"""
        self._model_list.clear()
        models = self._switcher.list_models()
        
        current_model = self._switcher.get_current_model()
        current_name = current_model.name if current_model else None

        for model in models:
            item = QListWidgetItem()
            item.setText(model.name)
            item.setData(Qt.ItemDataRole.UserRole, model)
            
            # 当前模型标记
            if model.name == current_name:
                item.setIcon(QIcon.fromTheme("check"))
                item.setBackground(QColor(theme_manager.colors.ACCENT_PRIMARY).lighter(180))
            
            # 禁用模型标记
            if not model.enabled:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
                item.setForeground(QColor(theme_manager.colors.TEXT_TERTIARY))
            
            self._model_list.addItem(item)

        self._update_status()

    def _update_status(self):
        """更新当前模型状态"""
        current = self._switcher.get_current_model()
        
        if current:
            self._current_model_label.setText(current.name)
            self._provider_label.setText(f"提供者: {current.provider}")
            self._model_id_label.setText(f"Model ID: {current.model_id}")
            self._status_indicator.setStyleSheet("color: #4CAF50;")
            self._status_indicator.setToolTip("模型正常")
        else:
            self._current_model_label.setText("未设置")
            self._provider_label.setText("提供者: -")
            self._model_id_label.setText("Model ID: -")
            self._status_indicator.setStyleSheet("color: #9E9E9E;")
            self._status_indicator.setToolTip("未选择模型")

    def _on_model_clicked(self, item):
        """点击模型列表项"""
        model = item.data(Qt.ItemDataRole.UserRole)
        if model and model.enabled:
            self._switch_button.setEnabled(True)
            self._switch_button.setText(f"切换到 {model.name}")
        else:
            self._switch_button.setEnabled(False)
            self._switch_button.setText("切换到此模型")

    def _on_switch_clicked(self):
        """点击切换按钮"""
        selected = self._model_list.selectedItems()
        if not selected:
            return

        model = selected[0].data(Qt.ItemDataRole.UserRole)
        if not model:
            return

        # 显示加载状态
        self._loading_bar.setVisible(True)
        self._switch_button.setEnabled(False)

        # 在后台线程执行切换
        self._worker = ModelSwitchWorker(self._switcher, model.name)
        self._worker.switch_done.connect(self._on_switch_done)
        self._worker.start()

    def _on_switch_done(self, result: SwitchResult):
        """切换完成回调"""
        self._loading_bar.setVisible(False)
        self._switch_button.setEnabled(True)

        if result.success:
            QMessageBox.information(self, "切换成功", result.message)
            self._update_model_list()
        else:
            QMessageBox.warning(self, "切换失败", result.message)

    def _on_prev_clicked(self):
        """点击上一个按钮"""
        result = self._switcher.cycle_models("previous")
        if result.success:
            self._update_model_list()
            QMessageBox.information(self, "切换成功", result.message)
        else:
            QMessageBox.warning(self, "切换失败", result.message)

    def _on_next_clicked(self):
        """点击下一个按钮"""
        result = self._switcher.cycle_models("next")
        if result.success:
            self._update_model_list()
            QMessageBox.information(self, "切换成功", result.message)
        else:
            QMessageBox.warning(self, "切换失败", result.message)

    def _on_add_model(self):
        """添加新模型"""
        name = self._new_model_name.text().strip()
        provider = self._new_model_provider.currentText()
        model_id = self._new_model_id.text().strip()

        if not name or not model_id:
            QMessageBox.warning(self, "输入错误", "请填写模型名称和 Model ID")
            return

        config = ModelConfig(
            name=name,
            provider=provider,
            model_id=model_id,
            enabled=True
        )

        self._switcher.add_model(config)
        self._update_model_list()

        # 清空输入
        self._new_model_name.clear()
        self._new_model_id.clear()

        QMessageBox.information(self, "添加成功", f"已添加模型: {name}")

    def _on_test_model(self):
        """测试模型连接"""
        current = self._switcher.get_current_model()
        if not current:
            QMessageBox.warning(self, "未选择模型", "请先选择一个模型")
            return

        # 在后台线程执行测试
        import asyncio
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(self._switcher.test_model(current.name))
        loop.close()

        if result["success"]:
            msg = f"连接成功!\n响应时间: {result.get('response_time', 0):.2f}s"
            QMessageBox.information(self, "测试成功", msg)
        else:
            QMessageBox.warning(self, "测试失败", result.get("message", "未知错误"))

    def _get_card_style(self):
        """获取卡片样式"""
        return f"""
            QGroupBox {{
                border: 1px solid {theme_manager.colors.BORDER};
                border-radius: 12px;
                padding: 16px;
                background: {theme_manager.colors.CARD};
            }}
            QGroupBox::title {{
                color: {theme_manager.colors.TEXT_SECONDARY};
                font-weight: bold;
                padding: 0 8px;
                left: 10px;
                top: -10px;
                background: {theme_manager.colors.BACKGROUND};
            }}
        """

    def _get_group_style(self):
        """获取分组样式"""
        return f"""
            QGroupBox {{
                border: 1px solid {theme_manager.colors.BORDER};
                border-radius: 8px;
                padding: 12px;
                background: {theme_manager.colors.CARD};
            }}
            QGroupBox::title {{
                color: {theme_manager.colors.TEXT_SECONDARY};
                font-weight: bold;
                padding: 0 8px;
                left: 10px;
                top: -8px;
                background: {theme_manager.colors.BACKGROUND};
            }}
        """

    def _get_button_style(self):
        """获取按钮样式"""
        return f"""
            QPushButton {{
                background: {theme_manager.colors.ACCENT_PRIMARY};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: {theme_manager.colors.ACCENT_PRIMARY_DARK};
            }}
            QPushButton:disabled {{
                background: {theme_manager.colors.BORDER};
                color: {theme_manager.colors.TEXT_TERTIARY};
            }}
        """

    def _get_small_button_style(self):
        """获取小按钮样式"""
        return f"""
            QPushButton {{
                background: {theme_manager.colors.SURFACE};
                color: {theme_manager.colors.TEXT_PRIMARY};
                border: 1px solid {theme_manager.colors.BORDER};
                border-radius: 6px;
                padding: 6px 12px;
            }}
            QPushButton:hover {{
                background: {theme_manager.colors.BORDER};
            }}
        """

    def _get_list_style(self):
        """获取列表样式"""
        return f"""
            QListWidget {{
                background: {theme_manager.colors.SURFACE};
                border: 1px solid {theme_manager.colors.BORDER};
                border-radius: 6px;
                padding: 4px;
            }}
            QListWidget::item {{
                padding: 8px;
                border-radius: 4px;
            }}
            QListWidget::item:hover {{
                background: {theme_manager.colors.BORDER};
            }}
            QListWidget::item:selected {{
                background: {theme_manager.colors.ACCENT_PRIMARY};
                color: white;
            }}
        """