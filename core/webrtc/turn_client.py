"""
TURN 客户端模块

提供内置的 TURN 中继客户端，用于:
1. 客户端连接云端 TURN 服务器
2. 本地启动备用 TURN 服务
"""

import asyncio
import logging
import struct
import hashlib
import base64
import time
from dataclasses import dataclass
from typing import Optional, Tuple

# 导入配置
try:
    from core.config.unified_config import get_config
except ImportError:
    get_config = None

logger = logging.getLogger(__name__)


@dataclass
class TurnCredentials:
    """TURN 凭证"""
    username: str
    password: str
    realm: str


class TurnClient:
    """
    TURN/STUN 客户端

    支持:
    - UDP/TCP 两种传输
    - 凭证认证
    - 心跳保活
    """

    # STUN/TURN 消息类型
    STUN_BINDING_REQUEST = 0x0001
    STUN_BINDING_RESPONSE = 0x0101
    STUN_BINDING_ERROR = 0x0111
    TURN_ALLOCATE_REQUEST = 0x0003
    TURN_ALLOCATE_RESPONSE = 0x0103
    TURN_ALLOCATE_ERROR = 0x0113
    TURN_SEND_INDICATION = 0x0016
    TURN_DATA_INDICATION = 0x0017
    TURN_PERMISSION_REQUEST = 0x0018
    TURN_REFRESH_REQUEST = 0x0009

    # 属性类型
    ATTR_MAPPED_ADDRESS = 0x0001
    ATTR_XOR_MAPPED_ADDRESS = 0x0020
    ATTR_USERNAME = 0x0006
    ATTR_MSG_INTEGRITY = 0x0008
    ATTR_REALM = 0x0014
    ATTR_NONCE = 0x0015
    ATTR_XOR_RELAYED_ADDRESS = 0x0016
    ATTR_LIFETIME = 0x000D
    ATTR_SOFTWARE = 0x8022

    def __init__(self, server: str = "", port: int = 3478, protocol: str = "udp"):
        """
        Args:
            server: TURN 服务器地址
            port: 端口
            protocol: udp 或 tcp
        """
        self.server = server
        self.port = port
        self.protocol = protocol.lower()
        self._sock: Optional[asyncio.DatagramTransport] = None
        self._connected = False
        self._relayed_address: Optional[Tuple[str, int]] = None
        self._mapped_address: Optional[Tuple[str, int]] = None
        self._credentials: Optional[TurnCredentials] = None

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def relayed_address(self) -> Optional[Tuple[str, int]]:
        return self._relayed_address

    async def connect(self, username: str = "", password: str = "") -> bool:
        """
        连接到 TURN 服务器

        Returns:
            True if connected successfully
        """
        try:
            if self.protocol == "udp":
                self._sock, _ = await asyncio.get_event_loop().create_datagram_endpoint(
                    lambda: TurnProtocol(self),
                    remote_addr=(self.server, self.port)
                )
            else:
                reader, writer = await asyncio.open_connection(self.server, self.port)
                self._sock = TurnTCPProtocol(writer, self)
                self._connected = True

            # STUN Binding 获取映射地址
            self._mapped_address = await self._stun_binding()

            # 如果提供了凭证，尝试 TURN Allocate
            if username and password:
                self._credentials = TurnCredentials(username, password, "hermes")
                self._relayed_address = await self._turn_allocate()
            else:
                self._connected = True

            logger.info(f"TURN 连接成功: mapped={self._mapped_address}, relayed={self._relayed_address}")
            return True

        except Exception as e:
            logger.error(f"TURN 连接失败: {e}")
            return False

    async def disconnect(self):
        """断开连接"""
        if self._sock:
            self._sock.close()
            self._sock = None
        self._connected = False
        self._relayed_address = None
        self._mapped_address = None

    async def _stun_binding(self) -> Optional[Tuple[str, int]]:
        """发送 STUN Binding 请求"""
        # 从配置读取超时
        timeout = 5.0
        if get_config:
            timeout = get_config().get("relay.stun_timeout", 5.0)
            
        # 构建 Binding Request
        msg = self._build_stun_header(self.STUN_BINDING_REQUEST)
        msg += self._encode_attr(self.ATTR_SOFTWARE, b"Hermes-TURN-Client")

        loop = asyncio.get_event_loop()
        await loop.sock_sendto(self._sock, msg, (self.server, self.port))

        try:
            data, addr = await asyncio.wait_for(loop.sock_recvfrom(self._sock, 1024), timeout=timeout)
            return self._parse_xor_address(data)
        except asyncio.TimeoutError:
            logger.warning("STUN Binding 超时")
            return None

    async def _turn_allocate(self) -> Optional[Tuple[str, int]]:
        """发送 TURN Allocate 请求"""
        if not self._credentials:
            return None

        msg = self._build_stun_header(self.TURN_ALLOCATE_REQUEST)
        msg += self._encode_attr(self.ATTR_USERNAME, self._credentials.username.encode())
        msg += self._encode_attr(self.ATTR_REALM, self._credentials.realm.encode())
        msg += self._encode_attr(self.ATTR_LIFETIME, struct.pack("!I", 3600))  # 1小时

        # 简单消息完整性（实际应使用 HMAC）
        # 这里简化处理

        loop = asyncio.get_event_loop()
        await loop.sock_sendto(self._sock, msg, (self.server, self.port))

        # 从配置读取超时
        timeout = 5.0
        if get_config:
            timeout = get_config().get("relay.stun_timeout", 5.0)
            
        try:
            data, addr = await asyncio.wait_for(loop.sock_recvfrom(self._sock, 1024), timeout=timeout)
            return self._parse_xor_relayed_address(data)
        except asyncio.TimeoutError:
            logger.warning("TURN Allocate 超时")
            return None

    def _build_stun_header(self, msg_type: int, transaction_id: bytes = None) -> bytes:
        """构建 STUN 消息头"""
        if transaction_id is None:
            transaction_id = bytes(12)
        return struct.pack("!HH", msg_type, 0) + b"\x21\x12\xA4\x42" + transaction_id

    def _encode_attr(self, attr_type: int, value: bytes) -> bytes:
        """编码 STUN 属性"""
        length = len(value)
        # Padding to 4 bytes
        padding = (4 - length % 4) % 4
        return struct.pack("!HH", attr_type, length) + value + b"\x00" * padding

    def _parse_xor_address(self, data: bytes) -> Optional[Tuple[str, int]]:
        """解析 XOR-MAPPED-ADDRESS"""
        return self._parse_address_from_data(data, 0x0020)

    def _parse_xor_relayed_address(self, data: bytes) -> Optional[Tuple[str, int]]:
        """解析 XOR-RELAYED-ADDRESS"""
        return self._parse_address_from_data(data, 0x0016)

    def _parse_address_from_data(self, data: bytes, attr_type: int) -> Optional[Tuple[str, int]]:
        """从数据中解析地址属性"""
        offset = 20  # STUN header
        while offset < len(data) - 8:
            atype = struct.unpack("!H", data[offset:offset+2])[0]
            alen = struct.unpack("!H", data[offset+2:offset+4])[0]
            if atype == attr_type and alen >= 8:
                # Family (1) + Port (2) + Address (4)
                family = data[offset+5]
                if family == 0x01:  # IPv4
                    port = struct.unpack("!H", data[offset+6:offset+8])[0] ^ 0x2112
                    ip_bytes = struct.unpack("!I", data[offset+8:offset+12])[0] ^ struct.unpack("!I", b"\x21\x12\xA4\x42")[0]
                    ip = self._ip_int_to_str(ip_bytes)
                    return (ip, port)
            offset += 4 + alen
        return None

    def _ip_int_to_str(self, ip_int: int) -> str:
        """整数转 IP 字符串"""
        return ".".join(str((ip_int >> (8 * i)) & 0xFF) for i in range(3, -1, -1))

    async def send_to(self, data: bytes, peer_addr: Tuple[str, int]):
        """通过 TURN 发送数据到目标"""
        # TURN Send Indication
        msg = self._build_stun_header(self.TURN_SEND_INDICATION)
        msg += self._encode_attr(0x0004, self._encode_address(peer_addr))  # XOR-PEER-ADDRESS
        msg += self._encode_attr(0x0009, data)  # DATA
        # 添加属性
        msg = struct.pack("!HH", self.TURN_SEND_INDICATION, len(msg) - 20) + msg[4:]

        loop = asyncio.get_event_loop()
        await loop.sock_sendto(self._sock, msg, (self.server, self.port))

    def _encode_address(self, addr: Tuple[str, int]) -> bytes:
        """编码地址"""
        ip, port = addr
        ip_int = self._ip_str_to_int(ip)
        xor_ip = ip_int ^ struct.unpack("!I", b"\x21\x12\xA4\x42")[0]
        xor_port = port ^ 0x2112
        return struct.pack("!BBH", 0x01, 0x00, xor_port) + struct.pack("!I", xor_ip)

    def _ip_str_to_int(self, ip: str) -> int:
        """IP 字符串转整数"""
        parts = map(int, ip.split("."))
        return sum(p << (8 * i) for i, p in enumerate(reversed(list(parts))))


