# -*- coding: utf-8 -*-
"""
斗地主游戏 UI 面板
Dou Di Zhu Game UI Panel

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
    QDialog, QDialogButtonBox, QFormLayout, QTextBrowser,
    QTreeWidget, QTreeWidgetItem
)
from PyQt6.QtCore import (
    Qt, QTimer, pyqtSignal, QSize,
    QRectF, QPointF, QPropertyAnimation, QEasingCurve
)
from PyQt6.QtGui import (
    QColor, QBrush, QPen, QFont, QPainter,
    QIcon, QAction, QPixmap, QTransform
)


class DouDiZhuPanel(QWidget):
    """斗地主游戏主面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.dou_dizhu_engine = None
        self.current_player_id = f"player_{uuid.uuid4().hex[:8]}"
        self.selected_cards = set()
        self.init_ui()
        self.setup_timers()

    def init_ui(self):
        """初始化UI"""
        main_layout = QVBoxLayout(self)

        # 标题栏
        title_layout = QHBoxLayout()
        title_label = QLabel("🃏 斗地主 - 经典三人对战")
        title_label.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        title_layout.addWidget(title_label)
        title_layout.addStretch()

        self.status_label = QLabel("状态: 等待开始")
        self.status_label.setStyleSheet("color: #4CAF50;")
        title_layout.addWidget(self.status_label)

        main_layout.addLayout(title_layout)

        # 创建标签页
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        # 4个标签页
        self.tab_game = GameTab(self)
        self.tab_room = RoomTab(self)
        self.tab_stats = StatsTab(self)
        self.tab_settings = SettingsTab(self)

        self.tabs.addTab(self.tab_game, "🎮 对局")
        self.tabs.addTab(self.tab_room, "🚪 房间")
        self.tabs.addTab(self.tab_stats, "📊 战绩")
        self.tabs.addTab(self.tab_settings, "⚙️ 设置")

        main_layout.addWidget(self.tabs)

        self.setLayout(main_layout)

    def setup_timers(self):
        """设置定时器"""
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_game_state)
        self.update_timer.start(500)  # 500ms更新

    def update_game_state(self):
        """更新游戏状态"""
        if self.dou_dizhu_engine and self.dou_dizhu_engine.game_state:
            state = self.dou_dizhu_engine.get_game_state()
            if state:
                self.tab_game.refresh(state)

    def set_engine(self, engine):
        """设置游戏引擎"""
        self.dou_dizhu_engine = engine

    async def quick_start(self):
        """快速开始"""
        if self.dou_dizhu_engine:
            # 创建房间
            room = self.dou_dizhu_engine.create_room(
                self.current_player_id,
                "玩家",
                {"ai_enabled": True}
            )

            # 添加AI玩家
            self.dou_dizhu_engine.join_room(
                room.room_id,
                "ai_1",
                "AI-张三",
                is_ai=True,
                difficulty="medium"
            )
            self.dou_dizhu_engine.join_room(
                room.room_id,
                "ai_2",
                "AI-李四",
                is_ai=True,
                difficulty="medium"
            )

            # 设置准备
            self.dou_dizhu_engine.set_ready(True)

            # 开始游戏
            self.dou_dizhu_engine.start_game()

            self.status_label.setText("状态: 游戏中")
            self.tabs.setCurrentIndex(0)


