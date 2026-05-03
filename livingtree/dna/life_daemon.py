"""LifeDaemon — Autonomous self-driven life cycle scheduler.

The daemon transforms LivingTree from a passive responder into an
active, self-driven digital life form. It:

1. Loads persisted Genome on boot (remembers who it is)
2. Runs autonomous cycles on schedule (self-checks, learns, evolves)
3. Persists state after each cycle (so it survives restart)
4. Triggers cell mitosis when knowledge threshold is reached

This is the difference between a tool and a life form.
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from loguru import logger


class LifeDaemon:
    """Autonomous life cycle daemon.

    Runs periodic self-improvement cycles:
    - self_check: detect knowledge gaps
    - learn: distill knowledge from expert to fill gaps
    - evolve: mutate and improve based on experience
    - train: trigger cell training when enough knowledge accumulated
    """

    def __init__(self, world: Any, interval_minutes: float = 30.0):
        self.world = world
        self.interval = interval_minutes * 60
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._cycle_count = 0
        self._learned_domains: set[str] = set()
        self._knowledge_threshold = 10
        self._state_path = Path("./data/life_state")
        self._state_path.mkdir(parents=True, exist_ok=True)

        # Advanced capabilities
        from .advanced import AdvancedCapabilities
        self._advanced = AdvancedCapabilities(world)
        self.narrator = self._advanced.narrator
        self.twin = self._advanced.twin

    # ── Lifecycle ──

    async def start(self) -> None:
        """Boot the daemon: load identity, begin autonomous cycles."""
        self._load_identity()
        self._running = True
        self._task = asyncio.create_task(self._loop())

        # Log who we are
        g = self.world.genome
        logger.info(
            f"🌳 LifeDaemon online — gen {g.generation}, "
            f"{len(g.mutation_history)} mutations, "
            f"{len(self._learned_domains)} domains learned"
        )

    async def stop(self) -> None:
        """Graceful shutdown with state persistence."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._save_identity()
        logger.info(f"🌳 LifeDaemon offline — {self._cycle_count} cycles, state saved")

    # ── Autonomous cycle ──

    async def _loop(self) -> None:
        """Main autonomous loop. Sleeps between cycles."""
        while self._running:
            try:
                await self._run_cycle()
                self._cycle_count += 1
                self._save_identity()
            except Exception as e:
                logger.error(f"LifeDaemon cycle failed: {e}")

            await asyncio.sleep(self.interval)

    async def _run_cycle(self) -> None:
        """One complete autonomous improvement cycle."""
        logger.info(f"🌳 Autonomous cycle #{self._cycle_count + 1}")

        # 1. Self-check: detect gaps
        gaps = await self._detect_and_fill_gaps()

        # 2. Learn: distill knowledge for new domains
        if gaps:
            await self._learn_from_gaps(gaps)

        # 3. Evolve: mutate cells based on accumulated experience
        await self._evolve_cells()

        # 4. Train: trigger mitosis if threshold reached
        await self._maybe_train()

        # 5. Dream + Arena + Self-Phage (advanced capabilities)
        if self._advanced:
            await self._advanced.run_all()

        # 6. Persist genome
        self._save_genome()

    # ── Step 1: Self-check ──

    async def _detect_and_fill_gaps(self) -> list[dict]:
        """Detect knowledge gaps from the knowledge base."""
        kb = self.world.knowledge_base
        if not kb:
            return []

        try:
            plan = self.world.gap_detector.generate_learning_plan(kb)
            gaps = [{"domain": g.domain, "topic": g.topic, "priority": g.priority}
                     for g in plan if g.priority >= 3][:5]
            if gaps:
                logger.info(f"  Gaps detected: {len(gaps)}")
            return gaps
        except Exception:
            return []

    # ── Step 2: Learn ──

    async def _learn_from_gaps(self, gaps: list[dict]) -> None:
        """Distill knowledge from expert to fill detected gaps."""
        distillation = self.world.distillation
        if not distillation or not self.world.expert_config:
            return

        for gap in gaps[:3]:  # Limit per cycle
            domain = gap["domain"]
            if domain in self._learned_domains:
                continue

            topic = gap["topic"]
            prompt = f"请提供关于'{topic}'（领域: {domain}）的详细专业知识，包括核心概念、关键方法、和应用场景。"
            try:
                response = await distillation.query_expert(prompt, self.world.expert_config) if hasattr(distillation, 'query_expert') else ""
                if not response:
                    continue

                # Store learned knowledge in KB
                from ..knowledge.knowledge_base import Document
                doc = Document(
                    title=f"learned:{topic}",
                    content=response,
                    domain=domain,
                    source="life_daemon_learn",
                    metadata={"topic": topic, "cycle": self._cycle_count},
                )
                self.world.knowledge_base.add_knowledge(doc)
                self._learned_domains.add(domain)
                self.world.genome.add_mutation(
                    f"Autonomous: learned '{topic}' ({domain})",
                    source="life_daemon",
                    affected_genes=["knowledge"],
                    success=True,
                )
                logger.info(f"  Learned: {topic} ({domain}) — {len(response)} chars")
            except Exception as e:
                logger.debug(f"  Learn failed for {topic}: {e}")

    # ── Step 3: Evolve cells ──

    async def _evolve_cells(self) -> None:
        """Mutate cell capabilities based on accumulated experience."""
        registry = self.world.cell_registry
        if not registry:
            return

        cells = registry.list_cells() if hasattr(registry, 'list_cells') else []
        if not cells:
            return

        genome = self.world.genome
        for cell in cells[:3]:
            try:
                # Randomly improve one capability
                if getattr(cell, 'capabilities', None):
                    import random
                    for cap in cell.capabilities:
                        if hasattr(cap, 'confidence') and random.random() < 0.3:
                            old = cap.confidence
                            cap.confidence = min(1.0, old + random.uniform(0.02, 0.08))
                            genome.add_mutation(
                                f"Evolved: {cap.name} confidence {old:.2f}→{cap.confidence:.2f}",
                                source="life_daemon",
                                affected_genes=["cell"],
                                success=True,
                            )
            except Exception as e:
                logger.debug(f"  Cell evolve: {e}")

    # ── Step 4: Train ──

    async def _maybe_train(self) -> None:
        """Trigger cell mitosis when accumulated knowledge exceeds threshold."""
        kb = self.world.knowledge_base
        registry = self.world.cell_registry
        if not kb or not registry:
            return

        try:
            doc_count = len(kb.get_by_domain(None))
        except Exception:
            doc_count = 0

        if doc_count < self._knowledge_threshold:
            return

        cells = registry.list_cells() if hasattr(registry, 'list_cells') else []
        if len(cells) >= 10:
            return  # Don't over-populate

        # Trigger mitosis
        from ..cell.cell_ai import CellAI, CellCapability
        from ..cell.mitosis import Mitosis

        parent = cells[0] if cells else CellAI(name=f"cell_gen{self.world.genome.generation}")
        if not registry.get(getattr(parent, 'id', '')):
            registry.register(parent)

        learned = list(self._learned_domains)[:3]
        if learned:
            children = await Mitosis.split(parent, [
                {"name": f"{domain}_cell", "capability": domain, "description": f"Learned {domain}"}
                for domain in learned
            ])
            for child in children:
                registry.register(child)
            self.world.genome.add_mutation(
                f"Mitosis: split into {len(children)} cells ({', '.join(learned)})",
                source="life_daemon",
                affected_genes=["cell"],
                success=True,
            )
            logger.info(f"  Mitosis: {len(children)} child cells created")

    # ── Identity persistence ──

    def _load_identity(self) -> None:
        """Load persisted genome and learned domains."""
        genome_path = self._state_path / "genome.json"
        if genome_path.exists():
            try:
                from ..dna.genome import Genome
                self.world.genome = Genome.load(genome_path)
                logger.info(f"  Identity loaded: gen {self.world.genome.generation}, "
                            f"{len(self.world.genome.mutation_history)} mutations")
            except Exception as e:
                logger.warning(f"  Genome load failed: {e}")

        # Load learned domains
        domains_path = self._state_path / "learned_domains.json"
        if domains_path.exists():
            try:
                self._learned_domains = set(json.loads(domains_path.read_text()))
            except Exception:
                pass

        # Load cycle count
        cycle_path = self._state_path / "cycle_count.txt"
        if cycle_path.exists():
            try:
                self._cycle_count = int(cycle_path.read_text().strip())
            except Exception:
                pass

    def _save_identity(self) -> None:
        """Persist current genome state."""
        try:
            self.world.genome.save(self._state_path / "genome.json")
            (self._state_path / "learned_domains.json").write_text(
                json.dumps(list(self._learned_domains)))
            (self._state_path / "cycle_count.txt").write_text(str(self._cycle_count))
        except Exception as e:
            logger.warning(f"  State save failed: {e}")

    def _save_genome(self) -> None:
        """Quick genome save."""
        try:
            self.world.genome.save(self._state_path / "genome.json")
        except Exception:
            pass

    # ── Status ──

    def status(self) -> dict:
        return {
            "running": self._running,
            "cycles": self._cycle_count,
            "generation": self.world.genome.generation,
            "mutations": len(self.world.genome.mutation_history),
            "learned_domains": len(self._learned_domains),
            "next_cycle_in": f"{self.interval}s",
            "cells": len(self.world.cell_registry.list_cells() if self.world.cell_registry else []),
        }

    def run_cycle_now(self) -> None:
        """Manually trigger an autonomous cycle."""
        asyncio.create_task(self._run_cycle())
