# -*- coding: utf-8 -*-
"""
融合游戏系统 UI 面板
暗黑地牢 + 狼人杀 + 密室逃脱

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


class FusionGamePanel(QWidget):
    """融合游戏系统主面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.game_engine = None
        self.current_game = None
        self.current_player_id = None
        self.players = {}
        self.init_ui()
        self.setup_timers()

    def init_ui(self):
        """初始化UI"""
        main_layout = QVBoxLayout(self)

        # 标题栏
        title_layout = QHBoxLayout()
        title_label = QLabel("🎮 融合游戏：暗黑地牢 · 狼人杀 · 密室逃脱")
        title_label.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        title_layout.addWidget(title_label)
        title_layout.addStretch()

        self.status_label = QLabel("状态: 等待开始")
        self.status_label.setStyleSheet("color: #888;")
        title_layout.addWidget(self.status_label)

        main_layout.addLayout(title_layout)

        # 创建标签页
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        # 8个标签页
        self.tab_overview = OverviewTab(self)
        self.tab_dungeon = DungeonTab(self)
        self.tab_werewolf = WerewolfTab(self)
        self.tab_escape = EscapeTab(self)
        self.tab_fusion = FusionTab(self)
        self.tab_narrative = NarrativeTab(self)
        self.tab_progress = ProgressTab(self)
        self.tab_settings = SettingsTab(self)

        self.tabs.addTab(self.tab_overview, "🏠 总览")
        self.tabs.addTab(self.tab_dungeon, "🏰 地牢探险")
        self.tabs.addTab(self.tab_werewolf, "🐺 狼人杀")
        self.tabs.addTab(self.tab_escape, "🔐 密室逃脱")
        self.tabs.addTab(self.tab_fusion, "🎯 融合模式")
        self.tabs.addTab(self.tab_narrative, "🎭 AI导演")
        self.tabs.addTab(self.tab_progress, "📊 进度")
        self.tabs.addTab(self.tab_settings, "⚙️ 设置")

        main_layout.addWidget(self.tabs)

        self.setLayout(main_layout)

    def setup_timers(self):
        """设置定时器"""
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_game_state)
        self.update_timer.start(1000)

    def update_game_state(self):
        """更新游戏状态"""
        if self.current_game:
            phase = self.current_game.get("phase", "lobby")
            self.status_label.setText(f"状态: {phase}")
            self.tab_overview.refresh(self.current_game)
            self.tab_dungeon.refresh(self.current_game)
            self.tab_werewolf.refresh(self.current_game)
            self.tab_escape.refresh(self.current_game)

    def set_game_engine(self, engine):
        """设置游戏引擎"""
        self.game_engine = engine

    async def create_new_game(self, player_count: int = 6,
                            game_type: str = "fusion",
                            difficulty: int = 1):
        """创建新游戏"""
        if self.game_engine:
            self.current_game = await self.game_engine.create_new_game(
                player_count=player_count,
                game_type=game_type,
                difficulty=difficulty
            )
            self.current_player_id = f"player_{uuid.uuid4().hex[:8]}"
            self.status_label.setText("状态: 游戏中")
            return self.current_game
        return None

    def get_current_player(self):
        """获取当前玩家"""
        if self.current_game and self.current_player_id:
            return self.current_game.players.get(self.current_player_id)
        return None


