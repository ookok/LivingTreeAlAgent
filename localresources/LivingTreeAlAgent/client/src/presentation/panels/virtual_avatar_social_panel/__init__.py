# -*- coding: utf-8 -*-
"""
虚拟形象与社交广场系统 UI 面板
VirtualAvatar + IntelligentPetCompanion + SocialPlaza

作者：Hermes Desktop V2.0
版本：1.0.0
"""

import asyncio
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QTabWidget, QTextEdit,
    QListWidget, QListWidgetItem, QComboBox, QSpinBox,
    QProgressBar, QGroupBox, QScrollArea, QFrame,
    QLineEdit, QCheckBox, QSlider, QStackedWidget,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QGraphicsView, QGraphicsScene, QGraphicsEllipseItem,
    QGraphicsRectItem, QGraphicsTextItem, QGraphicsLineItem,
    QDialog, QDialogButtonBox, QFormLayout, QTextBrowser,
    QTreeWidget, QTreeWidgetItem, QColorDialog, QFontComboBox
)
from PyQt6.QtCore import (
    Qt, QTimer, pyqtSignal, QSize,
    QRectF, QPointF, QPropertyAnimation, QEasingCurve
)
from PyQt6.QtGui import (
    QColor, QBrush, QPen, QFont, QPainter,
    QIcon, QAction, QPixmap, QTransform
)


class VirtualAvatarSocialPanel(QWidget):
    """虚拟形象与社交广场系统主面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.avatar_engine = None
        self.current_user_id = f"user_{uuid.uuid4().hex[:8]}"
        self.user_avatar = None
        self.user_pet = None
        self.init_ui()
        self.setup_timers()

    def init_ui(self):
        """初始化UI"""
        main_layout = QVBoxLayout(self)

        # 标题栏
        title_layout = QHBoxLayout()
        title_label = QLabel("🎭 虚拟形象与社交广场")
        title_label.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        title_layout.addWidget(title_label)
        title_layout.addStretch()

        self.status_label = QLabel("状态: 在线")
        self.status_label.setStyleSheet("color: #4CAF50;")
        title_layout.addWidget(self.status_label)

        main_layout.addLayout(title_layout)

        # 创建标签页
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        # 8个标签页
        self.tab_overview = OverviewTab(self)
        self.tab_avatar = AvatarEditTab(self)
        self.tab_pet = PetManagementTab(self)
        self.tab_plaza = PlazaTab(self)
        self.tab_social = SocialBondTab(self)
        self.tab_achievement = AchievementAppearanceTab(self)
        self.tab_weather = WeatherTimeTab(self)
        self.tab_settings = SettingsTab(self)

        self.tabs.addTab(self.tab_overview, "🏠 总览")
        self.tabs.addTab(self.tab_avatar, "👤 形象")
        self.tabs.addTab(self.tab_pet, "🐾 宠物")
        self.tabs.addTab(self.tab_plaza, "🌳 广场")
        self.tabs.addTab(self.tab_social, "👥 社交")
        self.tabs.addTab(self.tab_achievement, "🏆 成就")
        self.tabs.addTab(self.tab_weather, "🌤️ 环境")
        self.tabs.addTab(self.tab_settings, "⚙️ 设置")

        main_layout.addWidget(self.tabs)

        self.setLayout(main_layout)

    def setup_timers(self):
        """设置定时器"""
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_state)
        self.update_timer.start(2000)  # 每2秒更新

    def update_state(self):
        """更新状态"""
        if self.user_avatar:
            self.tab_overview.refresh(self.user_avatar, self.user_pet)
            self.tab_avatar.refresh(self.user_avatar)

    def set_avatar_engine(self, engine):
        """设置虚拟形象引擎"""
        self.avatar_engine = engine

    async def load_user_data(self):
        """加载用户数据"""
        if self.avatar_engine:
            self.user_avatar = await self.avatar_engine.get_user_avatar(self.current_user_id)
            self.user_pet = await self.avatar_engine.get_user_pet(self.current_user_id)
            self.tab_overview.refresh(self.user_avatar, self.user_pet)
            self.tab_pet.refresh(self.user_pet)

    def get_current_user_id(self):
        """获取当前用户ID"""
        return self.current_user_id


class OverviewTab(QWidget):
    """总览标签页"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_panel = parent
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # 用户概览卡片
        overview_group = QGroupBox("👤 我的形象")
        overview_layout = QGridLayout()

        # 左侧：形象预览
        preview_layout = QVBoxLayout()
        self.avatar_preview = AvatarPreviewWidget(self)
        self.avatar_preview.setMinimumSize(200, 250)
        preview_layout.addWidget(self.avatar_preview)
        overview_layout.addLayout(preview_layout, 0, 0, 3, 1)

        # 右侧：基本信息
        self.user_id_label = QLabel("用户ID: -")
        self.title_label = QLabel("称号: 萌新")
        self.level_label = QLabel("等级: 1")
        self.credit_label = QLabel("积分: 0")

        overview_layout.addWidget(self.user_id_label, 0, 1)
        overview_layout.addWidget(self.title_label, 0, 2)
        overview_layout.addWidget(self.level_label, 1, 1)
        overview_layout.addWidget(self.credit_label, 1, 2)

        # 社交数据
        friends_label = QLabel("好友数: 0")
        bonds_label = QLabel("羁绊数: 0")
        activity_label = QLabel("活跃度: 0")

        overview_layout.addWidget(friends_label, 2, 1)
        overview_layout.addWidget(bonds_label, 2, 2)

        overview_group.setLayout(overview_layout)
        layout.addWidget(overview_group)

        # 宠物概览
        pet_group = QGroupBox("🐾 我的宠物")
        pet_layout = QHBoxLayout()

        self.pet_preview = PetPreviewWidget(self)
        self.pet_preview.setMinimumSize(150, 150)
        pet_layout.addWidget(self.pet_preview)

        pet_info_layout = QVBoxLayout()
        self.pet_name_label = QLabel("名称: -")
        self.pet_type_label = QLabel("类型: -")
        self.pet_bond_label = QLabel("羁绊: -")
        self.pet_mood_label = QLabel("心情: -")
        pet_info_layout.addWidget(self.pet_name_label)
        pet_info_layout.addWidget(self.pet_type_label)
        pet_info_layout.addWidget(self.pet_bond_label)
        pet_info_layout.addWidget(self.pet_mood_label)
        pet_info_layout.addStretch()
        pet_layout.addLayout(pet_info_layout)

        pet_group.setLayout(pet_layout)
        layout.addWidget(pet_group)

        # 快捷操作
        action_group = QGroupBox("⚡ 快捷操作")
        action_layout = QHBoxLayout()

        self.edit_avatar_btn = QPushButton("✏️ 编辑形象")
        self.edit_avatar_btn.clicked.connect(lambda: parent.tabs.setCurrentIndex(1))
        self.manage_pet_btn = QPushButton("🐾 管理宠物")
        self.manage_pet_btn.clicked.connect(lambda: parent.tabs.setCurrentIndex(2))
        self.visit_plaza_btn = QPushButton("🌳 访问广场")
        self.visit_plaza_btn.clicked.connect(lambda: parent.tabs.setCurrentIndex(3))
        self.view_social_btn = QPushButton("👥 查看社交")
        self.view_social_btn.clicked.connect(lambda: parent.tabs.setCurrentIndex(4))

        action_layout.addWidget(self.edit_avatar_btn)
        action_layout.addWidget(self.manage_pet_btn)
        action_layout.addWidget(self.visit_plaza_btn)
        action_layout.addWidget(self.view_social_btn)

        action_group.setLayout(action_layout)
        layout.addWidget(action_group)

        # 动态身份融合显示
        identity_group = QGroupBox("🎭 当前身份融合")
        identity_layout = QHBoxLayout()

        self.identity_dungeon = IdentityBar("🏰 地牢", 0.3, self)
        self.identity_werewolf = IdentityBar("🐺 狼人杀", 0.2, self)
        self.identity_escape = IdentityBar("🔐 密室", 0.1, self)
        self.identity_social = IdentityBar("🎉 社交", 0.4, self)

        identity_layout.addWidget(self.identity_dungeon)
        identity_layout.addWidget(self.identity_werewolf)
        identity_layout.addWidget(self.identity_escape)
        identity_layout.addWidget(self.identity_social)

        identity_group.setLayout(identity_layout)
        layout.addWidget(identity_group)

        self.setLayout(layout)

    def refresh(self, avatar, pet):
        """刷新显示"""
        if avatar:
            self.user_id_label.setText(f"用户ID: {avatar.get('user_id', '-')}")
            self.title_label.setText(f"称号: {avatar.get('title', '萌新')}")
            self.level_label.setText(f"等级: {avatar.get('level', 1)}")
            self.credit_label.setText(f"积分: {avatar.get('credits', 0)}")
            self.avatar_preview.update_avatar(avatar)

        if pet:
            self.pet_name_label.setText(f"名称: {pet.get('name', '-')}")
            self.pet_type_label.setText(f"类型: {pet.get('pet_type', '-')}")
            self.pet_bond_label.setText(f"羁绊: {pet.get('bond_level', 1)}")
            self.pet_mood_label.setText(f"心情: {pet.get('mood', '平静')}")
            self.pet_preview.update_pet(pet)


