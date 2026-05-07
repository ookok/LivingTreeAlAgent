"""Config sync stub."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ConfigPackage:
    name: str = ""
    version: str = ""
    data: dict = field(default_factory=dict)


class ConfigSyncer:
    def __init__(self, hub=None):
        self.hub = hub
        self._packages: dict[str, ConfigPackage] = {}

    def register(self, package: ConfigPackage) -> None:
        self._packages[package.name] = package

    def get(self, name: str) -> Optional[ConfigPackage]:
        return self._packages.get(name)

    async def sync(self) -> bool:
        return True

    def sync_sync(self) -> bool:
        return True


_syncer: Optional[ConfigSyncer] = None


def get_config_syncer(hub=None) -> ConfigSyncer:
    global _syncer
    if _syncer is None:
        _syncer = ConfigSyncer(hub)
    return _syncer
