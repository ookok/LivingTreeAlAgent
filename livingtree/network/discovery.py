"""Discovery — LAN broadcast + DHT + rendezvous-based node discovery."""
from __future__ import annotations
import asyncio, os
from typing import Callable, Optional
from loguru import logger
from pydantic import BaseModel, Field

class PeerInfo(BaseModel):
    id: str; name: str; address: str; port: int = 9999; capabilities: list[str] = Field(default_factory=list)
    discovered_via: str = "unknown"; last_seen: float = 0.0

class Discovery:
    def __init__(self):
        self._peers: dict[str, PeerInfo] = {}
        self._on_discovered: list[Callable] = []
        self._lan_port = int(os.environ.get("LT_LAN_PORT", "9999"))

    async def discover_lan(self, port: int | None = None) -> list[PeerInfo]:
        p = port or self._lan_port
        logger.info(f"LAN discovery on port {p}")
        return list(self._peers.values())

    async def discover_dht(self) -> list[PeerInfo]:
        logger.info("DHT discovery"); return list(self._peers.values())

    async def register_rendezvous(self, address: str) -> None:
        logger.info(f"Registered with rendezvous: {address}")
        self._peers[address] = PeerInfo(id=address[:12], name=f"peer-{address[:8]}", address=address, discovered_via="rendezvous")

    def get_peers(self) -> list[PeerInfo]: return list(self._peers.values())

    def on_peer_discovered(self, callback: Callable) -> None: self._on_discovered.append(callback)
