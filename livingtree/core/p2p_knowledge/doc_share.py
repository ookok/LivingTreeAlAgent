"""
文档分享系统

实现短链接、二维码分享和P2P直连分享
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import logging
try:
    import qrcode
except ImportError:
    qrcode = None
import uuid
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Optional

from .models import ShareLink, ShareType, KnowledgeItem, DEFAULT_RELAY_PORT

logger = logging.getLogger(__name__)


@dataclass
class ShareConfig:
    """分享配置"""
    expires_hours: int = 168  # 默认7天
    max_access_count: Optional[int] = None
    require_password: bool = False
    allow_download: bool = True
    allow_preview: bool = True


class ShortLinkGenerator:
    """短链接生成器"""
    
    BASE62_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    
    def __init__(self, base_url: str = "https://relay.example.com"):
        self.base_url = base_url
        self._cache: dict[str, ShareLink] = {}
    
    def generate_code(self, item_id: str, user_id: str) -> str:
        """生成短码"""
        raw = f"{item_id}:{user_id}:{uuid.uuid4().hex}"
        hash_val = int(hashlib.sha1(raw.encode()).hexdigest()[:12], 16)
        
        code = ""
        for _ in range(8):
            code = self.BASE62_CHARS[hash_val % 62] + code
            hash_val //= 62
        
        return code
    
    def create_link(self, share_code: str) -> str:
        """创建完整短链接"""
        return f"{self.base_url}/s/{share_code}"
    
    def parse_link(self, link: str) -> Optional[str]:
        """解析短链接获取分享码"""
        if "/s/" in link:
            parts = link.split("/s/")
            if len(parts) == 2:
                return parts[1].split('?')[0]
        return None


class QRCodeGenerator:
    """二维码生成器"""
    
    def __init__(self, size: int = 300, border: int = 4):
        self.size = size
        self.border = border
    
    def generate(self, content: str) -> bytes:
        """生成二维码图片"""
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=self.border,
        )
        qr.add_data(content)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        img = img.resize((self.size, self.size))
        
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        return buffer.getvalue()
    
    def generate_sharing_qr(
        self,
        relay_server: str,
        share_code: str,
        password: Optional[str] = None
    ) -> bytes:
        """生成分享专用二维码"""
        # 编码协议内容
        protocol = "p2pks://"
        path = f"{relay_server}/s/{share_code}"
        
        if password:
            # 简单密码编码
            pwd_hash = base64.urlsafe_b64encode(password.encode()).decode()
            path += f"?pwd={pwd_hash}"
        
        return self.generate(f"{protocol}{path}")


class DocShare:
    """文档分享服务"""
    
    def __init__(
        self,
        user_id: str,
        base_url: str = "https://relay.example.com",
        db_path: Optional[str] = None
    ):
        self.user_id = user_id
        self.base_url = base_url
        
        self.short_link_gen = ShortLinkGenerator(base_url)
        self.qr_gen = QRCodeGenerator()
        
        # 分享存储
        self.shares: dict[str, ShareLink] = {}
        
        # 配置
        self.default_config = ShareConfig()
        
        # 可选的中继服务器
        self.relay_server: Optional[tuple[str, int]] = None
        
        logger.info(f"DocShare initialized for user {user_id}")
    
    def set_relay_server(self, host: str, port: int = DEFAULT_RELAY_PORT):
        """设置中继服务器"""
        self.relay_server = (host, port)
    
    def create_share(
        self,
        item: KnowledgeItem,
        share_type: ShareType = ShareType.LINK,
        config: Optional[ShareConfig] = None
    ) -> ShareLink:
        """创建分享链接"""
        config = config or self.default_config
        
        # 生成分享码
        share_code = self.short_link_gen.generate_code(item.item_id, self.user_id)
        
        # 计算过期时间
        expires_at = None
        if config.expires_hours > 0:
            import time
            expires_at = time.time() + config.expires_hours * 3600
        
        # 创建分享链接
        share = ShareLink(
            share_code=share_code,
            item_id=item.item_id,
            user_id=self.user_id,
            share_type=share_type,
            expires_at=expires_at,
            max_access_count=config.max_access_count,
            password=uuid.uuid4().hex[:8] if config.require_password else None,
            is_active=True
        )
        
        self.shares[share_code] = share
        
        logger.info(f"Created share: {share_code} for item {item.item_id}")
        return share
    
    def get_share(self, share_code: str) -> Optional[ShareLink]:
        """获取分享信息"""
        share = self.shares.get(share_code)
        
        if share and share.is_expired():
            share.is_active = False
        
        return share if share and share.is_active else None
    
    def access_share(self, share_code: str, password: Optional[str] = None) -> Optional[KnowledgeItem]:
        """访问分享"""
        share = self.get_share(share_code)
        
        if not share:
            return None
        
        # 验证密码
        if share.password and share.password != password:
            return None
        
        # 检查访问次数
        if share.max_access_count and share.access_count >= share.max_access_count:
            return None
        
        # 增加访问计数
        share.access_count += 1
        
        logger.info(f"Share accessed: {share_code}, count: {share.access_count}")
        
        # 返回知识条目（实际需要从知识库获取）
        return KnowledgeItem(
            item_id=share.item_id,
            user_id=share.user_id,
            title="Shared Item",
            content=""
        )
    
    def revoke_share(self, share_code: str) -> bool:
        """撤销分享"""
        if share_code in self.shares:
            self.shares[share_code].is_active = False
            logger.info(f"Share revoked: {share_code}")
            return True
        return False
    
    def get_user_shares(self) -> list[ShareLink]:
        """获取用户的所有分享"""
        return [
            s for s in self.shares.values()
            if s.user_id == self.user_id and s.is_active
        ]
    
    def cleanup_expired(self):
        """清理过期的分享"""
        expired = [
            code for code, share in self.shares.items()
            if share.is_expired()
        ]
        
        for code in expired:
            self.shares[code].is_active = False
        
        return len(expired)
    
    def generate_short_link(self, share: ShareLink) -> str:
        """生成短链接"""
        return self.short_link_gen.create_link(share.share_code)
    
    def generate_qr_code(self, share: ShareLink, password: Optional[str] = None) -> bytes:
        """生成二维码"""
        relay = self.relay_server[0] if self.relay_server else self.base_url
        
        if self.relay_server:
            relay = f"{relay}:{self.relay_server[1]}"
        
        return self.qr_gen.generate_sharing_qr(relay, share.share_code, password)


class PeerShare:
    """P2P直连分享"""
    
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.pending_shares: dict[str, dict] = {}
        self._share_queue: asyncio.Queue = asyncio.Queue()
    
    async def initiate_share(
        self,
        target_node_id: str,
        item: KnowledgeItem,
        transfer_data: bytes
    ) -> str:
        """发起P2P分享"""
        share_id = uuid.uuid4().hex[:12]
        
        self.pending_shares[share_id] = {
            "item": item.to_dict(),
            "data": transfer_data,
            "target": target_node_id,
            "status": "pending"
        }
        
        logger.info(f"Initiated P2P share {share_id} to {target_node_id}")
        return share_id
    
    async def send_share_request(self, target_node_id: str, item_id: str) -> bool:
        """发送分享请求"""
        logger.info(f"Sending share request to {target_node_id} for {item_id}")
        # 实际需要通过P2P网络发送
        return True
    
    async def receive_share(
        self,
        share_id: str,
        item: KnowledgeItem,
        data: bytes
    ):
        """接收分享"""
        await self._share_queue.put({
            "share_id": share_id,
            "item": item,
            "data": data
        })
    
    async def get_next_share(self, timeout: float = 30) -> Optional[dict]:
        """获取下一个待接收的分享"""
        try:
            return await asyncio.wait_for(self._share_queue.get(), timeout)
        except asyncio.TimeoutError:
            return None
    
    def get_pending_share(self, share_id: str) -> Optional[dict]:
        """获取待处理的分享"""
        return self.pending_shares.get(share_id)
    
    def complete_share(self, share_id: str):
        """标记分享完成"""
        if share_id in self.pending_shares:
            self.pending_shares[share_id]["status"] = "completed"
    
    def cancel_share(self, share_id: str):
        """取消分享"""
        if share_id in self.pending_shares:
            self.pending_shares[share_id]["status"] = "cancelled"
            del self.pending_shares[share_id]


class ShareLinkServer:
    """分享链接解析服务器（运行在中继服务器上）"""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8080):
        self.host = host
        self.port = port
        self.server: Optional[asyncio.Server] = None
        self.running = False
        
        # 分享码到节点信息的映射
        self.share_registry: dict[str, dict] = {}
    
    async def start(self):
        """启动服务器"""
        self.running = True
        
        async def handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
            addr = writer.get_extra_info('peername')
            
            try:
                request = await reader.read(1024)
                request_line = request.decode().split('\r\n')[0]
                
                if '/s/' in request_line:
                    # 解析分享码
                    parts = request_line.split('/s/')
                    if len(parts) == 2:
                        share_code = parts[1].split()[0]
                        await self._handle_share_request(share_code, writer)
                    else:
                        writer.write(b"HTTP/1.1 400 Bad Request\r\n\r\n")
                else:
                    writer.write(b"HTTP/1.1 404 Not Found\r\n\r\n")
                
            except Exception as e:
                logger.error(f"Share server error: {e}")
            finally:
                writer.close()
                await writer.wait_closed()
        
        self.server = await asyncio.start_server(handler, self.host, self.port)
        logger.info(f"Share link server started on {self.host}:{self.port}")
    
    async def stop(self):
        """停止服务器"""
        self.running = False
        if self.server:
            self.server.close()
            await self.server.wait_closed()
    
    async def register_share(
        self,
        share_code: str,
        item_id: str,
        node_info: dict
    ):
        """注册分享"""
        self.share_registry[share_code] = {
            "item_id": item_id,
            "node_info": node_info,
            "registered_at": asyncio.get_event_loop().time()
        }
    
    async def _handle_share_request(self, share_code: str, writer: asyncio.StreamWriter):
        """处理分享请求"""
        if share_code not in self.share_registry:
            response = b"HTTP/1.1 404 Not Found\r\nContent-Type: text/html\r\n\r\n<html><body><h1>Share not found</h1></body></html>"
            writer.write(response)
            return
        
        share_info = self.share_registry[share_code]
        
        # 返回分享信息
        response_body = f"""{{"item_id": "{share_info['item_id']}", "node": "{share_info['node_info']}"}}"""
        response = (
            f"HTTP/1.1 200 OK\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(response_body)}\r\n"
            f"\r\n"
        ).encode() + response_body.encode()
        
        writer.write(response)
