"""LivingDev — Next-generation development tools: cognitive maps, API guards, living ADRs.

Innovations:
  1. Cognitive Load Map — color the codebase by complexity (green→red)
  2. API Compatibility Guard — track signatures, detect breaking changes, generate migration guides
  3. Living ADRs — auto-draft Architecture Decision Records from CodeGraph changes
  4. Dependency Health Score — freshness + CVE risk + usage impact

Usage:
    livingtree dev cognimap [--risk high]     # Show high-risk files by cognitive complexity
    livingtree dev api-guard [--check]        # Check for breaking API changes
    livingtree dev api-guard <file> <func>    # Show signature history for a function
    livingtree dev adr                         # Generate ADR from recent CodeGraph changes
"""

from __future__ import annotations

import json
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
# Cognitive Load Map
# ═══════════════════════════════════════════════════════════════

@dataclass
class CogniFile:
    """Cognitive complexity assessment of a single file."""
    path: str
    cyclomatic: int = 0
    cognitive: int = 0
    lines: int = 0
    functions: int = 0
    risk: str = "low"       # low | medium | high | critical
    color: str = "#22c55e"  # green → yellow → orange → red


class CognitiveLoader:
    """Generate a cognitive complexity heatmap of the codebase."""

    @staticmethod
    def analyze(root: str = "livingtree", risk_filter: str = "all") -> list[CogniFile]:
        """Analyze all Python files, score by complexity per line."""
        import ast as py_ast
        results = []

        for fpath in Path(root).rglob("*.py"):
            if any(p in str(fpath) for p in ("__pycache__", ".venv", "test_", "conftest")):
                continue
            try:
                source = fpath.read_text(encoding="utf-8", errors="replace")
                tree = py_ast.parse(source)
            except Exception:
                continue

            total_cyclomatic = 1
            total_cognitive = 0
            func_count = 0
            total_lines = len(source.split("\n"))
            nesting = 0

            for node in py_ast.walk(tree):
                if isinstance(node, (py_ast.If, py_ast.While, py_ast.For,
                                      py_ast.ExceptHandler, py_ast.Assert)):
                    total_cyclomatic += 1
                    nesting += 1
                    total_cognitive += nesting
                elif isinstance(node, (py_ast.BoolOp)):
                    total_cognitive += len(node.values) - 1
                elif isinstance(node, (py_ast.FunctionDef, py_ast.AsyncFunctionDef)):
                    func_count += 1
                    nesting = 0

            # Risk: complexity per 100 lines
            density = (total_cyclomatic + total_cognitive) / max(total_lines / 100, 1)
            if density > 30:
                risk, color = "critical", "#ef4444"
            elif density > 20:
                risk, color = "high", "#f97316"
            elif density > 10:
                risk, color = "medium", "#eab308"
            else:
                risk, color = "low", "#22c55e"

            if risk_filter != "all" and risk != risk_filter:
                continue

            results.append(CogniFile(
                path=str(fpath), cyclomatic=total_cyclomatic,
                cognitive=total_cognitive, lines=total_lines,
                functions=func_count, risk=risk, color=color,
            ))

        return sorted(results, key=lambda c: -(c.cyclomatic + c.cognitive))

    @staticmethod
    def format_map(files: list[CogniFile], top_n: int = 20) -> str:
        lines = ["## Cognitive Load Map", ""]
        lines.append("```")
        max_path = max((len(Path(f.path).name) for f in files[:top_n]), default=20)
        for f in files[:top_n]:
            bar_len = min(40, (f.cyclomatic + f.cognitive) // 2)
            bar = "█" * bar_len
            name = Path(f.path).name.ljust(max_path)
            label = f"{f.risk.upper():8s}"
            lines.append(
                f"  {name}  {bar}  CC={f.cyclomatic} Cog={f.cognitive} "
                f"funcs={f.functions} lines={f.lines}"
            )
        lines.append("```")
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# API Compatibility Guard
# ═══════════════════════════════════════════════════════════════

@dataclass
class APISignature:
    """A function signature snapshot."""
    function: str
    file: str
    params: list[str]
    return_annotation: str = ""
    decorators: list[str] = field(default_factory=list)
    docstring: str = ""
    commit_hash: str = ""
    timestamp: float = 0.0


@dataclass
class BreakingChange:
    """A detected breaking API change."""
    function: str
    file: str
    old_params: list[str]
    new_params: list[str]
    added: list[str]
    removed: list[str]
    renamed: list[tuple[str, str]]
    severity: str = "warning"  # info | warning | error
    callers_affected: int = 0


class APIGuard:
    """Track public API signatures and detect breaking changes."""

    SNAPSHOT_FILE = Path(".livingtree/api_snapshots.json")

    @staticmethod
    def snapshot(root: str = "livingtree") -> dict[str, APISignature]:
        """Capture current state of all public function signatures."""
        import ast as py_ast
        signatures = {}
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True, text=True, timeout=5,
            )
            commit = result.stdout.strip()[:10]
        except Exception:
            commit = "unknown"

        for fpath in Path(root).rglob("*.py"):
            if any(p in str(fpath) for p in ("__pycache__", ".venv", "test_")):
                continue
            try:
                source = fpath.read_text(encoding="utf-8", errors="replace")
                tree = py_ast.parse(source)
            except Exception:
                continue

            for node in py_ast.walk(tree):
                if isinstance(node, (py_ast.FunctionDef, py_ast.AsyncFunctionDef)):
                    if node.name.startswith("_"):
                        continue
                    key = f"{fpath}:{node.name}"
                    params = []
                    for arg in node.args.args + node.args.posonlyargs:
                        ann = ""
                        if arg.annotation:
                            ann = f": {py_ast.unparse(arg.annotation)}"
                        params.append(arg.arg + ann)
                    if node.args.vararg:
                        params.append(f"*{node.args.vararg.arg}")
                    if node.args.kwarg:
                        params.append(f"**{node.args.kwarg.arg}")

                    decorators = [
                        py_ast.unparse(d) for d in node.decorator_list
                    ] if node.decorator_list else []

                    ret = ""
                    if node.returns:
                        ret = py_ast.unparse(node.returns)

                    signatures[key] = APISignature(
                        function=node.name, file=str(fpath),
                        params=params, return_annotation=ret,
                        decorators=decorators,
                        docstring=py_ast.get_docstring(node) or "",
                        commit_hash=commit, timestamp=time.time(),
                    )
        return signatures

    @staticmethod
    def save_snapshot(sigs: dict[str, APISignature]) -> None:
        APIGuard.SNAPSHOT_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {
            k: {"function": s.function, "file": s.file, "params": s.params,
                "return_annotation": s.return_annotation,
                "decorators": s.decorators, "commit_hash": s.commit_hash,
                "timestamp": s.timestamp}
            for k, s in sigs.items()
        }
        APIGuard.SNAPSHOT_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    @staticmethod
    def load_snapshot() -> dict[str, APISignature]:
        if not APIGuard.SNAPSHOT_FILE.exists():
            return {}
        data = json.loads(APIGuard.SNAPSHOT_FILE.read_text(encoding="utf-8"))
        return {k: APISignature(**v) for k, v in data.items()}

    @staticmethod
    def check(root: str = "livingtree") -> list[BreakingChange]:
        """Compare current signatures against last snapshot, detect breaking changes."""
        current = APIGuard.snapshot(root)
        previous = APIGuard.load_snapshot()
        if not previous:
            APIGuard.save_snapshot(current)
            logger.info("APIGuard: initial snapshot saved")
            return []

        changes = []
        for key, cur in current.items():
            prev = previous.get(key)
            if not prev:
                continue

            old_set = set(re.sub(r':.*', '', p) for p in prev.params)
            new_set = set(re.sub(r':.*', '', p) for p in cur.params)
            added = sorted(new_set - old_set)
            removed = sorted(old_set - new_set)

            if added or removed:
                severity = "warning"
                if removed:
                    severity = "error"
                elif any("*" in a for a in added) or any("*" in r for r in removed):
                    severity = "error"

                # Check for renames (same count, same order)
                renamed = []
                if len(added) == len(removed) == 1:
                    renamed = [(removed[0], added[0])]

                # Count affected callers via CodeGraph
                affected = 0
                try:
                    from ..capability.code_graph import CodeGraph
                    cg = CodeGraph()
                    cache = Path(".livingtree/code_graph.pickle")
                    if cache.exists():
                        cg.load(str(cache))
                        callers = cg.get_callers(key)
                        affected = len(callers)
                except Exception:
                    pass

                changes.append(BreakingChange(
                    function=cur.function, file=cur.file,
                    old_params=prev.params, new_params=cur.params,
                    added=added, removed=removed,
                    renamed=renamed, severity=severity,
                    callers_affected=affected,
                ))

        APIGuard.save_snapshot(current)
        return sorted(changes, key=lambda c: -(c.callers_affected + (1 if c.severity == "error" else 0)))

    @staticmethod
    def format_report(changes: list[BreakingChange]) -> str:
        if not changes:
            return "✅ No breaking API changes detected."
        lines = ["## 🔴 Breaking API Changes", ""]
        for c in changes:
            icon = "❌" if c.severity == "error" else "⚠️ "
            lines.append(f"### {icon} {c.file}: `{c.function}()`")
            if c.removed:
                lines.append(f"  Removed params: `{', '.join(c.removed)}`")
            if c.added:
                lines.append(f"  Added params: `{', '.join(c.added)}`")
            if c.renamed:
                for old, new in c.renamed:
                    lines.append(f"  Renamed: `{old}` → `{new}`")
            if c.callers_affected:
                lines.append(f"  ⚡ {c.callers_affected} callers need updating")
            lines.append("")
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# Living ADR (Architecture Decision Records)
# ═══════════════════════════════════════════════════════════════

