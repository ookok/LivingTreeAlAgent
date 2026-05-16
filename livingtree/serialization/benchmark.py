"""Binary Protocol Benchmark Engine — JSON vs Protobuf vs MessagePack vs FlatBuffers.

Measures exact performance differences for LivingTree's real message types:
  - Encode/decode speed (μs per message)
  - Serialized size (bytes)
  - Compression ratio vs JSON baseline

Usage:
    bench = SerializationBenchmark()
    result = bench.run_all()
    print(result.summary())
"""

from __future__ import annotations

import json
import time
import struct
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger

from .protobuf_engine import MessageEncoder, MessageDecoder, encode_varint, decode_varint

import msgpack


@dataclass
class BenchResult:
    """Single benchmark result for one format."""
    format_name: str
    message_type: str
    encode_us: float = 0.0
    decode_us: float = 0.0
    size_bytes: int = 0
    json_size_bytes: int = 0
    iterations: int = 1000
    encode_speedup: float = 0.0   # set after JSON baseline
    decode_speedup: float = 0.0

    @property
    def compression_ratio(self) -> float:
        if self.json_size_bytes == 0:
            return 1.0
        return self.size_bytes / self.json_size_bytes

    @property
    def savings_percent(self) -> float:
        return (1 - self.compression_ratio) * 100


@dataclass
class BenchmarkReport:
    results: list[BenchResult] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            "=" * 78,
            "  Binary Protocol Benchmark — LivingTree Message Types",
            "=" * 78,
            f"{'Format':<16} {'Msg Type':<16} {'Encode':>8} {'Decode':>8} {'Size':>8} {'vs JSON':>8}",
            "-" * 78,
        ]

        for r in self.results:
            speedup = f"{r.encode_speedup:.1f}x" if r.encode_speedup > 0 else "-"
            lines.append(
                f"{r.format_name:<16} {r.message_type:<16} "
                f"{r.encode_us:>6.1f}μs {r.decode_us:>6.1f}μs "
                f"{r.size_bytes:>5d}B {r.savings_percent:>6.1f}%"
            )

        lines.append("=" * 78)

        json_results = [r for r in self.results if r.format_name == "JSON"]
        proto_results = [r for r in self.results if r.format_name == "Protobuf"]
        msgp_results = [r for r in self.results if r.format_name == "MessagePack"]

        if json_results and proto_results:
            avg_json_size = sum(r.size_bytes for r in json_results) / len(json_results)
            avg_proto_size = sum(r.size_bytes for r in proto_results) / len(proto_results)
            savings = (1 - avg_proto_size / avg_json_size) * 100
            lines.append(f"\n  AVERAGE: Protobuf is {savings:.0f}% smaller than JSON")

        if json_results and msgp_results:
            avg_msgp_size = sum(r.size_bytes for r in msgp_results) / len(msgp_results)
            savings = (1 - avg_msgp_size / avg_json_size) * 100
            lines.append(f"  AVERAGE: MessagePack is {savings:.0f}% smaller than JSON")

        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "results": [
                {
                    "format": r.format_name,
                    "type": r.message_type,
                    "encode_us": r.encode_us,
                    "decode_us": r.decode_us,
                    "size_bytes": r.size_bytes,
                    "json_size_bytes": r.json_size_bytes,
                    "savings_percent": r.savings_percent,
                }
                for r in self.results
            ],
            "summary": self.summary(),
        }


