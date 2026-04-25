# -*- coding: utf-8 -*-
"""
Avatar 面板 - PyQt6 数字分身 UI
================================

功能：
- 数字分身状态查看
- 三层分身模型（核心层/行为层/记忆层）
- 成长系统（经验值/等级）
- 主动交互系统

Author: Hermes Desktop Team
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QLineEdit, QTextEdit, QListWidget,
    QListWidgetItem, QComboBox, QTabWidget, QGroupBox,
    QScrollArea, QFrame, QProgressBar, QTableWidget,
    QTableWidgetItem, QHeaderView, QStatusBar, QMenuBar, QMenu,
    QToolButton, QStackedWidget, QFormLayout, QSpinBox,
    QCheckBox, QMessageBox, QSlider, QDial
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QThread, pyqtSlot, QTimer
from PyQt6.QtGui import QFont, QIcon, QAction, QColor, QPalette, QPainter, QPen, QBrush, QConicalGradient

import asyncio
import json
import time
from datetime import datetime
from typing import Optional, Dict, List

from client.src.business.digital_avatar import (
    DigitalAvatar, AvatarDatabase, AvatarLevel, GrowthEvent
)


# ==================== 等级进度环组件 ====================

class LevelRing(QFrame):
    """等级进度环组件"""

    def __init__(self, level: int, exp: int, max_exp: int, parent=None):
        super().__init__(parent)
        self.level = level
        self.exp = exp
        self.max_exp = max_exp
        self.setMinimumSize(120, 120)
        self.setMaximumSize(120, 120)

    def set_progress(self, level: int, exp: int, max_exp: int):
        self.level = level
        self.exp = exp
        self.max_exp = max_exp
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 背景圆环
        rect = self.rect().adjusted(10, 10, -10, -10)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor("#e0e0e0")))
        painter.drawEllipse(rect)
        
        # 进度圆环
        if self.max_exp > 0:
            progress = self.exp / self.max_exp
            painter.setPen(QPen(QColor("#1890ff"), 8))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawArc(rect, 90 * 16, -int(progress * 360 * 16))
        
        # 中心文字
        painter.setPen(QPen(QColor("#333")))
        painter.setFont(QFont("Microsoft YaHei", 16, QFont.Weight.Bold))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, f"Lv{self.level}")
        
        painter.setFont(QFont("Microsoft YaHei", 8))
        painter.setPen(QPen(QColor("#888")))
        painter.drawText(self.rect().adjusted(0, 20, 0, 0), Qt.AlignmentFlag.AlignCenter, f"{self.exp}/{self.max_exp} EXP")


# ==================== 分身层级卡片 ====================

class AvatarLayerCard(QFrame):
    """分身层级卡片组件"""

    def __init__(self, layer_name: str, layer_desc: str, data: Dict, parent=None):
        super().__init__(parent)
        self.layer_name = layer_name
        self.layer_desc = layer_desc
        self.data = data
        self._setup_ui()
        self._update_style()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # 层级名称
        header = QHBoxLayout()
        self.icon_label = QLabel(self._get_layer_icon())
        self.icon_label.setFont(QFont("Segoe UI Emoji", 20))
        header.addWidget(self.icon_label)
        
        self.name_label = QLabel(self.layer_name)
        self.name_label.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        header.addWidget(self.name_label)
        header.addStretch()
        
        layout.addLayout(header)

        # 描述
        self.desc_label = QLabel(self.layer_desc)
        self.desc_label.setWordWrap(True)
        self.desc_label.setStyleSheet("color: #666; font-size: 10px;")
        layout.addWidget(self.desc_label)

        # 数据展示
        self.data_text = QTextEdit()
        self.data_text.setReadOnly(True)
        self.data_text.setMaximumHeight(100)
        self.data_text.setStyleSheet("""
            QTextEdit {
                background-color: #f5f5f5;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                font-family: Consolas;
                font-size: 10px;
            }
        """)
        self.data_text.setPlainText(json.dumps(self.data, ensure_ascii=False, indent=2))
        layout.addWidget(self.data_text)

    def _get_layer_icon(self) -> str:
        icons = {
            "核心层": "🎯",
            "行为层": "🧠",
            "记忆层": "📚"
        }
        return icons.get(self.layer_name, "📦")

    def _update_style(self):
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setStyleSheet("""
            AvatarLayerCard {
                background-color: #fff;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
            }
        """)

    def update_data(self, data: Dict):
        self.data = data
        self.data_text.setPlainText(json.dumps(data, ensure_ascii=False, indent=2))


# ==================== 成长事件卡片 ====================

class GrowthEventCard(QFrame):
    """成长事件卡片"""

    def __init__(self, event: GrowthEvent, parent=None):
        super().__init__(parent)
        self.event = event
        self._setup_ui()
        self._update_style()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        # 图标
        icon_label = QLabel("📈")
        icon_label.setFont(QFont("Segoe UI Emoji", 16))
        layout.addWidget(icon_label)

        # 事件信息
        info_layout = QVBoxLayout()
        
        self.type_label = QLabel(f"[{self.event.type}]")
        self.type_label.setFont(QFont("Microsoft YaHei", 9, QFont.Weight.Bold))
        info_layout.addWidget(self.type_label)
        
        self.desc_label = QLabel(self.event.description)
        self.desc_label.setFont(QFont("Microsoft YaHei", 10))
        self.desc_label.setWordWrap(True)
        info_layout.addWidget(self.desc_label)
        
        layout.addLayout(info_layout)
        layout.addStretch()

        # 经验值
        exp_label = QLabel(f"+{self.event.exp_gained} EXP")
        exp_label.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        exp_label.setStyleSheet("color: #2ecc71;")
        layout.addWidget(exp_label)

    def _update_style(self):
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setStyleSheet("""
            GrowthEventCard {
                background-color: #fff;
                border: 1px solid #e0e0e0;
                border-radius: 6px;
            }
        """)


# ==================== Avatar Panel ====================

class AvatarPanel(QWidget):
    """数字分身管理面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 初始化 Avatar 数据库
        self.db_path = "~/.hermes-desktop/digital_avatar.db"
        self.db = AvatarDatabase(self.db_path)
        
        # 获取或创建当前分身
        self.avatar = self._get_or_create_avatar()
        
        self._setup_ui()
        self._update_display()

    def _get_or_create_avatar(self) -> DigitalAvatar:
        """获取或创建默认分身"""
        avatar = self.db.get_avatar("default_user")
        if not avatar:
            avatar = DigitalAvatar(
                id=1,
                user_id="default_user",
                declared_interests=["编程", "AI", "技术"],
                level=1,
                experience=0
            )
            self.db.create_avatar(avatar)
        return avatar

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        # 顶部：等级环 + 统计
        top_layout = QHBoxLayout()
        
        # 等级进度环
        max_exp = self._calculate_max_exp(self.avatar.level)
        self.level_ring = LevelRing(self.avatar.level, self.avatar.experience, max_exp)
        top_layout.addWidget(self.level_ring)
        
        # 统计信息
        stats_layout = QVBoxLayout()
        
        stats_layout.addWidget(QLabel("📊 分身数据统计"))
        stats_layout.addSpacing(8)
        
        self.exp_label = QLabel(f"经验值: {self.avatar.experience}")
        stats_layout.addWidget(self.exp_label)
        
        self.level_label = QLabel(f"等级: {self.avatar.level} ({AvatarLevel(self.avatar.level).name})")
        stats_layout.addWidget(self.level_label)
        
        self.features_label = QLabel(f"已解锁功能: {len(self.avatar.unlocked_features)}")
        stats_layout.addWidget(self.features_label)
        
        stats_layout.addStretch()
        top_layout.addLayout(stats_layout)
        
        # 快捷操作
        actions_layout = QVBoxLayout()
        
        evolve_btn = QPushButton("🚀 触发进化")
        evolve_btn.clicked.connect(self._on_evolve)
        actions_layout.addWidget(evolve_btn)
        
        reset_btn = QPushButton("🔄 重置分身")
        reset_btn.setStyleSheet("color: #e74c3c;")
        reset_btn.clicked.connect(self._on_reset)
        actions_layout.addWidget(reset_btn)
        
        export_btn = QPushButton("📤 导出数据")
        export_btn.clicked.connect(self._on_export)
        actions_layout.addWidget(export_btn)
        
        top_layout.addLayout(actions_layout)
        main_layout.addLayout(top_layout)

        # 标签页：核心层 / 行为层 / 记忆层 / 成长记录
        self.tabs = QTabWidget()
        
        # 核心层
        self.core_tab = QWidget()
        self._setup_core_tab()
        self.tabs.addTab(self.core_tab, "🎯 核心层")
        
        # 行为层
        self.behavior_tab = QWidget()
        self._setup_behavior_tab()
        self.tabs.addTab(self.behavior_tab, "🧠 行为层")
        
        # 记忆层
        self.memory_tab = QWidget()
        self._setup_memory_tab()
        self.tabs.addTab(self.memory_tab, "📚 记忆层")
        
        # 成长记录
        self.growth_tab = QWidget()
        self._setup_growth_tab()
        self.tabs.addTab(self.growth_tab, "📈 成长记录")
        
        main_layout.addWidget(self.tabs)

    def _setup_core_tab(self):
        layout = QVBoxLayout(self.core_tab)
        
        info_label = QLabel("🎯 核心层 - 低频更新，定义你的本质特征")
        info_label.setFont(QFont("Microsoft YaHei", 10))
        info_label.setStyleSheet("color: #666; padding: 8px;")
        layout.addWidget(info_label)
        
        # 核心身份卡片
        self.core_identity_card = AvatarLayerCard(
            "核心层",
            "定义你的本质：身份认同、核心价值观、长期目标",
            self.avatar.core_identity
        )
        layout.addWidget(self.core_identity_card)
        
        # 声明的兴趣
        interests_group = QGroupBox("🧩 声明的兴趣")
        interests_layout = QVBoxLayout()
        
        self.interests_text = QTextEdit()
        self.interests_text.setPlaceholderText("每行一个兴趣...")
        self.interests_text.setPlainText("\n".join(self.avatar.declared_interests))
        interests_layout.addWidget(self.interests_text)
        
        save_interests_btn = QPushButton("保存兴趣")
        save_interests_btn.clicked.connect(self._on_save_interests)
        interests_layout.addWidget(save_interests_btn)
        
        interests_group.setLayout(interests_layout)
        layout.addWidget(interests_group)
        
        layout.addStretch()

    def _setup_behavior_tab(self):
        layout = QVBoxLayout(self.behavior_tab)
        
        info_label = QLabel("🧠 行为层 - 中频更新，反映你的习惯和模式")
        info_label.setFont(QFont("Microsoft YaHei", 10))
        info_label.setStyleSheet("color: #666; padding: 8px;")
        layout.addWidget(info_label)
        
        # 行为模式卡片
        self.behavior_card = AvatarLayerCard(
            "行为层",
            "你的行为模式、决策倾向、角色推断",
            self.avatar.behavioral_patterns
        )
        layout.addWidget(self.behavior_card)
        
        # 推断的角色
        roles_group = QGroupBox("👤 推断的角色")
        roles_layout = QVBoxLayout()
        
        for role, confidence in self.avatar.inferred_roles.items():
            role_label = QLabel(f"{role}: {confidence:.2f}")
            role_label.setFont(QFont("Microsoft YaHei", 10))
            roles_layout.addWidget(role_label)
        
        roles_group.setLayout(roles_layout)
        layout.addWidget(roles_group)
        
        layout.addStretch()

    def _setup_memory_tab(self):
        layout = QVBoxLayout(self.memory_tab)
        
        info_label = QLabel("📚 记忆层 - 高频更新，记录你的学习历程")
        info_label.setFont(QFont("Microsoft YaHei", 10))
        info_label.setStyleSheet("color: #666; padding: 8px;")
        layout.addWidget(info_label)
        
        # 里程碑卡片
        milestones_group = QGroupBox("🏆 对话里程碑")
        milestones_layout = QVBoxLayout()
        
        for milestone in self.avatar.conversation_milestones[-5:]:
            milestone_label = QLabel(f"- {milestone.get('description', '')}")
            milestone_label.setFont(QFont("Microsoft YaHei", 9))
            milestones_layout.addWidget(milestone_label)
        
        milestones_group.setLayout(milestones_layout)
        layout.addWidget(milestones_group)
        
        # 学习到的概念
        concepts_group = QGroupBox("💡 学习到的概念")
        concepts_layout = QVBoxLayout()
        
        for concept in list(self.avatar.learned_concepts.keys())[:10]:
            concept_label = QLabel(f"- {concept}")
            concept_label.setFont(QFont("Microsoft YaHei", 9))
            concepts_layout.addWidget(concept_label)
        
        concepts_group.setLayout(concepts_layout)
        layout.addWidget(concepts_group)
        
        # 知识缺口
        gaps_group = QGroupBox("❓ 知识缺口")
        gaps_layout = QVBoxLayout()
        
        for gap in self.avatar.knowledge_gaps[:5]:
            gap_label = QLabel(f"- {gap}")
            gap_label.setFont(QFont("Microsoft YaHei", 9))
            gaps_layout.addWidget(gap_label)
        
        gaps_group.setLayout(gaps_layout)
        layout.addWidget(gaps_group)
        
        layout.addStretch()

    def _setup_growth_tab(self):
        layout = QVBoxLayout(self.growth_tab)
        
        info_label = QLabel("📈 成长记录 - 追踪你的进化历程")
        info_label.setFont(QFont("Microsoft YaHei", 10))
        info_label.setStyleSheet("color: #666; padding: 8px;")
        layout.addWidget(info_label)
        
        # 成长事件列表
        self.growth_list = QListWidget()
        self.growth_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                background-color: #fff;
            }
        """)
        layout.addWidget(self.growth_list)
        
        # 刷新按钮
        refresh_btn = QPushButton("🔄 刷新记录")
        refresh_btn.clicked.connect(self._load_growth_events)
        layout.addWidget(refresh_btn)

    def _update_display(self):
        """更新显示"""
        # 更新等级环
        max_exp = self._calculate_max_exp(self.avatar.level)
        self.level_ring.set_progress(self.avatar.level, self.avatar.experience, max_exp)
        
        # 更新统计
        self.exp_label.setText(f"经验值: {self.avatar.experience}")
        self.level_label.setText(f"等级: {self.avatar.level} ({AvatarLevel(self.avatar.level).name})")
        self.features_label.setText(f"已解锁功能: {len(self.avatar.unlocked_features)}")
        
        # 更新核心层卡片
        self.core_identity_card.update_data(self.avatar.core_identity)
        self.behavior_card.update_data(self.avatar.behavioral_patterns)
        
        # 加载成长记录
        self._load_growth_events()

    def _calculate_max_exp(self, level: int) -> int:
        """计算升级所需经验值"""
        return level * 100

    def _load_growth_events(self):
        """加载成长事件"""
        self.growth_list.clear()
        events = self.db.get_growth_events(self.avatar.user_id)
        
        for event in events[-10:]:
            card = GrowthEventCard(event)
            item = QListWidgetItem()
            item.setSizeHint(QSize(300, 60))
            self.growth_list.addItem(item)
            self.growth_list.setItemWidget(item, card)

    def _on_save_interests(self):
        """保存兴趣"""
        interests_text = self.interests_text.toPlainText()
        self.avatar.declared_interests = [line.strip() for line in interests_text.split("\n") if line.strip()]
        self.db.update_avatar(self.avatar)
        self._update_display()

    def _on_evolve(self):
        """触发进化"""
        # 添加经验值
        exp_gain = 50
        self.avatar.experience += exp_gain
        
        # 检查是否升级
        max_exp = self._calculate_max_exp(self.avatar.level)
        if self.avatar.experience >= max_exp:
            self.avatar.level += 1
            self.avatar.experience = 0
        
        # 记录成长事件
        event = GrowthEvent(
            type="evolution",
            description=f"触发进化，获得 {exp_gain} 经验值",
            exp_gained=exp_gain
        )
        self.db.add_growth_event(self.avatar.user_id, event)
        
        # 更新数据库
        self.db.update_avatar(self.avatar)
        self._update_display()

    def _on_reset(self):
        """重置分身"""
        reply = QMessageBox.question(
            self, "确认重置", "确定要重置分身吗？这将清除所有数据和成长记录。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.avatar = DigitalAvatar(
                id=self.avatar.id,
                user_id="default_user",
                declared_interests=["编程", "AI", "技术"],
                level=1,
                experience=0
            )
            self.db.update_avatar(self.avatar)
            self._update_display()

    def _on_export(self):
        """导出数据"""
        data = {
            "user_id": self.avatar.user_id,
            "level": self.avatar.level,
            "experience": self.avatar.experience,
            "core_identity": self.avatar.core_identity,
            "declared_interests": self.avatar.declared_interests,
            "behavioral_patterns": self.avatar.behavioral_patterns,
            "inferred_roles": self.avatar.inferred_roles,
            "learned_concepts": self.avatar.learned_concepts,
            "unlocked_features": self.avatar.unlocked_features,
            "created_at": self.avatar.created_at,
            "updated_at": self.avatar.updated_at
        }
        
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(
            self, "导出分身数据", "~", "JSON Files (*.json)"
        )
        
        if path:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)


# ==================== 导出 ====================

__all__ = ['AvatarPanel', 'LevelRing', 'AvatarLayerCard', 'GrowthEventCard']
