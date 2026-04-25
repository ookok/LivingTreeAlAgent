#!/usr/bin/env python3
"""
游戏面板 - GameHubPanel
Phase 3: 领域面板 - 统一的游戏管理界面

功能模块：
- 游戏库管理
- 游戏会话跟踪
- 成就系统
- 统计面板

Author: LivingTreeAI Team
Version: 1.0.0
"""

from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import json


class GameStatus(Enum):
    """游戏状态"""
    IDLE = "idle"           # 空闲
    PLAYING = "playing"    # 游戏中
    PAUSED = "paused"      # 暂停
    COMPLETED = "completed"# 完成


class AchievementType(Enum):
    """成就类型"""
    STORY = "story"        # 剧情成就
    SKILL = "skill"        # 技能成就
    EXPLORATION = "exploration"  # 探索成就
    COLLECTION = "collection"    # 收集成就
    CHALLENGE = "challenge"      # 挑战成就


@dataclass
class Game:
    """游戏"""
    id: str
    name: str
    genre: str
    platform: str
    status: GameStatus = GameStatus.IDLE
    total_playtime: float = 0.0  # 分钟
    last_played: Optional[float] = None
    cover_image: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GameSession:
    """游戏会话"""
    id: str
    game_id: str
    start_time: float
    end_time: Optional[float] = None
    duration: float = 0.0  # 分钟
    achievements: List[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class Achievement:
    """成就"""
    id: str
    name: str
    description: str
    game_id: str
    achievement_type: AchievementType
    unlocked: bool = False
    unlocked_at: Optional[float] = None
    icon: Optional[str] = None
    rarity: float = 0.0  # 稀有度 0-1


@dataclass
class PlayerStats:
    """玩家统计"""
    total_games: int = 0
    completed_games: int = 0
    total_playtime: float = 0.0  # 分钟
    total_achievements: int = 0
    unlocked_achievements: int = 0
    favorite_genre: str = ""
    most_played_game: str = ""


class GameLibraryWidget:
    """游戏库组件"""
    
    def __init__(self):
        self.games: Dict[str, Game] = {}
        self._sorted_games: List[Game] = []
    
    def add_game(self, game: Game) -> None:
        """添加游戏"""
        self.games[game.id] = game
        self._update_sorted()
    
    def remove_game(self, game_id: str) -> bool:
        """移除游戏"""
        if game_id in self.games:
            del self.games[game_id]
            self._update_sorted()
            return True
        return False
    
    def get_game(self, game_id: str) -> Optional[Game]:
        """获取游戏"""
        return self.games.get(game_id)
    
    def get_games_by_status(self, status: GameStatus) -> List[Game]:
        """按状态获取游戏"""
        return [g for g in self.games.values() if g.status == status]
    
    def get_games_by_genre(self, genre: str) -> List[Game]:
        """按类型获取游戏"""
        return [g for g in self.games.values() if g.genre == genre]
    
    def get_recent_games(self, limit: int = 5) -> List[Game]:
        """获取最近游戏"""
        recent = [g for g in self.games.values() if g.last_played]
        return sorted(recent, key=lambda x: x.last_played or 0, reverse=True)[:limit]
    
    def _update_sorted(self) -> None:
        """更新排序列表"""
        self._sorted_games = sorted(
            self.games.values(),
            key=lambda x: x.last_played or 0,
            reverse=True
        )
    
    def get_library_stats(self) -> Dict[str, Any]:
        """获取库统计"""
        genres = {}
        platforms = {}
        
        for game in self.games.values():
            genres[game.genre] = genres.get(game.genre, 0) + 1
            platforms[game.platform] = platforms.get(game.platform, 0) + 1
        
        return {
            "total_games": len(self.games),
            "by_genre": genres,
            "by_platform": platforms,
            "total_playtime": sum(g.total_playtime for g in self.games.values()),
        }


class SessionTrackerWidget:
    """会话跟踪组件"""
    
    def __init__(self):
        self.sessions: Dict[str, GameSession] = {}
        self.active_session: Optional[GameSession] = None
    
    def start_session(self, game_id: str) -> GameSession:
        """开始会话"""
        import time
        
        if self.active_session:
            self.end_session()
        
        session = GameSession(
            id=f"session_{len(self.sessions)}",
            game_id=game_id,
            start_time=time.time(),
        )
        self.sessions[session.id] = session
        self.active_session = session
        return session
    
    def end_session(self) -> Optional[GameSession]:
        """结束会话"""
        if self.active_session:
            import time
            self.active_session.end_time = time.time()
            self.active_session.duration = (
                self.active_session.end_time - self.active_session.start_time
            ) / 60  # 转换为分钟
            session = self.active_session
            self.active_session = None
            return session
        return None
    
    def add_achievement_to_session(self, achievement_id: str) -> None:
        """添加成就到当前会话"""
        if self.active_session:
            self.active_session.achievements.append(achievement_id)
    
    def get_session_history(self, limit: int = 10) -> List[GameSession]:
        """获取会话历史"""
        sorted_sessions = sorted(
            self.sessions.values(),
            key=lambda x: x.start_time,
            reverse=True
        )
        return sorted_sessions[:limit]
    
    def get_session_stats(self) -> Dict[str, Any]:
        """获取会话统计"""
        if not self.sessions:
            return {
                "total_sessions": 0,
                "total_duration": 0,
                "average_duration": 0,
            }
        
        total_duration = sum(s.duration for s in self.sessions.values())
        return {
            "total_sessions": len(self.sessions),
            "total_duration": total_duration,
            "average_duration": total_duration / len(self.sessions),
            "active_sessions": 1 if self.active_session else 0,
        }


class AchievementWidget:
    """成就系统组件"""
    
    def __init__(self):
        self.achievements: Dict[str, Achievement] = {}
    
    def add_achievement(self, achievement: Achievement) -> None:
        """添加成就"""
        self.achievements[achievement.id] = achievement
    
    def unlock_achievement(self, achievement_id: str) -> bool:
        """解锁成就"""
        import time
        
        achievement = self.achievements.get(achievement_id)
        if achievement and not achievement.unlocked:
            achievement.unlocked = True
            achievement.unlocked_at = time.time()
            return True
        return False
    
    def get_game_achievements(self, game_id: str) -> List[Achievement]:
        """获取游戏成就"""
        return [
            a for a in self.achievements.values()
            if a.game_id == game_id
        ]
    
    def get_unlocked_achievements(self) -> List[Achievement]:
        """获取已解锁成就"""
        return [a for a in self.achievements.values() if a.unlocked]
    
    def get_locked_achievements(self) -> List[Achievement]:
        """获取未解锁成就"""
        return [a for a in self.achievements.values() if not a.unlocked]
    
    def get_achievement_progress(self) -> Dict[str, Any]:
        """获取成就进度"""
        total = len(self.achievements)
        unlocked = len(self.get_unlocked_achievements())
        
        by_type = {}
        for achievement in self.achievements.values():
            type_name = achievement.achievement_type.value
            if type_name not in by_type:
                by_type[type_name] = {"total": 0, "unlocked": 0}
            by_type[type_name]["total"] += 1
            if achievement.unlocked:
                by_type[type_name]["unlocked"] += 1
        
        return {
            "total": total,
            "unlocked": unlocked,
            "locked": total - unlocked,
            "progress": (unlocked / total * 100) if total > 0 else 0,
            "by_type": by_type,
        }


class GameStatsWidget:
    """统计面板组件"""
    
    def __init__(self):
        self.playtime_history: List[Dict[str, Any]] = []
    
    def update_stats(self, stats: PlayerStats) -> None:
        """更新统计"""
        # 保存历史
        import time
        self.playtime_history.append({
            "timestamp": time.time(),
            "total_playtime": stats.total_playtime,
            "completed_games": stats.completed_games,
        })
    
    def get_player_stats(self, library, sessions) -> PlayerStats:
        """获取玩家统计"""
        stats = PlayerStats()
        stats.total_games = len(library.games)
        stats.total_playtime = sum(s.duration for s in sessions.sessions.values())
        
        completed = [
            g for g in library.games.values()
            if g.status == GameStatus.COMPLETED
        ]
        stats.completed_games = len(completed)
        
        achievements = sessions.get_session_stats()
        stats.total_achievements = 0  # 从成就系统获取
        
        # 获取游玩最多的游戏
        game_playtimes = {}
        for session in sessions.sessions.values():
            game_playtimes[session.game_id] = (
                game_playtimes.get(session.game_id, 0) + session.duration
            )
        
        if game_playtimes:
            most_played = max(game_playtimes, key=game_playtimes.get)
            game = library.get_game(most_played)
            if game:
                stats.most_played_game = game.name
        
        return stats
    
    def get_playtime_chart_data(self) -> Dict[str, Any]:
        """获取游玩时间图表数据"""
        return {
            "type": "line",
            "data": {
                "labels": [str(h["timestamp"]) for h in self.playtime_history],
                "datasets": [{
                    "label": "Total Playtime",
                    "data": [h["total_playtime"] for h in self.playtime_history],
                }]
            },
            "options": {
                "title": "Playtime Trend",
            }
        }


class GameHubPanel:
    """
    统一游戏面板
    
    整合所有游戏相关模块：
    - 游戏库管理
    - 会话跟踪
    - 成就系统
    - 统计面板
    """
    
    def __init__(self):
        # 初始化所有组件
        self.library = GameLibraryWidget()
        self.sessions = SessionTrackerWidget()
        self.achievements = AchievementWidget()
        self.stats = GameStatsWidget()
        
        # 事件回调
        self._event_handlers: Dict[str, List[Callable]] = {
            "game_started": [],
            "game_ended": [],
            "achievement_unlocked": [],
            "stats_updated": [],
        }
    
    def add_game(self, game: Game) -> None:
        """添加游戏"""
        self.library.add_game(game)
        self._emit_event("game_started", {"game_id": game.id})
    
    def start_playing(self, game_id: str) -> None:
        """开始游戏"""
        game = self.library.get_game(game_id)
        if game:
            game.status = GameStatus.PLAYING
            import time
            game.last_played = time.time()
            self.sessions.start_session(game_id)
            self._emit_event("game_started", {"game_id": game_id})
    
    def stop_playing(self) -> None:
        """停止游戏"""
        if self.sessions.active_session:
            game_id = self.sessions.active_session.game_id
            session = self.sessions.end_session()
            
            if session:
                game = self.library.get_game(game_id)
                if game:
                    game.total_playtime += session.duration
                    game.status = GameStatus.IDLE
            
            self._emit_event("game_ended", {
                "game_id": game_id,
                "duration": session.duration if session else 0,
            })
    
    def unlock_achievement(self, achievement_id: str) -> bool:
        """解锁成就"""
        if self.achievements.unlock_achievement(achievement_id):
            achievement = self.achievements.achievements.get(achievement_id)
            if achievement:
                self.sessions.add_achievement_to_session(achievement_id)
                self._emit_event("achievement_unlocked", {
                    "achievement_id": achievement_id,
                    "game_id": achievement.game_id,
                })
                return True
        return False
    
    def get_overall_stats(self) -> Dict[str, Any]:
        """获取整体统计"""
        return {
            "library": self.library.get_library_stats(),
            "sessions": self.sessions.get_session_stats(),
            "achievements": self.achievements.get_achievement_progress(),
            "recent_games": [
                {
                    "id": g.id,
                    "name": g.name,
                    "status": g.status.value,
                }
                for g in self.library.get_recent_games()
            ],
        }
    
    def on_event(self, event_type: str, handler: Callable) -> None:
        """注册事件处理"""
        if event_type in self._event_handlers:
            self._event_handlers[event_type].append(handler)
    
    def _emit_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """触发事件"""
        for handler in self._event_handlers.get(event_type, []):
            try:
                handler(data)
            except Exception:
                pass
    
    def export_data(self) -> str:
        """导出数据"""
        data = {
            "library": {
                "games": [
                    {
                        "id": g.id,
                        "name": g.name,
                        "genre": g.genre,
                        "platform": g.platform,
                        "status": g.status.value,
                        "total_playtime": g.total_playtime,
                    }
                    for g in self.library.games.values()
                ]
            },
            "achievements": {
                "list": [
                    {
                        "id": a.id,
                        "name": a.name,
                        "unlocked": a.unlocked,
                    }
                    for a in self.achievements.achievements.values()
                ]
            },
            "stats": self.get_overall_stats(),
        }
        return json.dumps(data, indent=2, ensure_ascii=False)


# 全局面板实例
_global_panel: Optional[GameHubPanel] = None


def get_game_hub_panel() -> GameHubPanel:
    """获取全局游戏面板实例"""
    global _global_panel
    
    if _global_panel is None:
        _global_panel = GameHubPanel()
    
    return _global_panel


# ──────────────────────────────────────────────────────────────
# PyQt6 UI 层
# ──────────────────────────────────────────────────────────────

try:
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
        QLabel, QPushButton, QTabWidget, QTableWidget, QTableWidgetItem,
        QHeaderView, QGroupBox, QFormLayout, QProgressBar,
        QComboBox, QLineEdit, QSpinBox, QMessageBox,
        QListWidget, QListWidgetItem, QSplitter, QFrame,
    )
    from PyQt6.QtCore import (
        Qt, QTimer, pyqtSignal, QSize,
    )
    from PyQt6.QtGui import QFont, QIcon, QPalette, QColor
    HAS_PYQT = True
