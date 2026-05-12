"""Evolution Gene — Compact Gene-based experience encoding (arXiv:2604.15097, Wang et al., 2026).

Evolver's key finding across 4,590 controlled trials: compact, control-oriented Gene
representations outperform verbose, documentation-oriented Skill packages for agent evolution.

Gene (Evolver-style):
  {trigger: "code_review", actions: ["read","analyze","check_patterns","suggest","verify"],
   constraints: ["must_compile"], failure_warnings: ["skip_verify_if_small_change"]}
"""

from __future__ import annotations

import re
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger


# ── Constants ──

MAX_ACTIONS = 5
MAX_CONSTRAINTS = 3
MAX_WARNINGS = 3
DEFAULT_MAX_GENES = 500
DEFAULT_STALE_DAYS = 30
DEFAULT_PRUNE_DAYS = 90
MAX_USAGE_LOG = 200
TOP_K_DEFAULT = 3
MAX_COMPACT_LENGTH = 80
VALID_VALIDATION_CMDS = frozenset({"node", "npm", "npx"})


# ── EvolutionGene ──


@dataclass
class EvolutionGene:
    """Compact Gene-based experience encoding from Evolver strategy genes."""

    id: str
    trigger: str
    actions: list[str]
    constraints: list[str]
    failure_warnings: list[str]
    success_count: int = 0
    failure_count: int = 0
    last_used: float = field(default_factory=time.time)
    source_mutation: str = ""
    validation_cmd: Optional[str] = None
    version: int = 1
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def effectiveness(self) -> float:
        total = self.success_count + self.failure_count
        if total == 0:
            return 0.0
        return self.success_count / max(total, 1)

    def is_stale(self, days: int = DEFAULT_STALE_DAYS) -> bool:
        threshold = time.time() - (days * 86400)
        return self.last_used < threshold

    def to_compact(self) -> str:
        """Single-line compact repr for prompt injection (~80 chars).
        Format: GENE:{trigger}|{actions}|{constraints}|{warnings}"""
        actions_str = "→".join(self.actions)
        constraints_str = "✓".join(self.constraints)
        warnings_str = "⚠".join(self.failure_warnings)
        compact = f"GENE:{self.trigger}|{actions_str}|{constraints_str}|{warnings_str}"
        if len(compact) > MAX_COMPACT_LENGTH:
            compact = compact[:MAX_COMPACT_LENGTH - 3] + "..."
        return compact

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "trigger": self.trigger,
            "actions": list(self.actions), "constraints": list(self.constraints),
            "failure_warnings": list(self.failure_warnings),
            "success_count": self.success_count, "failure_count": self.failure_count,
            "last_used": self.last_used, "source_mutation": self.source_mutation,
            "validation_cmd": self.validation_cmd, "version": self.version,
            "created_at": self.created_at, "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvolutionGene:
        return cls(
            id=data.get("id", uuid.uuid4().hex[:12]),
            trigger=data.get("trigger", ""),
            actions=data.get("actions", []),
            constraints=data.get("constraints", []),
            failure_warnings=data.get("failure_warnings", []),
            success_count=data.get("success_count", 0),
            failure_count=data.get("failure_count", 0),
            last_used=data.get("last_used", time.time()),
            source_mutation=data.get("source_mutation", ""),
            validation_cmd=data.get("validation_cmd"),
            version=data.get("version", 1),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
        )


# ── GenePool ──


