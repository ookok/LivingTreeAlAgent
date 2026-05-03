"""
Cell Layer — Trainable AI cells that replicate, specialize, devour, and regenerate.

Each cell is a small trainable LLM that can:
- be trained on domain data via LoRA
- split (mitosis) into specialized child cells
- absorb (phage) code from external repos
- regenerate from checkpoints after failure
"""
from .cell_ai import CellAI, CellCapability
from .trainer import CellTrainer, TrainingConfig
from .registry import CellRegistry, CellMetadata
from .mitosis import Mitosis
from .phage import Phage
from .regen import Regen
from .distillation import Distillation, ExpertConfig
from .swift_trainer import SwiftDrillTrainer, DrillConfig, DrillResult

__all__ = [
    "CellAI", "CellCapability",
    "CellTrainer", "TrainingConfig",
    "CellRegistry", "CellMetadata",
    "Mitosis", "Phage", "Regen",
    "Distillation", "ExpertConfig",
    "SwiftDrillTrainer", "DrillConfig", "DrillResult",
]