class AvatarEditTab(QWidget):
    """形象编辑标签页"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_panel = parent
        self.current_avatar = None
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QHBoxLayout(self)

        # 左侧：形象预览
        left_panel = QFrame()
        left_layout = QVBoxLayout(left_panel)

        preview_group = QGroupBox("👤 形象预览")
        preview_layout = QVBoxLayout()
        self.avatar_preview = AvatarPreviewWidget(self)
        self.avatar_preview.setMinimumSize(250, 300)
        preview_layout.addWidget(self.avatar_preview)
        preview_group.setLayout(preview_layout)
        left_layout.addWidget(preview_group)

        # 当前形象信息
        info_group = QGroupBox("📋 当前属性")
        info_layout = QFormLayout()
        self.body_style_label = QLabel("身体: 默认")
        self.face_style_label = QLabel("面部: 默认")
        self.hair_style_label = QLabel("发型: 默认")
        self.outfit_label = QLabel("服装: 默认")
        self.accessory_label = QLabel("配饰: 无")
        self.aura_label = QLabel("光环: 无")
        self.title_display_label = QLabel("称号: 萌新")
        info_layout.addRow("身体:", self.body_style_label)
        info_layout.addRow("面部:", self.face_style_label)
        info_layout.addRow("发型:", self.hair_style_label)
        info_layout.addRow("服装:", self.outfit_label)
        info_layout.addRow("配饰:", self.accessory_label)
        info_layout.addRow("光环:", self.aura_label)
        info_layout.addRow("称号:", self.title_display_label)
        info_group.setLayout(info_layout)
        left_layout.addWidget(info_group)

        layout.addWidget(left_panel, 1)

        # 右侧：编辑选项
        right_panel = QFrame()
        right_layout = QVBoxLayout(right_panel)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)

        # 基础身体
        body_group = QGroupBox("🦴 基础身体")
        body_layout = QHBoxLayout()
        self.body_combo = QComboBox()
        self.body_combo.addItems(["默认身体", "健壮", "苗条", "娇小"])
        self.body_color_btn = QPushButton("🎨 颜色")
        self.body_color_btn.clicked.connect(self.select_body_color)
        body_layout.addWidget(self.body_combo)
        body_layout.addWidget(self.body_color_btn)
        body_group.setLayout(body_layout)
        scroll_layout.addWidget(body_group)

        # 面部特征
        face_group = QGroupBox("😊 面部特征")
        face_layout = QHBoxLayout()
        self.face_combo = QComboBox()
        self.face_combo.addItems(["默认", "微笑", "冷酷", "萌系", "帅气"])
        self.eye_color_btn = QPushButton("👁️ 眼睛颜色")
        face_layout.addWidget(self.face_combo)
        face_layout.addWidget(self.eye_color_btn)
        face_group.setLayout(face_layout)
        scroll_layout.addWidget(face_group)

        # 发型
        hair_group = QGroupBox("💇 发型")
        hair_layout = QHBoxLayout()
        self.hair_combo = QComboBox()
        self.hair_combo.addItems(["短发", "长发", "卷发", "马尾", "光头", "莫西干"])
        self.hair_color_btn = QPushButton("🎨 发色")
        hair_layout.addWidget(self.hair_combo)
        hair_layout.addWidget(self.hair_color_btn)
        hair_group.setLayout(hair_layout)
        scroll_layout.addWidget(hair_group)

        # 服装
        outfit_group = QGroupBox("👕 服装")
        outfit_layout = QVBoxLayout()
        self.outfit_list = QListWidget()
        self.outfit_list.addItems(["休闲装", "正装", "运动装", "科幻装", "古典装", "魔法装"])
        outfit_layout.addWidget(self.outfit_list)
        outfit_group.setLayout(outfit_layout)
        scroll_layout.addWidget(outfit_group)

        # 配饰
        accessory_group = QGroupBox("💎 配饰")
        accessory_layout = QVBoxLayout()
        self.accessory_list = QListWidget()
        self.accessory_list.addItems(["无", "眼镜", "帽子", "耳环", "项链", "手套", "披风"])
        self.accessory_list.setMaximumHeight(100)
        accessory_layout.addWidget(self.accessory_list)
        accessory_group.setLayout(accessory_layout)
        scroll_layout.addWidget(accessory_group)

        # 光环效果
        aura_group = QGroupBox("✨ 光环效果")
        aura_layout = QGridLayout()
        self.aura_list = QListWidget()
        self.aura_list.addItems(["无", "基本发光", "火焰光环", "冰霜光环", "雷电光环", "神圣光环", "暗影光环"])
        aura_layout.addWidget(self.aura_list, 0, 0, 1, 2)
        aura_group.setLayout(aura_layout)
        scroll_layout.addWidget(aura_group)

        # 称号徽章
        badge_group = QGroupBox("🏅 称号徽章")
        badge_layout = QFormLayout()
        self.badge_combo = QComboBox()
        self.badge_combo.addItems(["无", "萌新", "地牢探险者", "狼人杀手", "密室逃脱王", "社交达人"])
        badge_layout.addRow("选择称号:", self.badge_combo)
        badge_group.setLayout(badge_layout)
        scroll_layout.addWidget(badge_group)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        right_layout.addWidget(scroll, 1)

        # 底部按钮
        btn_layout = QHBoxLayout()
        self.preview_btn = QPushButton("👁️ 预览")
        self.preview_btn.clicked.connect(self.on_preview)
        self.apply_btn = QPushButton("✅ 应用")
        self.apply_btn.clicked.connect(self.on_apply)
        self.reset_btn = QPushButton("🔄 重置")
        self.reset_btn.clicked.connect(self.on_reset)

        btn_layout.addWidget(self.preview_btn)
        btn_layout.addWidget(self.apply_btn)
        btn_layout.addWidget(self.reset_btn)
        right_layout.addLayout(btn_layout)

        layout.addWidget(right_panel, 1)

        self.setLayout(layout)

    def select_body_color(self):
        """选择身体颜色"""
        color = QColorDialog.getColor()
        if color.isValid():
            self.body_color = color

    def on_preview(self):
        """预览形象"""
        avatar = self.build_avatar_config()
        self.avatar_preview.update_avatar(avatar)

    def on_apply(self):
        """应用形象"""
        avatar = self.build_avatar_config()
        self.current_avatar = avatar
        if self.parent_panel.avatar_engine:
            asyncio.create_task(
                self.parent_panel.avatar_engine.update_user_avatar(
                    self.parent_panel.current_user_id, avatar
                )
            )

    def on_reset(self):
        """重置形象"""
        self.body_combo.setCurrentIndex(0)
        self.face_combo.setCurrentIndex(0)
        self.hair_combo.setCurrentIndex(0)
        self.outfit_list.clearSelection()
        self.accessory_list.clearSelection()
        self.aura_list.clearSelection()
        self.badge_combo.setCurrentIndex(0)

    def build_avatar_config(self) -> Dict:
        """构建形象配置"""
        selected_outfits = [item.text() for item in self.outfit_list.selectedItems()]
        selected_accessories = [item.text() for item in self.accessory_list.selectedItems()]
        selected_aura = self.aura_list.currentItem().text() if self.aura_list.currentItem() else "无"

        return {
            "user_id": self.parent_panel.current_user_id,
            "body": {
                "style": self.body_combo.currentText(),
                "color": getattr(self, 'body_color', QColor(255, 220, 177)).name()
            },
            "face": {
                "style": self.face_combo.currentText(),
            },
            "hair": {
                "style": self.hair_combo.currentText(),
            },
            "outfit": selected_outfits[0] if selected_outfits else "休闲装",
            "accessories": selected_accessories,
            "aura": selected_aura,
            "title": self.badge_combo.currentText()
        }

    def refresh(self, avatar):
        """刷新显示"""
        if not avatar:
            return
        self.current_avatar = avatar


class PetManagementTab(QWidget):
    """宠物管理标签页"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_panel = parent
        self.current_pet = None
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QHBoxLayout(self)

        # 左侧：宠物预览和信息
        left_panel = QFrame()
        left_layout = QVBoxLayout(left_panel)

        preview_group = QGroupBox("🐾 宠物预览")
        preview_layout = QVBoxLayout()
        self.pet_preview = PetPreviewWidget(self)
        self.pet_preview.setMinimumSize(200, 200)
        preview_layout.addWidget(self.pet_preview)
        preview_group.setLayout(preview_layout)
        left_layout.addWidget(preview_group)

        # 宠物状态
        status_group = QGroupBox("📊 宠物状态")
        status_layout = QGridLayout()
        self.pet_name_label = QLabel("名称: -")
        self.pet_type_label = QLabel("类型: -")
        self.pet_level_label = QLabel("等级: 1")
        self.pet_exp_label = QLabel("经验: 0/100")
        self.pet_bond_label = QLabel("羁绊: 1级")
        self.pet_mood_label = QLabel("心情: 开心")

        status_layout.addWidget(self.pet_name_label, 0, 0)
        status_layout.addWidget(self.pet_type_label, 0, 1)
        status_layout.addWidget(self.pet_level_label, 1, 0)
        status_layout.addWidget(self.pet_exp_label, 1, 1)
        status_layout.addWidget(self.pet_bond_label, 2, 0)
        status_layout.addWidget(self.pet_mood_label, 2, 1)
        status_group.setLayout(status_layout)
        left_layout.addWidget(status_group)

        # AI个性
        personality_group = QGroupBox("🧠 AI个性")
        personality_layout = QVBoxLayout()
        self.personality_text = QTextEdit()
        self.personality_text.setReadOnly(True)
        self.personality_text.setMaximumHeight(80)
        personality_layout.addWidget(self.personality_text)
        personality_group.setLayout(personality_layout)
        left_layout.addWidget(personality_group)

        layout.addWidget(left_panel, 1)

        # 右侧：宠物管理和交互
        right_panel = QFrame()
        right_layout = QVBoxLayout(right_panel)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)

        # 进化树
        evolution_group = QGroupBox("🌳 进化树")
        evolution_layout = QVBoxLayout()
        self.evolution_tree = PetEvolutionTreeView(self)
        self.evolution_tree.setMinimumHeight(200)
        evolution_layout.addWidget(self.evolution_tree)
        evolution_group.setLayout(evolution_layout)
        scroll_layout.addWidget(evolution_group)

        # 宠物交互
        interaction_group = QGroupBox("🎮 宠物交互")
        interaction_layout = QGridLayout()

        self.feed_btn = QPushButton("🍖 喂食")
        self.play_btn = QPushButton("🎾 玩耍")
        self.bath_btn = QPushButton("🛁 洗澡")
        self.train_btn = QPushButton("📚 训练")
        self.talk_btn = QPushButton("💬 对话")
        self.walk_btn = QPushButton("🚶 散步")

        interaction_layout.addWidget(self.feed_btn, 0, 0)
        interaction_layout.addWidget(self.play_btn, 0, 1)
        interaction_layout.addWidget(self.bath_btn, 0, 2)
        interaction_layout.addWidget(self.train_btn, 1, 0)
        interaction_layout.addWidget(self.talk_btn, 1, 1)
        interaction_layout.addWidget(self.walk_btn, 1, 2)

        interaction_group.setLayout(interaction_layout)
        scroll_layout.addWidget(interaction_group)

        # 羁绊技能
        bond_group = QGroupBox("💫 羁绊技能")
        bond_layout = QVBoxLayout()
        self.bond_skill_list = QListWidget()
        self.bond_skill_list.addItems([
            "1级: 基础陪伴 - 宠物会跟随主人",
            "2级: 情绪感应 - 感知主人情绪变化",
            "3级: 技能共享 - 部分技能可共享给主人",
            "4级: 灵魂共鸣 - 主人受伤时宠物可挡伤",
            "5级: 灵魂伴侣 - 完全同步，共同进化"
        ])
        bond_layout.addWidget(self.bond_skill_list)
        bond_group.setLayout(bond_layout)
        scroll_layout.addWidget(bond_group)

        # 宠物社交
        social_group = QGroupBox("🐾 宠物社交")
        social_layout = QHBoxLayout()
        self.find_friends_btn = QPushButton("🔍 寻找伙伴")
        self.party_btn = QPushButton("🎉 参加聚会")
        self.trade_btn = QPushButton("💱 宠物交易")
        social_layout.addWidget(self.find_friends_btn)
        social_layout.addWidget(self.party_btn)
        social_layout.addWidget(self.trade_btn)
        social_group.setLayout(social_layout)
        scroll_layout.addWidget(social_group)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        right_layout.addWidget(scroll, 1)

        # 底部按钮
        btn_layout = QHBoxLayout()
        self.evolve_btn = QPushButton("🌟 进化")
        self.evolve_btn.clicked.connect(self.on_evolve)
        self.release_btn = QPushButton("💨 放生")
        self.release_btn.clicked.connect(self.on_release)

        btn_layout.addWidget(self.evolve_btn)
        btn_layout.addWidget(self.release_btn)
        right_layout.addLayout(btn_layout)

        layout.addWidget(right_panel, 1)

        self.setLayout(layout)

    def on_evolve(self):
        """进化宠物"""
        if self.current_pet:
            dialog = EvolveDialog(self.current_pet, self)
            if dialog.exec():
                evolution_path = dialog.get_selected_path()
                # 执行进化

    def on_release(self):
        """放生宠物"""
        pass

    def refresh(self, pet):
        """刷新显示"""
        if not pet:
            return
        self.current_pet = pet
        self.pet_name_label.setText(f"名称: {pet.get('name', '-')}")
        self.pet_type_label.setText(f"类型: {pet.get('pet_type', '-')}")
        self.pet_level_label.setText(f"等级: {pet.get('level', 1)}")
        self.pet_bond_label.setText(f"羁绊: {pet.get('bond_level', 1)}级")
        self.pet_mood_label.setText(f"心情: {pet.get('mood', '开心')}")
        self.pet_preview.update_pet(pet)

        personality = pet.get('personality', {})
        personality_text = f"个性: {personality.get('type', '活泼')}\n行为: {personality.get('behavior', '好奇')}"
        self.personality_text.setText(personality_text)


