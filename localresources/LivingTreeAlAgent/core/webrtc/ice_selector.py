"""
智能 ICE 服务器选路模块

根据网络环境自动选择最优的 ICE 配置:
- Tier 1: 公网IP/宽松NAT → STUN 直连
- Tier 2: 云 TURN 中继 → 主力中继
- Tier 3: 本地 TURN 兜底 → 内网备用
"""

import asyncio
import socket
import struct
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class NetworkTier(Enum):
    """网络层级"""
    TIER1_DIRECT = 1  # P2P 直连
    TIER2_CLOUD_RELAY = 2  # 云端中继
    TIER3_LOCAL_RELAY = 3  # 本地兜底


@dataclass
class IceServer:
    """ICE 服务器配置"""
    urls: List[str]
    username: Optional[str] = None
    credential: Optional[str] = None
    tier: NetworkTier = NetworkTier.TIER1_DIRECT

    def to_dict(self) -> dict:
        result = {"urls": self.urls}
        if self.username:
            result["username"] = self.username
        if self.credential:
            result["credential"] = self.credential
        return result


@dataclass
class IceConfig:
    """ICE 配置"""
    ice_servers: List[IceServer] = field(default_factory=list)
    ice_transport_policy: str = "all"  # all/component/restrict

    def to_js_config(self) -> dict:
        return {
            "iceServers": [server.to_dict() for server in self.ice_servers],
            "iceTransportPolicy": self.ice_transport_policy
        }


@dataclass
class ProbeResult:
    """探测结果"""
    tier: NetworkTier
    latency_ms: float
    success: bool
    nat_type: str = "unknown"
    public_ip: Optional[str] = None
    error: Optional[str] = None


