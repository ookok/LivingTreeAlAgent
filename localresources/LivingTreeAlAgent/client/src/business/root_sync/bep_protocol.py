"""
BEP 协议实现 - Block Exchange Protocol

Syncthing 文件同步的核心协议实现，支持：
- 设备发现与握手
- 文件清单交换
- 块请求与响应
- 增量同步
- 压缩传输
"""

import asyncio
import struct
import json
import hashlib
import zlib
import secrets
import time
from typing import Dict, List, Optional, Callable, Tuple, Any
from dataclasses import asdict

from .models import (
    MessageType, FileType, FileManifest, FileInfo,
    DeviceInfo, ClusterConfig, BEPChunk,
    SyncRequest, SyncResponse, DownloadProgress,
    PROTOCOL_VERSION, MAX_BLOCK_SIZE, COMPRESSION_THRESHOLD
)


class BEPProtocol:
    """
    BEP 协议处理器

    负责：
    1. 协议消息的序列化/反序列化
    2. 消息路由
    3. 连接状态管理
    """

    def __init__(self, device_id: str):
        self.device_id = device_id
        self._handlers: Dict[MessageType, Callable] = {}
        self._compression_threshold = COMPRESSION_THRESHOLD

        # 注册默认处理器
        self._register_default_handlers()

    def _register_default_handlers(self):
        """注册默认消息处理器"""
        self._handlers[MessageType.PING] = self._handle_ping
        self._handlers[MessageType.GET_HELLO] = self._handle_get_hello
        self._handlers[MessageType.HELLO_AGAIN] = self._handle_hello_again
        self._handlers[MessageType.CLUSTER_CONFIG] = self._handle_cluster_config
        self._handlers[MessageType.INDEX] = self._handle_index
        self._handlers[MessageType.INDEX_UPDATE] = self._handle_index_update
        self._handlers[MessageType.REQUEST] = self._handle_request
        self._handlers[MessageType.REQUEST_RESPONSE] = self._handle_response
        self._handlers[MessageType.DOWNLOAD_PROGRESS] = self._handle_download_progress

    def register_handler(self, msg_type: MessageType, handler: Callable):
        """注册消息处理器"""
        self._handlers[msg_type] = handler

    async def read_message(self, reader: asyncio.StreamReader) -> Tuple[MessageType, bytes]:
        """
        读取 BEP 消息

        格式: [1字节类型][4字节长度][数据]
        """
        header = await reader.readexactly(5)
        msg_type, length = struct.unpack(">BI", header)

        if length > 0:
            data = await reader.readexactly(length)
        else:
            data = b""

        return MessageType(msg_type), data

    async def write_message(self, writer: asyncio.StreamWriter,
                          msg_type: MessageType, data: bytes):
        """写入 BEP 消息"""
        header = struct.pack(">BI", int(msg_type), len(data))
        writer.write(header + data)
        await writer.drain()

    async def send_hello(self, writer: asyncio.StreamWriter,
                        device_name: str, device_info: DeviceInfo):
        """发送 Hello 消息"""
        msg = {
            "protocol_version": PROTOCOL_VERSION,
            "device_id": self.device_id,
            "device_name": device_name,
            "listening_ports": [22000],
            "flags": {
                "compress": True,
                "relay": True,
            },
            "device_info": asdict(device_info),
        }
        await self.write_message(writer, MessageType.HELLO_AGAIN, json.dumps(msg).encode())

    async def send_cluster_config(self, writer: asyncio.StreamWriter,
                                  configs: List[ClusterConfig]):
        """发送集群配置"""
        msg = {
            "device_id": self.device_id,
            "folders": [asdict(c) for c in configs],
        }
        await self.write_message(writer, MessageType.CLUSTER_CONFIG, json.dumps(msg).encode())

    async def send_index(self, writer: asyncio.StreamWriter,
                        folder_id: str, manifest: FileManifest):
        """发送文件清单"""
        msg = {
            "folder_id": folder_id,
            "device_id": self.device_id,
            "files": {k: v.to_dict() for k, v in manifest.files.items()},
            "sequence": manifest.sequence,
        }
        await self.write_message(writer, MessageType.INDEX, json.dumps(msg).encode())

    async def send_index_update(self, writer: asyncio.StreamWriter,
                               folder_id: str, files: Dict[str, FileInfo],
                               sequence: int):
        """发送增量更新"""
        msg = {
            "folder_id": folder_id,
            "device_id": self.device_id,
            "files": {k: v.to_dict() for k, v in files.items()},
            "sequence": sequence,
        }
        await self.write_message(writer, MessageType.INDEX_UPDATE, json.dumps(msg).encode())

    async def send_request(self, writer: asyncio.StreamWriter,
                          folder_id: str, file_id: str, chunk: BEPChunk):
        """发送块请求"""
        msg = {
            "id": f"{file_id}:{chunk.chunk_id}",
            "folder_id": folder_id,
            "file_id": file_id,
            "offset": chunk.offset,
            "size": chunk.size,
            "hash": chunk.hash,
        }
        await self.write_message(writer, MessageType.REQUEST, json.dumps(msg).encode())

    async def send_response(self, writer: asyncio.StreamWriter,
                           folder_id: str, file_id: str,
                           chunk_id: str, data: bytes,
                           compress: bool = True):
        """发送块响应"""
        if compress and len(data) >= self._compression_threshold:
            compressed = zlib.compress(data, level=6)
            if len(compressed) < len(data):
                data = compressed
                compress = True
            else:
                compress = False

        msg = {
            "id": f"{file_id}:{chunk_id}",
            "folder_id": folder_id,
            "file_id": file_id,
            "data": data.hex() if not compress else compressed.hex(),
            "compressed": compress,
            "size": len(data),
        }
        await self.write_message(writer, MessageType.REQUEST_RESPONSE, json.dumps(msg).encode())

    async def send_download_progress(self, writer: asyncio.StreamWriter,
                                     progress: DownloadProgress):
        """发送下载进度"""
        msg = asdict(progress)
        await self.write_message(writer, MessageType.DOWNLOAD_PROGRESS, json.dumps(msg).encode())

    async def send_ping(self, writer: asyncio.StreamWriter):
        """发送 Ping"""
        await self.write_message(writer, MessageType.PING, b"")

    # 处理器实现

    async def _handle_ping(self, data: bytes) -> Any:
        """处理 Ping，返回 Pong"""
        return MessageType.PONG, b""

    async def _handle_get_hello(self, data: bytes) -> Any:
        """处理 Get Hello 请求"""
        return MessageType.HELLO_AGAIN, data  # 返回客户端请求的数据

    async def _handle_hello_again(self, data: bytes) -> Tuple[MessageType, bytes]:
        """处理 Hello 消息"""
        try:
            msg = json.loads(data.decode())
            version = msg.get("protocol_version", 0)
            if version != PROTOCOL_VERSION:
                raise ValueError(f"协议版本不匹配: {version} != {PROTOCOL_VERSION}")
            return MessageType.HELLO_AGAIN, data
        except Exception as e:
            raise ValueError(f"Hello 解析失败: {e}")

    async def _handle_cluster_config(self, data: bytes) -> Any:
        """处理集群配置"""
        return json.loads(data.decode())

    async def _handle_index(self, data: bytes) -> Dict:
        """处理文件清单"""
        return json.loads(data.decode())

    async def _handle_index_update(self, data: bytes) -> Dict:
        """处理增量更新"""
        return json.loads(data.decode())

    async def _handle_request(self, data: bytes) -> Dict:
        """处理块请求"""
        return json.loads(data.decode())

    async def _handle_response(self, data: bytes) -> Dict:
        """处理块响应"""
        msg = json.loads(data.decode())
        if msg.get("compressed"):
            msg["data"] = zlib.decompress(bytes.fromhex(msg["data"]))
        else:
            msg["data"] = bytes.fromhex(msg["data"])
        return msg

    async def _handle_download_progress(self, data: bytes) -> Dict:
        """处理下载进度"""
        return json.loads(data.decode())

    async def process_message(self, msg_type: MessageType, data: bytes) -> Any:
        """处理消息并返回响应"""
        handler = self._handlers.get(msg_type)
        if not handler:
            raise ValueError(f"未知消息类型: {msg_type}")

        result = await handler(data)
        return result


