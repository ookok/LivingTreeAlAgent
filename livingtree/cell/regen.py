"""Regen — Detect failed cells and regenerate from checkpoints."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from loguru import logger
from .cell_ai import CellAI

class Regen:
    """Cell regeneration: detect, restore, validate."""
    @staticmethod
    async def detect_failed(cell: CellAI) -> bool:
        return cell.genome.generation <= 0 or not cell.checkpoint_dir.exists()

    @staticmethod
    async def restore(cell: CellAI, checkpoint_path: Path | None = None) -> bool:
        ckpt = checkpoint_path or cell.checkpoint_dir / f"{cell.id}_ckpt"
        logger.info(f"Restoring cell {cell.name} from {ckpt}")
        return cell.load_checkpoint(ckpt)

    @staticmethod
    async def validate(cell: CellAI) -> dict:
        checks = {"genome_valid": cell.genome.version > "", "capabilities": len(cell.capabilities), "checkpoint_exists": cell.checkpoint_dir.exists()}
        logger.info(f"Cell {cell.name} validation: {checks}")
        return checks
