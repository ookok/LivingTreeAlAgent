"""
登录和注册对话框
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton,
    QDialog, QCheckBox,
)
from PyQt6.QtGui import QFont, QPainter, QPixmap, QLinearGradient, QRadialGradient


class LoginDialog(QDialog):
    """登录对话框"""
    
    login_requested = pyqtSignal(str, str)  # username, password
    register_requested = pyqtSignal()
    guest_mode_requested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        self.setWindowTitle("🌳 生命之树AI OS - 登录")
        self.setMinimumSize(400, 520)
        self.setModal(True)
        self.setStyleSheet("""
            QDialog {
                background: #1A1A1A;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(24)
        
        # Logo 区域
        logo_layout = QVBoxLayout()
        logo_layout.setSpacing(16)
        logo_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        logo_label = QLabel("🌳")
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_label.setStyleSheet("font-size: 64px;")
        
        title = QLabel("生命之树AI OS")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("""
            color: #00D4AA;
            font-size: 24px;
            font-weight: bold;
            font-family: "Microsoft YaHei", sans-serif;
        """)
        
        subtitle = QLabel("您的智能助手")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("""
            color: #888888;
            font-size: 14px;
            font-family: "Microsoft YaHei", sans-serif;
        """)
        
        logo_layout.addWidget(logo_label)
        logo_layout.addWidget(title)
        logo_layout.addWidget(subtitle)
        layout.addLayout(logo_layout)
        
        # 输入区域
        input_layout = QVBoxLayout()
        input_layout.setSpacing(16)
        
        self.username = QLineEdit()
        self.username.setPlaceholderText("👤 用户名 / 邮箱")
        self.username.setFixedHeight(50)
        self.username.setStyleSheet("""
            QLineEdit {
                background: #252525;
                border: none;
                border-radius: 12px;
                padding: 0 20px;
                color: #FFFFFF;
                font-size: 15px;
                font-family: "Microsoft YaHei", sans-serif;
            }
            QLineEdit::placeholder {
                color: #666666;
            }
        """)
        input_layout.addWidget(self.username)
        
        self.password = QLineEdit()
        self.password.setPlaceholderText("🔒 密码")
        self.password.setFixedHeight(50)
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setStyleSheet("""
            QLineEdit {
                background: #252525;
                border: none;
                border-radius: 12px;
                padding: 0 20px;
                color: #FFFFFF;
                font-size: 15px;
                font-family: "Microsoft YaHei", sans-serif;
            }
            QLineEdit::placeholder {
                color: #666666;
            }
        """)
        # 回车登录
        self.password.returnPressed.connect(self._on_login)
        input_layout.addWidget(self.password)
        
        # 记住我
        remember_layout = QHBoxLayout()
        self.remember_cb = QCheckBox("记住我")
        self.remember_cb.setStyleSheet("""
            QCheckBox {
                color: #888888;
                font-size: 13px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 4px;
                border: 2px solid #666666;
                background: #252525;
            }
            QCheckBox::indicator:checked {
                border-color: #00D4AA;
                background: #00D4AA;
            }
        """)
        remember_layout.addWidget(self.remember_cb)
        remember_layout.addStretch()
        input_layout.addLayout(remember_layout)
        
        layout.addLayout(input_layout)
        
        # 按钮区域
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(12)
        
        login_btn = QPushButton("登录")
        login_btn.setFixedHeight(50)
        login_btn.setStyleSheet("""
            QPushButton {
                background: #00D4AA;
                border: none;
                border-radius: 12px;
                color: #0D0D0D;
                font-size: 16px;
                font-weight: bold;
                font-family: "Microsoft YaHei", sans-serif;
            }
            QPushButton:hover {
                background: #00E8BB;
            }
        """)
        login_btn.clicked.connect(self._on_login)
        btn_layout.addWidget(login_btn)
        
        register_btn = QPushButton("注册账号")
        register_btn.setFixedHeight(50)
        register_btn.setStyleSheet("""
            QPushButton {
                background: #333333;
                border: none;
                border-radius: 12px;
                color: #FFFFFF;
                font-size: 15px;
                font-family: "Microsoft YaHei", sans-serif;
            }
            QPushButton:hover {
                background: #444444;
            }
        """)
        register_btn.clicked.connect(self._on_register)
        btn_layout.addWidget(register_btn)
        
        # 分隔线
        sep_layout = QHBoxLayout()
        sep_layout.setSpacing(12)
        
        left_line = QLabel()
        left_line.setFixedHeight(1)
        left_line.setStyleSheet("background: #333333;")
        left_line.setSizePolicy(QWidget.SizePolicy.Policy.Expanding, QWidget.SizePolicy.Policy.Fixed)
        
        sep_label = QLabel("或")
        sep_label.setStyleSheet("color: #666666; font-size: 13px;")
        
        right_line = QLabel()
        right_line.setFixedHeight(1)
        right_line.setStyleSheet("background: #333333;")
        right_line.setSizePolicy(QWidget.SizePolicy.Policy.Expanding, QWidget.SizePolicy.Policy.Fixed)
        
        sep_layout.addWidget(left_line)
        sep_layout.addWidget(sep_label)
        sep_layout.addWidget(right_line)
        btn_layout.addLayout(sep_layout)
        
        guest_btn = QPushButton("🌿 游客模式体验")
        guest_btn.setFixedHeight(50)
        guest_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 2px solid #00D4AA;
                border-radius: 12px;
                color: #00D4AA;
                font-size: 15px;
                font-family: "Microsoft YaHei", sans-serif;
            }
            QPushButton:hover {
                background: #00D4AA20;
            }
        """)
        guest_btn.clicked.connect(self._on_guest)
        btn_layout.addWidget(guest_btn)
        
        layout.addLayout(btn_layout)
        
        # 底部信息
        footer_layout = QHBoxLayout()
        footer_layout.setSpacing(16)
        footer_layout.addStretch()
        
        version = QLabel("版本 1.0.0")
        version.setStyleSheet("color: #666666; font-size: 11px;")
        
        terms = QLabel("服务条款")
        terms.setStyleSheet("color: #888888; font-size: 11px; cursor: pointer;")
        terms.setCursor(Qt.CursorShape.PointingHandCursor)
        
        privacy = QLabel("隐私政策")
        privacy.setStyleSheet("color: #888888; font-size: 11px; cursor: pointer;")
        privacy.setCursor(Qt.CursorShape.PointingHandCursor)
        
        footer_layout.addWidget(version)
        footer_layout.addWidget(terms)
        footer_layout.addWidget(privacy)
        footer_layout.addStretch()
        
        layout.addLayout(footer_layout)
    
    def _on_login(self):
        username = self.username.text().strip()
        password = self.password.text()
        if username and password:
            self.login_requested.emit(username, password)
    
    def _on_register(self):
        self.register_requested.emit()
    
    def _on_guest(self):
        self.guest_mode_requested.emit()


class RegisterDialog(QDialog):
    """注册对话框"""
    
    register_requested = pyqtSignal(str, str, str)  # username, email, password
    login_requested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        self.setWindowTitle("🌳 注册账号")
        self.setMinimumSize(400, 580)
        self.setModal(True)
        self.setStyleSheet("""
            QDialog {
                background: #1A1A1A;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(24)
        
        # 标题
        title_layout = QVBoxLayout()
        title_layout.setSpacing(8)
        title_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        title = QLabel("创建账号")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("""
            color: #FFFFFF;
            font-size: 22px;
            font-weight: bold;
            font-family: "Microsoft YaHei", sans-serif;
        """)
        
        subtitle = QLabel("加入生命之树AI OS")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("""
            color: #888888;
            font-size: 14px;
            font-family: "Microsoft YaHei", sans-serif;
        """)
        
        title_layout.addWidget(title)
        title_layout.addWidget(subtitle)
        layout.addLayout(title_layout)
        
        # 输入区域
        input_layout = QVBoxLayout()
        input_layout.setSpacing(16)
        
        self.username = QLineEdit()
        self.username.setPlaceholderText("👤 用户名")
        self.username.setFixedHeight(50)
        self._style_input(self.username)
        input_layout.addWidget(self.username)
        
        self.email = QLineEdit()
        self.email.setPlaceholderText("📧 邮箱")
        self.email.setFixedHeight(50)
        self._style_input(self.email)
        input_layout.addWidget(self.email)
        
        self.password = QLineEdit()
        self.password.setPlaceholderText("🔒 密码（至少8位）")
        self.password.setFixedHeight(50)
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self._style_input(self.password)
        input_layout.addWidget(self.password)
        
        self.confirm_password = QLineEdit()
        self.confirm_password.setPlaceholderText("🔒 确认密码")
        self.confirm_password.setFixedHeight(50)
        self.confirm_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_password.returnPressed.connect(self._on_register)
        self._style_input(self.confirm_password)
        input_layout.addWidget(self.confirm_password)
        
        layout.addLayout(input_layout)
        
        # 协议
        self.agree_cb = QCheckBox("我已阅读并同意《服务条款》和《隐私政策》")
        self.agree_cb.setStyleSheet("""
            QCheckBox {
                color: #888888;
                font-size: 12px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 4px;
                border: 2px solid #666666;
                background: #252525;
            }
            QCheckBox::indicator:checked {
                border-color: #00D4AA;
                background: #00D4AA;
            }
        """)
        layout.addWidget(self.agree_cb)
        
        # 按钮
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(12)
        
        register_btn = QPushButton("注册")
        register_btn.setFixedHeight(50)
        register_btn.setStyleSheet("""
            QPushButton {
                background: #00D4AA;
                border: none;
                border-radius: 12px;
                color: #0D0D0D;
                font-size: 16px;
                font-weight: bold;
                font-family: "Microsoft YaHei", sans-serif;
            }
            QPushButton:hover {
                background: #00E8BB;
            }
            QPushButton:disabled {
                background: #333333;
                color: #666666;
            }
        """)
        register_btn.clicked.connect(self._on_register)
        self.register_btn = register_btn
        btn_layout.addWidget(register_btn)
        
        # 已有账号
        login_layout = QHBoxLayout()
        login_layout.addStretch()
        
        login_text = QLabel("已有账号？")
        login_text.setStyleSheet("color: #888888; font-size: 13px;")
        
        login_link = QLabel("登录")
        login_link.setStyleSheet("color: #00D4AA; font-size: 13px; cursor: pointer;")
        login_link.setCursor(Qt.CursorShape.PointingHandCursor)
        login_link.mousePressEvent = lambda e: self.login_requested.emit()
        
        login_layout.addWidget(login_text)
        login_layout.addWidget(login_link)
        login_layout.addStretch()
        
        btn_layout.addLayout(login_layout)
        layout.addLayout(btn_layout)
    
    def _style_input(self, widget: QLineEdit):
        widget.setStyleSheet("""
            QLineEdit {
                background: #252525;
                border: none;
                border-radius: 12px;
                padding: 0 20px;
                color: #FFFFFF;
                font-size: 15px;
                font-family: "Microsoft YaHei", sans-serif;
            }
            QLineEdit::placeholder {
                color: #666666;
            }
        """)
    
    def _on_register(self):
        if not self.agree_cb.isChecked():
            return
        
        username = self.username.text().strip()
        email = self.email.text().strip()
        password = self.password.text()
        confirm = self.confirm_password.text()
        
        if password != confirm:
            return
        
        if username and email and password:
            self.register_requested.emit(username, email, password)


__all__ = ["LoginDialog", "RegisterDialog"]