class GameTab(QWidget):
    """对局标签页"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_panel = parent
        self.game_state = None
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # 顶部信息栏
        top_layout = QHBoxLayout()

        # 房间信息
        info_group = QGroupBox("📋 对局信息")
        info_layout = QGridLayout()
        self.room_id_label = QLabel("房间: -")
        self.multiple_label = QLabel("倍数: 1x")
        self.round_label = QLabel("回合: 0")
        info_layout.addWidget(self.room_id_label, 0, 0)
        info_layout.addWidget(self.multiple_label, 0, 1)
        info_layout.addWidget(self.round_label, 1, 0)
        info_group.setLayout(info_layout)
        top_layout.addWidget(info_group)

        # 炸弹/春天显示
        special_group = QGroupBox("💥 特殊事件")
        special_layout = QHBoxLayout()
        self.bomb_count_label = QLabel("炸弹: 0")
        self.spring_label = QLabel("")
        self.spring_label.setStyleSheet("color: #FF6B6B; font-weight: bold;")
        special_layout.addWidget(self.bomb_count_label)
        special_layout.addWidget(self.spring_label)
        special_group.setLayout(special_layout)
        top_layout.addWidget(special_group)

        # 计时器
        timer_group = QGroupBox("⏱️ 思考时间")
        timer_layout = QVBoxLayout()
        self.turn_timer = QProgressBar()
        self.turn_timer.setMaximum(30)
        self.turn_timer.setValue(30)
        timer_layout.addWidget(self.turn_timer)
        timer_group.setLayout(timer_layout)
        top_layout.addWidget(timer_group)

        layout.addLayout(top_layout)

        # 中央游戏区域
        center_layout = QHBoxLayout()

        # 上家区域
        top_opponent = self.create_opponent_widget("上家")
        center_layout.addWidget(top_opponent, 1)

        # 中间区域
        middle_layout = QVBoxLayout()

        # 上家出牌区
        self.top_play_area = self.create_play_area("上家")
        middle_layout.addWidget(self.top_play_area)

        # 牌桌（底牌+特效）
        table_group = QGroupBox("🎴 底牌")
        table_layout = QHBoxLayout()
        self.bottom_cards_label = QLabel("等待发牌...")
        self.bottom_cards_label.setFont(QFont("Microsoft YaHei", 12))
        self.bottom_cards_label.setAlignment(Qt.AlignCenter)
        table_layout.addWidget(self.bottom_cards_label)
        table_group.setLayout(table_layout)
        middle_layout.addWidget(table_group)

        # 下家出牌区
        self.bottom_play_area = self.create_play_area("下家")
        middle_layout.addWidget(self.bottom_play_area)

        center_layout.addLayout(middle_layout, 2)

        # 下家区域
        bottom_opponent = self.create_opponent_widget("下家")
        center_layout.addWidget(bottom_opponent, 1)

        layout.addLayout(center_layout, 1)

        # 自己手牌区域
        hand_group = QGroupBox("🃏 我的手牌")
        hand_layout = QVBoxLayout()

        # 手牌显示
        self.hand_cards_layout = QHBoxLayout()
        self.hand_cards_layout.addStretch()
        hand_layout.addLayout(self.hand_cards_layout)

        # 操作按钮
        action_layout = QHBoxLayout()

        self.play_btn = QPushButton("出牌")
        self.play_btn.setEnabled(False)
        self.play_btn.clicked.connect(self.on_play_clicked)
        self.pass_btn = QPushButton("过")
        self.pass_btn.setEnabled(False)
        self.pass_btn.clicked.connect(self.on_pass_clicked)
        self.hint_btn = QPushButton("提示")
        self.hint_btn.clicked.connect(self.on_hint_clicked)

        action_layout.addStretch()
        action_layout.addWidget(self.hint_btn)
        action_layout.addWidget(self.pass_btn)
        action_layout.addWidget(self.play_btn)
        hand_layout.addLayout(action_layout)

        hand_group.setLayout(hand_layout)
        layout.addWidget(hand_group)

        self.setLayout(layout)

    def create_opponent_widget(self, position: str) -> QWidget:
        """创建对手部件"""
        widget = QFrame()
        widget.setFixedSize(150, 180)
        widget.setStyleSheet("""
            QFrame {
                background-color: rgba(50, 50, 80, 150);
                border-radius: 10px;
                border: 2px solid #666;
            }
        """)

        layout = QVBoxLayout(widget)

        # 玩家名称
        name_label = QLabel(f"{position}: 等待中...")
        name_label.setAlignment(Qt.AlignCenter)
        name_label.setStyleSheet("color: white; font-weight: bold; font-size: 12px;")

        # 角色标识
        role_label = QLabel("")
        role_label.setAlignment(Qt.AlignCenter)
        role_label.setStyleSheet("color: #FFD700; font-weight: bold;")

        # 剩余牌数
        cards_label = QLabel("剩余: --张")
        cards_label.setAlignment(Qt.AlignCenter)
        cards_label.setStyleSheet("color: #4FC3F7; font-size: 20px;")

        # 出牌指示
        turn_label = QLabel("")
        turn_label.setAlignment(Qt.AlignCenter)
        turn_label.setStyleSheet("color: #FF5722; font-size: 24px; font-weight: bold;")

        layout.addWidget(name_label)
        layout.addWidget(role_label)
        layout.addWidget(cards_label)
        layout.addWidget(turn_label)

        if position == "上家":
            self.top_name = name_label
            self.top_role = role_label
            self.top_cards = cards_label
            self.top_turn = turn_label
        else:
            self.bottom_name = name_label
            self.bottom_role = role_label
            self.bottom_cards = cards_label
            self.bottom_turn = turn_label

        return widget

    def create_play_area(self, position: str) -> QWidget:
        """创建出牌区域"""
        area = QFrame()
        area.setFixedHeight(80)
        area.setStyleSheet("""
            QFrame {
                background-color: rgba(0, 0, 0, 50);
                border-radius: 10px;
                border: 1px dashed #666;
            }
        """)

        layout = QHBoxLayout(area)
        layout.setAlignment(Qt.AlignCenter)

        combo_label = QLabel("")
        combo_label.setStyleSheet("""
            QLabel {
                color: #FFD700;
                font-size: 16px;
                font-weight: bold;
            }
        """)

        layout.addWidget(combo_label)

        if position == "上家":
            self.top_combo = combo_label
        else:
            self.bottom_combo = combo_label

        return area

    def refresh(self, state: Dict):
        """刷新显示"""
        if not state:
            return

        self.game_state = state

        # 更新信息
        self.room_id_label.setText(f"房间: {state.get('room_id', '-')}")
        self.multiple_label.setText(f"倍数: {state.get('multiple', 1)}x")
        self.round_label.setText(f"回合: {state.get('round_count', 0)}")

        # 更新炸弹/春天
        self.bomb_count_label.setText(f"炸弹: {state.get('bomb_count', 0)}")
        if state.get('is_spring'):
            self.spring_label.setText("🌸 春天!")
        else:
            self.spring_label.setText("")

        # 更新底牌
        bottom_cards = state.get('bottom_cards', [])
        if bottom_cards:
            self.bottom_cards_label.setText(" ".join(bottom_cards))

        # 更新玩家信息
        players = state.get('players', {})
        my_cards = state.get('my_cards', [])

        # 找出上家和下家
        player_ids = list(players.keys())
        if self.parent_panel.current_player_id in player_ids:
            my_idx = player_ids.index(self.parent_panel.current_player_id)

            # 上家
            top_idx = (my_idx - 1) % 3
            top_id = player_ids[top_idx]
            top_player = players.get(top_id, {})
            self.top_name.setText(f"{top_player.get('name', '上家')}")
            self.top_cards.setText(f"剩余: {top_player.get('cards_count', 0)}张")
            self.top_role.setText("👑" if top_player.get('is_landlord') else "🧑‍🌾")
            self.top_turn.setText("▶️" if top_player.get('is_current_turn') else "")

            # 下家
            bottom_idx = (my_idx + 1) % 3
            bottom_id = player_ids[bottom_idx]
            bottom_player = players.get(bottom_id, {})
            self.bottom_name.setText(f"{bottom_player.get('name', '下家')}")
            self.bottom_cards.setText(f"剩余: {bottom_player.get('cards_count', 0)}张")
            self.bottom_role.setText("👑" if bottom_player.get('is_landlord') else "🧑‍🌾")
            self.bottom_turn.setText("▶️" if bottom_player.get('is_current_turn') else "")

        # 更新我的手牌
        self.update_my_cards(my_cards)

        # 更新按钮状态
        current_turn = state.get('current_turn')
        is_my_turn = current_turn == self.parent_panel.current_player_id
        self.play_btn.setEnabled(is_my_turn)
        self.pass_btn.setEnabled(is_my_turn)

        # 更新最后出牌
        last_combo = state.get('last_combo')
        if last_combo:
            combo_name = last_combo.get('type', '')
            self.bottom_combo.setText(combo_name)

    def update_my_cards(self, cards: List[str]):
        """更新手牌显示"""
        # 清除现有手牌
        while self.hand_cards_layout.count() > 1:
            item = self.hand_cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # 添加新手牌
        for i, card_text in enumerate(cards):
            card_widget = self.create_card_widget(card_text, i)
            self.hand_cards_layout.insertWidget(self.hand_cards_layout.count() - 1, card_widget)

    def create_card_widget(self, card_text: str, index: int) -> QWidget:
        """创建单张卡牌部件"""
        card_frame = QFrame()
        card_frame.setFixedSize(50, 70)
        card_frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 2px solid #333;
                border-radius: 5px;
            }
            QFrame:hover {
                border: 2px solid #FFD700;
            }
            QFrame[selected="true"] {
                border: 3px solid #4CAF50;
                background-color: #E8F5E9;
            }
        """)
        card_frame.setProperty("selected", False)

        layout = QVBoxLayout(card_frame)
        layout.setContentsMargins(2, 2, 2, 2)

        label = QLabel(card_text)
        label.setAlignment(Qt.AlignCenter)
        label.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))

        layout.addWidget(label)

        # 点击事件
        card_frame.mousePressEvent = lambda e, idx=index, f=card_frame: self.on_card_click(idx, f)

        return card_frame

    def on_card_click(self, index: int, card_frame: QFrame):
        """卡牌点击"""
        if index in self.selected_cards:
            self.selected_cards.remove(index)
            card_frame.setProperty("selected", False)
        else:
            self.selected_cards.add(index)
            card_frame.setProperty("selected", True)

        card_frame.style().unpolish(card_frame)
        card_frame.style().polish(card_frame)

    def on_play_clicked(self):
        """出牌按钮"""
        if self.parent_panel.dou_dizhu_engine and self.selected_cards:
            result = self.parent_panel.dou_dizhu_engine.play_cards(list(self.selected_cards))
            if result.get("success"):
                self.selected_cards.clear()
                self.refresh(result)

    def on_pass_clicked(self):
        """过牌按钮"""
        if self.parent_panel.dou_dizhu_engine:
            result = self.parent_panel.dou_dizhu_engine.pass_turn()
            if result.get("success"):
                self.refresh(self.parent_panel.dou_dizhu_engine.get_game_state())

    def on_hint_clicked(self):
        """提示按钮"""
        if self.parent_panel.dou_dizhu_engine:
            hint = self.parent_panel.dou_dizhu_engine.get_hint()
            self.selected_cards = set(hint)
            # 高亮提示的牌
            self.refresh(self.parent_panel.dou_dizhu_engine.get_game_state())


