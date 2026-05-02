# -*- coding: utf-8 -*-
"""
斗地主房间管理与匹配系统
Room Manager and Matchmaking for Dou Di Zhu

作者：Hermes Desktop V2.0
版本：1.0.0
"""

from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import uuid
import asyncio


class RoomStatus(Enum):
    """房间状态"""
    WAITING = "waiting"      # 等待中
    READY = "ready"          # 准备开始
    PLAYING = "playing"       # 游戏中
    FINISHED = "finished"     # 已结束
    CLOSED = "closed"        # 已关闭


class MatchMode(Enum):
    """匹配模式"""
    QUICK = "quick"          # 快速匹配
    RANKED = "ranked"        # 排位匹配
    CUSTOM = "custom"         # 自定义房间


@dataclass
class PlayerInfo:
    """玩家信息"""
    player_id: str
    name: str
    credits: int = 0
    rank: int = 0
    avatar: str = "default"
    ready: bool = False
    is_ai: bool = False
    difficulty: str = "medium"
    joined_at: datetime = field(default_factory=datetime.now)


class GameRoom:
    """游戏房间"""

    def __init__(self, room_id: str, creator_id: str, config: Dict = None):
        self.room_id = room_id
        self.creator_id = creator_id
        self.config = config or {
            "max_players": 3,
            "min_credits": 0,
            "ai_enabled": True,
            "difficulty": "medium",
            "time_limit": 30,  # 秒
            "entry_fee": 0
        }

        self.players: Dict[str, PlayerInfo] = {}
        self.status = RoomStatus.WAITING
        self.created_at = datetime.now()
        self.started_at: Optional[datetime] = None
        self.game_state = None
        self.observers: List[str] = []  # 观战者

    def join(self, player_info: PlayerInfo) -> bool:
        """加入房间"""
        if self.status not in [RoomStatus.WAITING, RoomStatus.READY]:
            return False

        if len(self.players) >= self.config["max_players"]:
            return False

        if player_info.player_id in self.players:
            return False

        # 检查积分要求
        if player_info.credits < self.config.get("min_credits", 0):
            return False

        self.players[player_info.player_id] = player_info

        # 如果人数够了，标记为ready
        if len(self.players) >= 2:
            self.status = RoomStatus.READY

        return True

    def leave(self, player_id: str) -> bool:
        """离开房间"""
        if player_id not in self.players:
            return False

        if self.status == RoomStatus.PLAYING:
            # 游戏中离开，视为逃跑
            self.handle_player_escape(player_id)

        del self.players[player_id]

        # 更新状态
        if len(self.players) < 2:
            self.status = RoomStatus.WAITING

        # 如果房间空了，关闭房间
        if not self.players:
            self.status = RoomStatus.CLOSED

        return True

    def set_ready(self, player_id: str, ready: bool) -> bool:
        """设置准备状态"""
        if player_id not in self.players:
            return False

        self.players[player_id].ready = ready

        # 检查是否所有人都准备好了
        if len(self.players) >= 2 and all(p.ready for p in self.players.values()):
            self.status = RoomStatus.READY

        return True

    def start_game(self) -> bool:
        """开始游戏"""
        if self.status not in [RoomStatus.WAITING, RoomStatus.READY]:
            return False

        if len(self.players) < 2:
            return False

        # 检查是否都准备
        if not all(p.ready for p in self.players.values()):
            return False

        self.status = RoomStatus.PLAYING
        self.started_at = datetime.now()

        return True

    def handle_player_escape(self, player_id: str):
        """处理玩家逃跑"""
        # 逃跑惩罚：扣除积分
        escape_penalty = 100

        # 通知其他玩家
        for pid, player in self.players.items():
            if pid != player_id:
                # 可以发送逃跑通知
                pass

    def add_observer(self, observer_id: str) -> bool:
        """添加观战者"""
        if observer_id not in self.players and observer_id not in self.observers:
            self.observers.append(observer_id)
            return True
        return False

    def remove_observer(self, observer_id: str) -> bool:
        """移除观战者"""
        if observer_id in self.observers:
            self.observers.remove(observer_id)
            return True
        return False

    def is_full(self) -> bool:
        """房间是否已满"""
        return len(self.players) >= self.config["max_players"]

    def can_start(self) -> bool:
        """是否可以开始"""
        return (len(self.players) >= 2 and
                all(p.ready for p in self.players.values()) and
                self.status in [RoomStatus.WAITING, RoomStatus.READY])

    def get_available_slots(self) -> int:
        """获取可用位置"""
        return self.config["max_players"] - len(self.players)

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "room_id": self.room_id,
            "creator_id": self.creator_id,
            "status": self.status.value,
            "players": {
                pid: {
                    "player_id": p.player_id,
                    "name": p.name,
                    "credits": p.credits,
                    "rank": p.rank,
                    "avatar": p.avatar,
                    "ready": p.ready,
                    "is_ai": p.is_ai
                }
                for pid, p in self.players.items()
            },
            "config": self.config,
            "observer_count": len(self.observers),
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None
        }


