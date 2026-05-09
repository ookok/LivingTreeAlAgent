"""LivingTree One-Click Launcher — initialize the complete digital lifeform.

Usage:
    from livingtree.core.launch import startup
    
    life = await startup.full(identity="tree_001")
    
    # Interact
    result = await life.ask("帮我完成环评报告")
    
    # Monitor
    health = life.health()
    
    # Shutdown
    await life.shutdown()

Startup sequence (dependency-ordered):
  Phase 1: Config & Secrets
  Phase 2: Core Infrastructure (event bus, plasticity, cache)
  Phase 3: Model Providers (SenseTime + free pool + router)
  Phase 4: Knowledge Systems (KB, hypergraph, lazy index, graph tools)
  Phase 5: Reasoning & Planning (GTSM, pipelines, CoFEE)
  Phase 6: DNA & Consciousness (phenomenal, Gödelian, emergence)
  Phase 7: Economy & Optimization (orchestrator, GRPO, TDM, thermo)
  Phase 8: Research & Inquiry (team, agent, counterparty)
  Phase 9: Autonomy (health, action principle, autonomic loop)
  Phase 10: Optional (weather, MTP drafter, parallel drafter, resource tree)
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

from loguru import logger


@dataclass
class LivingTreeStartupConfig:
    """One-click configuration for the entire digital lifeform."""
    identity: str = "tree_001"
    # API keys
    sensetime_api_key: str = "sk-9kybnl63EsTepGUEwOK9H5FwIKlUkGkC"
    deepseek_api_key: str = ""
    # Features
    enable_autopilot: bool = True       # SystemHealth background daemons
    enable_autonomic: bool = True       # Self-correction loop
    enable_weather: bool = False        # Open-Meteo (needs network)
    weather_cities: list[str] = field(default_factory=list)
    enable_resource_tree: bool = True   # Mirage-style unified VFS
    # Tuning
    latent_dim: int = 6
    autonomic_interval_sec: float = 120.0
    homeostatic_interval_sec: float = 300.0


@dataclass
class LivingTreeInstance:
    """The complete initialized digital lifeform."""
    identity: str
    started_at: float
    modules: dict[str, Any]
    config: LivingTreeStartupConfig
    _daemons_started: bool = False
    _running: bool = True

    # ═══ Convenience accessors ═══

    @property
    def consciousness(self):
        return self.modules.get("consciousness")

    @property
    def kb(self):
        return self.modules.get("knowledge_base")

    @property
    def pool(self):
        return self.modules.get("free_pool")

    @property
    def router(self):
        return self.modules.get("bandit_router")

    @property
    def economic(self):
        return self.modules.get("economic")

    @property
    def health_monitor(self):
        return self.modules.get("health")

    # ═══ Operations ═══

    async def ask(self, task: str, domain: str = "general") -> dict[str, Any]:
        """Process a task through the full life cycle."""
        pipeline = self.modules.get("pipeline_orchestrator")
        if not pipeline:
            return {"error": "Pipeline orchestrator not available"}

        ctx = {
            "domain": domain,
            "consciousness": self.consciousness,
            "knowledge": self.kb,
        }
        result = await pipeline.run(task=task, context=ctx)
        return {
            "mode": result.mode,
            "steps": len(result.steps),
            "success": result.success,
            "confidence": result.confidence,
            "latency_ms": result.latency_ms,
        }

    def health(self) -> dict[str, Any]:
        """Get current system health."""
        hm = self.health_monitor
        if not hm:
            return {"status": "unavailable"}
        report = hm.check(self.modules)
        return {
            "status": report.overall_status.value,
            "score": report.overall_score,
            "degraded": report.degraded_modules,
            "action_items": report.action_items,
            "daemons": report.daemon_status,
        }

    def stats(self) -> dict[str, Any]:
        """Get comprehensive system statistics."""
        s = {
            "identity": self.identity,
            "uptime_sec": time.time() - self.started_at,
            "daemons": self._daemons_started,
        }
        for name, mod in self.modules.items():
            if hasattr(mod, 'stats'):
                try:
                    s[name] = mod.stats()
                except Exception:
                    pass
        return s

    async def shutdown(self):
        """Graceful shutdown."""
        self._running = False
        autonomic = self.modules.get("autonomic_loop")
        if autonomic:
            await autonomic.stop()
        health = self.modules.get("health")
        if health and hasattr(health, 'stop_daemons'):
            await health.stop_daemons()
        weather = self.modules.get("weather_client")
        if weather and hasattr(weather, 'close'):
            await weather.close()
        logger.info(f"LivingTree '{self.identity}' shut down")


# ═══ Startup Sequence ═══


async def startup(config: LivingTreeStartupConfig | None = None) -> LivingTreeInstance:
    """One-click full startup of the LivingTree digital lifeform.

    Args:
        config: Optional startup configuration.

    Returns:
        LivingTreeInstance with all modules initialized and wired.
    """
    cfg = config or LivingTreeStartupConfig()
    t0 = time.time()
    modules: dict[str, Any] = {}
    logger.info(f"LivingTree '{cfg.identity}' starting up...")

    # ═══ Phase 1: Config ═══
    _init_config(cfg, modules)

    # ═══ Phase 2: Core Infrastructure ═══
    _init_core(cfg, modules)

    # ═══ Phase 3: Model Providers ═══
    await _init_providers(cfg, modules)

    # ═══ Phase 4: Knowledge Systems ═══
    _init_knowledge(cfg, modules)

    # ═══ Phase 5: Reasoning & Planning ═══
    _init_reasoning(cfg, modules)

    # ═══ Phase 6: DNA & Consciousness ═══
    _init_consciousness(cfg, modules)

    # ═══ Phase 7: Economy & Optimization ═══
    _init_economy(cfg, modules)

    # ═══ Phase 8: Research & Inquiry ═══
    _init_research(cfg, modules)

    # ═══ Phase 9: Autonomy ═══
    await _init_autonomy(cfg, modules)

    # ═══ Phase 10: 小树觉醒 ═══
    await _awaken_xiaoshu(cfg, modules)

    # ═══ Phase 11: 完整生命体器官 ═══
    _init_organism(modules)

    # ═══ Phase 12: Optional ═══
    await _init_optional(cfg, modules)

    elapsed = time.time() - t0
    instance = LivingTreeInstance(
        identity=cfg.identity,
        started_at=time.time(),
        modules=modules,
        config=cfg,
    )
    logger.info(
        f"LivingTree '{cfg.identity}' ready ({len(modules)} modules, {elapsed:.1f}s)\n"
        f"  Consciousness: {instance.consciousness is not None}\n"
        f"  Knowledge:     {instance.kb is not None}\n"
        f"  Models:        {instance.pool is not None}\n"
        f"  Autopilot:     {cfg.enable_autopilot}\n"
        f"  Autonomic:     {cfg.enable_autonomic}"
    )
    return instance


# ═══ Phase Implementations ═══


def _init_config(cfg: LivingTreeStartupConfig, mods: dict) -> None:
    """Phase 1: Load configuration."""
    try:
        from ..config.settings import get_config
        mods["config"] = get_config()
        if cfg.sensetime_api_key:
            mods["config"].model.sensetime_api_key = cfg.sensetime_api_key
        if cfg.deepseek_api_key:
            mods["config"].model.deepseek_api_key = cfg.deepseek_api_key
        logger.debug("Phase 1: config loaded")
    except Exception as e:
        logger.warning(f"Phase 1 skipped: {e}")


def _init_core(cfg: LivingTreeStartupConfig, mods: dict) -> None:
    """Phase 2: Core infrastructure."""
    try:
        from ..core.resource_tree import ResourceTree, create_living_tree_fs
        from ..core.synaptic_plasticity import get_plasticity

        mods["synaptic_plasticity"] = get_plasticity()

        if cfg.enable_resource_tree:
            mods["resource_tree"] = ResourceTree()

        logger.debug(f"Phase 2: core infrastructure ready")
    except Exception as e:
        logger.warning(f"Phase 2 partial: {e}")


async def _init_providers(cfg: LivingTreeStartupConfig, mods: dict) -> None:
    """Phase 3: LLM Providers."""
    try:
        from ..treellm.providers import create_sensetime_provider
        from ..treellm.free_pool_manager import get_free_pool
        from ..treellm.bandit_router import get_bandit_router
        from ..treellm.holistic_election import get_election

        cm = mods.get("config")
        api_key = cm.model.sensetime_api_key if cm else cfg.sensetime_api_key

        if api_key:
            provider = create_sensetime_provider(api_key=api_key)
            mods["sensetime_provider"] = provider
            logger.debug("Phase 3: SenseTime provider created")

        mods["free_pool"] = get_free_pool()
        mods["bandit_router"] = get_bandit_router()
        mods["election"] = get_election()

        # Warm-start router from election stats
        try:
            mods["bandit_router"].warm_start(mods["election"])
        except Exception:
            pass

        logger.debug(f"Phase 3: {len(mods['free_pool']._models)} models in pool")
    except Exception as e:
        logger.warning(f"Phase 3 partial: {e}")


def _init_knowledge(cfg: LivingTreeStartupConfig, mods: dict) -> None:
    """Phase 4: Knowledge systems."""
    try:
        from ..knowledge.hypergraph_store import HypergraphStore
        from ..knowledge.lazy_index import get_lazy_index
        from ..knowledge.graph_introspector import get_introspector
        from ..knowledge.precedence_model import initialize_for_domain

        mods["hypergraph_store"] = HypergraphStore()
        mods["lazy_index"] = get_lazy_index()
        mods["graph_introspector"] = get_introspector()
        mods["precedence_model"] = initialize_for_domain("general")

        logger.debug("Phase 4: knowledge systems ready")
    except Exception as e:
        logger.warning(f"Phase 4 partial: {e}")


def _init_reasoning(cfg: LivingTreeStartupConfig, mods: dict) -> None:
    """Phase 5: Reasoning & Planning."""
    try:
        from ..knowledge.gravity_model import get_gravity_model
        from ..knowledge.order_aware_reranker import get_order_aware_reranker
        from ..execution.gtsm_planner import get_gtsm_planner
        from ..execution.unified_pipeline import get_pipeline_orchestrator
        from ..execution.cofee_engine import get_cofee_engine

        mods["gravity_model"] = get_gravity_model(mods.get("hypergraph_store"))
        mods["order_reranker"] = get_order_aware_reranker()
        mods["gtsm_planner"] = get_gtsm_planner()
        mods["pipeline_orchestrator"] = get_pipeline_orchestrator()
        mods["cofee_engine"] = get_cofee_engine()

        logger.debug("Phase 5: reasoning & planning ready")
    except Exception as e:
        logger.warning(f"Phase 5 partial: {e}")


def _init_consciousness(cfg: LivingTreeStartupConfig, mods: dict) -> None:
    """Phase 6: DNA & Consciousness."""
    try:
        from ..dna.phenomenal_consciousness import get_consciousness
        from ..dna.godelian_self import get_godelian_self
        from ..dna.emergence_detector import get_emergence_detector
        from ..dna.predictability_engine import get_predictability

        mods["consciousness"] = get_consciousness(identity_id=cfg.identity)
        mods["godelian_self"] = get_godelian_self(mods["consciousness"])
        mods["emergence_detector"] = get_emergence_detector()
        mods["predictability"] = get_predictability()

        # Initial self-awareness experience
        mods["consciousness"].experience(
            event_type="insight",
            content=f"I am {cfg.identity}. I have become operational.",
            causal_source="self",
            intensity=0.9,
        )
        logger.debug("Phase 6: consciousness layers online")
    except Exception as e:
        logger.warning(f"Phase 6 partial: {e}")


def _init_economy(cfg: LivingTreeStartupConfig, mods: dict) -> None:
    """Phase 7: Economy & Optimization."""
    try:
        from ..economy.economic_engine import get_economic_orchestrator
        from ..economy.thermo_budget import get_thermo_budget
        from ..economy.tdm_reward import get_tdm_optimizer
        from ..economy.spatial_reward import get_sgrpo
        from ..economy.latent_grpo import get_latent_grpo

        mods["economic"] = get_economic_orchestrator()
        mods["thermo_budget"] = get_thermo_budget()
        mods["tdm_optimizer"] = get_tdm_optimizer()
        mods["sgrpo"] = get_sgrpo()
        mods["latent_grpo"] = get_latent_grpo(latent_dim=cfg.latent_dim)

        logger.debug("Phase 7: economy ready")
    except Exception as e:
        logger.warning(f"Phase 7 partial: {e}")


def _init_research(cfg: LivingTreeStartupConfig, mods: dict) -> None:
    """Phase 8: Research & Inquiry."""
    try:
        from ..dna.research_team import get_research_team
        from ..dna.inquiry_engine import get_inquiry_engine

        mods["research_team"] = get_research_team(mods.get("consciousness"))
        mods["inquiry_engine"] = get_inquiry_engine()

        logger.debug("Phase 8: research team assembled")
    except Exception as e:
        logger.warning(f"Phase 8 partial: {e}")


async def _init_autonomy(cfg: LivingTreeStartupConfig, mods: dict) -> None:
    """Phase 9: Autonomy — health monitor + action principle + autonomic loop."""
    try:
        from ..core.system_health import get_system_health
        from ..core.action_principle import get_action_principle
        from ..core.autonomic_loop import AutonomicLoop

        mods["health"] = get_system_health()
        mods["action_principle"] = get_action_principle()

        # Feed initial module states
        try:
            from ..core.action_principle import feed_all_modules
            feed_all_modules(mods["action_principle"])
        except Exception:
            pass

        if cfg.enable_autopilot:
            await mods["health"].start_daemons(mods)
            instance_daemons = True
            logger.debug("Phase 9: autopilot daemons started")
        else:
            instance_daemons = False

        if cfg.enable_autonomic:
            mods["autonomic_loop"] = AutonomicLoop(mods)
            await mods["autonomic_loop"].start(
                interval_sec=cfg.autonomic_interval_sec)
            logger.debug("Phase 9: autonomic loop engaged")
    except Exception as e:
        logger.warning(f"Phase 9 partial: {e}")


async def _init_optional(cfg: LivingTreeStartupConfig, mods: dict) -> None:
    """Phase 11: Optional modules."""
    if cfg.enable_weather and cfg.weather_cities:
        try:
            from ..knowledge.om_weather import get_weather_client
            mods["weather_client"] = get_weather_client()
            for city in cfg.weather_cities[:3]:
                try:
                    await mods["weather_client"].get_for_city(city, days=3)
                except Exception:
                    pass
            logger.debug(f"Phase 10: weather for {len(cfg.weather_cities)} cities")
        except Exception as e:
            logger.warning(f"Phase 10 weather skipped: {e}")

    if cfg.enable_resource_tree:
        try:
            from ..core.resource_tree import create_living_tree_fs
            mods["resource_tree"] = create_living_tree_fs(
                kb=mods.get("knowledge_base"),
                om_weather=mods.get("weather_client"),
                pool=mods.get("free_pool"),
                hg=mods.get("hypergraph_store"),
                consciousness=mods.get("consciousness"),
            )
        except Exception:
            pass


# ═══ Exports ═══

__all__ = [
    "startup", "LivingTreeInstance", "LivingTreeStartupConfig",
]
