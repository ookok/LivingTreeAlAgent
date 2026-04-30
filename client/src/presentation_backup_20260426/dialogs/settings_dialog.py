"""
用户设置和系统设置对话框
包含：用户设置（数字身份+积分）、系统设置（模型+界面+性能+连接）
集成 AgentChat 配置
"""

from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QComboBox,
    QCheckBox, QGroupBox, QTabWidget, QSpinBox,
    QDialog, QFileDialog, QProgressBar, QTextEdit,
)
from PyQt6.QtGui import QFont

# 导入主题管理器
try:
    from .presentation.theme import theme_manager
except ImportError:
    theme_manager = None


class UserSettingsDialog(QDialog):
    """用户设置对话框 - 包含数字身份和积分"""

    settings_saved = pyqtSignal(dict)

    def __init__(self, user_info: dict = None, parent=None):
        super().__init__(parent)
        self.user_info = user_info or {}
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("👤 用户设置")
        self.setMinimumSize(600, 600)
        self.setStyleSheet("""
            QDialog {
                background: #1A1A1A;
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
            QPushButton[primary="true"] {
                background: #00D4AA;
                color: #0D0D0D;
                font-weight: bold;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # Tab 页面
        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #333333;
                border-radius: 8px;
                padding: 16px;
                background: #0D0D0D;
            }
            QTabBar::tab {
                background: #252525;
                color: #A0A0A0;
                padding: 8px 16px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }
            QTabBar::tab:selected {
                background: #00D4AA;
                color: #0D0D0D;
            }
        """)

        tabs.addTab(self._create_profile_tab(), "👤 个人信息")
        tabs.addTab(self._create_identity_tab(), "🎭 数字身份")
        tabs.addTab(self._create_credit_tab(), "💰 积分")
        tabs.addTab(self._create_workspace_tab(), "📁 工作空间")
        tabs.addTab(self._create_notification_tab(), "🔔 通知")

        layout.addWidget(tabs, 1)

        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("保存")
        save_btn.setProperty("primary", "true")
        save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

    def _create_profile_tab(self) -> QWidget:
        """个人信息"""
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setSpacing(16)

        self.username = QLineEdit()
        self.username.setText(self.user_info.get("username", ""))
        self._style_input(self.username)
        layout.addRow("用户名:", self.username)

        self.email = QLineEdit()
        self.email.setText(self.user_info.get("email", ""))
        self.email.setPlaceholderText("your@email.com")
        self._style_input(self.email)
        layout.addRow("邮箱:", self.email)

        self.signature = QLineEdit()
        self.signature.setText(self.user_info.get("signature", ""))
        self.signature.setPlaceholderText("一句话介绍自己...")
        self._style_input(self.signature)
        layout.addRow("签名:", self.signature)

        return widget

    def _create_identity_tab(self) -> QWidget:
        """数字身份"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(16)

        # 身份卡片
        identity_card = QFrame()
        identity_card.setStyleSheet("""
            QFrame {
                background: #252525;
                border-radius: 12px;
                padding: 16px;
            }
        """)
        card_layout = QVBoxLayout(identity_card)
        card_layout.setSpacing(12)

        # 标题行
        header_layout = QHBoxLayout()
        title = QLabel("🎭 我的数字身份")
        title.setStyleSheet("color: #00D4AA; font-size: 16px; font-weight: bold;")
        header_layout.addWidget(title)
        header_layout.addStretch()

        status_label = QLabel("● 已激活")
        status_label.setStyleSheet("color: #00D4AA; font-size: 12px;")
        header_layout.addWidget(status_label)
        card_layout.addLayout(header_layout)

        # 身份信息
        info_layout = QHBoxLayout()

        avatar_label = QLabel("🌳")
        avatar_label.setStyleSheet("font-size: 48px;")
        info_layout.addWidget(avatar_label)

        info_v_layout = QVBoxLayout()
        info_v_layout.setSpacing(8)

        identity_id = QLabel(f"身份ID: {self.user_info.get('identity_id', '未设置')}")
        identity_id.setStyleSheet("color: #FFFFFF; font-size: 14px;")
        info_v_layout.addWidget(identity_id)

        identity_address = QLabel(f"地址: {self.user_info.get('address', '0x...')[:20]}...")
        identity_address.setStyleSheet("color: #888888; font-size: 12px;")
        info_v_layout.addWidget(identity_address)

        info_layout.addLayout(info_v_layout)
        card_layout.addLayout(info_layout)

        # 助记词按钮
        mnemonic_btn = QPushButton("🔑 查看助记词")
        mnemonic_btn.setStyleSheet("""
            QPushButton {
                background: #333333;
                color: #FFFFFF;
                padding: 8px 16px;
                border-radius: 8px;
            }
            QPushButton:hover {
                background: #444444;
            }
        """)
        card_layout.addWidget(mnemonic_btn)

        layout.addWidget(identity_card)

        # 身份操作
        action_group = QGroupBox("身份操作")
        action_layout = QVBoxLayout(action_group)
        action_layout.setSpacing(12)

        create_btn = QPushButton("➕ 创建新身份")
        create_btn.setStyleSheet("""
            QPushButton {
                background: #00D4AA;
                color: #0D0D0D;
                font-weight: bold;
                padding: 12px;
                border-radius: 8px;
            }
            QPushButton:hover {
                background: #00E8BB;
            }
        """)
        action_layout.addWidget(create_btn)

        recover_btn = QPushButton("🔄 通过助记词恢复")
        recover_btn.setStyleSheet("""
            QPushButton {
                background: #333333;
                color: #FFFFFF;
                padding: 12px;
                border-radius: 8px;
            }
            QPushButton:hover {
                background: #444444;
            }
        """)
        action_layout.addWidget(recover_btn)

        export_btn = QPushButton("📤 导出身份")
        export_btn.setStyleSheet("""
            QPushButton {
                background: #333333;
                color: #FFFFFF;
                padding: 12px;
                border-radius: 8px;
            }
            QPushButton:hover {
                background: #444444;
            }
        """)
        action_layout.addWidget(export_btn)

        layout.addWidget(action_group)
        layout.addStretch()

        return widget

    def _create_credit_tab(self) -> QWidget:
        """积分"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(16)

        # 积分概览卡片
        credit_card = QFrame()
        credit_card.setStyleSheet("""
            QFrame {
                background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                border-radius: 12px;
                padding: 20px;
                border: 1px solid #333333;
            }
        """)
        credit_layout = QVBoxLayout(credit_card)
        credit_layout.setSpacing(16)

        # 标题
        header_layout = QHBoxLayout()
        title = QLabel("💰 积分余额")
        title.setStyleSheet("color: #FFFFFF; font-size: 18px; font-weight: bold;")
        header_layout.addWidget(title)

        refresh_btn = QPushButton("🔄")
        refresh_btn.setFixedSize(32, 32)
        refresh_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                font-size: 16px;
            }
            QPushButton:hover {
                background: #333333;
                border-radius: 16px;
            }
        """)
        header_layout.addWidget(refresh_btn)
        credit_layout.addLayout(header_layout)

        # 余额
        balance_layout = QHBoxLayout()
        balance_layout.setSpacing(16)

        self.balance_label = QLabel(str(self.user_info.get("credit_balance", 0)))
        self.balance_label.setStyleSheet("""
            color: #00D4AA;
            font-size: 36px;
            font-weight: bold;
        """)
        balance_layout.addWidget(self.balance_label)

        unit_label = QLabel("积分")
        unit_label.setStyleSheet("color: #888888; font-size: 16px;")
        balance_layout.addWidget(unit_label)

        balance_layout.addStretch()
        credit_layout.addLayout(balance_layout)

        # 统计信息
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(24)

        earned_label = QLabel(f"总收入: {self.user_info.get('credit_earned', 0)}")
        earned_label.setStyleSheet("color: #A0A0A0; font-size: 13px;")
        stats_layout.addWidget(earned_label)

        spent_label = QLabel(f"总支出: {self.user_info.get('credit_spent', 0)}")
        spent_label.setStyleSheet("color: #A0A0A0; font-size: 13px;")
        stats_layout.addWidget(spent_label)

        stats_layout.addStretch()
        credit_layout.addLayout(stats_layout)

        layout.addWidget(credit_card)

        # 快速充值
        charge_group = QGroupBox("💎 快速充值")
        charge_layout = QHBoxLayout(charge_group)
        charge_layout.setSpacing(12)

        charge_amounts = [100, 500, 1000, 5000]
        for amount in charge_amounts:
            btn = QPushButton(f"{amount} 积分")
            btn.setStyleSheet("""
                QPushButton {
                    background: #333333;
                    color: #FFFFFF;
                    padding: 10px 16px;
                    border-radius: 8px;
                }
                QPushButton:hover {
                    background: #00D4AA;
                    color: #0D0D0D;
                }
            """)
            charge_layout.addWidget(btn)

        charge_layout.addStretch()
        layout.addWidget(charge_group)

        # 积分记录
        history_group = QGroupBox("📜 最近记录")
        history_layout = QVBoxLayout(history_group)

        # 模拟记录
        records = [
            ("🎓 完成专家训练", "+50", "今天"),
            ("📝 生成文档", "-20", "昨天"),
            ("🔍 深度搜索", "-10", "昨天"),
        ]

        for action, amount, time in records:
            record_layout = QHBoxLayout()
            record_layout.setSpacing(12)

            action_label = QLabel(action)
            action_label.setStyleSheet("color: #FFFFFF; font-size: 13px;")
            record_layout.addWidget(action_label)

            amount_label = QLabel(amount)
            is_plus = amount.startswith("+")
            amount_label.setStyleSheet(f"color: {'#00D4AA' if is_plus else '#FF5252'}; font-size: 13px; font-weight: bold;")
            record_layout.addWidget(amount_label)

            time_label = QLabel(time)
            time_label.setStyleSheet("color: #666666; font-size: 12px;")
            record_layout.addWidget(time_label)

            history_layout.addLayout(record_layout)

        layout.addWidget(history_group, 1)

        return widget

    def _create_workspace_tab(self) -> QWidget:
        """工作空间"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(16)

        path_layout = QHBoxLayout()
        path_layout.setSpacing(12)

        self.workspace_path = QLineEdit()
        self.workspace_path.setText(self.user_info.get("workspace", ""))
        self.workspace_path.setPlaceholderText("选择工作空间文件夹...")
        self._style_input(self.workspace_path)
        path_layout.addWidget(self.workspace_path, 1)

        browse_btn = QPushButton("📂 浏览")
        browse_btn.setFixedWidth(80)
        browse_btn.clicked.connect(self._browse_workspace)
        path_layout.addWidget(browse_btn)

        layout.addLayout(path_layout)

        self.auto_open = QCheckBox("开机自动打开工作空间")
        self.auto_open.setChecked(self.user_info.get("auto_open", False))
        self._style_checkbox(self.auto_open)
        layout.addWidget(self.auto_open)

        layout.addStretch()

        return widget

    def _create_notification_tab(self) -> QWidget:
        """通知设置"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        self.notify_msg = QCheckBox("新消息通知")
        self.notify_msg.setChecked(self.user_info.get("notify_msg", True))
        self._style_checkbox(self.notify_msg)
        layout.addWidget(self.notify_msg)

        self.notify_complete = QCheckBox("任务完成提醒")
        self.notify_complete.setChecked(self.user_info.get("notify_complete", True))
        self._style_checkbox(self.notify_complete)
        layout.addWidget(self.notify_complete)

        self.notify_credit = QCheckBox("积分变动通知")
        self.notify_credit.setChecked(self.user_info.get("notify_credit", True))
        self._style_checkbox(self.notify_credit)
        layout.addWidget(self.notify_credit)

        layout.addStretch()

        return widget

    def _browse_workspace(self):
        folder = QFileDialog.getExistingDirectory(self, "选择工作空间", "")
        if folder:
            self.workspace_path.setText(folder)

    def _style_input(self, widget: QLineEdit):
        widget.setStyleSheet("""
            QLineEdit {
                background: #252525;
                border: none;
                border-radius: 6px;
                padding: 8px 12px;
                color: #FFFFFF;
                font-size: 13px;
            }
        """)

    def _style_checkbox(self, widget: QCheckBox):
        widget.setStyleSheet("""
            QCheckBox {
                color: #FFFFFF;
                font-size: 13px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 2px solid #666666;
                background: #252525;
            }
            QCheckBox::indicator:checked {
                border-color: #00D4AA;
                background: #00D4AA;
            }
        """)

    def _on_save(self):
        settings = {
            "username": self.username.text(),
            "email": self.email.text(),
            "signature": self.signature.text(),
            "workspace": self.workspace_path.text(),
            "auto_open": self.auto_open.isChecked(),
            "notify_msg": self.notify_msg.isChecked(),
            "notify_complete": self.notify_complete.isChecked(),
            "notify_credit": self.notify_credit.isChecked(),
        }
        self.settings_saved.emit(settings)
        self.accept()


class SystemSettingsDialog(QDialog):
    """
    系统设置对话框

    集成 AgentChat 配置：
    - L0/L3/L4 模型配置
    - 远程连接设置
    - 增强模式配置
    """

    settings_saved = pyqtSignal(dict)

    # 可用模型列表
    L0_MODELS = [
        ("qwen2.5:0.5b", "Qwen2.5 0.5B (快速路由)"),
        ("smollm2:latest", "SmolLM2 (备用轻量)"),
        ("gemma4:26b", "Gemma 4 26B (高性能)"),
    ]

    L3_MODELS = [
        ("qwen3.5:0.8b", "Qwen3.5 0.8B (轻量推理)"),
        ("qwen3.5:2b", "Qwen3.5 2B (均衡)"),
        ("qwen3.5:4b", "Qwen3.5 4B (推理优化)"),
    ]

    L4_MODELS = [
        ("qwen3.5:4b", "Qwen3.5 4B (均衡生成)"),
        ("qwen3.5:9b", "Qwen3.5 9B (深度生成)"),
        ("deepseek-r1:70b", "DeepSeek R1 70B (最强推理)"),
    ]

    def __init__(self, current_settings: dict = None, parent=None):
        super().__init__(parent)
        self.current_settings = current_settings or self._default_settings()
        self._setup_ui()

    def _default_settings(self) -> dict:
        return {
            # 模型配置
            "l0_model": "qwen2.5:0.5b",
            "l3_model": "qwen3.5:4b",
            "l4_model": "qwen3.5:9b",
            # 连接配置
            "remote_url": "http://www.mogoo.com.cn:8899/v1",
            "api_key": "",
            "connection_timeout": 30,
            # 界面配置
            "theme": "dark",
            "language": "zh-CN",
            "font_size": 14,
            "streaming_enabled": True,
            # 性能配置
            "gpu_enabled": False,
            "context_limit": 4096,
            # 增强模式
            "enhancement_enabled": True,
            "tts_enabled": False,
        }

    def _setup_ui(self):
        self.setWindowTitle("⚙️ 系统设置")
        self.setMinimumSize(600, 520)
        self.setStyleSheet("""
            QDialog {
                background: #1A1A1A;
            }
            QLabel {
                color: #FFFFFF;
                font-size: 13px;
            }
            QGroupBox {
                color: #A0A0A0;
                border: 1px solid #333333;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px;
            }
            QPushButton {
                background: #00D4AA;
                border: none;
                border-radius: 8px;
                color: #0D0D0D;
                font-size: 14px;
                font-weight: bold;
                padding: 8px 24px;
            }
            QPushButton:hover {
                background: #00E8BB;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #333333;
                border-radius: 8px;
                padding: 16px;
                background: #0D0D0D;
            }
            QTabBar::tab {
                background: #252525;
                color: #A0A0A0;
                padding: 8px 16px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }
            QTabBar::tab:selected {
                background: #00D4AA;
                color: #0D0D0D;
            }
        """)

        tabs.addTab(self._create_model_tab(), "🤖 AI模型")
        tabs.addTab(self._create_connection_tab(), "🔌 连接")
        tabs.addTab(self._create_ui_tab(), "🎨 界面")
        tabs.addTab(self._create_enhancement_tab(), "✨ 增强模式")

        layout.addWidget(tabs, 1)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.setStyleSheet("""
            QPushButton {
                background: #333333;
                color: #FFFFFF;
            }
            QPushButton:hover {
                background: #444444;
            }
        """)
        cancel_btn.clicked.connect(self.reject)

        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self._on_save)

        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

    def _create_model_tab(self) -> QWidget:
        """AI模型配置"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(16)

        # 模型层级说明
        info_label = QLabel(
            "🌳 LivingTreeAI 采用分层模型架构：\n"
            "• L0 路由模型：快速意图分类和路由（0.5B 轻量模型）\n"
            "• L3 推理模型：深度推理和意图理解（4B 思考模型）\n"
            "• L4 生成模型：高质量内容生成（9B+ 大模型）"
        )
        info_label.setStyleSheet("""
            color: #A0A0A0;
            font-size: 12px;
            background: #252525;
            border-radius: 8px;
            padding: 12px;
        """)
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # L0 路由模型
        l0_group = QGroupBox("L0 路由模型（快速路由）")
        l0_layout = QVBoxLayout(l0_group)

        l0_desc = QLabel("用于意图分类和任务路由，选择最快的模型")
        l0_desc.setStyleSheet("color: #666666; font-size: 11px; margin-bottom: 8px;")
        l0_layout.addWidget(l0_desc)

        self.l0_combo = QComboBox()
        for model_id, model_name in self.L0_MODELS:
            self.l0_combo.addItem(model_name, model_id)
        self._set_combo_by_data(self.l0_combo, self.current_settings.get("l0_model", "qwen2.5:0.5b"))
        self._style_combo(self.l0_combo)
        l0_layout.addWidget(self.l0_combo)
        layout.addWidget(l0_group)

        # L3 推理模型
        l3_group = QGroupBox("L3 推理模型（深度理解）")
        l3_layout = QVBoxLayout(l3_group)

        l3_desc = QLabel("用于深度推理、意图理解和复杂分析")
        l3_desc.setStyleSheet("color: #666666; font-size: 11px; margin-bottom: 8px;")
        l3_layout.addWidget(l3_desc)

        self.l3_combo = QComboBox()
        for model_id, model_name in self.L3_MODELS:
            self.l3_combo.addItem(model_name, model_id)
        self._set_combo_by_data(self.l3_combo, self.current_settings.get("l3_model", "qwen3.5:4b"))
        self._style_combo(self.l3_combo)
        l3_layout.addWidget(self.l3_combo)
        layout.addWidget(l3_group)

        # L4 生成模型
        l4_group = QGroupBox("L4 生成模型（高质量输出）")
        l4_layout = QVBoxLayout(l4_group)

        l4_desc = QLabel("用于高质量内容生成、深度搜索和专家训练")
        l4_desc.setStyleSheet("color: #666666; font-size: 11px; margin-bottom: 8px;")
        l4_layout.addWidget(l4_desc)

        self.l4_combo = QComboBox()
        for model_id, model_name in self.L4_MODELS:
            self.l4_combo.addItem(model_name, model_id)
        self._set_combo_by_data(self.l4_combo, self.current_settings.get("l4_model", "qwen3.5:9b"))
        self._style_combo(self.l4_combo)
        l4_layout.addWidget(self.l4_combo)
        layout.addWidget(l4_group)

        # 上下文限制
        ctx_group = QGroupBox("上下文限制")
        ctx_layout = QHBoxLayout(ctx_group)

        self.ctx_limit = QSpinBox()
        self.ctx_limit.setRange(1024, 128000)
        self.ctx_limit.setValue(self.current_settings.get("context_limit", 4096))
        self.ctx_limit.setSingleStep(1024)
        self.ctx_limit.setSuffix(" tokens")
        self.ctx_limit.setStyleSheet("""
            QSpinBox {
                background: #252525;
                border: none;
                border-radius: 6px;
                padding: 8px 12px;
                color: #FFFFFF;
            }
        """)
        ctx_layout.addWidget(self.ctx_limit)
        ctx_layout.addStretch()
        layout.addWidget(ctx_group)

        layout.addStretch()
        return widget

    def _set_combo_by_data(self, combo: QComboBox, data_value: str):
        """根据数据值设置 ComboBox 当前项"""
        for i in range(combo.count()):
            if combo.itemData(i) == data_value:
                combo.setCurrentIndex(i)
                return

    def _create_connection_tab(self) -> QWidget:
        """连接配置"""
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setSpacing(16)

        # 远程地址
        self.remote_url = QLineEdit()
        self.remote_url.setText(self.current_settings.get("remote_url", ""))
        self.remote_url.setPlaceholderText("http://www.mogoo.com.cn:8899/v1")
        self._style_input(self.remote_url)
        layout.addRow("Ollama 远程地址:", self.remote_url)

        # API Key
        self.api_key = QLineEdit()
        self.api_key.setText(self.current_settings.get("api_key", ""))
        self.api_key.setPlaceholderText("（如需要）")
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._style_input(self.api_key)
        layout.addRow("API Key:", self.api_key)

        # 连接超时
        self.timeout = QSpinBox()
        self.timeout.setRange(5, 120)
        self.timeout.setValue(self.current_settings.get("connection_timeout", 30))
        self.timeout.setSuffix(" 秒")
        self.timeout.setStyleSheet("""
            QSpinBox {
                background: #252525;
                border: none;
                border-radius: 6px;
                padding: 8px 12px;
                color: #FFFFFF;
            }
        """)
        layout.addRow("连接超时:", self.timeout)

        # 连接测试按钮
        test_btn = QPushButton("🔗 测试连接")
        test_btn.setStyleSheet("""
            QPushButton {
                background: #333333;
                color: #FFFFFF;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background: #00D4AA;
                color: #0D0D0D;
            }
        """)
        test_btn.clicked.connect(self._test_connection)
        layout.addRow("", test_btn)

        # 连接状态
        self.connection_status = QLabel("未测试")
        self.connection_status.setStyleSheet("color: #666666; font-size: 12px;")
        layout.addRow("状态:", self.connection_status)

        return widget

    def _test_connection(self):
        """测试连接"""
        url = self.remote_url.text().strip()
        if not url:
            self.connection_status.setText("请输入远程地址")
            self.connection_status.setStyleSheet("color: #FF5252; font-size: 12px;")
            return

        self.connection_status.setText("测试中...")
        self.connection_status.setStyleSheet("color: #FFD700; font-size: 12px;")

        # 异步测试连接
        QTimer.singleShot(100, lambda: self._do_test_connection(url))

    def _do_test_connection(self, url: str):
        """执行连接测试"""
        import urllib.request
        import json

        try:
            req = urllib.request.Request(
                f"{url.rstrip('/v1')}/api/tags",
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                models = data.get("models", [])
                model_names = [m.get("name", "unknown") for m in models[:5]]
                self.connection_status.setText(f"✅ 连接成功\n可用模型: {', '.join(model_names)}")
                self.connection_status.setStyleSheet("color: #00D4AA; font-size: 12px;")
        except Exception as e:
            self.connection_status.setText(f"❌ 连接失败\n{str(e)[:50]}")
            self.connection_status.setStyleSheet("color: #FF5252; font-size: 12px;")

    def _create_ui_tab(self) -> QWidget:
        """界面配置"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(16)

        # 主题选择区域
        theme_group = QGroupBox("主题设置")
        theme_layout = QVBoxLayout(theme_group)
        theme_layout.setSpacing(12)

        # 主题预览卡片
        self.theme_btns = {}
        themes = [
            ("light", "浅色主题", "#FFFFFF", "#10B981", "清爽明亮，适合白天使用"),
            ("dark", "深色主题", "#0D0D0D", "#10B981", "酷炫深色，减少眼睛疲劳"),
            ("blue", "蓝色主题", "#FFFFFF", "#3B82F6", "科技感强，专业风格"),
        ]

        current_theme = self.current_settings.get("theme", "light")

        for theme_id, theme_name, bg, accent, desc in themes:
            card = QWidget()
            card_layout = QHBoxLayout(card)
            card_layout.setContentsMargins(12, 8, 12, 8)
            card_layout.setSpacing(16)

            # 预览色块
            preview = QLabel()
            preview.setFixedSize(48, 32)
            preview.setStyleSheet(f"""
                background: {bg};
                border: 2px solid {accent};
                border-radius: 6px;
            """)
            card_layout.addWidget(preview)

            # 主题信息
            info_layout = QVBoxLayout()
            name_label = QLabel(theme_name)
            name_label.setStyleSheet("color: #FFFFFF; font-size: 14px; font-weight: bold;")
            info_layout.addWidget(name_label)

            desc_label = QLabel(desc)
            desc_label.setStyleSheet("color: #888888; font-size: 12px;")
            info_layout.addWidget(desc_label)
            card_layout.addLayout(info_layout, 1)

            # 选择按钮
            btn = QPushButton("使用" if theme_id != current_theme else "使用中")
            btn.setCheckable(True)
            btn.setChecked(theme_id == current_theme)
            btn.setFixedSize(80, 32)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {'#333333' if theme_id != current_theme else accent};
                    color: {'#FFFFFF' if theme_id != current_theme else '#0D0D0D'};
                    border: none;
                    border-radius: 6px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background: {accent};
                    color: #0D0D0D;
                }}
                QPushButton:checked {{
                    background: {accent};
                    color: #0D0D0D;
                }}
            """)
            btn.clicked.connect(lambda c, t=theme_id: self._select_theme(t))
            self.theme_btns[theme_id] = btn
            card_layout.addWidget(btn)

            theme_layout.addWidget(card)

        layout.addWidget(theme_group)

        # 保存当前选择
        self.selected_theme = current_theme

        # 语言设置
        lang_group = QGroupBox("语言设置")
        lang_layout = QFormLayout(lang_group)
        lang_layout.setSpacing(16)

        self.lang_combo = QComboBox()
        self.lang_combo.addItems(["中文", "English"])
        self.lang_combo.setCurrentText("中文" if "zh" in self.current_settings.get("language", "zh-CN") else "English")
        self._style_combo(self.lang_combo)
        lang_layout.addRow("界面语言:", self.lang_combo)

        layout.addWidget(lang_group)

        # 字体设置
        font_group = QGroupBox("字体设置")
        font_layout = QFormLayout(font_group)
        font_layout.setSpacing(16)

        self.font_size = QSpinBox()
        self.font_size.setRange(10, 20)
        self.font_size.setValue(self.current_settings.get("font_size", 14))
        self.font_size.setSuffix(" px")
        self.font_size.setStyleSheet("""
            QSpinBox {
                background: #252525;
                border: none;
                border-radius: 6px;
                padding: 6px 12px;
                color: #FFFFFF;
            }
        """)
        font_layout.addRow("字体大小:", self.font_size)

        layout.addWidget(font_group)
        layout.addStretch()

        return widget

    def _select_theme(self, theme_id: str):
        """选择主题"""
        self.selected_theme = theme_id

        # 更新按钮状态
        for tid, btn in self.theme_btns.items():
            is_selected = tid == theme_id
            btn.setText("使用中" if is_selected else "使用")
            accent = {"light": "#10B981", "dark": "#10B981", "blue": "#3B82F6"}.get(tid, "#10B981")
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {'#333333' if not is_selected else accent};
                    color: {'#FFFFFF' if not is_selected else '#0D0D0D'};
                    border: none;
                    border-radius: 6px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background: {accent};
                    color: #0D0D0D;
                }}
            """)

    def _create_enhancement_tab(self) -> QWidget:
        """增强模式配置"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(16)

        # 增强模式说明
        info_label = QLabel(
            "✨ 增强模式集成以下能力：\n"
            "• 16种意图识别：自动识别对话/推理/任务/创作/知识\n"
            "• Query压缩：智能压缩长查询，减少Token消耗\n"
            "• 上下文管理：自动管理对话历史和上下文\n"
            "• Expert Learning：专家指导和思维链蒸馏"
        )
        info_label.setStyleSheet("""
            color: #A0A0A0;
            font-size: 12px;
            background: #252525;
            border-radius: 8px;
            padding: 12px;
        """)
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # 增强模式开关
        enhancement_group = QGroupBox("增强模式")
        enhancement_layout = QVBoxLayout(enhancement_group)
        enhancement_layout.setSpacing(12)

        self.enhancement_enabled = QCheckBox("启用增强模式")
        self.enhancement_enabled.setChecked(self.current_settings.get("enhancement_enabled", True))
        self._style_checkbox(self.enhancement_enabled)
        enhancement_layout.addWidget(self.enhancement_enabled)

        enhancement_desc = QLabel("启用后将自动进行意图识别、Query压缩和上下文优化")
        enhancement_desc.setStyleSheet("color: #666666; font-size: 11px; margin-left: 28px;")
        enhancement_layout.addWidget(enhancement_desc)
        layout.addWidget(enhancement_group)

        # 流式输出
        streaming_group = QGroupBox("输出设置")
        streaming_layout = QVBoxLayout(streaming_group)
        streaming_layout.setSpacing(12)

        self.streaming_enabled = QCheckBox("启用流式输出")
        self.streaming_enabled.setChecked(self.current_settings.get("streaming_enabled", True))
        self._style_checkbox(self.streaming_enabled)
        streaming_layout.addWidget(self.streaming_enabled)

        streaming_desc = QLabel("打字机效果，边生成边显示响应")
        streaming_desc.setStyleSheet("color: #666666; font-size: 11px; margin-left: 28px;")
        streaming_layout.addWidget(streaming_desc)
        layout.addWidget(streaming_group)

        # TTS 设置
        tts_group = QGroupBox("语音输出 (TTS)")
        tts_layout = QVBoxLayout(tts_group)
        tts_layout.setSpacing(12)

        self.tts_enabled = QCheckBox("启用语音朗读")
        self.tts_enabled.setChecked(self.current_settings.get("tts_enabled", False))
        self._style_checkbox(self.tts_enabled)
        tts_layout.addWidget(self.tts_enabled)

        tts_desc = QLabel("Agent回复时自动语音朗读（使用Windows SAPI）")
        tts_desc.setStyleSheet("color: #666666; font-size: 11px; margin-left: 28px;")
        tts_layout.addWidget(tts_desc)
        layout.addWidget(tts_group)

        # GPU 加速
        gpu_group = QGroupBox("性能")
        gpu_layout = QVBoxLayout(gpu_group)
        gpu_layout.setSpacing(12)

        self.gpu_enabled = QCheckBox("启用GPU加速")
        self.gpu_enabled.setChecked(self.current_settings.get("gpu_enabled", False))
        self._style_checkbox(self.gpu_enabled)
        gpu_layout.addWidget(self.gpu_enabled)

        gpu_desc = QLabel("如本地有GPU可启用，提升推理速度")
        gpu_desc.setStyleSheet("color: #666666; font-size: 11px; margin-left: 28px;")
        gpu_layout.addWidget(gpu_desc)
        layout.addWidget(gpu_group)

        layout.addStretch()
        return widget

    def _style_input(self, widget: QLineEdit):
        widget.setStyleSheet("""
            QLineEdit {
                background: #252525;
                border: none;
                border-radius: 6px;
                padding: 8px 12px;
                color: #FFFFFF;
                font-size: 13px;
            }
        """)

    def _style_combo(self, widget: QComboBox):
        widget.setStyleSheet("""
            QComboBox {
                background: #252525;
                border: none;
                border-radius: 6px;
                padding: 8px 12px;
                color: #FFFFFF;
                font-size: 13px;
            }
            QComboBox::drop-down {
                border: none;
            }
        """)

    def _style_checkbox(self, widget: QCheckBox):
        widget.setStyleSheet("""
            QCheckBox {
                color: #FFFFFF;
                font-size: 13px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 2px solid #666666;
                background: #252525;
            }
            QCheckBox::indicator:checked {
                border-color: #00D4AA;
                background: #00D4AA;
            }
        """)

    def _on_save(self):
        settings = {
            # 模型配置
            "l0_model": self.l0_combo.currentData(),
            "l3_model": self.l3_combo.currentData(),
            "l4_model": self.l4_combo.currentData(),
            "context_limit": self.ctx_limit.value(),
            # 连接配置
            "remote_url": self.remote_url.text(),
            "api_key": self.api_key.text(),
            "connection_timeout": self.timeout.value(),
            # 界面配置
            "theme": self.selected_theme,
            "language": "zh-CN" if self.lang_combo.currentText() == "中文" else "en-US",
            "font_size": self.font_size.value(),
            "streaming_enabled": self.streaming_enabled.isChecked(),
            # 性能配置
            "gpu_enabled": self.gpu_enabled.isChecked(),
            # 增强模式
            "enhancement_enabled": self.enhancement_enabled.isChecked(),
            "tts_enabled": self.tts_enabled.isChecked(),
        }

        # 应用主题
        if theme_manager and "theme" in settings:
            theme_manager.set_theme(settings["theme"])

        self.settings_saved.emit(settings)
        self.accept()


__all__ = ["SystemSettingsDialog", "UserSettingsDialog"]
