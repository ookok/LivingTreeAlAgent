"""
服务器发现与选举模块

实现引导节点发现、服务器选举和志愿者管理
"""

from __future__ import annotations

import asyncio
import logging
import socket
import time
from dataclasses import dataclass, field
from typing import Optional

from .models import RelayServer, NetworkAddress, NatType

logger = logging.getLogger(__name__)


@dataclass
class ServerMetrics:
    """服务器指标"""
    server_id: str
    latency: float = 0.0
    load: float = 0.0
    bandwidth: int = 0
    reliability: float = 1.0
    last_update: float = field(default_factory=time.time)


class ServerDiscovery:
    """服务器发现服务"""
    
    # 引导服务器列表（公共的）
    BOOTSTRAP_SERVERS = [
        ("bootstrap1.p2pks.example.com", 18890),
        ("bootstrap2.p2pks.example.com", 18890),
    ]
    
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.discovered_servers: dict[str, RelayServer] = {}
        self.server_metrics: dict[str, ServerMetrics] = {}
        self.preferred_server: Optional[RelayServer] = None
        
        # 志愿者服务器列表
        self.volunteer_servers: list[RelayServer] = []
        
        # mDNS/UDP广播
        self._broadcast_socket: Optional[socket.socket] = None
        self._running = False
        self._discovery_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """启动服务器发现"""
        self._running = True
        self._discovery_task = asyncio.create_task(self._discovery_loop())
        logger.info("Server discovery started")
    
    async def stop(self):
        """停止服务器发现"""
        self._running = False
        
        if self._discovery_task:
            self._discovery_task.cancel()
            try:
                await self._discovery_task
            except asyncio.CancelledError:
                pass
        
        if self._broadcast_socket:
            self._broadcast_socket.close()
        
        logger.info("Server discovery stopped")
    
    async def discover_servers(self) -> list[RelayServer]:
        """发现可用的服务器"""
        servers = []
        
        # 1. 尝试引导服务器
        for host, port in self.BOOTSTRAP_SERVERS:
            server = await self._probe_server(host, port)
            if server:
                servers.append(server)
        
        # 2. 尝试本地网络发现
        local_servers = await self._discover_local_servers()
        servers.extend(local_servers)
        
        # 3. 添加已知志愿者服务器
        servers.extend(self.volunteer_servers)
        
        # 更新服务器列表
        for server in servers:
            self.discovered_servers[server.server_id] = server
            if server.is_available():
                await self._update_server_metrics(server)
        
        return servers
    
    async def get_best_server(self) -> Optional[RelayServer]:
        """获取最佳服务器"""
        # 刷新服务器列表
        if not self.discovered_servers:
            await self.discover_servers()
        
        available = [
            s for s in self.discovered_servers.values()
            if s.is_available()
        ]
        
        if not available:
            return None
        
        # 按评分排序
        def score(s: RelayServer) -> float:
            metrics = self.server_metrics.get(s.server_id)
            latency_score = max(0, 1 - (metrics.latency if metrics else 500) / 1000)
            load_score = 1 - (s.load if metrics else 0.5)
            return s.score * 0.5 + latency_score * 0.3 + load_score * 0.2
        
        available.sort(key=score, reverse=True)
        return available[0]
    
    async def _probe_server(self, host: str, port: int) -> Optional[RelayServer]:
        """探测服务器"""
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=5.0
            )
            
            # 发送探测请求
            writer.write(f"PING|{self.node_id}\n".encode())
            await writer.drain()
            
            response = await asyncio.wait_for(reader.readline(), timeout=5.0)
            data = response.decode().strip()
            
            if data.startswith("PONG|"):
                parts = data.split('|')
                server_time = float(parts[1]) if len(parts) > 1 else 0
                
                server = RelayServer(
                    server_id=f"{host}:{port}",
                    name=f"Server {host}",
                    addr=NetworkAddress(ip=host, port=port),
                    is_online=True
                )
                
                writer.close()
                await writer.wait_closed()
                return server
            
            writer.close()
            await writer.wait_closed()
            
        except Exception as e:
            logger.debug(f"Server probe failed {host}:{port}: {e}")
        
        return None
    
    async def _discover_local_servers(self) -> list[RelayServer]:
        """通过UDP广播发现本地服务器"""
        servers = []
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.settimeout(3.0)
            
            # 发送发现请求
            discovery_msg = f"SERVER_DISCOVER|{self.node_id}".encode()
            sock.sendto(discovery_msg, ('<broadcast>', 18891))
            
            # 接收响应
            for _ in range(10):
                try:
                    data, addr = sock.recvfrom(1024)
                    msg = data.decode().strip()
                    
                    if msg.startswith("SERVER_ANNOUNCE|"):
                        # 解析服务器信息
                        parts = msg.split('|')
                        if len(parts) >= 4:
                            server = RelayServer(
                                server_id=f"{addr[0]}:{parts[2]}",
                                name=parts[1],
                                addr=NetworkAddress(ip=addr[0], port=int(parts[2])),
                                is_online=True
                            )
                            servers.append(server)
                
                except socket.timeout:
                    break
            
            sock.close()
            
        except Exception as e:
            logger.debug(f"Local discovery failed: {e}")
        
        return servers
    
    async def _update_server_metrics(self, server: RelayServer):
        """更新服务器指标"""
        if server.server_id not in self.server_metrics:
            self.server_metrics[server.server_id] = ServerMetrics(server.server_id)
        
        metrics = self.server_metrics[server.server_id]
        
        # 测量延迟
        try:
            start = time.time()
            reader, writer = await asyncio.open_connection(
                server.addr.ip,
                server.addr.port
            )
            writer.write(f"PING|{self.node_id}\n".encode())
            await writer.drain()
            await reader.readline()
            metrics.latency = (time.time() - start) * 1000
            writer.close()
            await writer.wait_closed()
        except Exception:
            metrics.latency = 9999
        
        metrics.load = server.load
        metrics.last_update = time.time()
    
    async def _discovery_loop(self):
        """定期发现循环"""
        while self._running:
            try:
                await asyncio.sleep(60)  # 每分钟更新一次
                await self.discover_servers()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Discovery loop error: {e}")
    
    def add_volunteer_server(self, server: RelayServer):
        """添加志愿者服务器"""
        self.volunteer_servers.append(server)
        logger.info(f"Added volunteer server: {server.name}")
    
    def get_server_stats(self) -> dict:
        """获取服务器统计"""
        return {
            "total_servers": len(self.discovered_servers),
            "online_servers": sum(1 for s in self.discovered_servers.values() if s.is_online),
            "volunteer_servers": len(self.volunteer_servers),
            "preferred_server": str(self.preferred_server) if self.preferred_server else None,
            "metrics": {
                sid: {
                    "latency": m.latency,
                    "load": m.load,
                    "last_update": m.last_update
                }
                for sid, m in self.server_metrics.items()
            }
        }


