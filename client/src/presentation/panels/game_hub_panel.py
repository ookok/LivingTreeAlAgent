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