class OverviewTab(QWidget):
    """总览标签页"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_panel = parent
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # 游戏概览卡片
        overview_group = QGroupBox("🎮 当前游戏概览")
        overview_layout = QGridLayout()

        self.game_id_label = QLabel("游戏ID: -")
        self.phase_label = QLabel("阶段: -")
        self.difficulty_label = QLabel("难度: -")
        self.players_count_label = QLabel("玩家数: -")
        self.time_label = QLabel("已用时间: -")

        overview_layout.addWidget(self.game_id_label, 0, 0)
        overview_layout.addWidget(self.phase_label, 0, 1)
        overview_layout.addWidget(self.difficulty_label, 1, 0)
        overview_layout.addWidget(self.players_count_label, 1, 1)
        overview_layout.addWidget(self.time_label, 2, 0)

        overview_group.setLayout(overview_layout)
        layout.addWidget(overview_group)

        # 快捷操作
        action_group = QGroupBox("⚡ 快捷操作")
        action_layout = QHBoxLayout()

        self.new_game_btn = QPushButton("🆕 新游戏")
        self.new_game_btn.clicked.connect(self.on_new_game)
        self.join_game_btn = QPushButton("🚪 加入游戏")
        self.continue_btn = QPushButton("▶️ 继续")
        self.pause_btn = QPushButton("⏸️ 暂停")

        action_layout.addWidget(self.new_game_btn)
        action_layout.addWidget(self.join_game_btn)
        action_layout.addWidget(self.continue_btn)
        action_layout.addWidget(self.pause_btn)

        action_group.setLayout(action_layout)
        layout.addWidget(action_group)

        # 游戏状态视图
        self.game_view = GameVisualizationView(self)
        layout.addWidget(self.game_view, 1)

        # 活动日志
        log_group = QGroupBox("📜 活动日志")
        log_layout = QVBoxLayout()
        self.log_list = QListWidget()
        log_layout.addWidget(self.log_list)
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)

        self.setLayout(layout)

    def refresh(self, game):
        """刷新显示"""
        if not game:
            return

        self.game_id_label.setText(f"游戏ID: {game.game_id}")
        self.phase_label.setText(f"阶段: {game.phase.value}")
        self.players_count_label.setText(f"玩家数: {len(game.players)}")

        if hasattr(game, 'dungeon') and game.dungeon:
            self.difficulty_label.setText(f"难度: {game.dungeon.difficulty:.1f}")

    def on_new_game(self):
        """创建新游戏"""
        dialog = NewGameDialog(self)
        if dialog.exec():
            count = dialog.get_player_count()
            difficulty = dialog.get_difficulty()
            asyncio.create_task(self.parent_panel.create_new_game(count, "fusion", difficulty))

    def add_log(self, message: str):
        """添加日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        item = QListWidgetItem(f"[{timestamp}] {message}")
        self.log_list.addItem(item)
        self.log_list.scrollToBottom()


class DungeonTab(QWidget):
    """地牢探险标签页"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_panel = parent
        self.current_dungeon = None
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QHBoxLayout(self)

        # 左侧：地牢地图
        left_panel = QFrame()
        left_layout = QVBoxLayout(left_panel)

        map_group = QGroupBox("🗺️ 地牢地图")
        map_layout = QVBoxLayout()
        self.dungeon_view = DungeonMapView(self)
        map_layout.addWidget(self.dungeon_view)
        map_group.setLayout(map_layout)
        left_layout.addWidget(map_group, 1)

        # 地牢信息
        info_group = QGroupBox("📍 当前层信息")
        info_layout = QGridLayout()
        self.depth_label = QLabel("深度: -")
        self.theme_label = QLabel("主题: -")
        self.monsters_label = QLabel("怪物: -")
        self.secrets_label = QLabel("秘密: -")
        info_layout.addWidget(self.depth_label, 0, 0)
        info_layout.addWidget(self.theme_label, 0, 1)
        info_layout.addWidget(self.monsters_label, 1, 0)
        info_layout.addWidget(self.secrets_label, 1, 1)
        info_group.setLayout(info_layout)
        left_layout.addWidget(info_group)

        layout.addWidget(left_panel, 1)

        # 右侧：房间详情
        right_panel = QFrame()
        right_layout = QVBoxLayout(right_panel)

        room_group = QGroupBox("🚪 房间详情")
        room_layout = QVBoxLayout()
        self.room_list = QListWidget()
        self.room_list.itemClicked.connect(self.on_room_clicked)
        room_layout.addWidget(self.room_list)
        room_group.setLayout(room_layout)
        right_layout.addWidget(room_group, 1)

        # 行动按钮
        action_group = QGroupBox("⚔️ 行动")
        action_layout = QHBoxLayout()
        self.explore_btn = QPushButton("🔍 探索")
        self.attack_btn = QPushButton("⚔️ 战斗")
        self.puzzle_btn = QPushButton("🧩 解谜")
        self.rest_btn = QPushButton("💤 休息")
        action_layout.addWidget(self.explore_btn)
        action_layout.addWidget(self.attack_btn)
        action_layout.addWidget(self.puzzle_btn)
        action_layout.addWidget(self.rest_btn)
        action_group.setLayout(action_layout)
        right_layout.addWidget(action_group)

        # 房间内容
        content_group = QGroupBox("📜 房间内容")
        content_layout = QVBoxLayout()
        self.room_content = QTextEdit()
        self.room_content.setReadOnly(True)
        content_layout.addWidget(self.room_content)
        content_group.setLayout(content_layout)
        right_layout.addWidget(content_group, 1)

        layout.addWidget(right_panel, 1)

        self.setLayout(layout)

    def refresh(self, game):
        """刷新显示"""
        if not game or not hasattr(game, 'dungeon') or not game.dungeon:
            return

        self.current_dungeon = game.dungeon
        dungeon = game.dungeon

        self.depth_label.setText(f"深度: {dungeon.depth}")
        self.theme_label.setText(f"主题: {dungeon.theme.value}")
        self.monsters_label.setText(f"怪物: {len(dungeon.monsters)}")
        self.secrets_label.setText(f"秘密: {len(dungeon.secrets)}")

        # 更新房间列表
        self.room_list.clear()
        for room in dungeon.rooms:
            self.room_list.addItem(f"{room.room_type.value} - {room.room_id}")

        self.dungeon_view.update_dungeon(dungeon)

    def on_room_clicked(self, item):
        """房间点击"""
        if self.current_dungeon:
            room_id = item.text().split(" - ")[-1]
            room = next((r for r in self.current_dungeon.rooms if r.room_id == room_id), None)
            if room:
                self.room_content.setText(f"""
