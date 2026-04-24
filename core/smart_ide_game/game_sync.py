"""
游戏同步模块
提供实时多人游戏同步、状态同步、输入同步等功能
"""
import asyncio
import json
import hashlib
import struct
import uuid
from typing import Dict, List, Optional, Any, Callable, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import random
from core.logger import get_logger
logger = get_logger('smart_ide_game.game_sync')



class SyncMode(Enum):
    """同步模式"""
    FULL_STATE = "full_state"       # 全量状态同步
    DELTA_STATE = "delta_state"     # 增量状态同步
    INPUT_SYNC = "input_sync"       # 输入同步
    AUTHORITATIVE = "authoritative" # 服务器权威模式
    P2P_SYNC = "p2p_sync"           # P2P同步


class SyncPriority(Enum):
    """同步优先级"""
    CRITICAL = 0   # 最高优先级
    HIGH = 1       # 高优先级
    NORMAL = 2    # 普通优先级
    LOW = 3       # 低优先级


@dataclass
class GameState:
    """游戏状态"""
    tick: int
    timestamp: float
    players: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    entities: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    events: List[Dict] = field(default_factory=list)
    checksum: Optional[str] = None


@dataclass
class InputState:
    """输入状态"""
    player_id: str
    tick: int
    timestamp: float
    keys: Dict[str, bool] = field(default_factory=dict)
    mouse: Dict[str, float] = field(default_factory=dict)
    actions: List[str] = field(default_factory=list)


@dataclass
class SyncPacket:
    """同步数据包"""
    packet_type: str  # state, input, event, ack
    sequence: int
    tick: int
    priority: SyncPriority
    payload: bytes
    timestamp: float = field(default_factory=datetime.now().timestamp)
    sender_id: str = ""


@dataclass
class PlayerSnapshot:
    """玩家快照"""
    player_id: str
    position: Dict[str, float]
    rotation: Dict[str, float]
    velocity: Dict[str, float]
    health: float
    state: str
    tick: int
    timestamp: float


class StateInterpolator:
    """状态插值器"""

    def __init__(self, interpolation_delay: float = 0.1):
        self.interpolation_delay = interpolation_delay
        self.snapshots: Dict[str, List[PlayerSnapshot]] = {}
        self.max_snapshots = 60

    def add_snapshot(self, snapshot: PlayerSnapshot):
        """添加快照"""
        player_id = snapshot.player_id
        if player_id not in self.snapshots:
            self.snapshots[player_id] = []

        self.snapshots[player_id].append(snapshot)

        # 限制快照数量
        if len(self.snapshots[player_id]) > self.max_snapshots:
            self.snapshots[player_id].pop(0)

    def get_interpolated_state(
        self,
        player_id: str,
        current_time: float
    ) -> Optional[PlayerSnapshot]:
        """获取插值后的状态"""
        if player_id not in self.snapshots:
            return None

        snapshots = self.snapshots[player_id]
        if not snapshots:
            return None

        # 目标时间（考虑插值延迟）
        target_time = current_time - self.interpolation_delay

        # 找到最近的快照
        best_before = None
        best_after = None

        for snapshot in snapshots:
            if snapshot.timestamp <= target_time:
                if best_before is None or snapshot.timestamp > best_before.timestamp:
                    best_before = snapshot
            else:
                if best_after is None or snapshot.timestamp < best_after.timestamp:
                    best_after = snapshot

        # 如果没有之前的快照，返回最早的
        if best_before is None and snapshots:
            return snapshots[0]

        # 如果没有之后的快照，返回最后的
        if best_after is None:
            return best_before

        # 如果时间相同，返回一个
        if best_before.timestamp == best_after.timestamp:
            return best_before

        # 线性插值
        alpha = (target_time - best_before.timestamp) / (best_after.timestamp - best_before.timestamp)
        return self._interpolate(best_before, best_after, alpha)

    def _interpolate(
        self,
        before: PlayerSnapshot,
        after: PlayerSnapshot,
        alpha: float
    ) -> PlayerSnapshot:
        """执行插值"""
        def lerp(a: float, b: float, t: float) -> float:
            return a + (b - a) * t

        return PlayerSnapshot(
            player_id=before.player_id,
            position={
                k: lerp(before.position.get(k, 0), after.position.get(k, 0), alpha)
                for k in set(before.position.keys()) | set(after.position.keys())
            },
            rotation={
                k: lerp(before.rotation.get(k, 0), after.rotation.get(k, 0), alpha)
                for k in set(before.rotation.keys()) | set(after.rotation.keys())
            },
            velocity={
                k: lerp(before.velocity.get(k, 0), after.velocity.get(k, 0), alpha)
                for k in set(before.velocity.keys()) | set(after.velocity.keys())
            },
            health=lerp(before.health, after.health, alpha),
            state=after.state,
            tick=after.tick,
            timestamp=lerp(before.timestamp, after.timestamp, alpha)
        )


