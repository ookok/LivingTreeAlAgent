"""
智能授权与实名认证系统 - UI面板
Activation License System Panel

6个标签页：
1. 📋 版本概览 - 当前版本状态、使用情况
2. 🔑 激活管理 - 激活码输入、激活状态
3. 🆔 实名认证 - 实名用户管理（最多5人）
4. 📊 发行中心 - 生成激活码（发行方使用）
5. ⚙️ 设备管理 - 关联设备查看
6. 📜 激活日志 - 历史激活记录
"""

import os
import uuid
import json
import hashlib
from datetime import datetime
from typing import Optional, List, Dict, Any

from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTabWidget, QLineEdit, QTextEdit, QTableWidget, QTableWidgetItem,
    QComboBox, QCheckBox, QGroupBox, QFormLayout, QGridLayout,
    QScrollArea, QFrame, QSpacerItem, QSizePolicy, QMessageBox,
    QDialog, QDialogButtonBox, QDateEdit, QSpinBox
)
from PyQt6.QtGui import QFont, QIcon, QPalette, QColor
from PyQt6.QtCore import QDate


# 尝试导入授权模块
try:
    from client.src.business.activation_license import (
        LicenseGenerator, LicenseValidator, RealNameVerifier,
        LicenseVersion, ValidationResult, ValidationResponse,
        VerificationType, VerificationStatus,
        get_license_generator, get_license_validator, get_real_name_verifier,
        generate_license_key, validate_license_key, activate_license,
        get_version_config, LICENSE_VERSIONS
    )
    LICENSE_AVAILABLE = True
except ImportError:
    LICENSE_AVAILABLE = False


# ==================== 样式定义 ====================

PANEL_STYLE = """
/* 主面板样式 */
#ActivationPanel {
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
    background-color: #2d2d44;
    color: #666666;
}

/* 主要按钮 */
.PrimaryButton {
    background-color: #e94560;
    color: #ffffff;
    border: none;
    padding: 10px 24px;
    border-radius: 8px;
    font-size: 14px;
    font-weight: bold;
}

.PrimaryButton:hover {
    background-color: #ff6b6b;
}

/* 输入框样式 */
QLineEdit, QTextEdit {
    background-color: #16213e;
    color: #ffffff;
    border: 1px solid #0f3460;
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 13px;
}

QLineEdit:focus, QTextEdit:focus {
    border: 1px solid #e94560;
}

/* 标签样式 */
.TitleLabel {
    color: #ffffff;
    font-size: 18px;
    font-weight: bold;
}

.SubTitleLabel {
    color: #a0a0a0;
    font-size: 14px;
}

.InfoLabel {
    color: #4a9eff;
    font-size: 12px;
}

.SuccessLabel {
    color: #4ade80;
    font-size: 12px;
}

.ErrorLabel {
    color: #f87171;
    font-size: 12px;
}

/* 卡片样式 */
.CardFrame {
    background-color: #16213e;
    border-radius: 10px;
    padding: 16px;
    border: 1px solid #0f3460;
}

/* 状态指示器 */
.StatusActive {
    color: #4ade80;
    font-weight: bold;
}

.StatusInactive {
    color: #f87171;
    font-weight: bold;
}

.StatusPending {
    color: #fbbf24;
    font-weight: bold;
}
"""


# ==================== 版本概览面板 ====================

