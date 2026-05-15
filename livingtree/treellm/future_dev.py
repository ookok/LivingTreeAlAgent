"""FutureDev — Code Migration, Dead Code Impact, Test Amplifier, Living Diagrams, Bug Prediction.

Short-term (ready now):
  1. Code Migration    — "把 requests 换成 aiohttp" → find all call sites + generate migration code
  2. Dead Code Impact  — "删除这个函数会怎样？" → cascading impact + test coverage gaps
  3. Test Amplifier    — given existing tests, auto-generate edge case variants

Medium-term:
  4. Living Diagrams   — CodeGraph → auto-generated & maintained Mermaid architecture diagrams
  5. Bug Hotspot       — git history + complexity → predict where next bug will appear

Usage:
    livingtree dev migrate <old> <new>      # Generate migration plan
    livingtree dev dead-impact <file> <fn>  # Impact of deleting a function
    livingtree dev amplify <test_file>      # Generate test variants
    livingtree dev diagram [--type mermaid] # Auto-generate architecture diagram
    livingtree dev bug-radar                # Predict bug-prone files
"""

from __future__ import annotations

import ast as py_ast
import json
import math
import os
import re
import subprocess
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from loguru import logger


# ═══════════════════════════════════════════════════════════════
# 1. Code Migration — find all call sites + generate migration
# ═══════════════════════════════════════════════════════════════

@dataclass
class MigrationSite:
    """A single call site that needs migration."""
    file: str
    line: int
    code: str
    old_api: str
    new_api: str
    difficulty: str  # trivial | moderate | complex
    suggested_code: str = ""


@dataclass
class MigrationPlan:
    """Complete migration plan."""
    old_pattern: str
    new_pattern: str
    sites: list[MigrationSite]
    total_sites: int
    estimated_work_hours: float
    import_changes: list[str]


class CodeMigrator:
    """Find all call sites of an old API pattern and generate migration code."""

    @staticmethod
    def migrate(old_pattern: str, new_pattern: str,
                root: str = "livingtree") -> MigrationPlan:
        """Scan codebase for old_pattern usage, generate migration plan.

        Examples:
            old_pattern="requests.get" new_pattern="aiohttp.ClientSession().get"
            old_pattern="subprocess.run(" new_pattern="shell.execute("
            old_pattern="asyncio.get_event_loop()" new_pattern="asyncio.get_running_loop()"
        """
        sites = []
        old_func = old_pattern.split(".")[-1].split("(")[0]

        for fpath in Path(root).rglob("*.py"):
            if any(p in str(fpath) for p in ("__pycache__", ".venv", "test_", "conftest")):
                continue
            try:
                source = fpath.read_text(encoding="utf-8", errors="replace")
                lines = source.split("\n")
            except Exception:
                continue

            for i, line in enumerate(lines, 1):
                if old_pattern in line:
                    difficulty = "trivial"
                    if "async" in line or "await" in line:
                        difficulty = "moderate"
                    if "except" in line or "try" in line or "with" in line:
                        difficulty = "complex"

                    suggested = line.replace(old_pattern, new_pattern)

                    sites.append(MigrationSite(
                        file=str(fpath), line=i, code=line.strip()[:120],
                        old_api=old_pattern, new_api=new_pattern,
                        difficulty=difficulty, suggested_code=suggested.strip()[:120],
                    ))

        # Estimate work
        trivial = sum(1 for s in sites if s.difficulty == "trivial")
        moderate = sum(1 for s in sites if s.difficulty == "moderate")
        complex_s = sum(1 for s in sites if s.difficulty == "complex")
        hours = trivial * 0.05 + moderate * 0.3 + complex_s * 1.0

        # Import changes
        import_changes = []
        if "." in old_pattern:
            old_module = old_pattern.split(".")[0]
            new_module = new_pattern.split(".")[0]
            import_changes.append(f"import {old_module} → import {new_module}")

        return MigrationPlan(
            old_pattern=old_pattern, new_pattern=new_pattern,
            sites=sites, total_sites=len(sites),
            estimated_work_hours=round(hours, 1),
            import_changes=import_changes,
        )

    @staticmethod
    def format_plan(plan: MigrationPlan) -> str:
        lines = [
            f"## Migration Plan: `{plan.old_pattern}` → `{plan.new_pattern}`",
            "",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Call sites | {plan.total_sites} |",
            f"| Trivial | {sum(1 for s in plan.sites if s.difficulty == 'trivial')} |",
            f"| Moderate | {sum(1 for s in plan.sites if s.difficulty == 'moderate')} |",
            f"| Complex | {sum(1 for s in plan.sites if s.difficulty == 'complex')} |",
            f"| Est. time | {plan.estimated_work_hours}h |",
            "",
            "## Call Sites",
            "",
        ]
        for s in plan.sites[:15]:
            lines.append(f"  `{Path(s.file).name}:{s.line}` [{s.difficulty}]")
            lines.append(f"    {s.code}")
            if s.suggested_code != s.code:
                lines.append(f"    → `{s.suggested_code}`")
            lines.append("")
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# 2. Dead Code Impact — what happens if we delete this function?
# ═══════════════════════════════════════════════════════════════

