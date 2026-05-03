"""
LivingTree P2P 节点发现模块
============================

统一 p2p_broadcast (UDP 广播)、p2p_connector (目录服务)、p2p_knowledge (DHT)
三种发现机制为单一 PeerDiscovery 引擎。

策略链: BROADCAST → DIRECTORY → DHT → BOOTSTRAP → MANUAL

Author: LivingTreeAI Team
Version: 1.0.0
"""

from __future__ import annotations

import asyncio
import json
import socket
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from loguru import logger

from .models import (
    PeerInfo, PeerIdentity, PeerStatus, TrustLevel,
    NetworkAddress, DiscoveryMethod, ConnectionConfig,
    RoutingEntry, P2PMessage, MessageType,
)

# ============================================================================
# 发现结果
# ============================================================================

@dataclass
class DiscoveryResult:
    """发现结果"""
    peer: PeerInfo
    method: DiscoveryMethod
    discovered_at: datetime = field(default_factory=datetime.now)
    rtt_ms: float = 0.0


# ============================================================================
# 节点发现引擎
# ============================================================================

class PeerDiscovery:
    """
    节点发现引擎

    合并三种发现方式：
    1. BroadcastDiscovery — UDP 局域网广播 (来自 p2p_broadcast)
    2. DirectoryService — 中心化目录查询 (来自 p2p_connector)
    3. DHT/ServerDiscovery — 去中心化哈希表 (来自 p2p_knowledge)

    策略链（按优先级自动尝试）：
    BROADCAST → DIRECTORY → DHT → BOOTSTRAP → MANUAL
    """

    def __init__(
        self,
        local_identity: PeerIdentity,
        config: Optional[ConnectionConfig] = None,
    ):
        self.local_identity = local_identity
        self.config = config or ConnectionConfig()

        # 已发现的节点
        self._peers: Dict[str, PeerInfo] = {}          # node_id → PeerInfo

        # 路由表（DHT 风格）
        self._routing_table: Dict[str, RoutingEntry] = {}

        # 引导节点
        self._bootstrap_nodes: List[NetworkAddress] = []

        # 回调
        self._on_peer_discovered: List[Callable] = []
        self._on_peer_lost: List[Callable] = []

        # 后台任务
        self._running = False
        self._tasks: List[asyncio.Task] = []

    # ── 公共 API ──────────────────────────────────────────

    async def start(self) -> None:
        """启动发现引擎"""
        if self._running:
            return
        self._running = True
        logger.info("PeerDiscovery 启动")
        # 启动广播监听
        if self.config.broadcast_port:
            task = asyncio.create_task(self._listen_broadcast())
            self._tasks.append(task)

    async def stop(self) -> None:
        """停止发现引擎"""
        self._running = False
        for task in self._tasks:
            task.cancel()
        self._tasks.clear()
        logger.info("PeerDiscovery 已停止")

    async def discover(
        self,
        methods: Optional[List[DiscoveryMethod]] = None,
        max_peers: int = 50,
        timeout: float = 10.0,
    ) -> List[DiscoveryResult]:
        """
        主动发现节点

        Args:
            methods: 要使用的发现方法（None = 全部）
            max_peers: 最大节点数
            timeout: 超时秒数

        Returns:
            发现的节点列表
        """
        methods = methods or list(DiscoveryMethod)
        results: List[DiscoveryResult] = []
        seen: Set[str] = set()

        for method in methods:
            if len(results) >= max_peers:
                break
            try:
                method_results = await asyncio.wait_for(
                    self._discover_by_method(method), timeout=timeout
                )
                for r in method_results:
                    if r.peer.identity.node_id not in seen:
                        seen.add(r.peer.identity.node_id)
                        results.append(r)
                        self._add_or_update_peer(r.peer)
            except asyncio.TimeoutError:
                logger.debug(f"发现超时: {method.value}")
            except Exception as e:
                logger.warning(f"发现失败 ({method.value}): {e}")

        logger.info(f"发现完成: {len(results)} 个节点")
        return results

    def get_peer(self, node_id: str) -> Optional[PeerInfo]:
        """获取已知节点"""
        return self._peers.get(node_id)

    def list_peers(
        self,
        status_filter: Optional[List[PeerStatus]] = None,
        trust_filter: Optional[TrustLevel] = None,
    ) -> List[PeerInfo]:
        """列出节点（支持过滤）"""
        peers = list(self._peers.values())
        if status_filter:
            peers = [p for p in peers if p.status in status_filter]
        if trust_filter:
            peers = [p for p in peers if p.trust_level == trust_filter]
        return peers

    def on_discovered(self, callback: Callable) -> None:
        """注册发现回调"""
        self._on_peer_discovered.append(callback)

    def on_lost(self, callback: Callable) -> None:
        """注册丢失回调"""
        self._on_peer_lost.append(callback)

    # ── 发现策略 ──────────────────────────────────────────

    async def _discover_by_method(
        self, method: DiscoveryMethod
    ) -> List[DiscoveryResult]:
        """按指定方法发现"""
        if method == DiscoveryMethod.BROADCAST:
            return await self._discover_broadcast()
        elif method == DiscoveryMethod.DIRECTORY:
            return await self._discover_directory()
        elif method == DiscoveryMethod.DHT:
            return await self._discover_dht()
        elif method == DiscoveryMethod.BOOTSTRAP:
            return await self._discover_bootstrap()
        else:
            return []

    async def _discover_broadcast(self) -> List[DiscoveryResult]:
        """
        UDP 局域网广播发现

        发送广播包 → 等待响应 → 解析节点信息
        """
        results: List[DiscoveryResult] = []
        port = self.config.broadcast_port

        try:
            loop = asyncio.get_event_loop()
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.settimeout(3.0)
            sock.bind(("0.0.0.0", 0))

            # 发送发现包
            announcement = json.dumps({
                "type": "discovery",
                "node_id": self.local_identity.node_id,
                "short_id": self.local_identity.short_id,
                "display_name": self.local_identity.display_name,
                "device_name": self.local_identity.device_name,
            }).encode("utf-8")

            sock.sendto(announcement, ("255.255.255.255", port))

            # 收集响应
            start = time.time()
            while time.time() - start < 3.0:
                try:
                    data, addr = await loop.run_in_executor(None, sock.recvfrom, 4096)
                    peer_data = json.loads(data.decode("utf-8"))
                    if peer_data.get("type") == "discovery_response":
                        peer = PeerInfo(
                            identity=PeerIdentity(
                                node_id=peer_data.get("node_id", ""),
                                short_id=peer_data.get("short_id", ""),
                                display_name=peer_data.get("display_name", ""),
                                device_name=peer_data.get("device_name", ""),
                            ),
                            local_addr=NetworkAddress(addr[0], addr[1]),
                            status=PeerStatus.ONLINE,
                        )
                        results.append(DiscoveryResult(
                            peer=peer,
                            method=DiscoveryMethod.BROADCAST,
                        ))
                except socket.timeout:
                    break
                except json.JSONDecodeError:
                    continue

            sock.close()
        except Exception as e:
            logger.debug(f"广播发现失败: {e}")

        return results

    async def _discover_directory(self) -> List[DiscoveryResult]:
        """
        目录服务发现

        查询中心化目录服务获取在线节点列表
        """
        # 目录服务需要中心化服务器，提供占位实现
        logger.debug("目录服务发现暂未配置服务器")
        return []

    async def _discover_dht(self) -> List[DiscoveryResult]:
        """
        DHT 分布式发现

        从路由表中查找最近节点并交换路由信息
        """
        results: List[DiscoveryResult] = []

        # 从路由表获取已知节点
        for node_id, entry in list(self._routing_table.items()):
            if not entry.is_stale and not entry.is_dead:
                peer = self._peers.get(node_id)
                if peer:
                    results.append(DiscoveryResult(
                        peer=peer,
                        method=DiscoveryMethod.DHT,
                    ))

        return results

    async def _discover_bootstrap(self) -> List[DiscoveryResult]:
        """从引导节点发现"""
        results: List[DiscoveryResult] = []

        for addr in self._bootstrap_nodes[:5]:
            try:
                # 向引导节点请求节点列表
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(addr.host, addr.port),
                    timeout=self.config.connect_timeout,
                )
                # 发送节点列表请求
                request = json.dumps({
                    "type": "request_peers",
                    "node_id": self.local_identity.node_id,
                }).encode("utf-8")
                writer.write(len(request).to_bytes(4, "big") + request)
                await writer.drain()

                # 读取响应
                data = await reader.read(4096)
                if len(data) > 4:
                    peers_data = json.loads(data[4:].decode("utf-8"))
                    for pd in peers_data.get("peers", []):
                        peer = PeerInfo.from_dict(pd)
                        results.append(DiscoveryResult(
                            peer=peer,
                            method=DiscoveryMethod.BOOTSTRAP,
                        ))

                writer.close()
                await writer.wait_closed()
            except Exception as e:
                logger.debug(f"引导发现失败 ({addr}): {e}")

        return results

    # ── 广播监听（后台任务）───────────────────────────────

    async def _listen_broadcast(self) -> None:
        """后台监听广播发现请求"""
        try:
            loop = asyncio.get_event_loop()
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("0.0.0.0", self.config.broadcast_port))
            sock.setblocking(False)

            logger.info(f"广播监听启动: port={self.config.broadcast_port}")

            while self._running:
                try:
                    data, addr = await loop.sock_recvfrom(sock, 4096)
                    msg = json.loads(data.decode("utf-8"))
                    if msg.get("type") == "discovery":
                        # 回复发现响应
                        response = json.dumps({
                            "type": "discovery_response",
                            "node_id": self.local_identity.node_id,
                            "short_id": self.local_identity.short_id,
                            "display_name": self.local_identity.display_name,
                            "device_name": self.local_identity.device_name,
                        }).encode("utf-8")
                        await loop.sock_sendto(sock, response, addr)
                except (BlockingIOError, InterruptedError):
                    await asyncio.sleep(0.1)
                except json.JSONDecodeError:
                    continue
                except Exception as e:
                    if self._running:
                        logger.warning(f"广播监听异常: {e}")
                        await asyncio.sleep(1.0)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"广播监听致命错误: {e}")
        finally:
            try:
                sock.close()
            except Exception:
                pass

    # ── 内部方法 ──────────────────────────────────────────

    def _add_or_update_peer(self, peer: PeerInfo) -> None:
        """添加或更新节点信息"""
        node_id = peer.identity.node_id
        is_new = node_id not in self._peers
        self._peers[node_id] = peer

        # 更新路由表
        if peer.local_addr:
            self._routing_table[node_id] = RoutingEntry(
                peer_id=node_id,
                address=peer.local_addr,
            )

        if is_new:
            for cb in self._on_peer_discovered:
                try:
                    cb(peer)
                except Exception:
                    pass

    def add_bootstrap_node(self, addr: NetworkAddress) -> None:
        """手动添加引导节点"""
        if addr not in self._bootstrap_nodes:
            self._bootstrap_nodes.append(addr)

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        online = sum(1 for p in self._peers.values() if p.is_reachable())
        return {
            "total_peers": len(self._peers),
            "online_peers": online,
            "routing_entries": len(self._routing_table),
            "bootstrap_nodes": len(self._bootstrap_nodes),
        }


