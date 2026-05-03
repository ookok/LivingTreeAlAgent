"""Mitosis — Cell division: split a parent cell into specialized child cells."""
from __future__ import annotations
from typing import Any
from loguru import logger
from ..dna.genome import Genome
from .cell_ai import CellAI, CellCapability

class Mitosis:
    """Split a parent cell into specialized child cells."""
    @staticmethod
    async def split(parent: CellAI, specializations: list[dict]) -> list[CellAI]:
        """Create child cells from parent, each with a specialization."""
        children = []
        for spec in specializations:
            child_genome = parent.genome.fork()
            child_genome.add_mutation(f"Mitosis: specialized to {spec.get('name','unknown')}", source="mitosis")
            child = CellAI(
                name=spec.get("name", f"{parent.name}_child"),
                genome=child_genome,
                model_name=parent.model_name,
                capabilities=[CellCapability(name=spec.get("capability","general"), description=spec.get("description",""))],
                checkpoint_dir=parent.checkpoint_dir / child_genome.generation.__str__(),
            )
            children.append(child)
            logger.info(f"Mitosis: {parent.name} → {child.name}")
        return children
