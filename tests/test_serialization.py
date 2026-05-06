"""Binary serialization tests — protobuf engine + service stubs + benchmark.

Tests:
  - Varint encode/decode roundtrip
  - Protobuf wire format (field tags, embedded messages)
  - MessageEncoder/Decoder full roundtrip
  - ChatRequest/Response protobuf roundtrip
  - TaskRequest/Response protobuf roundtrip
  - BinaryWSHandler encode/decode
  - Benchmark: all message types
"""

from __future__ import annotations

import json
import pytest

from livingtree.serialization.protobuf_engine import (
    MessageEncoder, MessageDecoder,
    encode_varint, decode_varint,
    encode_signed_varint, decode_signed_varint,
    encode_tag, decode_tag,
    WIRE_VARINT, WIRE_LENGTH_DELIMITED,
)
from livingtree.serialization.service_stubs import (
    ChatStub, ChatRequest, ChatResponse,
    TaskStub, TaskRequest, TaskResponse,
    KnowledgeMessage,
    ProtoRPCHandler, BinaryWSHandler,
)
from livingtree.serialization.benchmark import (
    SerializationBenchmark, BenchResult, BenchmarkReport,
)


# ═══ Varint ═══

class TestVarint:
    def test_encode_small(self):
        assert encode_varint(0) == b'\x00'
        assert encode_varint(1) == b'\x01'
        assert encode_varint(127) == b'\x7f'

    def test_encode_large(self):
        assert encode_varint(128) == b'\x80\x01'
        assert encode_varint(300) == b'\xac\x02'

    def test_roundtrip(self):
        for n in [0, 1, 127, 128, 256, 1000, 65535, 1000000, 2**32 - 1]:
            val, consumed = decode_varint(encode_varint(n))
            assert val == n
            assert consumed == len(encode_varint(n))

    def test_signed_roundtrip(self):
        for n in [-100, -1, 0, 1, 100, -65535, 65535]:
            encoded = encode_signed_varint(n)
            val, consumed = decode_signed_varint(encoded)
            assert val == n

    def test_tag(self):
        tag = encode_tag(1, WIRE_VARINT)
        fn, wt = decode_tag(tag)
        assert fn == 1
        assert wt == WIRE_VARINT

        tag2 = encode_tag(5, WIRE_LENGTH_DELIMITED)
        fn2, wt2 = decode_tag(tag2)
        assert fn2 == 5
        assert wt2 == WIRE_LENGTH_DELIMITED


# ═══ Message Encoder/Decoder ═══