class GenePool:
    """Population of EvolutionGenes with FIFO eviction (default max 500)."""

    def __init__(self, max_genes: int = DEFAULT_MAX_GENES):
        self._genes: dict[str, EvolutionGene] = {}
        self._max_genes: int = max_genes
        self._gene_usage_log: deque[dict[str, Any]] = deque(maxlen=MAX_USAGE_LOG)
        self._insertion_order: list[str] = []

    def add_gene(
        self, trigger: str, actions: list[str], constraints: list[str],
        failure_warnings: list[str], validation_cmd: Optional[str] = None,
        source_mutation: str = "",
    ) -> EvolutionGene:
        if not trigger or not actions:
            raise ValueError("trigger and actions are required")
        actions = actions[:MAX_ACTIONS]
        constraints = constraints[:MAX_CONSTRAINTS]
        failure_warnings = failure_warnings[:MAX_WARNINGS]
        if validation_cmd is not None and validation_cmd not in VALID_VALIDATION_CMDS:
            logger.warning(
                f"GenePool: validation_cmd '{validation_cmd}' not in allowed set "
                f"{set(VALID_VALIDATION_CMDS)} — ignoring"
            )
            validation_cmd = None
        now = time.time()
        gene = EvolutionGene(
            id=uuid.uuid4().hex[:12], trigger=trigger, actions=actions,
            constraints=constraints, failure_warnings=failure_warnings,
            success_count=0, failure_count=0, last_used=now,
            source_mutation=source_mutation, validation_cmd=validation_cmd,
            version=1, created_at=now, updated_at=now,
        )
        self._genes[gene.id] = gene
        self._insertion_order.append(gene.id)
        if len(self._genes) > self._max_genes:
            self._evict_fifo()
        logger.debug(
            f"GenePool: added gene {gene.id} trigger='{trigger}' "
            f"actions={len(actions)} total_genes={len(self._genes)}"
        )
        return gene

    def find_matching(
        self, trigger_pattern: str, top_k: int = TOP_K_DEFAULT
    ) -> list[EvolutionGene]:
        """Find genes by regex trigger match, sorted by effectiveness descending."""
        matches: list[EvolutionGene] = []
        try:
            compiled = re.compile(trigger_pattern, re.IGNORECASE)
        except re.error:
            logger.warning(f"GenePool: invalid regex pattern '{trigger_pattern}'")
            return []
        for gene in self._genes.values():
            if compiled.search(gene.trigger):
                matches.append(gene)
        matches.sort(key=lambda g: g.effectiveness(), reverse=True)
        return matches[:top_k]

    def record_outcome(self, gene_id: str, success: bool) -> None:
        """Update success/failure counts and append to audit log."""
        gene = self._genes.get(gene_id)
        if gene is None:
            logger.warning(f"GenePool: record_outcome — gene '{gene_id}' not found")
            return
        now = time.time()
        if success:
            gene.success_count += 1
        else:
            gene.failure_count += 1
        gene.last_used = now
        gene.updated_at = now
        self._gene_usage_log.append({
            "gene_id": gene_id, "trigger": gene.trigger, "success": success,
            "effectiveness": gene.effectiveness(), "timestamp": now,
        })
        logger.debug(
            f"GenePool: record_outcome gene={gene_id} success={success} "
            f"effectiveness={gene.effectiveness():.2f}"
        )

    def evolve_gene(
        self, gene_id: str, new_actions: Optional[list[str]] = None,
        new_constraints: Optional[list[str]] = None,
        new_warnings: Optional[list[str]] = None,
    ) -> Optional[EvolutionGene]:
        """Create a new gene version; returns None if gene_id not found."""
        existing = self._genes.get(gene_id)
        if existing is None:
            logger.warning(f"GenePool: evolve_gene — gene '{gene_id}' not found")
            return None
        now = time.time()
        evolved = EvolutionGene(
            id=uuid.uuid4().hex[:12], trigger=existing.trigger,
            actions=(new_actions[:MAX_ACTIONS] if new_actions else list(existing.actions)),
            constraints=(new_constraints[:MAX_CONSTRAINTS] if new_constraints else list(existing.constraints)),
            failure_warnings=(new_warnings[:MAX_WARNINGS] if new_warnings else list(existing.failure_warnings)),
            success_count=0, failure_count=0, last_used=now,
            source_mutation=f"evolved_from:{gene_id}",
            validation_cmd=existing.validation_cmd, version=existing.version + 1,
            created_at=now, updated_at=now,
        )
        self._genes[evolved.id] = evolved
        self._insertion_order.append(evolved.id)
        if len(self._genes) > self._max_genes:
            self._evict_fifo()
        logger.info(f"GenePool: evolved gene {gene_id}→{evolved.id} v{evolved.version}")
        return evolved

    def get_top_genes(self, limit: int = 10) -> list[EvolutionGene]:
        ranked = sorted(self._genes.values(), key=lambda g: g.effectiveness(), reverse=True)
        return ranked[:limit]

    def prune_stale(self, days: int = DEFAULT_PRUNE_DAYS) -> int:
        threshold = time.time() - (days * 86400)
        to_remove = [gid for gid, g in self._genes.items() if g.last_used < threshold]
        for gid in to_remove:
            del self._genes[gid]
            if gid in self._insertion_order:
                self._insertion_order.remove(gid)
        if to_remove:
            logger.info(f"GenePool: pruned {len(to_remove)} stale genes "
                         f"(unused >{days}d), remaining={len(self._genes)}")
        return len(to_remove)

    def stats(self) -> dict[str, Any]:
        if not self._genes:
            return {"total_genes": 0, "avg_effectiveness": 0.0,
                    "most_used_trigger": None, "total_usages": 0}
        genes = list(self._genes.values())
        avg_eff = sum(g.effectiveness() for g in genes) / len(genes)
        total_usages = sum(g.success_count + g.failure_count for g in genes)
        trigger_counts: dict[str, int] = {}
        for g in genes:
            trigger_counts[g.trigger] = trigger_counts.get(g.trigger, 0) + 1
        most_used = max(trigger_counts, key=trigger_counts.get) if trigger_counts else None
        return {
            "total_genes": len(genes), "avg_effectiveness": round(avg_eff, 4),
            "most_used_trigger": most_used, "total_usages": total_usages,
        }

    def to_audit_log(self) -> list[dict[str, Any]]:
        return list(self._gene_usage_log)

    def _evict_fifo(self) -> None:
        while len(self._genes) > self._max_genes and self._insertion_order:
            oldest_id = self._insertion_order.pop(0)
            if oldest_id in self._genes:
                removed = self._genes.pop(oldest_id)
                logger.debug(
                    f"GenePool: FIFO evicted gene {removed.id} "
                    f"trigger='{removed.trigger}'"
                )

    def __len__(self) -> int:
        return len(self._genes)

    def __contains__(self, gene_id: str) -> bool:
        return gene_id in self._genes