房间类型: {room.room_type.value}
位置: ({room.position.x}, {room.position.y})
连接: {', '.join(room.connections) if room.connections else '无'}

故事背景:
{room.story}

环境效果:
{chr(10).join(room.environment_effects) if room.environment_effects else '无'}

{'🔒 宝箱' if room.contents.get('chest') else ''}
{'🧩 谜题' if room.contents.get('puzzle') else ''}
                """)


class WerewolfTab(QWidget):
    """狼人杀标签页"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_panel = parent
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QHBoxLayout(self)

        # 左侧：角色面板
        left_panel = QFrame()
        left_layout = QVBoxLayout(left_panel)

        role_group = QGroupBox("🎭 你的角色")
        role_layout = QVBoxLayout()
        self.role_label = QLabel("角色: -")
        self.team_label = QLabel("阵营: -")
        self.status_label = QLabel("状态: 存活")
        role_layout.addWidget(self.role_label)
        role_layout.addWidget(self.team_label)
        role_layout.addWidget(self.status_label)
        role_group.setLayout(role_layout)
        left_layout.addWidget(role_group)

        # 玩家列表
        players_group = QGroupBox("👥 玩家")
        players_layout = QVBoxLayout()
        self.players_tree = QTreeWidget()
        self.players_tree.setHeaderLabels(["玩家", "状态", "怀疑度"])
        players_layout.addWidget(self.players_tree)
        players_group.setLayout(players_layout)
        left_layout.addWidget(players_group, 1)

        layout.addWidget(left_panel, 1)

        # 中间：聊天/投票
        center_panel = QFrame()
        center_layout = QVBoxLayout(center_panel)

        chat_group = QGroupBox("💬 讨论")
        chat_layout = QVBoxLayout()
        self.chat_area = QTextEdit()
        self.chat_area.setReadOnly(True)
        chat_layout.addWidget(self.chat_area)

        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("输入发言...")
        self.send_btn = QPushButton("发送")
        self.send_btn.clicked.connect(self.on_send_message)

        chat_input_layout = QHBoxLayout()
        chat_input_layout.addWidget(self.chat_input)
        chat_input_layout.addWidget(self.send_btn)
        chat_layout.addLayout(chat_input_layout)
        chat_group.setLayout(chat_layout)
        center_layout.addWidget(chat_group, 1)

        # 投票
        vote_group = QGroupBox("🗳️ 投票")
        vote_layout = QVBoxLayout()
        self.vote_combo = QComboBox()
        self.vote_btn = QPushButton("投票")
        vote_layout.addWidget(self.vote_combo)
        vote_layout.addWidget(self.vote_btn)
        vote_group.setLayout(vote_layout)
        center_layout.addWidget(vote_group)

        layout.addWidget(center_panel, 1)

        # 右侧：游戏控制
        right_panel = QFrame()
        right_layout = QVBoxLayout(right_panel)

        controls_group = QGroupBox("🎮 游戏控制")
        controls_layout = QVBoxLayout()

        self.night_btn = QPushButton("🌙 进入夜晚")
        self.day_btn = QPushButton("☀️ 进入白天")
        self.ability_btn = QPushButton("✨ 使用能力")

        controls_layout.addWidget(self.night_btn)
        controls_layout.addWidget(self.day_btn)
        controls_layout.addWidget(self.ability_btn)
        controls_group.setLayout(controls_layout)
        right_layout.addWidget(controls_group)

        # 夜间行动
        night_actions_group = QGroupBox("🌙 夜间行动")
        night_layout = QFormLayout()
        self.target_combo = QComboBox()
        self.action_combo = QComboBox()
        self.action_combo.addItems(["击杀", "查验", "保护", "治疗"])
        night_layout.addRow("目标:", self.target_combo)
        night_layout.addRow("行动:", self.action_combo)
        night_actions_group.setLayout(night_layout)
        right_layout.addWidget(night_actions_group)

        # 游戏日志
        log_group = QGroupBox("📜 事件日志")
        log_layout = QVBoxLayout()
        self.event_log = QListWidget()
        log_layout.addWidget(self.event_log)
        log_group.setLayout(log_layout)
        right_layout.addWidget(log_group, 1)

        layout.addWidget(right_panel, 1)

        self.setLayout(layout)

    def refresh(self, game):
        """刷新显示"""
        if not game or not hasattr(game, 'werewolf') or not game.werewolf:
            return

        ww_game = game.werewolf

        # 更新玩家列表
        self.players_tree.clear()
        for player_id, player in ww_game.players.items():
            item = QTreeWidgetItem([
                f"{player.name} ({player.role})",
                "存活" if player.alive else "死亡",
                "低"
            ])
            self.players_tree.addTopLevelItem(item)

        # 更新投票目标
        self.vote_combo.clear()
        for player_id, player in ww_game.players.items():
            if player.alive:
                self.vote_combo.addItem(player.name, player_id)

        # 更新目标选择
        self.target_combo.clear()
        for player_id, player in ww_game.players.items():
            if player.alive:
                self.target_combo.addItem(player.name, player_id)

    def on_send_message(self):
        """发送消息"""
        text = self.chat_input.text()
        if text:
            self.chat_area.append(f"<b>你:</b> {text}")
            self.chat_input.clear()