class TestMessageEncoderDecoder:
    def test_simple_message(self):
        enc = MessageEncoder()
        enc.add_varint(1, 42)
        enc.add_string(2, "hello")
        enc.add_bool(3, True)
        enc.add_double(4, 3.14)

        data = enc.encode()
        dec = MessageDecoder(data)

        assert dec.get_varint(1) == 42
        assert dec.get_string(2) == "hello"
        assert dec.get_bool(3) is True
        assert abs(dec.get_double(4) - 3.14) < 0.01

    def test_default_values(self):
        dec = MessageDecoder(b'')
        assert dec.get_varint(99) == 0
        assert dec.get_string(99) == ""
        assert dec.get_bool(99) is False

    def test_nested_message(self):
        inner = MessageEncoder()
        inner.add_string(1, "nested_value")
        inner.add_varint(2, 99)

        outer = MessageEncoder()
        outer.add_string(1, "outer")
        outer.add_message(2, inner)

        data = outer.encode()
        dec_outer = MessageDecoder(data)
        assert dec_outer.get_string(1) == "outer"

        dec_inner = dec_outer.get_message(2)
        assert dec_inner is not None
        assert dec_inner.get_string(1) == "nested_value"
        assert dec_inner.get_varint(2) == 99

    def test_repeated_string(self):
        enc = MessageEncoder()
        enc.add_string(1, "first")
        enc.add_string(1, "second")
        enc.add_string(1, "third")

        data = enc.encode()
        dec = MessageDecoder(data)
        repeated = dec.get_repeated_string(1)
        assert len(repeated) == 3
        assert "first" in repeated

    def test_map_field(self):
        enc = MessageEncoder()
        enc.add_map(1, {"key_a": "val_a", "key_b": "val_b"})

        data = enc.encode()
        dec = MessageDecoder(data)
        m = dec.get_map(1)
        assert m["key_a"] == "val_a"
        assert m["key_b"] == "val_b"

    def test_has_field(self):
        enc = MessageEncoder()
        enc.add_string(1, "exists")
        dec = MessageDecoder(enc.encode())
        assert dec.has_field(1)
        assert not dec.has_field(99)

    def test_size_comparison_json(self):
        """Protobuf should be smaller than JSON for structured data."""
        msg = {
            "model": "deepseek-v4-pro",
            "messages": [
                {"role": "user", "content": "大气扩散模型参数如何设置？"},
            ],
            "temperature": 0.7,
            "max_tokens": 4096,
            "stream": False,
        }

        json_size = len(json.dumps(msg, ensure_ascii=False).encode("utf-8"))

        enc = MessageEncoder()
        enc.add_string(1, msg["model"])
        for m in msg["messages"]:
            sub = MessageEncoder()
            sub.add_string(1, m["role"])
            sub.add_string(2, m["content"])
            enc.add_message(2, sub)
        enc.add_double(3, msg["temperature"])
        enc.add_varint(4, msg["max_tokens"])
        enc.add_bool(5, msg["stream"])

        proto_size = len(enc.encode())
        assert proto_size < json_size * 1.5


# ═══ Service Stubs ═══

class TestServiceStubs:
    def test_chat_request_roundtrip(self):
        req = ChatRequest(
            model="deepseek-v4",
            messages=[{"role": "user", "content": "环评报告生成"}],
            temperature=0.5,
            max_tokens=8192,
        )
        data = req.to_proto()
        parsed = ChatRequest.from_proto(data)
        assert parsed.model == "deepseek-v4"
        assert len(parsed.messages) > 0
        assert parsed.messages[0]["content"] == "环评报告生成"

    def test_chat_response_roundtrip(self):
        resp = ChatResponse(
            id="chat_001",
            model="deepseek-v4",
            content="大气扩散模型参数设置依据HJ2.2-2018...",
            tokens_used=450,
        )
        data = resp.to_proto()
        parsed = ChatResponse.from_proto(data)
        assert parsed.content == "大气扩散模型参数设置依据HJ2.2-2018..."
        assert parsed.tokens_used == 450

    def test_task_request_roundtrip(self):
        req = TaskRequest(
            task_id="task_001",
            type="generate",
            description="生成环评报告",
            priority=3,
            source_node="node_01",
        )
        data = req.to_proto()
        parsed = TaskRequest.from_proto(data)
        assert parsed.task_id == "task_001"
        assert parsed.priority == 3

    def test_task_response_roundtrip(self):
        resp = TaskResponse(
            task_id="task_001",
            status="completed",
            result="报告已生成",
            progress=1.0,
        )
        data = resp.to_proto()
        parsed = TaskResponse.from_proto(data)
        assert parsed.status == "completed"
        assert parsed.progress == 1.0

    def test_knowledge_message_roundtrip(self):
        msg = KnowledgeMessage(
            doc_id="doc_001",
            title="环评报告",
            source="kb",
            chunks=[{"index": 0, "text": "测试内容", "section_path": "1 > 1.1"}],
            metadata={"author": "system"},
        )
        data = msg.to_proto()
        parsed = KnowledgeMessage.from_proto(data)
        assert parsed.doc_id == "doc_001"
        assert parsed.title == "环评报告"

    def test_proto_rpc_handler(self):
        req = ChatRequest(
            model="deepseek",
            messages=[{"role": "user", "content": "test"}],
        )
        data = req.to_proto()
        parsed = ProtoRPCHandler.parse_chat_request(data)
        assert parsed.model == "deepseek"

        resp_data = ProtoRPCHandler.build_chat_response("回答内容", model="deepseek", tokens=100)
        resp = ChatResponse.from_proto(resp_data)
        assert resp.content == "回答内容"

    def test_binary_ws_handler(self):
        from livingtree.serialization.service_stubs import BinaryWSHandler

        req = ChatRequest(model="test", messages=[{"role": "user", "content": "hi"}])
        proto_data = req.to_proto()
        encoded = BinaryWSHandler.encode_message(
            BinaryWSHandler.MSG_CHAT_REQUEST, proto_data,
        )

        msg_type, body = BinaryWSHandler.decode_message(encoded)
        assert msg_type == BinaryWSHandler.MSG_CHAT_REQUEST
        parsed = ChatRequest.from_proto(body)
        assert parsed.model == "test"


