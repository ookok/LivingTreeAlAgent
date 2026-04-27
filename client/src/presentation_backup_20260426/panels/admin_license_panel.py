"""
管理员授权管理面板
Admin Authorization Management Panel

三端（客户端/服务端/追踪端）通用管理员管理界面：
1. 作者配置
2. 管理员管理（添加/删除/禁用）
3. 序列号生成（需管理员权限）
4. 审计日志
"""

import os
import json
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTabWidget, QLineEdit, QTextEdit, QTableWidget, QTableWidgetItem,
    QComboBox, QCheckBox, QGroupBox, QFormLayout, QGridLayout,
    QScrollArea, QFrame, QSpacerItem, QSizePolicy, QMessageBox,
    QDialog, QDialogButtonBox, QDateEdit, QSpinBox, QProgressBar,
    QStatusBar, QToolBar
)
from PyQt6.QtGui import QFont, QIcon, QPalette, QColor
from PyQt6.QtCore import QDate


# 尝试导入授权模块
try:
    from client.src.business.admin_license_system import (
        get_author_config_manager,
        get_admin_auth,
        get_admin_manager,
        get_license_auth,
        Platform,
        AdminRole,
        AdminPermission,
        AdminUser,
        AuthorInfo,
    )
    ADMIN_SYSTEM_AVAILABLE = True
except ImportError:
    ADMIN_SYSTEM_AVAILABLE = False


# ==================== 样式定义 ====================

PANEL_STYLE = """
/* 主面板样式 */
#AdminLicensePanel {
    background-color: #1a1a2e;
}

/* 标签页样式 */
QTabWidget::pane {
    border: 1px solid #16213e;
    background-color: #1a1a2e;
    border-radius: 8px;
}

QTabBar::tab {
    background-color: #16213e;
    color: #a0a0a0;
    padding: 10px 20px;
    margin-right: 2px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}

QTabBar::tab:selected {
    background-color: #0f3460;
    color: #e94560;
    font-weight: bold;
}

QTabBar::tab:hover {
    background-color: #1a1a2e;
    color: #ffffff;
}

/* 按钮样式 */
.QPushButton {
    background-color: #0f3460;
    color: #ffffff;
    border: none;
    padding: 8px 16px;
    border-radius: 6px;
    font-size: 13px;
}

.QPushButton:hover {
    background-color: #e94560;
}

.QPushButton:pressed {
    background-color: #c23a51;
}

.QPushButton:disabled {
    background-color: #2a2a4a;
    color: #666666;
}

/* 危险按钮 */
.QPushButton#danger {
    background-color: #dc3545;
}

.QPushButton#danger:hover {
    background-color: #c82333;
}

/* 成功按钮 */
.QPushButton#success {
    background-color: #28a745;
}

.QPushButton#success:hover {
    background-color: #218838;
}

/* 输入框样式 */
QLineEdit, QTextEdit, QSpinBox {
    background-color: #16213e;
    color: #ffffff;
    border: 1px solid #0f3460;
    border-radius: 4px;
    padding: 8px;
}

QLineEdit:focus, QTextEdit:focus {
    border: 1px solid #e94560;
}

/* 表格样式 */
QTableWidget {
    background-color: #16213e;
    color: #ffffff;
    border: 1px solid #0f3460;
    gridline-color: #1a1a2e;
}

QTableWidget::item {
    padding: 5px;
}

QTableWidget::item:selected {
    background-color: #0f3460;
}

QHeaderView::section {
    background-color: #0f3460;
    color: #ffffff;
    padding: 8px;
    border: none;
}

/* 标签样式 */
QLabel {
    color: #ffffff;
}

QLabel#title {
    font-size: 18px;
    font-weight: bold;
    color: #e94560;
}

QLabel#subtitle {
    font-size: 14px;
    color: #a0a0a0;
}

/* 状态标签 */
QLabel#status_active {
    color: #28a745;
    font-weight: bold;
}

QLabel#status_inactive {
    color: #dc3545;
    font-weight: bold;
}

QLabel#status_author {
    color: #ffc107;
    font-weight: bold;
}
"""