class PlazaTab(QWidget):
    """虚拟社交广场标签页"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_panel = parent
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # 顶部：广场信息
        top_layout = QHBoxLayout()

        info_group = QGroupBox("🌳 广场信息")
        info_layout = QGridLayout()
        self.plaza_name_label = QLabel("广场: 中央广场")
        self.plaza_weather_label = QLabel("天气: 晴朗")
        self.plaza_time_label = QLabel("时间: 白天")
        self.online_count_label = QLabel("在线: 128人")
        info_layout.addWidget(self.plaza_name_label, 0, 0)
        info_layout.addWidget(self.plaza_weather_label, 0, 1)
        info_layout.addWidget(self.plaza_time_label, 1, 0)
        info_layout.addWidget(self.online_count_label, 1, 1)
        info_group.setLayout(info_layout)
        top_layout.addWidget(info_group)

        # 区域快速跳转
        area_group = QGroupBox("📍 区域跳转")
        area_layout = QHBoxLayout()
        area_buttons = [
            ("🏠 中央广场", 0),
            ("🎮 游戏区", 1),
            ("💬 聊天区", 2),
            ("🎭 表演区", 3),
            ("🌿 休息区", 4),
            ("🏪 市场区", 5),
            ("🎨 创作区", 6),
            ("🌙 夜间区", 7)
        ]
        for text, area_id in area_buttons:
            btn = QPushButton(text)
            btn.clicked.connect(lambda checked, a=area_id: self.jump_to_area(a))
            area_layout.addWidget(btn)
        area_group.setLayout(area_layout)
        top_layout.addWidget(area_group)

        layout.addLayout(top_layout)

        # 中央：广场视图
        self.plaza_view = PlazaVisualizationView(self)
        layout.addWidget(self.plaza_view, 1)

        # 底部：在线用户列表
        bottom_layout = QHBoxLayout()

        users_group = QGroupBox("👥 在线用户")
        users_layout = QVBoxLayout()
        self.users_list = QListWidget()
        self.users_list.setMaximumHeight(120)
        self.users_list.addItems([
            "用户A - 地牢探险者",
            "用户B - 狼人杀高手",
            "用户C - 社交达人",
            "用户D - 萌新",
            "用户E - 密室逃脱王"
        ])
        users_layout.addWidget(self.users_list)
        users_group.setLayout(users_layout)
        bottom_layout.addWidget(users_group, 1)

        # 宠物列表
        pets_group = QGroupBox("🐾 在线宠物")
        pets_layout = QVBoxLayout()
        self.pets_list = QListWidget()
        self.pets_list.setMaximumHeight(120)
        self.pets_list.addItems([
            "数字猫(用户A) - 赛博猫",
            "数据龙(用户B) - 成年龙",
            "AI凤凰(用户C) - 幼崽"
        ])
        pets_layout.addWidget(self.pets_list)
        pets_group.setLayout(pets_layout)
        bottom_layout.addWidget(pets_group, 1)

        # 活动日志
        log_group = QGroupBox("📜 广场动态")
        log_layout = QVBoxLayout()
        self.plaza_log = QListWidget()
        self.plaza_log.setMaximumHeight(120)
        self.plaza_log.addItems([
            "[系统] 用户A 进入了中央广场",
            "[宠物] 数字猫 正在玩耍",
            "[社交] 用户B 和 用户C 成为好友",
            "[系统] 夜间区已开放"
        ])
        log_layout.addWidget(self.plaza_log)
        log_group.setLayout(log_layout)
        bottom_layout.addWidget(log_group, 1)

        layout.addLayout(bottom_layout)

        self.setLayout(layout)

    def jump_to_area(self, area_id: int):
        """跳转到指定区域"""
        area_names = ["中央广场", "游戏区", "聊天区", "表演区", "休息区", "市场区", "创作区", "夜间区"]
        self.plaza_name_label.setText(f"广场: {area_names[area_id]}")
        self.plaza_view.set_current_area(area_id)


class SocialBondTab(QWidget):
    """社交羁绊标签页"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_panel = parent
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QHBoxLayout(self)

        # 左侧：关系网络
        left_panel = QFrame()
        left_layout = QVBoxLayout(left_panel)

        network_group = QGroupBox("🕸️ 社交关系网络")
        network_layout = QVBoxLayout()
        self.social_network_view = SocialNetworkView(self)
        self.social_network_view.setMinimumHeight(300)
        network_layout.addWidget(self.social_network_view)
        network_group.setLayout(network_layout)
        left_layout.addWidget(network_group, 1)

        # 关系统计
        stats_group = QGroupBox("📊 关系统计")
        stats_layout = QGridLayout()
        self.total_friends_label = QLabel("总好友数: 0")
        self.total_bonds_label = QLabel("总羁绊数: 0")
        self.energy_field_label = QLabel("能量场强度: 1级")
        stats_layout.addWidget(self.total_friends_label, 0, 0)
        stats_layout.addWidget(self.total_bonds_label, 0, 1)
        stats_layout.addWidget(self.energy_field_label, 1, 0)
        stats_group.setLayout(stats_layout)
        left_layout.addWidget(stats_group)

        layout.addWidget(left_panel, 1)

        # 右侧：好友列表和详情
        right_panel = QFrame()
        right_layout = QVBoxLayout(right_panel)

        # 好友列表
        friends_group = QGroupBox("👥 好友列表")
        friends_layout = QVBoxLayout()
        self.friends_list = QListWidget()
        self.friends_list.itemClicked.connect(self.on_friend_clicked)
        friends_layout.addWidget(self.friends_list)
        friends_group.setLayout(friends_layout)
        right_layout.addWidget(friends_group, 1)

        # 羁绊详情
        bond_detail_group = QGroupBox("💫 羁绊详情")
        bond_detail_layout = QFormLayout()
        self.friend_name_label = QLabel("-")
        self.bond_level_label = QLabel("羁绊等级: -")
        self.bond_progress = QProgressBar()
        self.bond_type_label = QLabel("羁绊类型: -")
        self.last_interaction_label = QLabel("最近互动: -")
        bond_detail_layout.addRow("好友:", self.friend_name_label)
        bond_detail_layout.addRow("羁绊等级:", self.bond_level_label)
        bond_detail_layout.addRow("进度:", self.bond_progress)
        bond_detail_layout.addRow("类型:", self.bond_type_label)
        bond_detail_layout.addRow("最近互动:", self.last_interaction_label)
        bond_detail_group.setLayout(bond_detail_layout)
        right_layout.addWidget(bond_detail_group)

        # 互动按钮
        action_layout = QHBoxLayout()
        self.chat_btn = QPushButton("💬 聊天")
        self.gift_btn = QPushButton("🎁 送礼")
        self.visit_btn = QPushButton("🚶 拜访")
        self.breakup_btn = QPushButton("💔 解除关系")
        action_layout.addWidget(self.chat_btn)
        action_layout.addWidget(self.gift_btn)
        action_layout.addWidget(self.visit_btn)
        action_layout.addWidget(self.breakup_btn)
        right_layout.addLayout(action_layout)

        layout.addWidget(right_panel, 1)

        self.setLayout(layout)

    def on_friend_clicked(self, item):
        """好友点击"""
        friend_name = item.text().split(" - ")[0]
        self.friend_name_label.setText(friend_name)
        self.bond_level_label.setText("羁绊等级: 2级")
        self.bond_progress.setValue(65)
        self.bond_type_label.setText("羁绊类型: 游戏伙伴")
        self.last_interaction_label.setText("最近互动: 10分钟前")


