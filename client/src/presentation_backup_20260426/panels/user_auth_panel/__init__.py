"""
用户认证与实名体系UI面板

功能：
1. 多级实名认证界面
2. 手机号认证
3. 身份证认证
4. 人脸识别
5. 认证状态展示
6. 认证进度与奖励
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QTabWidget, QLabel, QLineEdit, QPushButton,
    QTextEdit, QComboBox, QListWidget, QListWidgetItem,
    QGroupBox, QFormLayout, QSplitter, QScrollArea,
    QStatusBar, QProgressBar, QFrame, QCheckBox,
    QRadioButton, QButtonGroup, QSpinBox, QSlider,
    QDialog, QDialogButtonBox, QMessageBox, QInputDialog
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize
from PyQt6.QtGui import QIcon, QPalette, QColor, QPixmap


class UserAuthPanel(QWidget):
    """用户认证面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.auth_manager = None  # UserAuthManager instance
        self.current_user = None

        self._init_ui()
        self._init_connections()

    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # 顶部状态卡片
        status_group = QGroupBox("🔐 账户认证状态")
        status_layout = QHBoxLayout()

        # 认证级别
        self.level_label = QLabel("当前级别: 匿名用户")
        self.level_label.setStyleSheet("font-size: 16px; font-weight: bold;")

        self.badge_label = QLabel("")
        self.badge_label.setStyleSheet("font-size: 14px;")

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)

        self.progress_label = QLabel("0%")

        status_layout.addWidget(self.level_label)
        status_layout.addWidget(self.badge_label)
        status_layout.addStretch()
        status_layout.addWidget(self.progress_bar)
        status_layout.addWidget(self.progress_label)

        status_group.setLayout(status_layout)
        layout.addWidget(status_group)

        # 标签页
        tabs = QTabWidget()

        # Tab 1: 认证中心
        auth_tab = self._create_auth_center_tab()
        tabs.addTab(auth_tab, "🔐 认证中心")

        # Tab 2: 认证历史
        history_tab = self._create_history_tab()
        tabs.addTab(history_tab, "📜 认证历史")

        # Tab 3: 功能权限
        permissions_tab = self._create_permissions_tab()
        tabs.addTab(permissions_tab, "🔑 功能权限")

        # Tab 4: 隐私设置
        privacy_tab = self._create_privacy_tab()
        tabs.addTab(privacy_tab, "🛡️ 隐私设置")

        layout.addWidget(tabs)

    def _create_auth_center_tab(self) -> QWidget:
        """创建认证中心标签页"""
        tab = QScrollArea()
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 手机号认证区
        phone_group = QGroupBox("📱 手机号认证")
        phone_layout = QVBoxLayout()

        phone_form = QFormLayout()
        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("请输入手机号")
        phone_form.addRow("手机号:", self.phone_input)

        code_layout = QHBoxLayout()
        self.phone_code_input = QLineEdit()
        self.phone_code_input.setPlaceholderText("请输入验证码")
        self.send_code_btn = QPushButton("发送验证码")
        self.send_code_btn.setStyleSheet("background-color: #007acc; color: white;")
        code_layout.addWidget(self.phone_code_input)
        code_layout.addWidget(self.send_code_btn)

        phone_form.addRow("验证码:", code_layout)
        phone_layout.addLayout(phone_form)

        self.verify_phone_btn = QPushButton("✅ 完成手机认证")
        self.verify_phone_btn.setStyleSheet("background-color: #52c41a; color: white;")
        phone_layout.addWidget(self.verify_phone_btn)

        phone_group.setLayout(phone_layout)
        layout.addWidget(phone_group)

        # 身份证认证区
        id_card_group = QGroupBox("🆔 身份证认证")
        id_card_layout = QVBoxLayout()

        id_card_form = QFormLayout()
        self.real_name_input = QLineEdit()
        self.real_name_input.setPlaceholderText("请输入真实姓名")
        id_card_form.addRow("真实姓名:", self.real_name_input)

        self.id_card_input = QLineEdit()
        self.id_card_input.setPlaceholderText("请输入身份证号")
        id_card_form.addRow("身份证号:", self.id_card_input)

        id_card_layout.addLayout(id_card_form)

        # 认证方式选择
        channel_layout = QHBoxLayout()
        channel_layout.addWidget(QLabel("认证方式:"))
        self.channel_group = QButtonGroup()
        self.gov_channel = QRadioButton("🏛️ 官方认证（推荐）")
        self.bank_channel = QRadioButton("🏦 银行认证")
        self.alipay_channel = QRadioButton("💳 支付宝认证")
        self.gov_channel.setChecked(True)
        self.channel_group.addButton(self.gov_channel, 1)
        self.channel_group.addButton(self.bank_channel, 2)
        self.channel_group.addButton(self.alipay_channel, 3)
        channel_layout.addWidget(self.gov_channel)
        channel_layout.addWidget(self.bank_channel)
        channel_layout.addWidget(self.alipay_channel)
        channel_layout.addStretch()
        id_card_layout.addLayout(channel_layout)

        self.verify_id_card_btn = QPushButton("✅ 完成实名认证")
        self.verify_id_card_btn.setStyleSheet("background-color: #52c41a; color: white;")
        id_card_layout.addWidget(self.verify_id_card_btn)

        id_card_group.setLayout(id_card_layout)
        layout.addWidget(id_card_group)

        # 人脸识别区
        face_group = QGroupBox("👤 人脸识别认证")
        face_layout = QVBoxLayout()

        face_info = QLabel("完成人脸识别可进一步提升账户安全等级")
        face_layout.addWidget(face_info)

        self.face_preview_label = QLabel("📷 摄像头预览")
        self.face_preview_label.setFrameStyle(QFrame.Shape.StyledPanel)
        self.face_preview_label.setMinimumSize(200, 150)
        self.face_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.face_preview_label.setStyleSheet("background-color: #f0f0f0;")
        face_layout.addWidget(self.face_preview_label, 0, Qt.AlignmentFlag.AlignCenter)

        face_btn_layout = QHBoxLayout()
        self.start_face_btn = QPushButton("🎥 开始活体检测")
        self.verify_face_btn = QPushButton("✅ 完成人脸认证")
        self.verify_face_btn.setEnabled(False)
        face_btn_layout.addWidget(self.start_face_btn)
        face_btn_layout.addWidget(self.verify_face_btn)
        face_layout.addLayout(face_btn_layout)

        face_group.setLayout(face_layout)
        layout.addWidget(face_group)

        layout.addStretch()
        tab.setWidget(widget)
        return tab

    def _create_history_tab(self) -> QWidget:
        """创建认证历史标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 认证通道列表
        self.auth_history_list = QListWidget()
        self.auth_history_list.setAlternatingRowColors(True)
        layout.addWidget(QLabel("📜 认证历史"))
        layout.addWidget(self.auth_history_list)

        return tab

    def _create_permissions_tab(self) -> QWidget:
        """创建功能权限标签页"""
        tab = QScrollArea()
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 当前权限
        perms_group = QGroupBox("🔑 当前已解锁功能")
        perms_layout = QVBoxLayout()

        self.unlocked_features_list = QListWidget()
        perms_layout.addWidget(self.unlocked_features_list)

        perms_group.setLayout(perms_layout)
        layout.addWidget(perms_group)

        # 锁定功能
        locked_group = QGroupBox("🔒 待解锁功能")
        locked_layout = QVBoxLayout()

        self.locked_features_list = QListWidget()
        locked_layout.addWidget(self.locked_features_list)

        locked_group.setLayout(locked_layout)
        layout.addWidget(locked_group)

        # 功能所需认证
        requirement_group = QGroupBox("📋 认证要求")
        requirement_layout = QFormLayout()
        requirement_layout.addRow("创建表单:", QLabel("📱 基础实名"))
        requirement_layout.addRow("工作流审批:", QLabel("🆔 完全实名"))
        requirement_layout.addRow("数据导出:", QLabel("🆔 完全实名"))
        requirement_layout.addRow("团队管理:", QLabel("🏢 企业认证"))
        requirement_layout.addRow("API访问:", QLabel("🏢 企业认证"))
        requirement_group.setLayout(requirement_layout)
        layout.addWidget(requirement_group)

        layout.addStretch()
        tab.setWidget(widget)
        return tab

    def _create_privacy_tab(self) -> QWidget:
        """创建隐私设置标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 通知偏好
        notif_group = QGroupBox("🔔 通知偏好")
        notif_layout = QVBoxLayout()

        self.in_app_notif = QCheckBox("应用内通知")
        self.email_notif = QCheckBox("邮件通知")
        self.sms_notif = QCheckBox("短信通知")
        self.in_app_notif.setChecked(True)
        self.email_notif.setChecked(True)
        notif_layout.addWidget(self.in_app_notif)
        notif_layout.addWidget(self.email_notif)
        notif_layout.addWidget(self.sms_notif)

        notif_group.setLayout(notif_layout)
        layout.addWidget(notif_group)

        # 免打扰设置
        dnd_group = QGroupBox("🌙 免打扰设置")
        dnd_layout = QVBoxLayout()

        self.dnd_enabled = QCheckBox("启用免打扰模式")
        dnd_layout.addWidget(self.dnd_enabled)

        dnd_time_layout = QHBoxLayout()
        dnd_time_layout.addWidget(QLabel("开始时间:"))
        self.dnd_start = QComboBox()
        self.dnd_start.addItems([f"{h:02d}:00" for h in range(24)])
        self.dnd_start.setCurrentText("22:00")
        dnd_time_layout.addWidget(self.dnd_start)

        dnd_time_layout.addWidget(QLabel("结束时间:"))
        self.dnd_end = QComboBox()
        self.dnd_end.addItems([f"{h:02d}:00" for h in range(24)])
        self.dnd_end.setCurrentText("08:00")
        dnd_time_layout.addWidget(self.dnd_end)
        dnd_layout.addLayout(dnd_time_layout)

        dnd_group.setLayout(dnd_layout)
        layout.addWidget(dnd_group)

        # 同意管理
        consent_group = QGroupBox("📄 同意管理")
        consent_layout = QVBoxLayout()

        self.consent_list = QListWidget()
        consent_layout.addWidget(self.consent_list)

        consent_btn_layout = QHBoxLayout()
        self.view_consent_btn = QPushButton("查看协议")
        self.agree_consent_btn = QPushButton("同意")
        consent_btn_layout.addWidget(self.view_consent_btn)
        consent_btn_layout.addWidget(self.agree_consent_btn)
        consent_layout.addLayout(consent_btn_layout)

        consent_group.setLayout(consent_layout)
        layout.addWidget(consent_group)

        layout.addStretch()
        return tab

    def _init_connections(self):
        """初始化连接"""
        self.send_code_btn.clicked.connect(self._on_send_code)
        self.verify_phone_btn.clicked.connect(self._on_verify_phone)
        self.verify_id_card_btn.clicked.connect(self._on_verify_id_card)
        self.start_face_btn.clicked.connect(self._on_start_face_detection)

    def set_auth_manager(self, auth_manager):
        """设置认证管理器"""
        self.auth_manager = auth_manager
        self.refresh_status()

    def refresh_status(self):
        """刷新认证状态"""
        if not self.auth_manager:
            return

        user = self.auth_manager.get_current_user()
        if not user:
            return

        self.current_user = user

        # 更新级别显示
        self.level_label.setText(f"当前级别: {user.get_auth_level_name()}")

        # 更新徽章
        from ..core.user_auth import AUTH_REWARDS
        reward = AUTH_REWARDS.get(user.auth_level)
        if reward:
            self.badge_label.setText(reward.badge)

        # 更新进度
        progress = int((user.auth_level / 3) * 100)
        self.progress_bar.setValue(progress)
        self.progress_label.setText(f"{progress}%")

        # 更新认证历史
        self._update_auth_history()

        # 更新功能列表
        self._update_features()

    def _update_auth_history(self):
        """更新认证历史"""
        self.auth_history_list.clear()

        if not self.current_user:
            return

        for channel in self.current_user.verification_channels:
            item = QListWidgetItem(f"✅ {channel}")
            self.auth_history_list.addItem(item)

    def _update_features(self):
        """更新功能列表"""
        self.unlocked_features_list.clear()
        self.locked_features_list.clear()

        if not self.current_user:
            return

        # 已解锁
        for feature in self.current_user.unlocked_features:
            item = QListWidgetItem(f"🔓 {feature}")
            self.unlocked_features_list.addItem(item)

        # 待解锁（基于认证级别）
        from ..core.user_auth import AUTH_REWARDS

        all_features = {
            1: ["custom_theme", "basic_form_templates"],
            2: ["workflow_create", "data_export", "advanced_templates"],
            3: ["team_collaboration", "api_access", "priority_support"]
        }

        for level, features in all_features.items():
            if self.current_user.auth_level < level:
                for feature in features:
                    item = QListWidgetItem(f"🔒 {feature} (需要等级{level})")
                    self.locked_features_list.addItem(item)

    # ============ 事件处理 ============

    def _on_send_code(self):
        """发送验证码"""
        phone = self.phone_input.text()
        if not phone:
            QMessageBox.warning(self, "错误", "请输入手机号")
            return

        if self.auth_manager:
            # 实际会调用认证服务
            QMessageBox.information(self, "发送成功", f"验证码已发送到 {phone}")
            self.send_code_btn.setEnabled(False)
            self._start_countdown(60)

    def _start_countdown(self, seconds: int):
        """倒计时"""
        remaining = seconds
        def update():
            nonlocal remaining
            remaining -= 1
            if remaining > 0:
                self.send_code_btn.setText(f"{remaining}秒后重发")
            else:
                self.send_code_btn.setText("发送验证码")
                self.send_code_btn.setEnabled(True)
                self.timer.stop()

        self.timer = QTimer()
        self.timer.timeout.connect(update)
        self.timer.start(1000)

    def _on_verify_phone(self):
        """验证手机号"""
        phone = self.phone_input.text()
        code = self.phone_code_input.text()

        if not phone or not code:
            QMessageBox.warning(self, "错误", "请填写完整信息")
            return

        QMessageBox.information(self, "认证成功", "手机号认证已完成！")
        self.refresh_status()

    def _on_verify_id_card(self):
        """验证身份证"""
        real_name = self.real_name_input.text()
        id_card = self.id_card_input.text()

        if not real_name or not id_card:
            QMessageBox.warning(self, "错误", "请填写完整信息")
            return

        QMessageBox.information(self, "认证成功", "实名认证已完成！")
        self.refresh_status()

    def _on_start_face_detection(self):
        """开始人脸检测"""
        QMessageBox.information(
            self,
            "活体检测",
            "请按照屏幕提示完成活体检测动作"
        )
        self.verify_face_btn.setEnabled(True)


