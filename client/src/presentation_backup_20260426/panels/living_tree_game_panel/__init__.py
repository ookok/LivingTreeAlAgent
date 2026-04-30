# living_tree_game_panel/__init__.py
# 生命之树趣味游戏 PyQt6 UI面板

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QLabel,
    QPushButton, QScrollArea, QProgressBar, QFrame, QGridLayout,
    QComboBox, QGroupBox, QLineEdit, QTextEdit, QSpinBox,
    QProgressDialog, QMessageBox, QSlider, QCheckBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont, QPixmap, QPainter, QLinearGradient, QColor
from typing import Dict, List, Optional
import random

# 尝试导入游戏系统
try:
    from .business.living_tree_game import (
        LivingTreeGameManager, ForestAdventure, NumberPuzzleGame,
        LifeTreeNurturing, EcologyMiniGames, SeasonalFestival,
        AIForestPet, EcologyAchievementChain, WeatherImpactSystem,
        Weather, TreeStage
    )
    GAME_SYSTEM_AVAILABLE = True
except ImportError:
    GAME_SYSTEM_AVAILABLE = False


# ==================== 模拟游戏系统 ====================

class MockGameSystem:
    """当游戏系统不可用时的模拟版本"""

    def __init__(self):
        self.weather = "sunny"
        self.user_tree = {
            "stage": "sapling", "health": 250, "growth": 120,
            "happiness": 75, "size": 3
        }
        self.treasures = [
            {"id": "rusty_key", "name": "生锈的钥匙", "rarity": "common", "icon": "🗝️", "credits": 10},
            {"id": "enchanted_acorn", "name": "附魔橡果", "rarity": "uncommon", "icon": "🌰", "credits": 75},
            {"id": "golden_root", "name": "金根", "rarity": "rare", "icon": "🟡", "credits": 200},
            {"id": "tree_heart", "name": "树心", "rarity": "epic", "icon": "💚", "credits": 1000},
            {"id": "world_tree_leaf", "name": "世界树叶", "rarity": "legendary", "icon": "🍃", "credits": 5000},
        ]
        self.mini_games = [
            {"id": "pollination_race", "name": "授粉竞赛", "icon": "🐝", "high_score": 850},
            {"id": "water_cycle", "name": "水循环挑战", "icon": "💧", "high_score": 720},
            {"id": "food_chain", "name": "食物链平衡", "icon": "🦎", "high_score": 980},
            {"id": "seed_dispersal", "name": "种子传播", "icon": "🌬️", "high_score": 1100},
        ]
        self.pets = [
            {"type": "fire_spirit", "name": "小火焰", "icon": "🔥", "level": 5},
            {"type": "water_sprite", "name": "水滴", "icon": "💧", "level": 3},
            {"type": "forest_elf", "name": "森林精灵", "icon": "🌲", "level": 8},
        ]
        self.ecology_chains = [
            {"id": "plant_tree", "name": "植树者", "progress": 65, "completed": False},
            {"id": "protect_wildlife", "name": "野生动物保护者", "progress": 30, "completed": False},
            {"id": "clean_environment", "name": "环境清洁工", "progress": 100, "completed": True},
        ]
        self.season = "spring_bloom"
        self.current_event = {
            "name": "春日花开", "icon": "🌸", "progress": 45,
            "participants": 1234, "time_left": "7天"
        }

    def get_weather(self):
        return self.weather

    def get_tree_info(self):
        return self.user_tree

    def get_user_balance(self):
        return 15680


# ==================== 主面板 ====================