class RoomManager:
    """房间管理器"""

    def __init__(self):
        self.rooms: Dict[str, GameRoom] = {}
        self.player_rooms: Dict[str, str] = {}  # player_id -> room_id

    def create_room(self, creator_id: str, creator_name: str, config: Dict = None) -> GameRoom:
        """创建房间"""
        room_id = f"room_{uuid.uuid4().hex[:8]}"
        room = GameRoom(room_id, creator_id, config)
        room.players[creator_id] = PlayerInfo(creator_id, creator_name)
        self.rooms[room_id] = room
        self.player_rooms[creator_id] = room_id
        return room

    def get_room(self, room_id: str) -> Optional[GameRoom]:
        """获取房间"""
        return self.rooms.get(room_id)

    def get_player_room(self, player_id: str) -> Optional[GameRoom]:
        """获取玩家所在房间"""
        room_id = self.player_rooms.get(player_id)
        return self.rooms.get(room_id) if room_id else None

    def join_room(self, room_id: str, player_info: PlayerInfo) -> bool:
        """加入房间"""
        room = self.rooms.get(room_id)
        if not room:
            return False

        if not room.join(player_info):
            return False

        self.player_rooms[player_info.player_id] = room_id
        return True

    def leave_room(self, player_id: str) -> bool:
        """离开房间"""
        room = self.get_player_room(player_id)
        if not room:
            return False

        if not room.leave(player_id):
            return False

        del self.player_rooms[player_id]

        # 如果房间空了，删除房间
        if not room.players:
            del self.rooms[room.room_id]

        return True

    def close_room(self, room_id: str) -> bool:
        """关闭房间"""
        room = self.rooms.get(room_id)
        if not room:
            return False

        # 移除所有玩家的房间关联
        for player_id in list(room.players.keys()):
            if player_id in self.player_rooms:
                del self.player_rooms[player_id]

        room.status = RoomStatus.CLOSED
        del self.rooms[room_id]

        return True

    def get_available_rooms(self) -> List[Dict]:
        """获取可用房间列表"""
        return [
            room.to_dict()
            for room in self.rooms.values()
            if room.status in [RoomStatus.WAITING, RoomStatus.READY] and room.get_available_slots() > 0
        ]


class Matchmaking:
    """匹配系统"""

    def __init__(self, room_manager: RoomManager):
        self.room_manager = room_manager
        self.queues: Dict[str, List[PlayerInfo]] = {
            MatchMode.QUICK.value: [],
            MatchMode.RANKED.value: []
        }
        self.matchmaking_callbacks: Dict[str, Callable] = {}

    async def find_match(self, player_info: PlayerInfo, mode: str = "quick",
                       criteria: Dict = None) -> Optional[str]:
        """寻找匹配"""
        criteria = criteria or {}

        if mode == "quick":
            return await self._quick_match(player_info)
        elif mode == "ranked":
            return await self._ranked_match(player_info)
        elif mode == "custom":
            return await self._create_custom_room(player_info, criteria)

        return None

    async def _quick_match(self, player_info: PlayerInfo) -> Optional[str]:
        """快速匹配"""
        queue = self.queues[MatchMode.QUICK.value]

        # 添加到队列
        queue.append(player_info)

        # 尝试匹配
        if len(queue) >= 3:
            # 找到3个玩家
            players = queue[:3]
            del queue[:3]

            # 创建房间
            room = self.room_manager.create_room(
                players[0].player_id,
                players[0].name,
                {"mode": "quick"}
            )

            # 其他玩家加入
            for player in players[1:]:
                self.room_manager.join_room(room.room_id, player)
                self.room_manager.player_rooms[player.player_id] = room.room_id

            return room.room_id

        return None

    async def _ranked_match(self, player_info: PlayerInfo) -> Optional[str]:
        """排位匹配"""
        queue = self.queues[MatchMode.RANKED.value]
        player_rank = player_info.rank

        # 在相近等级中匹配
        for i, other_player in enumerate(queue):
            if abs(other_player.rank - player_rank) <= 500:
                # 等级相近，移除并继续寻找
                queue.pop(i)

                # 创建房间
                room = self.room_manager.create_room(
                    player_info.player_id,
                    player_info.name,
                    {"mode": "ranked"}
                )

                self.room_manager.join_room(room.room_id, other_player)
                self.room_manager.player_rooms[other_player.player_id] = room.room_id

                # 继续寻找第三个玩家
                if len(queue) >= 1:
                    third_player = queue.pop(0)
                    self.room_manager.join_room(room.room_id, third_player)
                    self.room_manager.player_rooms[third_player.player_id] = room.room_id

                return room.room_id

        # 没找到匹配，加入队列
        queue.append(player_info)

        return None

    async def _create_custom_room(self, player_info: PlayerInfo, criteria: Dict) -> Optional[str]:
        """创建自定义房间"""
        config = {
            "mode": "custom",
            "max_players": criteria.get("max_players", 3),
            "min_credits": criteria.get("min_credits", 0),
            "ai_enabled": criteria.get("ai_enabled", True),
            "difficulty": criteria.get("difficulty", "medium"),
            "time_limit": criteria.get("time_limit", 30),
            "entry_fee": criteria.get("entry_fee", 0)
        }

        room = self.room_manager.create_room(
            player_info.player_id,
            player_info.name,
            config
        )

        return room.room_id

    def cancel_match(self, player_id: str, mode: str = "quick") -> bool:
        """取消匹配"""
        queue = self.queues.get(mode)
        if not queue:
            return False

        for i, player in enumerate(queue):
            if player.player_id == player_id:
                queue.pop(i)
                return True

        return False

    def get_queue_size(self, mode: str = "quick") -> int:
        """获取队列大小"""
        return len(self.queues.get(mode, []))

    def register_callback(self, event: str, callback: Callable):
        """注册回调"""
        self.matchmaking_callbacks[event] = callback

    async def notify_match_found(self, room_id: str, players: List[PlayerInfo]):
        """通知匹配成功"""
        callback = self.matchmaking_callbacks.get("match_found")
        if callback:
            await callback(room_id, players)