@dataclass
class DeadCodeImpact:
    """Impact assessment of removing a code entity."""
    entity: str
    file: str
    direct_callers: list[str]
    downstream_impact: list[str]  # Cascading effect
    tests_affected: list[str]
    can_safely_delete: bool
    risk: str


class DeadCodeAnalyzer:
    """Analyze the impact of deleting a function or file."""

    @staticmethod
    def analyze(target_file: str, target_func: str = "",
                code_graph: Any = None) -> DeadCodeImpact | None:
        """What breaks if we delete target_func in target_file?"""
        if not code_graph:
            try:
                from ..capability.code_graph import CodeGraph
                code_graph = CodeGraph()
                cache = Path(".livingtree/code_graph.pickle")
                if cache.exists():
                    code_graph.load(str(cache))
            except Exception:
                return None
        if not code_graph:
            return None

        key = f"{target_file}:{target_func}" if target_func else target_file
        blast = code_graph.blast_radius([target_file], max_depth=3)

        callers = []
        try:
            callers = [c.name for c in code_graph.get_callers(key)[:10]]
        except Exception:
            callers = []

        downstream = [b.file for b in blast if b.risk in ("critical", "high")][:10]
        tests = [b.file for b in blast if "test" in b.file.lower()][:5]
        can_delete = len(callers) == 0 and len(downstream) == 0

        risk = "safe" if can_delete else \
               "low" if len(callers) <= 2 else \
               "high" if len(callers) > 5 else "medium"

        return DeadCodeImpact(
            entity=target_func or target_file,
            file=target_file,
            direct_callers=callers,
            downstream_impact=downstream,
            tests_affected=tests,
            can_safely_delete=can_delete,
            risk=risk,
        )

    @staticmethod
    def format_report(impact: DeadCodeImpact) -> str:
        icon = "✅" if impact.can_safely_delete else "⚠️" if impact.risk == "low" else "🔴"
        lines = [
            f"## Dead Code Impact: `{Path(impact.file).name}` → `{impact.entity}`",
            "",
            f"{icon} Risk: **{impact.risk.upper()}** | Safe to delete: {'Yes' if impact.can_safely_delete else 'No'}",
            "",
        ]
        if impact.direct_callers:
            lines.append(f"Direct callers ({len(impact.direct_callers)}):")
            for c in impact.direct_callers[:5]:
                lines.append(f"  - {c}")
        if impact.downstream_impact:
            lines.append(f"Downstream files affected ({len(impact.downstream_impact)}):")
            for f in impact.downstream_impact[:5]:
                lines.append(f"  - {Path(f).name}")
        if impact.tests_affected:
            lines.append(f"Tests affected ({len(impact.tests_affected)}):")
            for t in impact.tests_affected[:3]:
                lines.append(f"  - {Path(t).name}")
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# 3. Test Amplifier — generate edge case variants
# ═══════════════════════════════════════════════════════════════

@dataclass
class TestVariant:
    """An auto-generated test variant."""
    name: str
    code: str
    category: str  # boundary | null | error | concurrency | type_error
    description: str


