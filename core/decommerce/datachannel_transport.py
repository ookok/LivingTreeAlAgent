"""
DataChannel MessagePack 传输层
DataChannel MessagePack Transport Layer

优化AI任务/指令/小文件通过RTCDataChannel (SCTP/UDP) 传输,
比HTTP/WebSocket更快、更抗丢包。

特性:
1. MessagePack序列化 - 更紧凑的二进制格式
2. 流式传输 - 支持大文件分块
3. 优先级队列 - 紧急任务优先处理
4. 自动重传 - 可靠性保证
5. 心跳检测 - 连接健康监控
"""

from typing import Any, Awaitable, Callable, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import logging
import time
import uuid
import struct
import hashlib

logger = logging.getLogger(__name__)

# 尝试导入msgpack, 如果没有就用json作为后备
try:
    import msgpack
    _HAS_MSGPACK = True
except ImportError:
    import json
    _HAS_MSGPACK = False
    logger.warning("[DataChannelTransport] msgpack not available, using json fallback")


class MessageType(Enum):
    """消息类型"""
    # 控制消息
    HEARTBEAT = 0x01
    ACK = 0x02
    NACK = 0x03
    CLOSE = 0x04

    # 任务消息
    TASK_SUBMIT = 0x10      # 提交任务
    TASK_RESULT = 0x11       # 返回结果
    TASK_PROGRESS = 0x12     # 进度更新
    TASK_CANCEL = 0x13      # 取消任务

    # 流式消息
    STREAM_START = 0x20     # 流开始
    STREAM_DATA = 0x21      # 流数据
    STREAM_END = 0x22       # 流结束

    # 文件消息
    FILE_CHUNK = 0x30       # 文件块
    FILE_END = 0x31         # 文件结束


class Priority(Enum):
    """消息优先级"""
    CRITICAL = 0    # 关键 (支付/取消)
    HIGH = 1        # 高优先级 (AI任务)
    NORMAL = 2      # 普通 (聊天)
    LOW = 3         # 低优先级 (日志)


@dataclass
class TransportMessage:
    """传输消息"""
    msg_type: MessageType
    priority: Priority = Priority.NORMAL

    # 消息ID (用于ACK/重传)
    msg_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    # 关联ID (session_id, job_id等)
    correlation_id: str = ""

    # 负载
    payload: bytes = field(default_factory=bytes)

    # 元数据
    timestamp: float = field(default_factory=time.time)
    ttl: int = 60  # 生存时间(秒)

    # 序列号 (用于顺序保证)
    sequence: int = 0

    def is_expired(self) -> bool:
        """是否过期"""
        return time.time() - self.timestamp > self.ttl

    def to_bytes(self) -> bytes:
        """序列化为字节"""
        header = struct.pack(
            "!BBHIH",  # msg_type, priority, payload_len, sequence, msg_id_hash
            self.msg_type.value,
            self.priority.value,
            len(self.payload),
            self.sequence,
            int(hashlib.md5(self.msg_id.encode()).hexdigest()[:4], 16)
        )
        return header + self.payload

    @classmethod
    def from_bytes(cls, data: bytes) -> "TransportMessage":
        """从字节反序列化"""
        if len(data) < 10:
            raise ValueError("Data too short")

        msg_type_val, priority_val, payload_len, sequence, _ = struct.unpack(
            "!BBHIH", data[:10]
        )

        msg = cls(
            msg_type=MessageType(msg_type_val),
            priority=Priority(priority_val),
            sequence=sequence,
            payload=data[10:10+payload_len],
        )
        return msg

    def encode_payload(self, data: Any) -> None:
        """编码负载"""
        if _HAS_MSGPACK:
            self.payload = msgpack.packb(data, use_bin_type=True)
        else:
            self.payload = json.dumps(data).encode("utf-8")

    def decode_payload(self) -> Any:
        """解码负载"""
        if _HAS_MSGPACK:
            return msgpack.unpackb(self.payload, raw=False)
        else:
            return json.loads(self.payload.decode("utf-8"))


@dataclass
class TaskSpec:
    """任务规格"""
    task_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    task_type: str = "chat"  # chat | complete | embed | reasoning

    # 模型相关
    model: str = ""
    prompt: str = ""

    # 参数
    parameters: Dict[str, Any] = field(default_factory=dict)

    # 期望的响应格式
    stream: bool = False
    max_tokens: int = 2048
    temperature: float = 0.7

    # 上下文
    session_id: str = ""
    user_id: str = ""

    # 元数据
    created_at: float = field(default_factory=time.time)
    priority: Priority = Priority.HIGH