# ── GeneCompiler ──


class GeneCompiler:
    """Compiles verbose session experience into compact EvolutionGenes.

    Distills LifeEngine cycles: trigger (intent), actions (plan steps),
    constraints (from failures), warnings (from reflections).
    Only compiles if success_rate > 0.5.
    """

    EFFECTIVENESS_THRESHOLD: float = 0.5

    def compile_from_session(
        self, ctx: dict[str, Any], success_rate: float,
    ) -> Optional[EvolutionGene]:
        """Compile a session into a Gene, or None if success_rate <= 0.5.
        ctx keys: intent, plan_steps, failures, reflections, source_mutation, validation_cmd.
        """
        if success_rate <= self.EFFECTIVENESS_THRESHOLD:
            logger.debug(
                f"GeneCompiler: skip compile — success_rate={success_rate:.2f} "
                f"below threshold={self.EFFECTIVENESS_THRESHOLD}"
            )
            return None
        trigger = self._extract_trigger(ctx)
        if not trigger:
            logger.debug("GeneCompiler: skip compile — no trigger extracted")
            return None
        actions = self._extract_actions(ctx)
        constraints = self._extract_constraints(ctx)
        warnings = self._extract_warnings(ctx)
        validation_cmd = ctx.get("validation_cmd")
        source_mutation = ctx.get("source_mutation", "")
        pool = get_gene_pool()
        gene = pool.add_gene(
            trigger=trigger, actions=actions, constraints=constraints,
            failure_warnings=warnings, validation_cmd=validation_cmd,
            source_mutation=source_mutation,
        )
        logger.info(
            f"GeneCompiler: compiled gene {gene.id} trigger='{trigger}' "
            f"success_rate={success_rate:.2f} actions={len(actions)}"
        )
        return gene

    def _extract_trigger(self, ctx: dict[str, Any]) -> str:
        intent = ctx.get("intent", "")
        if not intent:
            return ""
        trigger = intent.lower().strip()
        trigger = re.sub(r"[，,。\.！!？?\s]+", "_", trigger)
        trigger = re.sub(r"_+", "_", trigger).strip("_")
        trigger = re.sub(r"[^a-z0-9_]", "", trigger)
        if len(trigger) > 40:
            trigger = trigger[:40].rstrip("_")
        return trigger

    def _extract_actions(self, ctx: dict[str, Any]) -> list[str]:
        plan_steps: list[str] = ctx.get("plan_steps", [])
        if not plan_steps:
            return ["execute"]
        actions: list[str] = []
        for step in plan_steps[:MAX_ACTIONS]:
            action = self._action_to_token(str(step))
            if action:
                actions.append(action)
        return actions if actions else ["execute"]

    def _extract_constraints(self, ctx: dict[str, Any]) -> list[str]:
        failures: list[str] = ctx.get("failures", [])
        constraints: list[str] = []
        compile_error_patterns = [
            (r"(?:does not compile|compilation error|syntax error)", "must_compile"),
            (r"(?:type error|TypeError|type mismatch)", "must_typecheck"),
            (r"(?:import error|ImportError|no module)", "all_imports_valid"),
            (r"(?:lint|flake8|ruff|pylint)", "must_pass_lint"),
            (r"(?:test failure|test.*fail|assertion)", "must_pass_tests"),
            (r"(?:timeout|too long|performance)", "must_be_fast"),
            (r"(?:permission|denied|unauthorized)", "check_permissions"),
            (r"(?:null|None|undefined|not found)", "check_null_safety"),
        ]
        for failure_msg in failures:
            for pattern, constraint in compile_error_patterns:
                if re.search(pattern, failure_msg, re.IGNORECASE):
                    if constraint not in constraints:
                        constraints.append(constraint)
                    break
            if len(constraints) >= MAX_CONSTRAINTS:
                break
        return constraints[:MAX_CONSTRAINTS]

    def _extract_warnings(self, ctx: dict[str, Any]) -> list[str]:
        reflections: list[str] = ctx.get("reflections", [])
        if not reflections:
            return []
        warning_keywords = {
            r"(?:skip|省略|跳过|ignore)": "skip_if_small",
            r"(?:review|审查|peer|人工)": "human_review_large",
            r"(?:expensive|贵|expensive|token)": "watch_token_cost",
            r"(?:retry|重试|retry|again)": "retry_on_fail",
            r"(?:cache|缓存|cache)": "check_cache_first",
            r"(?:batch|批量|batch)": "batch_when_possible",
            r"(?:unsafe|危险|unsafe|dangerous)": "sandbox_required",
            r"(?:complex|复杂|large|大)": "split_if_large",
        }
        seen: set[str] = set()
        warnings: list[str] = []
        for reflection in reflections:
            for pattern, warning in warning_keywords.items():
                if warning in seen:
                    continue
                if re.search(pattern, reflection, re.IGNORECASE):
                    warnings.append(warning)
                    seen.add(warning)
                    if len(warnings) >= MAX_WARNINGS:
                        return warnings
            if len(warnings) >= MAX_WARNINGS:
                break
        return warnings[:MAX_WARNINGS]

    @staticmethod
    def _action_to_token(step_description: str) -> str:
        lower = step_description.lower()
        for pattern, token in [
            (r"\b(?:read|阅读|读取)\b", "read"),
            (r"\b(?:analyze|分析)\b", "analyze"),
            (r"\b(?:check|检查|verify|验证)\b", "check"),
            (r"\b(?:suggest|建议|recommend)\b", "suggest"),
            (r"\b(?:implement|实现|write|编写|code)\b", "implement"),
            (r"\b(?:test|测试)\b", "test"),
            (r"\b(?:search|搜索|find|查找)\b", "search"),
            (r"\b(?:fix|修复|debug|纠正)\b", "fix"),
            (r"\b(?:optimize|优化|improve|改善)\b", "optimize"),
            (r"\b(?:refactor|重构)\b", "refactor"),
            (r"\b(?:deploy|部署|发布)\b", "deploy"),
            (r"\b(?:review|审查)\b", "review"),
            (r"\b(?:document|文档|记录)\b", "document"),
            (r"\b(?:explain|解释|说明)\b", "explain"),
            (r"\b(?:summarize|总结|概括)\b", "summarize"),
            (r"\b(?:plan|规划|计划)\b", "plan"),
            (r"\b(?:build|构建|建立)\b", "build"),
            (r"\b(?:validate|验证|核实)\b", "validate"),
            (r"\b(?:execute|执行|run|运行)\b", "execute"),
            (r"\b(?:format|格式化)\b", "format"),
        ]:
            if re.search(pattern, lower):
                return token
        return ""


# ── Singleton ──

_pool: Optional[GenePool] = None


def get_gene_pool(max_genes: int = DEFAULT_MAX_GENES) -> GenePool:
    global _pool
    if _pool is None:
        _pool = GenePool(max_genes=max_genes)
        logger.info(f"GenePool: initialized singleton with max_genes={max_genes}")
    return _pool


def reset_gene_pool() -> None:
    global _pool
    _pool = None


__all__ = [
    "EvolutionGene", "GenePool", "GeneCompiler",
    "get_gene_pool", "reset_gene_pool",
    "MAX_ACTIONS", "MAX_CONSTRAINTS", "MAX_WARNINGS", "DEFAULT_MAX_GENES",
]
