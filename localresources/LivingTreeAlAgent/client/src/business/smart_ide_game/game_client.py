"""
游戏客户端模块
提供游戏运行时、资源管理、游戏逻辑等功能
"""
import asyncio
import json
import hashlib
import os
import uuid
import base64
from typing import Dict, List, Optional, Any, Callable, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import struct
import zlib


class GameState(Enum):
    """游戏状态"""
    IDLE = "idle"
    LOADING = "loading"
    RUNNING = "running"
    PAUSED = "paused"
    GAME_OVER = "game_over"
    ERROR = "error"


class PlayerState(Enum):
    """玩家状态"""
    ALIVE = "alive"
    DEAD = "dead"
    SPECTATING = "spectating"
    DISCONNECTED = "disconnected"


class GameType(Enum):
    """游戏类型"""
    SINGLE_PLAYER = "single_player"
    MULTI_PLAYER = "multi_player"
    COOPERATIVE = "cooperative"
    COMPETITIVE = "competitive"


@dataclass
class GameResource:
    """游戏资源"""
    id: str
    name: str
    resource_type: str  # image, audio, video, model, data, script
    path: str
    url: Optional[str] = None
    size: int = 0
    hash: Optional[str] = None
    compressed: bool = False
    compression_ratio: float = 1.0
    mime_type: str = "application/octet-stream"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GamePlayer:
    """游戏玩家"""
    id: str
    name: str
    avatar: Optional[str] = None
    state: PlayerState = PlayerState.ALIVE
    position: Dict[str, float] = field(default_factory=lambda: {"x": 0, "y": 0, "z": 0})
    rotation: Dict[str, float] = field(default_factory=lambda: {"x": 0, "y": 0, "z": 0})
    health: float = 100.0
    max_health: float = 100.0
    score: int = 0
    team: Optional[str] = None
    inventory: List[str] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)
    input_state: Dict[str, Any] = field(default_factory=dict)
    latency: int = 0
    is_local: bool = False


@dataclass
class GameEvent:
    """游戏事件"""
    type: str
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    source_player: Optional[str] = None


@dataclass
class GameSettings:
    """游戏设置"""
    graphics_quality: str = "medium"
    audio_volume: float = 0.8
    music_volume: float = 0.6
    voice_volume: float = 1.0
    show_fps: bool = False
    show_ping: bool = True
    v_sync: bool = True
    fullscreen: bool = False
    resolution: str = "1920x1080"
    sensitivity: float = 1.0
    inverted_y: bool = False
    language: str = "zh-CN"
    subtitles: bool = True


@dataclass
class GameConfig:
    """游戏配置"""
    id: str
    name: str
    game_type: GameType = GameType.SINGLE_PLAYER
    max_players: int = 1
    min_players: int = 1
    map_size: str = "small"
    time_limit: Optional[int] = None
    score_limit: Optional[int] = None
    friendly_fire: bool = False
    auto_balance: bool = True
    respawn_time: int = 10
    custom_settings: Dict[str, Any] = field(default_factory=dict)


