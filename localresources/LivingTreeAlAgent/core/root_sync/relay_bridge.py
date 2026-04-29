"""
中继桥接 - Relay Bridge

Syncthing Relay 协议实现：
- WebSocket 中继连接
- PING/PONG 心跳
- 隧道建立
- 数据透传
"""

import asyncio
import json
import struct
import time
import hashlib
import secrets
from typing import Dict, List, Optional, Callable, Tuple
from dataclasses import dataclass, field
from enum import IntEnum

from .models import MessageType


class RelayMessageType(IntEnum):
    """中继消息类型"""
    PING = 1
    PONG = 2
    CONNECT = 3
    CONNECTED = 4
    DISCONNECT = 5
    RELAY = 10
    RELAY_REPLY = 11
    ERROR = 255


@dataclass
class RelayConfig:
    """中继配置"""
    url: str
    device_id: str
    token: Optional[str] = None

    # 连接参数
    read_timeout: int = 30
    write_timeout: int = 30
    ping_interval: int = 15


@dataclass
class RelaySession:
    """中继会话"""
    session_id: str
    remote_device_id: str
    started_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    bytes_sent: int = 0
    bytes_received: int = 0


class RelayBridge:
    """
    中继桥接器

    通过中继服务器建立设备间的直接连接：
    1. 连接到中继服务器
    2. 加入会话
    3. 建立 P2P 隧道
    4. 透传 BEP 数据
    """

    def __init__(self, config: RelayConfig):
        self.config = config
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None

        # 会话
        self._session: Optional[RelaySession] = None
        self._remote_session_id: Optional[str] = None

        # 状态
        self._connected = False
        self._authenticated = False

        # 回调
        self._on_data: Optional[Callable] = None
        self._on_disconnect: Optional[Callable] = None
        self._on_session_established: Optional[Callable] = None

        # 心跳
        self._ping_task: Optional[asyncio.Task] = None

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def is_authenticated(self) -> bool:
        return self._authenticated

    async def connect(self, remote_device_id: str) -> bool:
        """
        连接到中继服务器

        Args:
            remote_device_id: 目标设备ID

        Returns:
            是否连接成功
        """
        try:
            # 解析 URL
            import urllib.parse
            parsed = urllib.parse.urlparse(self.config.url)

            host = parsed.hostname or "localhost"
            port = parsed.port or 22067

            # 连接
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=self.config.read_timeout
            )

            self._connected = True

            # 发送 CONNECT
            if not await self._send_connect(remote_device_id):
                await self.disconnect()
                return False

            # 等待连接确认
            if not await self._wait_connected():
                await self.disconnect()
                return False

            # 启动心跳
            self._ping_task = asyncio.create_task(self._ping_loop())

            return True

        except Exception:
            self._connected = False
            return False

    async def _send_connect(self, remote_device_id: str) -> bool:
        """发送 CONNECT 消息"""
        try:
            msg = {
                "type": RelayMessageType.CONNECT,
                "device_id": self.config.device_id,
                "remote_device_id": remote_device_id,
                "relay_session_id": secrets.token_hex(16),
            }

            if self.config.token:
                msg["token"] = self.config.token

            data = json.dumps(msg).encode()
            self._writer.write(struct.pack(">I", len(data)) + data)
            await self._writer.drain()

            return True

        except Exception:
            return False

    async def _wait_connected(self) -> bool:
        """等待连接确认"""
        try:
            # 读取响应头
            header = await asyncio.wait_for(
                self._reader.readexactly(4),
                timeout=self.config.read_timeout
            )

            length = struct.unpack(">I", header)[0]

            # 读取响应数据
            data = await asyncio.wait_for(
                self._reader.readexactly(length),
                timeout=self.config.read_timeout
            )

            msg = json.loads(data.decode())

            if msg.get("type") == RelayMessageType.CONNECTED:
                self._session = RelaySession(
                    session_id=msg.get("relay_session_id", ""),
                    remote_device_id=msg.get("remote_device_id", ""),
                )
                self._remote_session_id = msg.get("remote_session_id")
                self._authenticated = True
                return True

            elif msg.get("type") == RelayMessageType.ERROR:
                return False

        except Exception:
            pass

        return False

    async def relay_data(self, data: bytes) -> bool:
        """
        通过中继发送数据

        Args:
            data: BEP 协议数据

        Returns:
            是否发送成功
        """
        if not self._connected or not self._session:
            return False

        try:
            # 包装为 RELAY 消息
            msg = {
                "type": RelayMessageType.RELAY,
                "session_id": self._session.session_id,
                "data": data.hex(),
            }

            encoded = json.dumps(msg).encode()
            self._writer.write(struct.pack(">I", len(encoded)) + encoded)
            await self._writer.drain()

            self._session.bytes_sent += len(data)
            self._session.last_activity = time.time()

            return True

        except Exception:
            return False

    async def _receive_loop(self):
        """接收数据循环"""
        while self._connected:
            try:
                # 读取消息头
                header = await asyncio.wait_for(
                    self._reader.readexactly(4),
                    timeout=self.config.read_timeout
                )

                length = struct.unpack(">I", header)[0]

                # 读取消息
                data = await asyncio.wait_for(
                    self._reader.readexactly(length),
                    timeout=self.config.read_timeout
                )

                msg = json.loads(data.decode())
                msg_type = RelayMessageType(msg.get("type", 0))

                if msg_type == RelayMessageType.RELAY:
                    # 透传 BEP 数据
                    bep_data = bytes.fromhex(msg.get("data", ""))
                    if bep_data and self._on_data:
                        self._session.bytes_received += len(bep_data)
                        await self._on_data(bep_data)

                elif msg_type == RelayMessageType.PING:
                    await self._send_pong()

                elif msg_type == RelayMessageType.PONG:
                    pass  # 心跳响应

                elif msg_type == RelayMessageType.DISCONNECT:
                    break

                elif msg_type == RelayMessageType.ERROR:
                    break

            except asyncio.TimeoutError:
                continue
            except Exception:
                break

        await self.disconnect()

    async def _send_pong(self):
        """发送 PONG"""
        try:
            msg = {"type": RelayMessageType.PONG}
            data = json.dumps(msg).encode()
            self._writer.write(struct.pack(">I", len(data)) + data)
            await self._writer.drain()
        except Exception:
            pass

    async def _ping_loop(self):
        """心跳循环"""
        while self._connected:
            try:
                await asyncio.sleep(self.config.ping_interval)

                if self._connected:
                    msg = {"type": RelayMessageType.PING}
                    data = json.dumps(msg).encode()
                    self._writer.write(struct.pack(">I", len(data)) + data)
                    await self._writer.drain()

            except Exception:
                break

    async def disconnect(self):
        """断开连接"""
        if not self._connected:
            return

        self._connected = False
        self._authenticated = False

        # 停止心跳
        if self._ping_task:
            self._ping_task.cancel()
            self._ping_task = None

        # 发送断开消息
        if self._writer:
            try:
                msg = {"type": RelayMessageType.DISCONNECT}
                data = json.dumps(msg).encode()
                self._writer.write(struct.pack(">I", len(data)) + data)
                await self._writer.drain()
            except Exception:
                pass

            self._writer.close()
            try:
                await self._writer.wait_closed()
            except Exception:
                pass

        self._reader = None
        self._writer = None
        self._session = None

        if self._on_disconnect:
            await self._on_disconnect()

    def set_callbacks(self,
                     on_data: Optional[Callable] = None,
                     on_disconnect: Optional[Callable] = None,
                     on_session_established: Optional[Callable] = None):
        """设置回调"""
        self._on_data = on_data
        self._on_disconnect = on_disconnect
        self._on_session_established = on_session_established

    def get_session_info(self) -> Optional[dict]:
        """获取会话信息"""
        if not self._session:
            return None

        return {
            "session_id": self._session.session_id,
            "remote_device_id": self._session.remote_device_id,
            "uptime": time.time() - self._session.started_at,
            "bytes_sent": self._session.bytes_sent,
            "bytes_received": self._session.bytes_received,
            "last_activity": self._session.last_activity,
        }