# ============================================================================
# 消息分发器
# ============================================================================

class MessageDispatcher:
    """
    统一消息分发器

    合并 ChatConnection (p2p_broadcast) + MultiChannelManager (p2p_connector)
    为单一消息路由层。
    """

    def __init__(self, discovery: PeerDiscovery):
        self.discovery = discovery
        self._handlers: Dict[MessageType, List[Callable]] = {
            mt: [] for mt in MessageType
        }

    def on_message(self, msg_type: MessageType, handler: Callable) -> None:
        """注册消息处理器"""
        self._handlers[msg_type].append(handler)

    async def send(
        self,
        recipient_id: str,
        msg_type: MessageType,
        payload: Dict[str, Any],
        priority: int = 0,
    ) -> bool:
        """
        发送消息

        自动选择最佳传输路径：
        1. 直连（如果可达）
        2. 中继（如果不可达）

        Returns:
            是否成功发送
        """
        msg = P2PMessage.create(
            msg_type=msg_type,
            sender_id=self.discovery.local_identity.node_id,
            recipient_id=recipient_id,
            payload=payload,
            priority=priority,
        )

        peer = self.discovery.get_peer(recipient_id)
        if peer and peer.is_reachable() and peer.local_addr:
            return await self._send_direct(peer.local_addr, msg)

        # 离线：队列存储（简化实现）
        logger.debug(f"节点不可达，消息排队: {recipient_id[:8]}...")
        return False

    async def _send_direct(
        self, addr: NetworkAddress, msg: P2PMessage
    ) -> bool:
        """直接发送"""
        try:
            data = json.dumps(msg.to_dict(), ensure_ascii=False).encode("utf-8")
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(addr.host, addr.port),
                timeout=5.0,
            )
            writer.write(len(data).to_bytes(4, "big") + data)
            await writer.drain()
            writer.close()
            await writer.wait_closed()
            return True
        except Exception as e:
            logger.debug(f"直连发送失败 ({addr}): {e}")
            return False


__all__ = [
    "PeerDiscovery",
    "MessageDispatcher",
    "DiscoveryResult",
]
