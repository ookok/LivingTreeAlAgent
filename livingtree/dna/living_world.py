"""LivingWorld — Single system-wide context for the digital life form.

Replaces the scattered DI pattern with one coherent context object.
LifeEngine receives a LivingWorld and accesses everything through it.

Usage:
    world = LivingWorld(consciousness=DualModelConsciousness(...))
    engine = LifeEngine(world)
"""

from __future__ import annotations

from typing import Any, Optional

from loguru import logger

from .genome import Genome
from .consciousness import Consciousness
from .safety import SafetyGuard


class LivingWorld:
    """Unified context shared across all LifeEngine stages.

    Holds references to every subsystem. Created once by IntegrationHub,
    passed to LifeEngine, accessible everywhere without scattered DI.
    """

    def __init__(
        self,
        consciousness: Consciousness,
        genome: Optional[Genome] = None,
        safety: Optional[SafetyGuard] = None,
    ):
        self.consciousness = consciousness
        self.genome = genome or Genome()
        self.safety = safety or SafetyGuard()

        # Layers — set by IntegrationHub during boot
        self.cell_registry: Any = None
        self.cell_trainer: Any = None
        self.distillation: Any = None
        self.expert_config: Any = None
        self.mitosis: Any = None
        self.phage: Any = None
        self.regen: Any = None
        self.drill: Any = None
        self.node: Any = None
        self.discovery: Any = None
        self.nat_traverser: Any = None
        self.reputation: Any = None
        self.encrypted_channel: Any = None
        self.knowledge_base: Any = None
        self.vector_store: Any = None
        self.knowledge_graph: Any = None
        self.format_discovery: Any = None
        self.gap_detector: Any = None
        self.skill_factory: Any = None
        self.tool_market: Any = None
        self.doc_engine: Any = None
        self.code_engine: Any = None
        self.material_collector: Any = None
        self.task_planner: Any = None
        self.orchestrator: Any = None
        self.self_healer: Any = None
        self.quality_checker: Any = None
        self.metrics: Any = None
        self.tracer: Any = None
        self.code_graph: Any = None
        self.ast_parser: Any = None
        self.hitl: Any = None
        self.checkpoint: Any = None
        self.cost_aware: Any = None
        self.template_learner: Any = None
        self.skill_discoverer: Any = None
        self.role_generator: Any = None
        # New v2.1 subsystems
        self.cache_optimizer: Any = None
        self.side_git: Any = None
        self.session_manager: Any = None
        self.lsp_manager: Any = None
        self.sub_agent_roles: Any = None
        self.rlm_runner: Any = None
        self.skill_discovery: Any = None
        self.struct_memory: Any = None

    def wire(self, **kwargs) -> "LivingWorld":
        """Wire subsystems into the world. Called during Hub boot."""
        for name, component in kwargs.items():
            if hasattr(self, name):
                setattr(self, name, component)
                logger.debug(f"World wired: {name} → {type(component).__name__}")
        return self

    def has(self, name: str) -> bool:
        return getattr(self, name, None) is not None
