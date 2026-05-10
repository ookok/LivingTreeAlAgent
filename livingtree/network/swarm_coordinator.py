"""SwarmCoordinator — Direct P2P collaboration between LivingTree nodes.

Enables:
- Direct peer-to-peer communication (no relay required)
- Cell migration between trusted nodes (protobuf binary)
- Knowledge sync (protobuf KnowledgeMessage)
- Cross-node task distribution (protobuf TaskRequest/Response)
- Reputation-weighted trust decisions

All messages use protobuf binary serialization (message_bus.py) for
5-10x faster serialization and 40%+ bandwidth reduction vs JSON.
"""

from __future__ import annotations

import asyncio
import time as _time
from typing import Any, Optional

import aiohttp
from loguru import logger

from .message_bus import (
    encode_cell_share, decode_cell_share,
    encode_knowledge_sync, decode_knowledge_sync,
    encode_task_distribute, decode_task_distribute,
    encode_task_response, decode_task_response,
    encode_health_report, decode_health_report,
)


class SwarmCoordinator:
    """Coordinates direct P2P collaboration between LivingTree instances."""

    def __init__(self, hub=None):
        self._hub = hub
        self._session: Optional[aiohttp.ClientSession] = None
        self._running = False
        self._sync_tasks: list[asyncio.Task] = []

    async def start(self):
        if self._running:
            return
        self._running = True
        self._session = aiohttp.ClientSession()
        logger.info("SwarmCoordinator: direct P2P collaboration active")

    async def stop(self):
        self._running = False
        for t in self._sync_tasks:
            t.cancel()
        if self._session:
            await self._session.close()
            self._session = None

    @property
    def hub(self):
        return self._hub

    @property
    def discovery(self):
        if self._hub and hasattr(self._hub, "world"):
            return getattr(self._hub.world, "discovery", None)
        return None

    @property
    def reputation(self):
        if self._hub and hasattr(self._hub, "world"):
            return getattr(self._hub.world, "reputation", None)
        return None

    def get_trusted_peers(self) -> list:
        """Get LAN-discovered peers that are trusted."""
        if not self.discovery:
            return []
        peers = self.discovery.get_peers()
        trusted = []
        for p in peers:
            if self.reputation and self.reputation.is_trusted(p.id):
                trusted.append(p)
            elif not self.reputation:
                trusted.append(p)
        return trusted

    async def ping_peer(self, endpoint: str) -> Optional[dict]:
        """Check if a peer is reachable via binary health probe."""
        if not self._session:
            return None
        try:
            node_id = ""
            if self.hub and self.hub.world and self.hub.world.node:
                node_id = self.hub.world.node.info.id
            binary_payload = encode_health_report(node_id, "ping", 1.0, [])
            async with self._session.post(
                f"{endpoint}/api/swarm/ping",
                data=binary_payload,
                headers={"Content-Type": "application/octet-stream"},
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                if resp.status == 200:
                    raw = await resp.read()
                    decoded = decode_health_report(raw)
                    return decoded or {"status": "ok"}
        except Exception:
            pass
        return None

    # ── Cell Migration ──

    async def share_cell(self, peer_endpoint: str, cell_name: str) -> dict:
        """Share a trained cell with a trusted peer via binary protobuf."""
        world = self.hub.world if self.hub else None
        if not world:
            return {"ok": False, "error": "no world"}

        registry = getattr(world, "cell_registry", None)
        if not registry:
            return {"ok": False, "error": "no cell registry"}

        cells = registry.discover()
        cell = next((c for c in cells if getattr(c, "name", "") == cell_name), None)
        if not cell:
            return {"ok": False, "error": f"cell '{cell_name}' not found"}

        genome = getattr(cell, "genome", None)
        genome_data = genome.to_dict() if genome and hasattr(genome, "to_dict") else {}
        node_id = getattr(getattr(world, "node", None), "info", {}).get("id", "unknown")

        binary_payload = encode_cell_share(
            cell_name=cell_name,
            model_name=getattr(cell, "model_name", ""),
            capability=getattr(cell, "capability", "general"),
            genome_data=genome_data,
            from_node=node_id,
        )

        try:
            async with self._session.post(
                f"{peer_endpoint}/api/swarm/cell/receive",
                data=binary_payload,
                headers={"Content-Type": "application/octet-stream"},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                raw = await resp.read()
                decoded = decode_task_response(raw)
                if decoded:
                    return {"ok": decoded["status"] == "completed", "cell_name": cell_name}
                return {"ok": False, "error": "decode failed"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    async def receive_cell(self, raw_data: bytes) -> dict:
        """Receive and register a cell from binary protobuf."""
        world = self.hub.world if self.hub else None
        if not world:
            return {"ok": False, "error": "no world"}

        decoded = decode_cell_share(raw_data)
        if not decoded:
            return {"ok": False, "error": "decode failed"}

        try:
            from ..cell import CellAI
            from_node = decoded.get("from_node", "unknown")
            cell = CellAI(
                name=f"{decoded['cell_name']}_from_{from_node[:8]}",
                model_name=decoded.get("model_name", ""),
            )
            world.cell_registry.register(cell)
            logger.info(f"Cell received via binary: {cell.name}")
            return {"cell_name": cell.name}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ── Knowledge Sync ──

    async def share_knowledge(self, peer_endpoint: str, query: str = "", top_k: int = 10) -> dict:
        """Share knowledge base entries via binary KnowledgeMessage."""
        world = self.hub.world if self.hub else None
        if not world:
            return {"ok": False, "error": "no world"}

        kb = getattr(world, "knowledge_base", None)
        if not kb:
            return {"ok": False, "error": "no knowledge base"}

        node_id = getattr(getattr(world, "node", None), "info", {}).get("id", "unknown")
        try:
            docs = kb.get_by_domain(None) if hasattr(kb, "get_by_domain") else []
            entries = []
            for doc in docs[:top_k]:
                entries.append({
                    "content": getattr(doc, "content", str(doc))[:500],
                    "domain": getattr(doc, "domain", "general"),
                })

            binary_payload = encode_knowledge_sync(entries, node_id)
            async with self._session.post(
                f"{peer_endpoint}/api/swarm/knowledge/receive",
                data=binary_payload,
                headers={"Content-Type": "application/octet-stream"},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                raw = await resp.read()
                decoded = decode_task_response(raw)
                return decoded or {"ok": True, "count": len(entries)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    async def receive_knowledge(self, raw_data: bytes) -> dict:
        """Receive knowledge entries from binary protobuf."""
        world = self.hub.world if self.hub else None
        if not world:
            return {"ok": False, "error": "no world"}

        decoded = decode_knowledge_sync(raw_data)
        if not decoded:
            return {"ok": False, "error": "decode failed"}

        entries = decoded.get("entries", [])
        kb = getattr(world, "knowledge_base", None)
        if kb and hasattr(kb, "add_document"):
            for entry in entries:
                try:
                    kb.add_document(content=entry.get("content", ""), domain=entry.get("domain", "general"))
                except Exception:
                    pass

        logger.info(f"Knowledge sync (binary): received {len(entries)} entries")
        return {"received": len(entries)}

    # ── Task Distribution ──

    async def distribute_task(self, goal: str, peer_endpoints: list[str]) -> dict:
        """Distribute a complex task via binary TaskRequest to multiple peers."""
        if not peer_endpoints:
            return {"ok": False, "error": "no peers available"}

        consc = self.hub.world.consciousness if self.hub and self.hub.world else None
        if not consc:
            return {"ok": False, "error": "no consciousness"}

        resp = await consc.chain_of_thought(
            f"将以下任务拆解为独立子任务(每行一个，以- 开头)，可以并行执行:\n\n{goal}\n\n"
            f"可用的节点数: {len(peer_endpoints)}",
            steps=1,
        )
        text = resp if isinstance(resp, str) else str(resp)
        subtasks = [l.strip().lstrip("- ").strip() for l in text.split("\n") if l.strip().startswith("-")]
        if not subtasks:
            subtasks = [goal]

        node_id = getattr(getattr(self.hub.world, "node", None), "info", {}).get("id", "unknown")
        tasks = []
        for i, sub in enumerate(subtasks[:len(peer_endpoints)]):
            ep = peer_endpoints[i % len(peer_endpoints)]
            binary_payload = encode_task_distribute(goal, node_id, sub)
            tasks.append(self._send_binary_task(ep, binary_payload))

        responses = await asyncio.gather(*tasks, return_exceptions=True)
        results = []
        for j, r in enumerate(responses):
            if isinstance(r, Exception):
                results.append({"subtask": subtasks[j] if j < len(subtasks) else "", "status": "error", "error": str(r)})
            else:
                results.append(r)

        return {
            "ok": True,
            "total_subtasks": len(subtasks),
            "completed": sum(1 for r in results if r.get("status") == "completed"),
            "results": results,
        }

    async def _send_binary_task(self, endpoint: str, binary_payload: bytes) -> dict:
        try:
            async with self._session.post(
                f"{endpoint}/api/swarm/task/execute",
                data=binary_payload,
                headers={"Content-Type": "application/octet-stream"},
                timeout=aiohttp.ClientTimeout(total=60),
            ) as resp:
                raw = await resp.read()
                decoded = decode_task_response(raw)
                return decoded or {"status": "error", "error": "decode failed"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ── Status ──

    def status(self) -> dict:
        trusted = self.get_trusted_peers()
        return {
            "active": self._running,
            "trusted_peers": len(trusted),
            "peers": [
                {
                    "id": p.id,
                    "name": p.name,
                    "endpoint": p.to_endpoint(),
                    "capabilities": p.capabilities,
                    "trusted": p.is_trusted or (self.reputation and self.reputation.is_trusted(p.id)),
                    "last_seen": p.last_seen,
                }
                for p in trusted
            ],
        }


_swarm_instance: Optional[SwarmCoordinator] = None


def get_swarm() -> SwarmCoordinator:
    global _swarm_instance
    if _swarm_instance is None:
        _swarm_instance = SwarmCoordinator()
    return _swarm_instance