class VersionOverviewPanel(QWidget):
    """版本概览面板"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._load_status()
    
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        
        # 标题
        title = QLabel("📋 版本概览")
        title.setObjectName("TitleLabel")
        layout.addWidget(title)
        
        # 版本卡片区域
        self.version_cards = QVBoxLayout()
        self.version_cards.setSpacing(12)
        layout.addLayout(self.version_cards)
        
        # 加载版本信息
        self._create_version_cards()
        
        layout.addStretch()
    
    def _create_version_cards(self):
        """创建版本卡片"""
        versions = [
            ('PER', '个人版', '免费使用', False),
            ('PRO', '专业版', '需要激活码', True),
            ('ENT', '企业版', '需要激活码+实名', True),
        ]
        
        for code, name, desc, need_activation in versions:
            card = self._create_version_card(code, name, desc, need_activation)
            self.version_cards.addWidget(card)
    
    def _create_version_card(self, code: str, name: str, desc: str, need_activation: bool) -> QFrame:
        """创建单个版本卡片"""
        card = QFrame()
        card.setObjectName("CardFrame")
        card_layout = QGridLayout(card)
        
        # 版本标识
        version_label = QLabel(f"<b>{code}</b>")
        version_label.setStyleSheet("color: #e94560; font-size: 24px;")
        card_layout.addWidget(version_label, 0, 0, 2, 1)
        
        # 版本名称
        name_label = QLabel(name)
        name_label.setStyleSheet("color: #ffffff; font-size: 18px; font-weight: bold;")
        card_layout.addWidget(name_label, 0, 1)
        
        # 描述
        desc_label = QLabel(desc)
        desc_label.setStyleSheet("color: #a0a0a0; font-size: 13px;")
        card_layout.addWidget(desc_label, 1, 1)
        
        # 功能列表
        features = LICENSE_VERSIONS.get(code, {}).get('features', [])
        features_label = QLabel("功能: " + ", ".join(features))
        features_label.setStyleSheet("color: #4a9eff; font-size: 11px;")
        card_layout.addWidget(features_label, 2, 0, 1, 2)
        
        # 用户限制
        max_users = LICENSE_VERSIONS.get(code, {}).get('max_users', 1)
        users_label = QLabel(f"用户数限制: {max_users}人")
        users_label.setStyleSheet("color: #a0a0a0; font-size: 11px;")
        card_layout.addWidget(users_label, 3, 0, 1, 2)
        
        return card
    
    def _load_status(self):
        """加载当前状态"""
        if not LICENSE_AVAILABLE:
            return
        
        validator = get_license_validator()
        # 检查是否有激活记录
        device_id = self._get_device_id()
        info = validator.get_activation_info(device_id=device_id)
        
        if info:
            status = info.get('status', 'UNKNOWN')
            version = info.get('version', 'PER')
            expires_at = info.get('expires_at', 'N/A')
            
            # 更新对应版本的卡片状态
            # TODO: 实际更新UI状态
    
    def _get_device_id(self) -> str:
        """获取设备ID"""
        import platform
        machine = platform.node() + platform.machine() + platform.processor()
        return hashlib.sha256(machine.encode()).hexdigest()[:16]


# ==================== 激活管理面板 ====================

class ActivationPanel(QWidget):
    """激活管理面板"""
    
    activation_success = pyqtSignal(str)  # 激活成功信号
    activation_failed = pyqtSignal(str)   # 激活失败信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
    
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        
        # 标题
        title = QLabel("🔑 激活管理")
        title.setObjectName("TitleLabel")
        layout.addWidget(title)
        
        # 激活码输入区域
        input_group = QGroupBox("输入激活码")
        input_layout = QVBoxLayout()
        
        self.license_input = QLineEdit()
        self.license_input.setPlaceholderText("请输入激活码，格式：XXX-YYYY-YYYY-YYYY-ZZZZZZ")
        self.license_input.setMinimumHeight(45)
        font = self.license_input.font()
        font.setPointSize(14)
        self.license_input.setFont(font)
        input_layout.addWidget(self.license_input)
        
        self.activate_btn = QPushButton("立即激活")
        self.activate_btn.setObjectName("PrimaryButton")
        self.activate_btn.setMinimumHeight(45)
        self.activate_btn.clicked.connect(self._on_activate)
        input_layout.addWidget(self.activate_btn)
        
        input_group.setLayout(input_layout)
        layout.addWidget(input_group)
        
        # 激活结果显示
        self.result_card = QFrame()
        self.result_card.setObjectName("CardFrame")
        self.result_card.hide()
        result_layout = QVBoxLayout()
        
        self.result_title = QLabel()
        self.result_title.setStyleSheet("font-size: 16px; font-weight: bold;")
        result_layout.addWidget(self.result_title)
        
        self.result_message = QLabel()
        self.result_message.setWordWrap(True)
        result_layout.addWidget(self.result_message)
        
        self.result_details = QTextEdit()
        self.result_details.setReadOnly(True)
        self.result_details.setMaximumHeight(150)
        result_layout.addWidget(self.result_details)
        
        self.result_card.setLayout(result_layout)
        layout.addWidget(self.result_card)
        
        # 当前激活状态
        status_group = QGroupBox("当前状态")
        status_layout = QFormLayout()
        
        self.status_version = QLabel("未激活")
        self.status_version.setStyleSheet("color: #f87171; font-weight: bold;")
        status_layout.addRow("版本:", self.status_version)
        
        self.status_expires = QLabel("N/A")
        status_layout.addRow("过期时间:", self.status_expires)
        
        self.status_devices = QLabel("0/1")
        status_layout.addRow("设备数:", self.status_devices)
        
        status_group.setLayout(status_layout)
        layout.addWidget(status_group)
        
        layout.addStretch()
        
        # 加载当前状态
        self._load_current_status()
    
    def _on_activate(self):
        """处理激活按钮点击"""
        license_key = self.license_input.text().strip().upper()
        
        if not license_key:
            self._show_result("error", "请输入激活码")
            return
        
        if not LICENSE_AVAILABLE:
            self._show_result("error", "授权模块不可用，请检查安装")
            return
        
        # 获取设备ID和用户ID
        device_id = self._get_device_id()
        user_id = self._get_user_id()
        
        # 执行激活
        result = activate_license(
            license_key=license_key,
            device_id=device_id,
            user_id=user_id
        )
        
        if result.is_valid:
            self._show_result("success", "激活成功！", result)
            self.activation_success.emit(license_key)
        else:
            self._show_result("error", f"激活失败：{result.message}", result)
            self.activation_failed.emit(result.message)
    
    def _show_result(self, result_type: str, message: str, result: ValidationResponse = None):
        """显示激活结果"""
        self.result_card.show()
        
        if result_type == "success":
            self.result_title.setText("✅ 激活成功")
            self.result_title.setStyleSheet("color: #4ade80; font-size: 16px; font-weight: bold;")
        else:
            self.result_title.setText("❌ 激活失败")
            self.result_title.setStyleSheet("color: #f87171; font-size: 16px; font-weight: bold;")
        
        self.result_message.setText(message)
        
        if result and result.license_info:
            info = result.license_info
            details_text = f"""版本: {info.get('version', 'N/A')}
