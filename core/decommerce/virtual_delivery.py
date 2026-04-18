"""
P2P 去中心化电商 - 虚物P2P交付
Virtual Goods P2P Delivery

虚物与服务通过P2P直连交付:
- 文件/游戏: WebRTC DataChannel / P2P传输 (croc协议)
- AI/远程: WebRTC音视频 + DataChannel传Hermes指令

交付过程:
1. 卖家发起交付 → 生成分发哈希
2. 买家确认接收 → 建立P2P连接
3. 数据传输 → 实时进度
4. 完成交付 → 双方签名确认
5. 交付哈希存证 → 触发结算
"""

from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import logging
import time
import uuid
import hashlib
import json

logger = logging.getLogger(__name__)


class DeliveryType(Enum):
    """交付类型"""
    FILE = "file"                 # 文件传输
    AI_SERVICE = "ai_service"     # AI服务调用
    REMOTE_SESSION = "remote_session"  # 远程桌面/协助
    STREAM = "stream"           # 视频/音频流


class DeliveryStatus(Enum):
    """交付状态"""
    INITIATED = "initiated"       # 交付发起
    TRANSFERRING = "transferring"  # 传输中
    COMPLETED = "completed"       # 交付完成
    FAILED = "failed"            # 交付失败
    CANCELLED = "cancelled"     # 已取消


@dataclass
class DeliveryManifest:
    """交付清单"""
    # 基础信息
    delivery_id: str = ""
    order_id: str = ""

    # 交付类型
    delivery_type: DeliveryType = DeliveryType.FILE

    # 内容信息
    content_name: str = ""        # 文件名/服务名
    content_size: int = 0         # 字节数
    content_hash: str = ""       # SHA256哈希
    content_type: str = ""       # MIME类型

    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)

    # 传输参数
    chunk_size: int = 16384      # 16KB分块
    priority: int = 1             # 传输优先级
    max_concurrent: int = 3       # 最大并发块数

    # 时间戳
    created_at: float = 0
    expires_at: float = 0        # 交付过期时间

    def compute_hash(self) -> str:
        """计算清单哈希"""
        content = f"{self.delivery_id}|{self.content_name}|{self.content_size}|{self.content_hash}"
        return hashlib.sha256(content.encode()).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "delivery_id": self.delivery_id,
            "order_id": self.order_id,
            "delivery_type": self.delivery_type.value,
            "content_name": self.content_name,
            "content_size": self.content_size,
            "content_hash": self.content_hash,
            "content_type": self.content_type,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
        }


@dataclass
class DeliveryProgress:
    """传输进度"""
    delivery_id: str = ""

    # 进度
    bytes_transferred: int = 0
    total_bytes: int = 0
    chunks_received: int = 0
    total_chunks: int = 0

    # 状态
    status: DeliveryStatus = DeliveryStatus.INITIATED

    # 性能
    speed_bps: float = 0         # 字节/秒
    eta_seconds: float = 0        # 预计剩余时间

    # 错误
    error: Optional[str] = None
    retry_count: int = 0

    # 时间
    started_at: float = 0
    last_updated: float = 0

    @property
    def percent(self) -> float:
        if self.total_bytes == 0:
            return 0
        return self.bytes_transferred / self.total_bytes * 100

    def to_dict(self) -> Dict[str, Any]:
        return {
            "delivery_id": self.delivery_id,
            "bytes_transferred": self.bytes_transferred,
            "total_bytes": self.total_bytes,
            "percent": self.percent,
            "status": self.status.value,
            "speed_bps": self.speed_bps,
            "eta_seconds": self.eta_seconds,
            "error": self.error,
        }


@dataclass
class DeliveryConfirmation:
    """交付确认 (双向签名)"""
    delivery_id: str = ""

    # 卖家确认
    seller_confirmed: bool = False
    seller_hash: str = ""        # 交付内容哈希确认
    seller_signature: str = ""
    seller_confirmed_at: float = 0

    # 买家确认
    buyer_confirmed: bool = False
    buyer_hash: str = ""         # 接收内容哈希确认
    buyer_signature: str = ""
    buyer_confirmed_at: float = 0

    # 最终交付哈希
    final_delivery_hash: str = ""

    def is_fully_confirmed(self) -> bool:
        return self.seller_confirmed and self.buyer_confirmed

    def to_dict(self) -> Dict[str, Any]:
        return {
            "delivery_id": self.delivery_id,
            "seller_confirmed": self.seller_confirmed,
            "seller_hash": self.seller_hash,
            "seller_signature": self.seller_signature,
            "seller_confirmed_at": self.seller_confirmed_at,
            "buyer_confirmed": self.buyer_confirmed,
            "buyer_hash": self.buyer_hash,
            "buyer_signature": self.buyer_signature,
            "buyer_confirmed_at": self.buyer_confirmed_at,
            "final_delivery_hash": self.final_delivery_hash,
        }