class BEPConnection:
    """
    BEP 连接会话

    管理一个对等连接的完整生命周期：
    - 握手
    - 清单同步
    - 块传输
    """

    def __init__(self, protocol: BEPProtocol, reader: asyncio.StreamReader,
                 writer: asyncio.StreamWriter, device_id: str):
        self.protocol = protocol
        self.reader = reader
        self.writer = writer
        self.peer_device_id = device_id

        self._closed = False
        self._last_pong = time.time()
        self._ping_interval = 30  # 秒
        self._tasks: List[asyncio.Task] = []

    @property
    def peer_address(self) -> str:
        """获取对等地址"""
        return f"{self.writer.get_extra_info('peername')}"

    async def handshake(self, device_name: str, device_info: DeviceInfo) -> Dict:
        """
        执行握手流程

        1. 发送 Hello
        2. 接收 Hello
        3. 交换集群配置
        """
        # 发送 Hello
        await self.protocol.send_hello(self.writer, device_name, device_info)

        # 接收 Hello
        msg_type, data = await self.protocol.read_message(self.reader)
        if msg_type == MessageType.HELLO_AGAIN:
            hello = json.loads(data.decode())
            peer_version = hello.get("protocol_version")
            if peer_version != PROTOCOL_VERSION:
                raise ValueError(f"对等协议版本不匹配: {peer_version}")

        # 接收集群配置
        msg_type, data = await self.protocol.read_message(self.reader)
        if msg_type == MessageType.CLUSTER_CONFIG:
            cluster_config = json.loads(data.decode())

        return cluster_config

    async def start_sync(self, folder_id: str, manifest: FileManifest):
        """开始同步文件夹"""
        # 发送文件清单
        await self.protocol.send_index(self.writer, folder_id, manifest)

        # 启动消息循环
        task = asyncio.create_task(self._message_loop())
        self._tasks.append(task)

    async def _message_loop(self):
        """消息处理循环"""
        while not self._closed:
            try:
                msg_type, data = await asyncio.wait_for(
                    self.protocol.read_message(self.reader),
                    timeout=self._ping_interval
                )

                # 处理消息
                result = await self.protocol.process_message(msg_type, data)

                # 处理响应
                if msg_type == MessageType.REQUEST:
                    await self._handle_block_request(result)
                elif msg_type == MessageType.INDEX:
                    await self._handle_index(result)
                elif msg_type == MessageType.INDEX_UPDATE:
                    await self._handle_index_update(result)
                elif msg_type == MessageType.PING:
                    await self.protocol.send_pong(self.writer)

            except asyncio.TimeoutError:
                # 发送心跳
                await self.protocol.send_ping(self.writer)
            except Exception as e:
                if not self._closed:
                    raise

    async def _handle_block_request(self, request: Dict):
        """处理块请求"""
        # 子类实现
        pass

    async def _handle_index(self, index: Dict):
        """处理文件清单"""
        # 子类实现
        pass

    async def _handle_index_update(self, update: Dict):
        """处理增量更新"""
        # 子类实现
        pass

    async def request_blocks(self, folder_id: str, file_id: str,
                             chunks: List[BEPChunk]):
        """请求块数据"""
        for chunk in chunks:
            await self.protocol.send_request(
                self.writer, folder_id, file_id, chunk
            )

    async def close(self):
        """关闭连接"""
        if self._closed:
            return

        self._closed = True

        # 取消所有任务
        for task in self._tasks:
            if not task.done():
                task.cancel()

        # 关闭连接
        self.writer.close()
        try:
            await self.writer.wait_closed()
        except:
            pass