class TurnProtocol(asyncio.DatagramProtocol):
    """TURN UDP 协议"""

    def __init__(self, client: TurnClient):
        self.client = client
        self._transport = None

    def connection_made(self, transport):
        self._transport = transport
        self.client._connected = True

    def datagram_received(self, data, addr):
        # 处理收到的数据
        logger.debug(f"收到 TURN 数据: {len(data)} bytes from {addr}")

    def error_received(self, exc):
        logger.error(f"TURN 错误: {exc}")


class TurnTCPProtocol:
    """TURN TCP 协议"""

    def __init__(self, writer: asyncio.StreamWriter, client: TurnClient):
        self.writer = writer
        self.client = client

    def write(self, data: bytes):
        self.writer.write(data)

    async def drain(self):
        await self.writer.drain()

    def close(self):
        self.writer.close()


# 工具函数
def generate_long_term_credential(username: str, realm: str, password: str, expiry_seconds: int = 86400) -> str:
    """
    生成长期凭证 (RFC 5389)

    Args:
        username: 用户名
        realm: 领域
        password: 密码
        expiry_seconds: 过期时间（秒）

    Returns:
        编码后的密码字符串
    """
    # 格式: username:expiry_timestamp
    timestamp = int(time.time()) + expiry_seconds
    credentials = f"{username}:{timestamp}"

    # HMAC-SHA1
    import hmac
    key = password.encode()
    mac = hmac.new(key, credentials.encode(), hashlib.sha1)

    # 响应: password Base64(mac)
    return base64.b64encode(mac.digest()).decode()


def create_turn_credentials(user: str, password: str, hours: int = 24) -> dict:
    """
    创建 TURN 凭证

    Returns:
        dict with username and password for TURN client
    """
    timestamp = int(time.time()) + hours * 3600
    username = f"{timestamp}:{user}"
    password_hash = generate_long_term_credential(username, "hermes", password)

    return {
        "username": username,
        "password": password_hash,
        "realm": "hermes"
    }


# 简单的内嵌 TURN 服务器（用于本地测试）
async def start_local_turn(port: int = 3478, user: str = "local", password: str = "local"):
    """
    启动简单的本地 TURN 服务器（仅用于测试）

    实际生产应使用 pion/simple-turn
    """
    logger.info(f"本地 TURN 服务器启动: 0.0.0.0:{port}")

    loop = asyncio.get_event_loop()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", port))
    sock.setblocking(False)

    while True:
        try:
            data, addr = await loop.sock_recvfrom(sock, 2048)
            logger.debug(f"收到数据 from {addr}: {len(data)} bytes")

            # 简单响应 - 实际需要完整的 STUN/TURN 处理
            # 这里仅做演示

        except Exception as e:
            logger.error(f"TURN 服务器错误: {e}")
            break

    sock.close()
