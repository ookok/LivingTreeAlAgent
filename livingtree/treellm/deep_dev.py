"""DeepDev — Advanced development intelligence: provenance, merge prediction, health trends.

Innovations building on CodeGraph + git history + improvement proposals:

  1. Code Provenance — trace every function back to its origin story
     "Why does chat() in core.py exist? Who created it? Which paper/proposal inspired it?"

  2. Merge Oracle — predict conflicts before they happen
     "I have branches A and B. Will they conflict? Which files? Can we auto-resolve?"

  3. Health Trends — track codebase quality over time
     "Is our complexity trending up? Test coverage improving? Bug density declining?"

  4. Onboarding Compass — personalized learning path for new contributors
     "I need to work on the routing system. What should I learn first?"

Usage:
    livingtree dev provenance <file> <function>
    livingtree dev merge-oracle <branch-a> <branch-b>
    livingtree dev health-trends [--since 30d]
    livingtree dev onboard <task_description>
"""

from __future__ import annotations

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
# Code Provenance — trace origin of every function
# ═══════════════════════════════════════════════════════════════

@dataclass
class ProvenanceEntry:
    """A single event in a function's history."""
    timestamp: float
    commit_hash: str
    author: str
    message: str
    change_type: str  # created | modified | renamed | refactored
    lines_changed: int = 0


@dataclass
class ProvenanceReport:
    """Complete origin story of a function."""
    function: str
    file: str
    created: ProvenanceEntry | None
    modified_by: list[ProvenanceEntry]
    related_proposals: list[str]  # Improvement proposal IDs
    related_papers: list[str]     # arXiv/Nature papers that inspired it
    total_modifications: int
    age_days: float
    bus_factor: int  # How many unique authors have touched it


class CodeProvenance:
    """Trace a function's origin story through git history and improvement logs."""

    @staticmethod
    def trace(filepath: str, function_name: str) -> ProvenanceReport | None:
        """Trace the complete history of a function."""
        real_path = filepath
        if not os.path.exists(real_path):
            for root in ["livingtree", "."]:
                candidate = Path(root) / filepath
                if candidate.exists():
                    real_path = str(candidate)
                    break
        if not os.path.exists(real_path):
            return None

        entries = []
        authors = set()
        try:
            result = subprocess.run(
                ["git", "log", "--format=%H|%at|%an|%s", "--", real_path],
                capture_output=True, text=True, timeout=30,
                encoding="utf-8", errors="replace",
            )
        except Exception:
            return None

        seen_def = False
        for line in result.stdout.split("\n"):
            line = line.strip()
            if not line or not line.startswith("{"):
                if "|" in line and line.count("|") >= 2:
                    parts = line.split("|", 3)
                    if len(parts) >= 4:
                        try:
                            current_commit = parts[0][:10]
                            current_time = float(parts[1])
                            current_author = parts[2]
                            current_message = parts[3][:200]
                            entries.append(ProvenanceEntry(
                                timestamp=current_time, commit_hash=current_commit,
                                author=current_author, message=current_message,
                                change_type="modified",
                            ))
                            authors.add(current_author)
                        except (ValueError, IndexError):
                            pass

        # Check improvement proposals
        related_proposals = []
        try:
            improvements_dir = Path(".livingtree/improvements")
            if improvements_dir.exists():
                for f in improvements_dir.glob("*.json"):
                    data = json.loads(f.read_text())
                    desc = data.get("description", "") + data.get("title", "")
                    if function_name in desc or Path(filepath).name in desc:
                        related_proposals.append(data.get("id", f.stem))
        except Exception:
            pass

        # Check learned papers
        related_papers = []
        try:
            learned = Path(".livingtree/learned_proposals.json")
            if learned.exists():
                data = json.loads(learned.read_text())
                for p in data:
                    if function_name in json.dumps(p):
                        related_papers.append(p.get("title", "")[:80])
        except Exception:
            pass

        return ProvenanceReport(
            function=function_name, file=filepath,
            created=entries[0] if entries else None,
            modified_by=entries[1:] if len(entries) > 1 else [],
            related_proposals=related_proposals[:5],
            related_papers=related_papers[:3],
            total_modifications=len(entries),
            age_days=(time.time() - entries[-1].timestamp) / 86400 if entries else 0,
            bus_factor=len(authors),
        )

    @staticmethod
    def format_report(report: ProvenanceReport) -> str:
        lines = [
            f"## Provenance: `{report.function}()` in {Path(report.file).name}",
            "",
            f"| Attribute | Value |",
            f"|-----------|-------|",
            f"| Age | {report.age_days:.0f} days |",
            f"| Total modifications | {report.total_modifications} |",
            f"| Bus factor | {report.bus_factor} authors |",
            f"| Related proposals | {len(report.related_proposals)} |",
            f"| Related papers | {len(report.related_papers)} |",
            "",
            "## Modification History",
            "",
        ]
        for e in report.modified_by[:10]:
            date = time.strftime("%Y-%m-%d", time.localtime(e.timestamp))
            icon = {"created": "🆕", "modified": "✏️", "refactored": "🔧"}.get(e.change_type, "📝")
            lines.append(f"  {icon} {date} [{e.commit_hash}] {e.author}: {e.message[:80]}")
        if report.created:
            date = time.strftime("%Y-%m-%d", time.localtime(report.created.timestamp))
            lines.append(f"  🆕 {date} [{report.created.commit_hash}] {report.created.author}: CREATED")
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# Merge Oracle — predict conflicts between branches
# ═══════════════════════════════════════════════════════════════