class AuthGuideDialog(QDialog):
    """认证引导对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📋 认证引导")
        self._init_ui()

    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # 引导步骤
        steps = [
            {"title": "完善账户信息", "desc": "设置昵称和头像", "icon": "👤"},
            {"title": "手机号验证", "desc": "保护账户安全", "icon": "📱"},
            {"title": "实名认证", "desc": "解锁高级功能", "icon": "🆔"},
            {"title": "企业认证", "desc": "团队协作功能", "icon": "🏢"}
        ]

        for i, step in enumerate(steps, 1):
            step_widget = QFrame()
            step_layout = QHBoxLayout()

            icon_label = QLabel(step["icon"])
            icon_label.setStyleSheet("font-size: 24px;")

            info_layout = QVBoxLayout()
            title_label = QLabel(f"{i}. {step['title']}")
            title_label.setStyleSheet("font-weight: bold;")
            desc_label = QLabel(step["desc"])
            desc_label.setStyleSheet("color: gray;")
            info_layout.addWidget(title_label)
            info_layout.addWidget(desc_label)

            step_layout.addWidget(icon_label)
            step_layout.addLayout(info_layout)
            step_layout.addStretch()

            step_widget.setLayout(step_layout)
            layout.addWidget(step_widget)

        # 按钮
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Skip
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class ConsentDialog(QDialog):
    """同意对话框"""

    def __init__(self, consent_type: str, parent=None):
        super().__init__(parent)
        self.consent_type = consent_type
        self.setWindowTitle("📄 同意确认")
        self._init_ui()

    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # 协议内容
        content = QTextEdit()
        content.setReadOnly(True)
        content.setPlainText(self._get_consent_content())
        layout.addWidget(content)

        # 按钮
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Yes |
            QDialogButtonBox.StandardButton.No
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _get_consent_content(self) -> str:
        """获取协议内容"""
        contents = {
            "user_agreement": "用户服务协议...",
            "privacy_policy": "隐私政策...",
            "phone_consent": "手机号使用授权...",
            "real_name_consent": "实名信息使用授权...",
            "biometric_consent": "生物特征信息授权..."
        }
        return contents.get(self.consent_type, "")


# 导入必要的模块
import json