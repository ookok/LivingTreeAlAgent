# achievement_panel/__init__.py
# 全链路成就系统 PyQt6 UI面板
# 从首次执行到永续成长的可视化展示

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QLabel,
    QPushButton, QScrollArea, QProgressBar, QFrame, QGridLayout,
    QListWidget, QStackedWidget, QLineEdit, QTextEdit, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox, QGroupBox,
    QFormLayout, QSpinBox, QDoubleSpinBox, QSlider, QProgressDialog,
    QDialog, QMessageBox, QGraphicsDropShadowEffect, QColorDialog
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread, QPropertyAnimation, QEasingCurve, QSize
from PyQt6.QtGui import QFont, QIcon, QPixmap, QPainter, QPainterPath, QLinearGradient, QColor, QPen, QBrush
from PyQt6.QtChart import QChart, QChartView, QPieSeries, QBarSeries, QBarSet, QCategoryAxis, QValueAxis
from typing import Dict, List, Optional
import asyncio
from datetime import datetime, timedelta
import random

# 尝试导入成就系统，如果失败则使用模拟
try:
    from .business.achievement_system import (
        AchievementSystemManager, AchievementRarity, AchievementCategory,
        AchievementMetaverse, AchievementTracker, TimeCapsuleAchievement,
        EvolvingAchievement, AchievementComboSystem, AchievementMetaverseGallery,
        AchievementTimeTravel, AchievementGeneInheritance, AchievementNeuralNetwork,
        AchievementLiveCard, AchievementSocialNetwork, AchievementPerpetualEngine,
        AchievementMetaverseMapping
    )
    ACHIEVEMENT_SYSTEM_AVAILABLE = True
except ImportError:
    ACHIEVEMENT_SYSTEM_AVAILABLE = False


# ==================== 成就系统管理器（模拟版本）====================

class MockAchievementSystem:
    """当成就系统不可用时的模拟版本"""

    def __init__(self):
        self.achievement_categories = {
            "first_steps": {"name": "首次体验", "icon": "🚀", "color": "#4CAF50"},
            "skill_mastery": {"name": "技能精通", "icon": "🎯", "color": "#2196F3"},
            "community_builder": {"name": "社区建设", "icon": "🤝", "color": "#FF9800"},
            "economic_power": {"name": "经济实力", "icon": "💰", "color": "#FFD700"},
            "innovation_pioneer": {"name": "创新先锋", "icon": "💡", "color": "#9C27B0"},
            "social_influence": {"name": "社会影响", "icon": "👑", "color": "#E91E63"}
        }

        self.achievements = [
            {"id": "first_agent_run", "name": "初试AI", "category": "first_steps",
             "description": "首次执行智能体任务", "icon": "🤖", "rarity": "common",
             "progress": 75, "tier": 3, "max_tier": 5, "unlocked": True},
            {"id": "first_knowledge_query", "name": "知识探索", "category": "first_steps",
             "description": "首次查询知识库", "icon": "📚", "rarity": "common",
             "progress": 100, "tier": 1, "max_tier": 5, "unlocked": True},
            {"id": "knowledge_architect", "name": "知识架构师", "category": "skill_mastery",
             "description": "创建知识索引", "icon": "🏛️", "rarity": "uncommon",
             "progress": 45, "tier": 2, "max_tier": 5, "unlocked": True},
            {"id": "master_creator", "name": "大师创造者", "category": "innovation_pioneer",
             "description": "创作杰作", "icon": "🎨", "rarity": "legendary",
             "progress": 20, "tier": 1, "max_tier": 5, "unlocked": False},
            {"id": "social_butterfly", "name": "社交蝴蝶", "category": "social_influence",
             "description": "结交好友", "icon": "🦋", "rarity": "epic",
             "progress": 60, "tier": 3, "max_tier": 5, "unlocked": True},
            {"id": "volume_trader", "name": "量大户", "category": "economic_power",
             "description": "交易量达到一定规模", "icon": "📈", "rarity": "epic",
             "progress": 85, "tier": 4, "max_tier": 5, "unlocked": True},
            {"id": "group_leader", "name": "群组领袖", "category": "community_builder",
             "description": "创建群组", "icon": "👥", "rarity": "rare",
             "progress": 100, "tier": 2, "max_tier": 5, "unlocked": True},
            {"id": "dedicated_learner", "name": "勤奋学习者", "category": "first_steps",
             "description": "连续学习打卡", "icon": "📖", "rarity": "epic",
             "progress": 33, "tier": 2, "max_tier": 5, "unlocked": True},
        ]

        self.user_stats = {
            "total_achievements": 100,
            "unlocked": 23,
            "total_credits": 15680,
            "current_level": 12,
            "streak_days": 7,
            "completion_rate": 23.0
        }

        self.time_capsules = [
            {"id": "capsule_001", "title": "一周年纪念", "unlock_date": "2027-01-01", "status": "sealed"},
            {"id": "capsule_002", "title": "首次传奇成就", "unlock_date": "2026-06-01", "status": "opened"}
        ]

        self.evolved_achievements = [
            {"base": "first_agent_run", "evolved": "first_agent_run_evolved_mastery",
             "path": "mastery", "name": "初试AI·精通进化"}
        ]

        self.combos = [
            {"id": "first_complete_set", "name": "初出茅庐", "components": 4,
             "progress": 75, "unlocked": False},
            {"id": "trading_master_set", "name": "交易大师", "components": 3,
             "progress": 100, "unlocked": True}
        ]

        self.galleries = [
            {"id": "gallery_001", "name": "成就殿堂", "achievements": 15, "visitors": 234}
        ]

        self.infinite_challenges = [
            {"id": "ch_001", "name": "每日磨砺", "level": 15, "best": 15, "progress": 65},
            {"id": "ch_002", "name": "无尽学习", "level": 8, "best": 12, "progress": 40}
        ]

    def get_all_achievements(self):
        return self.achievements

    def get_user_stats(self):
        return self.user_stats

    def get_categories(self):
        return self.achievement_categories

    def get_time_capsules(self):
        return self.time_capsules

    def get_evolved_achievements(self):
        return self.evolved_achievements

    def get_combos(self):
        return self.combos

    def get_galleries(self):
        return self.galleries

    def get_infinite_challenges(self):
        return self.infinite_challenges