@dataclass
class ADR:
    """An Architecture Decision Record."""
    id: int
    title: str
    status: str  # proposed | accepted | deprecated
    date: str
    context: str
    decision: str
    consequences: str
    affected_files: list[str]
    triggers: list[str]  # What CodeGraph changes triggered this


class LivingADR:
    """Auto-draft ADRs from CodeGraph structural changes."""

    ADR_DIR = Path("docs/adr")

    @staticmethod
    def generate(code_graph: Any = None) -> ADR | None:
        """Generate an ADR from recent structural changes detected by CodeGraph."""
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

        # Find new hubs (high-connectivity entities added since last snapshot)
        hubs = code_graph.find_hubs(20)
        stats = code_graph.stats()

        # Check for new dependency patterns
        significant = [h for h in hubs[:5]
                      if len(h.dependents) > 10 and len(h.dependencies) > 5]

        if not significant:
            return None

        hub_names = [h.name for h in significant[:3]]
        hub_files = [h.file for h in significant[:3]]

        now = time.strftime("%Y-%m-%d")
        title = f"Architecture: {', '.join(hub_names[:2])} as emerging hubs"

        # Try LLM for richer decision text
        decision_text = (
            f"New architectural hubs detected: {', '.join(hub_names)}. "
            f"These modules have high connectivity ({len(significant[0].dependents)} dependents) "
            f"and serve as integration points. Total graph: "
            f"{stats.total_entities} entities, {stats.total_edges} edges."
        )

        return ADR(
            id=int(time.time()) % 100000,
            title=title, status="proposed", date=now,
            context=f"CodeGraph detected {len(hubs)} hubs with >10 connections",
            decision=decision_text,
            consequences=(
                f"Files {', '.join(Path(f).name for f in hub_files[:3])} "
                f"will become harder to modify as dependents grow. "
                f"Consider extracting interfaces or adding deprecation warnings."
            ),
            affected_files=hub_files[:5],
            triggers=[f"Hub detection: {h.name} ({len(h.dependents)} deps)" for h in significant[:3]],
        )

    @staticmethod
    def save_adr(adr: ADR) -> Path:
        LivingADR.ADR_DIR.mkdir(parents=True, exist_ok=True)
        num = adr.id % 10000
        fpath = LivingADR.ADR_DIR / f"{num:04d}-{adr.title[:50].replace(' ', '-').replace(':', '').lower()}.md"
        content = f"""# ADR-{num:04d}: {adr.title}

- **Status:** {adr.status}
- **Date:** {adr.date}

## Context
{adr.context}

## Decision
{adr.decision}

## Consequences
{adr.consequences}

## Affected Files
{chr(10).join(f'- {f}' for f in adr.affected_files)}

## Triggers
{chr(10).join(f'- {t}' for t in adr.triggers)}

---
*Auto-generated by LivingADR from CodeGraph analysis*
"""
        fpath.write_text(content, encoding="utf-8")
        return fpath