class AchievementAppearanceTab(QWidget):
    """成就解锁外观标签页"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_panel = parent
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # 顶部：成就概览
        top_layout = QHBoxLayout()

        # 成就统计
        stats_group = QGroupBox("📊 成就统计")
        stats_layout = QGridLayout()
        self.total_achievements_label = QLabel("总成就: 0/100")
        self.unlocked_label = QLabel("已解锁: 0")
        self.total_points_label = QLabel("成就点数: 0")
        stats_layout.addWidget(self.total_achievements_label, 0, 0)
        stats_layout.addWidget(self.unlocked_label, 0, 1)
        stats_layout.addWidget(self.total_points_label, 1, 0)
        stats_group.setLayout(stats_layout)
        top_layout.addWidget(stats_group)

        # 稀有度分布
        rarity_group = QGroupBox("💎 稀有度分布")
        rarity_layout = QHBoxLayout()
        self.rarity_common = QLabel("普通: 0")
        self.rarity_rare = QLabel("稀有: 0")
        self.rarity_epic = QLabel("史诗: 0")
        self.rarity_legendary = QLabel("传说: 0")
        rarity_layout.addWidget(self.rarity_common)
        rarity_layout.addWidget(self.rarity_rare)
        rarity_layout.addWidget(self.rarity_epic)
        rarity_layout.addWidget(self.rarity_legendary)
        rarity_group.setLayout(rarity_layout)
        top_layout.addWidget(rarity_group)

        layout.addLayout(top_layout)

        # 中央：成就画廊
        self.achievement_gallery = AchievementGalleryView(self)
        layout.addWidget(self.achievement_gallery, 1)

        # 底部：解锁的外观预览
        bottom_layout = QHBoxLayout()

        unlocked_group = QGroupBox("✨ 已解锁的外观")
        unlocked_layout = QHBoxLayout()
        self.unlocked_list = QListWidget()
        self.unlocked_list.addItems(["萌新光环", "地牢探险者服装", "社交达人徽章"])
        unlocked_layout.addWidget(self.unlocked_list)
        unlocked_group.setLayout(unlocked_layout)
        bottom_layout.addWidget(unlocked_group, 1)

        # 待解锁
        locked_group = QGroupBox("🔒 下一解锁")
        locked_layout = QVBoxLayout()
        self.next_unlock_label = QLabel("地牢通关者 - 完成一次地牢")
        self.next_unlock_progress = QProgressBar()
        self.next_unlock_progress.setValue(30)
        locked_layout.addWidget(self.next_unlock_label)
        locked_layout.addWidget(self.next_unlock_progress)
        locked_group.setLayout(locked_layout)
        bottom_layout.addWidget(locked_group, 1)

        layout.addLayout(bottom_layout)

        self.setLayout(layout)


class WeatherTimeTab(QWidget):
    """天气与时间影响标签页"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_panel = parent
        self.current_weather = "sunny"
        self.current_time_period = "day"
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QHBoxLayout(self)

        # 左侧：当前环境状态
        left_panel = QFrame()
        left_layout = QVBoxLayout(left_panel)

        # 天气和时间显示
        env_group = QGroupBox("🌤️ 当前环境")
        env_layout = QVBoxLayout()

        self.weather_display = WeatherDisplayWidget(self)
        self.weather_display.setMinimumSize(200, 150)
        env_layout.addWidget(self.weather_display)

        time_layout = QHBoxLayout()
        self.time_period_label = QLabel("时间段: 白天")
        self.time_progress = QProgressBar()
        self.time_progress.setValue(50)
        time_layout.addWidget(self.time_period_label)
        time_layout.addWidget(self.time_progress)
        env_layout.addLayout(time_layout)

        env_group.setLayout(env_layout)
        left_layout.addWidget(env_group)

        # 环境效果
        effect_group = QGroupBox("✨ 环境效果")
        effect_layout = QVBoxLayout()
        self.effect_list = QListWidget()
        self.effect_list.addItems([
            "形象亮度 +10%",
            "宠物行为: 活跃",
            "社交互动加成 +5%",
            "经验获取 +3%"
        ])
        effect_layout.addWidget(self.effect_list)
        effect_group.setLayout(effect_layout)
        left_layout.addWidget(effect_group)

        layout.addWidget(left_panel, 1)

        # 右侧：环境模拟和预览
        right_panel = QFrame()
        right_layout = QVBoxLayout(right_panel)

        # 环境模拟器
        simulator_group = QGroupBox("🎮 环境模拟器")
        simulator_layout = QVBoxLayout()

        # 天气选择
        weather_layout = QHBoxLayout()
        weather_label = QLabel("天气:")
        self.weather_combo = QComboBox()
        self.weather_combo.addItems(["☀️ 晴朗", "🌧️ 下雨", "❄️ 下雪", "🌫️ 雾", "⛈️ 雷暴"])
        self.weather_combo.currentIndexChanged.connect(self.on_weather_changed)
        weather_layout.addWidget(weather_label)
        weather_layout.addWidget(self.weather_combo)
        simulator_layout.addLayout(weather_layout)

        # 时间选择
        time_layout = QHBoxLayout()
        time_label = QLabel("时间:")
        self.time_combo = QComboBox()
        self.time_combo.addItems(["🌅 清晨", "☀️ 白天", "🌆 傍晚", "🌙 夜晚", "🌑 深夜"])
        self.time_combo.currentIndexChanged.connect(self.on_time_changed)
        time_layout.addWidget(time_label)
        time_layout.addWidget(self.time_combo)
        simulator_layout.addLayout(time_layout)

        # 预览效果
        preview_group = QGroupBox("👤 形象预览")
        preview_layout = QVBoxLayout()
        self.environment_preview = AvatarPreviewWidget(self)
        self.environment_preview.setMinimumSize(200, 250)
        preview_layout.addWidget(self.environment_preview)
        preview_group.setLayout(preview_layout)
        simulator_layout.addWidget(preview_group)

        # 应用按钮
        self.apply_env_btn = QPushButton("✅ 应用环境")
        self.apply_env_btn.clicked.connect(self.on_apply_environment)
        simulator_layout.addWidget(self.apply_env_btn)

        simulator_group.setLayout(simulator_layout)
        right_layout.addWidget(simulator_group)

        layout.addWidget(right_panel, 1)

        self.setLayout(layout)

    def on_weather_changed(self, index):
        """天气改变"""
        weather_map = ["sunny", "rainy", "snowy", "foggy", "stormy"]
        self.current_weather = weather_map[index]
        self.update_weather_display()

    def on_time_changed(self, index):
        """时间改变"""
        time_map = ["morning", "day", "evening", "night", "midnight"]
        self.current_time_period = time_map[index]
        time_labels = ["清晨", "白天", "傍晚", "夜晚", "深夜"]
        self.time_period_label.setText(f"时间段: {time_labels[index]}")
        self.update_environment_effects()

    def update_weather_display(self):
        """更新天气显示"""
        weather_icons = ["☀️", "🌧️", "❄️", "🌫️", "⛈️"]
        self.weather_display.set_weather(
            self.weather_combo.currentIndex(),
            self.current_time_period
        )

    def update_environment_effects(self):
        """更新环境影响"""
        self.effect_list.clear()

        # 根据时间和天气计算效果
        brightness = 100
        pet_activity = "正常"
        social_bonus = 0
        exp_bonus = 0

        if self.current_time_period == "day":
            brightness = 100
            pet_activity = "活跃"
            exp_bonus = 3
        elif self.current_time_period == "night":
            brightness = 60
            pet_activity = "安静"
            exp_bonus = 5
        elif self.current_time_period == "midnight":
            brightness = 30
            pet_activity = "睡眠"
            exp_bonus = 10

        if self.current_weather == "rainy":
            social_bonus = -5
        elif self.current_weather == "stormy":
            social_bonus = -10
            exp_bonus += 2

        self.effect_list.addItem(f"形象亮度 {brightness}%")
        self.effect_list.addItem(f"宠物行为: {pet_activity}")
        self.effect_list.addItem(f"社交互动加成 {social_bonus:+d}%")
        self.effect_list.addItem(f"经验获取 {exp_bonus:+d}%")

    def on_apply_environment(self):
        """应用环境设置"""
        self.update_environment_effects()
        self.update_weather_display()


