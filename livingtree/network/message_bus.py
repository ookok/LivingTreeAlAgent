"""Binary Message Bus — high-performance protobuf serialization for all P2P messages.

Replaces JSON with protobuf for:
- Swarm peer communication (cell migration, knowledge sync, task distribution)
- Node discovery announcements
- Health/status heartbeat
- Cognitive event streaming

Expected: 5-10x faster serialization, 40%+ bandwidth reduction vs JSON.

Uses the compiled livingtree.proto at livingtree/network/livingtree_pb2.py
"""

from __future__ import annotations

import struct
import time as _time
from typing import Any, Optional

from loguru import logger

from . import livingtree_pb2 as pb


FRAME_MAGIC = b"LT\x01"  # LT protocol v1
FRAME_HEADER_SIZE = 8  # magic(3) + msg_type(1) + payload_len(4)


def encode_discovery_announce(node_id: str, name: str, host: str,
                               api_port: int, capabilities: list[str]) -> bytes:
    """Encode a LAN discovery announcement as binary."""
    status = pb.NodeStatus(
        node_id=node_id,
        status="online",
        capabilities=capabilities,
        custom_metrics={"api_port": float(api_port)},
    )
    payload = status.SerializeToString()
    return FRAME_MAGIC + struct.pack("!BI", 0x01, len(payload)) + payload


def decode_discovery_announce(data: bytes) -> Optional[dict]:
    """Decode a LAN discovery announcement from binary."""
    try:
        if not data.startswith(FRAME_MAGIC):
            return None
        payload_start = FRAME_HEADER_SIZE
        msg_type = data[3]
        if msg_type != 0x01:
            return None
        payload_len = struct.unpack("!I", data[4:FRAME_HEADER_SIZE])[0]
        payload = data[payload_start:payload_start + payload_len]
        status = pb.NodeStatus()
        status.ParseFromString(payload)
        return {
            "node_id": status.node_id,
            "status": status.status,
            "capabilities": list(status.capabilities),
            "api_port": int(status.custom_metrics.get("api_port", 8100)),
        }
    except Exception as e:
        logger.debug(f"Binary decode error: {e}")
        return None


def encode_cell_share(cell_name: str, model_name: str, capability: str,
                       genome_data: dict, from_node: str) -> bytes:
    """Encode cell migration data as binary task request."""
    task = pb.TaskRequest(
        task_id=f"cell_{cell_name}_{int(_time.time())}",
        type="cell_share",
        description=cell_name,
        parameters={
            "model_name": model_name.encode(),
            "capability": capability.encode(),
            "genome_data": str(genome_data).encode(),
        },
        source_node=from_node,
        priority=7,
    )
    payload = task.SerializeToString()
    return FRAME_MAGIC + struct.pack("!BI", 0x02, len(payload)) + payload


def decode_cell_share(data: bytes) -> Optional[dict]:
    """Decode a cell share message from binary."""
    try:
        if not data.startswith(FRAME_MAGIC):
            return None
        payload_len = struct.unpack("!I", data[4:FRAME_HEADER_SIZE])[0]
        payload = data[FRAME_HEADER_SIZE:FRAME_HEADER_SIZE + payload_len]
        task = pb.TaskRequest()
        task.ParseFromString(payload)
        return {
            "cell_name": task.description,
            "model_name": task.parameters.get("model_name", b"").decode(),
            "capability": task.parameters.get("capability", b"general").decode(),
            "from_node": task.source_node,
            "genome_data": {},
        }
    except Exception:
        return None


def encode_knowledge_sync(entries: list[dict], from_node: str) -> bytes:
    """Encode knowledge sync as KnowledgeMessage binary."""
    chunks = []
    for i, e in enumerate(entries):
        chunks.append(pb.Chunk(
            chunk_id=f"sync_{i}",
            index=i,
            text=e.get("content", "")[:1000],
            section_path=e.get("domain", "general"),
        ))
    km = pb.KnowledgeMessage(
        doc_id=f"sync_{int(_time.time())}",
        source=from_node,
        chunks=chunks,
        metadata={"count": str(len(entries))},
    )
    payload = km.SerializeToString()
    return FRAME_MAGIC + struct.pack("!BI", 0x03, len(payload)) + payload


def decode_knowledge_sync(data: bytes) -> Optional[dict]:
    """Decode knowledge sync from binary."""
    try:
        if not data.startswith(FRAME_MAGIC):
            return None
        payload_len = struct.unpack("!I", data[4:FRAME_HEADER_SIZE])[0]
        payload = data[FRAME_HEADER_SIZE:FRAME_HEADER_SIZE + payload_len]
        km = pb.KnowledgeMessage()
        km.ParseFromString(payload)
        entries = []
        for c in km.chunks:
            entries.append({
                "content": c.text,
                "domain": c.section_path,
                "source": km.source,
            })
        return {"entries": entries, "count": len(entries), "from_node": km.source}
    except Exception:
        return None