class VirtualDeliverySession:
    """
    虚物交付会话

    管理一次P2P虚物交付的完整生命周期
    """

    def __init__(self, delivery_id: str):
        self.delivery_id = delivery_id

        # 清单
        self.manifest: Optional[DeliveryManifest] = None

        # 进度
        self.progress = DeliveryProgress(delivery_id=delivery_id)

        # 确认
        self.confirmation: Optional[DeliveryConfirmation] = None

        # P2P传输
        self._transport = None  # DataChannelTransport
        self._file_chunks: Dict[int, bytes] = {}  # chunk_index -> data

        # 回调
        self._on_progress: List[Callable] = []
        self._on_completed: List[Callable] = []
        self._on_error: List[Callable] = []

        logger.info(f"[VirtualDelivery] Created session {delivery_id}")

    def set_manifest(self, manifest: DeliveryManifest) -> None:
        """设置交付清单"""
        self.manifest = manifest
        self.progress.total_bytes = manifest.content_size
        self.progress.total_chunks = (manifest.content_size + manifest.chunk_size - 1) // manifest.chunk_size
        self.progress.status = DeliveryStatus.INITIATED
        self.progress.started_at = time.time()

    async def start_transfer(self) -> bool:
        """开始传输"""
        if not self.manifest:
            return False

        self.progress.status = DeliveryStatus.TRANSFERRING
        self.progress.last_updated = time.time()

        logger.info(f"[VirtualDelivery] Started transfer {self.delivery_id}")
        return True

    async def receive_chunk(self, chunk_index: int, data: bytes) -> bool:
        """接收分块"""
        if not self.manifest:
            return False

        self._file_chunks[chunk_index] = data
        self.progress.chunks_received += 1
        self.progress.bytes_transferred += len(data)

        # 计算速度
        elapsed = time.time() - self.progress.started_at
        if elapsed > 0:
            self.progress.speed_bps = self.progress.bytes_transferred / elapsed

        # 计算ETA
        if self.progress.speed_bps > 0:
            remaining = self.progress.total_bytes - self.progress.bytes_transferred
            self.progress.eta_seconds = remaining / self.progress.speed_bps

        self.progress.last_updated = time.time()

        # 触发进度回调
        for cb in self._on_progress:
            try:
                if asyncio.iscoroutinefunction(cb):
                    await cb(self.progress)
                else:
                    cb(self.progress)
            except Exception as e:
                logger.error(f"[VirtualDelivery] Progress callback error: {e}")

        # 检查是否完成
        if self.progress.chunks_received >= self.progress.total_chunks:
            await self._complete_transfer()

        return True

    async def _complete_transfer(self) -> None:
        """完成传输"""
        # 组装文件
        if self.manifest.delivery_type == DeliveryType.FILE:
            complete_data = b""
            for i in range(self.progress.total_chunks):
                if i in self._file_chunks:
                    complete_data += self._file_chunks[i]

            # 验证哈希
            computed_hash = hashlib.sha256(complete_data).hexdigest()
            if computed_hash != self.manifest.content_hash:
                self.progress.status = DeliveryStatus.FAILED
                self.progress.error = "Hash mismatch"
                logger.error(f"[VirtualDelivery] Hash mismatch for {self.delivery_id}")
                return

        # 创建确认
        self.confirmation = DeliveryConfirmation(delivery_id=self.delivery_id)

        # 卖家签名 (确认内容正确)
        self.confirmation.seller_hash = self.manifest.content_hash
        self.confirmation.seller_confirmed = True
        self.confirmation.seller_confirmed_at = time.time()

        self.progress.status = DeliveryStatus.COMPLETED

        logger.info(f"[VirtualDelivery] Completed transfer {self.delivery_id}")

        # 触发完成回调
        for cb in self._on_completed:
            try:
                if asyncio.iscoroutinefunction(cb):
                    await cb(self.delivery_id, self.confirmation)
                else:
                    cb(self.delivery_id, self.confirmation)
            except Exception as e:
                logger.error(f"[VirtualDelivery] Completed callback error: {e}")

    def buyer_confirm(self, received_hash: str) -> bool:
        """买家确认接收"""
        if not self.confirmation:
            return False

        self.confirmation.buyer_hash = received_hash
        self.confirmation.buyer_confirmed = True
        self.confirmation.buyer_confirmed_at = time.time()

        # 计算最终交付哈希
        content = f"{self.delivery_id}|{self.confirmation.seller_hash}|{received_hash}"
        self.confirmation.final_delivery_hash = hashlib.sha256(content.encode()).hexdigest()

        logger.info(f"[VirtualDelivery] Buyer confirmed {self.delivery_id}")

        return True

    def cancel(self, reason: str = "") -> None:
        """取消传输"""
        self.progress.status = DeliveryStatus.CANCELLED
        self.progress.error = reason
        self._file_chunks.clear()

        logger.info(f"[VirtualDelivery] Cancelled {self.delivery_id}: {reason}")

    def on_progress(self, callback: Callable) -> None:
        """监听进度"""
        self._on_progress.append(callback)

    def on_completed(self, callback: Callable) -> None:
        """监听完成"""
        self._on_completed.append(callback)

    def on_error(self, callback: Callable) -> None:
        """监听错误"""
        self._on_error.append(callback)