class SettingsTab(QWidget):
    """设置标签页"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_panel = parent
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)

        # 基础设置
        basic_group = QGroupBox("🔧 基础设置")
        basic_layout = QFormLayout()
        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("输入用户名...")
        self.bio_edit = QTextEdit()
        self.bio_edit.setPlaceholderText("输入个人简介...")
        self.bio_edit.setMaximumHeight(60)
        self.auto_login_check = QCheckBox("启动时自动加载形象")
        self.show_pet_check = QCheckBox("在广场显示宠物")
        self.show_status_check = QCheckBox("在线状态对所有人可见")
        basic_layout.addRow("用户名:", self.username_edit)
        basic_layout.addRow("简介:", self.bio_edit)
        basic_layout.addRow("", self.auto_login_check)
        basic_layout.addRow("", self.show_pet_check)
        basic_layout.addRow("", self.show_status_check)
        basic_group.setLayout(basic_layout)
        scroll_layout.addWidget(basic_group)

        # 社交设置
        social_group = QGroupBox("👥 社交设置")
        social_layout = QFormLayout()
        self.friend_requests_check = QCheckBox("允许好友请求")
        self.group_invite_check = QCheckBox("允许群组邀请")
        self.pet_interaction_check = QCheckBox("允许宠物互动")
        self.visit_permission_combo = QComboBox()
        self.visit_permission_combo.addItems(["仅好友", "所有人", "仅自己"])
        social_layout.addRow("好友请求:", self.friend_requests_check)
        social_layout.addRow("群组邀请:", self.group_invite_check)
        social_layout.addRow("宠物互动:", self.pet_interaction_check)
        social_layout.addRow("拜访权限:", self.visit_permission_combo)
        social_group.setLayout(social_layout)
        scroll_layout.addWidget(social_group)

        # 通知设置
        notification_group = QGroupBox("🔔 通知设置")
        notification_layout = QFormLayout()
        self.friend_online_check = QCheckBox("好友上线通知")
        self.pet_event_check = QCheckBox("宠物事件通知")
        self.plaza_activity_check = QCheckBox("广场活动通知")
        self.system_msg_check = QCheckBox("系统消息通知")
        notification_layout.addRow("好友上线:", self.friend_online_check)
        notification_layout.addRow("宠物事件:", self.pet_event_check)
        notification_layout.addRow("广场活动:", self.plaza_activity_check)
        notification_layout.addRow("系统消息:", self.system_msg_check)
        notification_group.setLayout(notification_layout)
        scroll_layout.addWidget(notification_group)

        # 显示设置
        display_group = QGroupBox("🖥️ 显示设置")
        display_layout = QFormLayout()
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["低", "中", "高", "超高"])
        self.quality_combo.setCurrentIndex(2)
        self.animation_check = QCheckBox("启用动画效果")
        self.animation_check.setChecked(True)
        self.particle_check = QCheckBox("启用粒子效果")
        self.particle_check.setChecked(True)
        display_layout.addRow("渲染质量:", self.quality_combo)
        display_layout.addRow("", self.animation_check)
        display_layout.addRow("", self.particle_check)
        display_group.setLayout(display_layout)
        scroll_layout.addWidget(display_group)

        # 隐私设置
        privacy_group = QGroupBox("🔒 隐私设置")
        privacy_layout = QFormLayout()
        self.location_share_check = QCheckBox("在广场分享位置")
        self.activity_share_check = QCheckBox("分享活动动态")
        self.data_collection_check = QCheckBox("允许数据收集以改进体验")
        privacy_layout.addRow("位置分享:", self.location_share_check)
        privacy_layout.addRow("活动动态:", self.activity_share_check)
        privacy_layout.addRow("数据收集:", self.data_collection_check)
        privacy_group.setLayout(privacy_layout)
        scroll_layout.addWidget(privacy_group)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll, 1)

        # 底部按钮
        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton("💾 保存设置")
        self.save_btn.clicked.connect(self.on_save)
        self.reset_btn = QPushButton("🔄 恢复默认")
        self.reset_btn.clicked.connect(self.on_reset)
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.reset_btn)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def on_save(self):
        """保存设置"""
        pass

    def on_reset(self):
        """恢复默认"""
        self.username_edit.clear()
        self.bio_edit.clear()
        self.auto_login_check.setChecked(True)
        self.show_pet_check.setChecked(True)
        self.show_status_check.setChecked(True)


# ==================== 可视化组件 ====================

class AvatarPreviewWidget(QWidget):
    """虚拟形象预览组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.avatar_data = {}
        self.setStyleSheet("background-color: #1a1a2e; border-radius: 10px;")

    def update_avatar(self, avatar_data: Dict):
        """更新形象数据"""
        self.avatar_data = avatar_data
        self.update()

    def paintEvent(self, event):
        """绘制形象"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 获取中心点
        center_x = self.width() / 2
        center_y = self.height() / 2

        # 绘制背景光晕
        aura_color = QColor(100, 200, 255, 50)
        painter.setBrush(QBrush(aura_color))
        painter.drawEllipse(center_x - 80, center_y - 100, 160, 160)

        # 绘制身体
        body_color = QColor(255, 220, 177)
        if self.avatar_data.get("body", {}).get("color"):
            body_color = QColor(self.avatar_data["body"]["color"])
        painter.setBrush(QBrush(body_color))
        painter.drawEllipse(center_x - 30, center_y - 20, 60, 80)

        # 绘制头部
        painter.drawEllipse(center_x - 25, center_y - 80, 50, 50)

        # 绘制眼睛
        painter.setBrush(QBrush(QColor(50, 50, 50)))
        painter.drawEllipse(center_x - 15, center_y - 70, 8, 8)
        painter.drawEllipse(center_x + 7, center_y - 70, 8, 8)

        # 绘制表情
        if self.avatar_data.get("face", {}).get("style") == "微笑":
            painter.setPen(QPen(QColor(200, 100, 100), 2))
            painter.drawArc(center_x - 10, center_y - 55, 20, 10, 0, 180 * 16)
        elif self.avatar_data.get("face", {}).get("style") == "冷酷":
            painter.setPen(QPen(QColor(50, 50, 50), 2))
            painter.drawLine(center_x - 15, center_y - 68, center_x - 5, center_y - 65)
            painter.drawLine(center_x + 5, center_y - 65, center_x + 15, center_y - 68)

        # 绘制称号
        title = self.avatar_data.get("title", "萌新")
        painter.setFont(QFont("Microsoft YaHei", 8))
        painter.setPen(QPen(QColor(255, 215, 0)))
        painter.drawText(center_x - 30, center_y + 80, f"🏅 {title}")


class PetPreviewWidget(QWidget):
    """宠物预览组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pet_data = {}
        self.setStyleSheet("background-color: #16213e; border-radius: 10px;")

    def update_pet(self, pet_data: Dict):
        """更新宠物数据"""
        self.pet_data = pet_data
        self.update()

    def paintEvent(self, event):
        """绘制宠物"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        center_x = self.width() / 2
        center_y = self.height() / 2

        pet_type = self.pet_data.get("pet_type", "digital_cat")
        mood = self.pet_data.get("mood", "开心")

        # 根据宠物类型绘制不同形状
        if "cat" in pet_type.lower():
            self.draw_cat(painter, center_x, center_y, mood)
        elif "dragon" in pet_type.lower():
            self.draw_dragon(painter, center_x, center_y, mood)
        elif "phoenix" in pet_type.lower():
            self.draw_phoenix(painter, center_x, center_y, mood)
        elif "fox" in pet_type.lower():
            self.draw_fox(painter, center_x, center_y, mood)
        else:
            self.draw_default_pet(painter, center_x, center_y, mood)

        # 绘制宠物名
        name = self.pet_data.get("name", "宠物")
        painter.setFont(QFont("Microsoft YaHei", 9))
        painter.setPen(QPen(QColor(255, 255, 255)))
        painter.drawText(center_x - 30, self.height() - 20, f"🐾 {name}")

    def draw_cat(self, painter, cx, cy, mood):
        """绘制猫"""
        # 身体
        painter.setBrush(QBrush(QColor(100, 150, 255)))
        painter.drawEllipse(cx - 30, cy - 10, 60, 50)
        # 头
        painter.drawEllipse(cx - 20, cy - 40, 40, 40)
        # 耳朵
        painter.drawPolygon([
            cx - 20, cy - 40, cx - 30, cy - 60, cx - 10, cy - 45
        ])
        painter.drawPolygon([
            cx + 20, cy - 40, cx + 30, cy - 60, cx + 10, cy - 45
        ])
        # 眼睛
        eye_color = QColor(255, 255, 0) if mood == "开心" else QColor(100, 100, 100)
        painter.setBrush(QBrush(eye_color))
        painter.drawEllipse(cx - 12, cy - 35, 8, 8)
        painter.drawEllipse(cx + 4, cy - 35, 8, 8)

    def draw_dragon(self, painter, cx, cy, mood):
        """绘制龙"""
        # 身体
        painter.setBrush(QBrush(QColor(80, 200, 120)))
        painter.drawEllipse(cx - 35, cy, 70, 40)
        # 头
        painter.drawEllipse(cx - 25, cy - 45, 50, 45)
        # 角
        painter.setBrush(QBrush(QColor(255, 200, 50)))
        painter.drawPolygon([
            cx - 20, cy - 45, cx - 25, cy - 70, cx - 10, cy - 50
        ])
        painter.drawPolygon([
            cx + 20, cy - 45, cx + 25, cy - 70, cx + 10, cy - 50
        ])
        # 眼睛
        painter.setBrush(QBrush(QColor(255, 100, 0)))
        painter.drawEllipse(cx - 12, cy - 35, 8, 8)
        painter.drawEllipse(cx + 4, cy - 35, 8, 8)

    def draw_phoenix(self, painter, cx, cy, mood):
        """绘制凤凰"""
        # 翅膀
        painter.setBrush(QBrush(QColor(255, 100, 50)))
        painter.drawEllipse(cx - 50, cy - 20, 40, 30)
        painter.drawEllipse(cx + 10, cy - 20, 40, 30)
        # 身体
        painter.setBrush(QBrush(QColor(255, 150, 50)))
        painter.drawEllipse(cx - 20, cy - 10, 40, 50)
        # 头
        painter.drawEllipse(cx - 15, cy - 40, 30, 30)
        # 眼睛
        painter.setBrush(QBrush(QColor(255, 255, 0)))
        painter.drawEllipse(cx - 8, cy - 32, 6, 6)
        painter.drawEllipse(cx + 2, cy - 32, 6, 6)

    def draw_fox(self, painter, cx, cy, mood):
        """绘制狐狸"""
        # 身体
        painter.setBrush(QBrush(QColor(255, 130, 50)))
        painter.drawEllipse(cx - 25, cy - 5, 50, 40)
        # 头
        painter.drawEllipse(cx - 20, cy - 40, 40, 40)
        # 耳朵
        painter.drawPolygon([
            cx - 20, cy - 40, cx - 30, cy - 65, cx - 10, cy - 45
        ])
        painter.drawPolygon([
            cx + 20, cy - 40, cx + 30, cy - 65, cx + 10, cy - 45
        ])
        # 眼睛
        painter.setBrush(QBrush(QColor(50, 50, 50)))
        painter.drawEllipse(cx - 10, cy - 32, 6, 6)
        painter.drawEllipse(cx + 4, cy - 32, 6, 6)

    def draw_default_pet(self, painter, cx, cy, mood):
        """绘制默认宠物"""
        painter.setBrush(QBrush(QColor(150, 150, 255)))
        painter.drawEllipse(cx - 30, cy - 20, 60, 60)
        painter.drawEllipse(cx - 25, cy - 50, 50, 40)
        eye_color = QColor(255, 255, 0) if mood == "开心" else QColor(100, 100, 100)
        painter.setBrush(QBrush(eye_color))
        painter.drawEllipse(cx - 12, cy - 40, 8, 8)
        painter.drawEllipse(cx + 4, cy - 40, 8, 8)


class IdentityBar(QWidget):
    """身份融合进度条组件"""

    def __init__(self, label: str, value: float, parent=None):
        super().__init__(parent)
        self.label = label
        self.value = value
        self.setMinimumSize(80, 60)

    def set_value(self, value: float):
        """设置值"""
        self.value = value
        self.update()

    def paintEvent(self, event):
        """绘制"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 绘制标签
        painter.setFont(QFont("Microsoft YaHei", 8))
        painter.drawText(5, 15, self.label)

        # 绘制背景条
        painter.setBrush(QBrush(QColor(50, 50, 80)))
        painter.drawRoundedRect(5, 20, self.width() - 10, 20, 5)

        # 绘制进度
        progress_width = int((self.width() - 10) * self.value)
        color = QColor(100, 200, 255)
        painter.setBrush(QBrush(color))
        painter.drawRoundedRect(5, 20, progress_width, 20, 5)

        # 绘制百分比
        painter.setPen(QPen(QColor(255, 255, 255)))
        painter.drawText(5, 50, f"{int(self.value * 100)}%")


