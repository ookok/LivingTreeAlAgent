"""
用户认证对话框
User Authentication Dialog

支持用户注册、登录、个人资料管理。
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QCheckBox, QTabWidget,
    QFormLayout, QGroupBox, QMessageBox, QComboBox
)
from PyQt6.QtGui import QFont

from client.src.business.auth_system import AuthSystem, AuthResult, UserRole


class LoginDialog(QWidget):
    """
    用户认证对话框
    
    支持：
    - 登录
    - 注册
    - 个人资料
    """
    
    # 登录成功信号
    login_successful = pyqtSignal(str)  # user_id
    logout_signal = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.auth = AuthSystem()
        
        self._setup_ui()
        self._check_existing_session()
    
    def _setup_ui(self):
        """设置UI"""
        self.setWindowTitle("用户认证")
        self.setFixedSize(400, 450)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # 标题
        title = QLabel("🔐 Hermes Desktop")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Tab 切换
        self._tabs = QTabWidget()
        
        # 登录页
        login_tab = self._create_login_tab()
        self._tabs.addTab(login_tab, "登录")
        
        # 注册页
        register_tab = self._create_register_tab()
        self._tabs.addTab(register_tab, "注册")
        
        # 个人资料页
        profile_tab = self._create_profile_tab()
        self._tabs.addTab(profile_tab, "个人资料")
        
        layout.addWidget(self._tabs)
        
        # 当前用户状态
        self._status_label = QLabel("未登录")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setStyleSheet("color: #888;")
        layout.addWidget(self._status_label)
        
        # 关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.hide)
        layout.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignRight)
    
    def _create_login_tab(self) -> QWidget:
        """创建登录页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)
        
        # 用户名
        self._login_username = QLineEdit()
        self._login_username.setPlaceholderText("用户名")
        self._login_username.setFixedHeight(40)
        layout.addWidget(self._login_username)
        
        # 密码
        self._login_password = QLineEdit()
        self._login_password.setPlaceholderText("密码")
        self._login_password.setEchoMode(QLineEdit.EchoMode.Password)
        self._login_password.setFixedHeight(40)
        layout.addWidget(self._login_password)
        
        # 记住登录
        remember_layout = QHBoxLayout()
        self._remember_check = QCheckBox("记住登录状态")
        remember_layout.addWidget(self._remember_check)
        remember_layout.addStretch()
        layout.addLayout(remember_layout)
        
        # 登录按钮
        login_btn = QPushButton("登录")
        login_btn.setFixedHeight(45)
        login_btn.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        login_btn.setStyleSheet("""
            QPushButton {
                background: #3b82f6;
                color: white;
                border: none;
                border-radius: 8px;
            }
            QPushButton:hover {
                background: #2563eb;
            }
        """)
        login_btn.clicked.connect(self._do_login)
        layout.addWidget(login_btn)
        
        layout.addStretch()
        
        return widget
    
    def _create_register_tab(self) -> QWidget:
        """创建注册页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)
        
        # 用户名
        self._reg_username = QLineEdit()
        self._reg_username.setPlaceholderText("用户名 (3-20个字符)")
        self._reg_username.setFixedHeight(40)
        layout.addWidget(self._reg_username)
        
        # 邮箱
        self._reg_email = QLineEdit()
        self._reg_email.setPlaceholderText("邮箱 (可选)")
        self._reg_email.setFixedHeight(40)
        layout.addWidget(self._reg_email)
        
        # 显示名称
        self._reg_display_name = QLineEdit()
        self._reg_display_name.setPlaceholderText("显示名称")
        self._reg_display_name.setFixedHeight(40)
        layout.addWidget(self._reg_display_name)
        
        # 密码
        self._reg_password = QLineEdit()
        self._reg_password.setPlaceholderText("密码 (至少6个字符)")
        self._reg_password.setEchoMode(QLineEdit.EchoMode.Password)
        self._reg_password.setFixedHeight(40)
        layout.addWidget(self._reg_password)
        
        # 确认密码
        self._reg_password_confirm = QLineEdit()
        self._reg_password_confirm.setPlaceholderText("确认密码")
        self._reg_password_confirm.setEchoMode(QLineEdit.EchoMode.Password)
        self._reg_password_confirm.setFixedHeight(40)
        layout.addWidget(self._reg_password_confirm)
        
        # 注册按钮
        register_btn = QPushButton("注册")
        register_btn.setFixedHeight(45)
        register_btn.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        register_btn.setStyleSheet("""
            QPushButton {
                background: #10b981;
                color: white;
                border: none;
                border-radius: 8px;
            }
            QPushButton:hover {
                background: #059669;
            }
        """)
        register_btn.clicked.connect(self._do_register)
        layout.addWidget(register_btn)
        
        layout.addStretch()
        
        return widget
    
    def _create_profile_tab(self) -> QWidget:
        """创建个人资料页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)
        
        # 资料表单
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(10)
        
        # 用户名（只读）
        self._profile_username = QLineEdit()
        self._profile_username.setReadOnly(True)
        self._profile_username.setStyleSheet("background: #f5f5f5;")
        form.addRow("用户名:", self._profile_username)
        
        # 显示名称
        self._profile_display_name = QLineEdit()
        self._profile_display_name.setPlaceholderText("显示名称")
        form.addRow("显示名称:", self._profile_display_name)
        
        # 邮箱
        self._profile_email = QLineEdit()
        self._profile_email.setPlaceholderText("邮箱")
        form.addRow("邮箱:", self._profile_email)
        
        # 简介
        self._profile_bio = QLineEdit()
        self._profile_bio.setPlaceholderText("个人简介")
        form.addRow("简介:", self._profile_bio)
        
        # 角色
        self._profile_role = QLabel()
        form.addRow("角色:", self._profile_role)
        
        # 注册时间
        self._profile_created = QLabel()
        form.addRow("注册时间:", self._profile_created)
        
        layout.addLayout(form)
        
        # 保存按钮
        save_btn = QPushButton("💾 保存资料")
        save_btn.clicked.connect(self._save_profile)
        layout.addWidget(save_btn)
        
        # 修改密码
        pwd_group = QGroupBox("修改密码")
        pwd_layout = QFormLayout(pwd_group)
        
        self._old_password = QLineEdit()
        self._old_password.setPlaceholderText("旧密码")
        self._old_password.setEchoMode(QLineEdit.EchoMode.Password)
        pwd_layout.addRow("旧密码:", self._old_password)
        
        self._new_password = QLineEdit()
        self._new_password.setPlaceholderText("新密码")
        self._new_password.setEchoMode(QLineEdit.EchoMode.Password)
        pwd_layout.addRow("新密码:", self._new_password)
        
        change_pwd_btn = QPushButton("修改密码")
        change_pwd_btn.clicked.connect(self._change_password)
        pwd_layout.addRow("", change_pwd_btn)
        
        layout.addWidget(pwd_group)
        
        # 登出按钮
        logout_btn = QPushButton("退出登录")
        logout_btn.setStyleSheet("""
            QPushButton {
                background: #ef4444;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px;
            }
            QPushButton:hover {
                background: #dc2626;
            }
        """)
        logout_btn.clicked.connect(self._do_logout)
        layout.addWidget(logout_btn)
        
        layout.addStretch()
        
        return widget
    
    def _check_existing_session(self):
        """检查已有会话"""
        if self.auth.is_logged_in:
            self._update_profile_display()
            self._tabs.setCurrentIndex(2)  # 切换到资料页
        else:
            self._tabs.setCurrentIndex(0)  # 切换到登录页
    
    def _do_login(self):
        """执行登录"""
        username = self._login_username.text().strip()
        password = self._login_password.text()
        
        if not username or not password:
            QMessageBox.warning(self, "提示", "请输入用户名和密码")
            return
        
        result = self.auth.login(username, password)
        
        if result.success:
            self._status_label.setText(f"✅ 已登录: {result.user.username}")
            self._update_profile_display()
            self._tabs.setCurrentIndex(2)
            self.login_successful.emit(result.user.id)
            
            from client.src.presentation.panels.toast_notification import toast_success
            toast_success(f"欢迎回来, {result.user.username}!")
        else:
            QMessageBox.warning(self, "登录失败", result.message)
    
    def _do_register(self):
        """执行注册"""
        username = self._reg_username.text().strip()
        email = self._reg_email.text().strip()
        display_name = self._reg_display_name.text().strip()
        password = self._reg_password.text()
        password_confirm = self._reg_password_confirm.text()
        
        # 验证
        if not username:
            QMessageBox.warning(self, "提示", "请输入用户名")
            return
        
        if len(username) < 3:
            QMessageBox.warning(self, "提示", "用户名至少需要3个字符")
            return
        
        if not password:
            QMessageBox.warning(self, "提示", "请输入密码")
            return
        
        if len(password) < 6:
            QMessageBox.warning(self, "提示", "密码至少需要6个字符")
            return
        
        if password != password_confirm:
            QMessageBox.warning(self, "提示", "两次输入的密码不一致")
            return
        
        result = self.auth.register(
            username=username,
            password=password,
            email=email,
            display_name=display_name or username
        )
        
        if result.success:
            QMessageBox.information(self, "注册成功", "账号注册成功，请登录！")
            self._login_username.setText(username)
            self._login_password.clear()
            self._tabs.setCurrentIndex(0)
            
            from client.src.presentation.panels.toast_notification import toast_success
            toast_success("注册成功！")
        else:
            QMessageBox.warning(self, "注册失败", result.message)
    
    def _save_profile(self):
        """保存资料"""
        if not self.auth.is_logged_in:
            QMessageBox.warning(self, "提示", "请先登录")
            return
        
        success = self.auth.update_profile(
            self.auth.current_user.id,
            display_name=self._profile_display_name.text(),
            email=self._profile_email.text(),
            bio=self._profile_bio.text()
        )
        
        if success:
            QMessageBox.information(self, "保存成功", "个人资料已保存")
            self._update_profile_display()
            
            from client.src.presentation.panels.toast_notification import toast_success
            toast_success("资料已保存")
        else:
            QMessageBox.warning(self, "保存失败", "请重试")
    
    def _change_password(self):
        """修改密码"""
        if not self.auth.is_logged_in:
            QMessageBox.warning(self, "提示", "请先登录")
            return
        
        old_pwd = self._old_password.text()
        new_pwd = self._new_password.text()
        
        if not old_pwd or not new_pwd:
            QMessageBox.warning(self, "提示", "请填写完整")
            return
        
        result = self.auth.change_password(
            self.auth.current_user.id,
            old_pwd,
            new_pwd
        )
        
        if result.success:
            QMessageBox.information(self, "成功", "密码已修改")
            self._old_password.clear()
            self._new_password.clear()
            
            from client.src.presentation.panels.toast_notification import toast_success
            toast_success("密码修改成功")
        else:
            QMessageBox.warning(self, "失败", result.message)
    
    def _do_logout(self):
        """执行登出"""
        self.auth.logout()
        self._status_label.setText("未登录")
        self._tabs.setCurrentIndex(0)
        self._login_username.clear()
        self._login_password.clear()
        self.logout_signal.emit()
        
        from client.src.presentation.panels.toast_notification import toast_info
        toast_info("已退出登录")
    
    def _update_profile_display(self):
        """更新资料页显示"""
        user = self.auth.current_user
        if not user:
            return
        
        self._profile_username.setText(user.username)
        self._profile_display_name.setText(user.display_name)
        self._profile_email.setText(user.email)
        self._profile_bio.setText(user.bio)
        self._profile_role.setText(user.role.value)
        self._profile_created.setText(user.created_at[:10] if user.created_at else "")
        self._status_label.setText(f"✅ 已登录: {user.username}")
    
    def get_current_user(self):
        """获取当前用户"""
        return self.auth.current_user
    
    def is_logged_in(self) -> bool:
        """是否已登录"""
        return self.auth.is_logged_in
