"""
个人资料面板 - 对接真实用户配置
"""

import json
import os
from pathlib import Path
from typing import Optional, Dict

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QFormLayout,
    QGroupBox, QMessageBox, QFileDialog,
    QTextEdit, QComboBox,
)
from PyQt6.QtGui import QFont, QPixmap

from client.src.business.nanochat_config import config


# ── 个人资料面板 ─────────────────────────────────────────────────────

class ProfilePanel(QWidget):
    """个人资料面板 - 对接真实用户配置"""

    profile_updated = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._profile_data = {}
        self._config_file = Path.home() / ".livingtree" / "user_profile.json"
        self._setup_ui()
        self._load_profile()

    def _setup_ui(self):
        """构建UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # 标题
        title = QLabel("👤 个人资料")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(title)

        # 描述
        desc = QLabel("个人资料 - 查看和编辑个人信息")
        desc.setStyleSheet("font-size: 14px; color: #666;")
        layout.addWidget(desc)

        # 头像
        avatar_group = QGroupBox("头像")
        avatar_layout = QHBoxLayout(avatar_group)

        self.avatar_label = QLabel()
        self.avatar_label.setFixedSize(100, 100)
        self.avatar_label.setStyleSheet("""
            border: 1px solid #ccc;
            border-radius: 50px;
            background: #f0f0f0;
        """)
        self.avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avatar_label.setText("暂无头像")
        avatar_layout.addWidget(self.avatar_label)

        avatar_btn_layout = QVBoxLayout()

        upload_btn = QPushButton("上传头像")
        upload_btn.clicked.connect(self._upload_avatar)
        avatar_btn_layout.addWidget(upload_btn)

        remove_btn = QPushButton("移除头像")
        remove_btn.clicked.connect(self._remove_avatar)
        avatar_btn_layout.addWidget(remove_btn)

        avatar_btn_layout.addStretch()

        avatar_layout.addLayout(avatar_btn_layout)
        avatar_layout.addStretch()
        layout.addWidget(avatar_group)

        # 基本信息
        info_group = QGroupBox("基本信息")
        info_layout = QFormLayout(info_group)

        self.name_edit = QLineEdit()
        info_layout.addRow("姓名:", self.name_edit)

        self.email_edit = QLineEdit()
        info_layout.addRow("邮箱:", self.email_edit)

        self.phone_edit = QLineEdit()
        info_layout.addRow("电话:", self.phone_edit)

        self.bio_edit = QTextEdit()
        self.bio_edit.setMaximumHeight(100)
        info_layout.addRow("个人简介:", self.bio_edit)

        layout.addWidget(info_group)

        # 偏好设置
        pref_group = QGroupBox("偏好设置")
        pref_layout = QFormLayout(pref_group)

        self.language_combo = QComboBox()
        self.language_combo.addItems(["中文", "English", "日本語", "한국어"])
        pref_layout.addRow("语言:", self.language_combo)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["浅色", "深色", "自动"])
        pref_layout.addRow("主题:", self.theme_combo)

        layout.addWidget(pref_group)

        # 按钮
        btn_layout = QHBoxLayout()

        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self._save_profile)
        btn_layout.addWidget(save_btn)

        reset_btn = QPushButton("重置")
        reset_btn.clicked.connect(self._reset_profile)
        btn_layout.addWidget(reset_btn)

        btn_layout.addStretch()

        layout.addLayout(btn_layout)

    def _load_profile(self):
        """加载个人资料（从 JSON 文件）"""
        if self._config_file.exists():
            try:
                with open(self._config_file, "r", encoding="utf-8") as f:
                    self._profile_data = json.load(f)
            except Exception as e:
                QMessageBox.warning(self, "警告", f"加载个人资料失败: {e}")
                self._profile_data = {}
        else:
            # 默认数据
            self._profile_data = {
                "name": "用户",
                "email": "user@example.com",
                "phone": "13800138000",
                "bio": "这是一个示例个人简介。",
                "language": "中文",
                "theme": "自动",
                "avatar": None,
            }

        # 更新UI
        self.name_edit.setText(self._profile_data.get("name", ""))
        self.email_edit.setText(self._profile_data.get("email", ""))
        self.phone_edit.setText(self._profile_data.get("phone", ""))
        self.bio_edit.setText(self._profile_data.get("bio", ""))

        # 设置语言
        index = self.language_combo.findText(self._profile_data.get("language", "中文"))
        if index >= 0:
            self.language_combo.setCurrentIndex(index)

        # 设置主题
        index = self.theme_combo.findText(self._profile_data.get("theme", "自动"))
        if index >= 0:
            self.theme_combo.setCurrentIndex(index)

        # 设置头像
        avatar_path = self._profile_data.get("avatar")
        if avatar_path and Path(avatar_path).exists():
            pixmap = QPixmap(avatar_path)
            pixmap = pixmap.scaled(100, 100, Qt.AspectRatioMode.KeepAspectRatio)
            self.avatar_label.setPixmap(pixmap)
            self.avatar_label.setText("")
        else:
            self.avatar_label.setPixmap(QPixmap())
            self.avatar_label.setText("暂无头像")

    def _upload_avatar(self):
        """上传头像"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择头像", "", "Image Files (*.png *.jpg *.jpeg *.bmp)"
        )

        if file_path:
            # 复制到用户目录
            avatar_dir = self._config_file.parent / "avatars"
            avatar_dir.mkdir(parents=True, exist_ok=True)

            import shutil
            new_path = avatar_dir / Path(file_path).name
            shutil.copy(file_path, new_path)

            # 显示头像
            pixmap = QPixmap(str(new_path))
            pixmap = pixmap.scaled(100, 100, Qt.AspectRatioMode.KeepAspectRatio)
            self.avatar_label.setPixmap(pixmap)
            self.avatar_label.setText("")

            self._profile_data["avatar"] = str(new_path)

    def _remove_avatar(self):
        """移除头像"""
        self.avatar_label.setPixmap(QPixmap())
        self.avatar_label.setText("暂无头像")
        self._profile_data["avatar"] = None

    def _save_profile(self):
        """保存个人资料"""
        # 获取UI数据
        self._profile_data["name"] = self.name_edit.text()
        self._profile_data["email"] = self.email_edit.text()
        self._profile_data["phone"] = self.phone_edit.text()
        self._profile_data["bio"] = self.bio_edit.toPlainText()
        self._profile_data["language"] = self.language_combo.currentText()
        self._profile_data["theme"] = self.theme_combo.currentText()

        # 验证
        if not self._profile_data["name"]:
            QMessageBox.warning(self, "警告", "姓名不能为空")
            return

        if "@" not in self._profile_data["email"]:
            QMessageBox.warning(self, "警告", "邮箱格式不正确")
            return

        # 保存到文件
        try:
            self._config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._config_file, "w", encoding="utf-8") as f:
                json.dump(self._profile_data, f, ensure_ascii=False, indent=2)

            self.profile_updated.emit(self._profile_data)
            QMessageBox.information(self, "成功", "个人资料保存成功！")

        except Exception as e:
            QMessageBox.warning(self, "警告", f"保存失败: {e}")

    def _reset_profile(self):
        """重置个人资料"""
        reply = QMessageBox.question(
            self, "确认重置",
            "确定要重置个人资料吗？所有未保存的更改将丢失。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self._load_profile()
            QMessageBox.information(self, "成功", "个人资料已重置")
