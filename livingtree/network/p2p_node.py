"""P2PNode — standalone P2P networking (relay optional).

Auto-generates unique node ID. Relay connection is optional — 
the node works fine in local/offline mode without it.
"""
from __future__ import annotations

import asyncio
import json
import os
import platform
import secrets
import socket
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import aiohttp
from loguru import logger

NODE_ID_FILE = Path(".livingtree/node_id.json")
RELAY_URL = os.environ.get("LT_RELAY_URL", "http://www.mogoo.com.cn:8899")
_relay_pool: list[str] = []
_current_relay_index = 0
HEARTBEAT_INTERVAL = 30
WS_RECONNECT_DELAY = 5
RELAY_ENABLED = True  # Set to False to fully disable relay


@dataclass
class NodeCapabilities:
    providers: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    models: list[str] = field(default_factory=list)
    kb_domains: list[str] = field(default_factory=list)
    cpu_cores: int = 0
    memory_gb: float = 0.0
    platform: str = ""
    # Location info
    city: str = ""
    region: str = ""
    country: str = ""
    latitude: float = 0.0
    longitude: float = 0.0
    isp: str = ""


@dataclass
class PeerInfo:
    peer_id: str
    address: str = ""
    capabilities: NodeCapabilities | None = None
    last_seen: float = 0.0
    connected: bool = False
    location: dict = field(default_factory=dict)