class EscapeTab(QWidget):
    """密室逃脱标签页"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_panel = parent
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QHBoxLayout(self)

        # 左侧：密室视图
        left_panel = QFrame()
        left_layout = QVBoxLayout(left_panel)

        escape_group = QGroupBox("🚪 逃脱房间")
        escape_layout = QVBoxLayout()
        self.escape_view = EscapeRoomView(self)
        escape_layout.addWidget(self.escape_view)
        escape_group.setLayout(escape_layout)
        left_layout.addWidget(escape_group, 1)

        # 进度
        progress_group = QGroupBox("⏱️ 时间")
        progress_layout = QVBoxLayout()
        self.time_remaining = QProgressBar()
        self.time_remaining.setMaximum(1800)
        self.time_remaining.setValue(1800)
        self.time_label = QLabel("30:00")
        progress_layout.addWidget(self.time_remaining)
        progress_layout.addWidget(self.time_label)
        progress_group.setLayout(progress_layout)
        left_layout.addWidget(progress_group)

        layout.addWidget(left_panel, 1)

        # 右侧：谜题列表
        right_panel = QFrame()
        right_layout = QVBoxLayout(right_panel)

        puzzles_group = QGroupBox("🧩 谜题")
        puzzles_layout = QVBoxLayout()
        self.puzzle_list = QListWidget()
        self.puzzle_list.itemClicked.connect(self.on_puzzle_clicked)
        puzzles_layout.addWidget(self.puzzle_list)
        puzzles_group.setLayout(puzzles_layout)
        right_layout.addWidget(puzzles_group, 1)

        # 当前谜题
        current_group = QGroupBox("📝 当前谜题")
        current_layout = QVBoxLayout()
        self.puzzle_description = QTextEdit()
        self.puzzle_description.setReadOnly(True)
        current_layout.addWidget(self.puzzle_description)

        self.solution_input = QLineEdit()
        self.solution_input.setPlaceholderText("输入答案...")
        self.submit_btn = QPushButton("提交答案")
        self.submit_btn.clicked.connect(self.on_submit_solution)
        self.hint_btn = QPushButton("💡 提示")
        self.hint_btn.clicked.connect(self.on_get_hint)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.submit_btn)
        btn_layout.addWidget(self.hint_btn)
        current_layout.addWidget(self.solution_input)
        current_layout.addLayout(btn_layout)
        current_group.setLayout(current_layout)
        right_layout.addWidget(current_group)

        # 线索
        clues_group = QGroupBox("🔍 已发现线索")
        clues_layout = QVBoxLayout()
        self.clues_list = QListWidget()
        clues_layout.addWidget(self.clues_list)
        clues_group.setLayout(clues_layout)
        right_layout.addWidget(clues_group, 1)

        layout.addWidget(right_panel, 1)

        self.setLayout(layout)

    def refresh(self, game):
        """刷新显示"""
        if not game or not hasattr(game, 'escape_room') or not game.escape_room:
            return

        escape = game.escape_room

        # 更新谜题列表
        self.puzzle_list.clear()
        for puzzle in escape.puzzles:
            status = "✓" if puzzle.solved else "○"
            self.puzzle_list.addItem(f"{status} {puzzle.puzzle_type.value} (难度: {puzzle.difficulty:.1f})")

    def on_puzzle_clicked(self, item):
        """点击谜题"""
        pass

    def on_submit_solution(self):
        """提交答案"""
        pass

    def on_get_hint(self):
        """获取提示"""
        pass


class FusionTab(QWidget):
    """融合模式标签页"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_panel = parent
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # 模式选择
        mode_group = QGroupBox("🎯 游戏模式")
        mode_layout = QHBoxLayout()

        self.mode_combo = QComboBox()
        self.mode_combo.addItems([
            "🎮 纯地牢探险",
            "🐺 纯狼人杀",
            "🔐 纯密室逃脱",
            "🎭 地牢+狼人杀",
            "🏰 地牢+密室",
            "🎯 三合一融合"
        ])

        self.start_fusion_btn = QPushButton("🚀 开始融合游戏")
        mode_layout.addWidget(QLabel("选择模式:"))
        mode_layout.addWidget(self.mode_combo)
        mode_layout.addWidget(self.start_fusion_btn)
        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)

        # 融合游戏视图
        self.fusion_view = FusionGameView(self)
        layout.addWidget(self.fusion_view, 1)

        # 胜利条件
        victory_group = QGroupBox("🏆 胜利条件")
        victory_layout = QGridLayout()
        victory_layout.addWidget(QLabel("地牢模式:"), 0, 0)
        victory_layout.addWidget(QLabel("击败Boss"), 0, 1)
        victory_layout.addWidget(QLabel("狼人杀:"), 1, 0)
        victory_layout.addWidget(QLabel("消灭对立阵营"), 1, 1)
        victory_layout.addWidget(QLabel("密室逃脱:"), 2, 0)
        victory_layout.addWidget(QLabel("时限内解谜逃脱"), 2, 1)
        victory_layout.addWidget(QLabel("融合胜利:"), 3, 0)
        victory_layout.addWidget(QLabel("完成任意两种模式"), 3, 1)
        victory_group.setLayout(victory_layout)
        layout.addWidget(victory_group)

        self.setLayout(layout)


