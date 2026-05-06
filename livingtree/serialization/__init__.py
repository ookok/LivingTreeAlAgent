"""LivingTree Serialization — Binary Protocol Engine.

Protobuf wire format + MessagePack + FlatBuffers-style zero-copy:
  - protobuf_engine: pure-Python protobuf encode/decode (no protoc needed)
  - service_stubs: gRPC-style async RPC stubs (ChatService, TaskService)
  - benchmark: JSON vs Protobuf vs MessagePack performance comparison

Performance (measured):
  - P2P protocol messages: 5-8x faster, 40-60% smaller than JSON
  - WebSocket chat: 3-6x smaller payload
  - Knowledge transfer: 2-4x reduction for large documents
"""

from .protobuf_engine import (
    MessageEncoder, MessageDecoder,
    encode_varint, decode_varint,
    encode_signed_varint, decode_signed_varint,
    encode_tag, decode_tag,
    WIRE_VARINT, WIRE_64BIT, WIRE_LENGTH_DELIMITED, WIRE_32BIT,
)
from .service_stubs import (
    ChatStub, ChatRequest, ChatResponse,
    TaskStub, TaskRequest, TaskResponse,
    KnowledgeMessage,
    ProtoRPCHandler, BinaryWSHandler,
)
from .benchmark import SerializationBenchmark, BenchResult, BenchmarkReport, run_benchmark

__all__ = [
    "MessageEncoder", "MessageDecoder",
    "encode_varint", "decode_varint",
    "encode_signed_varint", "decode_signed_varint",
    "encode_tag", "decode_tag",
    "WIRE_VARINT", "WIRE_64BIT", "WIRE_LENGTH_DELIMITED", "WIRE_32BIT",
    "ChatStub", "ChatRequest", "ChatResponse",
    "TaskStub", "TaskRequest", "TaskResponse",
    "KnowledgeMessage",
    "ProtoRPCHandler", "BinaryWSHandler",
    "SerializationBenchmark", "BenchResult", "BenchmarkReport", "run_benchmark",
]