class LivingTreeGamePanel(QWidget):
    """生命之树趣味游戏主面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.game_system = MockGameSystem() if not GAME_SYSTEM_AVAILABLE else None
        self.setup_ui()
        self.refresh_display()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # 标题栏
        header = QWidget()
        header.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2E7D32, stop:1 #4CAF50); padding: 15px;")
        header_layout = QHBoxLayout(header)

        title = QLabel("🌳 生命之树趣味游戏")
        title.setFont(QFont("Microsoft YaHei", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: white;")
        header_layout.addWidget(title)

        subtitle = QLabel("将严肃的积分经济转化为有趣的生命探索")
        subtitle.setStyleSheet("color: rgba(255,255,255,0.8); font-size: 12px;")
        header_layout.addWidget(subtitle)

        header_layout.addStretch()

        # 天气显示
        weather_btn = QPushButton("☀️ 晴朗")
        weather_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255,255,255,0.2);
                color: white;
                border: 1px solid rgba(255,255,255,0.3);
                border-radius: 15px;
                padding: 8px 16px;
            }
        """)
        header_layout.addWidget(weather_btn)

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
                color: #2E7D32;
                font-weight: bold;
            }
        """)

        # 添加各标签页
        self.tabs.addTab(self.create_forest_tab(), "🌲 森林探险")
        self.tabs.addTab(self.create_puzzle_tab(), "🔢 数字猜谜")
        self.tabs.addTab(self.create_tree_tab(), "🌳 生命之树")
        self.tabs.addTab(self.create_minigames_tab(), "🎮 生态游戏")
        self.tabs.addTab(self.create_pet_tab(), "🐾 AI宠物")
        self.tabs.addTab(self.create_ecology_tab(), "🌍 生态成就")
        self.tabs.addTab(self.create_credit_tab(), "💰 积分系统")
        self.tabs.addTab(self.create_event_tab(), "🎉 季节庆典")

        main_layout.addWidget(self.tabs)

    def create_forest_tab(self) -> QWidget:
        """森林探险标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # 介绍
        intro = QLabel("""
        <div style='font-size: 14px; color: #333; line-height: 1.8;'>
        <b>🌲 森林探险挖宝</b><br>
        在神秘的森林中挖掘宝藏！使用体力值在不同地点进行挖掘，<br>
        天气、时间和季节都会影响您找到稀有宝藏的机会！
        </div>
        """)
        layout.addWidget(intro)

        # 地点选择
        location_group = QGroupBox("选择挖掘地点")
        location_layout = QHBoxLayout(location_group)

        locations = [
            ("forest_edge", "森林边缘", "🪵"),
            ("deep_forest", "森林深处", "🌲"),
            ("riverbank", "河岸", "🏞️"),
            ("mountain", "山峰", "⛰️")
        ]

        self.selected_location = "deep_forest"
        for loc_id, loc_name, loc_icon in locations:
            btn = QPushButton(f"{loc_icon}\n{loc_name}")
            btn.setStyleSheet("""
                QPushButton {
                    background-color: white;
                    border: 2px solid #e0e0e0;
                    border-radius: 10px;
                    padding: 15px;
                    min-width: 100px;
                }
                QPushButton:hover {
                    border-color: #4CAF50;
                }
            """)
            if loc_id == "deep_forest":
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #E8F5E9;
                        border: 2px solid #4CAF50;
                        border-radius: 10px;
                        padding: 15px;
                        min-width: 100px;
                    }
                """)
            btn.clicked.connect(lambda checked, l=loc_id: self.select_location(l))
            location_layout.addWidget(btn)

        layout.addWidget(location_group)

        # 挖掘按钮和结果
        action_layout = QHBoxLayout()

        self.stamina_label = QLabel("体力: 100/100")
        self.stamina_label.setFont(QFont("Microsoft YaHei", 11))
        action_layout.addWidget(self.stamina_label)

        dig_btn = QPushButton("⛏️ 开始挖掘")
        dig_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 30px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        dig_btn.clicked.connect(self.perform_dig)
        action_layout.addWidget(dig_btn)

        action_layout.addStretch()

        layout.addLayout(action_layout)

        # 宝藏展示
        treasure_group = QGroupBox("最近获得的宝藏")
        treasure_layout = QGridLayout(treasure_group)

        treasures = self.game_system.treasures[:4]
        for i, treasure in enumerate(treasures):
            card = self.create_treasure_card(treasure)
            treasure_layout.addWidget(card, i // 4, i % 4)

        layout.addWidget(treasure_group)

        # 宝藏图鉴
        gallery_group = QGroupBox("宝藏图鉴")
        gallery_layout = QHBoxLayout(gallery_group)

        for treasure in self.game_system.treasures:
            icon_label = QLabel(treasure["icon"])
            icon_label.setFont(QFont("Segoe UI Emoji", 24))
            icon_label.setToolTip(f"{treasure['name']} - {treasure['rarity']}")
            gallery_layout.addWidget(icon_label)

        layout.addWidget(gallery_group)

        layout.addStretch()
        return widget

    def create_treasure_card(self, treasure: Dict) -> QWidget:
        """创建宝藏卡片"""
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 10px;
                border: 1px solid #e0e0e0;
            }
        """)
        layout = QVBoxLayout(card)
        layout.setSpacing(5)

        icon = QLabel(treasure["icon"])
        icon.setFont(QFont("Segoe UI Emoji", 32))
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon)

        name = QLabel(treasure["name"])
        name.setFont(QFont("Microsoft YaHei", 10))
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(name)

        rarity_colors = {"common": "#9e9e9e", "uncommon": "#4caf50", "rare": "#2196f3", "epic": "#9c27b0", "legendary": "#ffc107"}
        rarity = QLabel(treasure["rarity"])
        rarity.setStyleSheet(f"color: {rarity_colors.get(treasure['rarity'], '#9e9e9e')}; font-size: 10px;")
        rarity.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(rarity)

        return card

    def select_location(self, location: str):
        """选择地点"""
        self.selected_location = location

    def perform_dig(self):
        """执行挖掘"""
        result_label = QLabel("🔍 正在挖掘中...")
        result_label.setFont(QFont("Microsoft YaHei", 12))
        result_label.setStyleSheet("color: #4CAF50; padding: 10px;")

        # 模拟挖掘结果
        treasure = random.choice(self.game_system.treasures)

        # 显示结果
        result_dialog = QMessageBox(self)
        result_dialog.setWindowTitle("挖掘结果")
        result_dialog.setText(f"{treasure['icon']} 恭喜获得 {treasure['name']}！\n\n稀有度: {treasure['rarity']}\n积分: +{treasure['credits']}")
        result_dialog.exec()

    def create_puzzle_tab(self) -> QWidget:
        """数字猜谜标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # 介绍
        intro = QLabel("""
        <div style='font-size: 14px; color: #333; line-height: 1.8;'>
        <b>🔢 数字猜谜游戏</b><br>
        猜测神秘数字！系统会给出提示，告诉您猜对了几个数字及其位置。<br>
        <b>提示格式: XAYB</b> - A表示位置正确的数字，B表示数字正确但位置错误。
        </div>
        """)
        layout.addWidget(intro)

        # 难度选择
        difficulty_group = QGroupBox("选择难度")
        difficulty_layout = QHBoxLayout(difficulty_group)

        difficulties = [
            ("easy", "简单 (3位)", "😊"),
            ("medium", "中等 (4位)", "🤔"),
            ("hard", "困难 (5位)", "😰"),
            ("expert", "专家 (6位)", "🧙")
        ]

        for diff_id, diff_name, diff_icon in difficulties:
            btn = QPushButton(f"{diff_icon}\n{diff_name}")
            btn.setStyleSheet("""
                QPushButton {
                    background-color: white;
                    border: 2px solid #e0e0e0;
                    border-radius: 10px;
                    padding: 15px;
                }
            """)
            difficulty_layout.addWidget(btn)

        layout.addWidget(difficulty_group)

        # 游戏区域
        game_group = QGroupBox("猜谜游戏")
        game_layout = QVBoxLayout(game_group)

        # 神秘数字提示
        hint_layout = QHBoxLayout()
        hint_layout.addWidget(QLabel("提示: "))
        hint_label = QLabel("? ? ? ?")
        hint_label.setFont(QFont("Microsoft YaHei", 24))
        hint_label.setStyleSheet("color: #2196F3; letter-spacing: 10px;")
        hint_layout.addWidget(hint_label)
        hint_layout.addStretch()
        game_layout.addLayout(hint_layout)

        # 猜测输入
        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("您的猜测:"))

        guess_input = QLineEdit()
        guess_input.setPlaceholderText("输入数字...")
        guess_input.setMaxLength(6)
        guess_input.setStyleSheet("""
            QLineEdit {
                border: 2px solid #e0e0e0;
                border-radius: 6px;
                padding: 8px;
                font-size: 16px;
            }
        """)
        guess_input.setFixedWidth(150)
        input_layout.addWidget(guess_input)

        guess_btn = QPushButton("猜测")
        guess_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
            }
        """)
        input_layout.addWidget(guess_btn)

        input_layout.addStretch()
        game_layout.addLayout(input_layout)

        # 历史记录
        history_label = QLabel("猜测历史: ")
        history_label.setFont(QFont("Microsoft YaHei", 10))
        history_label.setStyleSheet("color: #666;")
        game_layout.addWidget(history_label)

        layout.addWidget(game_group)

        # 统计
        stats_group = QGroupBox("游戏统计")
        stats_layout = QHBoxLayout(stats_group)

        stats = [("胜场", "23", "🏆"), ("负场", "5", "❌"), ("最高连胜", "8", "🔥"), ("总积分", "2,350", "💰")]
        for stat_name, stat_value, stat_icon in stats:
            stat_frame = QFrame()
            stat_frame.setStyleSheet("background-color: #f5f5f5; border-radius: 8px; padding: 10px;")
            stat_layout = QVBoxLayout(stat_frame)
            stat_layout.setSpacing(3)

            icon_label = QLabel(stat_icon)
            icon_label.setFont(QFont("Segoe UI Emoji", 16))
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            stat_layout.addWidget(icon_label)

            value_label = QLabel(stat_value)
            value_label.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
            value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            stat_layout.addWidget(value_label)

            name_label = QLabel(stat_name)
            name_label.setFont(QFont("Microsoft YaHei", 9))
            name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            name_label.setStyleSheet("color: #888;")
            stat_layout.addWidget(name_label)

            stats_layout.addWidget(stat_frame)

        layout.addWidget(stats_group)

        layout.addStretch()
        return widget

    def create_tree_tab(self) -> QWidget:
        """生命之树标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # 树信息
        tree_info = self.game_system.get_tree_info()

        tree_group = QGroupBox("🌳 您的生命之树")
        tree_layout = QVBoxLayout(tree_group)

        # 树可视化
        tree_display = QWidget()
        tree_display.setFixedHeight(150)
        tree_display.setStyleSheet("background-color: #E8F5E9; border-radius: 10px;")
        tree_layout.addWidget(tree_display)

        # 属性
        attr_layout = QHBoxLayout()

        stage_labels = {"seed": "种子", "sapling": "幼苗", "young": "青年", "mature": "成熟", "ancient": "古老", "world_tree": "世界树"}
        stage_label = QLabel(f"阶段: {stage_labels.get(tree_info['stage'], tree_info['stage'])}")
        stage_label.setFont(QFont("Microsoft YaHei", 11))
        attr_layout.addWidget(stage_label)

        health_label = QLabel(f"生命值: {tree_info['health']}")
        health_label.setFont(QFont("Microsoft YaHei", 11))
        attr_layout.addWidget(health_label)

        happiness_label = QLabel(f"幸福度: {tree_info['happiness']}%")
        happiness_label.setFont(QFont("Microsoft YaHei", 11))
        happiness_label.setStyleSheet("color: #FF9800;")
        attr_layout.addWidget(happiness_label)

        attr_layout.addStretch()
        tree_layout.addLayout(attr_layout)

        # 成长进度
        progress_layout = QHBoxLayout()
        progress_layout.addWidget(QLabel("成长进度:"))

        progress_bar = QProgressBar()
        progress_bar.setValue(int(tree_info['growth'] / 10))
        progress_bar.setFixedHeight(15)
        progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                background-color: #e0e0e0;
                border-radius: 8px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4CAF50, stop:1 #8BC34A);
                border-radius: 8px;
            }
        """)
        progress_layout.addWidget(progress_bar)

        tree_layout.addLayout(progress_layout)

        layout.addWidget(tree_group)

        # 培育操作
        action_group = QGroupBox("培育操作")
        action_layout = QGridLayout(action_group)

        actions = [
            ("💧 浇水", "water", 10),
            ("🌱 施肥", "fertilize", 20),
            ("✂️ 修剪", "prune", 5),
            ("💬 交流", "talk", 2),
            ("🎵 唱歌", "sing", 5),
            ("🧘 冥想", "meditate", 8)
        ]

        for i, (action_name, action_id, cost) in enumerate(actions):
            btn = QPushButton(f"{action_name}\n-{cost}体力")
            btn.setStyleSheet("""
                QPushButton {
                    background-color: white;
                    border: 2px solid #4CAF50;
                    border-radius: 10px;
                    padding: 15px;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #E8F5E9;
                }
            """)
            action_layout.addWidget(btn, i // 3, i % 3)

        layout.addWidget(action_group)

        # 果实
        fruit_group = QGroupBox("🍎 果树产出")
        fruit_layout = QHBoxLayout(fruit_group)

        fruits = ["🍎 生命果", "🍇 智慧果", "🍊 金果", "🍄 神秘果"]
        for fruit in fruits:
            fruit_btn = QPushButton(fruit)
            fruit_btn.setStyleSheet("""
                QPushButton {
                    background-color: #FFF3E0;
                    border: 1px solid #FF9800;
                    border-radius: 8px;
                    padding: 10px 15px;
                }
            """)
            fruit_layout.addWidget(fruit_btn)

        fruit_layout.addStretch()
        layout.addWidget(fruit_group)

        layout.addStretch()
        return widget

    def create_minigames_tab(self) -> QWidget:
        """生态游戏标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # 介绍
        intro = QLabel("""
        <div style='font-size: 14px; color: #333; line-height: 1.8;'>
        <b>🎮 生态小游戏合集</b><br>
        参与各种生态主题的小游戏，获取积分奖励！<br>
        每个游戏都有最高分记录，挑战自我！
        </div>
        """)
        layout.addWidget(intro)

        # 游戏列表
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        games_layout = QVBoxLayout(container)
        games_layout.setSpacing(15)

        for game in self.game_system.mini_games:
            game_card = self.create_minigame_card(game)
            games_layout.addWidget(game_card)

        games_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll)

        return widget

    def create_minigame_card(self, game: Dict) -> QWidget:
        """创建游戏卡片"""
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
        icon_label = QLabel(game["icon"])
        icon_label.setFont(QFont("Segoe UI Emoji", 40))
        icon_label.setFixedWidth(80)
        layout.addWidget(icon_label)

        # 信息
        info_layout = QVBoxLayout()
        name_label = QLabel(game["name"])
        name_label.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        info_layout.addWidget(name_label)

        high_label = QLabel(f"最高分: {game['high_score']}")
        high_label.setFont(QFont("Microsoft YaHei", 10))
        high_label.setStyleSheet("color: #FF9800;")
        info_layout.addWidget(high_label)

        info_layout.addStretch()

        # 按钮
        play_btn = QPushButton("开始游戏")
        play_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 25px;
            }
        """)
        layout.addWidget(play_btn)

        return card

    def create_pet_tab(self) -> QWidget:
        """AI宠物标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # 介绍
        intro = QLabel("""
        <div style='font-size: 14px; color: #333; line-height: 1.8;'>
        <b>🐾 AI森林宠物</b><br>
        领养一只可爱的AI宠物！宠物会帮助您进行各种活动，<br>
        并随着时间成长进化。不同宠物有不同的特殊能力！
        </div>
        """)
        layout.addWidget(intro)

        # 宠物展示
        pet_group = QGroupBox("我的宠物")
        pet_layout = QHBoxLayout(pet_group)

        for pet in self.game_system.pets:
            pet_card = self.create_pet_card(pet)
            pet_layout.addWidget(pet_card)

        pet_layout.addStretch()
        layout.addWidget(pet_group)

        # 宠物类型
        type_group = QGroupBox("可领养的宠物")
        type_layout = QGridLayout(type_group)

        pet_types = [
            ("fire_spirit", "火精灵", "🔥", ["温暖", "照明"]),
            ("water_sprite", "水精灵", "💧", ["治愈", "净化"]),
            ("earth_gnome", "土精灵", "🪨", ["稳定", "力量"]),
            ("wind_fairy", "风精灵", "🌪️", ["速度", "敏捷"]),
            ("forest_elf", "森林精灵", "🌲", ["自然", "成长"]),
            ("moon_rabbit", "月兔", "🐰", ["智慧", "耐心"])
        ]

        for i, (type_id, type_name, type_icon, abilities) in enumerate(pet_types):
            type_card = self.create_pet_type_card(type_id, type_name, type_icon, abilities)
            type_layout.addWidget(type_card, i // 3, i % 3)

        layout.addWidget(type_group)

        layout.addStretch()
        return widget

    def create_pet_card(self, pet: Dict) -> QWidget:
        """创建宠物卡片"""
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #FFF8E1;
                border-radius: 12px;
                border: 2px solid #FF9800;
            }
        """)
        layout = QVBoxLayout(card)
        layout.setSpacing(10)

        icon = QLabel(pet["icon"])
        icon.setFont(QFont("Segoe UI Emoji", 48))
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon)

        name = QLabel(pet["name"])
        name.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(name)

        level = QLabel(f"Lv.{pet['level']}")
        level.setFont(QFont("Microsoft YaHei", 10))
        level.setStyleSheet("color: #FF9800;")
        level.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(level)

        return card

    def create_pet_type_card(self, type_id: str, type_name: str, type_icon: str, abilities: List[str]) -> QWidget:
        """创建宠物类型卡片"""
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 10px;
                border: 1px solid #e0e0e0;
            }
        """)
        layout = QVBoxLayout(card)
        layout.setSpacing(8)

        icon = QLabel(type_icon)
        icon.setFont(QFont("Segoe UI Emoji", 32))
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon)

        name = QLabel(type_name)
        name.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(name)

        abilities_label = QLabel(", ".join(abilities))
        abilities_label.setFont(QFont("Microsoft YaHei", 9))
        abilities_label.setStyleSheet("color: #888;")
        abilities_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(abilities_label)

        adopt_btn = QPushButton("领养")
        adopt_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 5px 15px;
            }
        """)
        layout.addWidget(adopt_btn)

        return card

    def create_ecology_tab(self) -> QWidget:
        """生态成就标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # 介绍
        intro = QLabel("""
        <div style='font-size: 14px; color: #333; line-height: 1.8;'>
        <b>🌍 生态成就链</b><br>
        完成各种生态相关的成就链，为保护环境贡献力量！<br>
        每个成就链都有多个阶段，完成后可获得丰厚奖励。
        </div>
        """)
        layout.addWidget(intro)

        # 成就链列表
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        chain_layout = QVBoxLayout(container)
        chain_layout.setSpacing(15)

        for chain in self.game_system.ecology_chains:
            chain_card = self.create_ecology_chain_card(chain)
            chain_layout.addWidget(chain_card)

        chain_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll)

        return widget

    def create_ecology_chain_card(self, chain: Dict) -> QWidget:
        """创建生态成就卡片"""
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
        header_layout = QHBoxLayout()

        icons = {"plant_tree": "🌳", "protect_wildlife": "🦉", "clean_environment": "🧹"}
        icon = QLabel(icons.get(chain["id"], "🌍"))
        icon.setFont(QFont("Segoe UI Emoji", 32))
        header_layout.addWidget(icon)

        name = QLabel(chain["name"])
        name.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        header_layout.addWidget(name, 1)

        if chain["completed"]:
            status = QLabel("✅ 已完成")
            status.setStyleSheet("color: #4CAF50; font-weight: bold;")
        else:
            status = QLabel("🔄 进行中")
            status.setStyleSheet("color: #FF9800;")
        header_layout.addWidget(status)

        layout.addLayout(header_layout)

        # 进度
        progress_layout = QHBoxLayout()
        progress_layout.addWidget(QLabel("进度:"))

        progress_bar = QProgressBar()
        progress_bar.setValue(chain["progress"])
        progress_bar.setFixedHeight(12)
        progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                background-color: #e0e0e0;
                border-radius: 6px;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 6px;
            }
        """)
        progress_layout.addWidget(progress_bar)

        percent_label = QLabel(f"{chain['progress']}%")
        percent_label.setFont(QFont("Microsoft YaHei", 10))
        percent_label.setStyleSheet("color: #4CAF50;")
        progress_layout.addWidget(percent_label)

        layout.addLayout(progress_layout)

        return card

    def create_credit_tab(self) -> QWidget:
        """积分系统标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # 积分概览
        balance = self.game_system.get_user_balance()
        balance_group = QGroupBox("💰 积分余额")
        balance_layout = QVBoxLayout(balance_group)

        balance_label = QLabel(f"{balance:,}")
        balance_label.setFont(QFont("Microsoft YaHei", 32, QFont.Weight.Bold))
        balance_label.setStyleSheet("color: #2E7D32;")
        balance_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        balance_layout.addWidget(balance_label)

        layout.addWidget(balance_group)

        # 每日上限
        limit_group = QGroupBox("每日积分上限")
        limit_layout = QVBoxLayout(limit_group)

        limits = [
            ("🌲 森林探险", 10000),
            ("🔢 数字猜谜", 5000),
            ("🌳 生命之树", 3000),
            ("🎮 生态游戏", 2500),
            ("🎉 季节活动", 4000),
        ]

        for name, limit in limits:
            limit_row = QHBoxLayout()
            limit_row.addWidget(QLabel(name))
            limit_row.addStretch()

            limit_bar = QProgressBar()
            limit_bar.setValue(random.randint(10, 80))
            limit_bar.setFixedWidth(200)
            limit_bar.setStyleSheet("""
                QProgressBar {
                    border: none;
                    background-color: #e0e0e0;
                    border-radius: 4px;
                }
                QProgressBar::chunk {
                    background-color: #4CAF50;
                }
            """)
            limit_row.addWidget(limit_bar)

            used_label = QLabel(f"{random.randint(100, limit)}/{limit}")
            used_label.setFont(QFont("Microsoft YaHei", 9))
            used_label.setStyleSheet("color: #888;")
            limit_row.addWidget(used_label)

            limit_layout.addLayout(limit_row)

        layout.addWidget(limit_group)

        # 积分功能
        feature_group = QGroupBox("积分功能")
        feature_layout = QHBoxLayout(feature_group)

        features = [
            ("⏰ 时间锁", "锁定积分获取利息"),
            ("🛡️ 保险", "保护您的积分"),
            ("📊 统计", "查看积分明细")
        ]

        for feat_name, feat_desc in features:
            feat_card = QFrame()
            feat_card.setStyleSheet("background-color: #f5f5f5; border-radius: 8px; padding: 10px;")
            feat_layout = QVBoxLayout(feat_card)
            feat_layout.setSpacing(5)

            feat_title = QLabel(feat_name)
            feat_title.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
            feat_layout.addWidget(feat_title)

            feat_desc_label = QLabel(feat_desc)
            feat_desc_label.setFont(QFont("Microsoft YaHei", 9))
            feat_desc_label.setStyleSheet("color: #666;")
            feat_layout.addWidget(feat_desc_label)

            feature_layout.addWidget(feat_card)

        layout.addWidget(feature_group)

        layout.addStretch()
        return widget

    def create_event_tab(self) -> QWidget:
        """季节庆典标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # 当前活动
        event = self.game_system.current_event
        event_group = QGroupBox(f"{event['icon']} {event['name']}")
        event_layout = QVBoxLayout(event_group)

        # 时间
        time_layout = QHBoxLayout()
        time_layout.addWidget(QLabel("剩余时间:"))
        time_left = QLabel(event["time_left"])
        time_left.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        time_left.setStyleSheet("color: #FF9800;")
        time_layout.addWidget(time_left)
        time_layout.addStretch()
        event_layout.addLayout(time_layout)

        # 进度
        progress_layout = QHBoxLayout()
        progress_layout.addWidget(QLabel("活动进度:"))

        progress_bar = QProgressBar()
        progress_bar.setValue(event["progress"])
        progress_bar.setFixedHeight(15)
        progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                background-color: #e0e0e0;
                border-radius: 8px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #FF69B4, stop:1 #FF1493);
                border-radius: 8px;
            }
        """)
        progress_layout.addWidget(progress_bar)

        event_layout.addLayout(progress_layout)

        # 统计
        stats_layout = QHBoxLayout()
        stats_layout.addWidget(QLabel(f"👥 参与人数: {event['participants']}"))
        stats_layout.addStretch()
        event_layout.addLayout(stats_layout)

        layout.addWidget(event_group)

        # 活动列表
        activity_group = QGroupBox("可参与的活动")
        activity_layout = QVBoxLayout(activity_group)

        activities = [
            ("🌸 种植花朵", "完成春日种植任务", 50),
            ("🦋 捕捉蝴蝶", "收集稀有蝴蝶", 30),
            ("💃 雨舞", "参与祈雨仪式", 40)
        ]

        for act_name, act_desc, act_reward in activities:
            act_row = QHBoxLayout()

            act_info = QVBoxLayout()
            act_title = QLabel(act_name)
            act_title.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
            act_info.addWidget(act_title)
            act_desc_label = QLabel(act_desc)
            act_desc_label.setFont(QFont("Microsoft YaHei", 9))
            act_desc_label.setStyleSheet("color: #888;")
            act_info.addWidget(act_desc_label)
            act_row.addLayout(act_info)

            reward_label = QLabel(f"+{act_reward}积分")
            reward_label.setFont(QFont("Microsoft YaHei", 10))
            reward_label.setStyleSheet("color: #4CAF50;")
            act_row.addWidget(reward_label)

            participate_btn = QPushButton("参与")
            participate_btn.setStyleSheet("""
                QPushButton {
                    background-color: #FF69B4;
                    color: white;
                    border: none;
                    border-radius: 6px;
                    padding: 8px 20px;
                }
            """)
            act_row.addWidget(participate_btn)

            activity_layout.addLayout(act_row)

        layout.addWidget(activity_group)

        # 季节装饰
        decor_group = QGroupBox("活动装饰")
        decor_layout = QHBoxLayout(decor_group)

        decorations = ["🌸", "🌷", "🦋", "🌻", "🌺", "🐝", "🌈", "✨"]
        for decor in decorations:
            label = QLabel(decor)
            label.setFont(QFont("Segoe UI Emoji", 20))
            decor_layout.addWidget(label)

        decor_layout.addStretch()
        layout.addWidget(decor_group)

        layout.addStretch()
        return widget

    def refresh_display(self):
        """刷新显示"""
        pass


# ==================== 导出 ====================

__all__ = ['LivingTreeGamePanel']