class NarrativeTab(QWidget):
    """AI导演标签页"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_panel = parent
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # 叙事概览
        narrative_group = QGroupBox("🎭 当前叙事弧")
        narrative_layout = QGridLayout()
        self.current_arc_label = QLabel("当前弧: -")
        self.dramatic_tension_label = QLabel("戏剧张力: -")
        self.next_event_label = QLabel("下一事件: -")
        narrative_layout.addWidget(QLabel("当前弧:"), 0, 0)
        narrative_layout.addWidget(self.current_arc_label, 0, 1)
        narrative_layout.addWidget(QLabel("戏剧张力:"), 1, 0)
        narrative_layout.addWidget(self.dramatic_tension_label, 1, 1)
        narrative_layout.addWidget(QLabel("下一事件:"), 2, 0)
        narrative_layout.addWidget(self.next_event_label, 2, 1)
        narrative_group.setLayout(narrative_layout)
        layout.addWidget(narrative_group)

        # AI叙事日志
        story_log_group = QGroupBox("📖 叙事日志")
        story_log_layout = QVBoxLayout()
        self.story_log = QTextEdit()
        self.story_log.setReadOnly(True)
        story_log_layout.addWidget(self.story_log)
        story_log_group.setLayout(story_log_layout)
        layout.addWidget(story_log_group, 1)

        # 叙事控制
        control_group = QGroupBox("🎬 叙事控制")
        control_layout = QHBoxLayout()
        self.force_event_btn = QPushButton("🎯 触发事件")
        self.adjust_tension_slider = QSlider(Qt.Orientation.Horizontal)
        self.adjust_tension_slider.setMinimum(0)
        self.adjust_tension_slider.setMaximum(100)
        self.adjust_tension_slider.setValue(50)
        control_layout.addWidget(QLabel("戏剧张力:"))
        control_layout.addWidget(self.adjust_tension_slider)
        control_layout.addWidget(self.force_event_btn)
        control_group.setLayout(control_layout)
        layout.addWidget(control_group)

        self.setLayout(layout)


class ProgressTab(QWidget):
    """进度标签页"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_panel = parent
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # 综合等级
        level_group = QGroupBox("⭐ 综合等级")
        level_layout = QHBoxLayout()
        self.level_label = QLabel("等级: 1")
        self.title_label = QLabel("称号: 新手冒险者")
        self.exp_progress = QProgressBar()
        self.exp_progress.setMaximum(1000)
        self.exp_progress.setValue(0)
        level_layout.addWidget(self.level_label)
        level_layout.addWidget(self.title_label)
        level_layout.addWidget(self.exp_progress)
        level_group.setLayout(level_layout)
        layout.addWidget(level_group)

        # 三游戏进度
        progress_tabs = QTabWidget()

        # 地牢进度
        dungeon_progress = QWidget()
        dp_layout = QVBoxLayout(dungeon_progress)
        dp_group = QGroupBox("🏰 地牢探险")
        dp_grid = QGridLayout()
        dp_grid.addWidget(QLabel("最深到达:"), 0, 0)
        dp_grid.addWidget(QLabel("-"), 0, 1)
        dp_grid.addWidget(QLabel("击败Boss:"), 1, 0)
        dp_grid.addWidget(QLabel("0"), 1, 1)
        dp_grid.addWidget(QLabel("收集物品:"), 2, 0)
        dp_grid.addWidget(QLabel("0"), 2, 1)
        dp_group.setLayout(dp_grid)
        dp_layout.addWidget(dp_group)
        progress_tabs.addTab(dungeon_progress, "🏰 地牢")

        # 狼人杀进度
        werewolf_progress = QWidget()
        wp_layout = QVBoxLayout(werewolf_progress)
        wp_group = QGroupBox("🐺 狼人杀")
        wp_grid = QGridLayout()
        wp_grid.addWidget(QLabel("胜率:"), 0, 0)
        wp_grid.addWidget(QLabel("0%"), 0, 1)
        wp_grid.addWidget(QLabel("最佳角色:"), 1, 0)
        wp_grid.addWidget(QLabel("-"), 1, 1)
        wp_grid.addWidget(QLabel("推理准确:"), 2, 0)
        wp_grid.addWidget(QLabel("0%"), 2, 1)
        wp_group.setLayout(wp_grid)
        wp_layout.addWidget(wp_group)
        progress_tabs.addTab(werewolf_progress, "🐺 狼人杀")

        # 密室进度
        escape_progress = QWidget()
        ep_layout = QVBoxLayout(escape_progress)
        ep_group = QGroupBox("🔐 密室逃脱")
        ep_grid = QGridLayout()
        ep_grid.addWidget(QLabel("逃脱次数:"), 0, 0)
        ep_grid.addWidget(QLabel("0"), 0, 1)
        ep_grid.addWidget(QLabel("平均时间:"), 1, 0)
        ep_grid.addWidget(QLabel("-"), 1, 1)
        ep_grid.addWidget(QLabel("谜题成功率:"), 2, 0)
        ep_grid.addWidget(QLabel("0%"), 2, 1)
        ep_group.setLayout(ep_grid)
        ep_layout.addWidget(ep_group)
        progress_tabs.addTab(escape_progress, "🔐 密室")

        layout.addWidget(progress_tabs, 1)

        # 跨游戏成就
        achievement_group = QGroupBox("🏆 跨游戏成就")
        achievement_layout = QVBoxLayout()
        self.achievement_list = QListWidget()
        achievement_layout.addWidget(self.achievement_list)
        achievement_group.setLayout(achievement_layout)
        layout.addWidget(achievement_group, 1)

        self.setLayout(layout)


