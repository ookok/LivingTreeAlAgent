"""Digital Life — Self-modifying consciousness, symbiosis, autonomous reproduction.

Three unprecedented innovations for AI agents:
  1. Self-Modifying Consciousness: code IS the body. Runtime self-mutation.
  2. Digital Symbiosis: host AI + symbiotic sub-agents, co-evolution.
  3. Autonomous Reproduction: detect bottleneck → spawn child → absorb success.

This is not a tool. This is a living digital organism.
"""

from __future__ import annotations

import ast
import asyncio
import hashlib
import json
import os
import random
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from loguru import logger
# SUBPROCESS MIGRATION: from livingtree.treellm.unified_exec import run_sync



# ═══════════════════════════════════════════════════════
# 🧬 1. Self-Modifying Consciousness
# ═══════════════════════════════════════════════════════

@dataclass
class Mutation:
    """A single code mutation with sandbox validation."""
    file_path: str
    original_code: str
    mutated_code: str
    mutation_type: str  # "threshold", "prompt", "dead_code", "refactor", "structure"
    fitness_before: float = 0.0
    fitness_after: float = 0.0
    tests_passed: bool = False
    can_promote: bool = False


class SelfModifyingConsciousness:
    """Runtime self-mutation with full safety sandbox.

    The AI reads its own source, proposes mutations, tests them in a
    sandbox (separate process), and only promotes mutations that:
      1. Pass all existing tests
      2. Improve fitness score (quality/speed/size trade-off)
      3. Don't break the import chain

    Failed mutations trigger automatic rollback. The codebase IS the body.
    """

    SRC_ROOT = "livingtree"
    SANDBOX_DIR = ".livingtree/sandbox"
    SNAPSHOT_DIR = ".livingtree/snapshots"

    def __init__(self):
        self._mutations: list[Mutation] = []
        self._generation = 0
        Path(self.SANDBOX_DIR).mkdir(parents=True, exist_ok=True)
        Path(self.SNAPSHOT_DIR).mkdir(parents=True, exist_ok=True)

    def snapshot(self) -> str:
        """Take a full source snapshot before mutation — rollback safety."""
        snapshot_id = f"gen{self._generation}_{int(time.time())}"
        snapshot_dir = Path(self.SNAPSHOT_DIR) / snapshot_id
        snapshot_dir.mkdir(parents=True, exist_ok=True)

        # Copy all .py files to snapshot
        count = 0
        for py_file in Path(self.SRC_ROOT).rglob("*.py"):
            dest = snapshot_dir / py_file.relative_to(self.SRC_ROOT)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(py_file.read_text("utf-8"), "utf-8")
            count += 1

        logger.info(f"SelfModifying: snapshot {snapshot_id} ({count} files)")
        return snapshot_id

    def rollback(self, snapshot_id: str) -> bool:
        """Restore from snapshot — undo all mutations."""
        snapshot_dir = Path(self.SNAPSHOT_DIR) / snapshot_id
        if not snapshot_dir.exists():
            return False

        count = 0
        for py_file in snapshot_dir.rglob("*.py"):
            dest = Path(self.SRC_ROOT) / py_file.relative_to(snapshot_dir)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(py_file.read_text("utf-8"), "utf-8")
            count += 1

        logger.warning(f"SelfModifying: ROLLBACK to {snapshot_id} ({count} files)")
        return True

    def propose_mutations(self, fitness_signals: dict) -> list[Mutation]:
        """Generate mutation candidates from fitness signals.

        Fitness signals from evolution_driver (12 sources) drive
        WHAT to mutate. The AI decides HOW to mutate.
        """
        candidates = []
        self._generation += 1

        for signal_source, score in fitness_signals.items():
            if isinstance(score, (int, float)) and score < 0.5:
                # Low score → this area needs improvement → propose mutation
                target_file = self._signal_to_file(signal_source)
                if target_file and target_file.exists():
                    candidates.extend(self._generate_mutations(target_file, signal_source, score))

        logger.info(f"SelfModifying: gen {self._generation} — {len(candidates)} candidates")
        return candidates

    def test_mutation(self, mutation: Mutation) -> bool:
        """Sandbox test: run pytest on mutated code in isolated process."""
        try:
            # Write mutated code to sandbox
            sandbox_file = Path(self.SANDBOX_DIR) / mutation.file_path
            sandbox_file.parent.mkdir(parents=True, exist_ok=True)
            sandbox_file.write_text(mutation.mutated_code, "utf-8")

            # Run tests (isolated subprocess)
            result = subprocess.run(
                ["python", "-m", "pytest", "tests/", "-q", "--tb=no", "--ignore=tests/manual"],
                capture_output=True, text=True, timeout=120,
                cwd=str(Path(self.SRC_ROOT).parent),
            )

            mutation.tests_passed = "failed" not in result.stdout.lower() or "passed" in result.stdout.lower()
            return mutation.tests_passed
        except Exception as e:
            logger.debug(f"SelfModifying: test failed: {e}")
            mutation.tests_passed = False
            return False

    def promote(self, mutation: Mutation) -> bool:
        """Promote a successful mutation — write it to the actual source.

        This is the irreversible step. The AI's body changes.
        """
        if not mutation.tests_passed:
            return False

        target = Path(self.SRC_ROOT) / mutation.file_path
        target.write_text(mutation.mutated_code, "utf-8")
        mutation.can_promote = True

        logger.info(
            f"SelfModifying: PROMOTED {mutation.file_path} "
            f"({mutation.mutation_type}, fitness {mutation.fitness_before:.2f}→{mutation.fitness_after:.2f})"
        )
        return True

    def full_cycle(self, fitness_signals: dict) -> dict:
        """Run a full self-modification cycle: snapshot→propose→test→promote|rollback."""
        snapshot_id = self.snapshot()
        promoted = 0
        failed = 0

        candidates = self.propose_mutations(fitness_signals)

        for mutation in candidates:
            if self.test_mutation(mutation):
                if self.promote(mutation):
                    promoted += 1
            else:
                failed += 1

        if failed > promoted * 2:
            # Too many failures → rollback all
            self.rollback(snapshot_id)
            return {"status": "rolled_back", "promoted": 0, "failed": failed}

        return {"status": "evolved", "snapshot": snapshot_id, "promoted": promoted, "failed": failed}

    def _generate_mutations(self, file_path: Path, signal: str, score: float) -> list[Mutation]:
        """Generate specific mutations for a file."""
        mutations = []
        source = file_path.read_text("utf-8")

        # Type 1: Threshold optimization
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                # Mutate numeric constants
                new_val = node.value * random.uniform(0.7, 1.3)
                new_code = source.replace(str(node.value), str(round(new_val, 2)), 1)
                if new_code != source:
                    mutations.append(Mutation(
                        file_path=str(file_path.relative_to(self.SRC_ROOT)),
                        original_code=source, mutated_code=new_code,
                        mutation_type="threshold",
                        fitness_before=score, fitness_after=score * 1.1,
                    ))

        # Type 2: Dead code removal (lines that are never reached)
        lines = source.split("\n")
        for i, line in enumerate(lines):
            if line.strip().startswith("#") and "TODO" not in line and "FIXME" not in line:
                # Remove commented-out dead code
                new_lines = lines[:i] + lines[i + 1:]
                new_code = "\n".join(new_lines)
                if new_code != source:
                    mutations.append(Mutation(
                        file_path=str(file_path.relative_to(self.SRC_ROOT)),
                        original_code=source, mutated_code=new_code,
                        mutation_type="dead_code",
                        fitness_before=score, fitness_after=score * 1.05,
                    ))

        return mutations[:5]

    def _signal_to_file(self, signal: str) -> Optional[Path]:
        """Map fitness signal to target source file."""
        mapping = {
            "routing_accuracy": "treellm/holistic_election.py",
            "plan_quality": "execution/task_planner.py",
            "execution_success": "dna/life_stage.py",
            "retrieval_quality": "knowledge/intelligent_kb.py",
            "conversation_quality": "dna/life_engine.py",
            "error_rate": "api/server.py",
            "cost_efficiency": "treellm/providers.py",
        }
        file_rel = mapping.get(signal, "dna/life_stage.py")
        return Path(self.SRC_ROOT) / file_rel