def encode_task_distribute(goal: str, from_node: str, subtask: str = "") -> bytes:
    """Encode a distributed task as binary."""
    task = pb.TaskRequest(
        task_id=f"dist_{int(_time.time() * 1000)}",
        type="distribute",
        description=subtask or goal,
        parameters={"goal": goal.encode()},
        source_node=from_node,
        priority=5,
    )
    payload = task.SerializeToString()
    return FRAME_MAGIC + struct.pack("!BI", 0x04, len(payload)) + payload


def decode_task_distribute(data: bytes) -> Optional[dict]:
    """Decode a distributed task from binary."""
    try:
        if not data.startswith(FRAME_MAGIC):
            return None
        payload_len = struct.unpack("!I", data[4:FRAME_HEADER_SIZE])[0]
        payload = data[FRAME_HEADER_SIZE:FRAME_HEADER_SIZE + payload_len]
        task = pb.TaskRequest()
        task.ParseFromString(payload)
        return {
            "task_id": task.task_id,
            "type": task.type,
            "goal": task.parameters.get("goal", b"").decode() or task.description,
            "subtask": task.description,
            "source_node": task.source_node,
            "priority": task.priority,
        }
    except Exception:
        return None


def encode_task_response(task_id: str, status: str, result: str = "",
                          progress: float = 1.0) -> bytes:
    """Encode a task execution response as binary."""
    resp = pb.TaskResponse(
        task_id=task_id,
        status=status,
        result=result.encode()[:2000] if result else b"",
        progress=progress,
        completed_at=int(_time.time() * 1000),
    )
    payload = resp.SerializeToString()
    return FRAME_MAGIC + struct.pack("!BI", 0x05, len(payload)) + payload


def decode_task_response(data: bytes) -> Optional[dict]:
    """Decode task response from binary."""
    try:
        if not data.startswith(FRAME_MAGIC):
            return None
        payload_len = struct.unpack("!I", data[4:FRAME_HEADER_SIZE])[0]
        payload = data[FRAME_HEADER_SIZE:FRAME_HEADER_SIZE + payload_len]
        resp = pb.TaskResponse()
        resp.ParseFromString(payload)
        return {
            "task_id": resp.task_id,
            "status": resp.status,
            "result": resp.result.decode()[:500] if resp.result else "",
            "progress": resp.progress,
        }
    except Exception:
        return None


def encode_health_report(node_id: str, status: str, score: float,
                          capabilities: list[str]) -> bytes:
    """Encode health/status heartbeat as binary."""
    hs = pb.HealthResponse(
        status=status,
        timestamp=int(_time.time() * 1000),
        metrics={"score": score},
    )
    ns = pb.NodeStatus(
        node_id=node_id,
        status=status,
        capabilities=capabilities,
        custom_metrics={"score": score},
    )
    payload = ns.SerializeToString()
    return FRAME_MAGIC + struct.pack("!BI", 0x06, len(payload)) + payload


def decode_health_report(data: bytes) -> Optional[dict]:
    """Decode health report from binary."""
    try:
        if not data.startswith(FRAME_MAGIC):
            return None
        payload_len = struct.unpack("!I", data[4:FRAME_HEADER_SIZE])[0]
        payload = data[FRAME_HEADER_SIZE:FRAME_HEADER_SIZE + payload_len]
        ns = pb.NodeStatus()
        ns.ParseFromString(payload)
        return {
            "node_id": ns.node_id,
            "status": ns.status,
            "score": ns.custom_metrics.get("score", 0.0),
            "capabilities": list(ns.capabilities),
        }
    except Exception:
        return None


def identify_frame(data: bytes) -> int:
    """Identify message type from binary frame header. Returns msg_type byte or -1."""
    if len(data) < FRAME_HEADER_SIZE:
        return -1
    if data[:3] != FRAME_MAGIC[:3]:
        return -1
    return data[3]


def serialize_any(msg_type: int, payload: bytes) -> bytes:
    """Wrap any payload in a binary frame."""
    return FRAME_MAGIC + struct.pack("!BI", msg_type, len(payload)) + payload


FRAME_HANDLERS = {
    0x01: ("discovery_announce", decode_discovery_announce),
    0x02: ("cell_share", decode_cell_share),
    0x03: ("knowledge_sync", decode_knowledge_sync),
    0x04: ("task_distribute", decode_task_distribute),
    0x05: ("task_response", decode_task_response),
    0x06: ("health_report", decode_health_report),
}


def decode_frame(data: bytes) -> Optional[tuple[str, dict]]:
    """Universal binary frame decoder. Returns (message_type_name, decoded_dict)."""
    msg_type = identify_frame(data)
    if msg_type < 0:
        return None
    handler = FRAME_HANDLERS.get(msg_type)
    if not handler:
        return None
    name, decoder = handler
    result = decoder(data)
    if result is None:
        return None
    return (name, result)
