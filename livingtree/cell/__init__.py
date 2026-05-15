"""
Cell Layer — Trainable AI cells that replicate, specialize, devour, and regenerate.

Each cell is a small trainable LLM that can:
- be trained on domain data via LoRA
- split (mitosis) into specialized child cells
- absorb (phage) code from external repos
- regenerate from checkpoints after failure
"""
from .cell_ai import CellAI, CellCapability
from .trainer import (
    CellTrainer, TrainingConfig,
    PersonaRewardModel, PersonaRewardScores,
    PersonaSFTPipeline, PersonaSFTSample,
    get_persona_reward_model, get_persona_sft_pipeline,
    persona_preservation_reward, persona_reference_reward,
    EXTRACTION_PROMPT, RESPONSE_GEN_PROMPT,
)
from .registry import CellRegistry, CellMetadata
from .mitosis import Mitosis, ManifoldExtractor, InvariantManifold, get_manifold_extractor
from .phage import Phage
from .regen import Regen
from .distillation import Distillation, ExpertConfig
from .swift_trainer import SwiftDrillTrainer, DrillConfig, DrillResult
from .dsmtree_distiller import DSMTreeDistiller, DistilledPolicy, TreeRule, get_dsmtree_distiller

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
