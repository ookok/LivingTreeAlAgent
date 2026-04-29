"""
邮件提醒面板 UI
================

邮件提醒系统的 PyQt6 图形界面。
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QListWidget, QListWidgetItem, QLabel, QLineEdit,
    QComboBox, QCheckBox, QSpinBox, QGroupBox,
    QFormLayout, QTabWidget, QTextEdit, QProgressBar,
    QStatusBar, QMessageBox, QDialog, QDialogButtonBox,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, pyqtSlot, QTimer
from PyQt6.QtGui import QFont, QIcon
import logging

logger = logging.getLogger(__name__)


class EmailAccountDialog(QDialog):
    """
    邮箱账户配置对话框

    用于添加/编辑邮箱账户。
    """

    def __init__(self, account=None, parent=None):
        super().__init__(parent)
        self.account = account
        self.setup_ui()
        if account:
            self.load_account(account)

    def setup_ui(self):
        """设置UI"""
        self.setWindowTitle("邮箱账户配置")
        self.setMinimumWidth(500)
        self.setModal(True)

        layout = QVBoxLayout(self)

        # 基本信息
        basic_group = QGroupBox("基本信息")
        basic_layout = QFormLayout()

        self.email_edit = QLineEdit()
        self.email_edit.setPlaceholderText("your@email.com")
        basic_layout.addRow("邮箱地址:", self.email_edit)

        self.display_name_edit = QLineEdit()
        basic_layout.addRow("显示名称:", self.display_name_edit)

        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["QQ邮箱", "163邮箱", "126邮箱", "Gmail", "Outlook", "自定义"])
        self.provider_combo.currentIndexChanged.connect(self.on_provider_changed)
        basic_layout.addRow("邮件服务商:", self.provider_combo)

        basic_group.setLayout(basic_layout)
        layout.addWidget(basic_group)

        # 服务器配置
        server_group = QGroupBox("服务器配置")
        server_layout = QFormLayout()

        self.imap_host_edit = QLineEdit()
        self.imap_host_edit.setPlaceholderText("imap.example.com")
        server_layout.addRow("IMAP服务器:", self.imap_host_edit)

        self.imap_port_spin = QSpinBox()
        self.imap_port_spin.setRange(1, 65535)
        self.imap_port_spin.setValue(993)
        server_layout.addRow("IMAP端口:", self.imap_port_spin)

        self.ssl_check = QCheckBox()
        self.ssl_check.setChecked(True)
        server_layout.addRow("使用SSL:", self.ssl_check)

        self.auth_code_edit = QLineEdit()
        self.auth_code_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.auth_code_edit.setPlaceholderText("授权码/密码")
        server_layout.addRow("授权码:", self.auth_code_edit)

        server_group.setLayout(server_layout)
        layout.addWidget(server_group)

        # 通知设置
        notify_group = QGroupBox("通知设置")
        notify_layout = QFormLayout()

        self.notify_enabled_check = QCheckBox()
        self.notify_enabled_check.setChecked(True)
        notify_layout.addRow("启用通知:", self.notify_enabled_check)

        self.notify_sound_check = QCheckBox()
        self.notify_sound_check.setChecked(True)
        notify_layout.addRow("播放声音:", self.notify_sound_check)

        self.max_preview_spin = QSpinBox()
        self.max_preview_spin.setRange(50, 500)
        self.max_preview_spin.setValue(100)
        self.max_preview_spin.setSuffix(" 字符")
        notify_layout.addRow("预览长度:", self.max_preview_spin)

        notify_group.setLayout(notify_layout)
        layout.addWidget(notify_group)

        # 过滤规则
        filter_group = QGroupBox("过滤规则")
        filter_layout = QVBoxLayout()

        filter_layout.addWidget(QLabel("只提醒以下发件人 (留空=全部):"))
        self.filter_senders_edit = QLineEdit()
        self.filter_senders_edit.setPlaceholderText("用逗号分隔，多个发件人")
        filter_layout.addWidget(self.filter_senders_edit)

        filter_layout.addWidget(QLabel("屏蔽以下发件人:"))
        self.block_senders_edit = QLineEdit()
        self.block_senders_edit.setPlaceholderText("用逗号分隔")
        filter_layout.addWidget(self.block_senders_edit)

        filter_layout.addWidget(QLabel("关键词过滤 (满足任一即提醒):"))
        self.keywords_edit = QLineEdit()
        self.keywords_edit.setPlaceholderText("用逗号分隔")
        filter_layout.addWidget(self.keywords_edit)

        filter_group.setLayout(filter_layout)
        layout.addWidget(filter_group)

        # 按钮
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def on_provider_changed(self, index):
        """服务商变更"""
        providers = {
            0: ("imap.qq.com", 993, "smtp.qq.com", 465),
            1: ("imap.163.com", 993, "smtp.163.com", 465),
            2: ("imap.126.com", 993, "smtp.126.com", 465),
            3: ("imap.gmail.com", 993, "smtp.gmail.com", 465),
            4: ("smtp.office365.com", 993, "smtp.office365.com", 587),
        }

        if index in providers:
            imap_host, imap_port, smtp_host, smtp_port = providers[index]
            self.imap_host_edit.setText(imap_host)
            self.imap_port_spin.setValue(imap_port)

    def load_account(self, account):
        """加载账户数据"""
        from core.email_notification import EmailProvider

        self.email_edit.setText(account.email)
        self.display_name_edit.setText(account.display_name)

        # 设置服务商
        provider_map = {
            EmailProvider.QQ: 0,
            EmailProvider.Netease163: 1,
            EmailProvider.Netease126: 2,
            EmailProvider.Gmail: 3,
            EmailProvider.Outlook: 4,
            EmailProvider.CUSTOM: 5,
        }
        self.provider_combo.setCurrentIndex(provider_map.get(account.provider, 5))

        self.imap_host_edit.setText(account.imap_host)
        self.imap_port_spin.setValue(account.imap_port)
        self.ssl_check.setChecked(account.use_ssl)
        self.auth_code_edit.setText(account.auth_code)

        self.notify_enabled_check.setChecked(account.notify_enabled)
        self.notify_sound_check.setChecked(account.notify_sound)
        self.max_preview_spin.setValue(account.max_preview_length)

        self.filter_senders_edit.setText(", ".join(account.filter_senders))
        self.block_senders_edit.setText(", ".join(account.block_senders))
        self.keywords_edit.setText(", ".join(account.keywords))

    def get_account_data(self) -> dict:
        """获取账户数据"""
        from core.email_notification import EmailProvider

        providers = [
            EmailProvider.QQ,
            EmailProvider.Netease163,
            EmailProvider.Netease126,
            EmailProvider.Gmail,
            EmailProvider.Outlook,
            EmailProvider.CUSTOM,
        ]

        def parse_list(text: str) -> list:
            return [s.strip() for s in text.split(",") if s.strip()]

        return {
            "email": self.email_edit.text().strip(),
            "display_name": self.display_name_edit.text().strip(),
            "provider": providers[self.provider_combo.currentIndex()],
            "imap_host": self.imap_host_edit.text().strip(),
            "imap_port": self.imap_port_spin.value(),
            "use_ssl": self.ssl_check.isChecked(),
            "username": self.email_edit.text().strip(),
            "auth_code": self.auth_code_edit.text(),
            "notify_enabled": self.notify_enabled_check.isChecked(),
            "notify_sound": self.notify_sound_check.isChecked(),
            "max_preview_length": self.max_preview_spin.value(),
            "filter_senders": parse_list(self.filter_senders_edit.text()),
            "block_senders": parse_list(self.block_senders_edit.text()),
            "keywords": parse_list(self.keywords_edit.text()),
        }


class TestConnectionWorker(QThread):
    """测试连接线程"""
    finished = pyqtSignal(bool, str)
    progress = pyqtSignal(str)

    def __init__(self, account_data):
        super().__init__()
        self.account_data = account_data

    def run(self):
        from core.email_notification import EmailAccount, IMAPListener

        self.progress.emit("正在连接服务器...")

        account = EmailAccount(
            account_id="test",
            email=self.account_data["email"],
            imap_host=self.account_data["imap_host"],
            imap_port=self.account_data["imap_port"],
            use_ssl=self.account_data["use_ssl"],
            username=self.account_data["username"],
            auth_code=self.account_data["auth_code"],
        )

        listener = IMAPListener(account)
        success, message = listener.test_connection()

        self.finished.emit(success, message)


class EmailNotificationPanel(QWidget):
    """
    邮件提醒面板

    主面板，用于管理邮箱账户和查看通知。
    """

    # 信号
    new_email_signal = pyqtSignal(object)  # 新邮件信号

    def __init__(self, parent=None):
        super().__init__(parent)
        self._listener_manager = None
        self._config_manager = None
        self._notification_service = None
        self._tray_manager = None
        self._test_worker = None
        self.setup_ui()
        self.load_accounts()

    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)

        # 标题栏
        title_layout = QHBoxLayout()
        title = QLabel("📧 邮件提醒")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        title_layout.addWidget(title)
        title_layout.addStretch()

        # 免打扰按钮
        self.dnd_btn = QPushButton("🔕 免打扰")
        self.dnd_btn.setCheckable(True)
        self.dnd_btn.clicked.connect(self.toggle_dnd)
        title_layout.addWidget(self.dnd_btn)

        layout.addLayout(title_layout)

        # 标签页
        tabs = QTabWidget()

        # 账户管理标签页
        tabs.addTab(self._create_accounts_tab(), "📮 账户管理")

        # 通知历史标签页
        tabs.addTab(self._create_history_tab(), "📜 通知历史")

        # 设置标签页
        tabs.addTab(self._create_settings_tab(), "⚙️ 设置")

        layout.addWidget(tabs)

        # 状态栏
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("就绪")
        layout.addWidget(self.status_bar)

    def _create_accounts_tab(self) -> QWidget:
        """创建账户管理标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 账户列表
        self.account_list = QListWidget()
        self.account_list.itemClicked.connect(self.on_account_selected)
        layout.addWidget(self.account_list)

        # 操作按钮
        btn_layout = QHBoxLayout()

        add_btn = QPushButton("➕ 添加账户")
        add_btn.clicked.connect(self.add_account)
        btn_layout.addWidget(add_btn)

        edit_btn = QPushButton("✏️ 编辑")
        edit_btn.clicked.connect(self.edit_account)
        btn_layout.addWidget(edit_btn)

        remove_btn = QPushButton("🗑️ 删除")
        remove_btn.clicked.connect(self.remove_account)
        btn_layout.addWidget(remove_btn)

        btn_layout.addStretch()

        layout.addLayout(btn_layout)

        # 测试连接区域
        test_layout = QHBoxLayout()
        test_layout.addWidget(QLabel("测试连接:"))
        self.test_status = QLabel("")
        test_layout.addWidget(self.test_status)
        test_layout.addStretch()
        layout.addLayout(test_layout)

        return widget

    def _create_history_tab(self) -> QWidget:
        """创建通知历史标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 历史列表
        self.history_list = QListWidget()
        layout.addWidget(self.history_list)

        # 按钮
        btn_layout = QHBoxLayout()
        clear_btn = QPushButton("🗑️ 清空历史")
        clear_btn.clicked.connect(self.clear_history)
        btn_layout.addWidget(clear_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        return widget

    def _create_settings_tab(self) -> QWidget:
        """创建设置标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 全局设置
        global_group = QGroupBox("全局设置")
        global_layout = QFormLayout()

        self.global_notify_check = QCheckBox()
        self.global_notify_check.setChecked(True)
        global_layout.addRow("启用桌面通知:", self.global_notify_check)

        self.global_sound_check = QCheckBox()
        self.global_sound_check.setChecked(True)
        global_layout.addRow("播放提示音:", self.global_sound_check)

        self.global_startup_check = QCheckBox()
        global_layout.addRow("开机启动:", self.global_startup_check)

        global_group.setLayout(global_layout)
        layout.addWidget(global_group)

        # 托盘设置
        tray_group = QGroupBox("托盘设置")
        tray_layout = QFormLayout()

        self.minimize_to_tray_check = QCheckBox()
        self.minimize_to_tray_check.setChecked(True)
        tray_layout.addRow("最小化到托盘:", self.minimize_to_tray_check)

        self.close_to_tray_check = QCheckBox()
        tray_layout.addRow("关闭到托盘:", self.close_to_tray_check)

        tray_group.setLayout(tray_layout)
        layout.addWidget(tray_group)

        layout.addStretch()

        return widget

    def load_accounts(self):
        """加载账户"""
        try:
            from core.email_notification import get_config_manager
            self._config_manager = get_config_manager()
            self.refresh_account_list()
            self.update_status(f"已加载 {len(self._config_manager.get_accounts())} 个账户")
        except Exception as e:
            logger.error(f"Failed to load accounts: {e}")

    def refresh_account_list(self):
        """刷新账户列表"""
        self.account_list.clear()
        if not self._config_manager:
            return

        for account in self._config_manager.get_accounts():
            status = "🟢" if account.is_active else "⚪"
            item = QListWidgetItem(f"{status} {account.email}")
            item.setData(Qt.ItemDataRole.UserRole, account.account_id)
            self.account_list.addItem(item)

    def add_account(self):
        """添加账户"""
        dialog = EmailAccountDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_account_data()
            try:
                from core.email_notification import EmailAccount
                import uuid
                account = EmailAccount(
                    account_id=f"acc_{uuid.uuid4().hex[:8]}",
                    **data
                )
                if self._config_manager.add_account(account):
                    self.refresh_account_list()
                    self.update_status(f"已添加账户: {account.email}")
                else:
                    QMessageBox.warning(self, "错误", "添加账户失败")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"添加账户失败: {e}")

    def edit_account(self):
        """编辑账户"""
        current_item = self.account_list.currentItem()
        if not current_item:
            QMessageBox.information(self, "提示", "请先选择一个账户")
            return

        account_id = current_item.data(Qt.ItemDataRole.UserRole)
        account = self._config_manager.get_account(account_id)
        if not account:
            return

        dialog = EmailAccountDialog(account, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_account_data()
            try:
                for key, value in data.items():
                    setattr(account, key, value)
                if self._config_manager.update_account(account):
                    self.refresh_account_list()
                    self.update_status(f"已更新账户: {account.email}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"更新账户失败: {e}")

    def remove_account(self):
        """删除账户"""
        current_item = self.account_list.currentItem()
        if not current_item:
            return

        account_id = current_item.data(Qt.ItemDataRole.UserRole)
        account = self._config_manager.get_account(account_id)
        if not account:
            return

        reply = QMessageBox.question(
            self, "确认", f"确定删除账户 {account.email}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            if self._config_manager.remove_account(account_id):
                self.refresh_account_list()
                self.update_status(f"已删除账户")

    def on_account_selected(self, item):
        """账户选中"""
        pass

    def toggle_dnd(self, checked):
        """切换免打扰"""
        try:
            from core.email_notification import get_notification_service
            svc = get_notification_service()
            svc.set_do_not_disturb(checked)
            self.dnd_btn.setText("🔔 免打扰" if not checked else "🔕 免打扰")
        except Exception as e:
            logger.error(f"Failed to toggle DND: {e}")

    def clear_history(self):
        """清空历史"""
        try:
            from core.email_notification import get_notification_service
            svc = get_notification_service()
            svc.clear_history()
            self.history_list.clear()
            self.update_status("已清空历史")
        except Exception as e:
            logger.error(f"Failed to clear history: {e}")

    def update_status(self, message: str):
        """更新状态栏"""
        self.status_bar.showMessage(message)

    def set_listener_manager(self, manager):
        """设置监听管理器"""
        self._listener_manager = manager

    def set_notification_service(self, service):
        """设置通知服务"""
        self._notification_service = service

    def set_tray_manager(self, manager):
        """设置托盘管理器"""
        self._tray_manager = manager


# 快速创建函数
def create_email_notification_panel(parent=None) -> EmailNotificationPanel:
    """创建邮件通知面板"""
    return EmailNotificationPanel(parent)