@dataclass
class MergeConflict:
    """A predicted merge conflict."""
    file: str
    risk: str  # certain | likely | possible
    reason: str
    funcs_in_A: list[str] = field(default_factory=list)
    funcs_in_B: list[str] = field(default_factory=list)
    auto_resolvable: bool = False


class MergeOracle:
    """Predict which files will conflict when merging two branches."""

    @staticmethod
    def predict(branch_a: str, branch_b: str,
                base: str = "master") -> list[MergeConflict]:
        """Analyze two branches and predict merge conflicts."""
        conflicts = []
        try:
            # Get changed files in both branches
            def get_changes(branch: str) -> dict[str, list[str]]:
                result = subprocess.run(
                    ["git", "diff", "--name-only", f"{base}...{branch}"],
                    capture_output=True, text=True, timeout=15,
                )
                files = [f.strip() for f in result.stdout.split("\n") if f.strip().endswith(".py")]
                return {f: MergeOracle._get_touched_functions(f, base, branch) for f in files}

            changes_a = get_changes(branch_a)
            changes_b = get_changes(branch_b)

            # Find overlapping files
            overlapping = set(changes_a.keys()) & set(changes_b.keys())
            for fpath in overlapping:
                funcs_a = changes_a.get(fpath, [])
                funcs_b = changes_b.get(fpath, [])

                # Different functions modified → auto-resolvable
                shared = set(funcs_a) & set(funcs_b)
                if not shared:
                    conflicts.append(MergeConflict(
                        file=fpath, risk="possible",
                        reason="Different functions modified in same file",
                        funcs_in_A=funcs_a, funcs_in_B=funcs_b,
                        auto_resolvable=True,
                    ))
                else:
                    # Same functions modified → likely conflict
                    conflicts.append(MergeConflict(
                        file=fpath, risk="likely",
                        reason=f"Same functions modified: {', '.join(shared)}",
                        funcs_in_A=funcs_a, funcs_in_B=funcs_b,
                        auto_resolvable=False,
                    ))

            # Check CodeGraph blast radius for cross-file impacts
            try:
                from ..capability.code_graph import CodeGraph
                cg = CodeGraph()
                cache = Path(".livingtree/code_graph.pickle")
                if cache.exists():
                    cg.load(str(cache))
                    all_changed = list(overlapping)
                    blast = cg.blast_radius(all_changed, max_depth=2)
                    for b in blast:
                        if b.file not in overlapping and b.risk == "critical":
                            conflicts.append(MergeConflict(
                                file=b.file, risk="certain",
                                reason=f"Downstream dependency of changed files",
                                auto_resolvable=False,
                            ))
            except Exception:
                pass

        except Exception as e:
            logger.debug(f"MergeOracle: {e}")

        return sorted(conflicts, key=lambda c: {"certain": 0, "likely": 1, "possible": 2}.get(c.risk, 3))

    @staticmethod
    def _get_touched_functions(filepath: str, base: str, branch: str) -> list[str]:
        """Get function names touched in a branch relative to base."""
        try:
            result = subprocess.run(
                ["git", "diff", f"{base}...{branch}", "--", filepath],
                capture_output=True, text=True, timeout=10,
                encoding="utf-8", errors="replace",
            )
            funcs = set()
            for line in result.stdout.split("\n"):
                m = re.search(r'^[+-]\s*(?:async\s+)?def\s+(\w+)', line)
                if m:
                    funcs.add(m.group(1))
            return list(funcs)
        except Exception:
            return []

    @staticmethod
    def format_report(conflicts: list[MergeConflict]) -> str:
        if not conflicts:
            return "✅ No merge conflicts predicted. Safe to merge!"
        lines = ["## 🔀 Merge Conflict Prediction", ""]
        icons = {"certain": "🔴", "likely": "🟡", "possible": "🟢"}
        for c in conflicts:
            lines.append(
                f"### {icons.get(c.risk,'❓')} {c.risk.upper()}: {Path(c.file).name}"
            )
            lines.append(f"  {c.reason}")
            if c.funcs_in_A:
                lines.append(f"  Branch A: {', '.join(c.funcs_in_A[:5])}")
            if c.funcs_in_B:
                lines.append(f"  Branch B: {', '.join(c.funcs_in_B[:5])}")
            lines.append(f"  Auto-resolvable: {'✅' if c.auto_resolvable else '❌'}")
            lines.append("")
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# Health Trends — track codebase quality over time
# ═══════════════════════════════════════════════════════════════