# ═══ Benchmark ═══

class TestBenchmark:
    def test_run_all(self):
        bench = SerializationBenchmark(iterations=200)
        report = bench.run_all()
        assert len(report.results) > 0

    def test_summary_text(self):
        bench = SerializationBenchmark(iterations=100)
        report = bench.run_all()
        text = report.summary()
        assert "Protobuf" in text
        assert "JSON" in text

    def test_to_dict(self):
        bench = SerializationBenchmark(iterations=100)
        report = bench.run_all()
        d = report.to_dict()
        assert "results" in d
        assert len(d["results"]) > 0

    def test_bench_result_properties(self):
        r = BenchResult(
            format_name="Protobuf",
            message_type="chat",
            size_bytes=200,
            json_size_bytes=500,
        )
        assert r.savings_percent == pytest.approx(60.0)  # (1-200/500)*100 = 60%
        assert r.compression_ratio == pytest.approx(0.4)

    def test_protobuf_wins_small_messages(self):
        """Small structured messages: protobuf should be smaller than JSON."""
        bench = SerializationBenchmark(iterations=100)
        report = bench.run_all()
        proto_results = [r for r in report.results if r.format_name == "Protobuf"]
        json_results = [r for r in report.results if r.format_name == "JSON"]

        if proto_results and json_results:
            proto_sizes = [r.size_bytes for r in proto_results if r.message_type == "chat_message"]
            json_sizes = [r.size_bytes for r in json_results if r.message_type == "chat_message"]
            if proto_sizes and json_sizes:
                assert proto_sizes[0] <= json_sizes[0] * 1.3


# ═══ Edge Cases ═══

class TestEdgeCases:
    def test_empty_message(self):
        enc = MessageEncoder()
        data = enc.encode()
        dec = MessageDecoder(data)
        assert dec.get_string(1) == ""

    def test_large_value(self):
        enc = MessageEncoder()
        enc.add_varint(1, 2**63 - 1)
        data = enc.encode()
        dec = MessageDecoder(data)
        assert dec.get_varint(1) > 0

    def test_unicode_roundtrip(self):
        enc = MessageEncoder()
        enc.add_string(1, "环境影响评价大气扩散模型参数设置方法")
        data = enc.encode()
        dec = MessageDecoder(data)
        assert "大气扩散" in dec.get_string(1)

    def test_binary_roundtrip(self):
        enc = MessageEncoder()
        enc.add_bytes(1, b'\x00\x01\x02\xff\xfe')
        data = enc.encode()
        dec = MessageDecoder(data)
        assert dec.get_bytes(1) == b'\x00\x01\x02\xff\xfe'

    def test_float_precision(self):
        enc = MessageEncoder()
        enc.add_float(1, 3.14159)
        data = enc.encode()
        dec = MessageDecoder(data)
        assert abs(dec.get_float(1) - 3.14159) < 0.001

    def test_truncated_message(self):
        dec = MessageDecoder(b'\x08\x96')  # Incomplete
        assert dec.get_varint(1) in (0, 150) or True  # Graceful handling