class VirtualDeliveryManager:
    """
    虚物交付管理器

    功能:
    1. 创建和管理交付会话
    2. 支持多种交付类型 (文件/AI服务/远程/流)
    3. P2P传输集成 (DataChannel/croc)
    4. 交付确认与存证
    """

    def __init__(self):
        # 交付会话
        self._sessions: Dict[str, VirtualDeliverySession] = {}

        # 活跃传输
        self._active_transfers: Dict[str, Dict[str, Any]] = {}

        # 回调
        self._on_delivery_started: List[Callable] = []
        self._on_delivery_completed: List[Callable] = []

        logger.info("[VirtualDelivery] Initialized")

    # ==================== 文件交付 ====================

    async def create_file_delivery(
        self,
        order_id: str,
        file_path: str,
        file_name: str,
        file_size: int,
        content_type: str = "application/octet-stream",
    ) -> DeliveryManifest:
        """创建文件交付清单"""
        delivery_id = str(uuid.uuid4())[:12]

        # 计算文件哈希 (分块读取)
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha256.update(chunk)

        manifest = DeliveryManifest(
            delivery_id=delivery_id,
            order_id=order_id,
            delivery_type=DeliveryType.FILE,
            content_name=file_name,
            content_size=file_size,
            content_hash=sha256.hexdigest(),
            content_type=content_type,
            created_at=time.time(),
            expires_at=time.time() + 3600,  # 1小时过期
        )

        # 创建会话
        session = VirtualDeliverySession(delivery_id)
        session.set_manifest(manifest)
        self._sessions[delivery_id] = session

        logger.info(f"[VirtualDelivery] Created file delivery {delivery_id}: {file_name}")

        return manifest

    async def create_ai_service_delivery(
        self,
        order_id: str,
        service_name: str,
        service_params: Dict[str, Any],
    ) -> DeliveryManifest:
        """创建AI服务交付清单"""
        delivery_id = str(uuid.uuid4())[:12]

        # 生成服务参数哈希
        params_json = json.dumps(service_params, sort_keys=True)
        params_hash = hashlib.sha256(params_json.encode()).hexdigest()

        manifest = DeliveryManifest(
            delivery_id=delivery_id,
            order_id=order_id,
            delivery_type=DeliveryType.AI_SERVICE,
            content_name=service_name,
            content_size=len(params_json),  # 参数大小作为"内容大小"
            content_hash=params_hash,
            metadata=service_params,
            created_at=time.time(),
            expires_at=time.time() + 300,  # 5分钟过期
        )

        session = VirtualDeliverySession(delivery_id)
        session.set_manifest(manifest)
        self._sessions[delivery_id] = session

        logger.info(f"[VirtualDelivery] Created AI service delivery {delivery_id}: {service_name}")

        return manifest

    async def create_remote_session_delivery(
        self,
        order_id: str,
        session_type: str,  # desktop / terminal / app
        session_params: Dict[str, Any],
    ) -> DeliveryManifest:
        """创建远程会话交付清单"""
        delivery_id = str(uuid.uuid4())[:12]

        params_json = json.dumps({"session_type": session_type, **session_params}, sort_keys=True)
        params_hash = hashlib.sha256(params_json.encode()).hexdigest()

        manifest = DeliveryManifest(
            delivery_id=delivery_id,
            order_id=order_id,
            delivery_type=DeliveryType.REMOTE_SESSION,
            content_name=f"Remote {session_type}",
            content_size=len(params_json),
            content_hash=params_hash,
            metadata=session_params,
            created_at=time.time(),
            expires_at=time.time() + 3600,
        )

        session = VirtualDeliverySession(delivery_id)
        session.set_manifest(manifest)
        self._sessions[delivery_id] = session

        logger.info(f"[VirtualDelivery] Created remote session delivery {delivery_id}: {session_type}")

        return manifest

    # ==================== P2P传输 ====================

    async def initiate_p2p_transfer(
        self,
        delivery_id: str,
        seller_peer_id: str,
        buyer_peer_id: str,
        relay_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """发起P2P传输"""
        session = self._sessions.get(delivery_id)
        if not session or not session.manifest:
            raise ValueError(f"Delivery session not found: {delivery_id}")

        # 创建传输记录
        transfer = {
            "delivery_id": delivery_id,
            "seller_peer_id": seller_peer_id,
            "buyer_peer_id": buyer_peer_id,
            "relay_config": relay_config or {},
            "started_at": time.time(),
            "status": "initiated",
        }

        self._active_transfers[delivery_id] = transfer

        # 触发回调
        for cb in self._on_delivery_started:
            try:
                if asyncio.iscoroutinefunction(cb):
                    await cb(delivery_id, transfer)
                else:
                    cb(delivery_id, transfer)
            except Exception as e:
                logger.error(f"[VirtualDelivery] Started callback error: {e}")

        return {
            "delivery_id": delivery_id,
            "manifest": session.manifest.to_dict(),
            "peer_info": {
                "seller": seller_peer_id,
                "buyer": buyer_peer_id,
            },
            "relay_config": relay_config,
        }

    async def transmit_via_datachannel(
        self,
        delivery_id: str,
        datachannel,
    ) -> bool:
        """通过DataChannel传输 (用于AI服务/远程会话)"""
        session = self._sessions.get(delivery_id)
        if not session or not session.manifest:
            return False

        manifest = session.manifest

        if manifest.delivery_type == DeliveryType.AI_SERVICE:
            # AI服务: 传输参数JSON
            params_json = json.dumps(manifest.metadata, ensure_ascii=False)
            await datachannel.send(params_json.encode())

            # 等待结果
            result = await datachannel.receive()
            session.progress.bytes_transferred = len(params_json)
            session.progress.status = DeliveryStatus.COMPLETED

            logger.info(f"[VirtualDelivery] AI service delivered {delivery_id}")
            return True

        elif manifest.delivery_type == DeliveryType.REMOTE_SESSION:
            # 远程会话: 传输会话参数
            params_json = json.dumps(manifest.metadata, ensure_ascii=False)
            await datachannel.send(params_json.encode())

            logger.info(f"[VirtualDelivery] Remote session params delivered {delivery_id}")
            return True

        return False

    async def transmit_via_stream(
        self,
        delivery_id: str,
        stream_reader,
    ) -> bool:
        """通过流式传输 (用于大文件)"""
        session = self._sessions.get(delivery_id)
        if not session or not session.manifest:
            return False

        manifest = session.manifest
        chunk_size = manifest.chunk_size
        total_chunks = manifest.total_chunks

        await session.start_transfer()

        for i in range(total_chunks):
            chunk = await stream_reader.read(chunk_size)
            if not chunk:
                break

            await session.receive_chunk(i, chunk)

        return session.progress.status == DeliveryStatus.COMPLETED

    # ==================== 交付确认 ====================

    async def confirm_delivery(
        self,
        delivery_id: str,
        role: str,  # "seller" or "buyer"
        signature: str,
    ) -> DeliveryConfirmation:
        """确认交付"""
        session = self._sessions.get(delivery_id)
        if not session or not session.confirmation:
            raise ValueError(f"Delivery session not found or not completed: {delivery_id}")

        confirmation = session.confirmation

        if role == "seller":
            confirmation.seller_signature = signature
            confirmation.seller_confirmed = True

        elif role == "buyer":
            confirmation.buyer_signature = signature
            confirmation.buyer_confirmed = True
            confirmation.buyer_hash = session.manifest.content_hash

        # 如果双方都确认了,计算最终哈希
        if confirmation.is_fully_confirmed():
            content = f"{delivery_id}|{confirmation.seller_hash}|{confirmation.buyer_hash}"
            confirmation.final_delivery_hash = hashlib.sha256(content.encode()).hexdigest()

            logger.info(f"[VirtualDelivery] Delivery fully confirmed {delivery_id}")

            # 触发完成回调
            for cb in self._on_delivery_completed:
                try:
                    if asyncio.iscoroutinefunction(cb):
                        await cb(delivery_id, confirmation)
                    else:
                        cb(delivery_id, confirmation)
                except Exception as e:
                    logger.error(f"[VirtualDelivery] Completed callback error: {e}")

        return confirmation

    # ==================== 交付存证 ====================

    def create_delivery_proof(self, delivery_id: str) -> Optional[Dict[str, Any]]:
        """创建交付证明"""
        session = self._sessions.get(delivery_id)
        if not session or not session.confirmation:
            return None

        confirmation = session.confirmation

        proof = {
            "delivery_id": delivery_id,
            "order_id": session.manifest.order_id,
            "delivery_type": session.manifest.delivery_type.value,
            "content_hash": session.manifest.content_hash,
            "content_name": session.manifest.content_name,
            "content_size": session.manifest.content_size,
            "confirmation": confirmation.to_dict(),
            "created_at": session.manifest.created_at,
            "completed_at": time.time(),
        }

        logger.info(f"[VirtualDelivery] Created delivery proof for {delivery_id}")

        return proof

    # ==================== 查询 ====================

    def get_session(self, delivery_id: str) -> Optional[VirtualDeliverySession]:
        """获取交付会话"""
        return self._sessions.get(delivery_id)

    def get_progress(self, delivery_id: str) -> Optional[Dict[str, Any]]:
        """获取传输进度"""
        session = self._sessions.get(delivery_id)
        if session:
            return session.progress.to_dict()
        return None

    def get_active_deliveries(self) -> List[Dict[str, Any]]:
        """获取活跃的交付"""
        result = []
        for session in self._sessions.values():
            if session.progress.status in (DeliveryStatus.INITIATED, DeliveryStatus.TRANSFERRING):
                result.append({
                    "delivery_id": session.delivery_id,
                    "order_id": session.manifest.order_id if session.manifest else "",
                    "delivery_type": session.manifest.delivery_type.value if session.manifest else "",
                    "content_name": session.manifest.content_name if session.manifest else "",
                    "progress": session.progress.to_dict(),
                })
        return result

    # ==================== 回调 ====================

    def on_delivery_started(self, callback: Callable) -> None:
        """监听交付开始"""
        self._on_delivery_started.append(callback)

    def on_delivery_completed(self, callback: Callable) -> None:
        """监听交付完成"""
        self._on_delivery_completed.append(callback)

    # ==================== 统计 ====================

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        sessions = list(self._sessions.values())

        return {
            "total_sessions": len(sessions),
            "active_transfers": len([s for s in sessions if s.progress.status == DeliveryStatus.TRANSFERRING]),
            "completed": sum(1 for s in sessions if s.progress.status == DeliveryStatus.COMPLETED),
            "failed": sum(1 for s in sessions if s.progress.status == DeliveryStatus.FAILED),
            "by_type": {
                dt.value: sum(1 for s in sessions if s.manifest and s.manifest.delivery_type == dt)
                for dt in DeliveryType
            },
        }


# ==================== 全局实例 ====================

_virtual_delivery: Optional[VirtualDeliveryManager] = None


def get_virtual_delivery() -> VirtualDeliveryManager:
    """获取虚物交付管理器"""
    global _virtual_delivery
    if _virtual_delivery is None:
        _virtual_delivery = VirtualDeliveryManager()
    return _virtual_delivery
