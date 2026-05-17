"""CodeReviewer — Automated code review from git diffs with structured output.

Given a git diff or file change, produces:
  - Line-by-line review comments
  - Severity classification (error/warning/info)
  - Category tagging (bug/performance/style/security/maintainability)
  - Suggested fixes with code snippets

Integration:
  reviewer = get_code_reviewer()
  report = await reviewer.review_diff("HEAD~1", "HEAD")
  report = await reviewer.review_file("livingtree/treellm/core.py")
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Optional

from loguru import logger
# SUBPROCESS MIGRATION: from livingtree.treellm.unified_exec import run_sync



class ReviewSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ReviewCategory(StrEnum):
    BUG = "bug"
    PERFORMANCE = "performance"
    STYLE = "style"
    SECURITY = "security"
    MAINTAINABILITY = "maintainability"


@dataclass
class ReviewComment:
    file: str
    line: int = 0
    severity: ReviewSeverity = ReviewSeverity.INFO
    category: ReviewCategory = ReviewCategory.STYLE
    message: str = ""
    suggestion: str = ""
    code_snippet: str = ""


@dataclass
class ReviewReport:
    comments: list[ReviewComment] = field(default_factory=list)
    summary: str = ""
    score: int = 0   # 0-100
    files_changed: int = 0


# ═══ Pattern Database ══════════════════════════════════════════════

REVIEW_PATTERNS = [
    # Security
    (r'subprocess\.run\([^)]*shell\s*=\s*True', ReviewCategory.SECURITY, ReviewSeverity.ERROR,
     "shell=True is a command injection risk. Use list arguments instead: subprocess.run(['cmd', 'arg'])"),
    (r'os\.system\(', ReviewCategory.SECURITY, ReviewSeverity.ERROR,
     "os.system() is dangerous. Use subprocess.run() with list arguments"),
    (r'exec\(|eval\(', ReviewCategory.SECURITY, ReviewSeverity.WARNING,
     "exec()/eval() can execute arbitrary code. Consider safer alternatives"),

    # Performance
    (r'for\s+\w+\s+in\s+range\(len\(', ReviewCategory.PERFORMANCE, ReviewSeverity.INFO,
     "Use enumerate() instead of range(len()) for cleaner iteration"),
    (r'\.append\(.*\)\s*\n\s*.*\.append\(', ReviewCategory.PERFORMANCE, ReviewSeverity.INFO,
     "Multiple appends detected. Consider list comprehension or extend()"),
    (r'import\s+re\s*\n', ReviewCategory.PERFORMANCE, ReviewSeverity.INFO,
     "Import inside function body. Move to module level for better performance"),

    # Style
    (r'except\s+Exception\s*:\s*$', ReviewCategory.STYLE, ReviewSeverity.WARNING,
     "Bare except Exception: pass swallows all errors. Add logging: logger.debug(f'context: {e}')"),
    (r'^\s{5,}', ReviewCategory.STYLE, ReviewSeverity.INFO,
     "Deep nesting detected (>4 levels). Consider extracting to separate function"),

    # Bug patterns
    (r'\w+\.append\(\w+\)\s*\n\s*return\s+\w+', ReviewCategory.BUG, ReviewSeverity.WARNING,
     "Return after append within same indentation block may have unintended side effects"),
    (r'if\s+\w+\s*==\s*None\s*:\s*\n\s+\w+\s*\.\w+', ReviewCategory.BUG, ReviewSeverity.INFO,
     "Potential NoneType attribute access. Could raise AttributeError"),

    # Maintainability
    (r'def\s+\w+\([^)]{80,}\)', ReviewCategory.MAINTAINABILITY, ReviewSeverity.INFO,
     "Function with many parameters. Consider using a dataclass or config object"),
    (r'#\s*TODO|#\s*FIXME|#\s*HACK', ReviewCategory.MAINTAINABILITY, ReviewSeverity.INFO,
     "TODO/FIXME/HACK comment found. Consider creating an issue instead"),
]


class CodeReviewer:
    """Automated code review from diffs or files."""

    _instance: Optional["CodeReviewer"] = None

    @classmethod
    def instance(cls) -> "CodeReviewer":
        if cls._instance is None:
            cls._instance = CodeReviewer()
        return cls._instance

    def __init__(self):
        self._reports: list[ReviewReport] = []

    # ── Review APIs ────────────────────────────────────────────────

    async def review_diff(self, base: str = "HEAD~1",
                          current: str = "HEAD") -> ReviewReport:
        """Review changes between two git refs."""
        import subprocess
        try:
            result = subprocess.run(
                ["git", "diff", "--unified=5", base, current],
                capture_output=True, text=True, timeout=30,
            )
            changed = subprocess.run(
                ["git", "diff", "--name-only", base, current],
                capture_output=True, text=True, timeout=10,
            )
            files = [f.strip() for f in changed.stdout.split("\n") if f.strip()]
            return self._review_text(result.stdout, files)
        except Exception as e:
            return ReviewReport(summary=f"Review failed: {e}")

    async def review_file(self, file_path: str) -> ReviewReport:
        """Review a single file."""
        path = Path(file_path)
        if not path.exists():
            return ReviewReport(summary=f"File not found: {file_path}")
        content = path.read_text(errors="replace")
        return self._review_text(content, [file_path])

    async def review_staged(self) -> ReviewReport:
        """Review staged changes."""
        import subprocess
        try:
            result = subprocess.run(
                ["git", "diff", "--cached", "--unified=5"],
                capture_output=True, text=True, timeout=30,
            )
            changed = subprocess.run(
                ["git", "diff", "--cached", "--name-only"],
                capture_output=True, text=True, timeout=10,
            )
            files = [f.strip() for f in changed.stdout.split("\n") if f.strip()]
            return self._review_text(result.stdout, files)
        except Exception as e:
            return ReviewReport(summary=f"Review failed: {e}")

    # ── Review Engine ──────────────────────────────────────────────

    def _review_text(self, text: str, files: list[str]) -> ReviewReport:
        """Apply all review patterns to text."""
        report = ReviewReport(files_changed=len(files))
        comments = []

        for line_num, line in enumerate(text.split("\n"), 1):
            if not line.startswith("+"):
                continue
            # Map diff line to actual file
            current_file = files[0] if files else "unknown"
            for p_file in files:
                if p_file in text[:line_num * 100]:
                    current_file = p_file
                    break

            for pattern, category, severity, message in REVIEW_PATTERNS:
                if re.search(pattern, line):
                    comments.append(ReviewComment(
                        file=current_file, line=line_num,
                        severity=severity, category=category,
                        message=message,
                        code_snippet=line.strip()[:120],
                    ))

        report.comments = comments

        # Score: deduct per issue
        deductions = sum(
            {ReviewSeverity.ERROR: 15, ReviewSeverity.WARNING: 5, ReviewSeverity.INFO: 2}[c.severity]
            for c in comments
        )
        report.score = max(0, 100 - deductions)

        # Summary
        by_sev = {s: sum(1 for c in comments if c.severity == s)
                  for s in ReviewSeverity}
        report.summary = (
            f"Review complete: {len(comments)} issues found "
            f"({by_sev[ReviewSeverity.ERROR]} errors, "
            f"{by_sev[ReviewSeverity.WARNING]} warnings, "
            f"{by_sev[ReviewSeverity.INFO]} info). "
            f"Score: {report.score}/100"
        )

        self._reports.append(report)
        return report

    # ── Format Output ──────────────────────────────────────────────

    def format_markdown(self, report: ReviewReport) -> str:
        """Format review report as Markdown for PR comments."""
        lines = [
            f"## Code Review — Score: {report.score}/100",
            f"",
            report.summary,
            "",
        ]

        if report.comments:
            lines.append("| File | Line | Severity | Category | Issue |")
            lines.append("|------|------|----------|----------|-------|")
            for c in report.comments:
                lines.append(
                    f"| {c.file[:40]} | L{c.line} | {c.severity.value} "
                    f"| {c.category.value} | {c.message[:80]} |"
                )
            lines.append("")

            # Group by file
            by_file = {}
            for c in report.comments:
                by_file.setdefault(c.file, []).append(c)

            for file, file_comments in by_file.items():
                lines.append(f"### {file}")
                for c in file_comments[:5]:
                    icon = {"error": "🔴", "warning": "🟡", "info": "🔵"}[c.severity.value]
                    lines.append(f"- {icon} L{c.line}: {c.message}")
                    if c.code_snippet:
                        lines.append(f"  ```\n  {c.code_snippet}\n  ```")
                lines.append("")

        return "\n".join(lines)

    def stats(self) -> dict:
        return {"reports": len(self._reports)}


_reviewer: Optional[CodeReviewer] = None


def get_code_reviewer() -> CodeReviewer:
    global _reviewer
    if _reviewer is None:
        _reviewer = CodeReviewer()
    return _reviewer


__all__ = ["CodeReviewer", "ReviewReport", "ReviewComment",
           "ReviewSeverity", "ReviewCategory", "get_code_reviewer"]
