"""MetaMemory — Tracks which improvement strategies succeed in which contexts.

DGM-H inspired: the Meta Agent learns not just *what* to improve but *how*
to improve. This module records every evolution attempt (strategy + context + outcome),
computes success rates, and feeds recommendations back into the strategy engine.

Strategy types tracked:
  - mutation: "explore_alternatives" | "optimize" | "diversify" | "simplify"
  - crossover: "fuse_parents" | "selective_merge"
  - observation: "hub_analysis" | "uncovered_functions" | "error_patterns" | "custom"
  - generation: temperature, steps, max_tokens used
  - deployment: quality_threshold, auto_deploy, rollback_rate

Context dimensions:
  - domain: "code" | "eia" | "knowledge" | "network" | "general"
  - target_type: "module" | "function" | "class" | "prompt" | "config"
  - complexity: "low" | "medium" | "high"
  - error_type: "syntax" | "logic" | "performance" | "coverage" | "security"

Usage:
    mem = get_meta_memory()
    mem.record("mutation", "optimize", "code", success=True, tokens=1200)
    recs = mem.recommend("mutation", domain="code", top=3)
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from loguru import logger

MEMORY_DIR = Path(".livingtree/meta")
MEMORY_FILE = MEMORY_DIR / "meta_memory.json"


@dataclass
class StrategyRecord:
    id: str
    strategy_type: str
    strategy_name: str
    domain: str
    context: dict[str, Any] = field(default_factory=dict)
    success: bool = False
    fitness_delta: float = 0.0
    tokens_used: int = 0
    time_spent_ms: int = 0
    target_file: str = ""
    notes: str = ""
    created_at: float = field(default_factory=time.time)


@dataclass
class GatingRecord:
    """Engram paper [3] inspired: track whether gating decisions were correct.

    The "hot-to-cold advantage flip": strategies that were once effective
    can become ineffective over time. Gating calibration measures whether
    the recommendation engine is correctly tracking this decay.
    """
    id: str
    strategy_name: str
    context_snapshot: str
    recommended_as_appropriate: bool
    actual_success: bool
    domain: str = ""
    created_at: float = field(default_factory=time.time)

    @property
    def was_correct(self) -> bool:
        return self.recommended_as_appropriate == self.actual_success

    @property
    def was_false_positive(self) -> bool:
        return self.recommended_as_appropriate and not self.actual_success

    @property
    def was_false_negative(self) -> bool:
        return not self.recommended_as_appropriate and self.actual_success


@dataclass
class ToolEvent:
    """context-mode inspired: per-tool-call event tracking.

    Captures every tool invocation with category, output size, files, errors,
    and decisions. Enables session continuity across context compaction.
    """
    id: str
    tool_name: str
    args_preview: str = ""
    output_size: int = 0
    file_affected: str = ""
    category: str = "general"
    success: bool = True
    error_message: str = ""
    intercepted: bool = False
    tokens_saved: int = 0
    session_id: str = ""
    created_at: float = field(default_factory=time.time)


class MetaMemory:
    """Persistent record of every improvement attempt, enabling data-driven
    strategy selection instead of random choice.
    """

    MAX_RECORDS = 1000
    MAX_GATING_RECORDS = 500
    MIN_SAMPLES_FOR_REC = 3
    DEFAULT_SUCCESS_RATE = 0.5

    def __init__(self):
        self._records: list[StrategyRecord] = []
        self._gating_records: list[GatingRecord] = []
        self._tool_events: list[ToolEvent] = []
        self._load()

    def record(self, strategy_type: str, strategy_name: str, domain: str,
               success: bool = False, tokens_used: int = 0,
               time_spent_ms: int = 0, fitness_delta: float = 0.0,
               target_file: str = "", context: dict[str, Any] | None = None,
               notes: str = "") -> StrategyRecord:
        import uuid
        r = StrategyRecord(
            id=uuid.uuid4().hex[:10],
            strategy_type=strategy_type,
            strategy_name=strategy_name,
            domain=domain,
            context=context or {},
            success=success,
            fitness_delta=fitness_delta,
            tokens_used=tokens_used,
            time_spent_ms=time_spent_ms,
            target_file=target_file,
            notes=notes,
        )
        self._records.append(r)
        if len(self._records) > self.MAX_RECORDS:
            self._records = self._records[-self.MAX_RECORDS:]
        self._save()
        return r

    def recommend(self, strategy_type: str, domain: str = "",
                  top: int = 3) -> list[dict[str, Any]]:
        """Recommend the most successful strategies for a given type/domain."""
        candidates: dict[str, list[float]] = {}
        for r in self._records:
            if r.strategy_type != strategy_type:
                continue
            key = r.strategy_name
            if key not in candidates:
                candidates[key] = []
            candidates[key].append(1.0 if r.success else 0.0)

        scored: list[dict[str, Any]] = []
        for name, results in candidates.items():
            if len(results) < self.MIN_SAMPLES_FOR_REC:
                scored.append({"strategy": name, "success_rate": self.DEFAULT_SUCCESS_RATE,
                               "samples": len(results), "confidence": 0.0})
            else:
                rate = sum(results) / len(results)
                confidence = min(1.0, len(results) / 10.0)
                scored.append({"strategy": name, "success_rate": round(rate, 3),
                               "samples": len(results), "confidence": round(confidence, 3)})

        scored.sort(key=lambda x: (x["success_rate"], x["confidence"]), reverse=True)
        return scored[:top]

    def recommend_mutation_direction(self, domain: str = "") -> str:
        """Pick the best mutation direction based on history, fallback to random."""
        recs = self.recommend("mutation", domain=domain, top=4)
        if recs and recs[0]["success_rate"] > self.DEFAULT_SUCCESS_RATE:
            return recs[0]["strategy"]
        import random
        return random.choice(["explore_alternatives", "optimize", "diversify", "simplify"])

    def best_temperature(self, domain: str = "") -> float:
        """Recommend the best generation temperature for a domain."""
        temps: list[float] = []
        conns: list[str] = []
        for r in self._records:
            if r.strategy_type == "generation" and r.success:
                t = r.context.get("temperature")
                if t:
                    temps.append(t)
                    conns.append(r.strategy_name)
        if len(temps) < self.MIN_SAMPLES_FOR_REC:
            return 0.8
        from statistics import mean
        return round(mean(temps), 2)

    def underperforming_strategies(self, domain: str = "",
                                    threshold: float = 0.3) -> list[dict[str, Any]]:
        """Find strategies with low success rates that should be reconsidered."""
        bad = []
        for rec in self.recommend("mutation", domain=domain, top=20):
            if rec["success_rate"] < threshold and rec["samples"] >= self.MIN_SAMPLES_FOR_REC:
                bad.append(rec)
        return bad

    def cross_domain_strategies(self, target_domain: str,
                                 source_domain: str = "") -> list[dict[str, Any]]:
        """Find strategies successful in source_domain that could transfer to target_domain."""
        if not source_domain:
            all_domains = {r.domain for r in self._records if r.domain != target_domain}
            results = []
            for sd in all_domains:
                recs = self.recommend("mutation", domain=sd, top=3)
                for rec in recs:
                    if rec["success_rate"] > 0.6:
                        rec["source_domain"] = sd
                        rec["target_domain"] = target_domain
                        results.append(rec)
            results.sort(key=lambda x: x["success_rate"], reverse=True)
            return results[:5]
        else:
            recs = self.recommend("mutation", domain=source_domain, top=5)
            for r in recs:
                r["source_domain"] = source_domain
                r["target_domain"] = target_domain
            return [r for r in recs if r["success_rate"] > 0.5]

    def get_stats(self) -> dict[str, Any]:
        total = len(self._records)
        if total == 0:
            return {"total": 0}
        successes = sum(1 for r in self._records if r.success)
        total_tokens = sum(r.tokens_used for r in self._records)
        by_type: dict[str, dict] = {}
        for r in self._records:
            if r.strategy_type not in by_type:
                by_type[r.strategy_type] = {"total": 0, "success": 0, "tokens": 0}
            by_type[r.strategy_type]["total"] += 1
            by_type[r.strategy_type]["tokens"] += r.tokens_used
            if r.success:
                by_type[r.strategy_type]["success"] += 1
        return {
            "total_records": total,
            "success_rate": round(successes / total, 3),
            "total_tokens": total_tokens,
            "by_type": {k: {"total": v["total"], "rate": round(v["success"] / max(v["total"], 1), 3),
                            "tokens": v["tokens"]} for k, v in by_type.items()},
        }

    def get_process_efficiency(self, domain: str = "") -> dict[str, Any]:
        """Compute DGM-H process-level efficiency metrics."""
        relevant = [r for r in self._records if not domain or r.domain == domain]
        if not relevant:
            return {"token_per_successful_deploy": 0, "deploy_rate": 0}
        successful = [r for r in relevant if r.success and r.strategy_type in ("deployment", "mutation", "crossover")]
        total_tokens = sum(r.tokens_used for r in relevant)
        n_success = len(successful)
        return {
            "token_per_successful_deploy": round(total_tokens / max(n_success, 1), 1),
            "deploy_rate": round(n_success / max(len(relevant), 1), 3),
            "avg_tokens_per_attempt": round(total_tokens / max(len(relevant), 1), 1),
            "total_attempts": len(relevant),
            "total_successes": n_success,
        }

    # ── Gating Calibration (Engram paper [3]) ──

    def record_gating(self, strategy_name: str, context_snapshot: str,
                      recommended_as_appropriate: bool, actual_success: bool,
                      domain: str = ""):
        """Record whether a strategy recommendation was appropriate for its context.

        Engram paper [3] key insight: gating credit assignment is the bottleneck,
        not lookup precision. This tracks whether our gate is correctly calibrated.
        """
        import uuid
        r = GatingRecord(
            id=uuid.uuid4().hex[:10],
            strategy_name=strategy_name,
            context_snapshot=context_snapshot[:200],
            recommended_as_appropriate=recommended_as_appropriate,
            actual_success=actual_success,
            domain=domain,
        )
        self._gating_records.append(r)
        if len(self._gating_records) > self.MAX_GATING_RECORDS:
            self._gating_records = self._gating_records[-self.MAX_GATING_RECORDS:]

    @property
    def gating_calibration(self) -> dict[str, Any]:
        """Compute calibration score: how often the gate is correct vs wrong.

        Returns gating precision, recall, and calibration ratio.
        Calibration near 1.0 means the gate is well-calibrated.
        Below 0.7 indicates significant gating mismatch needing correction.
        """
        if not self._gating_records:
            return {"calibrated": True, "score": 1.0, "samples": 0}

        total = len(self._gating_records)
        correct = sum(1 for r in self._gating_records if r.was_correct)
        fp = sum(1 for r in self._gating_records if r.was_false_positive)
        fn = sum(1 for r in self._gating_records if r.was_false_negative)
        tp = sum(1 for r in self._gating_records if r.recommended_as_appropriate and r.actual_success)
        tn = sum(1 for r in self._gating_records if not r.recommended_as_appropriate and not r.actual_success)

        precision = tp / max(tp + fp, 1)
        recall = tp / max(tp + fn, 1)
        calibration = round(correct / total, 3)

        return {
            "calibrated": calibration >= 0.7,
            "score": calibration,
            "samples": total,
            "correct": correct,
            "false_positives": fp,
            "false_negatives": fn,
            "precision": round(precision, 3),
            "recall": round(recall, 3),
        }

    def misgated_strategies(self, min_samples: int = 3) -> list[dict[str, Any]]:
        """Find strategies where gating is frequently wrong (Engram paper [3] flip detection)."""
        per_strategy: dict[str, dict] = {}
        for r in self._gating_records:
            if r.strategy_name not in per_strategy:
                per_strategy[r.strategy_name] = {"total": 0, "wrong": 0, "fp": 0, "fn": 0}
            per_strategy[r.strategy_name]["total"] += 1
            if not r.was_correct:
                per_strategy[r.strategy_name]["wrong"] += 1
            if r.was_false_positive:
                per_strategy[r.strategy_name]["fp"] += 1
            if r.was_false_negative:
                per_strategy[r.strategy_name]["fn"] += 1

        misgated = []
        for name, stats in per_strategy.items():
            if stats["total"] >= min_samples:
                error_rate = stats["wrong"] / stats["total"]
                if error_rate > 0.3:
                    stats["name"] = name
                    stats["error_rate"] = round(error_rate, 3)
                    stats["dominant_error"] = "fp" if stats["fp"] >= stats["fn"] else "fn"
                    misgated.append(stats)

        misgated.sort(key=lambda x: x["error_rate"], reverse=True)
        return misgated

    def strategy_decay_tracker(self, strategy_name: str) -> dict[str, Any]:
        """Track if a strategy's effectiveness is decaying over time (hot-to-cold flip).

        Engram paper [3]: a strategy that was once effective can become
        ineffective. Early successes followed by failures = decay signal.
        """
        records = [r for r in self._records if r.strategy_name == strategy_name]
        if len(records) < 4:
            return {"decaying": False, "trend": "insufficient_data"}

        records.sort(key=lambda r: r.created_at)
        half = len(records) // 2
        early = records[:half]
        late = records[half:]

        early_rate = sum(1 for r in early if r.success) / max(len(early), 1)
        late_rate = sum(1 for r in late if r.success) / max(len(late), 1)
        delta = late_rate - early_rate

        trend = "improving" if delta > 0.1 else "decaying" if delta < -0.2 else "stable"
        return {
            "decaying": delta < -0.2,
            "trend": trend,
            "early_success_rate": round(early_rate, 3),
            "late_success_rate": round(late_rate, 3),
            "delta": round(delta, 3),
            "total_samples": len(records),
        }

    def get_gating_stats(self) -> dict[str, Any]:
        return {
            "calibration": self.gating_calibration,
            "misgated": self.misgated_strategies()[:5],
            "total_gating_records": len(self._gating_records),
        }

    # ── Tool-level event tracking (context-mode) ──

    def record_tool_event(self, tool_name: str, args_preview: str = "",
                          output_size: int = 0, file_affected: str = "",
                          category: str = "general", success: bool = True,
                          error_message: str = "", intercepted: bool = False,
                          tokens_saved: int = 0, session_id: str = ""):
        """context-mode: record every tool invocation for session continuity.

        Categories (following context-mode):
          file: read, edit, write, glob, grep
          git: checkout, commit, merge, push, pull
          task: create, update, complete
          error: tool failures, non-zero exit codes
          env: cwd changes, venv, package installs
          mcp: MCP tool calls
          generic: everything else
        """
        import uuid
        event = ToolEvent(
            id=uuid.uuid4().hex[:10],
            tool_name=tool_name,
            args_preview=args_preview[:200],
            output_size=output_size,
            file_affected=file_affected[:300],
            category=category,
            success=success,
            error_message=error_message[:200],
            intercepted=intercepted,
            tokens_saved=tokens_saved,
            session_id=session_id,
        )
        self._tool_events.append(event)
        if len(self._tool_events) > 500:
            self._tool_events = self._tool_events[-500:]

    def categorize_tool(self, tool_name: str, args: dict[str, Any] | None = None,
                         result: Any = None) -> str:
        """Auto-categorize tool events (context-mode classification)."""
        tool_lower = tool_name.lower()
        args_str = str(args).lower() if args else ""
        result_str = str(result).lower() if result else ""

        git_tools = {"bash", "run_shell_command", "shell"}
        git_ops = {"git", "stash", "push", "pull", "merge", "rebase", "checkout", "commit"}

        if tool_lower in git_tools and any(op in args_str for op in git_ops):
            return "git"
        if tool_lower in {"read", "read_file", "read_many_files", "glob", "grep",
                           "grep_search", "search_file_content"}:
            return "file"
        if tool_lower in {"write", "write_file", "edit", "edit_file"}:
            if result_str and ("error" in result_str or "fail" in result_str):
                return "error"
            return "file"
        if tool_lower in {"task", "todowrite"}:
            return "task"
        if tool_lower in {"mcp"} or tool_lower.startswith("mcp__"):
            return "mcp"
        if "install" in args_str or "venv" in args_str or "conda" in args_str:
            return "env"
        return "generic"

    def get_tool_stats(self, session_id: str = "") -> dict[str, Any]:
        """Get per-category tool event statistics."""
        events = [e for e in self._tool_events
                  if not session_id or e.session_id == session_id]
        if not events:
            return {"total": 0}

        by_category: dict[str, dict] = {}
        for e in events:
            if e.category not in by_category:
                by_category[e.category] = {"count": 0, "errors": 0,
                                            "total_output": 0, "saved": 0}
            by_category[e.category]["count"] += 1
            by_category[e.category]["total_output"] += e.output_size
            by_category[e.category]["saved"] += e.tokens_saved
            if not e.success:
                by_category[e.category]["errors"] += 1

        total_output = sum(e.output_size for e in events)
        total_saved = sum(e.tokens_saved for e in events)
        return {
            "total_events": len(events),
            "total_output_kb": round(total_output / 1024, 1),
            "total_saved_kb": round(total_saved / 1024, 1),
            "error_count": sum(1 for e in events if not e.success),
            "intercepted_count": sum(1 for e in events if e.intercepted),
            "by_category": {k: {
                "count": v["count"], "errors": v["errors"],
                "output_kb": round(v["total_output"] / 1024, 1),
                "saved_kb": round(v["saved"] / 1024, 1),
            } for k, v in by_category.items()},
        }

    def get_recent_tool_events(self, n: int = 10) -> list[dict[str, Any]]:
        """Get the N most recent tool events for session guide generation."""
        return [{
            "tool": e.tool_name, "category": e.category,
            "output_kb": round(e.output_size / 1024, 1),
            "success": e.success, "intercepted": e.intercepted,
            "file": e.file_affected, "error": e.error_message[:80],
        } for e in self._tool_events[-n:]]

    def build_session_guide(self, session_id: str = "") -> str:
        """context-mode: build a compact session guide from tool events.

        Uses ContextCodex for maximal compression of repeated patterns.
        """
        events = [e for e in self._tool_events
                  if not session_id or e.session_id == session_id]
        if not events:
            return ""

        from ..execution.context_codex import get_context_codex, DeltaEncoder
        codex = get_context_codex(seed=False)

        deltas = []
        for e in events:
            if e.category == "file":
                deltas.append(DeltaEncoder.encode_file_edit(
                    e.file_affected, cause=e.error_message[:30] if e.error_message else ""))
            elif e.category == "git":
                deltas.append(DeltaEncoder.encode_git_op(
                    "commit" if "commit" in e.args_preview.lower() else "checkout",
                    e.file_affected[:50]))
            elif e.category == "error":
                deltas.append(DeltaEncoder.encode_error(
                    e.file_affected[:50], fixed=not e.error_message))
            elif e.category == "task":
                deltas.append(f"ΔT:{e.args_preview[:50]}")

        delta_block = codex.compress_delta(deltas) if deltas else ""

        stats = self.get_tool_stats(session_id)
        lines = ["[Session Guide]", f"工具:{stats['total_events']}次 输出:{stats['total_output_kb']}KB"]
        if delta_block:
            lines.append(f"[Δ] {delta_block}")

        compressed, header = codex.compress("\n".join(lines), layer=2, max_header_chars=400)
        if header:
            return f"{header}\n---\n{compressed}"
        return compressed

    def _save(self):
        try:
            MEMORY_DIR.mkdir(parents=True, exist_ok=True)
            data = [{
                "id": r.id, "strategy_type": r.strategy_type,
                "strategy_name": r.strategy_name, "domain": r.domain,
                "context": r.context, "success": r.success,
                "fitness_delta": r.fitness_delta, "tokens_used": r.tokens_used,
                "time_spent_ms": r.time_spent_ms, "target_file": r.target_file,
                "notes": r.notes, "created_at": r.created_at,
            } for r in self._records]
            MEMORY_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))

            gating_file = MEMORY_DIR / "meta_gating.json"
            gating_data = [{
                "id": r.id, "strategy_name": r.strategy_name,
                "context_snapshot": r.context_snapshot,
                "recommended_as_appropriate": r.recommended_as_appropriate,
                "actual_success": r.actual_success, "domain": r.domain,
                "created_at": r.created_at,
            } for r in self._gating_records]
            gating_file.write_text(json.dumps(gating_data, indent=2, ensure_ascii=False))

            tool_file = MEMORY_DIR / "meta_tool_events.json"
            tool_data = [{
                "id": e.id, "tool_name": e.tool_name,
                "args_preview": e.args_preview, "output_size": e.output_size,
                "file_affected": e.file_affected, "category": e.category,
                "success": e.success, "error_message": e.error_message,
                "intercepted": e.intercepted, "tokens_saved": e.tokens_saved,
                "session_id": e.session_id, "created_at": e.created_at,
            } for e in self._tool_events]
            tool_file.write_text(json.dumps(tool_data, indent=2, ensure_ascii=False))
        except Exception as e:
            logger.debug(f"MetaMemory save: {e}")

    def _load(self):
        try:
            if MEMORY_FILE.exists():
                data = json.loads(MEMORY_FILE.read_text())
                self._records = [StrategyRecord(**d) for d in data]
        except Exception as e:
            logger.debug(f"MetaMemory load: {e}")
        try:
            gating_file = MEMORY_DIR / "meta_gating.json"
            if gating_file.exists():
                data = json.loads(gating_file.read_text())
                self._gating_records = [GatingRecord(**d) for d in data]
        except Exception as e:
            logger.debug(f"MetaMemory gating load: {e}")
        try:
            tool_file = MEMORY_DIR / "meta_tool_events.json"
            if tool_file.exists():
                data = json.loads(tool_file.read_text())
                self._tool_events = [ToolEvent(**d) for d in data]
        except Exception as e:
            logger.debug(f"MetaMemory tool events load: {e}")


_meta_memory: MetaMemory | None = None


def get_meta_memory() -> MetaMemory:
    global _meta_memory
    if _meta_memory is None:
        _meta_memory = MetaMemory()
    return _meta_memory
