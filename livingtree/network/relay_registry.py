"""Relay registry stub."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RelayServer:
    id: str = ""
    host: str = ""
    port: int = 0
    region: str = ""
    online: bool = False


@dataclass
class RelayList:
    servers: list = field(default_factory=list)


class RelayRegistry:
    def __init__(self):
        self._servers: dict[str, RelayServer] = {}

    def register(self, server: RelayServer) -> None:
        self._servers[server.id] = server

    def discover(self) -> RelayList:
        return RelayList(servers=list(self._servers.values()))


_registry: Optional[RelayRegistry] = None


def get_relay_registry() -> RelayRegistry:
    global _registry
    if _registry is None:
        _registry = RelayRegistry()
    return _registry