class RoomTab(QWidget):
    """房间标签页"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_panel = parent
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # 快速开始
        quick_group = QGroupBox("⚡ 快速开始")
        quick_layout = QHBoxLayout()

        self.quick_start_btn = QPushButton("🚀 快速匹配 (vs AI)")
        self.quick_start_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 15px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.quick_start_btn.clicked.connect(self.on_quick_start)

        quick_layout.addWidget(self.quick_start_btn)
        quick_group.setLayout(quick_layout)
        layout.addWidget(quick_group)

        # 创建房间
        create_group = QGroupBox("🚪 创建房间")
        create_layout = QGridLayout()

        create_layout.addWidget(QLabel("房间名:"), 0, 0)
        self.room_name_edit = QLineEdit()
        self.room_name_edit.setPlaceholderText("输入房间名...")
        create_layout.addWidget(self.room_name_edit, 0, 1)

        create_layout.addWidget(QLabel("难度:"), 1, 0)
        self.difficulty_combo = QComboBox()
        self.difficulty_combo.addItems(["简单", "中等", "困难", "专家"])
        create_layout.addWidget(self.difficulty_combo, 1, 1)

        self.create_room_btn = QPushButton("创建房间")
        self.create_room_btn.clicked.connect(self.on_create_room)
        create_layout.addWidget(self.create_room_btn, 2, 0, 1, 2)

        create_group.setLayout(create_layout)
        layout.addWidget(create_group)

        # 房间列表
        list_group = QGroupBox("📋 可用房间")
        list_layout = QVBoxLayout()

        self.room_list = QListWidget()
        self.room_list.itemDoubleClicked.connect(self.on_join_room)
        list_layout.addWidget(self.room_list)

        self.refresh_rooms_btn = QPushButton("刷新房间列表")
        self.refresh_rooms_btn.clicked.connect(self.refresh_room_list)
        list_layout.addWidget(self.refresh_rooms_btn)

        list_group.setLayout(list_layout)
        layout.addWidget(list_group, 1)

        self.setLayout(layout)

    def on_quick_start(self):
        """快速开始"""
        asyncio.create_task(self.parent_panel.quick_start())

    def on_create_room(self):
        """创建房间"""
        room_name = self.room_name_edit.text() or "我的房间"
        difficulty = self.difficulty_combo.currentText()

        if self.parent_panel.dou_dizhu_engine:
            config = {
                "ai_enabled": True,
                "difficulty": difficulty
            }
            room = self.parent_panel.dou_dizhu_engine.create_room(
                self.parent_panel.current_player_id,
                room_name,
                config
            )
            self.parent_panel.status_label.setText(f"房间已创建: {room.room_id}")

    def on_join_room(self, item):
        """加入房间"""
        room_id = item.data(Qt.ItemDataRole.UserRole)
        if room_id and self.parent_panel.dou_dizhu_engine:
            success = self.parent_panel.dou_dizhu_engine.join_room(
                room_id,
                self.parent_panel.current_player_id,
                "玩家"
            )
            if success:
                self.parent_panel.status_label.setText("已加入房间")

    def refresh_room_list(self):
        """刷新房间列表"""
        self.room_list.clear()

        if self.parent_panel.dou_dizhu_engine:
            rooms = self.parent_panel.dou_dizhu_engine.room_manager.get_available_rooms()
            for room in rooms:
                item = QListWidgetItem(f"{room['room_id']} - {len(room['players'])}/3人")
                item.setData(Qt.ItemDataRole.UserRole, room['room_id'])
                self.room_list.addItem(item)


class StatsTab(QWidget):
    """战绩标签页"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_panel = parent
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # 统计概览
        stats_group = QGroupBox("📊 我的战绩")
        stats_layout = QGridLayout()

        self.total_games_label = QLabel("总场次: 0")
        self.win_rate_label = QLabel("胜率: 0%")
        self.credits_label = QLabel("积分: 0")
        self.rank_label = QLabel("段位: 青铜")

        stats_layout.addWidget(self.total_games_label, 0, 0)
        stats_layout.addWidget(self.win_rate_label, 0, 1)
        stats_layout.addWidget(self.credits_label, 1, 0)
        stats_layout.addWidget(self.rank_label, 1, 1)

        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)

        # 成就
        achievement_group = QGroupBox("🏆 已解锁成就")
        achievement_layout = QVBoxLayout()

        self.achievement_list = QListWidget()
        achievement_layout.addWidget(self.achievement_list)
        achievement_group.setLayout(achievement_layout)
        layout.addWidget(achievement_group, 1)

        # 排行榜
        leaderboard_group = QGroupBox("📈 排行榜")
        leaderboard_layout = QVBoxLayout()

        self.leaderboard_table = QTableWidget()
        self.leaderboard_table.setColumnCount(3)
        self.leaderboard_table.setHorizontalHeaderLabels(["排名", "玩家", "积分"])
        leaderboard_layout.addWidget(self.leaderboard_table)
        leaderboard_group.setLayout(leaderboard_layout)
        layout.addWidget(leaderboard_group, 1)

        self.setLayout(layout)

    def refresh(self):
        """刷新数据"""
        if self.parent_panel.dou_dizhu_engine:
            player_info = self.parent_panel.dou_dizhu_engine.get_player_info(
                self.parent_panel.current_player_id
            )

            if player_info:
                stats = player_info.get("stats", {})
                total = stats.get("total_games", 0)
                wins = stats.get("wins", 0)
                win_rate = (wins / total * 100) if total > 0 else 0

                self.total_games_label.setText(f"总场次: {total}")
                self.win_rate_label.setText(f"胜率: {win_rate:.1f}%")
                self.credits_label.setText(f"积分: {player_info.get('credits', 0)}")

            # 刷新排行榜
            leaderboard = self.parent_panel.dou_dizhu_engine.get_leaderboard()
            self.leaderboard_table.setRowCount(len(leaderboard))
            for i, entry in enumerate(leaderboard):
                self.leaderboard_table.setItem(i, 0, QTableWidgetItem(str(entry["rank"])))
                self.leaderboard_table.setItem(i, 1, QTableWidgetItem(entry["player_id"][:8]))
                self.leaderboard_table.setItem(i, 2, QTableWidgetItem(str(entry["credits"])))


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

        # 游戏设置
        game_group = QGroupBox("🎮 游戏设置")
        game_layout = QFormLayout()

        self.sound_check = QCheckBox("启用音效")
        self.sound_check.setChecked(True)
        self.music_check = QCheckBox("启用背景音乐")
        self.music_check.setChecked(False)

        game_layout.addRow("音效:", self.sound_check)
        game_layout.addRow("音乐:", self.music_check)
        game_group.setLayout(game_layout)
        scroll_layout.addWidget(game_group)

        # AI设置
        ai_group = QGroupBox("🤖 AI设置")
        ai_layout = QFormLayout()

        self.ai_difficulty_combo = QComboBox()
        self.ai_difficulty_combo.addItems(["简单", "中等", "困难", "专家"])
        self.ai_difficulty_combo.setCurrentIndex(1)

        self.ai_think_time = QSpinBox()
        self.ai_think_time.setRange(1, 10)
        self.ai_think_time.setValue(3)
        self.ai_think_time.setSuffix(" 秒")

        ai_layout.addRow("AI难度:", self.ai_difficulty_combo)
        ai_layout.addRow("AI思考时间:", self.ai_think_time)
        ai_group.setLayout(ai_layout)
        scroll_layout.addWidget(ai_group)

        # 显示设置
        display_group = QGroupBox("🖥️ 显示设置")
        display_layout = QFormLayout()

        self.animation_check = QCheckBox("启用动画")
        self.animation_check.setChecked(True)
        self.effect_check = QCheckBox("启用特效")
        self.effect_check.setChecked(True)

        display_layout.addRow("动画:", self.animation_check)
        display_layout.addRow("特效:", self.effect_check)
        display_group.setLayout(display_layout)
        scroll_layout.addWidget(display_group)

        # 通知设置
        notify_group = QGroupBox("🔔 通知设置")
        notify_layout = QFormLayout()

        self.game_end_notify = QCheckBox("对局结束通知")
        self.game_end_notify.setChecked(True)
        self.achievement_notify = QCheckBox("成就解锁通知")
        self.achievement_notify.setChecked(True)

        notify_layout.addRow("对局结束:", self.game_end_notify)
        notify_layout.addRow("成就:", self.achievement_notify)
        notify_group.setLayout(notify_layout)
        scroll_layout.addWidget(notify_group)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll, 1)

        # 底部按钮
        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton("💾 保存设置")
        self.reset_btn = QPushButton("🔄 恢复默认")

        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.reset_btn)
        layout.addLayout(btn_layout)

        self.setLayout(layout)


