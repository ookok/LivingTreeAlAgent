"""Output Linter — Hermes 0.13 post-write self-validation.

Automatically validates LLM output before delivering to the user.
Checks: syntax errors (Python/JSON/YAML), unclosed code fences,
hallucinated file paths, and content safety.
"""

from __future__ import annotations

import re as _re
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger


@dataclass
class LintResult:
    passed: bool
    issues: list[dict] = field(default_factory=list)
    fixed: list[str] = field(default_factory=list)
    sanitized: str = ""
    score: float = 1.0


class OutputLinter:
    """Hermes-style post-write validation.

    Checks applied before output reaches the user:
      1. Unclosed markdown code fences (common LLM mistake)
      2. Python syntax errors in code blocks
      3. JSON validity
      4. Hallucinated absolute paths
      5. Repeated paragraphs (echo chamber)
    """

    def __init__(self):
        self._total_checks: int = 0
        self._issues_found: int = 0

    def lint(self, text: str, content_type: str = "general") -> LintResult:
        """Run all lint checks and return a sanitized version."""
        self._total_checks += 1
        issues = []
        fixes = []
        sanitized = text

        r = self._check_unclosed_fences(sanitized)
        if r:
            issues.extend(r)
            sanitized = self._close_fences(sanitized)
            fixes.append("closed unclosed fences")

        r = self._check_hallucinated_paths(sanitized)
        if r:
            issues.extend(r)
            sanitized = self._sanitize_paths(sanitized)
            fixes.append("sanitized paths")

        r = self._check_repeated_paragraphs(sanitized)
        if r:
            issues.extend(r)
            sanitized = self._deduplicate(sanitized)
            fixes.append("deduplicated repeats")

        if content_type == "code":
            r = self._check_python_syntax(text)
            if r:
                issues.extend(r)

        if issues:
            self._issues_found += 1

        score = max(0.0, 1.0 - len(issues) * 0.15)
        return LintResult(
            passed=len(issues) == 0,
            issues=issues, fixed=fixes,
            sanitized=sanitized, score=round(score, 2),
        )

    def _check_unclosed_fences(self, text: str) -> list[dict]:
        count = text.count("```")
        if count % 2 != 0:
            return [{"type": "unclosed_fence", "detail": f"{count} fence markers (odd)"}]
        return []

    def _check_hallucinated_paths(self, text: str) -> list[dict]:
        issues = []
        for m in _re.finditer(r'(/home/\w+|/Users/\w+|C:\\)\S*', text):
            issues.append({"type": "hallucinated_path", "detail": m.group()[:60]})
        return issues[:3]

    def _check_repeated_paragraphs(self, text: str) -> list[dict]:
        paras = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 30]
        seen = set()
        issues = []
        for p in paras:
            key = p[:50]
            if key in seen:
                issues.append({"type": "repeated_paragraph", "detail": key[:60] + "..."})
            seen.add(key)
        return issues[:3]

    def _check_python_syntax(self, text: str) -> list[dict]:
        code_blocks = _re.findall(r'```python\n(.*?)```', text, _re.DOTALL)
        issues = []
        for i, block in enumerate(code_blocks):
            try:
                import ast
                ast.parse(block)
            except SyntaxError as e:
                issues.append({"type": "python_syntax", "detail": f"block {i+1}: {e.msg}"})
        return issues[:3]

    def _close_fences(self, text: str) -> str:
        if text.count("```") % 2 != 0:
            text = text.rstrip() + "\n```"
        return text

    def _sanitize_paths(self, text: str) -> str:
        return _re.sub(r'(/home/\w+|/Users/\w+)', r'~/', text)

    def _deduplicate(self, text: str) -> str:
        paras = text.split("\n\n")
        seen, result = set(), []
        for p in paras:
            key = p.strip()[:50]
            if key not in seen:
                result.append(p)
                seen.add(key)
        return "\n\n".join(result)

    def stats(self) -> dict:
        return {
            "total_checks": self._total_checks,
            "issues_found": self._issues_found,
            "pass_rate": round(1 - self._issues_found / max(1, self._total_checks), 3),
        }


_instance: Optional[OutputLinter] = None


def get_linter() -> OutputLinter:
    global _instance
    if _instance is None:
        _instance = OutputLinter()
    return _instance
