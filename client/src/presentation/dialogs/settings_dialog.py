"""
用户设置和系统设置对话框
包含：用户设置（数字身份+积分）、系统设置
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QComboBox,
    QCheckBox, QGroupBox, QTabWidget, QSpinBox,
    QDialog, QFileDialog, QProgressBar,
)
from PyQt6.QtGui import QFont


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
    """系统设置对话框"""
    
    settings_saved = pyqtSignal(dict)
    
    def __init__(self, current_settings: dict = None, parent=None):
        super().__init__(parent)
        self.current_settings = current_settings or self._default_settings()
        self._setup_ui()
    
    def _default_settings(self) -> dict:
        return {
            "l0_model": "qwen2.5:0.5b",
            "l3_model": "qwen3.5:4b",
            "l4_model": "qwen3.5:9b",
            "remote_url": "http://www.mogoo.com.cn:8899/v1",
            "theme": "dark",
            "language": "zh-CN",
            "font_size": 14,
            "streaming_enabled": True,
            "gpu_enabled": False,
            "context_limit": 4096,
            "server_url": "http://localhost:8080",
            "api_key": "",
        }
    
    def _setup_ui(self):
        self.setWindowTitle("⚙️ 系统设置")
        self.setMinimumSize(550, 480)
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
        tabs.addTab(self._create_ui_tab(), "🎨 界面")
        tabs.addTab(self._create_performance_tab(), "⚡ 性能")
        tabs.addTab(self._create_connection_tab(), "🔌 连接")
        
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
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setSpacing(16)
        
        self.l0_combo = QComboBox()
        self.l0_combo.addItems(["qwen2.5:0.5b", "smollm2:latest", "gemma4:26b"])
        self.l0_combo.setCurrentText(self.current_settings.get("l0_model", "qwen2.5:0.5b"))
        self._style_combo(self.l0_combo)
        layout.addRow("L0 路由模型:", self.l0_combo)
        
        self.l3_combo = QComboBox()
        self.l3_combo.addItems(["qwen3.5:4b", "qwen3.5:2b", "qwen3.5:0.8b"])
        self.l3_combo.setCurrentText(self.current_settings.get("l3_model", "qwen3.5:4b"))
        self._style_combo(self.l3_combo)
        layout.addRow("L3 推理模型:", self.l3_combo)
        
        self.l4_combo = QComboBox()
        self.l4_combo.addItems(["qwen3.5:9b", "qwen3.5:4b", "deepseek-r1:70b"])
        self.l4_combo.setCurrentText(self.current_settings.get("l4_model", "qwen3.5:9b"))
        self._style_combo(self.l4_combo)
        layout.addRow("L4 生成模型:", self.l4_combo)
        
        self.remote_url = QLineEdit()
        self.remote_url.setText(self.current_settings.get("remote_url", ""))
        self.remote_url.setPlaceholderText("http://localhost:11434")
        self._style_input(self.remote_url)
        layout.addRow("远程地址:", self.remote_url)
        
        return widget
    
    def _create_ui_tab(self) -> QWidget:
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setSpacing(16)
        
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["深色", "浅色", "跟随系统"])
        themes = {"dark": "深色", "light": "浅色", "system": "跟随系统"}
        self.theme_combo.setCurrentText(themes.get(self.current_settings.get("theme", "dark"), "深色"))
        self._style_combo(self.theme_combo)
        layout.addRow("主题:", self.theme_combo)
        
        self.lang_combo = QComboBox()
        self.lang_combo.addItems(["中文", "English"])
        self.lang_combo.setCurrentText("中文" if "zh" in self.current_settings.get("language", "zh-CN") else "English")
        self._style_combo(self.lang_combo)
        layout.addRow("语言:", self.lang_combo)
        
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
        layout.addRow("字体大小:", self.font_size)
        
        return widget
    
    def _create_performance_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(16)
        
        self.streaming_cb = QCheckBox("启用流式输出")
        self.streaming_cb.setChecked(self.current_settings.get("streaming_enabled", True))
        self._style_checkbox(self.streaming_cb)
        layout.addWidget(self.streaming_cb)
        
        self.gpu_cb = QCheckBox("启用GPU加速")
        self.gpu_cb.setChecked(self.current_settings.get("gpu_enabled", False))
        self._style_checkbox(self.gpu_cb)
        layout.addWidget(self.gpu_cb)
        
        ctx_layout = QHBoxLayout()
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
                padding: 6px 12px;
                color: #FFFFFF;
            }
        """)
        ctx_layout.addWidget(self.ctx_limit)
        ctx_layout.addStretch()
        layout.addLayout(ctx_layout)
        
        layout.addStretch()
        return widget
    
    def _create_connection_tab(self) -> QWidget:
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setSpacing(16)
        
        self.server_url = QLineEdit()
        self.server_url.setText(self.current_settings.get("server_url", ""))
        self.server_url.setPlaceholderText("http://localhost:8080")
        self._style_input(self.server_url)
        layout.addRow("服务器:", self.server_url)
        
        self.api_key = QLineEdit()
        self.api_key.setText(self.current_settings.get("api_key", ""))
        self.api_key.setPlaceholderText("•••••••••••••••")
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._style_input(self.api_key)
        layout.addRow("API Key:", self.api_key)
        
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
            "l0_model": self.l0_combo.currentText(),
            "l3_model": self.l3_combo.currentText(),
            "l4_model": self.l4_combo.currentText(),
            "remote_url": self.remote_url.text(),
            "theme": {"深色": "dark", "浅色": "light", "跟随系统": "system"}.get(self.theme_combo.currentText(), "dark"),
            "language": "zh-CN" if self.lang_combo.currentText() == "中文" else "en-US",
            "font_size": self.font_size.value(),
            "streaming_enabled": self.streaming_cb.isChecked(),
            "gpu_enabled": self.gpu_cb.isChecked(),
            "context_limit": self.ctx_limit.value(),
            "server_url": self.server_url.text(),
            "api_key": self.api_key.text(),
        }
        self.settings_saved.emit(settings)
        self.accept()


__all__ = ["SystemSettingsDialog", "UserSettingsDialog"]