class PetEvolutionTreeView(QWidget):
    """宠物进化树视图"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_evolution = 0
        self.evolutions = [
            {"name": "幼崽期", "pets": ["数字猫", "数据龙", "AI凤凰", "量子狐"]},
            {"name": "成长期", "pets": ["赛博猫", "少年龙", "雏凤", "灵狐"]},
            {"name": "成熟期", "pets": ["机甲猫", "成年龙", "凤凰", "九尾狐"]},
            {"name": "完全体", "pets": ["量子豹", "神龙", "炽天使", "九尾妖狐"]}
        ]
        self.setStyleSheet("background-color: #1a1a2e; border-radius: 5px;")

    def paintEvent(self, event):
        """绘制进化树"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if not self.evolutions:
            return

        spacing_x = self.width() / (len(self.evolutions) + 1)

        # 绘制每个阶段的节点
        for i, stage in enumerate(self.evolutions):
            x = spacing_x * (i + 1)
            y = self.height() / 2 - 30

            # 绘制连接线
            if i > 0:
                prev_x = spacing_x * i
                painter.setPen(QPen(QColor(100, 100, 200), 2))
                painter.drawLine(prev_x, y + 15, x - 40, y + 15)

            # 绘制节点
            node_color = QColor(80, 150, 255) if i <= self.current_evolution else QColor(80, 80, 100)
            painter.setBrush(QBrush(node_color))
            painter.drawRoundedRect(x - 40, y, 80, 30, 10)

            # 绘制文字
            painter.setPen(QPen(QColor(255, 255, 255)))
            painter.setFont(QFont("Microsoft YaHei", 9))
            painter.drawText(x - 35, y + 20, stage["name"])