class ClientPredictor:
    """客户端预测器"""

    def __init__(self):
        self.predictions: Dict[str, Dict[str, Any]] = {}
        self.pending_inputs: Dict[str, List[InputState]] = {}
        self.server_acknowledged: Dict[str, int] = {}  # player_id -> acknowledged tick

    def add_prediction(
        self,
        player_id: str,
        tick: int,
        input_state: InputState,
        predicted_state: Dict[str, Any]
    ):
        """添加预测"""
        if player_id not in self.predictions:
            self.predictions[player_id] = {}
            self.pending_inputs[player_id] = []

        self.predictions[player_id][tick] = predicted_state
        self.pending_inputs[player_id].append(input_state)

    def acknowledge_server_state(
        self,
        player_id: str,
        server_tick: int,
        server_state: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """确认服务器状态并修正"""
        if player_id not in self.predictions:
            return None

        # 找到需要修正的第一个预测
        corrections = []
        for tick in sorted(self.predictions[player_id].keys()):
            if tick > server_tick:
                corrections.append((tick, self.predictions[player_id][tick]))
            else:
                # 移除已确认的预测
                if tick in self.predictions[player_id]:
                    del self.predictions[player_id][tick]

        self.server_acknowledged[player_id] = server_tick

        # 如果有需要修正的预测，应用服务器状态
        if corrections:
            return server_state

        return None

    def has_pending_predictions(self, player_id: str) -> bool:
        """检查是否有待确认的预测"""
        return len(self.predictions.get(player_id, {})) > 3  # 超过3个未确认则可能有延迟问题


class GameSync:
    """游戏同步核心"""

    def __init__(self):
        self.sync_mode = SyncMode.DELTA_STATE
        self.update_rate = 20  # 每秒更新次数
        self.tick_rate = 60    # 每秒tick数
        
        self.game_state = GameState(tick=0, timestamp=0)
        self.input_states: Dict[str, InputState] = {}
        self.interpolator = StateInterpolator()
        self.predictor = ClientPredictor()
        
        self.connected_peers: Set[str] = set()
        self.peer_states: Dict[str, GameState] = {}
        
        self._running = False
        self._send_queue: asyncio.Queue = asyncio.Queue()
        self._receive_queue: asyncio.Queue = asyncio.Queue()
        self._event_callbacks: Dict[str, List[Callable]] = {}

    async def start(self, room_id: str):
        """启动同步"""
        self._running = True
        self.game_state = GameState(tick=0, timestamp=datetime.now().timestamp())

    async def stop(self):
        """停止同步"""
        self._running = False

    def set_sync_mode(self, mode: SyncMode):
        """设置同步模式"""
        self.sync_mode = mode

    def set_update_rate(self, rate: int):
        """设置更新率"""
        self.update_rate = rate

    def connect_peer(self, peer_id: str):
        """连接对等节点"""
        self.connected_peers.add(peer_id)

    def disconnect_peer(self, peer_id: str):
        """断开对等节点"""
        self.connected_peers.discard(peer_id)
        if peer_id in self.peer_states:
            del self.peer_states[peer_id]

    def update_local_player(
        self,
        player_id: str,
        position: Dict[str, float],
        rotation: Dict[str, float],
        velocity: Dict[str, float],
        health: float,
        state: str
    ):
        """更新本地玩家状态"""
        if player_id not in self.game_state.players:
            self.game_state.players[player_id] = {}

        self.game_state.players[player_id] = {
            "position": position,
            "rotation": rotation,
            "velocity": velocity,
            "health": health,
            "state": state,
            "tick": self.game_state.tick,
            "timestamp": datetime.now().timestamp()
        }

        # 添加插值快照
        snapshot = PlayerSnapshot(
            player_id=player_id,
            position=position,
            rotation=rotation,
            velocity=velocity,
            health=health,
            state=state,
            tick=self.game_state.tick,
            timestamp=datetime.now().timestamp()
        )
        self.interpolator.add_snapshot(snapshot)

    def record_input(self, player_id: str, input_state: InputState):
        """记录输入"""
        self.input_states[player_id] = input_state

    async def send_state_update(self) -> Optional[bytes]:
        """发送状态更新"""
        self.game_state.tick += 1
        self.game_state.timestamp = datetime.now().timestamp()

        # 计算校验和
        state_json = json.dumps(self.game_state.players, sort_keys=True)
        self.game_state.checksum = hashlib.md5(state_json.encode()).hexdigest()[:8]

        # 序列化
        payload = json.dumps({
            "tick": self.game_state.tick,
            "timestamp": self.game_state.timestamp,
            "players": self.game_state.players,
            "checksum": self.game_state.checksum
        }).encode('utf-8')

        packet = SyncPacket(
            packet_type="state",
            sequence=self.game_state.tick,
            tick=self.game_state.tick,
            priority=SyncPriority.NORMAL,
            payload=payload
        )

        return self._serialize_packet(packet)

    def receive_state_update(self, data: bytes, peer_id: str):
        """接收状态更新"""
        try:
            packet = self._deserialize_packet(data)
            if not packet:
                return

            # 更新对等节点状态
            state_data = json.loads(packet.payload.decode('utf-8'))
            
            if peer_id not in self.peer_states:
                self.peer_states[peer_id] = GameState(tick=0, timestamp=0)

            self.peer_states[peer_id].tick = state_data["tick"]
            self.peer_states[peer_id].timestamp = state_data["timestamp"]
            self.peer_states[peer_id].players = state_data.get("players", {})

            # 添加插值快照
            for player_id, player_state in state_data.get("players", {}).items():
                snapshot = PlayerSnapshot(
                    player_id=player_id,
                    position=player_state.get("position", {}),
                    rotation=player_state.get("rotation", {}),
                    velocity=player_state.get("velocity", {}),
                    health=player_state.get("health", 0),
                    state=player_state.get("state", ""),
                    tick=state_data["tick"],
                    timestamp=state_data["timestamp"]
                )
                self.interpolator.add_snapshot(snapshot)

            # 确认服务器状态
            if self.predictor.has_pending_predictions(player_id):
                self.predictor.acknowledge_server_state(
                    player_id,
                    state_data["tick"],
                    player_state
                )

            self._emit_event("state_update", {
                "peer_id": peer_id,
                "tick": state_data["tick"]
            })

        except Exception as e:
            logger.info(f"Failed to receive state update: {e}")

    def get_interpolated_player_state(
        self,
        player_id: str,
        current_time: Optional[float] = None
    ) -> Optional[PlayerSnapshot]:
        """获取插值后的玩家状态"""
        if current_time is None:
            current_time = datetime.now().timestamp()

        return self.interpolator.get_interpolated_state(player_id, current_time)

    def create_input_packet(
        self,
        player_id: str,
        input_state: InputState
    ) -> bytes:
        """创建输入数据包"""
        payload = json.dumps({
            "player_id": player_id,
            "tick": input_state.tick,
            "timestamp": input_state.timestamp,
            "keys": input_state.keys,
            "mouse": input_state.mouse,
            "actions": input_state.actions
        }).encode('utf-8')

        packet = SyncPacket(
            packet_type="input",
            sequence=input_state.tick,
            tick=input_state.tick,
            priority=SyncPriority.HIGH,
            payload=payload,
            sender_id=player_id
        )

        return self._serialize_packet(packet)

    def receive_input_packet(self, data: bytes):
        """接收输入数据包"""
        try:
            packet = self._deserialize_packet(data)
            if not packet or packet.packet_type != "input":
                return

            input_data = json.loads(packet.payload.decode('utf-8'))
            
            input_state = InputState(
                player_id=input_data["player_id"],
                tick=input_data["tick"],
                timestamp=input_data["timestamp"],
                keys=input_data.get("keys", {}),
                mouse=input_data.get("mouse", {}),
                actions=input_data.get("actions", [])
            )

            self.input_states[input_state.player_id] = input_state

            self._emit_event("input_received", {
                "player_id": input_state.player_id,
                "tick": input_state.tick
            })

        except Exception as e:
            logger.info(f"Failed to receive input packet: {e}")

    def create_event_packet(
        self,
        event_type: str,
        event_data: Dict[str, Any],
        priority: SyncPriority = SyncPriority.NORMAL
    ) -> bytes:
        """创建事件数据包"""
        payload = json.dumps({
            "type": event_type,
            "data": event_data,
            "timestamp": datetime.now().timestamp()
        }).encode('utf-8')

        packet = SyncPacket(
            packet_type="event",
            sequence=self.game_state.tick,
            tick=self.game_state.tick,
            priority=priority,
            payload=payload
        )

        return self._serialize_packet(packet)

    def receive_event_packet(self, data: bytes):
        """接收事件数据包"""
        try:
            packet = self._deserialize_packet(data)
            if not packet or packet.packet_type != "event":
                return

            event_data = json.loads(packet.payload.decode('utf-8'))
            
            self._emit_event(event_data["type"], event_data["data"])

        except Exception as e:
            logger.info(f"Failed to receive event packet: {e}")

    def _serialize_packet(self, packet: SyncPacket) -> bytes:
        """序列化数据包"""
        header = struct.pack(
            "!BBHIf",
            ord(packet.packet_type[0]),
            packet.priority.value,
            packet.sequence,
            packet.tick,
            packet.timestamp
        )
        
        payload_length = len(packet.payload)
        length_prefix = struct.pack("!H", payload_length)
        
        return header + length_prefix + packet.payload

    def _deserialize_packet(self, data: bytes) -> Optional[SyncPacket]:
        """反序列化数据包"""
        try:
            if len(data) < 14:
                return None

            # 解析头部
            header = struct.unpack("!BBHIf", data[:14])
            
            packet_type_map = {
                's': "state",
                'i': "input",
                'e': "event",
                'a': "ack"
            }
            
            packet_type = packet_type_map.get(
                chr(header[0]),
                "unknown"
            )
            priority = SyncPriority(header[1])
            sequence = header[2]
            tick = header[3]
            timestamp = header[4]

            # 解析载荷
            length = struct.unpack("!H", data[14:16])[0]
            payload = data[16:16 + length]

            return SyncPacket(
                packet_type=packet_type,
                sequence=sequence,
                tick=tick,
                priority=priority,
                payload=payload,
                timestamp=timestamp
            )

        except Exception as e:
            logger.info(f"Failed to deserialize packet: {e}")
            return None

    def add_event_callback(self, event: str, callback: Callable):
        """添加事件回调"""
        if event not in self._event_callbacks:
            self._event_callbacks[event] = []
        self._event_callbacks[event].append(callback)

    def _emit_event(self, event: str, data: Dict[str, Any]):
        """触发事件"""
        if event in self._event_callbacks:
            for callback in self._event_callbacks[event]:
                try:
                    callback(event, data)
                except Exception as e:
                    logger.info(f"Event callback error: {e}")

    def get_sync_stats(self) -> Dict[str, Any]:
        """获取同步统计"""
        return {
            "sync_mode": self.sync_mode.value,
            "update_rate": self.update_rate,
            "tick_rate": self.tick_rate,
            "current_tick": self.game_state.tick,
            "connected_peers": len(self.connected_peers),
            "interpolated_players": len(self.interpolator.snapshots),
            "pending_predictions": sum(
                len(preds) for preds in self.predictor.predictions.values()
            )
        }


class NetworkQualityMonitor:
    """网络质量监控"""

    def __init__(self):
        self.ping_history: Dict[str, List[int]] = {}
        self.packet_loss_history: Dict[str, List[float]] = {}
        self.jitter_history: Dict[str, List[float]] = {}
        self.history_size = 60  # 保存60秒历史

    def record_ping(self, peer_id: str, ping_ms: int):
        """记录延迟"""
        if peer_id not in self.ping_history:
            self.ping_history[peer_id] = []

        self.ping_history[peer_id].append(ping_ms)
        if len(self.ping_history[peer_id]) > self.history_size:
            self.ping_history[peer_id].pop(0)

    def record_packet_loss(self, peer_id: str, loss_rate: float):
        """记录丢包率"""
        if peer_id not in self.packet_loss_history:
            self.packet_loss_history[peer_id] = []

        self.packet_loss_history[peer_id].append(loss_rate)
        if len(self.packet_loss_history[peer_id]) > self.history_size:
            self.packet_loss_history[peer_id].pop(0)

    def record_jitter(self, peer_id: str, jitter_ms: float):
        """记录抖动"""
        if peer_id not in self.jitter_history:
            self.jitter_history[peer_id] = []

        self.jitter_history[peer_id].append(jitter_ms)
        if len(self.jitter_history[peer_id]) > self.history_size:
            self.jitter_history[peer_id].pop(0)

    def get_quality_score(self, peer_id: str) -> float:
        """获取质量分数 (0-1)"""
        score = 1.0

        # 延迟评分
        if peer_id in self.ping_history and self.ping_history[peer_id]:
            avg_ping = sum(self.ping_history[peer_id]) / len(self.ping_history[peer_id])
            if avg_ping > 500:
                score *= 0.2
            elif avg_ping > 200:
                score *= 0.5
            elif avg_ping > 100:
                score *= 0.8

        # 丢包评分
        if peer_id in self.packet_loss_history and self.packet_loss_history[peer_id]:
            avg_loss = sum(self.packet_loss_history[peer_id]) / len(self.packet_loss_history[peer_id])
            score *= (1.0 - avg_loss)

        # 抖动评分
        if peer_id in self.jitter_history and self.jitter_history[peer_id]:
            avg_jitter = sum(self.jitter_history[peer_id]) / len(self.jitter_history[peer_id])
            if avg_jitter > 50:
                score *= 0.5
            elif avg_jitter > 20:
                score *= 0.8

        return max(0.0, min(1.0, score))

    def get_peer_stats(self, peer_id: str) -> Dict[str, Any]:
        """获取对等节点统计"""
        return {
            "peer_id": peer_id,
            "avg_ping": sum(self.ping_history.get(peer_id, [0])) / max(len(self.ping_history.get(peer_id, [])), 1),
            "min_ping": min(self.ping_history.get(peer_id, [0])) if self.ping_history.get(peer_id) else 0,
            "max_ping": max(self.ping_history.get(peer_id, [0])) if self.ping_history.get(peer_id) else 0,
            "packet_loss": sum(self.packet_loss_history.get(peer_id, [0])) / max(len(self.packet_loss_history.get(peer_id, [])), 1),
            "avg_jitter": sum(self.jitter_history.get(peer_id, [0])) / max(len(self.jitter_history.get(peer_id, [])), 1),
            "quality_score": self.get_quality_score(peer_id)
        }


# 便捷函数
def create_input_state(
    player_id: str,
    tick: int,
    keys: Dict[str, bool] = None,
    mouse: Dict[str, float] = None
) -> InputState:
    """创建输入状态"""
    return InputState(
        player_id=player_id,
        tick=tick,
        timestamp=datetime.now().timestamp(),
        keys=keys or {},
        mouse=mouse or {"x": 0, "y": 0},
        actions=[]
    )


def create_game_state(tick: int = 0) -> GameState:
    """创建游戏状态"""
    return GameState(
        tick=tick,
        timestamp=datetime.now().timestamp()
    )