class TestAmplifier:
    """Generate test variants from existing test code using AST analysis."""

    @staticmethod
    def amplify(test_file: str) -> list[TestVariant]:
        """Analyze an existing test and generate edge case variants."""
        variants = []
        try:
            source = Path(test_file).read_text(encoding="utf-8", errors="replace")
            tree = py_ast.parse(source)
        except Exception:
            return variants

        for node in py_ast.walk(tree):
            if isinstance(node, py_ast.FunctionDef) and node.name.startswith("test_"):
                var = TestAmplifier._amplify_test(node, source)
                variants.extend(var)

        return variants

    @staticmethod
    def _amplify_test(node: py_ast.FunctionDef, source: str) -> list[TestVariant]:
        variants = []

        # Find assert statements
        asserts = [n for n in py_ast.walk(node) if isinstance(n, py_ast.Assert)]
        values = []
        for a in asserts:
            try:
                # Extract the value being asserted
                if isinstance(a.test, py_ast.Compare):
                    left = py_ast.unparse(a.test.left)
                    values.append(left)
            except Exception:
                pass

        func_name = node.name

        for val in values[:2]:
            # Null/None variant
            variants.append(TestVariant(
                name=f"{func_name}_none",
                code=f"def {func_name}_none():\n    result = {val}\n    assert result is not None, 'should handle None input'",
                category="null",
                description="Test behavior with None/null input",
            ))
            # Error variant
            variants.append(TestVariant(
                name=f"{func_name}_error",
                code=f"def {func_name}_error():\n    try:\n        {val}()\n    except Exception as e:\n        assert str(e), 'should raise meaningful error'",
                category="error",
                description="Test error handling path",
            ))
            # Boundary variant
            variants.append(TestVariant(
                name=f"{func_name}_boundary",
                code=f"def {func_name}_boundary():\n    result = {val}\n    assert result, 'should handle boundary case (empty/zero)'",
                category="boundary",
                description="Test boundary condition (empty/zero input)",
            ))

        return variants

    @staticmethod
    def format_variants(variants: list[TestVariant]) -> str:
        if not variants:
            return "No test variants generated."
        lines = [f"## Test Amplifier — {len(variants)} variants", ""]
        for v in variants:
            lines.append(f"### `{v.name}()` [{v.category}]")
            lines.append(f"  {v.description}")
            lines.append(f"```python\n{v.code}\n```")
            lines.append("")
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# 4. Living Architecture Diagrams — auto-generate Mermaid
# ═══════════════════════════════════════════════════════════════

class LivingDiagram:
    """Auto-generate and maintain Mermaid architecture diagrams from CodeGraph."""

    @staticmethod
    def generate(code_graph: Any = None, diagram_type: str = "dependency") -> str:
        """Generate a Mermaid diagram from CodeGraph hub analysis."""
        if not code_graph:
            try:
                from ..capability.code_graph import CodeGraph
                code_graph = CodeGraph()
                cache = Path(".livingtree/code_graph.pickle")
                if cache.exists():
                    code_graph.load(str(cache))
            except Exception:
                return "CodeGraph unavailable"

        if not code_graph:
            return "CodeGraph unavailable"

        hubs = code_graph.find_hubs(20)
        if not hubs:
            return "No hubs detected"

        lines = ["```mermaid", "graph TD"]

        # Top 15 hubs with their connections
        hub_names = {h.name: f"N{i}" for i, h in enumerate(hubs[:15])}
        for i, h in enumerate(hubs[:15]):
            label = Path(h.file).stem[:15]
            lines.append(f"    N{i}[{label}]")

        for i, h in enumerate(hubs[:15]):
            for dep_id in h.dependencies[:3]:
                dep_entity = code_graph._entities.get(dep_id)
                if dep_entity:
                    for j, h2 in enumerate(hubs[:15]):
                        if dep_entity.name == h2.name and i != j:
                            lines.append(f"    N{i} --> N{j}")
                            break

        lines.append("```")
        return "\n".join(lines)

    @staticmethod
    def save_diagram(mermaid_code: str) -> Path:
        path = Path("docs/architecture.mmd")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(mermaid_code, encoding="utf-8")
        return path