class PlazaVisualizationView(QWidget):
    """社交广场可视化视图"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_area = 0
        self.users = []
        self.pets = []
        self.setStyleSheet("background-color: #0f0f23; border-radius: 10px;")

    def set_current_area(self, area_id: int):
        """设置当前区域"""
        self.current_area = area_id
        self.update()

    def update_users(self, users):
        """更新用户列表"""
        self.users = users
        self.update()

    def paintEvent(self, event):
        """绘制广场"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 绘制背景网格
        painter.setPen(QPen(QColor(40, 40, 80), 1))
        for x in range(0, self.width(), 40):
            painter.drawLine(x, 0, x, self.height())
        for y in range(0, self.height(), 40):
            painter.drawLine(0, y, self.width(), y)

        # 绘制区域标识
        area_names = ["中央广场", "游戏区", "聊天区", "表演区", "休息区", "市场区", "创作区", "夜间区"]
        painter.setFont(QFont("Microsoft YaHei", 16, QFont.Weight.Bold))
        painter.setPen(QPen(QColor(255, 215, 0)))
        painter.drawText(self.width() // 2 - 80, 40, f"🌳 {area_names[self.current_area]}")

        # 绘制几个示例用户
        import random
        random.seed(42)
        for i in range(5):
            x = random.randint(50, self.width() - 50)
            y = random.randint(80, self.height() - 50)

            # 用户光环
            painter.setBrush(QBrush(QColor(100, 200, 255, 30)))
            painter.drawEllipse(x - 25, y - 25, 50, 50)

            # 用户图标
            painter.setBrush(QBrush(QColor(100, 150, 255)))
            painter.drawEllipse(x - 10, y - 15, 20, 25)
            painter.drawEllipse(x - 8, y - 30, 16, 16)

        # 绘制宠物
        random.seed(123)
        for i in range(3):
            x = random.randint(50, self.width() - 50)
            y = random.randint(80, self.height() - 50)

            # 宠物光晕
            painter.setBrush(QBrush(QColor(255, 150, 100, 30)))
            painter.drawEllipse(x - 20, y - 20, 40, 40)

            # 宠物图标
            painter.setBrush(QBrush(QColor(255, 150, 50)))
            painter.drawEllipse(x - 12, y - 12, 24, 24)


class SocialNetworkView(QWidget):
    """社交网络视图"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.friends = [
            {"name": "用户A", "bond": 0.8, "x": 0.3, "y": 0.3},
            {"name": "用户B", "bond": 0.6, "x": 0.7, "y": 0.3},
            {"name": "用户C", "bond": 0.9, "x": 0.5, "y": 0.6},
            {"name": "用户D", "bond": 0.4, "x": 0.2, "y": 0.7},
            {"name": "用户E", "bond": 0.7, "x": 0.8, "y": 0.7}
        ]
        self.self_pos = {"x": 0.5, "y": 0.45}
        self.setStyleSheet("background-color: #1a1a2e; border-radius: 10px;")

    def paintEvent(self, event):
        """绘制社交网络"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 绘制连线
        for friend in self.friends:
            start_x = self.self_pos["x"] * self.width()
            start_y = self.self_pos["y"] * self.height()
            end_x = friend["x"] * self.width()
            end_y = friend["y"] * self.height()

            # 根据羁绊强度设置线宽和透明度
            line_width = int(friend["bond"] * 3)
            alpha = int(friend["bond"] * 200)
            painter.setPen(QPen(QColor(100, 200, 255, alpha), line_width))
            painter.drawLine(int(start_x), int(start_y), int(end_x), int(end_y))

        # 绘制好友节点
        for friend in self.friends:
            x = friend["x"] * self.width()
            y = friend["y"] * self.height()
            size = 15 + friend["bond"] * 10

            # 节点光晕
            painter.setBrush(QBrush(QColor(80, 150, 255, 50)))
            painter.drawEllipse(x - size, y - size, size * 2, size * 2)

            # 节点
            color = QColor(80, 150, 255)
            painter.setBrush(QBrush(color))
            painter.drawEllipse(x - size / 2, y - size / 2, size, size)

            # 名称
            painter.setFont(QFont("Microsoft YaHei", 7))
            painter.setPen(QPen(QColor(255, 255, 255)))
            painter.drawText(x - 20, y + size + 10, friend["name"])

        # 绘制自己
        self_x = self.self_pos["x"] * self.width()
        self_y = self.self_pos["y"] * self.height()

        # 自己光环
        painter.setBrush(QBrush(QColor(255, 215, 0, 50)))
        painter.drawEllipse(self_x - 30, self_y - 30, 60, 60)

        # 自己节点
        painter.setBrush(QBrush(QColor(255, 215, 0)))
        painter.drawEllipse(self_x - 12, self_y - 12, 24, 24)

        # 自己标签
        painter.setFont(QFont("Microsoft YaHei", 8, QFont.Weight.Bold))
        painter.setPen(QPen(QColor(255, 255, 255)))
        painter.drawText(self_x - 15, self_y + 30, "我")


class AchievementGalleryView(QWidget):
    """成就画廊视图"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.achievements = [
            {"name": "初次见面", "rarity": "common", "unlocked": True},
            {"name": "社交达人", "rarity": "rare", "unlocked": True},
            {"name": "地牢探险者", "rarity": "epic", "unlocked": False},
            {"name": "狼人杀手", "rarity": "rare", "unlocked": False},
            {"name": "密室逃脱王", "rarity": "legendary", "unlocked": False},
            {"name": "宠物训练师", "rarity": "common", "unlocked": True},
            {"name": "积分大亨", "rarity": "epic", "unlocked": False},
            {"name": "连续登录7天", "rarity": "common", "unlocked": True}
        ]
        self.setStyleSheet("background-color: #1a1a2e; border-radius: 10px;")

    def paintEvent(self, event):
        """绘制成就画廊"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        spacing_x = self.width() / 4
        spacing_y = 100

        for i, achievement in enumerate(self.achievements):
            col = i % 4
            row = i // 4
            x = spacing_x * col + spacing_x / 2
            y = spacing_y * row + 50

            # 稀有度颜色
            rarity_colors = {
                "common": QColor(150, 150, 150),
                "rare": QColor(80, 150, 255),
                "epic": QColor(180, 100, 255),
                "legendary": QColor(255, 180, 50)
            }
            color = rarity_colors.get(achievement["rarity"], QColor(150, 150, 150))

            # 成就框
            if achievement["unlocked"]:
                painter.setBrush(QBrush(color))
            else:
                painter.setBrush(QBrush(QColor(60, 60, 60)))
            painter.drawRoundedRect(x - 35, y - 35, 70, 70, 10)

            # 成就图标
            if achievement["unlocked"]:
                painter.setPen(QPen(QColor(255, 255, 255)))
                painter.setFont(QFont("Microsoft YaHei", 20))
                painter.drawText(x - 15, y + 8, "🏆")
            else:
                painter.setPen(QPen(QColor(100, 100, 100)))
                painter.setFont(QFont("Microsoft YaHei", 20))
                painter.drawText(x - 15, y + 8, "🔒")

            # 成就名称
            painter.setFont(QFont("Microsoft YaHei", 8))
            if achievement["unlocked"]:
                painter.setPen(QPen(QColor(255, 255, 255)))
            else:
                painter.setPen(QPen(QColor(150, 150, 150)))
            painter.drawText(x - 30, y + 55, achievement["name"])


class WeatherDisplayWidget(QWidget):
    """天气显示组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.weather = 0  # 0=sunny, 1=rainy, 2=snowy, 3=foggy, 4=stormy
        self.time_period = "day"
        self.setStyleSheet("background-color: #16213e; border-radius: 10px;")

    def set_weather(self, weather: int, time_period: str):
        """设置天气"""
        self.weather = weather
        self.time_period = time_period
        self.update()

    def paintEvent(self, event):
        """绘制天气"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        center_x = self.width() / 2
        center_y = self.height() / 2

        weather_icons = ["☀️", "🌧️", "❄️", "🌫️", "⛈️"]
        time_icons = {"morning": "🌅", "day": "☀️", "evening": "🌆", "night": "🌙", "midnight": "🌑"}

        # 绘制背景
        if self.time_period in ["night", "midnight"]:
            painter.setBrush(QBrush(QColor(20, 20, 60)))
        else:
            painter.setBrush(QBrush(QColor(100, 150, 200)))
        painter.drawRoundedRect(0, 0, self.width(), self.height(), 10)

        # 绘制天气图标
        painter.setFont(QFont("Microsoft YaHei", 40))
        painter.setPen(QPen(QColor(255, 255, 255)))
        painter.drawText(center_x - 25, center_y + 15, weather_icons[self.weather])

        # 绘制时间图标
        painter.setFont(QFont("Microsoft YaHei", 20))
        painter.drawText(10, 30, time_icons.get(self.time_period, "☀️"))


# ==================== 对话框 ====================

class EvolveDialog(QDialog):
    """宠物进化对话框"""

    def __init__(self, pet_data, parent=None):
        super().__init__(parent)
        self.pet_data = pet_data
        self.selected_path = None
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("🌟 宠物进化")
        self.setMinimumSize(400, 300)

        layout = QVBoxLayout(self)

        # 标题
        title = QLabel(f"选择 {self.pet_data.get('name', '宠物')} 的进化路径")
        title.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        layout.addWidget(title)

        # 进化选项
        self.evolution_list = QListWidget()
        evolutions = self.get_evolution_options()
        for evo in evolutions:
            self.evolution_list.addItem(f"{evo['icon']} {evo['name']} - {evo['description']}")
        layout.addWidget(self.evolution_list)

        # 按钮
        btn_layout = QHBoxLayout()
        confirm_btn = QPushButton("✅ 确认进化")
        confirm_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("❌ 取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(confirm_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def get_evolution_options(self):
        """获取进化选项"""
        pet_type = self.pet_data.get("pet_type", "digital_cat")
        if "cat" in pet_type.lower():
            return [
                {"icon": "🤖", "name": "赛博猫", "description": "机械与科技的结合"},
                {"icon": "⚡", "name": "闪电猫", "description": "掌控雷电之力"},
                {"icon": "🔮", "name": "量子猫", "description": "跨越次元的存在"}
            ]
        elif "dragon" in pet_type.lower():
            return [
                {"icon": "🔥", "name": "炎龙", "description": "掌控火焰之力"},
                {"icon": "❄️", "name": "冰龙", "description": "掌控冰雪之力"},
                {"icon": "⚡", "name": "雷龙", "description": "掌控雷电之力"}
            ]
        return [{"icon": "✨", "name": "进化", "description": "默认进化路径"}]

    def get_selected_path(self):
        """获取选中的进化路径"""
        current_row = self.evolution_list.currentRow()
        if current_row >= 0:
            options = self.get_evolution_options()
            return options[current_row]["name"]
        return None


# ==================== 便捷函数 ====================

def create_virtual_avatar_social_panel(parent=None) -> VirtualAvatarSocialPanel:
    """创建虚拟形象与社交广场面板"""
    panel = VirtualAvatarSocialPanel(parent)
    return panel
