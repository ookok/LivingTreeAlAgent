# -*- coding: utf-8 -*-
"""
Skill Market 面板 - PyQt6 Skill 市场 UI
======================================

功能：
- Skill 浏览与搜索
- Skill 安装/卸载/更新
- Skill 分类筛选
- Skill 配置管理

Author: Hermes Desktop Team
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QLineEdit, QTextEdit, QListWidget,
    QListWidgetItem, QComboBox, QTabWidget, QGroupBox,
    QScrollArea, QFrame, QProgressBar, QTableWidget,
    QTableWidgetItem, QHeaderView, QStatusBar, QMenuBar, QMenu,
    QToolButton, QStackedWidget, QFormLayout, QSpinBox,
    QCheckBox, QMessageBox
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QThread, pyqtSlot, QTimer
from PyQt6.QtGui import QFont, QIcon, QAction, QColor, QPalette
from PyQt6.QtNetwork import QTcpSocket

import asyncio
import json
import time
from datetime import datetime
from typing import Optional, Dict, List

from core.skill_market import (
    Skill, SkillManifest, SkillDatabase,
    SkillStatus, SkillCategory
)


# ==================== Skill 卡片组件 ====================

class SkillCard(QFrame):
    """Skill 卡片组件"""

    install_requested = pyqtSignal(str)  # 安装信号
    uninstall_requested = pyqtSignal(str)  # 卸载信号
    configure_requested = pyqtSignal(str)  # 配置信号
    activate_requested = pyqtSignal(str)  # 激活信号

    def __init__(self, skill: Skill, parent=None):
        super().__init__(parent)
        self.skill = skill
        self._setup_ui()
        self._update_style()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # 头部：图标 + 名称 + 状态徽章
        header = QHBoxLayout()
        
        # 图标
        icon_label = QLabel("🛠️")
        icon_label.setFont(QFont("Segoe UI Emoji", 20))
        header.addWidget(icon_label)
        
        # 名称和类别
        name_layout = QVBoxLayout()
        self.name_label = QLabel(self.skill.name)
        self.name_label.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        name_layout.addWidget(self.name_label)
        
        self.category_label = QLabel(f"📁 {self.skill.category}")
        self.category_label.setFont(QFont("Microsoft YaHei", 9))
        self.category_label.setStyleSheet("color: #888;")
        name_layout.addWidget(self.category_label)
        
        header.addLayout(name_layout)
        header.addStretch()
        
        # 状态徽章
        self.status_badge = QLabel(self._get_status_text())
        self.status_badge.setFont(QFont("Microsoft YaHei", 8))
        self.status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_badge.setFixedWidth(60)
        self._update_status_badge()
        header.addWidget(self.status_badge)
        
        layout.addLayout(header)

        # 描述
        self.desc_label = QLabel(self.skill.description)
        self.desc_label.setWordWrap(True)
        self.desc_label.setStyleSheet("color: #666; font-size: 11px;")
        self.desc_label.setMaximumHeight(40)
        layout.addWidget(self.desc_label)

        # 标签
        if self.skill.tags:
            tags_layout = QHBoxLayout()
            for tag in self.skill.tags[:3]:
                tag_label = QLabel(f"#{tag}")
                tag_label.setStyleSheet("""
                    background-color: #e8f4fd;
                    color: #1890ff;
                    border-radius: 4px;
                    padding: 2px 6px;
                    font-size: 9px;
                """)
                tags_layout.addWidget(tag_label)
            tags_layout.addStretch()
            layout.addLayout(tags_layout)

        # 统计信息
        stats_layout = QHBoxLayout()
        
        # 评分
        self.rating_label = QLabel(f"⭐ {self.skill.rating:.1f}")
        self.rating_label.setFont(QFont("Microsoft YaHei", 9))
        self.rating_label.setStyleSheet("color: #f5a623;")
        stats_layout.addWidget(self.rating_label)
        
        # 下载量
        downloads_label = QLabel(f"⬇️ {self.skill.downloads:,}")
        downloads_label.setFont(QFont("Microsoft YaHei", 9))
        downloads_label.setStyleSheet("color: #888;")
        stats_layout.addWidget(downloads_label)
        
        # 版本
        version_label = QLabel(f"v{self.skill.version}")
        version_label.setFont(QFont("Consolas", 9))
        version_label.setStyleSheet("color: #888;")
        stats_layout.addWidget(version_label)
        
        stats_layout.addStretch()
        layout.addLayout(stats_layout)

        # 操作按钮
        btn_layout = QHBoxLayout()
        
        if self.skill.status == "installed":
            self.action_btn = QPushButton("⚙️ 配置")
            self.action_btn.clicked.connect(lambda: self.configure_requested.emit(self.skill.id))
        else:
            self.action_btn = QPushButton("📥 安装")
            self.action_btn.clicked.connect(lambda: self.install_requested.emit(self.skill.id))
        
        self.action_btn.setFont(QFont("Microsoft YaHei", 9))
        btn_layout.addWidget(self.action_btn)
        
        if self.skill.status == "installed":
            self.uninstall_btn = QPushButton("🗑️ 卸载")
            self.uninstall_btn.setFont(QFont("Microsoft YaHei", 9))
            self.uninstall_btn.setStyleSheet("color: #e74c3c;")
            self.uninstall_btn.clicked.connect(lambda: self.uninstall_requested.emit(self.skill.id))
            btn_layout.addWidget(self.uninstall_btn)
        
        layout.addLayout(btn_layout)

    def _get_status_text(self) -> str:
        status_map = {
            "installed": "已安装",
            "available": "可安装",
            "outdated": "有更新",
            "installing": "安装中",
            "error": "错误"
        }
        return status_map.get(self.skill.status, self.skill.status)

    def _update_status_badge(self):
        colors = {
            "installed": "#2ecc71",
            "available": "#3498db",
            "outdated": "#f39c12",
            "installing": "#9b59b6",
            "error": "#e74c3c"
        }
        color = colors.get(self.skill.status, "#95a5a6")
        self.status_badge.setStyleSheet(f"""
            background-color: {color};
            color: white;
            border-radius: 4px;
            padding: 2px 4px;
        """)

    def _update_style(self):
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setStyleSheet("""
            SkillCard {
                background-color: #fff;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
            }
            SkillCard:hover {
                border-color: #1890ff;
                background-color: #fafafa;
            }
        """)


# ==================== Skill Market Panel ====================

class SkillMarketPanel(QWidget):
    """Skill 市场与管理面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 初始化 Skill 数据库
        self.db_path = "~/.hermes-desktop/skill_market.db"
        self.db = SkillDatabase(self.db_path)
        
        self._setup_ui()
        self._load_skills()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        # 顶部工具栏
        toolbar = QHBoxLayout()
        
        # 搜索框
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 搜索 Skills...")
        self.search_input.textChanged.connect(self._on_search)
        toolbar.addWidget(self.search_input, 1)
        
        # 分类筛选
        self.category_filter = QComboBox()
        self.category_filter.addItems(["全部分类", "general", "writing", "code", "research", "business", "creative", "document", "data", "custom"])
        self.category_filter.currentTextChanged.connect(self._on_filter_changed)
        toolbar.addWidget(self.category_filter)
        
        # 状态筛选
        self.status_filter = QComboBox()
        self.status_filter.addItems(["全部状态", "已安装", "可安装", "有更新"])
        self.status_filter.currentTextChanged.connect(self._on_filter_changed)
        toolbar.addWidget(self.status_filter)
        
        # 刷新按钮
        self.refresh_btn = QPushButton("🔄 刷新")
        self.refresh_btn.clicked.connect(self._load_skills)
        toolbar.addWidget(self.refresh_btn)
        
        main_layout.addLayout(toolbar)

        # 标签页
        self.tabs = QTabWidget()
        
        # 我的 Skills 标签
        self.my_skills_tab = QWidget()
        self._setup_my_skills_tab()
        self.tabs.addTab(self.my_skills_tab, "📦 我的 Skills")
        
        # 市场标签
        self.market_tab = QWidget()
        self._setup_market_tab()
        self.tabs.addTab(self.market_tab, "🏪 发现市场")
        
        # 模板标签
        self.templates_tab = QWidget()
        self._setup_templates_tab()
        self.tabs.addTab(self.templates_tab, "📋 模板市场")
        
        main_layout.addWidget(self.tabs)

    def _setup_my_skills_tab(self):
        layout = QVBoxLayout(self.my_skills_tab)
        
        # Skill 列表（滚动区域）
        self.skills_scroll = QScrollArea()
        self.skills_scroll.setWidgetResizable(True)
        self.skills_scroll.setStyleSheet("border: none;")
        
        self.skills_container = QWidget()
        self.skills_grid = QGridLayout(self.skills_container)
        self.skills_grid.setSpacing(12)
        self.skills_grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        
        self.skills_scroll.setWidget(self.skills_container)
        layout.addWidget(self.skills_scroll)

    def _setup_market_tab(self):
        layout = QVBoxLayout(self.market_tab)
        
        # 市场信息
        info_label = QLabel("🌐 从社区发现和安装 Skills")
        info_label.setFont(QFont("Microsoft YaHei", 10))
        info_label.setStyleSheet("color: #666; padding: 8px;")
        layout.addWidget(info_label)
        
        # 市场 Skill 列表
        self.market_list = QListWidget()
        self.market_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                background-color: #fff;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #f0f0f0;
            }
            QListWidget::item:selected {
                background-color: #e6f7ff;
            }
        """)
        layout.addWidget(self.market_list)

    def _setup_templates_tab(self):
        layout = QVBoxLayout(self.templates_tab)
        
        info_label = QLabel("📋 使用模板快速创建 Skill")
        info_label.setFont(QFont("Microsoft YaHei", 10))
        info_label.setStyleSheet("color: #666; padding: 8px;")
        layout.addWidget(info_label)
        
        # 模板列表
        self.templates_list = QListWidget()
        self.templates_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                background-color: #fff;
            }
        """)
        layout.addWidget(self.templates_list)
        
        # 创建按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.create_skill_btn = QPushButton("➕ 从模板创建")
        self.create_skill_btn.clicked.connect(self._on_create_from_template)
        btn_layout.addWidget(self.create_skill_btn)
        
        layout.addLayout(btn_layout)

    def _load_skills(self):
        """加载 Skill 列表"""
        # 从数据库加载
        skills = self.db.get_all_skills()
        
        # 清空现有卡片
        while self.skills_grid.count():
            item = self.skills_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # 添加 Skill 卡片
        for i, skill in enumerate(skills):
            card = SkillCard(skill)
            card.install_requested.connect(self._on_install)
            card.uninstall_requested.connect(self._on_uninstall)
            card.configure_requested.connect(self._on_configure)
            
            row = i // 2
            col = i % 2
            self.skills_grid.addWidget(card, row, col)

    def _on_search(self, text: str):
        """搜索过滤"""
        for i in range(self.skills_grid.count()):
            widget = self.skills_grid.itemAt(i).widget()
            if widget and isinstance(widget, SkillCard):
                visible = text.lower() in widget.skill.name.lower() or text.lower() in widget.skill.description.lower()
                widget.setVisible(visible)

    def _on_filter_changed(self):
        """分类/状态过滤"""
        category = self.category_filter.currentText()
        status = self.status_filter.currentText()
        
        for i in range(self.skills_grid.count()):
            widget = self.skills_grid.itemAt(i).widget()
            if widget and isinstance(widget, SkillCard):
                visible = True
                
                if category != "全部分类":
                    visible = visible and widget.skill.category == category
                
                if status != "全部状态":
                    status_map = {"已安装": "installed", "可安装": "available", "有更新": "outdated"}
                    visible = visible and widget.skill.status == status_map.get(status, "")
                
                widget.setVisible(visible)

    def _on_install(self, skill_id: str):
        """安装 Skill"""
        skill = self.db.get_skill(skill_id)
        if not skill:
            return
        
        skill.status = "installing"
        skill.installed_at = time.time()
        self.db.update_skill(skill)
        self._load_skills()
        
        # 模拟安装过程
        QTimer.singleShot(1000, lambda: self._complete_install(skill_id))

    def _complete_install(self, skill_id: str):
        """完成安装"""
        skill = self.db.get_skill(skill_id)
        if skill:
            skill.status = "installed"
            self.db.update_skill(skill)
            self._load_skills()

    def _on_uninstall(self, skill_id: str):
        """卸载 Skill"""
        reply = QMessageBox.question(
            self, "确认卸载", "确定要卸载这个 Skill 吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            skill = self.db.get_skill(skill_id)
            if skill:
                skill.status = "available"
                skill.installed_at = 0
                self.db.update_skill(skill)
                self._load_skills()

    def _on_configure(self, skill_id: str):
        """配置 Skill"""
        skill = self.db.get_skill(skill_id)
        if not skill:
            return
        
        from PyQt6.QtWidgets import QDialog, QFormLayout
        
        dialog = QDialog(self)
        dialog.setWindowTitle(f"配置 {skill.name}")
        dialog.setMinimumWidth(400)
        
        layout = QFormLayout(dialog)
        
        name_input = QLineEdit(skill.name)
        layout.addRow("名称:", name_input)
        
        desc_input = QTextEdit(skill.description)
        desc_input.setMaximumHeight(80)
        layout.addRow("描述:", desc_input)
        
        triggers_input = QLineEdit(", ".join(skill.triggers) if skill.triggers else "")
        layout.addRow("触发词:", triggers_input)
        
        btns = QHBoxLayout()
        ok_btn = QPushButton("保存")
        ok_btn.clicked.connect(dialog.accept)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(dialog.reject)
        btns.addWidget(ok_btn)
        btns.addWidget(cancel_btn)
        layout.addRow(btns)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            skill.name = name_input.text()
            skill.description = desc_input.toPlainText()
            skill.triggers = [t.strip() for t in triggers_input.text().split(",") if t.strip()]
            skill.updated_at = time.time()
            self.db.update_skill(skill)
            self._load_skills()

    def _on_create_from_template(self):
        """从模板创建 Skill"""
        from PyQt6.QtWidgets import QDialog, QFormLayout
        
        dialog = QDialog(self)
        dialog.setWindowTitle("从模板创建 Skill")
        dialog.setMinimumWidth(400)
        
        layout = QFormLayout(dialog)
        
        name_input = QLineEdit()
        name_input.setPlaceholderText("Skill 名称")
        layout.addRow("名称:", name_input)
        
        desc_input = QTextEdit()
        desc_input.setPlaceholderText("Skill 描述")
        desc_input.setMaximumHeight(80)
        layout.addRow("描述:", desc_input)
        
        category_combo = QComboBox()
        category_combo.addItems(["general", "writing", "code", "research", "business", "creative", "document", "data", "custom"])
        layout.addRow("分类:", category_combo)
        
        triggers_input = QLineEdit()
        triggers_input.setPlaceholderText("触发词 (逗号分隔)")
        layout.addRow("触发词:", triggers_input)
        
        btns = QHBoxLayout()
        ok_btn = QPushButton("创建")
        ok_btn.clicked.connect(dialog.accept)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(dialog.reject)
        btns.addWidget(ok_btn)
        btns.addWidget(cancel_btn)
        layout.addRow(btns)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            skill = Skill(
                id=f"local_{int(time.time())}",
                name=name_input.text() or "Unnamed Skill",
                description=desc_input.toPlainText(),
                category=category_combo.currentText(),
                version="1.0.0",
                source="local",
                status="available",
                triggers=[t.strip() for t in triggers_input.text().split(",") if t.strip()]
            )
            self.db.add_skill(skill)
            self._load_skills()


# ==================== 导出 ====================

__all__ = ['SkillMarketPanel', 'SkillCard']
