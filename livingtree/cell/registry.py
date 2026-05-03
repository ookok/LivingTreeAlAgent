"""CellRegistry — Register, discover, and query AI cells by capability."""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Optional
from loguru import logger
from pydantic import BaseModel, Field

class CellMetadata(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    name: str; model_name: str = "gpt2"
    capabilities: list[str] = Field(default_factory=list)
    size_mb: float = 0.0; parent_cell_id: Optional[str] = None
    generation: int = 1; status: str = "active"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class CellRegistry:
    def __init__(self): self._cells: dict[str, CellMetadata] = {}
    def register(self, metadata: CellMetadata) -> str:
        self._cells[metadata.id] = metadata; logger.info(f"Cell registered: {metadata.name} ({metadata.id})"); return metadata.id
    def discover(self) -> list[CellMetadata]: return list(self._cells.values())
    def query(self, capability: str) -> list[CellMetadata]:
        return [c for c in self._cells.values() if capability in c.capabilities]
    def get(self, cell_id: str) -> Optional[CellMetadata]: return self._cells.get(cell_id)
    def remove(self, cell_id: str) -> bool:
        if cell_id in self._cells: del self._cells[cell_id]; return True
        return False
    def list_cells(self) -> list: return list(self._cells.values())