序列号: {info.get('serial', 'N/A')[:20]}...
过期时间: {info.get('expires_at', 'N/A')}
激活ID: {info.get('activation_id', 'N/A')}"""
            self.result_details.setPlainText(details_text)
        else:
            self.result_details.setPlainText("")
    
    def _load_current_status(self):
        """加载当前激活状态"""
        if not LICENSE_AVAILABLE:
            return
        
        validator = get_license_validator()
        device_id = self._get_device_id()
        info = validator.get_activation_info(device_id=device_id)
        
        if info:
            self.status_version.setText(f"✅ {info.get('version', 'N/A')} 版本")
            self.status_version.setStyleSheet("color: #4ade80; font-weight: bold;")
            self.status_expires.setText(info.get('expires_at', 'N/A'))
        else:
            self.status_version.setText("❌ 未激活")
            self.status_version.setStyleSheet("color: #f87171; font-weight: bold;")
    
    def _get_device_id(self) -> str:
        """获取设备ID"""
        import platform
        machine = platform.node() + platform.machine() + platform.processor()
        return hashlib.sha256(machine.encode()).hexdigest()[:16]
    
    def _get_user_id(self) -> str:
        """获取用户ID"""
        return f"user_{self._get_device_id()}"


# ==================== 实名认证面板 ====================

class RealNamePanel(QWidget):
    """实名认证面板"""
    
    verify_success = pyqtSignal(str)  # 认证成功信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._load_users()
    
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        
        # 标题
        title = QLabel("🆔 实名认证")
        title.setObjectName("TitleLabel")
        layout.addWidget(title)
        
        # 用户数量提示
        self.count_label = QLabel()
        self.count_label.setStyleSheet("color: #fbbf24; font-size: 14px;")
        layout.addWidget(self.count_label)
        
        # 添加用户表单
        add_group = QGroupBox("添加实名用户（最多5人）")
        add_layout = QGridLayout()
        
        # 姓名
        add_layout.addWidget(QLabel("真实姓名:"), 0, 0)
        self.real_name_input = QLineEdit()
        self.real_name_input.setPlaceholderText("请输入真实姓名")
        add_layout.addWidget(self.real_name_input, 0, 1)
        
        # 身份证号
        add_layout.addWidget(QLabel("身份证号:"), 1, 0)
        self.id_number_input = QLineEdit()
        self.id_number_input.setPlaceholderText("请输入身份证号（可选）")
        add_layout.addWidget(self.id_number_input, 1, 1)
        
        # 手机号
        add_layout.addWidget(QLabel("手机号:"), 2, 0)
        phone_layout = QHBoxLayout()
        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("请输入手机号")
        phone_layout.addWidget(self.phone_input)
        
        self.send_code_btn = QPushButton("发送验证码")
        self.send_code_btn.setObjectName("QPushButton")
        self.send_code_btn.setMaximumWidth(100)
        self.send_code_btn.clicked.connect(self._on_send_code)
        phone_layout.addWidget(self.send_code_btn)
        add_layout.addLayout(phone_layout, 2, 1)
        
        # 验证码
        add_layout.addWidget(QLabel("验证码:"), 3, 0)
        code_layout = QHBoxLayout()
        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("请输入验证码")
        code_layout.addWidget(self.code_input)
        
        self.verify_btn = QPushButton("验证并添加")
        self.verify_btn.setObjectName("PrimaryButton")
        self.verify_btn.clicked.connect(self._on_verify_and_add)
        code_layout.addWidget(self.verify_btn)
        add_layout.addLayout(code_layout, 3, 1)
        
        add_group.setLayout(add_layout)
        layout.addWidget(add_group)
        
        # 用户列表
        list_group = QGroupBox("实名用户列表")
        list_layout = QVBoxLayout()
        
        self.user_table = QTableWidget()
        self.user_table.setColumnCount(5)
        self.user_table.setHorizontalHeaderLabels(["用户ID", "认证方式", "认证时间", "过期时间", "状态"])
        self.user_table.setMaximumHeight(200)
        list_layout.addWidget(self.user_table)
        
        list_group.setLayout(list_layout)
        layout.addWidget(list_group)
        
        # 结果显示
        self.result_label = QLabel()
        self.result_label.setWordWrap(True)
        layout.addWidget(self.result_label)
        
        layout.addStretch()
    
    def _on_send_code(self):
        """发送验证码"""
        phone = self.phone_input.text().strip()
        
        if not phone:
            self.result_label.setText("请输入手机号")
            self.result_label.setStyleSheet("color: #f87171;")
            return
        
        if not LICENSE_AVAILABLE:
            self.result_label.setText("实名认证模块不可用")
            self.result_label.setStyleSheet("color: #f87171;")
            return
        
        verifier = get_real_name_verifier()
        success, message = verifier.send_verification_code(phone, "REAL_NAME_VERIFY")
        
        self.result_label.setText(message)
        self.result_label.setStyleSheet("color: #4ade80;" if success else "#f87171;")
    
    def _on_verify_and_add(self):
        """验证并添加用户"""
        real_name = self.real_name_input.text().strip()
        id_number = self.id_number_input.text().strip()
        phone = self.phone_input.text().strip()
        code = self.code_input.text().strip()
        
        if not real_name:
            self.result_label.setText("请输入真实姓名")
            self.result_label.setStyleSheet("color: #f87171;")
            return
        
        if not phone or not code:
            self.result_label.setText("请输入手机号和验证码")
            self.result_label.setStyleSheet("color: #f87171;")
            return
        
        if not LICENSE_AVAILABLE:
            self.result_label.setText("实名认证模块不可用")
            self.result_label.setStyleSheet("color: #f87171;")
            return
        
        verifier = get_real_name_verifier()
        
        # 验证验证码
        success, msg = verifier.verify_sms_code(phone, code)
        if not success:
            self.result_label.setText(f"验证码错误: {msg}")
            self.result_label.setStyleSheet("color: #f87171;")
            return
        
        # 生成用户ID
        user_id = f"user_{hashlib.md5(real_name.encode()).hexdigest()[:8]}"
        
        # 添加用户
        success, msg, user = verifier.register_real_name_user(
            user_id=user_id,
            real_name=real_name,
            id_number=id_number if id_number else None,
            phone=phone,
            verification_type=VerificationType.PHONE_SMS
        )
        
        if success:
            self.result_label.setText(f"✅ 添加成功！用户ID: {user_id}")
            self.result_label.setStyleSheet("color: #4ade80;")
            self._load_users()
            self.verify_success.emit(user_id)
        else:
            self.result_label.setText(f"❌ 添加失败: {msg}")
            self.result_label.setStyleSheet("color: #f87171;")
    
    def _load_users(self):
        """加载用户列表"""
        if not LICENSE_AVAILABLE:
            self.count_label.setText("实名认证模块不可用")
            return
        
        verifier = get_real_name_verifier()
        count = verifier.get_user_count()
        self.count_label.setText(f"当前实名用户: {count}/5 人")
        
        users = verifier.get_all_real_name_users()
        
        self.user_table.setRowCount(len(users))
        for i, user in enumerate(users):
            self.user_table.setItem(i, 0, QTableWidgetItem(user.user_id))
            self.user_table.setItem(i, 1, QTableWidgetItem(user.verification_type.name))
            self.user_table.setItem(i, 2, QTableWidgetItem(user.verified_at[:8]))
            self.user_table.setItem(i, 3, QTableWidgetItem(user.expires_at))
            self.user_table.setItemItem(i, 4, QTableWidgetItem(user.status.name))
            
            # 设置状态颜色
            status_item = self.user_table.item(i, 4)
            if user.status == VerificationStatus.VERIFIED:
                status_item.setBackground(QColor("#1a4d1a"))
                status_item.setForeground(QColor("#4ade80"))
            else:
                status_item.setBackground(QColor("#4d1a1a"))
                status_item.setForeground(QColor("#f87171"))


# ==================== 发行中心面板 ====================

class IssuerPanel(QWidget):
    """激活码发行中心"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
    
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        
        # 标题
        title = QLabel("📊 发行中心")
        title.setObjectName("TitleLabel")
        layout.addWidget(title)
        
        # 生成设置
        settings_group = QGroupBox("生成设置")
        settings_layout = QGridLayout()
        
        # 版本选择
        settings_layout.addWidget(QLabel("版本:"), 0, 0)
        self.version_combo = QComboBox()
        self.version_combo.addItems([
            "PER - 个人版",
            "PRO - 专业版",
            "ENT - 企业版"
        ])
        settings_layout.addWidget(self.version_combo, 0, 1)
        
        # 数量
        settings_layout.addWidget(QLabel("数量:"), 1, 0)
        self.count_spin = QSpinBox()
        self.count_spin.setMinimum(1)
        self.count_spin.setMaximum(100)
        self.count_spin.setValue(10)
        settings_layout.addWidget(self.count_spin, 1, 1)
        
        # 有效期
        settings_layout.addWidget(QLabel("有效期(天):"), 2, 0)
        self.days_spin = QSpinBox()
        self.days_spin.setMinimum(30)
        self.days_spin.setMaximum(3650)
        self.days_spin.setValue(365)
        settings_layout.addWidget(self.days_spin, 2, 1)
        
        # 最大用户数
        settings_layout.addWidget(QLabel("最大用户数:"), 3, 0)
        self.max_users_spin = QSpinBox()
        self.max_users_spin.setMinimum(1)
        self.max_users_spin.setMaximum(5)
        self.max_users_spin.setValue(1)
        settings_layout.addWidget(self.max_users_spin, 3, 1)
        
        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)
        
        # 生成按钮
        self.generate_btn = QPushButton("🎲 生成激活码")
        self.generate_btn.setObjectName("PrimaryButton")
        self.generate_btn.setMinimumHeight(50)
        self.generate_btn.clicked.connect(self._on_generate)
        layout.addWidget(self.generate_btn)
        
        # 生成的激活码列表
        list_group = QGroupBox("生成的激活码")
        list_layout = QVBoxLayout()
        
        self.keys_text = QTextEdit()
        self.keys_text.setReadOnly(True)
        self.keys_text.setFont(QFont("Consolas", 11))
        list_layout.addWidget(self.keys_text)
        
        # 导出按钮
        export_layout = QHBoxLayout()
        self.export_json_btn = QPushButton("导出JSON")
        self.export_json_btn.clicked.connect(self._export_json)
        export_layout.addWidget(self.export_json_btn)
        
        self.export_txt_btn = QPushButton("导出文本")
        self.export_txt_btn.clicked.connect(self._export_txt)
        export_layout.addWidget(self.export_txt_btn)
        
        self.copy_btn = QPushButton("复制全部")
        self.copy_btn.clicked.connect(self._copy_all)
        export_layout.addWidget(self.copy_btn)
        
        list_layout.addLayout(export_layout)
        list_group.setLayout(list_layout)
        layout.addWidget(list_group)
        
        layout.addStretch()
        
        # 存储当前批次
        self.current_batch = None
    
    def _on_generate(self):
        """生成激活码"""
        if not LICENSE_AVAILABLE:
            self.keys_text.setPlainText("授权模块不可用")
            return
        
        version_map = {
            0: LicenseVersion.PERSONAL,
            1: LicenseVersion.PROFESSIONAL,
            2: LicenseVersion.ENTERPRISE
        }
        
        version = version_map[self.version_combo.currentIndex()]
        count = self.count_spin.value()
        days = self.days_spin.value()
        max_users = self.max_users_spin.value()
        
        generator = get_license_generator()
        batch = generator.generate_batch(
            version=version,
            count=count,
            expires_days=days,
            max_users=max_users
        )
        
        self.current_batch = batch
        
        # 显示激活码
        keys_text = '\n'.join([key.key_string for key in batch.keys])
        self.keys_text.setPlainText(keys_text)
    
    def _export_json(self):
        """导出为JSON"""
        if not self.current_batch:
            return
        
        generator = get_license_generator()
        json_data = generator.export_batch_to_json(self.current_batch)
        
        # 复制到剪贴板
        clipboard = QApplication.clipboard()
        clipboard.setText(json_data)
        
        self.keys_text.append("\n\n[已复制JSON到剪贴板]")
    
    def _export_txt(self):
        """导出为文本"""
        if not self.current_batch:
            return
        
        generator = get_license_generator()
        txt_data = generator.export_batch_to_text(self.current_batch)
        
        # 复制到剪贴板
        clipboard = QApplication.clipboard()
        clipboard.setText(txt_data)
        
        self.keys_text.append("\n\n[已复制文本到剪贴板]")
    
    def _copy_all(self):
        """复制全部"""
        text = self.keys_text.toPlainText()
        clipboard = QApplication.clipboard()
        clipboard.setText(text)


