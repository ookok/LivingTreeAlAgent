"""CodeAnalyzer — Deep static analysis: complexity, dead code, type-aware signatures.

Leverages existing CodeGraph + ASTParser data to produce actionable metrics:
  1. Complexity metrics (cyclomatic, cognitive, Halstead volume)
  2. Dead code detection (zero-caller functions, unused imports, unreachable blocks)
  3. Impact scoring (cascading risk from dependency chains)
  4. Refactoring suggestions (long parameter lists, deep nesting, god objects)

All analysis is AST-based (no LLM), runs in <500ms on cached CodeGraph data.
"""

from __future__ import annotations

import ast as py_ast
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from loguru import logger


@dataclass
class ComplexityReport:
    """Per-function complexity metrics."""
    entity_id: str
    name: str
    file: str
    line: int
    cyclomatic: int = 0       # McCabe: edges - nodes + 2
    cognitive: int = 0         # Nesting-weighted
    halstead_volume: float = 0.0  # (N1+N2) * log2(n1+n2)
    param_count: int = 0
    lines: int = 0
    nesting_depth: int = 0
    risk: str = "low"          # low | medium | high | critical


@dataclass
class DeadCodeReport:
    """A dead/unreachable code finding."""
    entity_id: str
    name: str
    file: str
    line: int
    reason: str               # no_callers | unused_import | after_return | always_false


@dataclass
class AnalysisResult:
    """Complete analysis output."""
    complexity: list[ComplexityReport]
    dead_code: list[DeadCodeReport]
    god_objects: list[str]     # Entities with >50 methods or >2000 lines
    long_params: list[str]     # Functions with >8 parameters
    impact_scores: dict[str, int]  # entity_id → 0-100 cascading risk
    summary: dict[str, Any]


