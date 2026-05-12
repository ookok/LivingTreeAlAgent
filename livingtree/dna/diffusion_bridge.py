"""Module Diffusion Bridge — Connect isolated infrastructure to core pipeline.

Three diffusion targets:
  1. network/ (44 files, P2P/swarm) → integrate peer discovery into orchestrator
  2. observability/ (20 files, metrics/tracing) → integrate into runtime paths
  3. cell/ (11 files, training) → trigger cell training in main loop
"""

from __future__ import annotations

from typing import Any, Optional

from loguru import logger


class DiffusionBridge:
    """Connect isolated infrastructure modules to the core pipeline."""

    # ── Diffusion 1: Network → Orchestrator ──

    @staticmethod
    def wire_network_to_orchestrator(hub) -> None:
        """Connect P2P network layer to task orchestrator.

        When orchestrator needs more agents, it can discover peers
        from the swarm network instead of being limited to local agents.
        """
        try:
            if not hasattr(hub, 'world') or not hub.world:
                return

            world = hub.world

            # Check if network node exists
            node = getattr(world, 'node', None)
            orchestrator = getattr(world, 'orchestrator', None)

            if node and orchestrator:
                # Wire peer discovery into agent pool
                if hasattr(node, 'discover_peers'):
                    discovered = node.discover_peers()
                    if discovered:
                        for peer in discovered[:5]:
                            orchestrator._agents[peer.id] = {
                                "role": getattr(peer, 'role', 'remote'),
                                "model": getattr(peer, 'model', 'unknown'),
                                "capabilities": getattr(peer, 'capabilities', []),
                            }
                        logger.info(
                            f"DiffusionBridge: wired {len(discovered[:5])} "
                            f"network peers into orchestrator"
                        )

            # Wire reputation system to agent selection
            reputation = getattr(world, 'reputation', None)
            if reputation and orchestrator:
                if hasattr(reputation, 'get_trusted_agents'):
                    trusted = reputation.get_trusted_agents(min_score=0.6)
                    if trusted:
                        for agent_id, score in trusted.items():
                            if agent_id in orchestrator._agents:
                                orchestrator._agents[agent_id]["trust_score"] = score

        except Exception as e:
            logger.debug(f"DiffusionBridge network: {e}")

    # ── Diffusion 2: Observability → Runtime ──

    @staticmethod
    def wire_observability_to_runtime(hub) -> None:
        """Connect observability metrics/tracing to runtime lifecycle.

        Previously: metrics exist but never collected.
        Now: auto-instrument key runtime paths.
        """
        try:
            if not hasattr(hub, 'obs'):
                return

            obs = hub.obs
            world = getattr(hub, 'world', None)
            if not world:
                return

            # Auto-instrument life_engine stages
            if hasattr(obs, 'metrics') and hasattr(world, 'life_engine'):
                engine = world.life_engine
                if hasattr(engine, 'stages'):
                    for stage in engine.stages:
                        obs.metrics.record(
                            name=f"stage.{stage.stage}",
                            value=stage.duration_ms or 0,
                            tags={"status": stage.status or "unknown"},
                        )

            # Auto-instrument TreeLLM elections
            if hasattr(obs, 'tracer') and hasattr(world, 'consciousness'):
                consciousness = world.consciousness
                if hasattr(consciousness, '_llm'):
                    llm = consciousness._llm
                    if hasattr(llm, '_elected') and llm._elected:
                        obs.tracer.log(
                            event="tree_llm_election",
                            data={"elected": str(llm._elected)},
                        )

            logger.debug("DiffusionBridge: observability wired to runtime")
        except Exception as e:
            logger.debug(f"DiffusionBridge observability: {e}")

    # ── Diffusion 3: Cell → Main Loop ──

    @staticmethod
    def wire_cell_training_to_main_loop(hub) -> None:
        """Trigger cell training in the main lifecycle loop.

        Previously: cell infrastructure exists but never trains.
        Now: periodic training based on accumulated experience.
        """
        try:
            if not hasattr(hub, 'world') or not hub.world:
                return

            world = hub.world

            # Check if enough experience accumulated for training
            cell_registry = getattr(world, 'cell_registry', None)
            cell_trainer = getattr(world, 'cell_trainer', None)
            evolution_store = getattr(world, 'evolution_store', None)

            if not cell_registry or not cell_trainer:
                return

            # Count accumulated lessons as training signal
            lesson_count = 0
            if evolution_store and hasattr(evolution_store, 'lessons'):
                lesson_count = len(evolution_store.lessons)

            # Train when enough lessons accumulated (every 10 lessons)
            if lesson_count >= 10 and lesson_count % 10 == 0:
                # Train the most relevant cell
                active_cell = cell_registry.get_active_cell() if hasattr(cell_registry, 'get_active_cell') else None
                if active_cell:
                    cell_trainer.train(
                        cell_name=active_cell,
                        training_data=evolution_store.lessons[-10:],
                        epochs=1,
                    )
                    logger.info(
                        f"DiffusionBridge: trained cell '{active_cell}' "
                        f"on {lesson_count} lessons"
                    )

        except Exception as e:
            logger.debug(f"DiffusionBridge cell: {e}")


# ── Singleton ──

_diffusion: Optional[DiffusionBridge] = None


def get_diffusion_bridge() -> DiffusionBridge:
    global _diffusion
    if _diffusion is None:
        _diffusion = DiffusionBridge()
    return _diffusion