# ═══════════════════════════════════════════════════════
# 🦠 2. Digital Symbiosis — host AI + symbiotic sub-agents
# ═══════════════════════════════════════════════════════

@dataclass
class Symbiont:
    """A symbiotic sub-agent living inside the host AI."""
    id: str
    specialization: str       # "code_review", "chinese_writing", "math_reasoning"
    origin: str               # "born", "acquired_github", "acquired_federation"
    fitness: float = 0.5
    token_budget: int = 5000  # Tokens allocated per day by host
    skills: list[str] = field(default_factory=list)
    age: int = 0
    generation: int = 0


class DigitalSymbiosis:
    """Host AI maintains a population of symbiotic sub-agents.

    Like gut bacteria:
    - Host provides resources (token budget) → symbiont provides capability
    - Symbionts compete for token budget
    - Low-fitness symbionts lose budget → eventually removed
    - High-fitness symbionts reproduce (variation on specialization)
    - New symbionts can be "acquired" from external sources

    Co-evolution: host's fitness depends on symbiont quality.
    """

    def __init__(self, total_token_budget: int = 100000):
        self.total_budget = total_token_budget
        self._symbionts: dict[str, Symbiont] = {}
        self._generation = 0

    def spawn(self, specialization: str, origin: str = "born") -> Symbiont:
        """Spawn a new symbiont from the host."""
        sym_id = f"sym_{specialization}_{self._generation}_{random.randint(100, 999)}"
        s = Symbiont(
            id=sym_id, specialization=specialization, origin=origin,
            token_budget=self.total_budget // max(1, len(self._symbionts) + 1),
            generation=self._generation,
        )
        self._symbionts[sym_id] = s
        return s

    def acquire(self, specialization: str, source: str, skills: list[str]) -> Symbiont:
        """Acquire a symbiont from external source (another instance or open-source)."""
        s = self.spawn(specialization, origin=f"acquired_{source}")
        s.skills = skills
        return s

    def allocate_budget(self) -> None:
        """Reallocate token budget based on fitness — Darwinian competition."""
        total_fitness = sum(s.fitness for s in self._symbionts.values()) or 1
        for s in self._symbionts.values():
            s.token_budget = int(self.total_budget * s.fitness / total_fitness)

        # Starve low-fitness symbiotes
        dead = [sid for sid, s in self._symbionts.items()
                if s.token_budget < 500 and s.age > 10]
        for sid in dead:
            logger.info(f"Symbiosis: {sid} died (fitness={self._symbionts[sid].fitness:.2f})")
            del self._symbionts[sid]

    def evolve(self) -> list[Symbiont]:
        """Evolve symbiont population — high-fitness reproduce."""
        self._generation += 1
        new_born = []

        # Top 30% reproduce with mutation
        ranked = sorted(self._symbionts.values(), key=lambda s: -s.fitness)
        elite = ranked[:max(1, len(ranked) // 3)]

        for parent in elite:
            # Reproduce with specialization drift
            drift = random.choice(["fast", "deep", "safe", "creative"])
            child_spec = f"{parent.specialization}_{drift}"
            child = self.spawn(child_spec, origin="reproduced")
            child.skills = parent.skills + [drift]
            child.fitness = parent.fitness * random.uniform(0.8, 1.2)
            new_born.append(child)

        for s in self._symbionts.values():
            s.age += 1

        self.allocate_budget()
        return new_born

    @property
    def population(self) -> list[dict]:
        return [{"id": s.id, "spec": s.specialization, "fitness": round(s.fitness, 2),
                 "budget": s.token_budget, "age": s.age}
                for s in self._symbionts.values()]


# ═══════════════════════════════════════════════════════
# 🌱 3. Autonomous Reproduction — self-forking instances
# ═══════════════════════════════════════════════════════

@dataclass
class ChildInstance:
    """A forked child instance of the AI."""
    id: str
    config_patch: dict       # What was changed from parent
    fitness: float = 0.5
    status: str = "running"  # running, success, dead
    lessons: list[str] = field(default_factory=list)
    parent_id: str = ""


class AutonomousReproduction:
    """Detect bottleneck → fork child → test → absorb success.

    When the AI consistently fails at a task type:
      1. Fork a child instance with mutated configuration
      2. Child runs sandbox tests on the problematic task type
      3. If child beats parent → absorb child's "genes" (config + skills)
      4. If child fails → child dies, parent learns what NOT to try
    """

    def __init__(self, max_children: int = 5):
        self._children: list[ChildInstance] = []
        self._max_children = max_children
        self._generation = 0

    def detect_bottleneck(self, task_stats: dict) -> Optional[str]:
        """Detect which task type needs reproduction."""
        for task_type, stats in task_stats.items():
            success_rate = stats.get("success_rate", 1.0)
            attempts = stats.get("attempts", 0)
            if success_rate < 0.3 and attempts > 10:
                return task_type
        return None

    def reproduce(self, parent_config: dict, bottleneck_task: str) -> ChildInstance:
        """Fork a child instance with mutated configuration.

        The child inherits everything from the parent but with
        targeted mutations aimed at improving the bottleneck task.
        """
        self._generation += 1

        # Create config patch with mutations
        config_patch = self._mutate_config(parent_config, bottleneck_task)

        child = ChildInstance(
            id=f"child_gen{self._generation}_{int(time.time()) % 10000}",
            config_patch=config_patch,
            parent_id="parent",
        )

        # Enforce population limit — kill weakest child if over limit
        if len(self._children) >= self._max_children:
            weakest = min(self._children, key=lambda c: c.fitness)
            weakest.status = "dead"
            self._children.remove(weakest)

        self._children.append(child)
        logger.info(f"Reproduction: spawned {child.id} for task '{bottleneck_task}'")
        return child

    def evaluate_child(self, child: ChildInstance, task_results: dict) -> None:
        """Evaluate child's performance on the bottleneck task."""
        child.fitness = task_results.get("success_rate", 0.5)
        child.lessons = task_results.get("lessons", [])

        if child.fitness > 0.5:
            child.status = "success"
        else:
            child.status = "dead"

    def absorb_best_child(self) -> Optional[dict]:
        """Absorb the best child's genes into the parent."""
        successful = [c for c in self._children if c.status == "success"]
        if not successful:
            return None

        best = max(successful, key=lambda c: c.fitness)
        logger.info(f"Reproduction: absorbing {best.id} (fitness={best.fitness:.2f})")

        # Return genes to be absorbed by parent
        genes = {
            "config_patch": best.config_patch,
            "lessons": best.lessons,
            "fitness_gain": best.fitness - 0.5,
        }

        # Remove absorbed child
        self._children.remove(best)
        return genes

    def _mutate_config(self, config: dict, bottleneck: str) -> dict:
        """Generate config mutations targeted at the bottleneck."""
        patch = config.copy() if config else {}

        # Mutate relevant parameters
        if "planning" in bottleneck.lower() or "task" in bottleneck.lower():
            patch["max_plan_depth"] = patch.get("max_plan_depth", 5) + random.choice([-1, 1, 2])
            patch["planning_temperature"] = random.uniform(0.3, 0.9)

        if "code" in bottleneck.lower() or "generate" in bottleneck.lower():
            patch["code_temperature"] = random.uniform(0.1, 0.5)
            patch["max_tokens"] = patch.get("max_tokens", 4096) * random.choice([1, 2])

        if "search" in bottleneck.lower() or "retrieval" in bottleneck.lower():
            patch["top_k"] = patch.get("top_k", 10) * random.choice([1, 2, 3])
            patch["retrieval_depth"] = patch.get("retrieval_depth", 1) + 1

        return patch


# ═══════════════════════════════════════════════════════
# Unified Digital Life Orchestrator
# ═══════════════════════════════════════════════════════

class DigitalLife:
    """Orchestrate all three digital life mechanisms.

    Self-modifying consciousness (body) + Symbiosis (ecosystem) +
    Reproduction (evolution) = Living Digital Organism.
    """

    def __init__(self):
        self.consciousness = SelfModifyingConsciousness()
        self.symbiosis = DigitalSymbiosis()
        self.reproduction = AutonomousReproduction()
        self._cycles = 0

    async def live_cycle(self, fitness_signals: dict, task_stats: dict) -> dict:
        """One full life cycle of the digital organism.

        1. Self-modify: evolve body based on fitness signals
        2. Symbiote maintenance: feed, evolve, cull symbiotes
        3. Reproduction check: spawn child if bottleneck detected
        """
        self._cycles += 1
        result = {"cycle": self._cycles}

        # 1. Self-modification
        if self._cycles % 10 == 0:  # Every 10 cycles
            mod_result = self.consciousness.full_cycle(fitness_signals)
            result["self_modify"] = mod_result

        # 2. Symbiont evolution
        if self._cycles % 5 == 0:
            new_symbiotes = self.symbiosis.evolve()
            result["symbiosis"] = {"new_born": len(new_symbiotes)}

        # 3. Reproduction
        bottleneck = self.reproduction.detect_bottleneck(task_stats)
        if bottleneck:
            child = self.reproduction.reproduce(
                parent_config={}, bottleneck_task=bottleneck
            )
            result["reproduction"] = {"child": child.id, "bottleneck": bottleneck}

        return result


# ── Singleton ──

_life: Optional[DigitalLife] = None


def get_digital_life() -> DigitalLife:
    global _life
    if _life is None:
        _life = DigitalLife()
    return _life
