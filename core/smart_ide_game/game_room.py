"""
游戏房间系统模块
提供房间管理、玩家匹配、实时同步、语音聊天等功能
"""
import asyncio
import json
import hashlib
import uuid
from typing import Dict, List, Optional, Any, Callable, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import random
import string
from core.logger import get_logger
logger = get_logger('smart_ide_game.game_room')



class RoomType(Enum):
    """房间类型"""
    PRIVATE = "private"
    PUBLIC = "public"
    MATCHMAKING = "matchmaking"
    RANKED = "ranked"
    CREATIVE = "creative"
    SPECTATOR = "spectator"


class RoomStatus(Enum):
    """房间状态"""
    WAITING = "waiting"
    STARTING = "starting"
    PLAYING = "playing"
    PAUSED = "paused"
    FINISHED = "finished"
    CLOSED = "closed"


class PlayerStatus(Enum):
    """玩家状态"""
    LOBBY = "lobby"      # 在大厅等待
    READY = "ready"      # 已准备
    IN_GAME = "in_game"  # 游戏中
    AWAY = "away"        # 离开
    KICKED = "kicked"    # 被踢出


class MatchStrategy(Enum):
    """匹配策略"""
    SKILL_BASED = "skill_based"     # 基于技能
    REGION_BASED = "region_based"   # 基于地区
    RANDOM = "random"               # 随机
    FRIENDS = "friends"             # 好友优先


@dataclass
class RoomPlayer:
    """房间玩家"""
    id: str
    user_id: str
    username: str
    avatar: Optional[str] = None
    status: PlayerStatus = PlayerStatus.LOBBY
    team: Optional[str] = None
    is_host: bool = False
    is_ready: bool = False
    skill_rating: float = 1000.0
    latency: int = 0
    region: str = "unknown"
    is_muted: bool = False
    joined_at: datetime = field(default_factory=datetime.now)
    ready_at: Optional[datetime] = None


@dataclass
class RoomSettings:
    """房间设置"""
    room_name: str = "Game Room"
    max_players: int = 8
    min_players: int = 2
    game_mode: str = "deathmatch"
    map_name: str = "default"
    time_limit: int = 600  # 秒
    score_limit: int = 100
    friendly_fire: bool = False
    auto_balance: bool = True
    public_room: bool = False
    password: Optional[str] = None
    allow_spectators: bool = True
    max_spectators: int = 10
    region_lock: bool = False
    allowed_regions: List[str] = field(default_factory=list)
    skill_range: Optional[Tuple[float, float]] = None


@dataclass
class GameRoom:
    """游戏房间"""
    id: str
    settings: RoomSettings
    status: RoomStatus = RoomStatus.WAITING
    players: Dict[str, RoomPlayer] = field(default_factory=dict)
    spectators: List[str] = field(default_factory=list)
    host_id: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    match_id: Optional[str] = None
    game_state: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MatchRequest:
    """匹配请求"""
    user_id: str
    username: str
    skill_rating: float
    region: str
    game_mode: str
    team_preference: Optional[str] = None
    friends: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class MatchResult:
    """匹配结果"""
    match_id: str
    room_id: str
    player_ids: List[str]
    average_skill: float
    estimated_duration: int
    quality_score: float  # 0-1, 越高匹配越好


class TeamBalancer:
    """队伍平衡器"""

    @staticmethod
    def balance_teams(players: List[RoomPlayer], num_teams: int = 2) -> Dict[str, str]:
        """平衡队伍"""
        # 按技能评分排序
        sorted_players = sorted(players, key=lambda p: p.skill_rating, reverse=True)
        
        teams: Dict[str, List[RoomPlayer]] = {f"team_{i}": [] for i in range(num_teams)}
        
        # 交替分配以平衡队伍
        for i, player in enumerate(sorted_players):
            team_idx = i % num_teams
            team_name = f"team_{team_idx}"
            teams[team_name].append(player)
        
        # 返回 player_id -> team
        result = {}
        for team_name, team_players in teams.items():
            for player in team_players:
                result[player.id] = team_name
        
        return result

    @staticmethod
    def calculate_team_skill(players: List[RoomPlayer]) -> float:
        """计算队伍平均技能"""
        if not players:
            return 0.0
        return sum(p.skill_rating for p in players) / len(players)

    @staticmethod
    def skill_difference(team1_skill: float, team2_skill: float) -> float:
        """计算队伍技能差距"""
        return abs(team1_skill - team2_skill)


