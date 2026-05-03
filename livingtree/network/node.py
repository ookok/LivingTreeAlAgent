"""Node — P2P node with identity, heartbeat, and capability broadcasting."""
from __future__ import annotations
import asyncio, uuid, json
from datetime import datetime, timezone
from typing import Optional
from loguru import logger
from pydantic import BaseModel, Field

class NodeInfo(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = "livingtree-node"; version: str = "2.0.0"
    capabilities: list[str] = Field(default_factory=list)
    status: str = "offline"; address: str = ""; port: int = 0
    last_heartbeat: str = ""

class Node:
    def __init__(self, name: str = "livingtree-node", capabilities: list[str] | None = None):
        self.info = NodeInfo(name=name, capabilities=capabilities or ["chat","code","documents"])
        self._heartbeat_task: Optional[asyncio.Task] = None; self._running = False
    async def register(self) -> None:
        self.info.status = "online"; self.info.last_heartbeat = datetime.now(timezone.utc).isoformat()
        logger.info(f"Node registered: {self.info.name} ({self.info.id})")
    async def heartbeat(self, interval: float = 10.0) -> None:
        self._running = True
        while self._running:
            self.info.last_heartbeat = datetime.now(timezone.utc).isoformat(); self.info.status = "online"
            await asyncio.sleep(interval)
    def get_status(self) -> dict: return self.info.model_dump()
    def update_capabilities(self, capabilities: list[str]) -> None: self.info.capabilities = capabilities
    async def shutdown(self) -> None:
        self._running = False; self.info.status = "offline"
        if self._heartbeat_task: self._heartbeat_task.cancel()
        logger.info(f"Node {self.info.name} shutdown")
    def to_json(self) -> str: return self.info.model_dump_json(indent=2)