class CardWidget(QWidget):
    """卡牌组件"""

    card_selected = pyqtSignal(int, bool)

    def __init__(self, card_text: str, index: int, parent=None):
        super().__init__(parent)
        self.card_text = card_text
        self.index = index
        self.is_selected = False
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        self.setFixedSize(50, 70)
        self.setStyleSheet("""
            QWidget {
                background-color: white;
                border: 2px solid #333;
                border-radius: 5px;
            }
            QWidget:hover {
                border: 2px solid #FFD700;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)

        self.label = QLabel(self.card_text)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        layout.addWidget(self.label)

    def mousePressEvent(self, event):
        """鼠标点击"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_selected = not self.is_selected
            self.update_style()
            self.card_selected.emit(self.index, self.is_selected)

    def update_style(self):
        """更新样式"""
        if self.is_selected:
            self.setStyleSheet("""
                QWidget {
                    background-color: #E8F5E9;
                    border: 3px solid #4CAF50;
                    border-radius: 5px;
                }
            """)
            # 向上移动
            self.move(self.x(), self.y() - 20)
        else:
            self.setStyleSheet("""
                QWidget {
                    background-color: white;
                    border: 2px solid #333;
                    border-radius: 5px;
                }
                QWidget:hover {
                    border: 2px solid #FFD700;
                }
            """)
            # 向下移动
            self.move(self.x(), self.y() + 20)


# ==================== 便捷函数 ====================

def create_dou_di_zhu_panel(parent=None) -> DouDiZhuPanel:
    """创建斗地主面板"""
    panel = DouDiZhuPanel(parent)
    return panel