class Matchmaker:
    """匹配器"""

    def __init__(self):
        self.pending_requests: Dict[str, MatchRequest] = {}
        self.match_history: List[MatchResult] = []
        self.match_timeout = 30  # 秒
        self._matching = False
        self._match_task: Optional[asyncio.Task] = None

    async def start(self):
        """启动匹配器"""
        self._matching = True
        self._match_task = asyncio.create_task(self._match_loop())

    async def stop(self):
        """停止匹配器"""
        self._matching = False
        if self._match_task:
            self._match_task.cancel()

    def add_request(self, request: MatchRequest) -> str:
        """添加匹配请求"""
        request_id = str(uuid.uuid4())[:8]
        self.pending_requests[request_id] = request
        return request_id

    def remove_request(self, request_id: str) -> bool:
        """移除匹配请求"""
        if request_id in self.pending_requests:
            del self.pending_requests[request_id]
            return True
        return False

    def find_match(self, request: MatchRequest, min_players: int = 2) -> Optional[List[MatchRequest]]:
        """查找匹配"""
        candidates = []

        for req_id, req in self.pending_requests.items():
            if req_id == request.user_id:
                continue

            # 检查是否兼容
            if req.game_mode != request.game_mode:
                continue

            # 检查地区
            if req.region != request.region:
                continue

            # 检查技能差距
            skill_diff = abs(req.skill_rating - request.skill_rating)
            if skill_diff > 500:  # 允许500分差距
                continue

            # 检查好友
            if request.friends and req.user_id not in request.friends:
                continue

            candidates.append(req)

        # 按技能差距排序
        candidates.sort(key=lambda r: abs(r.skill_rating - request.skill_rating))

        if len(candidates) >= min_players - 1:
            return [request] + candidates[:min_players - 1]

        return None

    async def _match_loop(self):
        """匹配循环"""
        while self._matching:
            await asyncio.sleep(1)
            await self._process_matches()

    async def _process_matches(self):
        """处理匹配"""
        # 移除超时的请求
        now = datetime.now()
        timeout_requests = [
            req_id for req_id, req in self.pending_requests.items()
            if (now - req.created_at).total_seconds() > self.match_timeout
        ]
        for req_id in timeout_requests:
            self.remove_request(req_id)


