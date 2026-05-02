"""
P2P知识库系统 - 统一调度器

整合所有模块，提供统一的P2P知识库服务
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path
from typing import Optional

from .models import (
    PeerNode, NetworkAddress, NatType, NodeRole,
    KnowledgeItem, SyncState, ShareLink, ShareType,
    DEFAULT_UDP_PORT, DEFAULT_TCP_PORT, DEFAULT_RELAY_PORT
)

# 子模块
from .p2p_node import P2PNode, create_node
from .nat_traversal import NATTraversal, NATTraversal, detect_nat, TurnClient
from .relay_server import RelayService, RelayClient, create_relay_server
from .knowledge_sync import KnowledgeSync, KnowledgeDatabase, SelectiveSync
from .doc_share import DocShare, PeerShare, ShareLinkServer, ShortLinkGenerator
from .virtual_storage import VirtualStorage, create_local_storage
from .server_discovery import ServerDiscovery, ServerElection, VolunteerManager
from .security import (
    CryptoManager, IdentityManager, SecureChannel,
    AccessControl, WatermarkGenerator
)

logger = logging.getLogger(__name__)


class P2PKnowledgeNode:
    """
    P2P知识库节点 - 统一入口
    
    整合P2P网络、NAT穿透、知识库同步、文档分享、虚拟存储、安全加密等功能
    """
    
    def __init__(
        self,
        user_id: str,
        data_dir: Optional[str] = None,
        enable_relay: bool = False
    ):
        self.node_id = uuid.uuid4().hex[:12]
        self.user_id = user_id
        self.data_dir = Path(data_dir or f"~/.hermes-p2p/{self.node_id}")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # 核心组件
        self.p2p_node: Optional[P2PNode] = None
        self.nat_traversal: Optional[NATTraversal] = None
        self.knowledge_sync: Optional[KnowledgeSync] = None
        self.doc_share: Optional[DocShare] = None
        self.virtual_storage: Optional[VirtualStorage] = None
        self.server_discovery: Optional[ServerDiscovery] = None
        self.relay_client: Optional[RelayClient] = None
        
        # 安全组件
        self.crypto = CryptoManager()
        self.identity = IdentityManager(self.crypto)
        self.access_control = AccessControl()
        
        # 配置
        self.enable_relay = enable_relay
        self.relay_server: Optional[RelayService] = None
        
        # 状态
        self.is_running = False
        self.nat_type: NatType = NatType.UNKNOWN
        self.public_addr: Optional[NetworkAddress] = None
        
        # 服务器列表
        self.bootstrap_servers: list[tuple[str, int]] = []
    
    async def start(self):
        """启动P2P知识库节点"""
        logger.info(f"Starting P2P Knowledge Node {self.node_id}...")
        
        # 1. 初始化身份
        self.identity.create_identity(self.node_id, self.user_id)
        
        # 2. 检测NAT类型
        logger.info("Detecting NAT type...")
        self.nat_traversal = NATTraversal(local_port=DEFAULT_UDP_PORT)
        nat_result = await self.nat_traversal.detect_nat_type()
        self.nat_type = nat_result.nat_type
        self.public_addr = nat_result.public_addr
        logger.info(f"NAT type: {nat_result.nat_type.name}, Public addr: {nat_result.public_addr}")
        
        # 3. 初始化P2P节点
        self.p2p_node = P2PNode(
            node_id=self.node_id,
            user_id=self.user_id,
            udp_port=DEFAULT_UDP_PORT,
            tcp_port=DEFAULT_TCP_PORT
        )
        self.p2p_node.public_addr = self.public_addr
        await self.p2p_node.start()
        
        # 4. 初始化知识库同步
        db_path = str(self.data_dir / "knowledge.db")
        self.knowledge_sync = KnowledgeSync(
            user_id=self.user_id,
            db_path=db_path
        )
        await self.knowledge_sync.start()
        
        # 5. 初始化文档分享
        self.doc_share = DocShare(
            user_id=self.user_id,
            db_path=db_path
        )
        
        # 6. 初始化虚拟存储
        self.virtual_storage = create_local_storage(
            str(self.data_dir / "storage")
        )
        
        # 7. 初始化服务器发现
        self.server_discovery = ServerDiscovery(self.node_id)
        await self.server_discovery.start()
        
        # 8. 如果是启用relay模式，启动中继服务
        if self.enable_relay:
            self.relay_server = await create_relay_server(
                host="0.0.0.0",
                port=DEFAULT_RELAY_PORT
            )
            logger.info("Relay server started")
        
        # 9. 连接到中继服务器
        best_server = await self.server_discovery.get_best_server()
        if best_server:
            self.relay_client = RelayClient(
                best_server.addr.ip,
                best_server.addr.port
            )
            connected = await self.relay_client.connect(self.node_id)
            if connected:
                logger.info(f"Connected to relay server: {best_server.name}")
            else:
                logger.warning("Failed to connect to relay server")
        
        # 10. 启动志愿者模式（如果愿意贡献）
        # await self._become_volunteer_if_able()
        
        self.is_running = True
        logger.info(f"P2P Knowledge Node {self.node_id} started successfully")
    
    async def stop(self):
        """停止节点"""
        logger.info(f"Stopping P2P Knowledge Node {self.node_id}...")
        
        self.is_running = False
        
        # 断开中继连接
        if self.relay_client:
            await self.relay_client.disconnect()
        
        # 停止服务器发现
        if self.server_discovery:
            await self.server_discovery.stop()
        
        # 停止知识库同步
        if self.knowledge_sync:
            await self.knowledge_sync.stop()
        
        # 停止P2P节点
        if self.p2p_node:
            await self.p2p_node.stop()
        
        # 停止中继服务器
        if self.relay_server:
            await self.relay_server.stop()
        
        logger.info(f"P2P Knowledge Node {self.node_id} stopped")
    
    # ============= 知识库操作 =============
    
    async def add_knowledge(
        self,
        title: str,
        content: str,
        content_type: str = "text",
        tags: list[str] = None
    ) -> KnowledgeItem:
        """添加知识条目"""
        item = KnowledgeItem(
            user_id=self.user_id,
            title=title,
            content=content,
            content_type=content_type,
            tags=tags or []
        )
        
        await self.knowledge_sync.add_item(item)
        return item
    
    async def update_knowledge(self, item: KnowledgeItem) -> bool:
        """更新知识条目"""
        return await self.knowledge_sync.update_item(item)
    
    async def delete_knowledge(self, item_id: str) -> bool:
        """删除知识条目"""
        return await self.knowledge_sync.delete_item(item_id)
    
    def get_all_knowledge(self) -> list[KnowledgeItem]:
        """获取所有知识条目"""
        return self.knowledge_sync.get_items()
    
    def search_knowledge(self, keyword: str) -> list[KnowledgeItem]:
        """搜索知识条目"""
        items = self.get_all_knowledge()
        keyword_lower = keyword.lower()
        return [
            item for item in items
            if keyword_lower in item.title.lower() or keyword_lower in item.content.lower()
        ]
    
    # ============= 文档分享 =============
    
    def create_share_link(
        self,
        item: KnowledgeItem,
        expires_hours: int = 168
    ) -> ShareLink:
        """创建分享链接"""
        from .doc_share import ShareConfig
        config = ShareConfig(expires_hours=expires_hours)
        return self.doc_share.create_share(item, ShareType.LINK, config)
    
    def create_qr_share(self, item: KnowledgeItem) -> bytes:
        """创建二维码分享"""
        share = self.create_share_link(item)
        return self.doc_share.generate_qr_code(share)
    
    # ============= 文件存储 =============
    
    async def upload_file(self, data: bytes, filename: str) -> Optional[str]:
        """上传文件到虚拟存储"""
        return await self.virtual_storage.upload_file(
            data, filename, self.user_id
        )
    
    async def download_file(self, file_id: str) -> Optional[bytes]:
        """从虚拟存储下载文件"""
        return await self.virtual_storage.download_file(file_id)
    
    # ============= 网络操作 =============
    
    async def connect_to_peer(self, addr: NetworkAddress) -> bool:
        """连接到对等节点"""
        if self.p2p_node:
            return await self.p2p_node.connect_to_peer(addr)
        return False
    
    async def discover_peers(self) -> list[PeerNode]:
        """发现对等节点"""
        if self.relay_client:
            nodes_str = await self.relay_client.find_nodes(self.node_id)
            peers = []
            for node_str in nodes_str:
                parts = node_str.split(':')
                if len(parts) >= 2:
                    peers.append(PeerNode(
                        node_id=parts[0],
                        public_addr=NetworkAddress(ip=parts[1].split(':')[0], port=int(parts[1].split(':')[1]))
                    ))
            return peers
        return []
    
    async def force_sync(self):
        """强制同步"""
        if self.knowledge_sync:
            await self.knowledge_sync.force_sync()
    
    # ============= 状态查询 =============
    
    def get_sync_status(self) -> SyncState:
        """获取同步状态"""
        if self.knowledge_sync:
            return self.knowledge_sync.get_status()
        return SyncState(user_id=self.user_id)
    
    def get_node_stats(self) -> dict:
        """获取节点统计"""
        return {
            "node_id": self.node_id,
            "user_id": self.user_id,
            "nat_type": self.nat_type.name,
            "public_addr": str(self.public_addr) if self.public_addr else None,
            "is_running": self.is_running,
            "peer_count": self.p2p_node.get_peer_count() if self.p2p_node else 0,
            "knowledge_count": len(self.get_all_knowledge()),
            "relay_connected": self.relay_client.is_connected if self.relay_client else False,
            "storage_stats": self.virtual_storage.get_storage_stats() if self.virtual_storage else {},
            "server_stats": self.server_discovery.get_server_stats() if self.server_discovery else {}
        }


# ============= 独立中继服务器 =============

class StandaloneRelayServer:
    """独立中继服务器"""
    
    def __init__(self, host: str = "0.0.0.0", port: int = DEFAULT_RELAY_PORT):
        self.host = host
        self.port = port
        self.server: Optional[RelayService] = None
    
    async def start(self):
        """启动中继服务器"""
        self.server = await create_relay_server(self.host, self.port)
        return self.server
    
    async def stop(self):
        """停止中继服务器"""
        if self.server:
            await self.server.stop()
    
    def get_stats(self) -> dict:
        """获取服务器统计"""
        if self.server:
            return self.server.get_stats()
        return {}


# ============= 便捷函数 =============

async def create_p2p_knowledge_node(
    user_id: str,
    data_dir: Optional[str] = None,
    enable_relay: bool = False
) -> P2PKnowledgeNode:
    """创建P2P知识库节点"""
    node = P2PKnowledgeNode(user_id, data_dir, enable_relay)
    await node.start()
    return node


# ============= 模块导出 =============

__all__ = [
    # 核心类
    'P2PKnowledgeNode',
    'StandaloneRelayServer',
    
    # 子模块
    'P2PNode',
    'NATTraversal',
    'RelayService',
    'RelayClient',
    'KnowledgeSync',
    'KnowledgeDatabase',
    'DocShare',
    'PeerShare',
    'VirtualStorage',
    'ServerDiscovery',
    'ServerElection',
    'VolunteerManager',
    
    # 安全类
    'CryptoManager',
    'IdentityManager',
    'SecureChannel',
    'AccessControl',
    
    # 便捷函数
    'create_p2p_knowledge_node',
    'create_relay_server',
    'create_node',
    'create_local_storage',
    'detect_nat',
    
    # 模型
    'PeerNode',
    'NetworkAddress',
    'KnowledgeItem',
    'SyncState',
    'ShareLink',
    'NatType',
    'NodeRole',
    'ShareType',
]
