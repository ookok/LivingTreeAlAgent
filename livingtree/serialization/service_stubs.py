"""gRPC-style Service Stubs — async RPC client/server without gRPC dependency.

Pure-Python implementation of gRPC concepts:
  - Service definitions (like .proto `service` blocks)
  - Message serialization via Protobuf engine
  - Streaming support (unary, server-stream, client-stream, bidi)
  - Async-first design (compatible with existing aiohttp/FastAPI)

Maps to protos/livingtree.proto service definitions:
  - ChatService → ChatStub
  - TaskService → TaskStub

Usage:
    stub = ChatStub(base_url="http://localhost:8000")
    response = await stub.chat(ChatRequest(model="deepseek", messages=[...]))
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Optional, AsyncIterator

from loguru import logger

from .protobuf_engine import MessageEncoder, MessageDecoder


# ═══ Service Definition ═══

@dataclass
class RPCMethod:
    name: str
    request_encoder: callable
    response_decoder: callable
    streaming: bool = False


@dataclass
class ServiceDef:
    name: str
    methods: dict[str, RPCMethod] = field(default_factory=dict)


# ═══ Chat Message Types ═══

@dataclass
class ChatRequest:
    model: str = ""
    messages: list[dict] = field(default_factory=list)
    temperature: float = 0.7
    max_tokens: int = 4096
    stream: bool = False
    metadata: dict[str, str] = field(default_factory=dict)

    def to_proto(self) -> bytes:
        enc = MessageEncoder()
        enc.add_string(1, self.model)
        for msg in self.messages:
            sub = MessageEncoder()
            sub.add_string(1, msg.get("role", "user"))
            sub.add_string(2, msg.get("content", ""))
            enc.add_message(2, sub)
        enc.add_double(3, self.temperature)
        enc.add_varint(4, self.max_tokens)
        enc.add_bool(5, self.stream)
        enc.add_map(7, self.metadata)
        return enc.encode()

    @classmethod
    def from_proto(cls, data: bytes) -> "ChatRequest":
        dec = MessageDecoder(data)
        messages = []
        for field_num in [2]:
            sub = dec.get_message(field_num)
            if sub:
                messages.append({
                    "role": sub.get_string(1, "user"),
                    "content": sub.get_string(2, ""),
                })
        return cls(
            model=dec.get_string(1, ""),
            messages=messages or [{"role": "user", "content": ""}],
            temperature=dec.get_double(3, 0.7),
            max_tokens=dec.get_varint(4, 4096),
            stream=dec.get_bool(5, False),
            metadata=dec.get_map(7),
        )


@dataclass
class ChatResponse:
    id: str = ""
    model: str = ""
    content: str = ""
    cost: float = 0.0
    tokens_used: int = 0

    def to_proto(self) -> bytes:
        enc = MessageEncoder()
        enc.add_string(1, self.id)
        enc.add_string(2, self.model)
        enc.add_string(3, self.content)
        enc.add_double(4, self.cost)
        enc.add_varint(5, self.tokens_used)
        return enc.encode()

    @classmethod
    def from_proto(cls, data: bytes) -> "ChatResponse":
        dec = MessageDecoder(data)
        return cls(
            id=dec.get_string(1, ""),
            model=dec.get_string(2, ""),
            content=dec.get_string(3, ""),
            cost=dec.get_double(4, 0.0),
            tokens_used=dec.get_varint(5, 0),
        )


# ═══ Task Message Types ═══

@dataclass
class TaskRequest:
    task_id: str = ""
    type: str = ""
    description: str = ""
    priority: int = 0
    source_node: str = ""

    def to_proto(self) -> bytes:
        enc = MessageEncoder()
        enc.add_string(1, self.task_id)
        enc.add_string(2, self.type)
        enc.add_string(3, self.description)
        enc.add_varint(4, self.priority)
        enc.add_string(5, self.source_node)
        return enc.encode()

    @classmethod
    def from_proto(cls, data: bytes) -> "TaskRequest":
        dec = MessageDecoder(data)
        return cls(
            task_id=dec.get_string(1, ""),
            type=dec.get_string(2, ""),
            description=dec.get_string(3, ""),
            priority=dec.get_varint(4, 0),
            source_node=dec.get_string(5, ""),
        )


@dataclass
class TaskResponse:
    task_id: str = ""
    status: str = ""
    result: str = ""
    error: str = ""
    progress: float = 0.0

    def to_proto(self) -> bytes:
        enc = MessageEncoder()
        enc.add_string(1, self.task_id)
        enc.add_string(2, self.status)
        enc.add_string(3, self.result)
        enc.add_string(4, self.error)
        enc.add_float(5, self.progress)
        return enc.encode()

    @classmethod
    def from_proto(cls, data: bytes) -> "TaskResponse":
        dec = MessageDecoder(data)
        return cls(
            task_id=dec.get_string(1, ""),
            status=dec.get_string(2, ""),
            result=dec.get_string(3, ""),
            error=dec.get_string(4, ""),
            progress=dec.get_float(5, 0.0),
        )


# ═══ Knowledge Message Types ═══

@dataclass
class KnowledgeMessage:
    doc_id: str = ""
    title: str = ""
    source: str = ""
    chunks: list[dict] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)

    def to_proto(self) -> bytes:
        enc = MessageEncoder()
        enc.add_string(1, self.doc_id)
        enc.add_string(2, self.title)
        enc.add_string(3, self.source)
        for chunk in self.chunks:
            sub = MessageEncoder()
            sub.add_varint(1, chunk.get("index", 0))
            sub.add_string(2, chunk.get("text", ""))
            sub.add_string(3, chunk.get("section_path", ""))
            enc.add_message(4, sub)
        enc.add_map(5, self.metadata)
        return enc.encode()

    @classmethod
    def from_proto(cls, data: bytes) -> "KnowledgeMessage":
        dec = MessageDecoder(data)
        return cls(
            doc_id=dec.get_string(1, ""),
            title=dec.get_string(2, ""),
            source=dec.get_string(3, ""),
            chunks=[],
            metadata=dec.get_map(5),
        )


# ═══ Service Stubs (async RPC) ═══

class ChatStub:
    """Async ChatService RPC stub — Protobuf over HTTP/2 (or HTTP/1.1 fallback)."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.content_type = "application/x-protobuf"

    async def chat(self, request: ChatRequest) -> ChatResponse:
        import aiohttp
        data = request.to_proto()
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/rpc/chat",
                data=data,
                headers={"Content-Type": self.content_type, "Accept": self.content_type},
            ) as resp:
                body = await resp.read()
                return ChatResponse.from_proto(body)

    async def stream_chat(self, request: ChatRequest) -> AsyncIterator[ChatResponse]:
        import aiohttp
        data = request.to_proto()
        request.stream = True
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/rpc/chat/stream",
                data=data,
                headers={"Content-Type": self.content_type},
            ) as resp:
                async for chunk in resp.content.iter_chunks():
                    yield ChatResponse.from_proto(chunk[0])

    async def chat_json(self, request: ChatRequest) -> ChatResponse:
        """Fallback: JSON mode for backward compatibility."""
        import aiohttp, json
        payload = {
            "model": request.model,
            "messages": request.messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "stream": False,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload,
            ) as resp:
                data = await resp.json()
                choice = data.get("choices", [{}])[0]
                return ChatResponse(
                    id=data.get("id", ""),
                    model=data.get("model", ""),
                    content=choice.get("message", {}).get("content", ""),
                    tokens_used=data.get("usage", {}).get("total_tokens", 0),
                )


