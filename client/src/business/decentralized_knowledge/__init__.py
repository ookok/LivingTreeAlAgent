"""
去中心化知识协作系统 - 核心协调器
Decentralized Knowledge Collaboration System
"""

import asyncio
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

from .models import NodeStatus, ConnectionQuality
from .p2p_node import P2PNode
from .knowledge_sync import KnowledgeSyncEngine
from .relay_client import RelayClient
from .identity_manager import IdentityManager, UserIdentity
from .message_system import MessageSystem, Message
from .tencent_sync import TencentSyncEngine
from .collab_editor import CollabEditorHub
from .config_manager import DecentralizedConfig
from .network_monitor import NetworkMonitor, NetworkState

logger = logging.getLogger(__name__)


class SystemMode(Enum):
    """系统运行模式"""
    FULL = "full"           # 完全模式，有服务器支持
    LIGHT = "light"         # 轻量模式，无服务器，纯P2P
    OFFLINE = "offline"     # 完全离线，仅本地功能


@dataclass
class SystemStats:
    """系统统计信息"""
    mode: SystemMode = SystemMode.FULL
    network_state: NetworkState = NetworkState.UNKNOWN
    connection_quality: ConnectionQuality = ConnectionQuality.UNKNOWN
    
    # P2P状态
    peers_connected: int = 0
    peers_max: int = 100
    
    # 消息状态
    messages_pending: int = 0
    messages_sent_today: int = 0
    
    # 同步状态
    sync_last_time: Optional[datetime] = None
    sync_pending: int = 0
    
    # 存储状态
    local_storage_used: int = 0
    local_storage_total: int = 0
    cloud_storage_used: int = 0
    
    # 性能指标
    avg_latency_ms: float = 0.0
    bandwidth_mbps: float = 0.0