def _get_default_datachannel_config() -> Dict[str, float]:
    """从统一配置获取默认值"""
    try:
        from core.config.unified_config import get_config
        config = get_config()
        return config.get_heartbeat_config("datachannel")
    except Exception:
        return {"interval": 5.0, "timeout": 30.0}


# 获取默认值
_default_dc_config = _get_default_datachannel_config()


class DataChannelTransport:
    """
    DataChannel传输层

    功能:
    - 封装RTCDataChannel提供可靠的消息传递
    - 支持优先级队列
    - 自动重传和ACK
    - 流式传输支持
    """

    def __init__(
        self,
        channel_label: str = "decommerce_datachannel",
        ordered: bool = True,
        max_retransmits: int = 3,
        heartbeat_interval: Optional[float] = None,
        heartbeat_timeout: Optional[float] = None,
    ):
        # WebRTC DataChannel
        self._channel: Optional[Any] = None
        self._channel_label = channel_label
        self._ordered = ordered
        self._max_retransmits = max_retransmits

        # 消息处理
        self._handlers: Dict[MessageType, Callable] = {}
        self._pending_messages: Dict[str, asyncio.Future] = {}  # msg_id -> Future
        self._message_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._processing_task: Optional[asyncio.Task] = None

        # 流式传输
        self._active_streams: Dict[str, asyncio.Queue] = {}

        # 心跳（从统一配置获取）
        self._heartbeat_interval: float = heartbeat_interval or _default_dc_config.get("interval", 5.0)
        self._heartbeat_timeout: float = heartbeat_timeout or _default_dc_config.get("timeout", 30.0)
        self._last_received: float = time.time()
        self._heartbeat_task: Optional[asyncio.Task] = None

        # 统计
        self._stats = {
            "sent": 0,
            "received": 0,
            "failed": 0,
            "avg_latency_ms": 0,
        }

        # 回调
        self._on_task_result: Optional[Callable] = None
        self._on_task_progress: Optional[Callable] = None
        self._on_connection_lost: Optional[Callable] = None

        # 状态
        self._running = False

    def set_channel(self, channel: Any) -> None:
        """设置DataChannel (由WebRTC层调用)"""
        self._channel = channel
        channel.onmessage = self._on_message
        channel.onopen = self._on_open
        channel.onclose = self._on_close
        channel.onerror = self._on_error
        logger.info(f"[DataChannelTransport] Channel set: {channel.label}")

    async def start(self) -> None:
        """启动传输层"""
        self._running = True
        self._processing_task = asyncio.create_task(self._process_queue())
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info("[DataChannelTransport] Started")

    async def stop(self) -> None:
        """停止传输层"""
        self._running = False

        if self._processing_task:
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass

        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        # 关闭所有流
        for stream_id in list(self._active_streams.keys()):
            await self.close_stream(stream_id)

        # 发送关闭消息
        if self._channel and self._channel.readyState == "open":
            close_msg = TransportMessage(MessageType.CLOSE)
            self._send_raw(close_msg.to_bytes())

        logger.info("[DataChannelTransport] Stopped")

    def _on_open(self) -> None:
        """通道打开"""
        logger.info("[DataChannelTransport] Channel opened")
        self._last_received = time.time()

    def _on_close(self) -> None:
        """通道关闭"""
        logger.info("[DataChannelTransport] Channel closed")
        if self._on_connection_lost:
            try:
                self._on_connection_lost()
            except Exception as e:
                logger.error(f"[DataChannelTransport] Connection lost callback error: {e}")

    def _on_error(self, error: Any) -> None:
        """通道错误"""
        logger.error(f"[DataChannelTransport] Channel error: {error}")

    def _on_message(self, event: Any) -> None:
        """收到消息"""
        try:
            data = event.data
            if isinstance(data, str):
                data = data.encode("utf-8")

            msg = TransportMessage.from_bytes(data)
            self._last_received = time.time()

            # 加入处理队列
            priority_val = msg.priority.value * 1000 - msg.sequence
            self._message_queue.put_nowait((priority_val, msg))

            self._stats["received"] += 1

        except Exception as e:
            logger.error(f"[DataChannelTransport] Message parse error: {e}")
            self._stats["failed"] += 1

    async def _process_queue(self) -> None:
        """处理消息队列"""
        while self._running:
            try:
                _, msg = await asyncio.wait_for(
                    self._message_queue.get(),
                    timeout=1.0
                )

                await self._handle_message(msg)

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"[DataChannelTransport] Queue processing error: {e}")

    async def _handle_message(self, msg: TransportMessage) -> None:
        """处理单个消息"""
        msg_type = msg.msg_type

        # 发送ACK (除了心跳和ACK本身)
        if msg_type not in (MessageType.HEARTBEAT, MessageType.ACK, MessageType.CLOSE):
            ack = TransportMessage(
                MessageType.ACK,
                correlation_id=msg.msg_id,
                payload=msg.msg_id.encode()
            )
            self._send_raw(ack.to_bytes())

        # 处理不同类型的消息
        if msg_type == MessageType.HEARTBEAT:
            # 收到心跳，回复心跳
            hb_reply = TransportMessage(MessageType.HEARTBEAT)
            self._send_raw(hb_reply.to_bytes())

        elif msg_type == MessageType.TASK_RESULT:
            # 任务结果
            payload = msg.decode_payload()
            task_id = msg.correlation_id

            # 查找等待的Future并唤醒
            future = self._pending_messages.pop(task_id, None)
            if future and not future.done():
                future.set_result(payload)

            if self._on_task_result:
                await self._safe_call(self._on_task_result, task_id, payload)

        elif msg_type == MessageType.TASK_PROGRESS:
            # 进度更新
            payload = msg.decode_payload()
            if self._on_task_progress:
                await self._safe_call(self._on_task_progress, msg.correlation_id, payload)

        elif msg_type == MessageType.STREAM_DATA:
            # 流式数据
            stream_id = msg.correlation_id
            if stream_id in self._active_streams:
                self._active_streams[stream_id].put_nowait(msg.payload)

        elif msg_type == MessageType.STREAM_END:
            # 流结束
            stream_id = msg.correlation_id
            if stream_id in self._active_streams:
                self._active_streams[stream_id].put_nowait(None)  # None表示结束

        elif msg_type == MessageType.NACK:
            # 重传请求
            logger.warning(f"[DataChannelTransport] NACK received for {msg.correlation_id}")
            # TODO: 实现重传逻辑

        else:
            # 通用处理器
            handler = self._handlers.get(msg_type)
            if handler:
                payload = msg.decode_payload() if msg.payload else None
                await self._safe_call(handler, msg.correlation_id, payload)

    async def _heartbeat_loop(self) -> None:
        """心跳循环"""
        while self._running:
            try:
                await asyncio.sleep(self._heartbeat_interval)

                # 检查连接是否存活
                if time.time() - self._last_received > self._heartbeat_timeout:
                    logger.warning("[DataChannelTransport] Heartbeat timeout")
                    if self._on_connection_lost:
                        await self._safe_call(self._on_connection_lost)
                    break

                # 发送心跳
                hb = TransportMessage(MessageType.HEARTBEAT)
                self._send_raw(hb.to_bytes())

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[DataChannelTransport] Heartbeat error: {e}")

    def _send_raw(self, data: bytes) -> None:
        """发送原始数据"""
        if self._channel and self._channel.readyState == "open":
            try:
                self._channel.send(data)
                self._stats["sent"] += 1
            except Exception as e:
                logger.error(f"[DataChannelTransport] Send error: {e}")
                self._stats["failed"] += 1

    # ==================== 公共API ====================

    def send_task(
        self,
        task: TaskSpec,
        timeout: float = 60.0,
    ) -> Awaitable[Dict[str, Any]]:
        """
        发送AI任务并等待结果

        Returns:
            Future, 结果可通过 await future 获取
        """
        msg = TransportMessage(
            MessageType.TASK_SUBMIT,
            priority=task.priority,
            correlation_id=task.task_id,
        )
        msg.encode_payload({
            "task_id": task.task_id,
            "task_type": task.task_type,
            "model": task.model,
            "prompt": task.prompt,
            "parameters": task.parameters,
            "stream": task.stream,
            "max_tokens": task.max_tokens,
            "temperature": task.temperature,
            "session_id": task.session_id,
            "user_id": task.user_id,
        })

        # 发送消息
        self._send_raw(msg.to_bytes())

        # 创建Future用于接收结果
        future: asyncio.Future[Dict[str, Any]] = asyncio.get_event_loop().create_future()
        self._pending_messages[task.task_id] = future

        # 设置超时
        async def with_timeout():
            try:
                return await asyncio.wait_for(future, timeout)
            except asyncio.TimeoutError:
                self._pending_messages.pop(task.task_id, None)
                raise TimeoutError(f"Task {task.task_id} timed out after {timeout}s")

        return with_timeout()

    async def send_task_no_wait(self, task: TaskSpec) -> bool:
        """发送任务但不等待结果 (用于fire-and-forget)"""
        msg = TransportMessage(
            MessageType.TASK_SUBMIT,
            priority=task.priority,
            correlation_id=task.task_id,
        )
        msg.encode_payload({
            "task_id": task.task_id,
            "task_type": task.task_type,
            "model": task.model,
            "prompt": task.prompt,
            "parameters": task.parameters,
        })

        self._send_raw(msg.to_bytes())
        return True

    def send_progress(
        self,
        task_id: str,
        progress: float,
        message: str = "",
    ) -> None:
        """发送进度更新"""
        msg = TransportMessage(
            MessageType.TASK_PROGRESS,
            priority=Priority.HIGH,
            correlation_id=task_id,
        )
        msg.encode_payload({
            "progress": progress,
            "message": message,
        })
        self._send_raw(msg.to_bytes())

    def cancel_task(self, task_id: str) -> None:
        """取消任务"""
        msg = TransportMessage(
            MessageType.TASK_CANCEL,
            priority=Priority.CRITICAL,
            correlation_id=task_id,
        )
        msg.encode_payload({"task_id": task_id})
        self._send_raw(msg.to_bytes())

        # 清理Future
        future = self._pending_messages.pop(task_id, None)
        if future and not future.done():
            future.set_exception(asyncio.CancelledError("Task cancelled"))

    # ==================== 流式传输 ====================

    async def start_stream(
        self,
        stream_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> asyncio.Queue:
        """
        开始流式传输

        Returns:
            Queue, 接收数据 via await queue.get()
            None表示流结束
        """
        queue: asyncio.Queue = asyncio.Queue()
        self._active_streams[stream_id] = queue

        # 发送流开始
        msg = TransportMessage(
            MessageType.STREAM_START,
            priority=Priority.HIGH,
            correlation_id=stream_id,
        )
        msg.encode_payload(metadata or {})
        self._send_raw(msg.to_bytes())

        return queue

    async def close_stream(self, stream_id: str) -> None:
        """关闭流"""
        if stream_id in self._active_streams:
            # 发送流结束
            msg = TransportMessage(
                MessageType.STREAM_END,
                priority=Priority.NORMAL,
                correlation_id=stream_id,
            )
            self._send_raw(msg.to_bytes())

            # 清理队列
            del self._active_streams[stream_id]

    def send_stream_chunk(self, stream_id: str, data: bytes) -> None:
        """发送流数据块"""
        msg = TransportMessage(
            MessageType.STREAM_DATA,
            priority=Priority.NORMAL,
            correlation_id=stream_id,
            payload=data,
        )
        self._send_raw(msg.to_bytes())

    # ==================== 文件传输 ====================

    async def send_file(
        self,
        file_id: str,
        data: bytes,
        chunk_size: int = 16384,  # 16KB
    ) -> bool:
        """
        分块发送文件

        Args:
            file_id: 文件唯一ID
            data: 文件数据
            chunk_size: 块大小
        """
        total_chunks = (len(data) + chunk_size - 1) // chunk_size

        for i in range(total_chunks):
            chunk = data[i*chunk_size:(i+1)*chunk_size]
            is_last = (i == total_chunks - 1)

            msg = TransportMessage(
                MessageType.FILE_CHUNK if not is_last else MessageType.FILE_END,
                priority=Priority.NORMAL,
                correlation_id=file_id,
            )
            msg.encode_payload({
                "chunk_index": i,
                "total_chunks": total_chunks,
                "data": chunk.hex(),  # 十六进制编码
            })
            self._send_raw(msg.to_bytes())

            # 小延迟避免阻塞
            if i % 10 == 0:
                await asyncio.sleep(0.001)

        return True

    # ==================== 辅助 ====================

    def register_handler(self, msg_type: MessageType, handler: Callable) -> None:
        """注册消息处理器"""
        self._handlers[msg_type] = handler

    def set_task_result_callback(self, callback: Callable) -> None:
        """设置任务结果回调"""
        self._on_task_result = callback

    def set_task_progress_callback(self, callback: Callable) -> None:
        """设置任务进度回调"""
        self._on_task_progress = callback

    def set_connection_lost_callback(self, callback: Callable) -> None:
        """设置连接丢失回调"""
        self._on_connection_lost = callback

    async def _safe_call(self, callback: Callable, *args) -> None:
        """安全调用回调"""
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(*args)
            else:
                callback(*args)
        except Exception as e:
            logger.error(f"[DataChannelTransport] Callback error: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return self._stats.copy()

    @property
    def is_connected(self) -> bool:
        """是否已连接"""
        return self._channel is not None and self._channel.readyState == "open"