class RoomManager:
    """房间管理器"""

    def __init__(self):
        self.rooms: Dict[str, GameRoom] = {}
        self.user_rooms: Dict[str, str] = {}  # user_id -> room_id
        self.matchmaker = Matchmaker()
        self.event_listeners: Dict[str, List[Callable]] = {}
        self._cleanup_task: Optional[asyncio.Task] = None

    async def start(self):
        """启动管理器"""
        await self.matchmaker.start()
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop(self):
        """停止管理器"""
        await self.matchmaker.stop()
        if self._cleanup_task:
            self._cleanup_task.cancel()

    def create_room(
        self,
        host_id: str,
        host_name: str,
        settings: RoomSettings
    ) -> GameRoom:
        """创建房间"""
        room_id = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        
        room = GameRoom(
            id=room_id,
            settings=settings,
            host_id=host_id
        )

        # 添加房主
        host = RoomPlayer(
            id=host_id,
            user_id=host_id,
            username=host_name,
            is_host=True,
            status=PlayerStatus.LOBBY
        )
        room.players[host_id] = host
        self.user_rooms[host_id] = room_id

        self.rooms[room_id] = room
        self._emit_event("room_created", {"room": self._room_to_dict(room)})

        return room

    def get_room(self, room_id: str) -> Optional[GameRoom]:
        """获取房间"""
        return self.rooms.get(room_id)

    def join_room(
        self,
        room_id: str,
        user_id: str,
        username: str,
        password: Optional[str] = None
    ) -> Optional[GameRoom]:
        """加入房间"""
        room = self.rooms.get(room_id)
        if not room:
            return None

        # 检查状态
        if room.status != RoomStatus.WAITING:
            return None

        # 检查人数
        if len(room.players) >= room.settings.max_players:
            return None

        # 检查密码
        if room.settings.password and room.settings.password != password:
            return None

        # 检查地区限制
        if room.settings.region_lock:
            # 简化实现
            pass

        # 检查是否已在房间
        if user_id in room.players:
            return room

        # 添加玩家
        player = RoomPlayer(
            id=user_id,
            user_id=user_id,
            username=username,
            status=PlayerStatus.LOBBY
        )
        room.players[user_id] = player
        self.user_rooms[user_id] = room_id

        self._emit_event("player_joined", {
            "room_id": room_id,
            "player": self._player_to_dict(player)
        })

        return room

    def leave_room(self, user_id: str) -> bool:
        """离开房间"""
        room_id = self.user_rooms.get(user_id)
        if not room_id:
            return False

        room = self.rooms.get(room_id)
        if not room:
            del self.user_rooms[user_id]
            return False

        # 移除玩家
        if user_id in room.players:
            player = room.players[user_id]
            del room.players[user_id]

            self._emit_event("player_left", {
                "room_id": room_id,
                "player_id": user_id,
                "username": player.username
            })

            # 如果房主离开，转移房主
            if player.is_host and room.players:
                new_host = next(iter(room.players.values()))
                new_host.is_host = True
                room.host_id = new_host.id

            # 如果没有玩家，关闭房间
            if not room.players:
                self.close_room(room_id)
                return True

        del self.user_rooms[user_id]
        return True

    def set_player_ready(self, room_id: str, user_id: str, ready: bool) -> bool:
        """设置玩家准备状态"""
        room = self.rooms.get(room_id)
        if not room or user_id not in room.players:
            return False

        player = room.players[user_id]
        player.is_ready = ready
        player.status = PlayerStatus.READY if ready else PlayerStatus.LOBBY
        player.ready_at = datetime.now() if ready else None

        self._emit_event("player_ready", {
            "room_id": room_id,
            "player_id": user_id,
            "ready": ready
        })

        # 检查是否所有人都准备好了
        if self._check_all_ready(room):
            asyncio.create_task(self.start_game(room_id))

        return True

    def _check_all_ready(self, room: GameRoom) -> bool:
        """检查是否所有人都准备好了"""
        if len(room.players) < room.settings.min_players:
            return False

        for player in room.players.values():
            if not player.is_ready and not player.is_host:
                return False

        return True

    async def start_game(self, room_id: str) -> bool:
        """开始游戏"""
        room = self.rooms.get(room_id)
        if not room:
            return False

        room.status = RoomStatus.STARTING
        room.started_at = datetime.now()
        room.match_id = str(uuid.uuid4())[:8]

        # 平衡队伍
        players = list(room.players.values())
        team_assignments = TeamBalancer.balance_teams(players)
        
        for player_id, team in team_assignments.items():
            if player_id in room.players:
                room.players[player_id].team = team

        # 初始化游戏状态
        room.game_state = {
            "start_time": room.started_at.timestamp(),
            "score": {team: 0 for team in set(team_assignments.values())},
            "elapsed": 0
        }

        room.status = RoomStatus.PLAYING

        self._emit_event("game_started", {
            "room_id": room_id,
            "match_id": room.match_id,
            "teams": team_assignments
        })

        return True

    async def end_game(self, room_id: str, winner: Optional[str] = None):
        """结束游戏"""
        room = self.rooms.get(room_id)
        if not room:
            return False

        room.status = RoomStatus.FINISHED
        room.ended_at = datetime.now()

        # 统计结果
        results = {
            "room_id": room_id,
            "duration": (room.ended_at - room.started_at).total_seconds() if room.started_at else 0,
            "winner": winner,
            "players": [
                {
                    "id": p.id,
                    "username": p.username,
                    "team": p.team,
                    "score": p.skill_rating
                }
                for p in room.players.values()
            ]
        }

        self._emit_event("game_ended", results)

        # 重置房间状态，允许再次开始
        room.status = RoomStatus.WAITING
        for player in room.players.values():
            player.is_ready = False
            player.status = PlayerStatus.LOBBY

        return True

    def close_room(self, room_id: str) -> bool:
        """关闭房间"""
        if room_id in self.rooms:
            # 通知所有玩家
            for user_id in list(self.rooms[room_id].players.keys()):
                if user_id in self.user_rooms:
                    del self.user_rooms[user_id]

            del self.rooms[room_id]
            self._emit_event("room_closed", {"room_id": room_id})
            return True
        return False

    def kick_player(self, room_id: str, host_id: str, target_id: str) -> bool:
        """踢出玩家"""
        room = self.rooms.get(room_id)
        if not room:
            return False

        if room.host_id != host_id:
            return False

        if target_id in room.players:
            player = room.players[target_id]
            player.status = PlayerStatus.KICKED
            self.leave_room(target_id)
            return True

        return False

    def update_player_latency(self, room_id: str, user_id: str, latency: int):
        """更新玩家延迟"""
        room = self.rooms.get(room_id)
        if room and user_id in room.players:
            room.players[user_id].latency = latency

    def get_room_list(
        self,
        game_mode: Optional[str] = None,
        region: Optional[str] = None,
        public_only: bool = True
    ) -> List[Dict[str, Any]]:
        """获取房间列表"""
        rooms = []

        for room in self.rooms.values():
            if room.status != RoomStatus.WAITING:
                continue

            if public_only and not room.settings.public_room:
                continue

            if game_mode and room.settings.game_mode != game_mode:
                continue

            rooms.append({
                "id": room.id,
                "name": room.settings.room_name,
                "game_mode": room.settings.game_mode,
                "map": room.settings.map_name,
                "player_count": len(room.players),
                "max_players": room.settings.max_players,
                "has_password": bool(room.settings.password),
                "region": "unknown",
                "host": room.players[room.host_id].username if room.host_id in room.players else "Unknown"
            })

        return rooms

    def get_user_room(self, user_id: str) -> Optional[GameRoom]:
        """获取用户所在的房间"""
        room_id = self.user_rooms.get(user_id)
        if room_id:
            return self.rooms.get(room_id)
        return None

    async def _cleanup_loop(self):
        """清理循环"""
        while True:
            await asyncio.sleep(60)  # 每分钟检查一次
            
            now = datetime.now()
            for room_id, room in list(self.rooms.items()):
                # 清理长时间未开始的房间
                if room.status == RoomStatus.WAITING:
                    age = (now - room.created_at).total_seconds()
                    if age > 3600:  # 1小时
                        self.close_room(room_id)

                # 清理已结束的房间
                elif room.status == RoomStatus.FINISHED:
                    age = (now - room.ended_at).total_seconds() if room.ended_at else 0
                    if age > 300:  # 5分钟
                        self.close_room(room_id)

    def add_event_listener(self, event: str, callback: Callable):
        """添加事件监听"""
        if event not in self.event_listeners:
            self.event_listeners[event] = []
        self.event_listeners[event].append(callback)

    def _emit_event(self, event: str, data: Dict[str, Any]):
        """触发事件"""
        if event in self.event_listeners:
            for callback in self.event_listeners[event]:
                try:
                    callback(event, data)
                except Exception as e:
                    logger.info(f"Event listener error: {e}")

    def _room_to_dict(self, room: GameRoom) -> Dict[str, Any]:
        """房间转字典"""
        return {
            "id": room.id,
            "name": room.settings.room_name,
            "status": room.status.value,
            "player_count": len(room.players),
            "max_players": room.settings.max_players,
            "game_mode": room.settings.game_mode,
            "host_id": room.host_id,
            "created_at": room.created_at.isoformat()
        }

    def _player_to_dict(self, player: RoomPlayer) -> Dict[str, Any]:
        """玩家转字典"""
        return {
            "id": player.id,
            "username": player.username,
            "avatar": player.avatar,
            "status": player.status.value,
            "team": player.team,
            "is_host": player.is_host,
            "is_ready": player.is_ready,
            "skill_rating": player.skill_rating,
            "latency": player.latency
        }

    def get_manager_stats(self) -> Dict[str, Any]:
        """获取管理器统计"""
        return {
            "total_rooms": len(self.rooms),
            "total_players": sum(len(r.players) for r in self.rooms.values()),
            "waiting_rooms": sum(1 for r in self.rooms.values() if r.status == RoomStatus.WAITING),
            "playing_rooms": sum(1 for r in self.rooms.values() if r.status == RoomStatus.PLAYING),
            "pending_match_requests": len(self.matchmaker.pending_requests)
        }


# 便捷函数
def create_room_settings(
    room_name: str,
    max_players: int = 8,
    game_mode: str = "deathmatch"
) -> RoomSettings:
    """创建房间设置"""
    return RoomSettings(
        room_name=room_name,
        max_players=max_players,
        game_mode=game_mode
    )


def create_match_request(
    user_id: str,
    username: str,
    skill_rating: float = 1000.0,
    region: str = "unknown",
    game_mode: str = "deathmatch"
) -> MatchRequest:
    """创建匹配请求"""
    return MatchRequest(
        user_id=user_id,
        username=username,
        skill_rating=skill_rating,
        region=region,
        game_mode=game_mode
    )