class SerializationBenchmark:
    """Benchmarks JSON vs Protobuf vs MessagePack for LivingTree workloads.

    Tests real message patterns from the codebase:
      - chat_message: small frequent chat messages (200-500 chars)
      - task_message: medium task dispatch (500-2000 chars)
      - knowledge_message: large knowledge transfer (5k-50k chars)
      - status_message: tiny health/status updates (50-150 chars)
    """

    def __init__(self, iterations: int = 5000):
        self.iterations = iterations

    def run_all(self) -> BenchmarkReport:
        report = BenchmarkReport()

        messages = [
            ("chat_message", self._make_chat_message()),
            ("chat_long", self._make_long_chat()),
            ("task_message", self._make_task_message()),
            ("knowledge_small", self._make_knowledge_small()),
            ("knowledge_large", self._make_knowledge_large()),
            ("status_message", self._make_status_message()),
            ("node_status", self._make_node_status()),
        ]

        for msg_type, msg in messages:
            report.results.extend(self._bench_message(msg_type, msg))

        return report

    def _bench_message(self, msg_type: str, msg: dict) -> list[BenchResult]:
        results = []

        # JSON benchmark
        enc_json, dec_json, size_json = self._measure_json(msg, self.iterations)
        json_result = BenchResult(
            format_name="JSON", message_type=msg_type,
            encode_us=enc_json, decode_us=dec_json, size_bytes=size_json,
            json_size_bytes=size_json, iterations=self.iterations,
        )
        results.append(json_result)

        # Protobuf benchmark
        enc_proto, dec_proto, size_proto = self._measure_protobuf(msg, self.iterations)
        proto_result = BenchResult(
            format_name="Protobuf", message_type=msg_type,
            encode_us=enc_proto, decode_us=dec_proto, size_bytes=size_proto,
            json_size_bytes=size_json, iterations=self.iterations,
        )
        proto_result.encode_speedup = enc_json / max(enc_proto, 1)
        proto_result.decode_speedup = dec_json / max(dec_proto, 1)
        results.append(proto_result)

        # MessagePack benchmark
        enc_mp, dec_mp, size_mp = self._measure_msgpack(msg, self.iterations)
        mp_result = BenchResult(
            format_name="MessagePack", message_type=msg_type,
            encode_us=enc_mp, decode_us=dec_mp, size_bytes=size_mp,
            json_size_bytes=size_json, iterations=self.iterations,
        )
        mp_result.encode_speedup = enc_json / max(enc_mp, 1)
        mp_result.decode_speedup = dec_json / max(dec_mp, 1)
        results.append(mp_result)

        return results

    def _measure_json(self, msg: dict, iterations: int) -> tuple[float, float, int]:
        json_str = json.dumps(msg, ensure_ascii=False)
        data = json_str.encode("utf-8")

        start = time.perf_counter()
        for _ in range(iterations):
            encoded = json.dumps(msg, ensure_ascii=False).encode("utf-8")
        encode_time = (time.perf_counter() - start) / iterations * 1e6

        start = time.perf_counter()
        for _ in range(iterations):
            decoded = json.loads(data)
        decode_time = (time.perf_counter() - start) / iterations * 1e6

        return encode_time, decode_time, len(data)

    def _measure_protobuf(self, msg: dict, iterations: int) -> tuple[float, float, int]:
        encoder = self._dict_to_proto(msg)
        data = encoder.encode()

        start = time.perf_counter()
        for _ in range(iterations):
            enc = self._dict_to_proto(msg)
            enc.encode()
        encode_time = (time.perf_counter() - start) / iterations * 1e6

        start = time.perf_counter()
        for _ in range(iterations):
            MessageDecoder(data)
        decode_time = (time.perf_counter() - start) / iterations * 1e6

        return encode_time, decode_time, len(data)

    def _measure_msgpack(self, msg: dict, iterations: int) -> tuple[float, float, int]:
        data = msgpack.packb(msg)

        start = time.perf_counter()
        for _ in range(iterations):
            msgpack.packb(msg)
        encode_time = (time.perf_counter() - start) / iterations * 1e6

        start = time.perf_counter()
        for _ in range(iterations):
            msgpack.unpackb(data)
        decode_time = (time.perf_counter() - start) / iterations * 1e6

        return encode_time, decode_time, len(data)

    def _dict_to_proto(self, msg: dict) -> MessageEncoder:
        enc = MessageEncoder()
        field_idx = 1
        for key, value in msg.items():
            if isinstance(value, bool):
                enc.add_bool(field_idx, value)
            elif isinstance(value, int):
                if value < 0:
                    enc.add_signed(field_idx, value)
                else:
                    enc.add_varint(field_idx, value)
            elif isinstance(value, float):
                enc.add_double(field_idx, value)
            elif isinstance(value, str):
                enc.add_string(field_idx, value)
            elif isinstance(value, bytes):
                enc.add_bytes(field_idx, value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, str):
                        enc.add_string(field_idx, str(item))
                    elif isinstance(item, dict):
                        sub = self._dict_to_proto(item)
                        enc.add_message(field_idx, sub)
            elif isinstance(value, dict):
                sub = self._dict_to_proto(value)
                enc.add_message(field_idx, sub)
            field_idx += 1
        return enc

    # ── Message factories ──

    @staticmethod
    def _make_chat_message() -> dict:
        return {
            "model": "deepseek-v4-pro",
            "messages": [
                {"role": "system", "content": "你是环评专家助手"},
                {"role": "user", "content": "大气扩散模型参数如何设置？"},
            ],
            "temperature": 0.7,
            "max_tokens": 4096,
            "stream": False,
        }

    @staticmethod
    def _make_long_chat() -> dict:
        return {
            "model": "deepseek-v4-pro",
            "messages": [
                {"role": "user", "content": "请详细分析环评报告中大气扩散模型、噪声衰减模型、水污染扩散模型的参数设置方法和标准依据。需要包括GB3095、HJ2.2等标准的具体要求。"},
            ],
            "temperature": 0.5,
            "max_tokens": 8192,
            "stream": True,
            "metadata": {"source": "web", "priority": "high", "user_id": "u12345"},
        }

    @staticmethod
    def _make_task_message() -> dict:
        return {
            "task_id": "task_20260401_001",
            "type": "generate",
            "description": "生成环评报告大气环境影响评价章节" * 5,
            "parameters": {
                "template": "eia_atmosphere",
                "standards": "GB3095;HJ2.2",
                "language": "zh",
            },
            "dependencies": ["data_202603", "template_v3"],
            "priority": 3,
            "deadline_ms": 3600000,
            "source_node": "node_beijing_01",
        }

    @staticmethod
    def _make_knowledge_small() -> dict:
        return {
            "doc_id": "doc_eia_2026",
            "title": "环评大气扩散技术规范",
            "source": "knowledge_base",
            "chunks": [
                {"index": 0, "text": "依据HJ2.2-2018标准，大气扩散模型参数包括：" * 3},
                {"index": 1, "text": "AERMOD模式适用于平坦地形。CALPUFF适用于复杂地形。" * 3},
            ],
        }

    @staticmethod
    def _make_knowledge_large() -> dict:
        return {
            "doc_id": "doc_large_2026",
            "title": "环评综合技术报告汇编",
            "source": "batch_generation",
            "chunks": [
                {"index": i, "text": f"第{i}章技术内容。依据相关标准规范要求，本项目环境影响评价...。监测数据表明各项指标符合标准。" * 20}
                for i in range(50)
            ],
            "metadata": {"total_chars": "50000", "standards": "GB3095;GB12348;HJ2.2"},
        }

    @staticmethod
    def _make_status_message() -> dict:
        return {
            "node_id": "node_bj_01",
            "status": "online",
            "cpu_usage": 0.45,
            "memory_usage": 0.62,
            "active_tasks": 3,
        }

    @staticmethod
    def _make_node_status() -> dict:
        return {
            "node_id": "node_sh_02",
            "status": "busy",
            "capabilities": ["chat", "generate", "train", "search", "analyze"],
            "cpu_usage": 0.78,
            "memory_usage": 0.85,
            "disk_usage": 0.55,
            "active_tasks": 12,
            "uptime_seconds": 864000,
            "custom_metrics": {"qps": 150.5, "error_rate": 0.002, "avg_latency_ms": 45.3},
        }


def run_benchmark() -> BenchmarkReport:
    """Convenience: run all benchmarks and print summary."""
    bench = SerializationBenchmark(iterations=2000)
    report = bench.run_all()
    print(report.summary())
    return report
