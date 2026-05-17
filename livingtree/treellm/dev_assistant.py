"""DevAssistant — Integrated developer workflow tools for the LivingTree project.

Innovations building on existing infrastructure (CodeGraph, CodeContext, ASTParser):

  1. Change Rehearsal — predict impact before committing:
     "What happens if I modify core.py:chat()?"
     → blast radius + affected tests + caller breakage prediction

  2. Hot/Cold Analysis — identify stabilization candidates:
     "Which files churn the most? Which are stable enough to freeze API?"
     → git log frequency + CodeGraph hub score + external pattern matching

  3. Convention Extractor — living style guide from codebase itself:
     "What naming conventions does this project use?"
     → analyze function/class names, import ordering, error handling patterns

  4. Docstring Drift Detector — find mismatched signatures:
     "Which docstrings don't match their function signatures?"
     → AST parse signature vs docstring param list comparison

Usage:
    livingtree dev rehearse [--files core.py chat]
    livingtree dev hotspots [--top 10]
    livingtree dev conventions
    livingtree dev doccheck [--fix]
"""

from __future__ import annotations

import json
import re
import subprocess
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from loguru import logger
# SUBPROCESS MIGRATION: from livingtree.treellm.unified_exec import run_sync



@dataclass
class ChangeImpact:
    """Predicted impact of a code change."""
    file: str
    function: str = ""
    dependents_affected: int = 0
    tests_at_risk: list[str] = field(default_factory=list)
    callers_that_break: list[str] = field(default_factory=list)
    risk_level: str = "low"
    estimated_fix_time_minutes: int = 0


@dataclass
class HotspotReport:
    """A frequently-changed or risky file."""
    file: str
    change_count: int
    last_changed_days: float
    hub_score: int = 0
    complexity: int = 0
    status: str = "active"


@dataclass
class ConventionReport:
    """Extracted coding conventions from codebase."""
    naming_patterns: dict[str, list[str]]
    import_style: str
    error_handling: dict[str, int]
    docstring_coverage: float
    avg_function_length: float
    top_patterns: list[str]


@dataclass
class DocstringDrift:
    """A function whose docstring doesn't match its signature."""
    file: str
    function: str
    line: int
    sig_params: list[str]
    doc_params: list[str]
    missing_in_doc: list[str]
    extra_in_doc: list[str]


class ChangeRehearsal:
    """Predict the impact of a code change before committing."""

    @staticmethod
    def rehearse(files: list[str], functions: list[str] | None = None,
                 code_graph: Any = None) -> list[ChangeImpact]:
        """Simulate a change and predict its blast radius."""
        if not code_graph:
            try:
                from ..capability.code_graph import CodeGraph
                cg = CodeGraph()
                cache = Path(".livingtree/code_graph.pickle")
                if cache.exists():
                    cg.load(str(cache))
                code_graph = cg
            except Exception:
                return []

        impacts = []
        for fpath in files:
            blast = code_graph.blast_radius([fpath], max_depth=3)
            for b in blast:
                impact = ChangeImpact(
                    file=b.file,
                    dependents_affected=len(b.affected_entities),
                    tests_at_risk=[e for e in b.affected_entities if "test" in e.lower()],
                    callers_that_break=[e for e in b.affected_entities if b.risk == "critical"],
                    risk_level=b.risk,
                    estimated_fix_time_minutes=len(b.affected_entities) * 2,
                )
                impacts.append(impact)

        return sorted(impacts, key=lambda i: -i.dependents_affected)

    @staticmethod
    def format_report(impacts: list[ChangeImpact]) -> str:
        if not impacts:
            return "No changes to rehearse."
        lines = [
            "## Change Rehearsal Report",
            f"",
            f"| File | Risk | Dependents | Tests at Risk | Fix Time |",
            f"|------|------|------------|---------------|----------|",
        ]
        for i in impacts[:10]:
            lines.append(
                f"| {Path(i.file).name} | {i.risk_level.upper()} | "
                f"{i.dependents_affected} | {len(i.tests_at_risk)} | "
                f"~{i.estimated_fix_time_minutes}min |"
            )
        return "\n".join(lines)