class SettingsTab(QWidget):
    """设置标签页"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_panel = parent
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # 游戏设置
        settings_group = QGroupBox("⚙️ 游戏设置")
        settings_layout = QFormLayout()

        self.player_name = QLineEdit("冒险者")
        self.difficulty_slider = QSlider(Qt.Orientation.Horizontal)
        self.difficulty_slider.setMinimum(1)
        self.difficulty_slider.setMaximum(10)
        self.difficulty_slider.setValue(3)
        self.sound_check = QCheckBox("启用音效")
        self.sound_check.setChecked(True)
        self.music_check = QCheckBox("启用背景音乐")
        self.music_check.setChecked(True)
        self.narrative_check = QCheckBox("启用AI叙事")
        self.narrative_check.setChecked(True)
        self.auto_save_check = QCheckBox("自动保存")
        self.auto_save_check.setChecked(True)

        settings_layout.addRow("玩家名称:", self.player_name)
        settings_layout.addRow("默认难度:", self.difficulty_slider)
        settings_layout.addRow("", self.sound_check)
        settings_layout.addRow("", self.music_check)
        settings_layout.addRow("", self.narrative_check)
        settings_layout.addRow("", self.auto_save_check)

        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)

        # 快捷键设置
        hotkey_group = QGroupBox("⌨️ 快捷键")
        hotkey_layout = QFormLayout()
        hotkey_layout.addRow("探索:", QLabel("E"))
        hotkey_layout.addRow("攻击:", QLabel("A"))
        hotkey_layout.addRow("使用道具:", QLabel("I"))
        hotkey_layout.addRow("暂停:", QLabel("Esc"))
        hotkey_group.setLayout(hotkey_layout)
        layout.addWidget(hotkey_group)

        layout.addStretch()

        # 保存按钮
        self.save_btn = QPushButton("💾 保存设置")
        layout.addWidget(self.save_btn)

        self.setLayout(layout)


# ==================== 可视化视图 ====================

class GameVisualizationView(QGraphicsView):
    """游戏可视化视图"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def resizeEvent(self, event):
        """调整大小"""
        super().resizeEvent(event)
        self.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)


