"""SemanticDiff — LLM translates code diffs into human language.

    Not line counts. Tells you WHAT changed and WHY.

    Usage:
        sd = get_semantic_diff()
        result = await sd.explain_diff(hub)
        # → "把端口从8100改成了8888，server.py增加了超时重试..."

    Commands:
        /semdiff — explain current git diff
        /semdiff <branch> — explain diff vs another branch
        /semdiff <commit>..<commit> — explain diff between commits
"""
from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger


@dataclass
class DiffExplanation:
    summary: str = ""
    changes: list[dict] = field(default_factory=list)  # [{file, what, why}]
    affected_files: list[str] = field(default_factory=list)
    risk_level: str = "low"  # low, medium, high
    recommendation: str = ""


class SemanticDiff:
    """LLM-powered diff explanation engine."""

    async def explain_diff(
        self,
        hub,
        target: str = "",  # branch, commit range, or empty for unstaged
        max_lines: int = 500,
    ) -> DiffExplanation:
        """Explain git diff in natural language.

        Args:
            hub: LLM access
            target: "origin/master..HEAD", "HEAD~3..HEAD", or "" for unstaged
            max_lines: Max diff lines to analyze
        """
        if not hub or not hub.world:
            return DiffExplanation(summary="LLM unavailable")

        # Get diff
        diff_text = self._get_diff(target, max_lines)
        if not diff_text.strip():
            return DiffExplanation(summary="No changes detected")

        affected = self._parse_files(diff_text)
        result = DiffExplanation(affected_files=affected)

        llm = hub.world.consciousness._llm
        try:
            resp = await llm.chat(
                messages=[{"role": "user", "content": (
                    "Explain this code diff in plain language. "
                    "Focus on WHAT changed and WHY it matters.\n\n"
                    "DIFF:\n```diff\n" + diff_text[:8000] + "\n```\n\n"
                    "Output JSON:\n"
                    '{"summary": "one-paragraph human-readable summary of all changes", '
                    '"changes": [{"file": "path.py", "what": "description of change", '
                    '"why": "likely reason"}, ...], '
                    '"risk_level": "low|medium|high", '
                    '"recommendation": "one-line advice for reviewer"}'
                )}],
                provider=getattr(llm, '_elected', ''),
                temperature=0.2, max_tokens=800, timeout=30,
            )

            if resp and resp.text:
                import json, re
                m = re.search(r'\{[\s\S]*\}', resp.text)
                if m:
                    d = json.loads(m.group())
                    result.summary = d.get("summary", "")[:1000]
                    result.changes = d.get("changes", [])[:10]
                    result.risk_level = d.get("risk_level", "low")
                    result.recommendation = d.get("recommendation", "")[:200]
        except Exception as e:
            logger.debug(f"SemanticDiff: {e}")
            result.summary = f"Diff analysis failed: {e}"

        return result

    async def explain_commit(self, hub, commit: str) -> DiffExplanation:
        """Explain a single commit in plain language."""
        return await self.explain_diff(hub, target=f"{commit}~1..{commit}")

    async def explain_file(self, hub, filepath: str, target: str = "") -> DiffExplanation:
        """Explain changes to a specific file."""
        diff_text = self._get_diff(target, 300, filepath)
        if not diff_text.strip():
            return DiffExplanation(summary=f"No changes in {filepath}")
        return await self.explain_diff(hub, target=target)

    def _get_diff(self, target: str = "", max_lines: int = 500, filepath: str = "") -> str:
        """Run git diff and return output."""
        import asyncio
        cmd_parts = ["diff"]
        if target:
            cmd_parts.append(target)
        if filepath:
            cmd_parts.extend(["--", filepath])
        args = " ".join(cmd_parts)

        try:
            try:
                from ..treellm.unified_exec import git
                result = asyncio.run(git(args, timeout=15))
                diff_output = result.stdout
            except ImportError:
                cmd = ["git", "diff"]
                if target:
                    cmd.append(target)
                if filepath:
                    cmd.extend(["--", filepath])
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=15,
                                        encoding="utf-8", errors="replace")
                diff_output = result.stdout

            lines = diff_output.splitlines()
            if len(lines) > max_lines:
                return "\n".join(lines[:max_lines]) + f"\n... ({len(lines) - max_lines} more lines)"
            return diff_output
        except Exception as e:
            return str(e)

    def _parse_files(self, diff_text: str) -> list[str]:
        import re
        files = set()
        for m in re.finditer(r'^[+]{3} b/(.+)', diff_text, re.MULTILINE):
            f = m.group(1).strip()
            if f and f != "/dev/null":
                files.add(f)
        return list(files)[:20]

    def format(self, explanation: DiffExplanation) -> str:
        """Format explanation for display."""
        lines = [f"## 📊 语义差异分析", "", f"**风险等级:** {explanation.risk_level}", ""]
        if explanation.summary:
            lines.append(f"{explanation.summary}")
        if explanation.changes:
            lines.append("")
            for c in explanation.changes:
                lines.append(f"- **{c.get('file', '')}**")
                lines.append(f"  {c.get('what', '')}")
                if c.get("why"):
                    lines.append(f"  [dim]原因: {c['why']}[/dim]")
        if explanation.recommendation:
            lines.append(f"\n💡 {explanation.recommendation}")
        return "\n".join(lines)


_sd: SemanticDiff | None = None


def get_semantic_diff() -> SemanticDiff:
    global _sd
    if _sd is None:
        _sd = SemanticDiff()
    return _sd