class TaskStub:
    """Async TaskService RPC stub."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.content_type = "application/x-protobuf"

    async def submit_task(self, request: TaskRequest) -> TaskResponse:
        import aiohttp
        data = request.to_proto()
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/rpc/task/submit",
                data=data,
                headers={"Content-Type": self.content_type},
            ) as resp:
                return TaskResponse.from_proto(await resp.read())


# ═══ Server-side Handler ═══

class ProtoRPCHandler:
    """FastAPI-compatible protobuf RPC request handler.

    Wire into existing FastAPI routes:

        @app.post("/rpc/chat")
        async def rpc_chat(request: Request):
            body = await request.body()
            req = ChatRequest.from_proto(body)
            # ... process with existing logic ...
            return Response(content=resp.to_proto(), media_type="application/x-protobuf")
    """

    @staticmethod
    def parse_chat_request(data: bytes) -> ChatRequest:
        return ChatRequest.from_proto(data)

    @staticmethod
    def build_chat_response(content: str, model: str = "", tokens: int = 0) -> bytes:
        return ChatResponse(model=model, content=content, tokens_used=tokens).to_proto()

    @staticmethod
    def parse_task_request(data: bytes) -> TaskRequest:
        return TaskRequest.from_proto(data)

    @staticmethod
    def build_task_response(task_id: str, status: str, result: str = "") -> bytes:
        return TaskResponse(task_id=task_id, status=status, result=result).to_proto()


# ═══ Binary WebSocket Handler ═══

class BinaryWSHandler:
    """Binary WebSocket message helper.

    Replaces: websocket.send_json() / websocket.receive_json()
    With:     send_binary(proto.encode()) / receive_bytes() → decoder

    Wire format: [1-byte msg_type][varint-length][protobuf-body]
    """

    MSG_CHAT_REQUEST = 1
    MSG_CHAT_RESPONSE = 2
    MSG_TASK_REQUEST = 3
    MSG_TASK_RESPONSE = 4
    MSG_STATUS = 5
    MSG_KNOWLEDGE = 6
    MSG_PING = 7
    MSG_PONG = 8

    @staticmethod
    def encode_message(msg_type: int, proto_data: bytes) -> bytes:
        from .protobuf_engine import encode_varint
        return bytes([msg_type]) + encode_varint(len(proto_data)) + proto_data

    @staticmethod
    def decode_message(data: bytes) -> tuple[int, bytes]:
        from .protobuf_engine import decode_varint
        msg_type = data[0]
        length, consumed = decode_varint(data, 1)
        body = data[1 + consumed: 1 + consumed + length]
        return msg_type, body
