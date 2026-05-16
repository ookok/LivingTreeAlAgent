"""
Cell Layer — Trainable AI cells that replicate, specialize, devour, and regenerate.

Each cell is a small trainable LLM that can:
- be trained on domain data via LoRA
- split (mitosis) into specialized child cells
- regenerate from checkpoints after failure
"""
from .trainer import (
    CellTrainer, TrainingConfig,
    PersonaRewardModel, PersonaRewardScores,
    PersonaSFTPipeline, PersonaSFTSample,
    get_persona_reward_model, get_persona_sft_pipeline,
    persona_preservation_reward, persona_reference_reward,
    EXTRACTION_PROMPT, RESPONSE_GEN_PROMPT,
)
from .registry import CellRegistry, CellMetadata
from .regen import Regen
from .distillation import Distillation, ExpertConfig
from .dsmtree_distiller import DSMTreeDistiller, DistilledPolicy, TreeRule, get_dsmtree_distiller

# ── Stubs for deleted modules (cell_ai, mitosis, phage, swift_trainer) ──

class CellAI:
    """Stub: cell_ai.py deleted."""
    pass

class CellCapability:
    """Stub: cell_ai.py deleted."""
    pass

class Mitosis:
    """Stub: module deleted."""
    pass

class Phage:
    """Stub: phage.py deleted."""
    pass

class SwiftDrillTrainer:
    """Stub: swift_trainer.py deleted."""
    pass

class DrillConfig:
    """Stub: swift_trainer.py deleted."""
    pass

class DrillResult:
    """Stub: swift_trainer.py deleted."""
    pass

class ManifoldExtractor:
    """Stub: mitosis module deleted."""
    pass

class InvariantManifold:
    """Stub: mitosis module deleted."""
    pass

def get_manifold_extractor():
    """Stub: mitosis module deleted."""
    return ManifoldExtractor()

__all__ = [
    "CellAI", "CellCapability",
    "CellTrainer", "TrainingConfig",
    "PersonaRewardModel", "PersonaRewardScores",
    "PersonaSFTPipeline", "PersonaSFTSample",
    "get_persona_reward_model", "get_persona_sft_pipeline",
    "persona_preservation_reward", "persona_reference_reward",
    "EXTRACTION_PROMPT", "RESPONSE_GEN_PROMPT",
    "CellRegistry", "CellMetadata",
    "Mitosis", "ManifoldExtractor", "InvariantManifold", "get_manifold_extractor",
    "Phage", "Regen",
    "Distillation", "ExpertConfig",
    "SwiftDrillTrainer", "DrillConfig", "DrillResult",
    "DSMTreeDistiller", "DistilledPolicy", "TreeRule", "get_dsmtree_distiller",
]