class RelayPool:
    """
    中继连接池

    管理多个中继连接，自动选择最优
    """

    def __init__(self, device_id: str):
        self.device_id = device_id
        self._relays: Dict[str, RelayBridge] = {}
        self._active_relay: Optional[RelayBridge] = None

    async def add_relay(self, url: str, token: Optional[str] = None):
        """添加中继服务器"""
        config = RelayConfig(
            url=url,
            device_id=self.device_id,
            token=token,
        )
        relay = RelayBridge(config)
        self._relays[url] = relay

    async def connect_to(self, remote_device_id: str,
                        preferred_relay: Optional[str] = None) -> Optional[RelayBridge]:
        """
        连接到远程设备

        Args:
            remote_device_id: 目标设备ID
            preferred_relay: 优先使用的中继

        Returns:
            连接的 RelayBridge
        """
        # 尝试优先中继
        if preferred_relay and preferred_relay in self._relays:
            relay = self._relays[preferred_relay]
            if await relay.connect(remote_device_id):
                self._active_relay = relay
                return relay

        # 尝试其他中继
        for url, relay in self._relays.items():
            if url == preferred_relay:
                continue

            if await relay.connect(remote_device_id):
                self._active_relay = relay
                return relay

        return None

    async def disconnect_all(self):
        """断开所有中继"""
        for relay in self._relays.values():
            await relay.disconnect()

        self._active_relay = None

    def get_active_relay(self) -> Optional[RelayBridge]:
        """获取当前活动的中继"""
        return self._active_relay

    def get_all_relays(self) -> List[RelayBridge]:
        """获取所有中继"""
        return list(self._relays.values())