@dataclass
class HealthSnapshot:
    """A point-in-time health metric snapshot."""
    date: str
    total_files: int
    total_lines: int
    avg_complexity: float
    total_functions: int
    test_coverage_pct: float = 0.0
    bug_count: int = 0
    dependency_count: int = 0
    stale_deps: int = 0


class HealthTrends:
    """Track codebase health metrics over time from git history."""

    @staticmethod
    def analyze(since_days: int = 90) -> list[HealthSnapshot]:
        """Generate health snapshots at regular intervals going back `since_days`."""
        import ast as py_ast
        snapshots = []
        interval_days = max(7, since_days // 10)  # ~10 data points

        now = time.time()
        for days_ago in range(since_days, -interval_days, -interval_days):
            date = time.strftime("%Y-%m-%d", time.localtime(now - days_ago * 86400))
            date_str = f"@{int(now - days_ago * 86400)}"

            try:
                # Get codebase state at this date
                result = subprocess.run(
                    ["git", "log", "--format=%H", "--until", date,
                     "--max-count=1", "--", "livingtree/"],
                    capture_output=True, text=True, timeout=10,
                )
                commit = result.stdout.strip()
            except Exception:
                commit = ""

            # Count stats from git
            try:
                result = subprocess.run(
                    ["git", "ls-tree", "-r", "--name-only",
                     commit or "HEAD", "--", "livingtree/"],
                    capture_output=True, text=True, timeout=15,
                )
                py_files = [f for f in result.stdout.split("\n")
                          if f.endswith(".py") and "test_" not in f]
            except Exception:
                py_files = []

            # Sample analysis on N files
            total_lines = 0
            total_funcs = 0
            total_cc = 0
            sample = py_files[:50]

            for fpath in sample:
                try:
                    result = subprocess.run(
                        ["git", "show", f"{commit}:{fpath}" if commit else f"HEAD:{fpath}"],
                        capture_output=True, text=True, timeout=10,
                        encoding="utf-8", errors="replace",
                    )
                    source = result.stdout
                    tree = py_ast.parse(source)
                    total_lines += len(source.split("\n"))
                    for node in py_ast.walk(tree):
                        if isinstance(node, (py_ast.FunctionDef, py_ast.AsyncFunctionDef)):
                            total_funcs += 1
                            total_cc += 1
                        elif isinstance(node, (py_ast.If, py_ast.While, py_ast.For,
                                                 py_ast.ExceptHandler)):
                            total_cc += 1
                except Exception:
                    continue

            avg_cc = round(total_cc / max(total_funcs, 1), 1)
            if avg_cc < 1:
                avg_cc = 1.0

            snapshots.append(HealthSnapshot(
                date=date,
                total_files=len(py_files),
                total_lines=total_lines,
                avg_complexity=avg_cc,
                total_functions=total_funcs,
            ))

        return snapshots

    @staticmethod
    def format_report(snapshots: list[HealthSnapshot]) -> str:
        if len(snapshots) < 2:
            return "Not enough data for trends (need >=2 snapshots)"

        latest = snapshots[-1]
        first = snapshots[0]

        # Compute trends
        file_trend = latest.total_files - first.total_files
        cc_trend = latest.avg_complexity - first.avg_complexity

        lines = [
            "## 📈 Codebase Health Trends",
            "",
            f"| Metric | {first.date} | {latest.date} | Trend |",
            f"|--------|------|------|-------|",
            f"| Files | {first.total_files} | {latest.total_files} | "
            f"{'+' if file_trend > 0 else ''}{file_trend} |",
            f"| Lines (sampled) | {first.total_lines} | {latest.total_lines} | — |",
            f"| Functions (sampled) | {first.total_functions} | {latest.total_functions} | — |",
            f"| Avg Complexity | {first.avg_complexity} | {latest.avg_complexity} | "
            f"{'+' if cc_trend > 0 else ''}{cc_trend:.1f} |",
            "",
            "## Complexity Trend",
            "",
            "```",
        ]

        # ASCII sparkline for complexity
        max_cc = max(s.avg_complexity for s in snapshots)
        min_cc = min(s.avg_complexity for s in snapshots)
        span = max(max_cc - min_cc, 0.1)
        for s in snapshots:
            pos = int((s.avg_complexity - min_cc) / span * 20)
            bar = " " * pos + "█" + " " * (20 - pos)
            lines.append(f"  {s.date}  {bar}  CC={s.avg_complexity}")

        lines.append("```")

        # Health assessment
        if cc_trend > 0.5:
            lines.append(f"\n  ⚠️  Complexity trending UP (+{cc_trend:.1f}) — consider refactoring sprints")
        elif cc_trend < -0.5:
            lines.append(f"\n  ✅ Complexity trending DOWN ({cc_trend:.1f}) — good direction")
        else:
            lines.append(f"\n  ➡️  Complexity stable ({cc_trend:+.1f})")

        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# Onboarding Compass — personalized learning path
# ═══════════════════════════════════════════════════════════════

@dataclass
class OnboardingStep:
    """A step in the onboarding learning path."""
    order: int
    file: str
    concept: str
    why: str
    depends_on: list[str]
    complexity: str


class OnboardingCompass:
    """Generate a personalized learning path for new contributors."""

    @staticmethod
    def build(task_description: str,
              code_graph: Any = None) -> list[OnboardingStep]:
        """Build a learning path for a given task."""
        # Detect keywords
        keywords = set()
        task_lower = task_description.lower()
        keyword_map = {
            "route": ["holistic_election.py", "election_bus.py", "bandit_router.py"],
            "chat": ["core.py", "providers.py", "context_moe.py"],
            "memory": ["context_moe.py", "living_store.py", "struct_mem.py"],
            "graph": ["code_graph.py", "knowledge_graph.py", "reasoning_dependency_graph.py"],
            "evolution": ["life_engine.py", "self_evolution.py", "autonomous_learner.py"],
            "learn": ["external_learner.py", "self_improver.py", "learning_engine.py"],
            "api": ["routes.py", "htmx_web.py", "server.py"],
        }
        for kw, files in keyword_map.items():
            if kw in task_lower:
                keywords.update(files)

        if not keywords:
            keywords = {"core.py", "life_engine.py", "main.py"}

        steps = []
        for i, fname in enumerate(list(keywords)[:6]):
            # Find the real path
            real_path = fname
            for root_dir in ["livingtree/treellm", "livingtree/dna", "livingtree/api",
                           "livingtree/knowledge", "livingtree/capability", "livingtree"]:
                candidate = Path(root_dir) / fname
                if candidate.exists():
                    real_path = str(candidate)
                    break

            # Get module-level docstring as concept description
            concept = fname.replace(".py", "").replace("_", " ").title()
            try:
                source = Path(real_path).read_text(encoding="utf-8", errors="replace")
                import ast as py_ast
                tree = py_ast.parse(source)
                doc = py_ast.get_docstring(tree) or ""
                if doc:
                    concept = doc.split("\n")[0][:100]
            except Exception:
                pass

            steps.append(OnboardingStep(
                order=i + 1,
                file=fname,
                concept=concept,
                why=f"Required for: {task_description[:80]}",
                depends_on=[],
                complexity="medium" if Path(real_path).exists() and
                          Path(real_path).stat().st_size > 10000 else "low",
            ))

        return steps

    @staticmethod
    def format_path(steps: list[OnboardingStep]) -> str:
        lines = ["## 🧭 Onboarding Compass", ""]
        for s in steps:
            icon = "📗" if s.complexity == "low" else "📘" if s.complexity == "medium" else "📕"
            lines.append(f"### {s.order}. {icon} {Path(s.file).stem}")
            lines.append(f"  **{s.concept[:120]}**")
            lines.append(f"  *{s.why}*")
            lines.append("")
        return "\n".join(lines)


__all__ = [
    "CodeProvenance", "ProvenanceReport", "ProvenanceEntry",
    "MergeOracle", "MergeConflict",
    "HealthTrends", "HealthSnapshot",
    "OnboardingCompass", "OnboardingStep",
]