class ServerElection:
    """服务器选举（用于选择引导节点）"""
    
    def __init__(self):
        self.candidates: dict[str, dict] = {}
        self.current_leader: Optional[str] = None
    
    def register_candidate(self, server_id: str, uptime: float, bandwidth: int, load: float):
        """注册候选服务器"""
        score = self._calculate_score(uptime, bandwidth, load)
        
        self.candidates[server_id] = {
            "uptime": uptime,
            "bandwidth": bandwidth,
            "load": load,
            "score": score,
            "last_update": time.time()
        }
        
        self._elect_leader()
    
    def _calculate_score(self, uptime: float, bandwidth: int, load: float) -> float:
        """计算选举分数"""
        uptime_score = min(uptime / (7 * 24 * 3600), 1.0) * 30  # 最多30分
        bandwidth_score = min(bandwidth / 100, 1.0) * 40  # 最多40分
        load_score = max(0, (1 - load)) * 30  # 最多30分
        
        return uptime_score + bandwidth_score + load_score
    
    def _elect_leader(self):
        """选举领导者"""
        if not self.candidates:
            self.current_leader = None
            return
        
        # 找到得分最高的候选者
        best = max(self.candidates.items(), key=lambda x: x[1]["score"])
        self.current_leader = best[0]
    
    def get_leader(self) -> Optional[str]:
        """获取当前领导者"""
        return self.current_leader
    
    def is_leader(self, server_id: str) -> bool:
        """检查是否是领导者"""
        return self.current_leader == server_id
    
    def remove_candidate(self, server_id: str):
        """移除候选服务器"""
        if server_id in self.candidates:
            del self.candidates[server_id]
            if self.current_leader == server_id:
                self._elect_leader()


class VolunteerManager:
    """志愿者服务器管理器"""
    
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.is_volunteer = False
        self.volunteer_config: dict = {}
        self.contribution_stats: dict = {
            "total_bandwidth": 0,
            "total_connections": 0,
            "total_data_relayed": 0,
            "uptime": 0
        }
    
    async def become_volunteer(
        self,
        bandwidth: int = 10,
        max_connections: int = 50,
        port: int = 18890
    ) -> bool:
        """成为志愿者"""
        self.is_volunteer = True
        self.volunteer_config = {
            "bandwidth": bandwidth,
            "max_connections": max_connections,
            "port": port,
            "registered_at": time.time()
        }
        
        logger.info(f"Node {self.node_id} became a volunteer server")
        logger.info(f"  Bandwidth: {bandwidth} Mbps")
        logger.info(f"  Max connections: {max_connections}")
        
        # TODO: 向引导服务器注册
        return True
    
    async def leave_volunteer(self):
        """退出志愿者"""
        self.is_volunteer = False
        self.volunteer_config = {}
        logger.info(f"Node {self.node_id} left volunteer network")
    
    def update_stats(self, connections: int, data_relayed: int):
        """更新贡献统计"""
        self.contribution_stats["total_connections"] += connections
        self.contribution_stats["total_data_relayed"] += data_relayed
        self.contribution_stats["uptime"] += 1
    
    def get_contribution_score(self) -> float:
        """计算贡献分数"""
        bandwidth_factor = self.volunteer_config.get("bandwidth", 10) / 10
        uptime_factor = min(self.contribution_stats["uptime"] / (30 * 24 * 3600), 1.0)  # 最多30天
        data_factor = min(self.contribution_stats["total_data_relayed"] / (1024 * 1024 * 1024), 1.0)  # 最多1GB
        
        return (bandwidth_factor * 0.4 + uptime_factor * 0.3 + data_factor * 0.3) * 100
    
    def get_benefits(self) -> dict:
        """获取志愿者权益"""
        score = self.get_contribution_score()
        
        benefits = {
            "priority_access": score >= 30,
            "extra_storage": int(score / 10) * 100,  # 每10分增加100MB
            "advanced_features": score >= 60,
            "community_badge": score >= 50
        }
        
        return benefits