class ResourceLoader:
    """资源加载器"""

    def __init__(self, cache_dir: str = None):
        self.cache_dir = cache_dir or os.path.join(os.path.expanduser("~"), ".hermes-desktop", "game_cache")
        os.makedirs(self.cache_dir, exist_ok=True)
        self.loaded_resources: Dict[str, GameResource] = {}
        self.loading_progress: Dict[str, float] = {}
        self._load_cache_index()

    def _load_cache_index(self):
        """加载缓存索引"""
        index_file = os.path.join(self.cache_dir, "index.json")
        if os.path.exists(index_file):
            try:
                with open(index_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for item in data.get("resources", []):
                        self.loaded_resources[item["id"]] = GameResource(
                            id=item["id"],
                            name=item["name"],
                            resource_type=item["resource_type"],
                            path=item["path"],
                            size=item.get("size", 0),
                            hash=item.get("hash"),
                        )
            except Exception as e:
                print(f"Failed to load cache index: {e}")

    def _save_cache_index(self):
        """保存缓存索引"""
        index_file = os.path.join(self.cache_dir, "index.json")
        data = {
            "resources": [
                {
                    "id": r.id,
                    "name": r.name,
                    "resource_type": r.resource_type,
                    "path": r.path,
                    "size": r.size,
                    "hash": r.hash,
                }
                for r in self.loaded_resources.values()
            ]
        }
        with open(index_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    async def load_resource(
        self,
        resource: GameResource,
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> Optional[bytes]:
        """加载资源"""
        self.loading_progress[resource.id] = 0

        try:
            # 检查缓存
            cached_path = os.path.join(self.cache_dir, resource.id)
            if os.path.exists(cached_path) and resource.hash:
                with open(cached_path, 'rb') as f:
                    data = f.read()
                    if hashlib.md5(data).hexdigest() == resource.hash:
                        self.loading_progress[resource.id] = 1.0
                        self.loaded_resources[resource.id] = resource
                        return data

            # 加载文件
            if os.path.exists(resource.path):
                with open(resource.path, 'rb') as f:
                    data = f.read()
                    resource.size = len(data)

                    # 解压
                    if resource.compressed:
                        data = zlib.decompress(data)

                    # 保存到缓存
                    with open(cached_path, 'wb') as cf:
                        cf.write(data)

                    # 计算哈希
                    resource.hash = hashlib.md5(data).hexdigest()

                    self.loading_progress[resource.id] = 1.0
                    self.loaded_resources[resource.id] = resource
                    self._save_cache_index()

                    if progress_callback:
                        progress_callback(1.0)

                    return data

        except Exception as e:
            print(f"Failed to load resource {resource.id}: {e}")

        return None

    async def load_resources_batch(
        self,
        resources: List[GameResource],
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> Dict[str, bytes]:
        """批量加载资源"""
        results = {}
        total = len(resources)

        for i, resource in enumerate(resources):
            data = await self.load_resource(resource)
            if data:
                results[resource.id] = data

            if progress_callback:
                progress_callback((i + 1) / total, resource.name)

        return results

    def get_loading_progress(self, resource_id: str) -> float:
        """获取加载进度"""
        return self.loading_progress.get(resource_id, 0.0)

    def clear_cache(self) -> int:
        """清理缓存"""
        count = 0
        for resource in self.loaded_resources.values():
            cached_path = os.path.join(self.cache_dir, resource.id)
            if os.path.exists(cached_path):
                os.remove(cached_path)
                count += 1

        self.loaded_resources.clear()
        self._save_cache_index()
        return count


class GameStateManager:
    """游戏状态管理器"""

    def __init__(self):
        self.state = GameState.IDLE
        self.players: Dict[str, GamePlayer] = {}
        self.local_player_id: Optional[str] = None
        self.game_config: Optional[GameConfig] = None
        self.game_time: float = 0.0
        self.tick: int = 0
        self.game_data: Dict[str, Any] = {}
        self.event_history: List[GameEvent] = []
        self.max_history = 1000

    def set_state(self, state: GameState):
        """设置游戏状态"""
        old_state = self.state
        self.state = state

        self.record_event(GameEvent(
            type="state_change",
            data={"old": old_state.value, "new": state.value}
        ))

    def add_player(self, player: GamePlayer):
        """添加玩家"""
        self.players[player.id] = player
        if player.is_local:
            self.local_player_id = player.id

    def remove_player(self, player_id: str) -> bool:
        """移除玩家"""
        if player_id in self.players:
            del self.players[player_id]
            return True
        return False

    def get_player(self, player_id: str) -> Optional[GamePlayer]:
        """获取玩家"""
        return self.players.get(player_id)

    def get_local_player(self) -> Optional[GamePlayer]:
        """获取本地玩家"""
        if self.local_player_id:
            return self.players.get(self.local_player_id)
        return None

    def update_player_state(
        self,
        player_id: str,
        position: Dict[str, float] = None,
        rotation: Dict[str, float] = None,
        health: float = None,
        score: int = None
    ):
        """更新玩家状态"""
        player = self.players.get(player_id)
        if not player:
            return

        if position is not None:
            player.position = position
        if rotation is not None:
            player.rotation = rotation
        if health is not None:
            player.health = health
            if health <= 0:
                player.state = PlayerState.DEAD
        if score is not None:
            player.score = score

    def record_event(self, event: GameEvent):
        """记录事件"""
        self.event_history.append(event)
        if len(self.event_history) > self.max_history:
            self.event_history = self.event_history[-self.max_history:]

    def get_game_snapshot(self) -> Dict[str, Any]:
        """获取游戏快照"""
        return {
            "state": self.state.value,
            "game_time": self.game_time,
            "tick": self.tick,
            "player_count": len(self.players),
            "players": [
                {
                    "id": p.id,
                    "name": p.name,
                    "state": p.state.value,
                    "position": p.position,
                    "health": p.health,
                    "score": p.score,
                    "team": p.team,
                    "is_local": p.is_local
                }
                for p in self.players.values()
            ],
            "game_data": self.game_data
        }


class InputManager:
    """输入管理器"""

    def __init__(self):
        self.key_states: Dict[str, bool] = {}
        self.mouse_position: Dict[str, float] = {"x": 0, "y": 0}
        self.mouse_buttons: Dict[int, bool] = {}
        self.gamepad_states: Dict[int, Dict[str, float]] = {}
        self.action_bindings: Dict[str, str] = {}
        self._input_callbacks: List[Callable] = []

    def bind_action(self, action: str, key: str):
        """绑定动作到按键"""
        self.action_bindings[action] = key

    def update_key_state(self, key: str, pressed: bool):
        """更新按键状态"""
        self.key_states[key] = pressed
        self._notify_input(key, pressed)

    def update_mouse_position(self, x: float, y: float):
        """更新鼠标位置"""
        self.mouse_position = {"x": x, "y": y}

    def update_mouse_button(self, button: int, pressed: bool):
        """更新鼠标按钮"""
        self.mouse_buttons[button] = pressed
        self._notify_input(f"mouse_{button}", pressed)

    def get_action_state(self, action: str) -> bool:
        """获取动作状态"""
        key = self.action_bindings.get(action)
        if key:
            return self.key_states.get(key, False)
        return False

    def is_key_pressed(self, key: str) -> bool:
        """检查按键是否按下"""
        return self.key_states.get(key, False)

    def get_mouse_position(self) -> Dict[str, float]:
        """获取鼠标位置"""
        return self.mouse_position.copy()

    def add_input_callback(self, callback: Callable):
        """添加输入回调"""
        self._input_callbacks.append(callback)

    def _notify_input(self, input_name: str, pressed: bool):
        """通知输入更新"""
        for callback in self._input_callbacks:
            try:
                callback(input_name, pressed)
            except Exception as e:
                print(f"Input callback error: {e}")


class NetworkSync:
    """网络同步"""

    def __init__(self):
        self.sync_mode = "delta"  # full, delta, input
        self.update_rate = 20  # 每秒更新次数
        self.interpolation_time = 0.1  # 插值时间
        self.client_predictions: Dict[str, Dict] = {}
        self.server_states: List[Dict] = []
        self.max_server_states = 60

    def create_update_packet(
        self,
        player_id: str,
        state: Dict[str, Any],
        tick: int
    ) -> bytes:
        """创建更新包"""
        data = {
            "player_id": player_id,
            "state": state,
            "tick": tick,
            "timestamp": datetime.now().timestamp()
        }
        return json.dumps(data).encode('utf-8')

    def parse_update_packet(self, packet: bytes) -> Optional[Dict]:
        """解析更新包"""
        try:
            return json.loads(packet.decode('utf-8'))
        except Exception:
            return None

    def predict_player_state(
        self,
        player_id: str,
        current_state: Dict[str, Any],
        input_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """预测玩家状态（客户端预测）"""
        # 简化实现：直接返回当前状态
        # 实际实现需要运行物理模拟
        return current_state

    def interpolate_state(
        self,
        from_state: Dict[str, Any],
        to_state: Dict[str, Any],
        alpha: float
    ) -> Dict[str, Any]:
        """插值状态"""
        result = {}
        for key in from_state.keys():
            if key in to_state:
                if isinstance(from_state[key], (int, float)):
                    result[key] = from_state[key] + (to_state[key] - from_state[key]) * alpha
                else:
                    result[key] = to_state[key]
        return result

    def add_server_state(self, state: Dict):
        """添加服务器状态"""
        self.server_states.append(state)
        if len(self.server_states) > self.max_server_states:
            self.server_states.pop(0)

    def reconcile(
        self,
        player_id: str,
        predicted_state: Dict[str, Any],
        server_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """协调预测和服务器状态"""
        # 简化实现：使用服务器状态
        # 实际实现需要检测并修正错误预测
        return server_state.get("state", predicted_state)


class AudioManager:
    """音频管理器"""

    def __init__(self):
        self.music_volume = 0.6
        self.effects_volume = 0.8
        self.voice_volume = 1.0
        self.muted = False
        self.music_playing: Optional[str] = None
        self.effects_playing: List[str] = []
        self.audio_sources: Dict[str, Any] = {}

    def set_music_volume(self, volume: float):
        """设置音乐音量"""
        self.music_volume = max(0.0, min(1.0, volume))

    def set_effects_volume(self, volume: float):
        """设置音效音量"""
        self.effects_volume = max(0.0, min(1.0, volume))

    def set_voice_volume(self, volume: float):
        """设置语音音量"""
        self.voice_volume = max(0.0, min(1.0, volume))

    def toggle_mute(self):
        """切换静音"""
        self.muted = not self.muted

    async def play_music(self, resource_id: str, loop: bool = True):
        """播放音乐"""
        self.music_playing = resource_id
        # 实际实现需要调用音频播放API

    def stop_music(self):
        """停止音乐"""
        self.music_playing = None

    async def play_effect(self, resource_id: str):
        """播放音效"""
        if resource_id not in self.effects_playing:
            self.effects_playing.append(resource_id)
        # 实际实现需要调用音频播放API

    def stop_effect(self, resource_id: str):
        """停止音效"""
        if resource_id in self.effects_playing:
            self.effects_playing.remove(resource_id)

    def stop_all(self):
        """停止所有音频"""
        self.music_playing = None
        self.effects_playing.clear()


class GameClient:
    """游戏客户端核心"""

    def __init__(self):
        self.game_id: Optional[str] = None
        self.state_manager = GameStateManager()
        self.resource_loader = ResourceLoader()
        self.input_manager = InputManager()
        self.network_sync = NetworkSync()
        self.audio_manager = AudioManager()
        self.settings = GameSettings()
        
        self._running = False
        self._update_task: Optional[asyncio.Task] = None
        self._network_task: Optional[asyncio.Task] = None
        self._event_callbacks: Dict[str, List[Callable]] = {}

    async def start(self, game_id: str):
        """启动游戏"""
        self.game_id = game_id
        self.state_manager.set_state(GameState.LOADING)
        self._running = True
        
        # 启动更新循环
        self._update_task = asyncio.create_task(self._update_loop())
        self._network_task = asyncio.create_task(self._network_loop())

    async def stop(self):
        """停止游戏"""
        self._running = False
        
        if self._update_task:
            self._update_task.cancel()
        if self._network_task:
            self._network_task.cancel()
        
        self.state_manager.set_state(GameState.IDLE)

    async def load_game(
        self,
        config: GameConfig,
        resources: List[GameResource],
        progress_callback: Optional[Callable[[float, str], None]] = None
    ):
        """加载游戏"""
        self.state_manager.game_config = config
        
        # 添加玩家
        for i in range(config.min_players):
            player_id = str(uuid.uuid4())[:8]
            player = GamePlayer(
                id=player_id,
                name=f"Player {i + 1}",
                is_local=(i == 0)
            )
            self.state_manager.add_player(player)

        # 加载资源
        await self.resource_loader.load_resources_batch(resources, progress_callback)
        
        self.state_manager.set_state(GameState.RUNNING)

    async def pause(self):
        """暂停游戏"""
        if self.state_manager.state == GameState.RUNNING:
            self.state_manager.set_state(GameState.PAUSED)
            self.audio_manager.set_music_volume(0.3)  # 降低音乐音量

    async def resume(self):
        """继续游戏"""
        if self.state_manager.state == GameState.PAUSED:
            self.state_manager.set_state(GameState.RUNNING)
            self.audio_manager.set_music_volume(self.settings.music_volume)

    async def end_game(self, reason: str = ""):
        """结束游戏"""
        self.state_manager.set_state(GameState.GAME_OVER)
        self.state_manager.record_event(GameEvent(
            type="game_over",
            data={"reason": reason}
        ))

    def apply_settings(self, settings: GameSettings):
        """应用设置"""
        self.settings = settings
        self.audio_manager.set_music_volume(settings.music_volume)
        self.audio_manager.set_effects_volume(settings.audio_volume)

    async def _update_loop(self):
        """更新循环"""
        target_fps = 60
        frame_time = 1.0 / target_fps

        while self._running:
            if self.state_manager.state == GameState.RUNNING:
                # 更新游戏时间
                self.state_manager.game_time += frame_time
                self.state_manager.tick += 1

                # 处理输入
                await self._process_input()

                # 更新玩家
                await self._update_players()

                # 检查游戏结束条件
                await self._check_game_over()

            await asyncio.sleep(frame_time)

    async def _network_loop(self):
        """网络同步循环"""
        while self._running:
            if self.state_manager.state == GameState.RUNNING:
                # 同步玩家状态
                await self._sync_players()

            await asyncio.sleep(1.0 / self.network_sync.update_rate)

    async def _process_input(self):
        """处理输入"""
        local_player = self.state_manager.get_local_player()
        if not local_player:
            return

        # 处理移动输入
        move_x = 0.0
        move_y = 0.0

        if self.input_manager.get_action_state("move_forward"):
            move_y = 1.0
        if self.input_manager.get_action_state("move_backward"):
            move_y = -1.0
        if self.input_manager.get_action_state("move_left"):
            move_x = -1.0
        if self.input_manager.get_action_state("move_right"):
            move_x = 1.0

        if move_x != 0 or move_y != 0:
            # 简化实现：直接更新位置
            # 实际实现需要应用速度和时间
            local_player.position["x"] += move_x * 0.1
            local_player.position["y"] += move_y * 0.1

        # 处理跳跃
        if self.input_manager.get_action_state("jump"):
            local_player.position["z"] += 0.5

    async def _update_players(self):
        """更新玩家"""
        for player in self.state_manager.players.values():
            if not player.is_local and player.state == PlayerState.ALIVE:
                # 插值其他玩家位置
                pass

    async def _sync_players(self):
        """同步玩家"""
        local_player = self.state_manager.get_local_player()
        if not local_player:
            return

        # 创建并发送更新包
        state = {
            "position": local_player.position,
            "rotation": local_player.rotation,
            "health": local_player.health,
            "score": local_player.score,
            "input_state": local_player.input_state
        }

        packet = self.network_sync.create_update_packet(
            local_player.id,
            state,
            self.state_manager.tick
        )

        # 实际实现需要发送数据包
        # await self.send_packet(packet)

    async def _check_game_over(self):
        """检查游戏结束"""
        config = self.state_manager.game_config
        if not config:
            return

        # 检查时间限制
        if config.time_limit and self.state_manager.game_time >= config.time_limit:
            await self.end_game("Time limit reached")

        # 检查分数限制
        if config.score_limit:
            for player in self.state_manager.players.values():
                if player.score >= config.score_limit:
                    await self.end_game(f"{player.name} reached score limit")

        # 检查玩家数量
        alive_players = [p for p in self.state_manager.players.values() 
                        if p.state == PlayerState.ALIVE]
        if config.game_type == GameType.COMPETITIVE:
            if len(alive_players) <= 1:
                if alive_players:
                    await self.end_game(f"{alive_players[0].name} wins!")

    def add_event_callback(self, event: str, callback: Callable):
        """添加事件回调"""
        if event not in self._event_callbacks:
            self._event_callbacks[event] = []
        self._event_callbacks[event].append(callback)

    def get_client_stats(self) -> Dict[str, Any]:
        """获取客户端统计"""
        return {
            "game_id": self.game_id,
            "state": self.state_manager.state.value,
            "game_time": self.state_manager.game_time,
            "tick": self.state_manager.tick,
            "player_count": len(self.state_manager.players),
            "loaded_resources": len(self.resource_loader.loaded_resources),
            "fps": 60,  # 简化实现
            "latency": 0  # 简化实现
        }


# 便捷函数
def create_game_config(
    name: str,
    game_type: GameType = GameType.SINGLE_PLAYER,
    max_players: int = 1
) -> GameConfig:
    """创建游戏配置"""
    return GameConfig(
        id=str(uuid.uuid4())[:8],
        name=name,
        game_type=game_type,
        max_players=max_players,
        min_players=1
    )


def create_game_player(name: str, is_local: bool = False) -> GamePlayer:
    """创建游戏玩家"""
    return GamePlayer(
        id=str(uuid.uuid4())[:8],
        name=name,
        is_local=is_local
    )
