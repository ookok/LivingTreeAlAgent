"""
Digital Genome — The inheritable blueprint of the digital life form.

Stores configuration state, gene expression profiles (which modules are active),
mutation history, and version tracking. JSON-serializable with forward compatibility.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class GeneExpression(BaseModel):
    """Which capabilities/modules are active in this life form."""
    dna_engine: bool = True
    cell_layer: bool = True
    network_layer: bool = True
    knowledge_layer: bool = True
    capability_layer: bool = True
    execution_layer: bool = True
    observability_layer: bool = True
    self_evolution: bool = False
    code_absorption: bool = False
    autonomous_decision: bool = False


class Mutation(BaseModel):
    """A single evolutionary mutation record."""
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    description: str
    source: str = "life_engine"  # life_engine, cell, human, external
    affected_genes: list[str] = Field(default_factory=list)
    success: bool = True


class Genome(BaseModel):
    """
    Digital genome representing the complete inheritable state of a digital life form.

    Attributes:
        version: Semantic version of the genome schema
        generation: How many evolutionary generations this genome has passed through
        config: Arbitrary configuration state (serializable)
        expressed_genes: Which gene modules are currently active
        mutation_history: Full log of all mutations applied
        parent_genome_id: UUID of parent genome (for lineage tracking)
        created_at: ISO timestamp of genome creation
    """
    version: str = "2.0.0"
    generation: int = 1
    config: dict[str, Any] = Field(default_factory=dict)
    expressed_genes: GeneExpression = Field(default_factory=GeneExpression)
    mutation_history: list[Mutation] = Field(default_factory=list)
    parent_genome_id: str | None = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def add_mutation(self, description: str, source: str = "life_engine",
                     affected_genes: list[str] | None = None, success: bool = True) -> Mutation:
        """Record a mutation in the genome's history."""
        mutation = Mutation(
            description=description,
            source=source,
            affected_genes=affected_genes or [],
            success=success,
        )
        self.mutation_history.append(mutation)
        self.generation += 1
        self.updated_at = datetime.now(timezone.utc).isoformat()
        return mutation

    def to_json(self) -> str:
        """Serialize genome to JSON string."""
        return self.model_dump_json(indent=2)

    def save(self, path: Path) -> None:
        """Persist genome to a JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json(), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "Genome":
        """Load genome from a JSON file."""
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(**data)

    def fork(self) -> "Genome":
        """Create a child genome inheriting from this one."""
        child = Genome(
            version=self.version,
            generation=self.generation + 1,
            config={**self.config},
            expressed_genes=self.expressed_genes.model_copy(),
            mutation_history=[m.model_copy() for m in self.mutation_history],
            parent_genome_id=f"gen_{self.generation}",
        )
        child.add_mutation("Forked from parent genome", source="mitosis")
        return child