class HotColdAnalyzer:
    """Identify file churn patterns and stabilization candidates."""

    @staticmethod
    def analyze(root: str = "livingtree", top_n: int = 15,
                code_graph: Any = None) -> list[HotspotReport]:
        """Analyze git log frequency + CodeGraph hub scores."""
        reports = []
        try:
            result = subprocess.run(
                ["git", "log", "--format=", "--name-only", "--since=90.days", "--", root],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=30,
            )
            file_counts = Counter(
                f.strip() for f in result.stdout.split("\n")
                if f.strip().endswith(".py")
            )
        except Exception:
            file_counts = Counter()

        # Add last-changed dates
        try:
            result = subprocess.run(
                ["git", "log", "--format=%ad %n", "--date=short", "--name-only",
                 "--since=90.days", "--", root],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=30,
            )
            last_changed = {}
            current_date = ""
            for line in result.stdout.split("\n"):
                line = line.strip()
                if re.match(r'\d{4}-\d{2}-\d{2}', line):
                    current_date = line
                elif line.endswith(".py"):
                    last_changed[line] = current_date
        except Exception:
            last_changed = {}

        # Add hub scores from CodeGraph
        hub_scores = {}
        if code_graph:
            try:
                hubs = code_graph.find_hubs(50)
                for h in hubs:
                    hub_scores[h.file] = len(h.dependents) + len(h.dependencies)
            except Exception:
                pass

        for fpath, count in file_counts.most_common(top_n):
            if not Path(fpath).exists():
                continue
            days_ago = 90
            if fpath in last_changed and last_changed[fpath]:
                try:
                    last_date = time.strptime(last_changed[fpath], "%Y-%m-%d")
                    days_ago = (time.time() - time.mktime(last_date)) / 86400
                except Exception:
                    pass

            status = "stable" if days_ago > 60 else "cooling" if days_ago > 30 else "active"
            if count > 15:
                status = "hot"

            reports.append(HotspotReport(
                file=fpath, change_count=count,
                last_changed_days=round(days_ago, 1),
                hub_score=hub_scores.get(fpath, 0),
                status=status,
            ))

        return reports

    @staticmethod
    def format_report(reports: list[HotspotReport]) -> str:
        lines = [
            "## Hot/Cold File Analysis",
            "",
            f"| Status | File | Changes (90d) | Last Changed | Hub Score |",
            f"|--------|------|---------------|--------------|-----------|",
        ]
        icons = {"hot": "🔥", "active": "⚡", "cooling": "❄️", "stable": "✅"}
        for r in reports:
            lines.append(
                f"| {icons.get(r.status,' ')} {r.status} | {Path(r.file).name} | "
                f"{r.change_count} | {r.last_changed_days}d ago | {r.hub_score} |"
            )
        return "\n".join(lines)


class DocstringChecker:
    """Detect drift between function signatures and docstrings."""

    @staticmethod
    def check_file(filepath: str) -> list[DocstringDrift]:
        """Find functions whose docstring params don't match actual signature."""
        findings = []
        try:
            source = Path(filepath).read_text(encoding="utf-8", errors="replace")
            import ast as py_ast
            tree = py_ast.parse(source)
        except (SyntaxError, OSError):
            return findings

        for node in py_ast.walk(tree):
            if isinstance(node, (py_ast.FunctionDef, py_ast.AsyncFunctionDef)):
                drift = DocstringChecker._check_function(node, filepath)
                if drift:
                    findings.append(drift)
        return findings

    @staticmethod
    def _check_function(node, filepath: str) -> DocstringDrift | None:
        docstring = py_ast.get_docstring(node)
        if not docstring:
            return None

        # Extract actual params from signature
        sig_params = []
        for arg in node.args.args + node.args.posonlyargs:
            sig_params.append(arg.arg)
        if node.args.vararg:
            sig_params.append(f"*{node.args.vararg.arg}")
        if node.args.kwarg:
            sig_params.append(f"**{node.args.kwarg.arg}")

        # Exclude 'self' and 'cls'
        sig_params = [p for p in sig_params if p not in ("self", "cls")]

        # Extract documented params from docstring
        doc_params = re.findall(r':param\s+(\w+)', docstring)
        doc_params += re.findall(r'Args:\s*\n(?:\s+(\w+):.*?\n)+', docstring)

        if not sig_params and not doc_params:
            return None

        missing = [p for p in sig_params if p not in doc_params]
        extra = [p for p in doc_params if p not in sig_params]

        if missing or extra:
            return DocstringDrift(
                file=filepath, function=node.name, line=node.lineno,
                sig_params=sig_params, doc_params=doc_params,
                missing_in_doc=missing, extra_in_doc=extra,
            )
        return None

    @staticmethod
    def format_report(drifts: list[DocstringDrift]) -> str:
        if not drifts:
            return "✅ No docstring drift detected."
        lines = ["## Docstring Drift Report", ""]
        for d in drifts[:20]:
            lines.append(f"### {d.file}:{d.line} `{d.function}()`")
            if d.missing_in_doc:
                lines.append(f"  Missing in docstring: {', '.join(d.missing_in_doc)}")
            if d.extra_in_doc:
                lines.append(f"  Extra in docstring (removed from code): {', '.join(d.extra_in_doc)}")
        return "\n".join(lines)