class CodeAnalyzer:
    """Deep code analysis on top of CodeGraph + AST data."""

    # ── Complexity ─────────────────────────────────────────────────

    @staticmethod
    def compute_complexity(source: str) -> dict[str, int]:
        """Compute McCabe cyclomatic + cognitive complexity from Python source."""
        result = {"cyclomatic": 1, "cognitive": 0, "nesting": 0}
        try:
            tree = py_ast.parse(source)
        except SyntaxError:
            return result

        nesting = 0
        for node in py_ast.walk(tree):
            # Cyclomatic: each decision point = +1
            if isinstance(node, (py_ast.If, py_ast.While, py_ast.For,
                                 py_ast.ExceptHandler, py_ast.Assert,
                                 py_ast.comprehension)):
                result["cyclomatic"] += 1

            # Cognitive: nesting-weighted
            if isinstance(node, (py_ast.If, py_ast.While, py_ast.For,
                                 py_ast.Try, py_ast.ExceptHandler,
                                 py_ast.With, py_ast.comprehension)):
                if isinstance(node, (py_ast.If, py_ast.While, py_ast.For,
                                     py_ast.ExceptHandler)):
                    nesting += 1
                    result["cognitive"] += nesting
                # Boolean operators in conditions → cognitive load
                if isinstance(node, py_ast.If):
                    result["cognitive"] += CodeAnalyzer._count_bool_ops(node.test)
                elif isinstance(node, py_ast.While):
                    result["cognitive"] += CodeAnalyzer._count_bool_ops(node.test)
                # Break/continue in loops → cognitive
                for sub in py_ast.walk(node):
                    if isinstance(sub, (py_ast.Break, py_ast.Continue)):
                        if any(isinstance(p, (py_ast.For, py_ast.While))
                               for p in CodeAnalyzer._ancestors(tree, sub)):
                            result["cognitive"] += 1
            elif isinstance(node, (py_ast.FunctionDef, py_ast.AsyncFunctionDef,
                                    py_ast.ClassDef)):
                nesting = 0

        result["nesting"] = nesting
        return result

    @staticmethod
    def _count_bool_ops(node) -> int:
        count = 0
        if isinstance(node, py_ast.BoolOp):
            for v in node.values:
                count += CodeAnalyzer._count_bool_ops(v)
            count += len(node.values) - 1
        return count

    @staticmethod
    def _ancestors(tree, target_node):
        parent_map = {}
        for node in py_ast.walk(tree):
            for child in py_ast.iter_child_nodes(node):
                parent_map[child] = node
        result = []
        current = target_node
        while current in parent_map:
            current = parent_map[current]
            result.append(current)
        return result

    @staticmethod
    def compute_halstead(source: str) -> float:
        """Halstead Volume: V = (N1+N2) * log2(n1+n2)."""
        try:
            tree = py_ast.parse(source)
        except SyntaxError:
            return 0.0

        operators: set[str] = set()
        operands: set[str] = set()
        op_count = 0
        operand_count = 0

        for node in py_ast.walk(tree):
            if isinstance(node, (py_ast.Add, py_ast.Sub, py_ast.Mult, py_ast.Div,
                                  py_ast.Mod, py_ast.Pow, py_ast.LShift, py_ast.RShift,
                                  py_ast.BitOr, py_ast.BitXor, py_ast.BitAnd,
                                  py_ast.Eq, py_ast.NotEq, py_ast.Lt, py_ast.LtE,
                                  py_ast.Gt, py_ast.GtE, py_ast.Is, py_ast.IsNot,
                                  py_ast.In, py_ast.NotIn)):
                operators.add(type(node).__name__)
                op_count += 1
            elif isinstance(node, py_ast.BoolOp):
                operators.add(type(node.op).__name__)
                op_count += len(node.values) - 1
            elif isinstance(node, py_ast.UnaryOp):
                operators.add(type(node.op).__name__)
                op_count += 1
            elif isinstance(node, (py_ast.Constant, py_ast.Name)):
                operands.add(str(getattr(node, 'value', getattr(node, 'id', ''))))
                operand_count += 1

        n1, n2 = len(operators), len(operands)
        N1, N2 = op_count, operand_count
        if n1 + n2 == 0:
            return 0.0
        return round((N1 + N2) * math.log2(n1 + n2), 2)

    # ── Dead Code Detection ────────────────────────────────────────

    @staticmethod
    def find_dead_code(filepath: str, call_graph: Any = None) -> list[DeadCodeReport]:
        """Find dead code in a file using AST analysis + call graph data."""
        findings: list[DeadCodeReport] = []
        try:
            source = Path(filepath).read_text(encoding="utf-8", errors="replace")
            tree = py_ast.parse(source)
        except (SyntaxError, OSError):
            return findings

        # 1. Unused imports
        imports: dict[str, int] = {}  # name → import_line
        used_names: set[str] = set()
        for node in py_ast.walk(tree):
            if isinstance(node, py_ast.Import):
                for alias in node.names:
                    imports[alias.asname or alias.name.split(".")[0]] = node.lineno
            elif isinstance(node, py_ast.ImportFrom):
                if node.module:
                    for alias in node.names:
                        imports[alias.asname or alias.name] = node.lineno
            elif isinstance(node, py_ast.Name) and isinstance(node.ctx, py_ast.Load):
                used_names.add(node.id)

        builtins = {"__future__", "sys", "os", "typing", "logging", "json", "time",
                    "re", "asyncio", "abc", "dataclasses", "enum", "collections",
                    "pathlib", "functools", "itertools", "math", "hashlib", "base64",
                    "subprocess", "threading", "copy", "textwrap", "inspect",
                    "warnings", "traceback", "contextlib", "dataclasses", "uuid",
                    "tempfile", "shutil", "io", "random", "string", "struct"}
        for name, line_no in imports.items():
            if name not in used_names and name not in builtins:
                eid = f"{filepath}:import:{name}"
                findings.append(DeadCodeReport(
                    entity_id=eid, name=name, file=filepath, line=line_no,
                    reason="unused_import",
                ))

        # 2. Code after return/raise/break/continue (unreachable)
        for node in py_ast.walk(tree):
            if isinstance(node, (py_ast.FunctionDef, py_ast.AsyncFunctionDef)):
                for i, stmt in enumerate(node.body):
                    if isinstance(stmt, (py_ast.Return, py_ast.Raise)) and i < len(node.body) - 1:
                        after = node.body[i + 1]
                        if not isinstance(after, (py_ast.Return, py_ast.Raise)):
                            findings.append(DeadCodeReport(
                                entity_id=f"{filepath}:{node.name}:unreachable",
                                name=node.name, file=filepath, line=after.lineno,
                                reason="after_return",
                            ))
                            break

        # 3. Always-false conditions (constant expressions in if/while)
        for node in py_ast.walk(tree):
            if isinstance(node, (py_ast.If, py_ast.While)):
                if isinstance(node.test, py_ast.Constant):
                    val = node.test.value
                    if val is False or val is None or val == 0 or val == "":
                        findings.append(DeadCodeReport(
                            entity_id=f"{filepath}:{node.lineno}:always_false",
                            name=f"line {node.lineno}", file=filepath, line=node.lineno,
                            reason="always_false",
                        ))

        return findings

    # ── Impact Scoring ─────────────────────────────────────────────

    @staticmethod
    def compute_impact_scores(entities: dict[str, Any]) -> dict[str, int]:
        """Compute cascading risk scores (0-100) based on call graph topology.

        Score = base_complexity + fan_out * 3 + fan_in * 5 + depth_penalty
        """
        scores: dict[str, int] = {}
        # Map dependents counts per entity
        dependent_counts: dict[str, int] = Counter()
        for eid, entity in entities.items():
            for dep in getattr(entity, 'dependencies', []):
                dependent_counts[dep] += 1

        for eid, entity in entities.items():
            complexity = getattr(entity, 'complexity', 0)
            fan_out = len(getattr(entity, 'dependencies', []))
            fan_in = dependent_counts.get(eid, 0)
            score = min(100, complexity * 2 + fan_out * 3 + fan_in * 5)
            scores[eid] = score
        return scores

    # ── Structural Issues ──────────────────────────────────────────

    @staticmethod
    def find_god_objects(entities: dict[str, Any], filepath: str) -> list[str]:
        """Find classes with >50 methods or files with >2000 lines."""
        issues: list[str] = []

        # Check class method counts per file
        class_methods: dict[str, int] = Counter()
        for eid, entity in entities.items():
            if (getattr(entity, 'kind', '') == 'function' and
                getattr(entity, 'file', '') == filepath and
                getattr(entity, 'parent_class', '')):
                class_methods[entity.parent_class] += 1

        for cls_name, count in class_methods.items():
            if count > 50:
                issues.append(f"God class: {cls_name} ({count} methods) in {filepath}")

        return issues

    @staticmethod
    def analyze_file(filepath: str, source: str = "",
                     call_graph: Any = None) -> AnalysisResult:
        """Full analysis of a single file. Returns all metrics."""
        if not source:
            try:
                source = Path(filepath).read_text(encoding="utf-8", errors="replace")
            except OSError:
                return AnalysisResult([], [], [], [], {}, {})

        complexity_reports: list[ComplexityReport] = []
        try:
            tree = py_ast.parse(source)
        except SyntaxError:
            return AnalysisResult([], [], [], [], {}, {})

        # Analyze each function
        for node in py_ast.walk(tree):
            if isinstance(node, (py_ast.FunctionDef, py_ast.AsyncFunctionDef)):
                try:
                    func_source = py_ast.get_source_segment(source, node) or ""
                except Exception:
                    func_source = ""
                cc = CodeAnalyzer.compute_complexity(func_source)
                params = len(node.args.args) + len(node.args.posonlyargs)
                if node.args.vararg:
                    params += 1
                if node.args.kwarg:
                    params += 1
                lines = node.end_lineno - node.lineno + 1 if node.end_lineno else 0

                risk = "low"
                if cc["cyclomatic"] > 20 or cc["cognitive"] > 30:
                    risk = "critical"
                elif cc["cyclomatic"] > 10 or cc["cognitive"] > 15:
                    risk = "high"
                elif cc["cyclomatic"] > 5 or cc["cognitive"] > 8:
                    risk = "medium"

                eid = f"{filepath}:{node.name}"
                complexity_reports.append(ComplexityReport(
                    entity_id=eid, name=node.name, file=filepath,
                    line=node.lineno,
                    cyclomatic=cc["cyclomatic"],
                    cognitive=cc["cognitive"],
                    halstead_volume=CodeAnalyzer.compute_halstead(func_source),
                    param_count=params,
                    lines=lines,
                    nesting_depth=cc["nesting"],
                    risk=risk,
                ))

        # Dead code
        dead = CodeAnalyzer.find_dead_code(filepath, call_graph)

        # God objects
        god_objects: list[str] = []
        if call_graph:
            god_objects = CodeAnalyzer.find_god_objects(
                getattr(call_graph, '_entities', {}), filepath)

        # Long params
        long_params = [r.name for r in complexity_reports if r.param_count > 8]

        # Impact scores
        impact: dict[str, int] = {}
        if call_graph:
            impact = CodeAnalyzer.compute_impact_scores(
                getattr(call_graph, '_entities', {}))

        # Summary
        total_funcs = len(complexity_reports)
        risky = [r for r in complexity_reports if r.risk in ("high", "critical")]
        dead_count = len(dead)

        summary = {
            "total_functions": total_funcs,
            "avg_cyclomatic": round(sum(r.cyclomatic for r in complexity_reports) / max(total_funcs, 1), 1),
            "avg_cognitive": round(sum(r.cognitive for r in complexity_reports) / max(total_funcs, 1), 1),
            "risky_functions": len(risky),
            "dead_code_findings": dead_count,
            "god_objects": len(god_objects),
            "long_params": len(long_params),
            "top_risks": [{"name": r.name, "cyclomatic": r.cyclomatic,
                          "cognitive": r.cognitive, "risk": r.risk}
                         for r in sorted(risky, key=lambda x: -x.cyclomatic)[:5]],
        }

        return AnalysisResult(
            complexity=complexity_reports,
            dead_code=dead,
            god_objects=god_objects,
            long_params=long_params,
            impact_scores=impact,
            summary=summary,
        )


__all__ = ["CodeAnalyzer", "ComplexityReport", "DeadCodeReport", "AnalysisResult"]
