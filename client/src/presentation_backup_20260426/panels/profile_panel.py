"""
Profile 管理面板 - ProfilePanel
多实例配置管理
参考 hermes-agent profiles.py 设计
"""

from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QGroupBox, QScrollArea,
    QLineEdit, QComboBox, QCheckBox, QTextEdit,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QFrame, QStackedWidget, QDialog, QMessageBox,
    QFormLayout, QFileDialog, QInputDialog,
)
from PyQt6.QtGui import QFont, QIcon

from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

from .business.profiles import (
    get_profile_manager, ProfileInfo, ProfileManager,
    create_profile, delete_profile, rename_profile,
    export_profile, import_profile, get_active_profile,
    set_active_profile, profile_exists,
)


class ProfileCard(QFrame):
    """Profile 卡片"""
    
    profile_selected = pyqtSignal(str)
    profile_deleted = pyqtSignal(str)
    
    def __init__(self, profile: ProfileInfo, is_active: bool = False, parent=None):
        super().__init__(parent)
        self.profile = profile
        self.is_active = is_active
        self._init_ui()
    
    def _init_ui(self):
        # 样式
        if self.is_active:
            self.setStyleSheet("""
                ProfileCard {
                    background: #252540;
                    border: 2px solid #5a5aff;
                    border-radius: 10px;
                    padding: 16px;
                }
            """)
        else:
            self.setStyleSheet("""
                ProfileCard {
                    background: #1e1e1e;
                    border: 1px solid #333;
                    border-radius: 10px;
                    padding: 16px;
                }
                ProfileCard:hover {
                    border-color: #5a5aff;
                }
            """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        # 头部
        header = QHBoxLayout()
        
        # 名称
        name_layout = QVBoxLayout()
        
        name_label = QLabel(self.profile.name)
        name_label.setStyleSheet("color: #e8e8e8; font-size: 16px; font-weight: 600;")
        name_layout.addWidget(name_label)
        
        if self.is_active:
            active_badge = QLabel("ACTIVE")
            active_badge.setStyleSheet("""
                background: #5a5aff;
                color: white;
                font-size: 9px;
                padding: 2px 6px;
                border-radius: 3px;
            """)
            name_layout.addWidget(active_badge)
        
        header.addLayout(name_layout)
        
        # Gateway 状态
        if self.profile.gateway_running:
            gw_status = QLabel("GATEWAY")
            gw_status.setStyleSheet("""
                background: #4ade80;
                color: #1a1a1a;
                font-size: 9px;
                padding: 2px 6px;
                border-radius: 3px;
            """)
        else:
            gw_status = QLabel("STOPPED")
            gw_status.setStyleSheet("""
                background: #333;
                color: #888;
                font-size: 9px;
                padding: 2px 6px;
                border-radius: 3px;
            """)
        header.addWidget(gw_status)
        
        layout.addLayout(header)
        
        # 路径
        path_label = QLabel(str(self.profile.path))
        path_label.setStyleSheet("color: #666; font-size: 11px;")
        path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(path_label)
        
        # 信息
        info_layout = QHBoxLayout()
        info_layout.setSpacing(16)
        
        # 模型
        if self.profile.model:
            model_label = QLabel(f"Model: {self.profile.model}")
            model_label.setStyleSheet("color: #888; font-size: 11px;")
            info_layout.addWidget(model_label)
        
        # Skills
        skills_label = QLabel(f"Skills: {self.profile.skill_count}")
        skills_label.setStyleSheet("color: #888; font-size: 11px;")
        info_layout.addWidget(skills_label)
        
        # .env
        if self.profile.has_env:
            env_label = QLabel("ENV")
            env_label.setStyleSheet("""
                background: #4ade80;
                color: #1a1a1a;
                font-size: 9px;
                padding: 2px 6px;
                border-radius: 3px;
            """)
            info_layout.addWidget(env_label)
        
        info_layout.addStretch()
        layout.addLayout(info_layout)
        
        # 操作按钮
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        
        if not self.is_active:
            activate_btn = QPushButton("Activate")
            activate_btn.setStyleSheet("""
                QPushButton {
                    background: #5a5aff;
                    color: white;
                    border: none;
                    border-radius: 6px;
                    padding: 6px 14px;
                    font-size: 12px;
                }
                QPushButton:hover { background: #4a4aef; }
            """)
            activate_btn.clicked.connect(self._on_activate)
            btn_layout.addWidget(activate_btn)
        
        export_btn = QPushButton("Export")
        export_btn.setStyleSheet("""
            QPushButton {
                background: #333;
                color: #ccc;
                border: none;
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 12px;
            }
            QPushButton:hover { background: #444; }
        """)
        export_btn.clicked.connect(self._on_export)
        btn_layout.addWidget(export_btn)
        
        if not self.profile.is_default:
            delete_btn = QPushButton("Delete")
            delete_btn.setStyleSheet("""
                QPushButton {
                    background: #f87171;
                    color: white;
                    border: none;
                    border-radius: 6px;
                    padding: 6px 14px;
                    font-size: 12px;
                }
                QPushButton:hover { background: #ef4444; }
            """)
            delete_btn.clicked.connect(self._on_delete)
            btn_layout.addWidget(delete_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
    
    def _on_activate(self):
        """激活 Profile"""
        try:
            set_active_profile(self.profile.name)
            self.profile_selected.emit(self.profile.name)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to activate: {e}")
    
    def _on_export(self):
        """导出 Profile"""
        default_name = f"{self.profile.name}_{datetime.now().strftime('%Y%m%d')}.tar.gz"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Profile", default_name,
            "Archive (*.tar.gz)"
        )
        
        if file_path:
            try:
                export_profile(self.profile.name, file_path)
                QMessageBox.information(self, "Success", f"Profile exported to {file_path}")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Export failed: {e}")
    
    def _on_delete(self):
        """删除 Profile"""
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete profile '{self.profile.name}'?\n\nThis will permanently delete all data.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                delete_profile(self.profile.name)
                self.profile_deleted.emit(self.profile.name)
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Delete failed: {e}")


class ProfilePanel(QWidget):
    """Profile 管理面板主组件"""
    
    profile_changed = pyqtSignal(str)  # profile_name
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.manager = get_profile_manager()
        self._init_ui()
    
    def _init_ui(self):
        self.setStyleSheet("background: #151515;")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        
        # 标题栏
        header = QHBoxLayout()
        
        title = QLabel("Profiles / 配置方案")
        title.setStyleSheet("""
            color: #e8e8e8;
            font-size: 20px;
            font-weight: 700;
        """)
        header.addWidget(title)
        
        header.addStretch()
        
        # 操作按钮
        import_btn = QPushButton("Import")
        import_btn.clicked.connect(self._on_import)
        import_btn.setStyleSheet("""
            QPushButton {
                background: #333;
                color: #ccc;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
            }
            QPushButton:hover { background: #444; }
        """)
        header.addWidget(import_btn)
        
        create_btn = QPushButton("Create New")
        create_btn.clicked.connect(self._on_create)
        create_btn.setStyleSheet("""
            QPushButton {
                background: #5a5aff;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 600;
            }
            QPushButton:hover { background: #4a4aef; }
        """)
        header.addWidget(create_btn)
        
        layout.addLayout(header)
        
        # 说明
        info = QLabel(
            "Profiles allow you to run multiple isolated Hermes instances with different configurations. "
            "Each profile has its own config, API keys, memories, sessions, and skills."
        )
        info.setStyleSheet("color: #666; font-size: 12px; padding: 8px 0;")
        info.setWordWrap(True)
        layout.addWidget(info)
        
        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none;")
        
        content = QWidget()
        self.content_layout = QVBoxLayout(content)
        self.content_layout.setSpacing(16)
        
        # 加载 Profile
        self._load_profiles()
        
        self.content_layout.addStretch()
        
        scroll.setWidget(content)
        layout.addWidget(scroll)
    
    def _load_profiles(self):
        """加载 Profile 列表"""
        # 清除现有
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # 当前活跃 Profile
        active_profile = get_active_profile()
        
        # 获取所有 Profile
        profiles = self.manager.get_all_profiles()
        
        if not profiles:
            empty_label = QLabel("No profiles found. Create one to get started.")
            empty_label.setStyleSheet("color: #888; padding: 40px; text-align: center;")
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.content_layout.addWidget(empty_label)
            return
        
        # 显示卡片
        for profile in profiles:
            is_active = profile.name == active_profile
            card = ProfileCard(profile, is_active)
            card.profile_selected.connect(self._on_profile_selected)
            card.profile_deleted.connect(self._on_profile_deleted)
            self.content_layout.addWidget(card)
    
    def _on_profile_selected(self, profile_name: str):
        """Profile 被选中"""
        self.profile_changed.emit(profile_name)
        self._load_profiles()  # 刷新 UI
    
    def _on_profile_deleted(self, profile_name: str):
        """Profile 被删除"""
        self._load_profiles()  # 刷新 UI
    
    def _on_create(self):
        """创建新 Profile"""
        dialog = CreateProfileDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            name = dialog.get_profile_name()
            clone_from = dialog.get_clone_from()
            
            try:
                create_profile(name, clone_from)
                self._load_profiles()
                QMessageBox.information(self, "Success", f"Profile '{name}' created!")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to create profile: {e}")
    
    def _on_import(self):
        """导入 Profile"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Profile", "",
            "Archive (*.tar.gz *.tgz)"
        )
        
        if file_path:
            # 询问名称
            name, ok = QInputDialog.getText(
                self, "Import Profile",
                "Enter profile name (leave empty to auto-detect):"
            )
            
            if ok:
                try:
                    profile_dir = import_profile(file_path, name or None)
                    self._load_profiles()
                    QMessageBox.information(
                        self, "Success",
                        f"Profile imported to {profile_dir}!"
                    )
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Import failed: {e}")
    
    def refresh(self):
        """刷新"""
        self._load_profiles()


class CreateProfileDialog(QDialog):
    """创建 Profile 对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create Profile / 创建配置方案")
        self.setMinimumSize(400, 200)
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        
        # 名称
        name_layout = QFormLayout()
        
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("my-profile")
        self.name_input.setStyleSheet("""
            QLineEdit {
                background: #252525;
                border: 1px solid #333;
                border-radius: 6px;
                padding: 10px;
                color: #ccc;
            }
            QLineEdit:focus { border-color: #5a5aff; }
        """)
        name_layout.addRow("Name:", self.name_input)
        
        layout.addLayout(name_layout)
        
        # 克隆选项
        clone_layout = QHBoxLayout()
        
        clone_label = QLabel("Clone from:")
        clone_label.setStyleSheet("color: #888;")
        clone_layout.addWidget(clone_label)
        
        self.clone_combo = QComboBox()
        self.clone_combo.addItem("None (empty)", None)
        self.clone_combo.addItem("default", "default")
        
        # 添加现有 profiles
        profiles = get_profile_manager().get_all_profiles()
        for profile in profiles:
            if not profile.is_default:
                self.clone_combo.addItem(profile.name, profile.name)
        
        self.clone_combo.setStyleSheet("""
            QComboBox {
                background: #252525;
                border: 1px solid #333;
                border-radius: 6px;
                padding: 8px;
                color: #ccc;
            }
            QComboBox::drop-down { border: none; }
        """)
        clone_layout.addWidget(self.clone_combo, 1)
        
        layout.addLayout(clone_layout)
        
        # 说明
        info = QLabel(
            "Profile names must be lowercase alphanumeric, "
            "can contain hyphens and underscores (e.g., 'work-profile', 'dev_1')."
        )
        info.setStyleSheet("color: #666; font-size: 11px;")
        info.setWordWrap(True)
        layout.addWidget(info)
        
        layout.addStretch()
        
        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        create_btn = QPushButton("Create")
        create_btn.setStyleSheet("""
            QPushButton {
                background: #5a5aff;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-weight: 600;
            }
            QPushButton:hover { background: #4a4aef; }
        """)
        create_btn.clicked.connect(self._on_create)
        btn_layout.addWidget(create_btn)
        
        layout.addLayout(btn_layout)
    
    def _on_create(self):
        """创建"""
        name = self.name_input.text().strip()
        
        if not name:
            QMessageBox.warning(self, "Error", "Please enter a profile name")
            return
        
        if not profile_exists(name):
            self.accept()
        else:
            QMessageBox.warning(self, "Error", f"Profile '{name}' already exists")
    
    def get_profile_name(self) -> str:
        """获取 Profile 名称"""
        return self.name_input.text().strip()
    
    def get_clone_from(self) -> Optional[str]:
        """获取克隆源"""
        return self.clone_combo.currentData()