class AdminLicensePanel(QWidget):
    """
    管理员授权管理面板

    标签页：
    1. 📝 作者配置 - 作者信息设置
    2. 👥 管理员管理 - 管理员CRUD
    3. 🔑 序列号生成 - 生成激活码（需权限）
    4. 📋 审计日志 - 操作记录查看
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("AdminLicensePanel")

        if not ADMIN_SYSTEM_AVAILABLE:
            self._show_unavailable()
            return

        self._auth = get_admin_auth()
        self._admin_manager = get_admin_manager()
        self._license_auth = get_license_auth()
        self._author_config = get_author_config_manager()

        self._init_ui()
        self._refresh()

    def _show_unavailable(self):
        """显示模块不可用"""
        layout = QVBoxLayout(self)
        label = QLabel("管理员授权系统模块不可用")
        label.setStyleSheet("color: #dc3545; font-size: 16px;")
        layout.addWidget(label)

    def _init_ui(self):
        """初始化UI"""
        self.setStyleSheet(PANEL_STYLE)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # 顶部信息栏
        self._create_header()

        # 标签页
        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_author_tab(), "📝 作者配置")
        self.tabs.addTab(self._create_admin_tab(), "👥 管理员管理")
        self.tabs.addTab(self._create_license_tab(), "🔑 序列号生成")
        self.tabs.addTab(self._create_audit_tab(), "📋 审计日志")

        main_layout.addWidget(self.tabs)

        # 状态栏
        self.status_bar = QStatusBar()
        main_layout.addWidget(self.status_bar)

    def _create_header(self):
        """创建顶部信息栏"""
        header = QFrame()
        header.setStyleSheet("background-color: #16213e; border-radius: 8px; padding: 10px;")
        layout = QHBoxLayout(header)

        self.title_label = QLabel("🔐 管理员授权中心")
        self.title_label.setObjectName("title")

        self.user_label = QLabel("未登录")
        self.user_label.setStyleSheet("color: #a0a0a0;")

        self.login_btn = QPushButton("登录")
        self.login_btn.setObjectName("success")
        self.login_btn.clicked.connect(self._on_login_click)

        self.logout_btn = QPushButton("登出")
        self.logout_btn.setObjectName("danger")
        self.logout_btn.clicked.connect(self._on_logout_click)
        self.logout_btn.setVisible(False)

        layout.addWidget(self.title_label)
        layout.addStretch()
        layout.addWidget(self.user_label)
        layout.addWidget(self.login_btn)
        layout.addWidget(self.logout_btn)

        # 添加到主布局
        self.layout().addWidget(header) if self.layout() else None

    def _create_author_tab(self) -> QWidget:
        """创建作者配置标签页"""
        widget = QScrollArea()
        widget.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)

        # 作者信息表单
        group = QGroupBox("作者信息")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #0f3460;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        form = QFormLayout()

        self.author_name = QLineEdit()
        self.author_email = QLineEdit()
        self.author_company = QLineEdit()
        self.author_website = QLineEdit()
        self.author_phone = QLineEdit()
        self.author_max_admins = QSpinBox()
        self.author_max_admins.setRange(1, 1000)
        self.author_max_admins.setValue(100)

        form.addRow("名称:", self.author_name)
        form.addRow("邮箱:", self.author_email)
        form.addRow("公司:", self.author_company)
        form.addRow("网站:", self.author_website)
        form.addRow("电话:", self.author_phone)
        form.addRow("最大管理员数:", self.author_max_admins)

        group.setLayout(form)
        layout.addWidget(group)

        # 操作按钮
        btn_layout = QHBoxLayout()
        self.save_author_btn = QPushButton("💾 保存配置")
        self.save_author_btn.clicked.connect(self._on_save_author)
        self.gen_credentials_btn = QPushButton("🔑 生成凭证")
        self.gen_credentials_btn.clicked.connect(self._on_generate_credentials)

        btn_layout.addWidget(self.save_author_btn)
        btn_layout.addWidget(self.gen_credentials_btn)
        btn_layout.addStretch()

        layout.addLayout(btn_layout)

        # 凭证显示
        self.credentials_group = QGroupBox("平台凭证")
        self.credentials_group.setVisible(False)
        cred_layout = QFormLayout()
        self.cred_app_id = QLineEdit()
        self.cred_app_id.setReadOnly(True)
        self.cred_app_secret = QLineEdit()
        self.cred_app_secret.setReadOnly(True)
        cred_layout.addRow("APP ID:", self.cred_app_id)
        cred_layout.addRow("APP Secret:", self.cred_app_secret)
        self.credentials_group.setLayout(cred_layout)
        layout.addWidget(self.credentials_group)

        layout.addStretch()
        return widget

    def _create_admin_tab(self) -> QWidget:
        """创建管理员管理标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 统计信息
        stats_group = QGroupBox("管理员统计")
        stats_layout = QHBoxLayout()
        self.stats_labels = {}
        stats_layout.addWidget(QLabel("总数:"))
        self.stats_labels['total'] = QLabel("0")
        stats_layout.addWidget(self.stats_labels['total'])
        stats_layout.addWidget(QLabel("活跃:"))
        self.stats_labels['active'] = QLabel("0")
        stats_layout.addWidget(self.stats_labels['active'])
        stats_layout.addWidget(QLabel("作者:"))
        self.stats_labels['author'] = QLabel("0")
        stats_layout.addWidget(self.stats_labels['author'])
        stats_layout.addWidget(QLabel("超级管理员:"))
        self.stats_labels['super_admin'] = QLabel("0")
        stats_layout.addWidget(self.stats_labels['super_admin'])
        stats_layout.addStretch()
        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)

        # 管理员表格
        self.admin_table = QTableWidget()
        self.admin_table.setColumns([
            '用户名', '显示名', '邮箱', '角色', '状态', '最后登录', '操作'
        ])
        self.admin_table.setColumnWidth(6, 200)
        layout.addWidget(self.admin_table)

        # 添加管理员表单
        add_group = QGroupBox("添加管理员")
        add_layout = QHBoxLayout()

        self.add_username = QLineEdit()
        self.add_username.setPlaceholderText("用户名")
        self.add_password = QLineEdit()
        self.add_password.setPlaceholderText("密码")
        self.add_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.add_email = QLineEdit()
        self.add_email.setPlaceholderText("邮箱")
        self.add_role = QComboBox()
        self.add_role.addItems([
            AdminRole.ADMIN.value,
            AdminRole.OPERATOR.value,
            AdminRole.SUPER_ADMIN.value,
        ])

        self.add_admin_btn = QPushButton("➕ 添加")
        self.add_admin_btn.setObjectName("success")
        self.add_admin_btn.clicked.connect(self._on_add_admin)

        add_layout.addWidget(self.add_username)
        add_layout.addWidget(self.add_password)
        add_layout.addWidget(self.add_email)
        add_layout.addWidget(self.add_role)
        add_layout.addWidget(self.add_admin_btn)

        add_group.setLayout(add_layout)
        layout.addWidget(add_group)

        # 刷新按钮
        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.clicked.connect(self._refresh_admins)
        layout.addWidget(refresh_btn)

        return widget

    def _create_license_tab(self) -> QWidget:
        """创建序列号生成标签页"""
        widget = QScrollArea()
        widget.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)

        # 权限提示
        self.license_permission_label = QLabel("⚠️ 您没有生成序列号的权限")
        self.license_permission_label.setStyleSheet("color: #ffc107; font-weight: bold; padding: 10px;")
        self.license_permission_label.setVisible(True)
        layout.addWidget(self.license_permission_label)

        # 单个生成
        single_group = QGroupBox("生成单个序列号")
        single_layout = QFormLayout()

        self.license_version = QComboBox()
        self.license_version.addItems(['PER (个人版)', 'PRO (专业版)', 'ENT (企业版)'])
        self.license_expires = QSpinBox()
        self.license_expires.setRange(1, 3650)
        self.license_expires.setValue(365)
        self.license_expires.setSuffix(" 天")
        self.license_max_users = QSpinBox()
        self.license_max_users.setRange(1, 100)
        self.license_max_users.setValue(1)

        single_layout.addRow("版本:", self.license_version)
        single_layout.addRow("有效期:", self.license_expires)
        single_layout.addRow("最大用户:", self.license_max_users)

        single_group.setLayout(single_layout)
        layout.addWidget(single_group)

        self.generate_single_btn = QPushButton("🎫 生成序列号")
        self.generate_single_btn.setObjectName("success")
        self.generate_single_btn.clicked.connect(self._on_generate_single)
        layout.addWidget(self.generate_single_btn)

        # 批量生成
        batch_group = QGroupBox("批量生成序列号")
        batch_layout = QFormLayout()

        self.batch_count = QSpinBox()
        self.batch_count.setRange(1, 1000)
        self.batch_count.setValue(10)
        self.batch_name = QLineEdit()
        self.batch_name.setPlaceholderText("批次名称（可选）")

        batch_layout.addRow("数量:", self.batch_count)
        batch_layout.addRow("批次名称:", self.batch_name)

        batch_group.setLayout(batch_layout)
        layout.addWidget(batch_group)

        self.generate_batch_btn = QPushButton("🎫 批量生成")
        self.generate_batch_btn.setObjectName("success")
        self.generate_batch_btn.clicked.connect(self._on_generate_batch)
        layout.addWidget(self.generate_batch_btn)

        # 结果显示
        self.license_result = QTextEdit()
        self.license_result.setReadOnly(True)
        self.license_result.setMaximumHeight(200)
        layout.addWidget(QLabel("生成结果:"))
        layout.addWidget(self.license_result)

        # 历史记录
        history_btn = QPushButton("📜 查看生成历史")
        history_btn.clicked.connect(self._on_show_history)
        layout.addWidget(history_btn)

        layout.addStretch()
        return widget

    def _create_audit_tab(self) -> QWidget:
        """创建审计日志标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 筛选
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("筛选管理员:"))
        self.audit_admin_filter = QComboBox()
        self.audit_admin_filter.addItem("全部", None)
        filter_layout.addWidget(self.audit_admin_filter)

        self.audit_action_filter = QComboBox()
        self.audit_action_filter.addItems([
            "全部", "ADD_ADMIN", "REMOVE_ADMIN", "DISABLE_ADMIN", "ENABLE_ADMIN",
            "GENERATE_LICENSE", "GENERATE_LICENSE_BATCH"
        ])
        filter_layout.addWidget(self.audit_action_filter)

        refresh_audit_btn = QPushButton("🔄 刷新")
        refresh_audit_btn.clicked.connect(self._refresh_audit)
        filter_layout.addWidget(refresh_audit_btn)
        filter_layout.addStretch()

        layout.addLayout(filter_layout)

        # 日志表格
        self.audit_table = QTableWidget()
        self.audit_table.setColumns([
            '时间', '管理员', '操作', '目标', '详情'
        ])
        layout.addWidget(self.audit_table)

        return widget

    def _refresh(self):
        """刷新面板状态"""
        # 刷新用户信息
        if self._auth.is_logged_in:
            user = self._auth.current_user
            self.user_label.setText(f"登录: {user.username} ({user.role})")
            self.user_label.setVisible(True)
            self.login_btn.setVisible(False)
            self.logout_btn.setVisible(True)
        else:
            self.user_label.setText("未登录")
            self.login_btn.setVisible(True)
            self.logout_btn.setVisible(False)

        # 刷新作者配置
        self._refresh_author_config()

        # 刷新管理员列表
        self._refresh_admins()

        # 刷新审计日志
        self._refresh_audit()

        # 检查序列号权限
        self._check_license_permission()

    def _refresh_author_config(self):
        """刷新作者配置"""
        if self._author_config.has_author_config():
            info = self._author_config.get_author_info()
            if info:
                self.author_name.setText(info.name)
                self.author_email.setText(info.email)
                self.author_company.setText(info.company)
                self.author_website.setText(info.website)
                self.author_phone.setText(info.phone)
                self.author_max_admins.setValue(info.max_admins)

    def _refresh_admins(self):
        """刷新管理员列表"""
        stats = self._admin_manager.get_admin_stats()
        self.stats_labels['total'].setText(str(stats['total']))
        self.stats_labels['active'].setText(str(stats['active']))
        self.stats_labels['author'].setText(str(stats['by_role'].get('author', 0)))
        self.stats_labels['super_admin'].setText(str(stats['by_role'].get('super_admin', 0)))

        # 刷新表格
        admins = self._auth.get_all_admins()
        self.admin_table.setRowCount(len(admins))

        for row, admin in enumerate(admins):
            self.admin_table.setItem(row, 0, QTableWidgetItem(admin.username))
            self.admin_table.setItem(row, 1, QTableWidgetItem(admin.display_name))
            self.admin_table.setItem(row, 2, QTableWidgetItem(admin.email))
            self.admin_table.setItem(row, 3, QTableWidgetItem(admin.role))

            status_item = QTableWidgetItem("活跃" if admin.is_active else "禁用")
            status_item.setForeground(QColor("#28a745" if admin.is_active else "#dc3545"))
            self.admin_table.setItem(row, 4, status_item)

            self.admin_table.setItem(row, 5, QTableWidgetItem(admin.last_login or "从未"))

            # 操作按钮
            action_widget = QWidget()
            action_layout = QHBoxLayout()
            action_layout.setContentsMargins(0, 0, 0, 0)

            if admin.id != self._auth.current_user.id if self._auth.current_user else False:
                disable_btn = QPushButton("禁用" if admin.is_active else "启用")
                disable_btn.setObjectName("danger" if admin.is_active else "success")
                disable_btn.clicked.connect(lambda _, aid=admin.id: self._on_toggle_admin(aid))
                action_layout.addWidget(disable_btn)

                if not admin.is_author:
                    delete_btn = QPushButton("删除")
                    delete_btn.setObjectName("danger")
                    delete_btn.clicked.connect(lambda _, aid=admin.id: self._on_delete_admin(aid))
                    action_layout.addWidget(delete_btn)

            action_widget.setLayout(action_layout)
            self.admin_table.setCellWidget(row, 6, action_widget)

        # 刷新审计筛选下拉框
        self.audit_admin_filter.clear()
        self.audit_admin_filter.addItem("全部", None)
        for admin in admins:
            self.audit_admin_filter.addItem(f"{admin.username}", admin.id)

    def _refresh_audit(self):
        """刷新审计日志"""
        admin_id = self.audit_admin_filter.currentData()
        action = self.audit_action_filter.currentText()
        action = None if action == "全部" else action

        logs = self._admin_manager.get_audit_logs(admin_id=admin_id, action=action, limit=100)

        self.audit_table.setRowCount(len(logs))
        for row, log in enumerate(logs):
            self.audit_table.setItem(row, 0, QTableWidgetItem(log.created_at))
            self.audit_table.setItem(row, 1, QTableWidgetItem(log.admin_username))
            self.audit_table.setItem(row, 2, QTableWidgetItem(log.action))
            self.audit_table.setItem(row, 3, QTableWidgetItem(log.target_username))
            self.audit_table.setItem(row, 4, QTableWidgetItem(log.details))

    def _check_license_permission(self):
        """检查序列号生成权限"""
        can_generate, reason = self._license_auth.can_generate_license()

        if can_generate:
            self.license_permission_label.setText("✅ 您有生成序列号的权限")
            self.license_permission_label.setStyleSheet("color: #28a745; font-weight: bold; padding: 10px;")
            self.generate_single_btn.setEnabled(True)
            self.generate_batch_btn.setEnabled(True)
        else:
            self.license_permission_label.setText(f"⚠️ {reason}")
            self.license_permission_label.setStyleSheet("color: #ffc107; font-weight: bold; padding: 10px;")
            self.generate_single_btn.setEnabled(False)
            self.generate_batch_btn.setEnabled(False)

    def _on_login_click(self):
        """登录按钮点击"""
        dialog = LoginDialog(self)
        if dialog.exec() == QDialog.Accepted:
            self._refresh()

    def _on_logout_click(self):
        """登出按钮点击"""
        self._auth.logout()
        self._refresh()

    def _on_save_author(self):
        """保存作者配置"""
        try:
            if not self._author_config.has_author_config():
                self._author_config.create_author_config(
                    name=self.author_name.text(),
                    email=self.author_email.text(),
                    company=self.author_company.text(),
                    website=self.author_website.text(),
                    phone=self.author_phone.text(),
                    max_admins=self.author_max_admins.value()
                )
            else:
                self._author_config.update_author_info(
                    name=self.author_name.text(),
                    email=self.author_email.text(),
                    company=self.author_company.text(),
                    website=self.author_website.text(),
                    phone=self.author_phone.text(),
                    max_admins=self.author_max_admins.value()
                )

            QMessageBox.information(self, "成功", "作者配置已保存")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败: {e}")

    def _on_generate_credentials(self):
        """生成凭证"""
        app_id, app_secret = self._author_config.generate_author_credentials()
        self.cred_app_id.setText(app_id)
        self.cred_app_secret.setText(app_secret)
        self.credentials_group.setVisible(True)

        # 添加平台绑定
        self._author_config.add_platform_binding(Platform.WINDOWS, app_id, app_secret)

        QMessageBox.information(self, "成功", f"凭证已生成并绑定到Windows平台\n\nAPP ID: {app_id}\nAPP Secret: {app_secret}\n\n请妥善保管APP Secret，它只会显示一次！")

    def _on_add_admin(self):
        """添加管理员"""
        username = self.add_username.text().strip()
        password = self.add_password.text()
        email = self.add_email.text().strip()
        role = self.add_role.currentText()

        if not username or not password:
            QMessageBox.warning(self, "错误", "用户名和密码不能为空")
            return

        result = self._admin_manager.add_admin(
            username=username,
            password=password,
            email=email,
            role=role
        )

        if result.success:
            QMessageBox.information(self, "成功", f"管理员 {username} 添加成功")
            self.add_username.clear()
            self.add_password.clear()
            self.add_email.clear()
            self._refresh_admins()
        else:
            QMessageBox.critical(self, "错误", result.message)

    def _on_toggle_admin(self, admin_id: str):
        """切换管理员状态"""
        admin = self._auth.get_admin(admin_id)
        if not admin:
            return

        if admin.is_active:
            result = self._admin_manager.disable_admin(admin_id)
        else:
            result = self._admin_manager.enable_admin(admin_id)

        if result.success:
            self._refresh_admins()
        else:
            QMessageBox.critical(self, "错误", result.message)

    def _on_delete_admin(self, admin_id: str):
        """删除管理员"""
        admin = self._auth.get_admin(admin_id)
        if not admin:
            return

        reply = QMessageBox.question(
            self, "确认", f"确定要删除管理员 {admin.username} 吗？\n此操作不可恢复！",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            result = self._admin_manager.remove_admin(admin_id)
            if result.success:
                self._refresh_admins()
            else:
                QMessageBox.critical(self, "错误", result.message)

    def _on_generate_single(self):
        """生成单个序列号"""
        version_map = {'PER (个人版)': 'PER', 'PRO (专业版)': 'PRO', 'ENT (企业版)': 'ENT'}
        version = version_map[self.license_version.currentText()]

        success, msg, key = self._license_auth.generate_license_with_auth(
            version=version,
            expires_days=self.license_expires.value(),
            max_users=self.license_max_users.value()
        )

        if success:
            self.license_result.append(f"✅ {key.key_string}")
        else:
            self.license_result.append(f"❌ {msg}")

    def _on_generate_batch(self):
        """批量生成序列号"""
        version_map = {'PER (个人版)': 'PER', 'PRO (专业版)': 'PRO', 'ENT (企业版)': 'ENT'}
        version = version_map[self.license_version.currentText()]

        success, msg, batch = self._license_auth.generate_batch_with_auth(
            version=version,
            count=self.batch_count.value(),
            expires_days=self.license_expires.value(),
            max_users=self.license_max_users.value(),
            batch_name=self.batch_name.text()
        )

        if success:
            self.license_result.append(f"✅ 批次 {batch.batch_id}:")
            for key in batch.keys:
                self.license_result.append(f"   {key.key_string}")
        else:
            self.license_result.append(f"❌ {msg}")

    def _on_show_history(self):
        """显示生成历史"""
        history = self._license_auth.get_generation_history(limit=50)
        self.license_result.append("\n📜 生成历史:")
        for h in history:
            self.license_result.append(f"   [{h['created_at']}] {h['admin_username']}: {h['details']}")


class LoginDialog(QDialog):
    """登录对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("管理员登录")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)

        # 登录类型选择
        self.login_type = QComboBox()
        self.login_type.addItems(["普通登录", "作者登录"])
        layout.addWidget(QLabel("登录方式:"))
        layout.addWidget(self.login_type)

        # 用户名
        self.username = QLineEdit()
        self.username.setPlaceholderText("用户名")
        layout.addWidget(QLabel("用户名:"))
        layout.addWidget(self.username)

        # 密码
        self.password = QLineEdit()
        self.password.setPlaceholderText("密码")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(QLabel("密码:"))
        layout.addWidget(self.password)

        # 作者邮箱（仅作者登录）
        self.author_email = QLineEdit()
        self.author_email.setPlaceholderText("作者邮箱")
        layout.addWidget(QLabel("作者邮箱:"))
        layout.addWidget(self.author_email)
        self.author_email.setVisible(False)

        # 连接信号
        self.login_type.currentIndexChanged.connect(self._on_type_changed)

        # 按钮
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_type_changed(self, index):
        """登录类型改变"""
        if index == 0:  # 普通登录
            self.username.setVisible(True)
            self.password.setVisible(True)
            self.author_email.setVisible(False)
        else:  # 作者登录
            self.username.setVisible(False)
            self.password.setVisible(False)
            self.author_email.setVisible(True)

    def _on_accept(self):
        """确认登录"""
        auth = get_admin_auth()

        if self.login_type.currentIndex() == 0:
            # 普通登录
            result = auth.login(self.username.text(), self.password.text())
        else:
            # 作者登录
            result = auth.author_login(email=self.author_email.text())

        if result.success:
            self.accept()
        else:
            QMessageBox.critical(self, "错误", result.message)


# ==================== QTableWidget 扩展 ====================

class AdminTable(QTableWidget):
    """管理员表格扩展"""

    def setColumns(self, columns):
        """设置列"""
        self.setColumnCount(len(columns))
        self.setHorizontalHeaderLabels(columns)

    def setRowData(self, row, data):
        """设置行数据"""
        for col, value in enumerate(data):
            self.setItem(row, col, QTableWidgetItem(str(value)))


# 单例
_panel_instance = None


def get_admin_license_panel() -> AdminLicensePanel:
    """获取管理员授权面板单例"""
    global _panel_instance
    if _panel_instance is None:
        _panel_instance = AdminLicensePanel()
    return _panel_instance