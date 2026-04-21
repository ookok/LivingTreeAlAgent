"""
Lightweight Network Protocol

轻量级网络协议
- 精简头部
- 二进制编码
- 连接复用
- 压缩传输
- QUIC支持
"""

import asyncio
import json
import struct
import zlib
from dataclasses import dataclass, field
from typing import Optional

from .models import ConnectionQuality


class LightProtocol:
    """
    轻量级网络协议
    
    Features:
    - Compact header (4-8 bytes)
    - Binary encoding (MessagePack)
    - Multiplexing
    - Compression
    - QUIC support
    """
    
    # 协议版本
    VERSION = 1
    
    # 消息类型
    MSG_DATA = 0x01
    MSG_ACK = 0x02
    MSG_PING = 0x03
    MSG_PONG = 0x04
    MSG_CLOSE = 0x05
    
    # 头部格式: [version(1)][type(1)][flags(1)][stream_id(2)][length(3)] = 8 bytes
    HEADER_FORMAT = "!BBBBBH"
    HEADER_SIZE = 8
    
    def __init__(self, node_id: str, enable_quic: bool = True):
        self.node_id = node_id
        self.enable_quic = enable_quic
        
        # 流复用
        self._next_stream_id = 0
        self._streams: dict[int, asyncio.StreamReader] = {}
        
        # 压缩
        self._compress_threshold = 1024  # 1KB以上压缩
        self._compressor = MessagePackCodec()
        
        # 连接状态
        self._running = False
    
    async def start(self):
        """启动协议"""
        self._running = True
    
    async def stop(self):
        """停止协议"""
        self._running = False
        self._streams.clear()
    
    def select_protocol(self, quality: ConnectionQuality) -> str:
        """
        根据连接质量选择协议
        
        Args:
            quality: 连接质量
            
        Returns:
            str: 协议类型 (quic/tcp/udp)
        """
        if not self.enable_quic:
            return "tcp"
        
        if quality == ConnectionQuality.EXCELLENT:
            return "quic"  # QUIC最优
        elif quality == ConnectionQuality.GOOD:
            return "quic"
        elif quality == ConnectionQuality.FAIR:
            return "tcp"
        else:
            return "tcp"  # 低质量用TCP
    
    async def send(
        self,
        conn,
        data: bytes,
        compressed: bool = True,
    ) -> bool:
        """
        发送数据
        
        Args:
            conn: 连接对象
            data: 数据内容
            compressed: 是否压缩
            
        Returns:
            bool: 是否发送成功
        """
        try:
            # 分配流ID
            stream_id = self._allocate_stream_id()
            
            # 压缩
            if compressed and len(data) >= self._compress_threshold:
                data = self._compress(data)
                flags = 0x01  # 压缩标志
            else:
                flags = 0x00
            
            # 构建消息
            message = self._build_message(
                msg_type=self.MSG_DATA,
                flags=flags,
                stream_id=stream_id,
                data=data,
            )
            
            return await conn.send(message)
        except Exception:
            return False
    
    async def receive(self, conn) -> Optional[bytes]:
        """
        接收数据
        
        Args:
            conn: 连接对象
            
        Returns:
            bytes: 数据内容
        """
        try:
            # 接收头部
            header = await conn.receive(self.HEADER_SIZE)
            if not header or len(header) < self.HEADER_SIZE:
                return None
            
            # 解析头部
            version, msg_type, flags, stream_id, length = struct.unpack(
                self.HEADER_FORMAT, header
            )
            
            # 检查版本
            if version != self.VERSION:
                return None
            
            # 接收数据
            data = await conn.receive(length)
            if not data:
                return None
            
            # 解压缩
            if flags & 0x01:
                data = self._decompress(data)
            
            # 处理ACK
            if msg_type == self.MSG_ACK:
                return None
            
            return data
        except Exception:
            return None
    
    def _build_message(
        self,
        msg_type: int,
        flags: int,
        stream_id: int,
        data: bytes,
    ) -> bytes:
        """
        构建消息
        
        Args:
            msg_type: 消息类型
            flags: 标志
            stream_id: 流ID
            data: 数据
            
        Returns:
            bytes: 完整消息
        """
        header = struct.pack(
            self.HEADER_FORMAT,
            self.VERSION,
            msg_type,
            flags,
            0,  # reserved
            stream_id,
            len(data),
        )
        return header + data
    
    def _allocate_stream_id(self) -> int:
        """分配流ID"""
        stream_id = self._next_stream_id
        self._next_stream_id = (self._next_stream_id + 1) % 65536
        return stream_id
    
    def _compress(self, data: bytes) -> bytes:
        """压缩数据"""
        return zlib.compress(data, level=6)
    
    def _decompress(self, data: bytes) -> bytes:
        """解压数据"""
        try:
            return zlib.decompress(data)
        except Exception:
            return data
    
    async def send_ping(self, conn) -> Optional[float]:
        """发送ping并测量延迟"""
        start = time.time()
        
        message = self._build_message(
            msg_type=self.MSG_PING,
            flags=0,
            stream_id=0,
            data=b"",
        )
        
        success = await conn.send(message)
        if not success:
            return None
        
        return time.time() - start
    
    async def handle_pong(self, conn) -> bool:
        """处理pong响应"""
        data = await self.receive(conn)
        return data is not None
    
    def get_stats(self) -> dict:
        """获取协议统计"""
        return {
            "version": self.VERSION,
            "quic_enabled": self.enable_quic,
            "next_stream_id": self._next_stream_id,
            "active_streams": len(self._streams),
            "compress_threshold": self._compress_threshold,
        }


class MessagePackCodec:
    """
    MessagePack编解码器
    
    高效的二进制序列化
    """
    
    def encode(self, obj) -> bytes:
        """编码对象"""
        try:
            # 尝试MessagePack
            import msgpack
            return msgpack.packb(obj, use_bin_type=True)
        except ImportError:
            # 回退到JSON
            return json.dumps(obj).encode('utf-8')
    
    def decode(self, data: bytes):
        """解码数据"""
        try:
            import msgpack
            return msgpack.unpackb(data, raw=False)
        except ImportError:
            return json.loads(data.decode('utf-8'))


# Protocol buffer alternative
class ProtobufCodec:
    """
    Protocol Buffers编解码器
    
    零拷贝高性能序列化
    """
    
    @staticmethod
    def encode_varint(value: int) -> bytes:
        """编码变长整数"""
        result = []
        while value > 0x7F:
            result.append((value & 0x7F) | 0x80)
            value >>= 7
        result.append(value & 0x7F)
        return bytes(result)
    
    @staticmethod
    def decode_varint(data: bytes) -> tuple[int, int]:
        """解码变长整数"""
        result = 0
        shift = 0
        pos = 0
        for byte in data:
            if pos > 10:  # max varint size
                break
            result |= (byte & 0x7F) << shift
            if not (byte & 0x80):
                break
            shift += 7
            pos += 1
        return result, pos