class DecentralizedKnowledgeSystem:
    """
    去中心化知识协作系统核心协调器
    
    功能：
    - 多模式运行（完全/轻量/离线）
    - 智能网络状态管理
    - 消息通信
    - 腾讯云同步
    - 实时协同编辑
    - 离线支持
    """
    
    def __init__(self, config: Optional[DecentralizedConfig] = None):
        self.config = config or DecentralizedConfig()
        self._running = False
        
        # 核心组件
        self.identity: Optional[IdentityManager] = None
        self.p2p_node: Optional[P2PNode] = None
        self.knowledge_sync: Optional[KnowledgeSyncEngine] = None
        self.relay_client: Optional[RelayClient] = None
        self.message_system: Optional[MessageSystem] = None
        self.tencent_sync: Optional[TencentSyncEngine] = None
        self.collab_hub: Optional[CollabEditorHub] = None
        self.network_monitor: Optional[NetworkMonitor] = None
        
        # 状态管理
        self._current_mode: SystemMode = SystemMode.FULL
        self._user_identity: Optional[UserIdentity] = None
        
        # 锁
        self._lock = asyncio.Lock()
        
        logger.info("去中心化知识协作系统初始化完成")
    
    @property
    def current_mode(self) -> SystemMode:
        return self._current_mode
    
    @property
    def is_online(self) -> bool:
        return self._current_mode != SystemMode.OFFLINE
    
    async def start(self, user_id: Optional[str] = None) -> bool:
        """启动系统"""
        if self._running:
            logger.warning("系统已在运行中")
            return True
        
        try:
            # 初始化网络监控
            self.network_monitor = NetworkMonitor(self.config)
            
            # 检测初始网络状态
            network_state = await self.network_monitor.check_network_state()
            logger.info(f"网络状态检测: {network_state}")
            
            # 根据网络状态选择运行模式
            await self._determine_mode(network_state)
            
            # 初始化身份系统（最先初始化）
            self.identity = IdentityManager(self.config)
            if user_id:
                self._user_identity = self.identity.load_identity(user_id)
            
            # 初始化P2P节点
            self.p2p_node = P2PNode(
                node_id=self._user_identity.user_id if self._user_identity else None,
                config=self.config
            )
            
            # 根据模式初始化不同组件
            if self._current_mode == SystemMode.FULL:
                await self._start_full_mode()
            elif self._current_mode == SystemMode.LIGHT:
                await self._start_light_mode()
            else:
                await self._start_offline_mode()
            
            # 启动网络监控
            self.network_monitor.add_callback(self._on_network_change)
            asyncio.create_task(self.network_monitor.start_monitoring())
            
            self._running = True
            logger.info(f"系统启动成功，模式: {self._current_mode.value}")
            return True
            
        except Exception as e:
            logger.error(f"系统启动失败: {e}")
            await self.stop()
            return False
    
    async def _determine_mode(self, network_state: NetworkState) -> None:
        """根据网络状态确定运行模式"""
        if network_state == NetworkState.OFFLINE:
            self._current_mode = SystemMode.OFFLINE
        elif network_state in [NetworkState.P2P_ONLY, NetworkState.RELAY_ONLY]:
            self._current_mode = SystemMode.LIGHT
        else:
            self._current_mode = SystemMode.FULL
    
    async def _start_full_mode(self) -> None:
        """启动完全模式"""
        logger.info("启动完全模式...")
        
        # 连接中继服务器
        self.relay_client = RelayClient(self.config)
        await self.relay_client.connect()
        
        # 初始化消息系统
        self.message_system = MessageSystem(
            identity=self.identity,
            p2p_node=self.p2p_node,
            relay_client=self.relay_client
        )
        await self.message_system.start()
        
        # 初始化知识同步引擎
        self.knowledge_sync = KnowledgeSyncEngine(
            p2p_node=self.p2p_node,
            identity=self.identity,
            relay_client=self.relay_client
        )
        await self.knowledge_sync.start()
        
        # 初始化腾讯云同步（如果配置了）
        if self.config.tencent_sync_enabled:
            self.tencent_sync = TencentSyncEngine(
                config=self.config.tencent_sync_config,
                knowledge_base=self.knowledge_sync
            )
            await self.tencent_sync.start()
        
        # 初始化协同编辑中心
        self.collab_hub = CollabEditorHub(
            identity=self.identity,
            p2p_node=self.p2p_node
        )
        await self.collab_hub.start()
    
    async def _start_light_mode(self) -> None:
        """启动轻量模式"""
        logger.info("启动轻量模式...")
        
        # 仅初始化P2P相关组件
        self.knowledge_sync = KnowledgeSyncEngine(
            p2p_node=self.p2p_node,
            identity=self.identity,
            relay_client=None  # 无中继
        )
        await self.knowledge_sync.start()
        
        # 简化消息系统
        self.message_system = MessageSystem(
            identity=self.identity,
            p2p_node=self.p2p_node,
            relay_client=None
        )
        await self.message_system.start()
        
        # 协同编辑（仅本地）
        self.collab_hub = CollabEditorHub(
            identity=self.identity,
            p2p_node=self.p2p_node
        )
        await self.collab_hub.start()
    
    async def _start_offline_mode(self) -> None:
        """启动离线模式"""
        logger.info("启动离线模式...")
        
        # 仅初始化本地组件
        self.knowledge_sync = KnowledgeSyncEngine(
            p2p_node=self.p2p_node,
            identity=self.identity,
            relay_client=None
        )
        await self.knowledge_sync.start()
        
        # 本地消息系统
        self.message_system = MessageSystem(
            identity=self.identity,
            p2p_node=None,
            relay_client=None
        )
        await self.message_system.start()
    
    async def _on_network_change(self, old_state: NetworkState, new_state: NetworkState) -> None:
        """网络状态变化回调"""
        logger.info(f"网络状态变化: {old_state} -> {new_state}")
        
        old_mode = self._current_mode
        await self._determine_mode(new_state)
        
        if old_mode != self._current_mode:
            logger.info(f"系统模式切换: {old_mode.value} -> {self._current_mode.value}")
            
            # 根据模式变化调整组件
            if self._current_mode == SystemMode.FULL and old_mode != SystemMode.FULL:
                await self._upgrade_to_full()
            elif self._current_mode == SystemMode.LIGHT and old_mode == SystemMode.OFFLINE:
                await self._upgrade_to_light()
            elif self._current_mode == SystemMode.OFFLINE:
                await self._downgrade_to_offline()
    
    async def _upgrade_to_full(self) -> None:
        """升级到完全模式"""
        try:
            self.relay_client = RelayClient(self.config)
            await self.relay_client.connect()
            
            if self.tencent_sync and not self.tencent_sync.is_running:
                await self.tencent_sync.start()
                
        except Exception as e:
            logger.error(f"升级到完全模式失败: {e}")
    
    async def _upgrade_to_light(self) -> None:
        """升级到轻量模式"""
        try:
            # 尝试建立P2P连接
            await self.p2p_node.start()
        except Exception as e:
            logger.error(f"升级到轻量模式失败: {e}")
    
    async def _downgrade_to_offline(self) -> None:
        """降级到离线模式"""
        # 断开网络连接
        if self.relay_client:
            await self.relay_client.disconnect()
            self.relay_client = None
        
        logger.info("系统已降级到离线模式")
    
    async def stop(self) -> None:
        """停止系统"""
        if not self._running:
            return
        
        logger.info("正在停止系统...")
        
        # 停止所有组件
        if self.network_monitor:
            await self.network_monitor.stop()
        
        if self.collab_hub:
            await self.collab_hub.stop()
        
        if self.tencent_sync:
            await self.tencent_sync.stop()
        
        if self.message_system:
            await self.message_system.stop()
        
        if self.knowledge_sync:
            await self.knowledge_sync.stop()
        
        if self.relay_client:
            await self.relay_client.disconnect()
        
        if self.p2p_node:
            await self.p2p_node.stop()
        
        self._running = False
        logger.info("系统已停止")
    
    # ============ 身份管理 ============
    
    async def login(self, username: str, password: str) -> Optional[UserIdentity]:
        """用户登录"""
        identity = await self.identity.login(username, password)
        if identity:
            self._user_identity = identity
        return identity
    
    async def register(self, username: str, password: str, 
                       email: Optional[str] = None) -> Optional[UserIdentity]:
        """用户注册"""
        identity = await self.identity.register(username, password, email)
        if identity:
            self._user_identity = identity
        return identity
    
    async def logout(self) -> None:
        """用户登出"""
        if self._user_identity:
            await self.identity.logout(self._user_identity.user_id)
            self._user_identity = None
    
    @property
    def current_user(self) -> Optional[UserIdentity]:
        """获取当前用户"""
        return self._user_identity
    
    # ============ 消息通信 ============
    
    async def send_message(self, recipient: str, content: str,
                          msg_type: str = "text") -> Optional[Message]:
        """发送消息"""
        if not self.message_system:
            return None
        
        return await self.message_system.send_message(
            sender_id=self._user_identity.user_id if self._user_identity else "anonymous",
            recipient_id=recipient,
            content=content,
            msg_type=msg_type
        )
    
    async def get_messages(self, folder: str = "inbox",
                          unread_only: bool = False) -> List[Message]:
        """获取消息"""
        if not self.message_system:
            return []
        
        return await self.message_system.get_messages(
            user_id=self._user_identity.user_id if self._user_identity else "anonymous",
            folder=folder,
            unread_only=unread_only
        )
    
    async def get_pending_messages(self) -> List[Message]:
        """获取待发送消息（用于离线恢复）"""
        if not self.message_system:
            return []
        
        return await self.message_system.get_pending_messages()
    
    # ============ 知识库同步 ============
    
    async def sync_knowledge(self, force: bool = False) -> Dict[str, Any]:
        """触发知识库同步"""
        if not self.knowledge_sync:
            return {"success": False, "reason": "知识同步未初始化"}
        
        return await self.knowledge_sync.sync(force=force)
    
    async def add_knowledge(self, title: str, content: str,
                           tags: Optional[List[str]] = None) -> Optional[str]:
        """添加知识条目"""
        if not self.knowledge_sync:
            return None
        
        return await self.knowledge_sync.add_entry(
            user_id=self._user_identity.user_id if self._user_identity else "anonymous",
            title=title,
            content=content,
            tags=tags
        )
    
    async def search_knowledge(self, query: str) -> List[Dict[str, Any]]:
        """搜索知识库"""
        if not self.knowledge_sync:
            return []
        
        return await self.knowledge_sync.search(query)
    
    # ============ 腾讯云同步 ============
    
    async def sync_to_tencent(self) -> Dict[str, Any]:
        """同步到腾讯云"""
        if not self.tencent_sync:
            return {"success": False, "reason": "腾讯云同步未启用"}
        
        return await self.tencent_sync.sync_to_cloud()
    
    async def sync_from_tencent(self) -> Dict[str, Any]:
        """从腾讯云同步"""
        if not self.tencent_sync:
            return {"success": False, "reason": "腾讯云同步未启用"}
        
        return await self.tencent_sync.sync_from_cloud()
    
    # ============ 协同编辑 ============
    
    async def create_collab_doc(self, title: str, 
                               initial_content: str = "") -> Optional[str]:
        """创建协同文档"""
        if not self.collab_hub:
            return None
        
        return await self.collab_hub.create_document(
            owner_id=self._user_identity.user_id if self._user_identity else "anonymous",
            title=title,
            initial_content=initial_content
        )
    
    async def join_collab(self, doc_id: str) -> bool:
        """加入协同编辑"""
        if not self.collab_hub:
            return False
        
        return await self.collab_hub.join_document(
            doc_id=doc_id,
            user_id=self._user_identity.user_id if self._user_identity else "anonymous"
        )
    
    async def create_invite_link(self, doc_id: str, 
                                 permission: str = "edit") -> Optional[str]:
        """创建邀请链接"""
        if not self.collab_hub:
            return None
        
        return await self.collab_hub.create_invite_link(
            doc_id=doc_id,
            owner_id=self._user_identity.user_id if self._user_identity else "anonymous",
            permission=permission
        )
    
    # ============ 系统状态 ============
    
    def get_stats(self) -> SystemStats:
        """获取系统统计信息"""
        stats = SystemStats(
            mode=self._current_mode,
            network_state=self.network_monitor.state if self.network_monitor else NetworkState.UNKNOWN,
        )
        
        if self.p2p_node:
            stats.peers_connected = len(self.p2p_node.get_peers())
        
        if self.message_system:
            pending, sent = self.message_system.get_stats()
            stats.messages_pending = pending
            stats.messages_sent_today = sent
        
        if self.knowledge_sync:
            sync_stats = self.knowledge_sync.get_sync_stats()
            stats.sync_last_time = sync_stats.get("last_sync")
            stats.sync_pending = sync_stats.get("pending_count", 0)
        
        if self.network_monitor:
            stats.connection_quality = self.network_monitor.get_connection_quality()
            stats.avg_latency_ms = self.network_monitor.get_avg_latency()
        
        return stats
    
    def get_capabilities(self) -> Dict[str, bool]:
        """获取当前模式支持的功能"""
        return {
            "p2p_connection": self._current_mode != SystemMode.OFFLINE,
            "relay_server": self._current_mode == SystemMode.FULL,
            "cloud_sync": self._current_mode == SystemMode.FULL and self.tencent_sync is not None,
            "message_send": True,  # 离线也有发件箱
            "message_receive": self._current_mode != SystemMode.OFFLINE,
            "collaborative_edit": self._current_mode != SystemMode.OFFLINE,
            "offline_mode": True,
            "local_storage": True,
        }


# ============ 便捷函数 ============

async def create_decentralized_system(
    user_id: Optional[str] = None,
    config: Optional[DecentralizedConfig] = None
) -> DecentralizedKnowledgeSystem:
    """创建去中心化知识系统实例"""
    system = DecentralizedKnowledgeSystem(config)
    await system.start(user_id)
    return system