class IceSelector:
    """
    智能 ICE 选路器

    探测流程:
    1. STUN 探测公网 IP 和 NAT 类型
    2. 尝试连接云端 TURN 服务器
    3. 若都失败，启动本地 TURN 兜底
    """

    PUBLIC_STUN_SERVERS = [
        ("stun.l.google.com", 19302),
        ("stun1.l.google.com", 19302),
        ("stun2.l.google.com", 19305),
    ]

    def __init__(self,
                 cloud_turn_url: str = "",
                 cloud_turn_user: str = "",
                 cloud_turn_credential: str = "",
                 local_turn_binary: str = ""):
        self.cloud_turn_url = cloud_turn_url
        self.cloud_turn_user = cloud_turn_user
        self.cloud_turn_credential = cloud_turn_credential
        self.local_turn_binary = local_turn_binary
        self._local_turn_process: Optional[asyncio.subprocess.Process] = None

    async def probe_stun(self, stun_server: Tuple[str, int], timeout: float = 3.0) -> ProbeResult:
        """探测 STUN 服务器，获取公网 IP"""
        try:
            # STUN Binding Request
            transaction_id = bytes(12)
            stun_header = b'\x00\x01\x00\x00\x21\x12\xA4\x42' + transaction_id

            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(timeout)

            loop = asyncio.get_event_loop()
            send_time = loop.time()
            await loop.sock_sendto(sock, stun_header, (stun_server[0], stun_server[1]))
            data, _ = await loop.sock_recvfrom(sock, 1024)
            recv_time = loop.time()

            sock.close()
            latency = (recv_time - send_time) * 1000

            # 解析 XOR-MAPPED-ADDRESS
            public_ip = None
            offset = 20
            while offset < len(data) - 8:
                attr_type = struct.unpack('!H', data[offset:offset+2])[0]
                attr_len = struct.unpack('!H', data[offset+2:offset+4])[0]
                if attr_type == 0x0020 and attr_len >= 8:
                    xor_port = struct.unpack('!H', data[offset+6:offset+8])[0]
                    port = xor_port ^ 0x2112
                    xor_ip = struct.unpack('!I', data[offset+8:offset+12])[0]
                    ip_int = xor_ip ^ struct.unpack('!I', b'\x21\x12\xA4\x42')[0]
                    public_ip = socket.inet_ntoa(struct.pack('!I', ip_int))
                    break
                offset += 4 + attr_len

            return ProbeResult(
                tier=NetworkTier.TIER1_DIRECT,
                latency_ms=latency,
                success=True,
                nat_type="full",
                public_ip=public_ip
            )

        except asyncio.TimeoutError:
            return ProbeResult(tier=NetworkTier.TIER3_LOCAL_RELAY, latency_ms=timeout*1000, success=False, error="timeout")
        except Exception as e:
            return ProbeResult(tier=NetworkTier.TIER3_LOCAL_RELAY, latency_ms=0, success=False, error=str(e))

    async def probe_cloud_turn(self, timeout: float = 5.0) -> ProbeResult:
        """探测云端 TURN 服务器"""
        if not self.cloud_turn_url:
            return ProbeResult(tier=NetworkTier.TIER3_LOCAL_RELAY, latency_ms=0, success=False, error="No TURN configured")

        try:
            turn_host = self.cloud_turn_url.replace("turn:", "").replace("turns:", "")
            if ":" in turn_host:
                host, port_str = turn_host.rsplit(":", 1)
                port = int(port_str)
            else:
                host, port = turn_host, 3478

            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(timeout)

            loop = asyncio.get_event_loop()
            send_time = loop.time()
            await loop.sock_sendto(sock, b'\x00\x01\x00\x00\x21\x12\xA4\x42\x00\x00\x00\x00\x00\x00\x00\x00', (host, port))
            await loop.sock_recvfrom(sock, 1024)
            recv_time = loop.time()

            sock.close()
            return ProbeResult(tier=NetworkTier.TIER2_CLOUD_RELAY, latency_ms=(recv_time-send_time)*1000, success=True, public_ip=f"{host}:{port}")

        except Exception as e:
            return ProbeResult(tier=NetworkTier.TIER3_LOCAL_RELAY, latency_ms=0, success=False, error=str(e))

    async def select_ice_config(self) -> IceConfig:
        """智能选择最优 ICE 配置"""
        config = IceConfig()

        # 阶段1: STUN 探测
        logger.info("开始 STUN 探测...")
        stun_result = await self._probe_all_stun()

        if stun_result.success:
            logger.info(f"STUN 成功: {stun_result.public_ip}, {stun_result.latency_ms:.1f}ms")
            config.ice_servers.append(IceServer(urls=["stun:stun.l.google.com:19302"], tier=NetworkTier.TIER1_DIRECT))
            if self.cloud_turn_url:
                config.ice_servers.append(IceServer(urls=[self.cloud_turn_url], username=self.cloud_turn_user,
                                                   credential=self.cloud_turn_credential, tier=NetworkTier.TIER2_CLOUD_RELAY))
            return config

        # 阶段2: 云端 TURN
        logger.info("STUN 失败，探测云端 TURN...")
        turn_result = await self.probe_cloud_turn()

        if turn_result.success:
            logger.info(f"云端 TURN 成功: {turn_result.latency_ms:.1f}ms")
            config.ice_servers.append(IceServer(urls=[self.cloud_turn_url], username=self.cloud_turn_user,
                                               credential=self.cloud_turn_credential, tier=NetworkTier.TIER2_CLOUD_RELAY))
            return config

        # 阶段3: 本地兜底
        logger.info("云端 TURN 失败，启动本地 TURN...")
        await self._start_local_turn()
        config.ice_servers.append(IceServer(urls=["turn:127.0.0.1:3478"], username="local",
                                           credential="local", tier=NetworkTier.TIER3_LOCAL_RELAY))
        return config

    async def _probe_all_stun(self) -> ProbeResult:
        """探测所有 STUN 服务器"""
        tasks = [self.probe_stun(s) for s in self.PUBLIC_STUN_SERVERS]
        done, _ = await asyncio.wait(tasks, timeout=3.0)
        results = [t.result() for t in done if t.exception() is None]
        successful = [r for r in results if r.success]
        if successful:
            return min(successful, key=lambda x: x.latency_ms)
        return results[0] if results else ProbeResult(tier=NetworkTier.TIER3_LOCAL_RELAY, latency_ms=3000, success=False, error="All failed")

    async def _start_local_turn(self):
        """启动本地 TURN"""
        if self._local_turn_process or not self.local_turn_binary:
            return
        try:
            import os
            env = os.environ.copy()
            env["USERS"] = "local=local"
            env["REALM"] = "localhost"
            env["UDP_PORT"] = "3478"
            self._local_turn_process = await asyncio.create_subprocess_exec(
                self.local_turn_binary, env=env,
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL
            )
            logger.info(f"本地 TURN 启动 (PID: {self._local_turn_process.pid})")
            await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"启动本地 TURN 失败: {e}")

    async def stop_local_turn(self):
        """停止本地 TURN"""
        if self._local_turn_process:
            self._local_turn_process.terminate()
            await self._local_turn_process.wait()
            self._local_turn_process = None


def tier1_stun_only() -> IceConfig:
    return IceConfig(ice_servers=[IceServer(urls=["stun:stun.l.google.com:19302"], tier=NetworkTier.TIER1_DIRECT)])


def tier2_cloud_relay(user: str, credential: str, host: str = "") -> IceConfig:
    return IceConfig(ice_servers=[IceServer(urls=[f"turn:{host}:3478" if host else "turn:your-server.com:3478"],
                                            username=user, credential=credential, tier=NetworkTier.TIER2_CLOUD_RELAY)])


def tier3_local_fallback() -> IceConfig:
    return IceConfig(ice_servers=[IceServer(urls=["turn:127.0.0.1:3478"], username="local",
                                            credential="local", tier=NetworkTier.TIER3_LOCAL_RELAY)])


_selector_instance: Optional[IceSelector] = None


def get_ice_selector(**kwargs) -> IceSelector:
    global _selector_instance
    if _selector_instance is None:
        _selector_instance = IceSelector(**kwargs)
    return _selector_instance


async def select_best_ice_config(**kwargs) -> IceConfig:
    selector = get_ice_selector(**kwargs)
    return await selector.select_ice_config()