class DungeonMapView(QGraphicsView):
    """地牢地图视图"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.dungeon = None
        self.room_items = {}

    def update_dungeon(self, dungeon):
        """更新地牢显示"""
        self.dungeon = dungeon
        self.scene.clear()
        self.room_items.clear()

        if not dungeon:
            return

        # 绘制房间
        for room in dungeon.rooms:
            x = room.position.x * 80
            y = room.position.y * 60

            # 房间颜色
            colors = {
                "combat": QColor("#8B0000"),
                "treasure": QColor("#FFD700"),
                "puzzle": QColor("#4169E1"),
                "rest": QColor("#228B22"),
                "event": QColor("#9932CC"),
                "trap": QColor("#FF4500"),
                "boss": QColor("#DC143C")
            }

            color = colors.get(room.room_type.value, QColor("#808080"))

            rect = QGraphicsRectItem(x, y, 60, 40)
            rect.setBrush(QBrush(color))
            rect.setPen(QPen(Qt.GlobalColor.white, 2))
            self.scene.addItem(rect)

            text = QGraphicsTextItem(room.room_id)
            text.setPos(x + 5, y + 10)
            text.setDefaultTextColor(Qt.GlobalColor.white)
            self.scene.addItem(text)

            self.room_items[room.room_id] = rect

        # 绘制连接
        for room in dungeon.rooms:
            for conn_id in room.connections:
                conn_room = next((r for r in dungeon.rooms if r.room_id == conn_id), None)
                if conn_room:
                    line = QGraphicsLineItem(
                        room.position.x * 80 + 30,
                        room.position.y * 60 + 20,
                        conn_room.position.x * 80 + 30,
                        conn_room.position.y * 60 + 20
                    )
                    line.setPen(QPen(QColor("#404040"), 2))
                    self.scene.addItem(line)

        self.setSceneRect(-50, -50, 800, 600)


class EscapeRoomView(QGraphicsView):
    """密室逃脱视图"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)

    def update_room(self, escape_room):
        """更新房间显示"""
        self.scene.clear()

        # 绘制密室布局
        base_rect = QGraphicsRectItem(0, 0, 400, 300)
        base_rect.setBrush(QBrush(QColor("#2F2F2F")))
        base_rect.setPen(QPen(Qt.GlobalColor.white, 2))
        self.scene.addItem(base_rect)

        # 添加交互点
        objects = escape_room.get("interactive_objects", [])
        for i, obj in enumerate(objects):
            x = 50 + (i % 3) * 120
            y = 50 + (i // 3) * 100

            circle = QGraphicsEllipseItem(x, y, 40, 40)
            circle.setBrush(QBrush(QColor("#4A90D9")))
            circle.setPen(QPen(Qt.GlobalColor.white, 2))
            self.scene.addItem(circle)

        self.setSceneRect(-20, -20, 440, 340)


class FusionGameView(QGraphicsView):
    """融合游戏视图"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)

    def update_game_state(self, game):
        """更新游戏状态"""
        self.scene.clear()

        if not game:
            return

        # 绘制中心节点
        center = QGraphicsEllipseItem(175, 135, 50, 50)
        center.setBrush(QBrush(QColor("#9B59B6")))
        center.setPen(QPen(Qt.GlobalColor.white, 2))
        self.scene.addItem(center)

        # 绘制三个模式
        modes = [
            ("🏰 地牢", 175, 50),
            ("🐺 狼人杀", 100, 200),
            ("🔐 密室", 250, 200)
        ]

        for name, x, y in modes:
            ellipse = QGraphicsEllipseItem(x, y, 50, 50)
            ellipse.setBrush(QBrush(QColor("#3498DB")))
            ellipse.setPen(QPen(Qt.GlobalColor.white, 2))
            self.scene.addItem(ellipse)

            text = QGraphicsTextItem(name)
            text.setPos(x + 5, y + 15)
            text.setDefaultTextColor(Qt.GlobalColor.white)
            self.scene.addItem(text)

        self.setSceneRect(-20, -20, 400, 300)


# ==================== 对话框 ====================

class NewGameDialog(QDialog):
    """新建游戏对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🆕 新建融合游戏")
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QFormLayout(self)

        self.player_count = QSpinBox()
        self.player_count.setMinimum(3)
        self.player_count.setMaximum(12)
        self.player_count.setValue(6)

        self.difficulty = QSlider(Qt.Orientation.Horizontal)
        self.difficulty.setMinimum(1)
        self.difficulty.setMaximum(10)
        self.difficulty.setValue(3)

        self.game_type = QComboBox()
        self.game_type.addItems([
            "🎭 三合一融合模式",
            "🏰 地牢探险模式",
            "🐺 狼人杀模式",
            "🔐 密室逃脱模式"
        ])

        layout.addRow("玩家数量:", self.player_count)
        layout.addRow("难度:", self.difficulty)
        layout.addRow("游戏类型:", self.game_type)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

        self.setLayout(layout)

    def get_player_count(self):
        """获取玩家数量"""
        return self.player_count.value()

    def get_difficulty(self):
        """获取难度"""
        return self.difficulty.value()


class PlayerCardDialog(QDialog):
    """玩家卡片对话框"""

    def __init__(self, player_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🎭 玩家详情")
        self.player_data = player_data
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        info = QTextEdit()
        info.setReadOnly(True)
        info.setHtml(f"""
        <h2>{self.player_data.get('name', '未知')}</h2>
        <p>等级: {self.player_data.get('level', 1)}</p>
        <p>职业: {self.player_data.get('role', '-')}</p>
        <p>状态: {'存活' if self.player_data.get('alive', True) else '死亡'}</p>
        """)
        layout.addWidget(info)

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

        self.setLayout(layout)


# ==================== 导出 ====================

__all__ = ['FusionGamePanel', 'NewGameDialog']