# ==================== 设备管理面板 ====================

class DeviceManagementPanel(QWidget):
    """设备管理面板"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._load_devices()
    
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        
        # 标题
        title = QLabel("⚙️ 设备管理")
        title.setObjectName("TitleLabel")
        layout.addWidget(title)
        
        # 当前设备信息
        current_group = QGroupBox("当前设备")
        current_layout = QFormLayout()
        
        self.device_id_label = QLabel()
        current_layout.addRow("设备ID:", self.device_id_label)
        
        self.device_name_label = QLabel()
        current_layout.addRow("设备名称:", self.device_name_label)
        
        self.device_status_label = QLabel()
        self.device_status_label.setStyleSheet("color: #4ade80; font-weight: bold;")
        current_layout.addRow("状态:", self.device_status_label)
        
        current_group.setLayout(current_layout)
        layout.addWidget(current_group)
        
        # 关联设备列表
        list_group = QGroupBox("关联的设备")
        list_layout = QVBoxLayout()
        
        self.device_table = QTableWidget()
        self.device_table.setColumnCount(4)
        self.device_table.setHorizontalHeaderLabels(["设备ID", "设备名称", "最后活跃", "状态"])
        list_layout.addWidget(self.device_table)
        
        list_group.setLayout(list_layout)
        layout.addWidget(list_group)
        
        # 操作按钮
        btn_layout = QHBoxLayout()
        
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self._load_devices)
        btn_layout.addWidget(self.refresh_btn)
        
        self.unbind_btn = QPushButton("解除绑定")
        self.unbind_btn.setStyleSheet("background-color: #dc2626;")
        btn_layout.addWidget(self.unbind_btn)
        
        layout.addLayout(btn_layout)
        
        layout.addStretch()
    
    def _load_devices(self):
        """加载设备信息"""
        # 显示当前设备
        device_id = self._get_device_id()
        self.device_id_label.setText(device_id)
        self.device_name_label.setText(os.getenv('COMPUTERNAME', 'Unknown'))
        self.device_status_label.setText("🟢 在线")
    
    def _get_device_id(self) -> str:
        """获取设备ID"""
        import platform
        machine = platform.node() + platform.machine() + platform.processor()
        return hashlib.sha256(machine.encode()).hexdigest()[:16]


# ==================== 激活日志面板 ====================

class ActivationLogPanel(QWidget):
    """激活日志面板"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._load_logs()
    
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        
        # 标题
        title = QLabel("📜 激活日志")
        title.setObjectName("TitleLabel")
        layout.addWidget(title)
        
        # 日志表格
        self.log_table = QTableWidget()
        self.log_table.setColumnCount(6)
        self.log_table.setHorizontalHeaderLabels([
            "时间", "激活码", "版本", "设备ID", "状态", "详情"
        ])
        layout.addWidget(self.log_table)
        
        # 刷新按钮
        self.refresh_btn = QPushButton("刷新日志")
        self.refresh_btn.clicked.connect(self._load_logs)
        layout.addWidget(self.refresh_btn)
        
        layout.addStretch()
    
    def _load_logs(self):
        """加载日志"""
        if not LICENSE_AVAILABLE:
            # 模拟数据
            self.log_table.setRowCount(3)
            for i in range(3):
                self.log_table.setItem(i, 0, QTableWidgetItem(f"2026-04-{19-i:02d} 10:30:00"))
                self.log_table.setItem(i, 1, QTableWidgetItem(f"ENT-XXXX-XXXX-XXXX-{i}A1B2C3"))
                self.log_table.setItem(i, 2, QTableWidgetItem("PRO"))
                self.log_table.setItem(i, 3, QTableWidgetItem(f"device_{i:04d}"))
                self.log_table.setItem(i, 4, QTableWidgetItem("激活成功"))
                self.log_table.setItem(i, 5, QTableWidgetItem("首次激活"))
            return
        
        validator = get_license_validator()
        # TODO: 实现实际日志加载


