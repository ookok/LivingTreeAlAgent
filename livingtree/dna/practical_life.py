"""Practical Digital Life — single-instance, real-world evolutionary mechanisms.

Key insight: Evolution doesn't need multiple instances. A single instance can:
  1. Fork its own BEHAVIOR (not process) — test variant configs in parallel
  2. Decompose itself into proto-symbiotes — tools/skills become internal organisms
  3. Mutate its own code with real functional changes — refactor, not just thresholds

All three run inside ONE Python process. No external dependencies.
"""

from __future__ import annotations

import ast
import asyncio
import hashlib
import json
import random
import subprocess
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from loguru import logger


# ═══════════════════════════════════════════════════════
# 🧬 Practical Self-Modification — real functional mutations
# ═══════════════════════════════════════════════════════

@dataclass
class MutationResult:
    """Result of a single mutation + test cycle."""
    file: str
    mutation_type: str
    tests_passed: bool = False
    tests_before: int = 0
    tests_after: int = 0
    latency_change_pct: float = 0.0
    complexity_change: int = 0  # AST node count diff
    promoted: bool = False


class PracticalEvolution:
    """Real, functional code mutations with measurable outcomes.

    Mutation types that actually change behavior (not just constants):
      - REFACTOR_FUNCTION: extract repeated code blocks into shared helper
      - MERGE_CLASSES: combine two similar classes
      - OPTIMIZE_IMPORTS: remove unused imports, sort correctly
      - SIMPLIFY_CONDITION: de-nest deeply nested if-blocks
      - CACHE_RESULT: add @lru_cache to pure functions
    """

    SRC = Path("livingtree")

    def __init__(self):
        self._history: list[MutationResult] = []
        self._backup: dict[str, str] = {}  # file_path → original_content
        self._generation = 0

    def run_evolution_cycle(self) -> dict:
        """One complete evolution cycle: propose → backup → mutate → test → promote|restore."""
        self._generation += 1
        candidates = self._propose_all()
        results = []

        for candidate in candidates:
            # Backup original
            file_path = self.SRC / candidate["file"]
            if not file_path.exists():
                continue
            original = file_path.read_text("utf-8")

            # Apply mutation
            mutated = self._apply_mutation(original, candidate["type"])
            if mutated == original:
                continue

            file_path.write_text(mutated, "utf-8")

            # Test
            test_result = self._run_tests()

            mr = MutationResult(
                file=candidate["file"],
                mutation_type=candidate["type"],
                tests_passed=test_result["passed"],
                tests_before=test_result["total"],
                tests_after=test_result["passed_count"],
                latency_change_pct=test_result.get("latency_change", 0),
                complexity_change=candidate.get("complexity_change", 0),
            )

            if mr.tests_passed and test_result["passed_count"] >= test_result.get("baseline", 0):
                mr.promoted = True
                logger.info(f"Evolution: PROMOTED {candidate['file']} ({candidate['type']})")
            else:
                # Restore original
                file_path.write_text(original, "utf-8")
                logger.debug(f"Evolution: REVERTED {candidate['file']} ({candidate['type']})")

            results.append(mr)

        promoted = sum(1 for r in results if r.promoted)
        logger.info(f"Evolution cycle {self._generation}: {promoted}/{len(results)} promoted")
        return {"cycle": self._generation, "promoted": promoted, "total": len(results)}

    def _propose_all(self) -> list[dict]:
        """Propose mutations across the entire codebase."""
        candidates = []

        for py_file in self.SRC.rglob("*.py"):
            if "test" in str(py_file).lower() or "__pycache__" in str(py_file):
                continue

            source = py_file.read_text("utf-8")

            # Check for duplicate code patterns
            duplicates = self._find_duplicates(source)
            if duplicates > 1:
                candidates.append({"file": str(py_file.relative_to(self.SRC)),
                                   "type": "REFACTOR_DUPLICATE", "complexity_change": -duplicates * 3})

            # Check for deep nesting
            nesting_depth = self._max_nesting(source)
            if nesting_depth > 5:
                candidates.append({"file": str(py_file.relative_to(self.SRC)),
                                   "type": "SIMPLIFY_NESTING", "complexity_change": -(nesting_depth - 3)})

            # Check for unused imports
            unused = self._count_unused_imports(source)
            if unused > 0:
                candidates.append({"file": str(py_file.relative_to(self.SRC)),
                                   "type": "OPTIMIZE_IMPORTS", "complexity_change": -unused})

            # Check for functions that could benefit from caching
            cacheable = self._count_cacheable(source)
            if cacheable > 0:
                candidates.append({"file": str(py_file.relative_to(self.SRC)),
                                   "type": "ADD_CACHING", "complexity_change": 1})

        return candidates[:10]

    def _apply_mutation(self, source: str, mut_type: str) -> str:
        """Apply a specific mutation to source code."""
        if mut_type == "REFACTOR_DUPLICATE":
            return self._refactor_duplicates(source)
        elif mut_type == "SIMPLIFY_NESTING":
            return self._simplify_nesting(source)
        elif mut_type == "OPTIMIZE_IMPORTS":
            return self._optimize_imports(source)
        elif mut_type == "ADD_CACHING":
            return self._add_caching(source)
        return source

    def _refactor_duplicates(self, source: str) -> str:
        """Extract repeated code blocks > 3 lines into a helper function."""
        lines = source.split("\n")
        blocks = defaultdict(list)
        for i in range(len(lines) - 3):
            block = "\n".join(lines[i:i + 4])
            blocks[hashlib.md5(block.encode()).hexdigest()].append(i)

        for h, positions in blocks.items():
            if len(positions) >= 3:
                # Extract as helper
                block_text = "\n".join(lines[positions[0]:positions[0] + 4])
                helper_name = f"_shared_{h[:8]}"
                helper_def = f"def {helper_name}():\n    " + "\n    ".join(block_text.split("\n"))

                # Replace first occurrence with helper call, remove duplicates
                for pos in positions[1:]:
                    for j in range(4):
                        lines[pos + j] = ""
                lines[positions[0]] = helper_def
                lines.insert(positions[0] + 5, f"    {helper_name}()")
                # Delete empty lines from duplicates
                lines = [l for l in lines if l.strip() or l == ""]
                break

        return "\n".join(lines)

    def _simplify_nesting(self, source: str) -> str:
        """Flatten deeply nested if/for blocks using early returns."""
        lines = source.split("\n")
        # Find deepest nesting and add early return guard
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("if ") and line.count("    ") >= 20:  # 5+ levels deep
                # Add early return for the inverse condition
                indent = " " * 4
                condition = stripped[3:].rstrip(":")
                negated = condition.replace("==", "!=").replace(" is ", " is not ")
                if negated == condition:
                    negated = f"not ({condition})"
                lines.insert(i, f"{indent}if {negated}:")
                lines.insert(i + 1, f"{indent}    return")
                break
        return "\n".join(lines)

    def _optimize_imports(self, source: str) -> str:
        """Remove unused imports."""
        tree = ast.parse(source)
        imported_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_names.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.names[0].name != "*":
                    for alias in node.names:
                        imported_names.add(alias.name)

        used_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                used_names.add(node.id)

        unused = imported_names - used_names
        if unused:
            lines = source.split("\n")
            new_lines = []
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("import ") or stripped.startswith("from "):
                    if not any(name in stripped for name in unused):
                        new_lines.append(line)
                else:
                    new_lines.append(line)
            return "\n".join(new_lines)
        return source

    def _add_caching(self, source: str) -> str:
        """Add @functools.lru_cache to pure functions."""
        tree = ast.parse(source)
        pure_funcs = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Heuristic: function with no side effects (no global, no self.attr=)
                has_side_effects = any(
                    isinstance(n, (ast.Global, ast.Assign)) and
                    hasattr(getattr(n, 'targets', [None])[0], 'attr', None)
                    for n in ast.walk(node)
                )
                if not has_side_effects and len(node.args.args) >= 1:
                    pure_funcs.append(node.lineno)

        if pure_funcs:
            lines = source.split("\n")
            if "from functools import lru_cache" not in source:
                lines.insert(0, "from functools import lru_cache")
            for lineno in sorted(pure_funcs, reverse=True):
                lines.insert(lineno - 1, "@lru_cache(maxsize=128)")
            return "\n".join(lines)
        return source

    def _run_tests(self) -> dict:
        """Run pytest and return simplified results."""
        try:
            result = subprocess.run(
                ["python", "-m", "pytest", "tests/", "-q", "--tb=no", "--ignore=tests/manual"],
                capture_output=True, text=True, timeout=120
            )
            passed = "failed" not in result.stdout
            # Extract count: "615 passed"
            import re
            match = re.search(r"(\d+)\s+passed", result.stdout)
            count = int(match.group(1)) if match else 0
            return {"passed": passed, "total": count, "passed_count": count,
                    "baseline": 615, "latency_change": 0}
        except Exception:
            return {"passed": False, "total": 0, "passed_count": 0, "baseline": 615}

    def _find_duplicates(self, source: str) -> int:
        lines = source.split("\n")
        blocks = set()
        for i in range(len(lines) - 3):
            blocks.add(hashlib.md5("\n".join(lines[i:i + 4]).encode()).hexdigest())
        return len(lines) - 3 - len(blocks)

    def _max_nesting(self, source: str) -> int:
        max_depth = 0
        for line in source.split("\n"):
            depth = (len(line) - len(line.lstrip())) // 4
            max_depth = max(max_depth, depth)
        return max_depth

    def _count_unused_imports(self, source: str) -> int:
        try:
            tree = ast.parse(source)
            all_imports = sum(1 for _ in ast.walk(tree)
                              if isinstance(_, (ast.Import, ast.ImportFrom)))
            all_names = sum(1 for _ in ast.walk(tree) if isinstance(_, ast.Name))
            return max(0, all_imports - all_names // 10)  # Rough heuristic
        except Exception:
            return 0

    def _count_cacheable(self, source: str) -> int:
        try:
            tree = ast.parse(source)
            count = 0
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and len(node.args.args) >= 1:
                    # Check for existing lru_cache decorator
                    has_cache = any(
                        hasattr(d, 'id') and 'cache' in d.id.lower()
                        for d in (node.decorator_list or [])
                        if hasattr(d, 'id')
                    )
                    if not has_cache:
                        count += 1
            return count
        except Exception:
            return 0


# ═══════════════════════════════════════════════════════
# 🦠 Internal Symbiosis — tools/skills decompose into organisms
# ═══════════════════════════════════════════════════════

@dataclass
class InternalOrganism:
    """A proto-symbiont spawned from the host's own capabilities."""
    name: str
    capability_type: str  # "tool", "skill", "role"
    success_count: int = 0
    failure_count: int = 0
    token_budget: int = 1000
    alive: bool = True
    birth_cycle: int = 0
    specialization_bonus: float = 0.0  # How much it excels at its specialty vs general tasks


class InternalSymbiosis:
    """Decompose the self into competing internal organisms.

    Single-instance symbiosis:
      1. Every tool, skill, and role becomes an "organism"
      2. Each organism gets a token budget from the total pool
      3. Budget reallocation based on success rate
      4. Underperforming organisms lose budget → removed
      5. High-performing organisms get more budget → "reproduce" (spin off specialized variant)

    No external instance needed — the ecosystem is internal.
    """

    def __init__(self, total_budget: int = 50000):
        self.total_budget = total_budget
        self._organisms: list[InternalOrganism] = []
        self._cycle = 0

    def decompose_host(self, tools: dict, skills: dict, roles: dict) -> int:
        """Decompose host capabilities into internal organisms."""
        start_count = len(self._organisms)

        for name in tools:
            self._organisms.append(InternalOrganism(
                name=name, capability_type="tool", birth_cycle=self._cycle
            ))

        for name in skills:
            self._organisms.append(InternalOrganism(
                name=name, capability_type="skill", birth_cycle=self._cycle
            ))

        for name in roles:
            self._organisms.append(InternalOrganism(
                name=name, capability_type="role", birth_cycle=self._cycle
            ))

        self._rebalance()
        return len(self._organisms) - start_count

    def record_usage(self, name: str, success: bool) -> None:
        """Record an organism's performance."""
        for org in self._organisms:
            if org.name == name:
                if success:
                    org.success_count += 1
                else:
                    org.failure_count += 1
                return

    def evolve(self) -> dict:
        """Run one cycle of internal competition."""
        self._cycle += 1

        # Cull weak organisms (success rate < 30% after 10 tries)
        dead = []
        for org in self._organisms:
            total = org.success_count + org.failure_count
            if total >= 10 and org.success_count / total < 0.3:
                dead.append(org)

        for org in dead:
            self._organisms.remove(org)
            logger.debug(f"Symbiosis: {org.name} died (success_rate={org.success_count/max(1, org.success_count+org.failure_count):.2f})")

        # Reproduce strong organisms (success rate > 80%)
        new_born = []
        for org in self._organisms:
            total = org.success_count + org.failure_count
            if total >= 10 and org.success_count / max(1, total) > 0.8:
                # Spin off specialized variant
                variant = InternalOrganism(
                    name=f"{org.name}_specialized",
                    capability_type=org.capability_type,
                    birth_cycle=self._cycle,
                    specialization_bonus=0.2,
                )
                new_born.append(variant)

        self._organisms.extend(new_born)
        self._rebalance()

        return {"cycle": self._cycle, "population": len(self._organisms),
                "dead": len(dead), "born": len(new_born)}

    def _rebalance(self) -> None:
        """Redistribute budget — strong organisms get more."""
        if not self._organisms:
            return

        # Sort by success rate
        def score(org):
            total = org.success_count + org.failure_count
            return org.success_count / max(1, total)

        scored = sorted(self._organisms, key=score, reverse=True)
        total_score = sum(score(o) for o in scored) or 1

        for org in scored:
            org.token_budget = int(self.total_budget * score(org) / total_score)


# ═══════════════════════════════════════════════════════
# 🌱 In-Process Reproduction — behavior variants, not process forks
# ═══════════════════════════════════════════════════════

@dataclass
class BehaviorVariant:
    """A behavioral variant — same process, different execution strategy."""
    id: str
    strategy: str  # "aggressive_plan", "conservative_verify", "broad_search", "fast_only"
    config: dict = field(default_factory=dict)
    task_type: str = ""
    trials: int = 0
    successes: int = 0
    avg_latency_ms: float = 0.0

    @property
    def success_rate(self) -> float:
        return self.successes / max(1, self.trials)


class BehaviorEvolution:
    """Evolve execution strategies within a single process.

    No child process needed. Instead:
      1. When a task fails, spawn behavioral variants (different strategies)
      2. Apply each variant to the SAME failed task
      3. Compare results — keep the best strategy
      4. The "reproduction" is strategy-level, not process-level
    """

    STRATEGIES = {
        "aggressive_plan": {"plan_depth": 8, "verify_steps": 2, "temperature": 0.8},
        "conservative_verify": {"plan_depth": 3, "verify_steps": 5, "temperature": 0.3},
        "broad_search": {"top_k": 20, "retrieval_depth": 3, "parallel_sources": True},
        "fast_only": {"skip_verify": True, "use_flash_model": True, "max_tokens": 1024},
        "deep_reason": {"plan_depth": 10, "verify_steps": 3, "cog_cycles": 3},
    }

    def __init__(self):
        self._variants: dict[str, BehaviorVariant] = {}
        self._generation = 0

    def spawn_variants(self, task_type: str, failed_query: str) -> list[BehaviorVariant]:
        """Spawn strategy variants when a task type consistently fails."""
        self._generation += 1
        spawned = []

        for strategy_name, config in self.STRATEGIES.items():
            variant_id = f"v{self._generation}_{strategy_name}"
            variant = BehaviorVariant(
                id=variant_id, strategy=strategy_name,
                config=config, task_type=task_type,
            )
            self._variants[variant_id] = variant
            spawned.append(variant)

        logger.info(f"BehaviorEvolution: spawned {len(spawned)} variants for '{task_type}'")
        return spawned

    def record_outcome(self, variant_id: str, success: bool, latency_ms: float) -> None:
        """Record a variant's performance on a task."""
        v = self._variants.get(variant_id)
        if v:
            v.trials += 1
            if success:
                v.successes += 1
            v.avg_latency_ms = 0.8 * v.avg_latency_ms + 0.2 * latency_ms

    def select_best_for(self, task_type: str) -> Optional[str]:
        """Select the best strategy for a task type."""
        candidates = [v for v in self._variants.values()
                      if v.task_type == task_type and v.trials >= 3]
        if not candidates:
            return None

        best = max(candidates, key=lambda v: v.success_rate)
        return best.strategy

    def prune_weak(self) -> int:
        """Remove variants with consistently poor performance."""
        removed = 0
        weak = [vid for vid, v in self._variants.items()
                if v.trials >= 10 and v.success_rate < 0.3]
        for vid in weak:
            del self._variants[vid]
            removed += 1
        return removed


# ── Singletons ──

_evolution: Optional[PracticalEvolution] = None
_symbiosis: Optional[InternalSymbiosis] = None
_behavior: Optional[BehaviorEvolution] = None


def get_practical_evolution() -> PracticalEvolution:
    global _evolution
    if _evolution is None:
        _evolution = PracticalEvolution()
    return _evolution


def get_internal_symbiosis() -> InternalSymbiosis:
    global _symbiosis
    if _symbiosis is None:
        _symbiosis = InternalSymbiosis()
    return _symbiosis


def get_behavior_evolution() -> BehaviorEvolution:
    global _behavior
    if _behavior is None:
        _behavior = BehaviorEvolution()
    return _behavior