class ConventionExtractor:
    """Extract coding conventions from the codebase itself."""

    @staticmethod
    def extract(root: str = "livingtree", sample_files: int = 30) -> ConventionReport:
        """Analyze naming patterns, import style, error handling, docstring coverage."""
        import ast as py_ast

        py_files = list(Path(root).rglob("*.py"))[:sample_files]
        func_names = []
        class_names = []
        import_style = Counter()
        error_patterns = Counter()
        docstring_count = 0
        total_funcs = 0
        total_lines = 0
        func_lines = []

        for fpath in py_files:
            try:
                source = fpath.read_text(encoding="utf-8", errors="replace")
                tree = py_ast.parse(source)
                total_lines += len(source.split("\n"))
            except Exception:
                continue

            for node in py_ast.walk(tree):
                if isinstance(node, py_ast.FunctionDef):
                    func_names.append(node.name)
                    total_funcs += 1
                    if node.end_lineno:
                        func_lines.append(node.end_lineno - node.lineno + 1)
                    if py_ast.get_docstring(node):
                        docstring_count += 1
                elif isinstance(node, py_ast.ClassDef):
                    class_names.append(node.name)
                elif isinstance(node, py_ast.Import):
                    for alias in node.names:
                        import_style["direct"] += 1
                elif isinstance(node, py_ast.ImportFrom):
                    import_style["from_import"] += 1
                elif isinstance(node, py_ast.Try):
                    for handler in node.handlers:
                        if handler.type:
                            error_patterns[py_ast.unparse(handler.type)] += 1
                        else:
                            error_patterns["bare_except"] += 1

        # Naming conventions
        snake = sum(1 for n in func_names if "_" in n and n == n.lower())
        camel = sum(1 for n in func_names if any(c.isupper() for c in n[1:]))

        return ConventionReport(
            naming_patterns={
                "snake_case": [f"{snake}/{len(func_names)} functions ({snake*100//max(len(func_names),1)}%)"],
                "PascalCase": [f"{len([n for n in class_names if n[0].isupper()])}/{len(class_names)} classes"],
            },
            import_style="from_import" if import_style["from_import"] > import_style["direct"] else "direct_import",
            error_handling=dict(error_patterns.most_common(5)),
            docstring_coverage=round(docstring_count / max(total_funcs, 1) * 100, 1),
            avg_function_length=round(sum(func_lines) / max(len(func_lines), 1), 1),
            top_patterns=[
                f"Functions: snake_case dominant ({snake} vs {camel} CamelCase)",
                f"Imports: {'from X import Y' if import_style['from_import'] > import_style['direct'] else 'import X'} style",
                f"Top error caught: {error_patterns.most_common(1)[0][0] if error_patterns else 'Exception'}",
            ],
        )

    @staticmethod
    def format_report(report: ConventionReport) -> str:
        lines = [
            "## Living Code Conventions",
            "",
            "### Naming",
        ]
        for k, v in report.naming_patterns.items():
            lines.append(f"  {k}: {v[0]}")
        lines += [
            "",
            "### Imports",
            f"  Style: {report.import_style}",
            "",
            "### Error Handling",
        ]
        for exc, count in report.error_handling.items():
            lines.append(f"  {exc}: {count}x")
        lines += [
            "",
            "### Documentation",
            f"  Docstring coverage: {report.docstring_coverage}%",
            f"  Avg function length: {report.avg_function_length} lines",
            "",
            "### Inferred Patterns",
        ]
        for p in report.top_patterns:
            lines.append(f"  - {p}")
        return "\n".join(lines)


__all__ = [
    "ChangeRehearsal", "ChangeImpact",
    "HotColdAnalyzer", "HotspotReport",
    "DocstringChecker", "DocstringDrift",
    "ConventionExtractor", "ConventionReport",
]