except ImportError:
    HAS_PYQT = False


if HAS_PYQT:
    class GameHubPanelUI(QWidget):
        """
        GameHub 主面板 UI
        
        整合所有游戏模块的可视化界面。
        """
        
        # 信号
        game_started = pyqtSignal(str)
        game_stopped = pyqtSignal(str)
        achievement_unlocked = pyqtSignal(str)
        
        def __init__(self, parent: Optional[QWidget] = None):
            super().__init__(parent)
            self._panel = get_game_hub_panel()
            self._init_ui()
            self._init_mock_data()
            self._update_ui()
        
        def _init_ui(self) -> None:
            """初始化 UI"""
            layout = QVBoxLayout(self)
            layout.setContentsMargins(8, 8, 8, 8)
            layout.setSpacing(8)
            
            # 标题
            title = QLabel("🎮 游戏中心")
            font = QFont()
            font.setPointSize(16)
            font.setBold(True)
            title.setFont(font)
            layout.addWidget(title)
            
            # 选项卡
            self._tabs = QTabWidget()
            self._tabs.currentChanged.connect(self._on_tab_changed)
            
            # 游戏库选项卡
            self._library_widget = self._create_library_tab()
            self._tabs.addTab(self._library_widget, "🎮 游戏库")
            
            # 会话选项卡
            self._sessions_widget = self._create_sessions_tab()
            self._tabs.addTab(self._sessions_widget, "⏱ 会话")
            
            # 成就选项卡
            self._achievements_widget = self._create_achievements_tab()
            self._tabs.addTab(self._achievements_widget, "🏆 成就")
            
            # 统计选项卡
            self._stats_widget = self._create_stats_tab()
            self._tabs.addTab(self._stats_widget, "📊 统计")
            
            layout.addWidget(self._tabs)
            
            # 状态栏
            self._status_bar = QLabel("就绪")
            self._status_bar.setStyleSheet("color: #666; font-size: 12px;")
            layout.addWidget(self._status_bar)
        
        def _create_library_tab(self) -> QWidget:
            """创建游戏库选项卡"""
            widget = QWidget()
            layout = QVBoxLayout(widget)
            layout.setContentsMargins(8, 8, 8, 8)
            
            # 游戏列表
            list_group = QGroupBox("游戏列表")
            list_layout = QVBoxLayout(list_group)
            self._games_table = QTableWidget()
            self._games_table.setColumnCount(6)
            self._games_table.setHorizontalHeaderLabels(["ID", "名称", "类型", "平台", "状态", "游玩时间"])
            self._games_table.horizontalHeader().setStretchLastSection(True)
            self._games_table.cellDoubleClicked.connect(self._on_game_double_clicked)
            list_layout.addWidget(self._games_table)
            layout.addWidget(list_group)
            
            # 操作按钮
            btn_layout = QHBoxLayout()
            add_btn = QPushButton("添加游戏")
            start_btn = QPushButton("开始游戏")
            stop_btn = QPushButton("停止游戏")
            refresh_btn = QPushButton("刷新")
            btn_layout.addWidget(add_btn)
            btn_layout.addWidget(start_btn)
            btn_layout.addWidget(stop_btn)
            btn_layout.addStretch()
            btn_layout.addWidget(refresh_btn)
            layout.addLayout(btn_layout)
            
            return widget
        
        def _create_sessions_tab(self) -> QWidget:
            """创建会话选项卡"""
            widget = QWidget()
            layout = QVBoxLayout(widget)
            layout.setContentsMargins(8, 8, 8, 8)
            
            # 活跃会话
            active_group = QGroupBox("活跃会话")
            active_layout = QFormLayout(active_group)
            self._active_session_label = QLabel("无")
            active_layout.addRow("当前会话：", self._active_session_label)
            self._session_duration_label = QLabel("0 分钟")
            active_layout.addRow("时长：", self._session_duration_label)
            layout.addWidget(active_group)
            
            # 会话历史
            history_group = QGroupBox("会话历史")
            history_layout = QVBoxLayout(history_group)
            self._sessions_table = QTableWidget()
            self._sessions_table.setColumnCount(4)
            self._sessions_table.setHorizontalHeaderLabels(["ID", "游戏", "时长", "成就"])
            self._sessions_table.horizontalHeader().setStretchLastSection(True)
            history_layout.addWidget(self._sessions_table)
            layout.addWidget(history_group)
            
            return widget
        
        def _create_achievements_tab(self) -> QWidget:
            """创建成就选项卡"""
            widget = QWidget()
            layout = QVBoxLayout(widget)
            layout.setContentsMargins(8, 8, 8, 8)
            
            # 成就进度
            progress_group = QGroupBox("成就进度")
            progress_layout = QFormLayout(progress_group)
            self._achievement_progress_bar = QProgressBar()
            self._achievement_progress_bar.setRange(0, 100)
            self._achievement_progress_bar.setValue(0)
            progress_layout.addRow("总进度：", self._achievement_progress_bar)
            self._achievement_count_label = QLabel("0/0")
            progress_layout.addRow("解锁数：", self._achievement_count_label)
            layout.addWidget(progress_group)
            
            # 成就列表
            list_group = QGroupBox("成就列表")
            list_layout = QVBoxLayout(list_group)
            self._achievements_list = QListWidget()
            list_layout.addWidget(self._achievements_list)
            layout.addWidget(list_group)
            
            # 按类型统计
            type_group = QGroupBox("按类型统计")
            type_layout = QFormLayout(type_group)
            self._achievement_type_labels = {}
            for type_name in ["story", "skill", "exploration", "collection", "challenge"]:
                label = QLabel("0/0")
                self._achievement_type_labels[type_name] = label
                type_layout.addRow(f"{type_name}：", label)
            layout.addWidget(type_group)
            
            return widget
        
        def _create_stats_tab(self) -> QWidget:
            """创建统计选项卡"""
            widget = QWidget()
            layout = QVBoxLayout(widget)
            layout.setContentsMargins(8, 8, 8, 8)
            
            # 玩家统计
            stats_group = QGroupBox("玩家统计")
            stats_layout = QFormLayout(stats_group)
            self._total_games_label = QLabel("0")
            stats_layout.addRow("总游戏数：", self._total_games_label)
            self._completed_games_label = QLabel("0")
            stats_layout.addRow("已完成：", self._completed_games_label)
            self._total_playtime_label = QLabel("0 分钟")
            stats_layout.addRow("总游玩时间：", self._total_playtime_label)
            self._total_achievements_label = QLabel("0")
            stats_layout.addRow("总成就数：", self._total_achievements_label)
            self._unlocked_achievements_label = QLabel("0")
            stats_layout.addRow("已解锁：", self._unlocked_achievements_label)
            self._favorite_genre_label = QLabel("-")
            stats_layout.addRow("最喜爱类型：", self._favorite_genre_label)
            self._most_played_game_label = QLabel("-")
            stats_layout.addRow("最常玩：", self._most_played_game_label)
            layout.addWidget(stats_group)
            
            # 游戏推荐（占位）
            recommend_group = QGroupBox("🎯 游戏推荐")
            recommend_layout = QVBoxLayout(recommend_group)
            recommend_layout.addWidget(QLabel("（推荐算法待集成）"))
            layout.addWidget(recommend_group)
            
            layout.addStretch()
            return widget
        
        def _init_mock_data(self) -> None:
            """初始化模拟数据"""
            # 添加示例游戏
            from typing import cast
            self._panel.add_game(Game(
                id="game_001",
                name="塞尔达传说",
                genre="冒险",
                platform="Switch",
                status=GameStatus.COMPLETED,
                total_playtime=1200.0,
            ))
            self._panel.add_game(Game(
                id="game_002",
                name="艾尔登法环",
                genre="动作RPG",
                platform="PC",
                status=GameStatus.PLAYING,
                total_playtime=800.0,
            ))
            self._panel.add_game(Game(
                id="game_003",
                name="星露谷物语",
                genre="模拟",
                platform="PC",
                status=GameStatus.IDLE,
                total_playtime=300.0,
            ))
            
            # 添加示例成就
            self._panel.achievements.add_achievement(Achievement(
                id="ach_001",
                name="初次冒险",
                description="开始第一个游戏",
                game_id="game_001",
                achievement_type=AchievementType.STORY,
                unlocked=True,
                unlocked_at=time.time() - 86400 * 30,
                rarity=0.8,
            ))
            self._panel.achievements.add_achievement(Achievement(
                id="ach_002",
                name="百小时大师",
                description="累计游玩 100 小时",
                game_id="game_001",
                achievement_type=AchievementType.CHALLENGE,
                unlocked=False,
                rarity=0.1,
            ))
        
        def _update_ui(self) -> None:
            """更新 UI 显示"""
            # 游戏库
            self._update_games_table()
            
            # 会话
            self._update_sessions_ui()
            
            # 成就
            self._update_achievements_ui()
            
            # 统计
            self._update_stats_ui()
            
            self._status_bar.setText(f"最后更新：{time.strftime('%H:%M:%S')}")
        
        def _update_games_table(self) -> None:
            """更新游戏列表"""
            games = list(self._panel.library.games.values())
            self._games_table.setRowCount(len(games))
            for row, game in enumerate(games):
                self._games_table.setItem(row, 0, QTableWidgetItem(game.id))
                self._games_table.setItem(row, 1, QTableWidgetItem(game.name))
                self._games_table.setItem(row, 2, QTableWidgetItem(game.genre))
                self._games_table.setItem(row, 3, QTableWidgetItem(game.platform))
                status_item = QTableWidgetItem(game.status.value)
                if game.status == GameStatus.PLAYING:
                    status_item.setForeground(QColor("green"))
                elif game.status == GameStatus.COMPLETED:
                    status_item.setForeground(QColor("blue"))
                self._games_table.setItem(row, 4, status_item)
                self._games_table.setItem(row, 5, QTableWidgetItem(f"{game.total_playtime:.0f} 分钟"))
        
        def _update_sessions_ui(self) -> None:
            """更新会话 UI"""
            # 活跃会话
            active = self._panel.sessions.active_session
            if active:
                game = self._panel.library.get_game(active.game_id)
                game_name = game.name if game else active.game_id
                self._active_session_label.setText(f"{game_name} (开始于 {time.strftime('%H:%M', time.localtime(active.start_time))})")
                duration = (time.time() - active.start_time) / 60
                self._session_duration_label.setText(f"{duration:.0f} 分钟")
            else:
                self._active_session_label.setText("无")
                self._session_duration_label.setText("0 分钟")
            
            # 会话历史
            sessions = self._panel.sessions.get_session_history(limit=50)
            self._sessions_table.setRowCount(len(sessions))
            for row, session in enumerate(sessions):
                game = self._panel.library.get_game(session.game_id)
                game_name = game.name if game else session.game_id
                self._sessions_table.setItem(row, 0, QTableWidgetItem(session.id))
                self._sessions_table.setItem(row, 1, QTableWidgetItem(game_name))
                self._sessions_table.setItem(row, 2, QTableWidgetItem(f"{session.duration:.0f} 分钟"))
                self._sessions_table.setItem(row, 3, QTableWidgetItem(f"{len(session.achievements)} 个"))
        
        def _update_achievements_ui(self) -> None:
            """更新成就 UI"""
            progress = self._panel.achievements.get_achievement_progress()
            
            # 进度条
            self._achievement_progress_bar.setValue(int(progress["progress"]))
            self._achievement_count_label.setText(f"{progress['unlocked']}/{progress['total']}")
            
            # 成就列表
            self._achievements_list.clear()
            for ach in self._panel.achievements.achievements.values():
                item_text = f"{'✅' if ach.unlocked else '🔒'} {ach.name} ({ach.achievement_type.value})"
                item = QListWidgetItem(item_text)
                self._achievements_list.addItem(item)
            
            # 按类型统计
            for type_name, data in progress.get("by_type", {}).items():
                if type_name in self._achievement_type_labels:
                    label = self._achievement_type_labels[type_name]
                    label.setText(f"{data['unlocked']}/{data['total']}")
        
        def _update_stats_ui(self) -> None:
            """更新统计 UI"""
            stats = self._panel.get_overall_stats()
            
            self._total_games_label.setText(str(stats["library"]["total_games"]))
            self._completed_games_label.setText(str(stats["library"].get("completed_games", 0)))
            self._total_playtime_label.setText(f"{stats['library'].get('total_playtime', 0):.0f} 分钟")
            self._total_achievements_label.setText(str(stats["achievements"]["total"]))
            self._unlocked_achievements_label.setText(str(stats["achievements"]["unlocked"]))
            
            # 获取玩家统计
            player_stats = self._panel.stats.get_player_stats(
                self._panel.library,
                self._panel.sessions,
            )
            self._favorite_genre_label.setText(player_stats.favorite_genre or "-")
            self._most_played_game_label.setText(player_stats.most_played_game or "-")
        
        def _on_tab_changed(self, index: int) -> None:
            """选项卡切换"""
            self._update_ui()
        
        def _on_game_double_clicked(self, row: int, column: int) -> None:
            """双击游戏"""
            if row >= 0:
                item = self._games_table.item(row, 0)
                if item:
                    game_id = item.text()
                    self.game_started.emit(game_id)
        
        def refresh(self) -> None:
            """刷新数据"""
            self._update_ui()
        
        def get_panel(self) -> GameHubPanel:
            """获取底层面板（用于数据操作）"""
            return self._panel

else:
    # 无 PyQt6 时的占位
    class GameHubPanelUI:
        def __init__(self, *args, **kwargs):
            raise ImportError("PyQt6 未安装，无法使用 GameHubPanelUI")