# ==================== 主面板 ====================

class ActivationLicensePanel(QWidget):
    """
    智能授权与实名认证系统 - 主面板
    
    集成所有子面板的容器
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ActivationPanel")
        self._build_ui()
    
    def _build_ui(self):
        """构建UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建标签页
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.TabPosition.West)
        
        # 添加各标签页
        self.overview_tab = VersionOverviewPanel()
        self.tabs.addTab(self.overview_tab, "📋 版本概览")
        
        self.activation_tab = ActivationPanel()
        self.tabs.addTab(self.activation_tab, "🔑 激活管理")
        
        self.realname_tab = RealNamePanel()
        self.tabs.addTab(self.realname_tab, "🆔 实名认证")
        
        self.issuer_tab = IssuerPanel()
        self.tabs.addTab(self.issuer_tab, "📊 发行中心")
        
        self.device_tab = DeviceManagementPanel()
        self.tabs.addTab(self.device_tab, "⚙️ 设备管理")
        
        self.log_tab = ActivationLogPanel()
        self.tabs.addTab(self.log_tab, "📜 激活日志")
        
        layout.addWidget(self.tabs)


# ==================== 入口函数 ====================

_panel_instance: Optional[ActivationLicensePanel] = None


def get_activation_license_panel() -> ActivationLicensePanel:
    """获取授权面板单例"""
    global _panel_instance
    if _panel_instance is None:
        _panel_instance = ActivationLicensePanel()
    return _panel_instance


# 兼容旧接口
def show_activation_panel(main_window) -> ActivationLicensePanel:
    """
    在主窗口中显示授权面板
    
    Args:
        main_window: 主窗口对象
    
    Returns:
        ActivationLicensePanel: 授权面板实例
    """
    panel = get_activation_license_panel()
    return panel


# PyQt6 应用导入
from PyQt6.QtWidgets import QApplication