class P2PNode:
    """P2P networking — auto-discovery, capability sharing, direct connect."""

    def __init__(self, hub=None):
        self._hub = hub
        self.node_id = self._load_or_generate_id()
        self._peers: dict[str, PeerInfo] = {}
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._running = False
        self._tasks: list[asyncio.Task] = []
        self._on_message_handlers: list[callable] = []
        logger.info(f"P2P Node: {self.node_id[:16]}")

    def _get_active_relay(self) -> str:
        """Get the currently active relay URL, cycling on failure."""
        global _relay_pool, _current_relay_index
        pool = [RELAY_URL] + _relay_pool
        if not pool:
            return RELAY_URL
        return pool[_current_relay_index % len(pool)]

    def _switch_relay(self):
        """Switch to next relay on failure."""
        global _current_relay_index
        _current_relay_index += 1
        pool = [RELAY_URL] + _relay_pool
        url = self._get_active_relay()
        logger.info(f"Switched relay: {url} ({_current_relay_index % len(pool)}/{len(pool)})")
        return url

    # ═══ Node ID ═══

    def _load_or_generate_id(self) -> str:
        try:
            if NODE_ID_FILE.exists():
                data = json.loads(NODE_ID_FILE.read_text())
                return data["node_id"]
        except Exception:
            pass

        node_id = f"lt-{platform.node()[:8]}-{secrets.token_hex(4)}"
        NODE_ID_FILE.parent.mkdir(parents=True, exist_ok=True)
        NODE_ID_FILE.write_text(json.dumps({"node_id": node_id, "created": time.time()}))
        return node_id

    # ═══ Default component lifecycle ═══

    async def start(self):
        self._running = True
        if RELAY_ENABLED:
            self._tasks.append(asyncio.create_task(self._heartbeat_loop()))
            self._tasks.append(asyncio.create_task(self._ws_listen()))
        try:
            from ..dna.swarm_evolution import get_swarm_evolution
            se = get_swarm_evolution()
            se.register_with_p2p(self)
        except Exception:
            pass
        logger.info(f"P2P started: {self.node_id[:16]}" + (" (relay)" if RELAY_ENABLED else " (local)"))

    async def stop(self):
        self._running = False
        for t in self._tasks:
            t.cancel()
        if self._ws:
            await self._ws.close()
        logger.info("P2P stopped")

    # ═══ Heartbeat: broadcast capabilities to relay ═══

    async def _heartbeat_loop(self):
        await asyncio.sleep(2)
        fail_count = 0
        while self._running:
            try:
                caps = self._collect_capabilities()
                relay_url = self._get_active_relay()
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{relay_url}/peers/register",
                        json={"peer_id": self.node_id, "port": 0, "nat_type": "client", "metadata": {
                            "username": getattr(self, "_username", ""),
                            "capabilities": {
                                "providers": caps.providers, "tools": caps.tools,
                                "skills": caps.skills, "models": caps.models,
                                "kb_domains": caps.kb_domains,
                            },
                            "cpu": caps.cpu_cores, "memory_gb": caps.memory_gb,
                            "platform": caps.platform,
                            "location": {
                                "city": caps.city, "region": caps.region,
                                "country": caps.country, "lat": caps.latitude,
                                "lon": caps.longitude, "isp": caps.isp,
                            },
                        }},
                        timeout=10,
                    ) as resp:
                        if resp.status == 200:
                            fail_count = 0
                await asyncio.sleep(HEARTBEAT_INTERVAL)
            except Exception:
                fail_count += 1
                if fail_count >= 3:
                    self._switch_relay()
                    fail_count = 0
                await asyncio.sleep(5)

    async def report_cost(self, provider: str, tokens_in: int, tokens_out: int):
        """Report token usage to relay server for cost tracking."""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {}
                if hasattr(self, '_auth_token') and self._auth_token:
                    headers["Authorization"] = f"Bearer {self._auth_token}"
                await session.post(
                    f"{RELAY_URL}/cost/report",
                    json={"provider": provider, "tokens_in": tokens_in, "tokens_out": tokens_out},
                    headers=headers,
                    timeout=5,
                )
        except Exception:
            pass

    async def login(self, username: str, password: str) -> str:
        """Login to relay server. Returns token on success, error message on failure."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{RELAY_URL}/login",
                    json={"username": username, "password": password},
                    timeout=10,
                ) as resp:
                    data = await resp.json()
                    if resp.status == 200:
                        self._auth_token = data.get("token", "")
                        self._username = username
                        return ""
                    return data.get("error", "登录失败")
        except Exception as e:
            return f"连接失败: {e}"

    def _collect_capabilities(self) -> NodeCapabilities:
        caps = NodeCapabilities(platform=platform.system())
        caps.cpu_cores = os.cpu_count() or 0
        try:
            import psutil
            caps.memory_gb = psutil.virtual_memory().total / (1024**3)
        except ImportError:
            pass

        if self._hub and self._hub.world:
            try:
                llm = self._hub.world.consciousness._llm
                caps.providers = list(llm._providers.keys())[:10]
            except Exception:
                pass

        try:
            from ..core.unified_registry import get_registry
            r = get_registry()
            caps.tools = list(r.tools.keys())[:20]
            caps.skills = list(r.skills.keys())[:10]
        except Exception:
            pass

        # Location detection (lazy, cached)
        self._fill_location(caps)
        return caps

    def _fill_location(self, caps: NodeCapabilities):
        """Auto-detect geographic location via IP lookup (cached)."""
        if hasattr(self, '_location_filled') and self._location_filled:
            return
        try:
            import urllib.request, json
            # Use ip-api.com (free, no key needed)
            req = urllib.request.Request("http://ip-api.com/json/", headers={"User-Agent": "LivingTree/2.1"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
                caps.city = data.get("city", "")
                caps.region = data.get("regionName", "")
                caps.country = data.get("country", "")
                caps.latitude = data.get("lat", 0.0)
                caps.longitude = data.get("lon", 0.0)
                caps.isp = data.get("isp", "")
                self._location_filled = True
                logger.debug(f"Location: {caps.city}, {caps.region}, {caps.country}")
        except Exception as e:
            logger.debug(f"Location detect: {e}")

    # ═══ WebSocket: listen for peer messages ═══

    async def _ws_listen(self):
        while self._running:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.ws_connect(f"{RELAY_URL}/ws/relay") as ws:
                        self._ws = ws
                        logger.debug("WS connected to relay")
                        async for msg in ws:
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                data = json.loads(msg.data)
                                for handler in self._on_message_handlers:
                                    try:
                                        await handler(data)
                                    except Exception:
                                        pass
            except Exception as e:
                logger.debug(f"Relay WS reconnect in {WS_RECONNECT_DELAY}s")
                await asyncio.sleep(WS_RECONNECT_DELAY)

    def on_message(self, handler):
        """Register a callback for incoming P2P messages."""
        self._on_message_handlers.append(handler)

    # ═══ Peer discovery ═══

    async def discover_peers(self) -> list[PeerInfo]:
        """Fetch peer list + relay pool from relay server."""
        global _relay_pool
        relay_url = self._get_active_relay()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{relay_url}/peers/discover", timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        peers = []
                        for p in data.get("peers", []):
                            pid = p["peer_id"]
                            if pid == self.node_id:
                                continue
                            meta = p.get("metadata", {})
                            caps_data = meta.get("capabilities", {})
                            info = PeerInfo(peer_id=pid, last_seen=p.get("last_seen", 0),
                                           location=meta.get("location", {}))
                            info.capabilities = NodeCapabilities(
                                providers=caps_data.get("providers", []),
                                tools=caps_data.get("tools", []),
                                skills=caps_data.get("skills", []),
                                models=caps_data.get("models", []),
                                kb_domains=caps_data.get("kb_domains", []),
                                cpu_cores=meta.get("cpu", 0),
                                memory_gb=meta.get("memory_gb", 0),
                                platform=meta.get("platform", ""),
                            )
                            peers.append(info)
                        self._peers = {p.peer_id: p for p in peers}
                        # Update relay pool from server broadcast
                        pool = data.get("relay_pool", [])
                        if pool:
                            _relay_pool = [u for u in pool if u != RELAY_URL]
                        return peers
        except Exception as e:
            logger.debug(f"Peer discovery: {e}")
        return []

    # ═══ Connect to a specific node ═══

    async def connect_to(self, peer_id: str) -> str:
        """Initiate a connection to a specific peer node."""
        if peer_id == self.node_id:
            return "不能连接自己"

        # Check if already known
        if peer_id in self._peers:
            peer = self._peers[peer_id]
            caps_str = ""
            if peer.capabilities:
                caps_str = f" (工具:{len(peer.capabilities.tools)}, 技能:{len(peer.capabilities.skills)})"
            return f"已连接到 {peer_id[:16]}...{caps_str}"

        # Try to discover
        peers = await self.discover_peers()
        for p in peers:
            if peer_id.startswith(p.peer_id[:16]):
                caps_str = ""
                if p.capabilities:
                    caps_str = f" (提供者:{len(p.capabilities.providers)}, 工具:{len(p.capabilities.tools)})"
                self._peers[p.peer_id] = p
                return f"✓ 已连接到 {p.peer_id[:16]}...{caps_str}"

        return f"未找到节点: {peer_id[:16]}..."

    async def send_to_peer(self, peer_id: str, data: dict) -> bool:
        """Send a message to a specific peer via WebSocket relay."""
        if self._ws and not self._ws.closed:
            await self._ws.send_json({"to": peer_id, "data": data})
            return True
        return False

    def get_status(self) -> dict:
        return {
            "node_id": self.node_id[:16] + "...",
            "peers": len(self._peers),
            "ws_connected": self._ws is not None and not self._ws.closed,
            "running": self._running,
        }


# ═══ Global default component ═══

_node: P2PNode | None = None


def get_p2p_node(hub=None) -> P2PNode:
    global _node
    if _node is None:
        _node = P2PNode(hub)
    return _node