# ═══════════════════════════════════════════════════════════════
# 5. Bug Hotspot Prediction — where will the next bug appear?
# ═══════════════════════════════════════════════════════════════

@dataclass
class BugHotspot:
    """A file predicted to be bug-prone."""
    file: str
    bug_score: float  # 0-100
    reasons: list[str]
    risk_factors: dict[str, float]


class BugRadar:
    """Predict bug-prone files using git history + complexity + churn."""

    @staticmethod
    def scan(root: str = "livingtree", top_n: int = 15) -> list[BugHotspot]:
        """Score files by bug risk: high complexity + high churn = high risk."""
        # Collect complexity data
        complexity = {}
        for fpath in Path(root).rglob("*.py"):
            if any(p in str(fpath) for p in ("__pycache__", ".venv", "test_")):
                continue
            try:
                source = fpath.read_text(encoding="utf-8", errors="replace")
                tree = py_ast.parse(source)
                cc = 1
                for node in py_ast.walk(tree):
                    if isinstance(node, (py_ast.If, py_ast.While, py_ast.For, py_ast.ExceptHandler)):
                        cc += 1
                complexity[str(fpath)] = cc
            except Exception:
                pass

        # Collect churn data
        churn = {}
        try:
            result = subprocess.run(
                ["git", "log", "--format=", "--name-only", "--since=90.days", "--", root],
                capture_output=True, text=True, timeout=30,
            )
            churn = Counter(f.strip() for f in result.stdout.split("\n")
                          if f.strip().endswith(".py"))
        except Exception:
            pass

        # Collect bug-fix commit frequency
        bug_fixes = {}
        try:
            result = subprocess.run(
                ["git", "log", "--format=%s", "--name-only", "--since=90.days", "--", root],
                capture_output=True, text=True, timeout=30,
            )
            current_is_bug = False
            for line in result.stdout.split("\n"):
                if line and not line.startswith("livingtree"):
                    current_is_bug = any(
                        kw in line.lower()
                        for kw in ["fix", "bug", "crash", "error", "fail", "broken"]
                    )
                elif line.strip().endswith(".py") and current_is_bug:
                    bug_fixes[line.strip()] = bug_fixes.get(line.strip(), 0) + 1
        except Exception:
            pass

        # Combined risk score
        hotspots = []
        for fpath, cc in complexity.items():
            if cc < 10:
                continue
            ch = churn.get(fpath, 0)
            bf = bug_fixes.get(fpath, 0)
            lines = 0
            try:
                lines = Path(fpath).stat().st_size // 50
            except Exception:
                pass

            score = min(100, cc * 0.4 + ch * 0.8 + bf * 5.0 + lines * 0.01)
            reasons = []
            if cc > 50:
                reasons.append(f"High complexity (CC={cc})")
            if ch > 10:
                reasons.append(f"Frequent changes ({ch}x in 90d)")
            if bf > 0:
                reasons.append(f"Bug-fix history ({bf}x)")

            hotspots.append(BugHotspot(
                file=fpath, bug_score=round(score, 1),
                reasons=reasons,
                risk_factors={"complexity": cc, "churn": ch, "bug_fixes": bf, "lines": lines},
            ))

        return sorted(hotspots, key=lambda h: -h.bug_score)[:top_n]

    @staticmethod
    def format_report(hotspots: list[BugHotspot]) -> str:
        lines = ["## 🐛 Bug Hotspot Radar", ""]
        lines.append("| Risk | File | Score | Reasons |")
        lines.append("|------|------|-------|---------|")
        for h in hotspots[:15]:
            icon = "🔴" if h.bug_score > 70 else "🟡" if h.bug_score > 40 else "🟢"
            lines.append(
                f"| {icon} | {Path(h.file).name} | {h.bug_score} | "
                f"{'; '.join(h.reasons[:2])} |"
            )
        return "\n".join(lines)


__all__ = [
    "CodeMigrator", "MigrationPlan", "MigrationSite",
    "DeadCodeAnalyzer", "DeadCodeImpact",
    "TestAmplifier", "TestVariant",
    "LivingDiagram",
    "BugRadar", "BugHotspot",
]