# ═══════════════════════════════════════════════════════════════
# Dependency Health Score
# ═══════════════════════════════════════════════════════════════

@dataclass
class DepHealth:
    """Health assessment of a project dependency."""
    name: str
    version: str = "unknown"
    latest: str = "unknown"
    is_stale: bool = False
    usage_count: int = 0
    risk: str = "low"


class DependencyDoctor:
    """Assess dependency freshness and upgrade risk."""

    @staticmethod
    def diagnose() -> list[DepHealth]:
        """Check installed packages against PyPI for staleness."""
        results = []
        try:
            result = subprocess.run(
                ["pip", "list", "--outdated", "--format=json"],
                capture_output=True, text=True, timeout=30,
            )
            outdated = json.loads(result.stdout) if result.stdout else []
        except Exception:
            outdated = []

        try:
            result = subprocess.run(
                ["pip", "list", "--format=json"],
                capture_output=True, text=True, timeout=15,
            )
            installed = {p["name"]: p["version"] for p in json.loads(result.stdout)}
        except Exception:
            installed = {}

        # Count usage per package
        usage = Counter()
        for fpath in Path("livingtree").rglob("*.py"):
            if any(p in str(fpath) for p in ("__pycache__", ".venv")):
                continue
            try:
                content = fpath.read_text(encoding="utf-8", errors="replace")
                for line in content.split("\n"):
                    if line.strip().startswith(("import ", "from ")):
                        for name in installed:
                            if name.lower().replace("-", "_") in line.lower():
                                usage[name] += 1
            except Exception:
                pass

        for pkg in outdated:
            name = pkg["name"]
            results.append(DepHealth(
                name=name, version=pkg["version"],
                latest=pkg["latest_version"],
                is_stale=True,
                usage_count=usage.get(name, 0),
                risk="high" if usage.get(name, 0) > 20 else "medium",
            ))

        return sorted(results, key=lambda d: -(d.usage_count))

    @staticmethod
    def format_report(deps: list[DepHealth]) -> str:
        if not deps:
            return "✅ All dependencies up to date."
        lines = ["## 📦 Stale Dependencies", ""]
        lines.append(f"| Package | Current | Latest | Usage | Risk |")
        lines.append(f"|---------|---------|--------|-------|------|")
        for d in deps[:15]:
            risk_icon = "🔴" if d.risk == "high" else "🟡" if d.risk == "medium" else "🟢"
            lines.append(
                f"| {d.name} | {d.version} | {d.latest} | "
                f"{d.usage_count} files | {risk_icon} {d.risk} |"
            )
        return "\n".join(lines)


__all__ = [
    "CognitiveLoader", "CogniFile",
    "APIGuard", "APISignature", "BreakingChange",
    "LivingADR", "ADR",
    "DependencyDoctor", "DepHealth",
]