# ==================== 成就卡片组件 ====================

class AchievementCard(QFrame):
    """成就卡片组件"""

    def __init__(self, achievement: Dict, parent=None):
        super().__init__(parent)
        self.achievement = achievement
        self.setup_ui()
        self.apply_style()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # 图标和名称行
        header_layout = QHBoxLayout()

        icon_label = QLabel(self.achievement.get("icon", "🏆"))
        icon_label.setFont(QFont("Segoe UI Emoji", 24))
        header_layout.addWidget(icon_label)

        name_label = QLabel(self.achievement.get("name", "未知成就"))
        name_label.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        header_layout.addWidget(name_label, 1)

        # 稀有度标签
        rarity = self.achievement.get("rarity", "common")
        rarity_labels = {
            "common": ("普通", "#9e9e9e"),
            "uncommon": ("优秀", "#4caf50"),
            "rare": ("稀有", "#2196f3"),
            "epic": ("史诗", "#9c27b0"),
            "legendary": ("传说", "#ffc107"),
            "mythic": ("神话", "#e91e63")
        }
        rarity_text, rarity_color = rarity_labels.get(rarity, ("普通", "#9e9e9e"))
        rarity_label = QLabel(rarity_text)
        rarity_label.setStyleSheet(f"""
            background-color: {rarity_color};
            color: white;
            border-radius: 8px;
            padding: 2px 8px;
            font-size: 10px;
        """)
        header_layout.addWidget(rarity_label)

        layout.addLayout(header_layout)

        # 描述
        desc_label = QLabel(self.achievement.get("description", ""))
        desc_label.setStyleSheet("color: #666; font-size: 11px;")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        # 进度条
        progress_layout = QHBoxLayout()
        progress_label = QLabel("进度")
        progress_label.setStyleSheet("font-size: 10px; color: #888;")
        progress_layout.addWidget(progress_label)

        tier_info = f"Tier {self.achievement.get('tier', 0)}/{self.achievement.get('max_tier', 5)}"
        tier_label = QLabel(tier_info)
        tier_label.setStyleSheet("font-size: 10px; color: #888;")
        progress_layout.addWidget(tier_label)

        layout.addLayout(progress_layout)

        progress_bar = QProgressBar()
        progress_bar.setValue(self.achievement.get("progress", 0))
        progress_bar.setMaximum(100)
        progress_bar.setFixedHeight(6)
        progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                background-color: #e0e0e0;
                border-radius: 3px;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 3px;
            }
        """)
        layout.addWidget(progress_bar)

        # 解锁状态
        if self.achievement.get("unlocked"):
            unlocked_label = QLabel("✅ 已解锁")
            unlocked_label.setStyleSheet("color: #4CAF50; font-size: 11px; font-weight: bold;")
        else:
            unlocked_label = QLabel("🔒 未解锁")
            unlocked_label.setStyleSheet("color: #999; font-size: 11px;")
        layout.addWidget(unlocked_label)

    def apply_style(self):
        self.setFixedSize(220, 180)
        self.setStyleSheet("""
            AchievementCard {
                background-color: white;
                border-radius: 12px;
                border: 1px solid #e0e0e0;
            }
            AchievementCard:hover {
                border: 2px solid #4CAF50;
            }
        """)


# ==================== 主面板 ====================

class AchievementPanel(QWidget):
    """成就系统主面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.achievement_system = MockAchievementSystem() if not ACHIEVEMENT_SYSTEM_AVAILABLE else None
        self.setup_ui()
        self.populate_data()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # 标题栏
        header = QWidget()
        header.setStyleSheet("background-color: #1a1a2e; padding: 15px;")
        header_layout = QHBoxLayout(header)

        title = QLabel("🎮 全链路成就系统")
        title.setFont(QFont("Microsoft YaHei", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: white;")
        header_layout.addWidget(title)

        subtitle = QLabel("每个行为都有成就，每次成长都有记录")
        subtitle.setStyleSheet("color: #888; font-size: 12px;")
        header_layout.addWidget(subtitle)

        header_layout.addStretch()

        # 刷新按钮
        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        refresh_btn.clicked.connect(self.refresh_data)
        header_layout.addWidget(refresh_btn)

        main_layout.addWidget(header)

        # 创建标签页
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background-color: #f5f5f5;
            }
            QTabBar::tab {
                background-color: #e0e0e0;
                padding: 10px 20px;
                margin-right: 2px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }
            QTabBar::tab:selected {
                background-color: white;
                color: #4CAF50;
                font-weight: bold;
            }
        """)

        # 添加各标签页
        self.tabs.addTab(self.create_overview_tab(), "📊 总览")
        self.tabs.addTab(self.create_achievements_tab(), "🏆 成就")
        self.tabs.addTab(self.create_time_capsule_tab(), "⏰ 时间胶囊")
        self.tabs.addTab(self.create_evolution_tab(), "⚡ 成就进化")
        self.tabs.addTab(self.create_combo_tab(), "🎯 组合技")
        self.tabs.addTab(self.create_gallery_tab(), "🖼️ 成就画廊")
        self.tabs.addTab(self.create_infinite_tab(), "♾️ 无限挑战")
        self.tabs.addTab(self.create_social_tab(), "🌐 社交动态")

        main_layout.addWidget(self.tabs)

    def create_overview_tab(self) -> QWidget:
        """总览标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # 统计卡片行
        stats_layout = QHBoxLayout()

        stats = self.achievement_system.get_user_stats()
        stat_cards = [
            ("总成就", f"{stats['unlocked']}/{stats['total_achievements']}", "🏆"),
            ("积分", f"{stats['total_credits']:,}", "💰"),
            ("等级", f"Lv.{stats['current_level']}", "⭐"),
            ("连续", f"{stats['streak_days']}天", "🔥"),
            ("完成率", f"{stats['completion_rate']:.1f}%", "📈")
        ]

        for title, value, icon in stat_cards:
            card = self.create_stat_card(title, value, icon)
            stats_layout.addWidget(card)

        layout.addLayout(stats_layout)

        # 分类进度
        progress_group = QGroupBox("分类完成进度")
        progress_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                margin-top: 12px;
                padding: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        progress_layout = QVBoxLayout(progress_group)

        categories = self.achievement_system.get_categories()
        for cat_id, cat_info in categories.items():
            cat_layout = QHBoxLayout()
            cat_label = QLabel(f"{cat_info['icon']} {cat_info['name']}")
            cat_label.setFixedWidth(100)
            cat_layout.addWidget(cat_label)

            cat_bar = QProgressBar()
            cat_bar.setValue(random.randint(20, 90))
            cat_bar.setFixedHeight(12)
            cat_bar.setStyleSheet("""
                QProgressBar {
                    border: none;
                    background-color: #e0e0e0;
                    border-radius: 6px;
                }
                QProgressBar::chunk {
                    background-color: %s;
                    border-radius: 6px;
                }
            """ % cat_info['color'])
            cat_layout.addWidget(cat_bar)

            cat_percent = QLabel(f"{random.randint(20, 90)}%")
            cat_percent.setFixedWidth(40)
            cat_layout.addWidget(cat_percent)

            progress_layout.addLayout(cat_layout)

        layout.addWidget(progress_group)

        # 最近成就
        recent_group = QGroupBox("最近解锁")
        recent_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                margin-top: 12px;
                padding: 15px;
            }
        """)
        recent_layout = QHBoxLayout(recent_group)

        achievements = self.achievement_system.get_all_achievements()
        for ach in achievements[:4]:
            if ach.get("unlocked"):
                card = self.create_achievement_mini_card(ach)
                recent_layout.addWidget(card)

        layout.addWidget(recent_group)

        layout.addStretch()
        return widget

    def create_stat_card(self, title: str, value: str, icon: str) -> QWidget:
        """创建统计卡片"""
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 12px;
                border: 1px solid #e0e0e0;
            }
        """)
        layout = QVBoxLayout(card)
        layout.setSpacing(5)

        icon_label = QLabel(icon)
        icon_label.setFont(QFont("Segoe UI Emoji", 20))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)

        value_label = QLabel(value)
        value_label.setFont(QFont("Microsoft YaHei", 16, QFont.Weight.Bold))
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value_label.setStyleSheet("color: #1a1a2e;")
        layout.addWidget(value_label)

        title_label = QLabel(title)
        title_label.setFont(QFont("Microsoft YaHei", 10))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("color: #888;")
        layout.addWidget(title_label)

        return card

    def create_achievement_mini_card(self, achievement: Dict) -> QWidget:
        """创建迷你成就卡片"""
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #f5f5f5;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        layout = QVBoxLayout(card)
        layout.setSpacing(5)

        icon = QLabel(achievement.get("icon", "🏆"))
        icon.setFont(QFont("Segoe UI Emoji", 24))
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon)

        name = QLabel(achievement.get("name", ""))
        name.setFont(QFont("Microsoft YaHei", 9))
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name.setStyleSheet("color: #333;")
        name.setWordWrap(True)
        layout.addWidget(name)

        return card

    def create_achievements_tab(self) -> QWidget:
        """成就标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)

        # 筛选栏
        filter_layout = QHBoxLayout()

        filter_label = QLabel("筛选:")
        filter_layout.addWidget(filter_label)

        category_combo = QComboBox()
        category_combo.addItems(["全部", "首次体验", "技能精通", "社区建设", "经济实力", "创新先锋", "社会影响"])
        category_combo.setStyleSheet("""
            QComboBox {
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                padding: 5px 10px;
            }
        """)
        filter_layout.addWidget(category_combo)

        rarity_combo = QComboBox()
        rarity_combo.addItems(["全部稀有度", "普通", "优秀", "稀有", "史诗", "传说", "神话"])
        filter_layout.addWidget(rarity_combo)

        filter_layout.addStretch()

        # 搜索框
        search_input = QLineEdit()
        search_input.setPlaceholderText("🔍 搜索成就...")
        search_input.setStyleSheet("""
            QLineEdit {
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                padding: 5px 10px;
            }
        """)
        filter_layout.addWidget(search_input)

        layout.addLayout(filter_layout)

        # 成就网格
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none;")

        container = QWidget()
        grid_layout = QGridLayout(container)
        grid_layout.setSpacing(15)

        achievements = self.achievement_system.get_all_achievements()
        for i, ach in enumerate(achievements):
            row = i // 4
            col = i % 4
            card = self.create_achievement_card_widget(ach)
            grid_layout.addWidget(card, row, col)

        scroll.setWidget(container)
        layout.addWidget(scroll)

        return widget

    def create_achievement_card_widget(self, achievement: Dict) -> QWidget:
        """创建成就卡片组件"""
        card = QFrame()
        card.setFixedSize(200, 200)
        card.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 12px;
                border: 1px solid #e0e0e0;
            }
            QFrame:hover {
                border: 2px solid #4CAF50;
            }
        """)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # 头部
        header = QHBoxLayout()

        icon = QLabel(achievement.get("icon", "🏆"))
        icon.setFont(QFont("Segoe UI Emoji", 28))
        header.addWidget(icon)

        name = QLabel(achievement.get("name", ""))
        name.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        name.setStyleSheet("color: #1a1a2e;")
        header.addWidget(name, 1)

        rarity = achievement.get("rarity", "common")
        colors = {"common": "#9e9e9e", "uncommon": "#4caf50", "rare": "#2196f3",
                  "epic": "#9c27b0", "legendary": "#ffc107", "mythic": "#e91e63"}
        rarity_badge = QLabel(rarity.upper())
        rarity_badge.setStyleSheet(f"""
            background-color: {colors.get(rarity, '#9e9e9e')};
            color: white;
            border-radius: 6px;
            padding: 2px 6px;
            font-size: 9px;
        """)
        header.addWidget(rarity_badge)

        layout.addLayout(header)

        # 描述
        desc = QLabel(achievement.get("description", ""))
        desc.setStyleSheet("color: #666; font-size: 10px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        layout.addStretch()

        # 进度
        progress_layout = QHBoxLayout()
        progress_label = QLabel(f"Tier {achievement.get('tier', 0)}/{achievement.get('max_tier', 5)}")
        progress_label.setStyleSheet("font-size: 10px; color: #888;")
        progress_layout.addWidget(progress_label)
        progress_layout.addStretch()

        tier_label = QLabel(f"{achievement.get('progress', 0)}%")
        tier_label.setStyleSheet("font-size: 10px; color: #4CAF50; font-weight: bold;")
        progress_layout.addWidget(tier_label)

        layout.addLayout(progress_layout)

        bar = QProgressBar()
        bar.setValue(achievement.get("progress", 0))
        bar.setFixedHeight(8)
        bar.setStyleSheet("""
            QProgressBar {
                border: none;
                background-color: #e0e0e0;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4CAF50, stop:1 #8BC34A);
                border-radius: 4px;
            }
        """)
        layout.addWidget(bar)

        # 状态
        if achievement.get("unlocked"):
            status = QLabel("✅ 已解锁")
            status.setStyleSheet("color: #4CAF50; font-size: 10px; font-weight: bold;")
        else:
            status = QLabel("🔒 继续努力")
            status.setStyleSheet("color: #999; font-size: 10px;")
        layout.addWidget(status)

        return card

    def create_time_capsule_tab(self) -> QWidget:
        """时间胶囊标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # 介绍
        intro = QLabel("""
        <div style='font-size: 14px; color: #333; line-height: 1.8;'>
        <b>⏰ 时间胶囊成就</b><br>
        将您的成就封存于时光之中，在未来的某一天重新开启，收获时光的礼物与惊喜回忆。<br>
        封存时间越久，解锁时的时光旅行奖励越丰厚！
        </div>
        """)
        layout.addWidget(intro)

        # 创建按钮
        create_btn = QPushButton("🆕 创建时间胶囊")
        create_btn.setStyleSheet("""
            QPushButton {
                background-color: #9C27B0;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #7B1FA2;
            }
        """)
        layout.addWidget(create_btn)

        # 胶囊列表
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        capsule_layout = QVBoxLayout(container)
        capsule_layout.setSpacing(15)

        for capsule in self.achievement_system.get_time_capsules():
            capsule_card = self.create_capsule_card(capsule)
            capsule_layout.addWidget(capsule_card)

        capsule_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll)

        return widget

    def create_capsule_card(self, capsule: Dict) -> QWidget:
        """创建胶囊卡片"""
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 12px;
                border: 1px solid #e0e0e0;
            }
        """)
        layout = QHBoxLayout(card)
        layout.setContentsMargins(15, 15, 15, 15)

        # 图标
        icon = QLabel("⏰")
        icon.setFont(QFont("Segoe UI Emoji", 36))
        layout.addWidget(icon)

        # 信息
        info_layout = QVBoxLayout()
        title = QLabel(capsule.get("title", "时间胶囊"))
        title.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        info_layout.addWidget(title)

        status = capsule.get("status", "sealed")
        status_text = "🔒 已封存" if status == "sealed" else "✅ 已开启"
        status_label = QLabel(status_text)
        status_label.setStyleSheet("color: #4CAF50;" if status == "opened" else "color: #FF9800;")
        info_layout.addWidget(status_label)

        unlock_date = QLabel(f"解锁日期: {capsule.get('unlock_date', '未知')}")
        unlock_date.setStyleSheet("color: #888; font-size: 11px;")
        info_layout.addWidget(unlock_date)

        layout.addLayout(info_layout, 1)

        # 操作按钮
        if status == "sealed":
            open_btn = QPushButton("开启")
            open_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    border: none;
                    border-radius: 6px;
                    padding: 8px 16px;
                }
            """)
            layout.addWidget(open_btn)
        else:
            view_btn = QPushButton("查看")
            view_btn.setStyleSheet("""
                QPushButton {
                    background-color: #2196F3;
                    color: white;
                    border: none;
                    border-radius: 6px;
                    padding: 8px 16px;
                }
            """)
            layout.addWidget(view_btn)

        return card

    def create_evolution_tab(self) -> QWidget:
        """成就进化标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # 说明
        intro = QLabel("""
        <div style='font-size: 14px; color: #333; line-height: 1.8;'>
        <b>⚡ 成就进化系统</b><br>
        成就可以通过进化变得更强大！选择适合的进化路径，让您的成就焕发新的光彩。<br>
        <br>
        <b>进化路径:</b><br>
        🔥 <b>精通进化</b> - 通过反复精通达到极致 (需Tier 5)<br>
        🔮 <b>融合进化</b> - 将多个成就融合成更强存在 (需Tier 3)<br>
        🌟 <b>觉醒进化</b> - 在特殊事件中觉醒 (需等级10)
        </div>
        """)
        layout.addWidget(intro)

        # 进化路径选择
        path_group = QGroupBox("选择进化路径")
        path_layout = QHBoxLayout(path_group)

        paths = [
            ("mastery", "🔥 精通进化", "通过精通达到极致", "#4CAF50"),
            ("fusion", "🔮 融合进化", "将多个成就融合", "#9C27B0"),
            ("awakening", "🌟 觉醒进化", "在特殊事件中觉醒", "#FF9800")
        ]

        for path_id, path_name, path_desc, color in paths:
            path_card = QFrame()
            path_card.setStyleSheet(f"""
                QFrame {{
                    background-color: white;
                    border-radius: 12px;
                    border: 2px solid {color};
                }}
            """)
            path_layout_inner = QVBoxLayout(path_card)
            path_layout_inner.setSpacing(10)

            path_title = QLabel(path_name)
            path_title.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
            path_layout_inner.addWidget(path_title)

            path_desc_label = QLabel(path_desc)
            path_desc_label.setStyleSheet("color: #666; font-size: 10px;")
            path_layout_inner.addWidget(path_desc_label)

            evolve_btn = QPushButton("选择此路径")
            evolve_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color};
                    color: white;
                    border: none;
                    border-radius: 6px;
                    padding: 8px 16px;
                }}
            """)
            path_layout_inner.addWidget(evolve_btn)

            path_layout.addWidget(path_card)

        layout.addWidget(path_group)

        # 已进化成就
        evolved_label = QLabel("已进化成就")
        evolved_label.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        layout.addWidget(evolved_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        evolved_container = QWidget()
        evolved_layout = QVBoxLayout(evolved_container)
        evolved_layout.setSpacing(10)

        for evolved in self.achievement_system.get_evolved_achievements():
            evolved_card = self.create_evolved_card(evolved)
            evolved_layout.addWidget(evolved_card)

        evolved_layout.addStretch()
        scroll.setWidget(evolved_container)
        layout.addWidget(scroll)

        return widget

    def create_evolved_card(self, evolved: Dict) -> QWidget:
        """创建已进化成就卡片"""
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 10px;
                border: 1px solid #e0e0e0;
            }
        """)
        layout = QHBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)

        base_icon = QLabel("🤖")
        base_icon.setFont(QFont("Segoe UI Emoji", 24))
        layout.addWidget(base_icon)

        arrow = QLabel("→")
        arrow.setFont(QFont("Microsoft YaHei", 18))
        layout.addWidget(arrow)

        evolved_icon = QLabel("⚡")
        evolved_icon.setFont(QFont("Segoe UI Emoji", 24))
        layout.addWidget(evolved_icon)

        info_layout = QVBoxLayout()
        name = QLabel(evolved.get("name", ""))
        name.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        info_layout.addWidget(name)

        path = QLabel(f"进化路径: {evolved.get('path', '')}")
        path.setStyleSheet("color: #666; font-size: 10px;")
        info_layout.addWidget(path)

        layout.addLayout(info_layout, 1)

        status = QLabel("✅ 已激活")
        status.setStyleSheet("color: #4CAF50; font-weight: bold;")
        layout.addWidget(status)

        return card

    def create_combo_tab(self) -> QWidget:
        """组合技标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # 说明
        intro = QLabel("""
        <div style='font-size: 14px; color: #333; line-height: 1.8;'>
        <b>🎯 成就组合技</b><br>
        集齐特定成就组合即可激活强大的组合技能！组合成就不仅有额外奖励，还能解锁独特称号和特效。
        </div>
        """)
        layout.addWidget(intro)

        # 组合列表
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        combo_container = QWidget()
        combo_layout = QVBoxLayout(combo_container)
        combo_layout.setSpacing(15)

        for combo in self.achievement_system.get_combos():
            combo_card = self.create_combo_card(combo)
            combo_layout.addWidget(combo_card)

        combo_layout.addStretch()
        scroll.setWidget(combo_container)
        layout.addWidget(scroll)

        return widget

    def create_combo_card(self, combo: Dict) -> QWidget:
        """创建组合卡片"""
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 12px;
                border: 1px solid #e0e0e0;
            }
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        header = QHBoxLayout()

        title = QLabel(f"🎯 {combo.get('name', '')}")
        title.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        header.addWidget(title)

        header.addStretch()

        status = QLabel("✅ 已解锁" if combo.get("unlocked") else "🔒 未解锁")
        status.setStyleSheet("color: #4CAF50; font-weight: bold;" if combo.get("unlocked") else "color: #999;")
        header.addWidget(status)

        layout.addLayout(header)

        # 进度
        progress_layout = QHBoxLayout()
        progress_layout.addWidget(QLabel("组合进度:"))

        bar = QProgressBar()
        bar.setValue(combo.get("progress", 0))
        bar.setFixedHeight(12)
        bar.setStyleSheet("""
            QProgressBar {
                border: none;
                background-color: #e0e0e0;
                border-radius: 6px;
            }
            QProgressBar::chunk {
                background-color: #9C27B0;
                border-radius: 6px;
            }
        """)
        progress_layout.addWidget(bar)

        progress_text = QLabel(f"{combo.get('progress', 0)}%")
        progress_text.setStyleSheet("font-weight: bold; color: #9C27B0;")
        progress_layout.addWidget(progress_text)

        layout.addLayout(progress_layout)

        # 所需成就
        components_label = QLabel(f"需要 {combo.get('components', 0)} 个成就")
        components_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(components_label)

        return card

    def create_gallery_tab(self) -> QWidget:
        """成就画廊标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # 操作栏
        action_layout = QHBoxLayout()

        create_btn = QPushButton("🆕 创建画廊")
        create_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
            }
        """)
        action_layout.addWidget(create_btn)

        action_layout.addStretch()

        layout.addLayout(action_layout)

        # 画廊列表
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        gallery_container = QWidget()
        gallery_layout = QVBoxLayout(gallery_container)
        gallery_layout.setSpacing(15)

        for gallery in self.achievement_system.get_galleries():
            gallery_card = self.create_gallery_card(gallery)
            gallery_layout.addWidget(gallery_card)

        gallery_layout.addStretch()
        scroll.setWidget(gallery_container)
        layout.addWidget(scroll)

        return widget

    def create_gallery_card(self, gallery: Dict) -> QWidget:
        """创建画廊卡片"""
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 12px;
                border: 1px solid #e0e0e0;
            }
        """)
        layout = QHBoxLayout(card)
        layout.setContentsMargins(15, 15, 15, 15)

        # 预览
        preview = QLabel("🖼️")
        preview.setFont(QFont("Segoe UI Emoji", 40))
        preview.setFixedSize(100, 80)
        preview.setStyleSheet("""
            background-color: #f5f5f5;
            border-radius: 8px;
        """)
        preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(preview)

        # 信息
        info_layout = QVBoxLayout()

        title = QLabel(gallery.get("name", ""))
        title.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        info_layout.addWidget(title)

        stats = QLabel(f"展示成就: {gallery.get('achievements', 0)} | 访客: {gallery.get('visitors', 0)}")
        stats.setStyleSheet("color: #666; font-size: 11px;")
        info_layout.addWidget(stats)

        info_layout.addStretch()

        # 操作
        visit_btn = QPushButton("参观")
        visit_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
            }
        """)
        layout.addWidget(visit_btn)

        return card

    def create_infinite_tab(self) -> QWidget:
        """无限挑战标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # 说明
        intro = QLabel("""
        <div style='font-size: 14px; color: #333; line-height: 1.8;'>
        <b>♾️ 成就永动机</b><br>
        无限挑战，永续成长！选择您喜欢的挑战类型，系统将持续为您生成越来越有挑战性的目标。<br>
        每完成一个等级，都会获得丰厚奖励，而且挑战永远不会结束！
        </div>
        """)
        layout.addWidget(intro)

        # 创建挑战
        create_layout = QHBoxLayout()

        challenge_type = QComboBox()
        challenge_type.addItems(["每日磨砺", "无尽学习", "社交达人", "经济大师"])
        create_layout.addWidget(challenge_type)

        create_btn = QPushButton("🆕 开始挑战")
        create_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
            }
        """)
        create_layout.addWidget(create_btn)

        layout.addLayout(create_layout)

        # 挑战列表
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        challenge_container = QWidget()
        challenge_layout = QVBoxLayout(challenge_container)
        challenge_layout.setSpacing(15)

        for challenge in self.achievement_system.get_infinite_challenges():
            challenge_card = self.create_challenge_card(challenge)
            challenge_layout.addWidget(challenge_card)

        challenge_layout.addStretch()
        scroll.setWidget(challenge_container)
        layout.addWidget(scroll)

        return widget

    def create_challenge_card(self, challenge: Dict) -> QWidget:
        """创建挑战卡片"""
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 12px;
                border: 1px solid #e0e0e0;
            }
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # 头部
        header = QHBoxLayout()

        icon = QLabel("♾️")
        icon.setFont(QFont("Segoe UI Emoji", 28))
        header.addWidget(icon)

        title = QLabel(challenge.get("name", ""))
        title.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        header.addWidget(title, 1)

        level = QLabel(f"Lv.{challenge.get('level', 1)}")
        level.setStyleSheet("""
            background-color: #FF9800;
            color: white;
            border-radius: 10px;
            padding: 4px 12px;
            font-weight: bold;
        """)
        header.addWidget(level)

        layout.addLayout(header)

        # 进度条
        progress_layout = QHBoxLayout()
        progress_label = QLabel("挑战进度:")
        progress_layout.addWidget(progress_label)

        bar = QProgressBar()
        bar.setValue(challenge.get("progress", 0))
        bar.setFixedHeight(15)
        bar.setStyleSheet("""
            QProgressBar {
                border: none;
                background-color: #e0e0e0;
                border-radius: 8px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #FF9800, stop:1 #FFC107);
                border-radius: 8px;
            }
        """)
        progress_layout.addWidget(bar)

        layout.addLayout(progress_layout)

        # 统计
        stats_layout = QHBoxLayout()

        best = QLabel(f"最高: Lv.{challenge.get('best', 1)}")
        best.setStyleSheet("color: #4CAF50; font-weight: bold;")
        stats_layout.addWidget(best)

        stats_layout.addStretch()

        continue_btn = QPushButton("继续挑战")
        continue_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
            }
        """)
        stats_layout.addWidget(continue_btn)

        layout.addLayout(stats_layout)

        return card

    def create_social_tab(self) -> QWidget:
        """社交动态标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # 标签切换
        tab_layout = QHBoxLayout()

        tabs = [("🔥 热门成就", True), ("⭐ 上升最快", False), ("🎉 新成就", False)]
        for tab_name, active in tabs:
            btn = QPushButton(tab_name)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: %s;
                    color: white;
                    border: none;
                    border-radius: 8px;
                    padding: 8px 16px;
                }
            """ % ("#4CAF50" if active else "#e0e0e0"))
            tab_layout.addWidget(btn)

        tab_layout.addStretch()

        layout.addLayout(tab_layout)

        # 动态列表
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        social_container = QWidget()
        social_layout = QVBoxLayout(social_container)
        social_layout.setSpacing(15)

        # 模拟动态
        for i in range(5):
            post_card = self.create_social_post_card()
            social_layout.addWidget(post_card)

        social_layout.addStretch()
        scroll.setWidget(social_container)
        layout.addWidget(scroll)

        return widget

    def create_social_post_card(self) -> QWidget:
        """创建社交帖子卡片"""
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 12px;
                border: 1px solid #e0e0e0;
            }
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # 用户信息
        user_layout = QHBoxLayout()

        avatar = QLabel("👤")
        avatar.setFont(QFont("Segoe UI Emoji", 24))
        user_layout.addWidget(avatar)

        user_info = QVBoxLayout()
        username = QLabel("用户***")
        username.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        user_info.addWidget(username)

        time = QLabel("5分钟前")
        time.setStyleSheet("color: #888; font-size: 10px;")
        user_info.addWidget(time)

        user_layout.addLayout(user_info)
        user_layout.addStretch()

        layout.addLayout(user_layout)

        # 内容
        content = QLabel("🎉 刚刚解锁了【大师创造者】成就！创作之路永无止境！ #成就 #创作")
        content.setStyleSheet("color: #333; font-size: 12px;")
        content.setWordWrap(True)
        layout.addWidget(content)

        # 成就卡片
        ach_preview = QFrame()
        ach_preview.setStyleSheet("""
            background-color: #f5f5f5;
            border-radius: 8px;
            padding: 10px;
        """)
        ach_layout = QHBoxLayout(ach_preview)

        ach_icon = QLabel("🎨")
        ach_icon.setFont(QFont("Segoe UI Emoji", 28))
        ach_layout.addWidget(ach_icon)

        ach_info = QVBoxLayout()
        ach_name = QLabel("大师创造者")
        ach_name.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        ach_info.addWidget(ach_name)

        ach_desc = QLabel("传说稀有成就")
        ach_desc.setStyleSheet("color: #ffc107; font-size: 10px;")
        ach_info.addWidget(ach_desc)

        ach_layout.addLayout(ach_info)
        ach_layout.addStretch()

        layout.addWidget(ach_preview)

        # 互动
        interaction_layout = QHBoxLayout()

        like_btn = QPushButton("❤️ 128")
        like_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #666;
                border: none;
            }
        """)
        interaction_layout.addWidget(like_btn)

        comment_btn = QPushButton("💬 12")
        comment_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #666;
                border: none;
            }
        """)
        interaction_layout.addWidget(comment_btn)

        share_btn = QPushButton("🔄 分享")
        share_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #666;
                border: none;
            }
        """)
        interaction_layout.addWidget(share_btn)

        interaction_layout.addStretch()

        layout.addLayout(interaction_layout)

        return card

    def populate_data(self):
        """填充数据"""
        pass

    def refresh_data(self):
        """刷新数据"""
        self.populate_data()


# ==================== 导出 ====================

__all__ = ['AchievementPanel']
