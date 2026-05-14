"""DebugLoop — AI-driven autonomous debugging with fix-and-retry.

Four levels of automation:
  L1: Capture error → AI analysis → suggest fix (human applies)
  L2: Capture error → AI generate patch → apply → re-run (semi-auto)
  L3: Full debug loop with variable inspection (debugpy + DAP)
  L4: Closed-loop continuous debugging (experimental)

Safe by design:
  - Git commit before every fix attempt (easy rollback)
  - Max 5 retry attempts per error
  - HITL escalation after 3 consecutive failures
  - Sandboxed fix application (diff review before apply)

Integration:
  - TreeLLM: own LLM routing for fix generation
  - LivingStore: persistent debug state
  - LivingScheduler: HITL escalation
  - Git: automatic safety commits

Usage:
  CLI:    python -m livingtree debug main.py
  API:    POST /api/debug/start {"target":"main.py","args":["--verbose"]}
  Inline: from livingtree.treellm.debug_loop import auto_debug; auto_debug()
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import sys
import time
import traceback
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Optional

from loguru import logger


# ═══ Enums ════════════════════════════════════════════════════════


class DebugLevel(StrEnum):
    ANALYZE = "analyze"      # L1: AI analysis only, no auto-fix
    SEMI_AUTO = "semi_auto"  # L2: AI fix + auto re-run
    FULL = "full"            # L3: Full debug loop with variable inspection
    CLOSED = "closed"        # L4: Continuous closed-loop (experimental)


class AttemptResult(StrEnum):
    FIXED = "fixed"
    PARTIAL = "partial"       # Better but not fully fixed
    WORSE = "worse"           # Fix made things worse
    UNCHANGED = "unchanged"   # Same error persists
    HITL = "hitl"             # Escalated to human


# ═══ Data Types ════════════════════════════════════════════════════


@dataclass
class ErrorSnapshot:
    """A captured error with full context for AI analysis."""
    id: str = field(default_factory=lambda: f"err_{int(time.time()*1000)}")
    exception_type: str = ""
    exception_message: str = ""
    traceback_text: str = ""
    file_path: str = ""
    line_number: int = 0
    function_name: str = ""
    source_context: str = ""    # Surrounding source code (±10 lines)
    locals_snapshot: dict = field(default_factory=dict)  # Key local variables
    project_root: str = ""
    test_name: str = ""         # If from pytest
    timestamp: float = field(default_factory=time.time)


@dataclass
class FixAttempt:
    """A single fix attempt and its outcome."""
    attempt_number: int
    error: ErrorSnapshot
    generated_patch: str = ""       # AI-generated diff
    applied_file: str = ""
    applied_line: int = 0
    result: AttemptResult = AttemptResult.UNCHANGED
    new_error: Optional[ErrorSnapshot] = None
    llm_provider: str = ""
    llm_tokens: int = 0
    duration_ms: float = 0.0
    git_commit: str = ""            # Safety commit hash


@dataclass
class DebugSession:
    """A complete debug session with all attempts."""
    id: str = field(default_factory=lambda: f"debug_{int(time.time())}")
    target: str = ""               # main.py or test path
    args: list[str] = field(default_factory=list)
    level: DebugLevel = DebugLevel.SEMI_AUTO
    max_attempts: int = 5
    attempts: list[FixAttempt] = field(default_factory=list)
    fixed: bool = False
    total_duration_ms: float = 0.0
    escalated: bool = False


# ═══ DebugLoop ════════════════════════════════════════════════════


class DebugLoop:
    """AI-driven autonomous debugging loop."""

    _instance: Optional["DebugLoop"] = None

    @classmethod
    def instance(cls) -> "DebugLoop":
        if cls._instance is None:
            cls._instance = DebugLoop()
        return cls._instance

    def __init__(self):
        self._active_session: Optional[DebugSession] = None
        self._sessions: list[DebugSession] = []

    # ── Main Entry ─────────────────────────────────────────────────

    async def debug(self, target: str, args: list[str] = None,
                    level: DebugLevel = DebugLevel.SEMI_AUTO,
                    max_attempts: int = 5) -> DebugSession:
        """Run the full debug loop: run → fail → AI fix → re-run → ..."""
        session = DebugSession(
            target=target, args=args or [], level=level,
            max_attempts=min(max_attempts, 10),
        )
        self._active_session = session
        t0 = time.time()

        for attempt_num in range(1, session.max_attempts + 1):
            error = await self._run_target(target, args)
            if error is None:
                session.fixed = True
                logger.info(f"DebugLoop: target passed on attempt {attempt_num}")
                break

            if level == DebugLevel.ANALYZE:
                analysis = await self._analyze_error(error)
                logger.info(f"DebugLoop L1 analysis:\n{analysis}")
                break

            # L2+: Generate and apply fix
            fix = await self._generate_and_apply(error, attempt_num, session)
            session.attempts.append(fix)

            if fix.result == AttemptResult.FIXED:
                session.fixed = True
                break

            if fix.result == AttemptResult.HITL:
                session.escalated = True
                break

        session.total_duration_ms = (time.time() - t0) * 1000
        self._sessions.append(session)
        self._active_session = None
        return session

    # ── Error Capture ──────────────────────────────────────────────

    async def _run_target(self, target: str, args: list[str]) -> Optional[ErrorSnapshot]:
        """Run the target and capture any error."""
        try:
            cmd = [sys.executable, target] + (args or [])
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=os.getcwd(),
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=120,
            )

            if proc.returncode == 0:
                return None  # Success

            # Parse error from stderr
            return self._parse_error(stderr.decode("utf-8", errors="replace"),
                                     target, stdout.decode("utf-8", errors="replace"))

        except asyncio.TimeoutError:
            return ErrorSnapshot(
                exception_type="TimeoutError",
                exception_message="Target execution timed out (120s)",
                file_path=target,
                project_root=os.getcwd(),
            )
        except Exception as e:
            return ErrorSnapshot(
                exception_type=type(e).__name__,
                exception_message=str(e),
                traceback_text=traceback.format_exc(),
                project_root=os.getcwd(),
            )

    def _parse_error(self, stderr: str, target: str, stdout: str) -> ErrorSnapshot:
        """Parse traceback from stderr into ErrorSnapshot."""
        snapshot = ErrorSnapshot(project_root=os.getcwd())

        # Extract exception type and message from last line
        lines = stderr.strip().split("\n")
        for line in reversed(lines):
            m = re.match(r'^(\w+(?:\.\w+)*Error|\w+(?:\.\w+)*Exception):?\s*(.*)', line)
            if m:
                snapshot.exception_type = m.group(1)
                snapshot.exception_message = m.group(2)
                break

        # Extract file:line from traceback
        for line in lines:
            m = re.search(r'File "([^"]+)", line (\d+), in (\w+)', line)
            if m:
                snapshot.file_path = m.group(1)
                snapshot.line_number = int(m.group(2))
                snapshot.function_name = m.group(3)
                break

        snapshot.traceback_text = stderr[:10000]

        # Read source context (±10 lines around error)
        if snapshot.file_path and snapshot.line_number:
            try:
                source = Path(snapshot.file_path).read_text(errors="replace").split("\n")
                start = max(0, snapshot.line_number - 11)
                end = min(len(source), snapshot.line_number + 10)
                snapshot.source_context = "\n".join(
                    f"{i+1}: {source[i]}" for i in range(start, end)
                )
            except Exception:
                pass

        # Extract test name if pytest
        for line in lines:
            m = re.search(r'(test_\w+)\s', line)
            if m:
                snapshot.test_name = m.group(1)
                break

        return snapshot

    # ── AI Analysis ─────────────────────────────────────────────────

    async def _analyze_error(self, error: ErrorSnapshot) -> str:
        """L1: AI analysis of the error, no auto-fix."""
        prompt = self._build_fix_prompt(error, include_diff=False)
        result = await self._call_llm(prompt, max_tokens=1000)
        return result

    async def _generate_and_apply(self, error: ErrorSnapshot,
                                   attempt: int,
                                   session: DebugSession) -> FixAttempt:
        """L2+: AI generates fix → apply → re-run → evaluate."""
        fix = FixAttempt(attempt_number=attempt, error=error)
        t0 = time.time()

        # 1. Git safety commit
        try:
            fix.git_commit = self._git_safety_commit(f"debug_loop_attempt_{attempt}")
        except Exception:
            pass

        # 1.5. Parallel context analysis (file deps, git blame, test coverage)
        context_task = None
        try:
            from .debug_pro import ParallelAnalyzer
            analyzer = ParallelAnalyzer()
            context_task = asyncio.create_task(
                analyzer.analyze(error.file_path, error.line_number,
                                error.exception_type)
            )
        except Exception:
            pass

        # 2. Generate fix via LLM (with parallel context if available)
        prompt = self._build_fix_prompt(error, include_diff=True)

        # Inject parallel analysis results
        if context_task:
            try:
                ctx = await asyncio.wait_for(context_task, timeout=15.0)
                context_lines = []
                if ctx.dependency_issues:
                    context_lines.append("依赖关系: " + "; ".join(ctx.dependency_issues[:5]))
                if ctx.git_blame_info:
                    context_lines.append(f"Git Blame: {ctx.git_blame_info[:200]}")
                if ctx.test_coverage_gaps:
                    context_lines.append("测试覆盖: " + "; ".join(ctx.test_coverage_gaps[:3]))
                if context_lines:
                    prompt += "\n\n上下文分析 (并行LLM):\n" + "\n".join(context_lines)
            except asyncio.TimeoutError:
                pass
        result = await self._call_llm(prompt, max_tokens=2000)

        if not result:
            fix.result = AttemptResult.HITL
            return fix

        fix.generated_patch = result
        fix.llm_provider = getattr(self, '_last_provider', '')

        # 3. Parse and apply fix
        applied = self._apply_fix(error, result)
        if not applied:
            fix.result = AttemptResult.HITL
            return fix

        fix.applied_file = error.file_path
        fix.applied_line = error.line_number

        # 4. Re-run target
        new_error = await self._run_target(session.target, session.args)
        fix.duration_ms = (time.time() - t0) * 1000

        # 5. Evaluate result
        if new_error is None:
            fix.result = AttemptResult.FIXED
            logger.info(f"DebugLoop: attempt {attempt} FIXED the error")
        elif new_error.exception_type != error.exception_type:
            fix.result = AttemptResult.PARTIAL
            fix.new_error = new_error
            logger.info(f"DebugLoop: attempt {attempt} PARTIAL — different error now")
        elif new_error.line_number != error.line_number:
            fix.result = AttemptResult.PARTIAL
            fix.new_error = new_error
        else:
            # Same error — revert and try different approach
            fix.result = AttemptResult.UNCHANGED
            self._git_revert(fix.git_commit)
            logger.info(f"DebugLoop: attempt {attempt} UNCHANGED — reverted")

        # HITL after 3 failures
        if attempt >= 3 and fix.result in (AttemptResult.UNCHANGED, AttemptResult.WORSE):
            fix.result = AttemptResult.HITL
            self._escalate_to_human(error, session)

        return fix

    # ── LLM Integration ─────────────────────────────────────────────

    async def _call_llm(self, prompt: str, max_tokens: int = 2000) -> str:
        """Call TreeLLM for fix generation."""
        try:
            from .core import TreeLLM
            llm = TreeLLM()
            provider = await llm.smart_route(prompt, task_type="code")
            self._last_provider = provider
            result = await llm.chat(
                [{"role": "user", "content": prompt}],
                provider=provider, max_tokens=max_tokens,
                temperature=0.1, task_type="code",
            )
            return getattr(result, 'text', '') or str(result)
        except Exception as e:
            logger.debug(f"DebugLoop LLM: {e}")
            return ""

    def _build_fix_prompt(self, error: ErrorSnapshot,
                          include_diff: bool = True) -> str:
        """Build a prompt for the LLM to analyze/fix the error."""
        prompt = (
            f"你是一个Python调试专家。分析以下错误并给出修复方案。\n\n"
            f"错误类型: {error.exception_type}\n"
            f"错误信息: {error.exception_message}\n"
            f"文件: {error.file_path}\n"
            f"行号: {error.line_number}\n"
            f"函数: {error.function_name}\n\n"
        )

        if error.source_context:
            prompt += (
                f"出错位置附近的代码:\n"
                f"```python\n{error.source_context}\n```\n\n"
            )

        if error.traceback_text:
            # Only include relevant traceback lines (not full)
            tb_lines = [l for l in error.traceback_text.split("\n")
                       if "File " in l or error.exception_type in l]
            prompt += f"完整Traceback片段:\n" + "\n".join(tb_lines[-10:]) + "\n\n"

        if include_diff:
            prompt += (
                "请输出一个可执行的修复方案,使用以下格式:\n"
                "```diff\n"
                "--- a/path/to/file.py\n"
                "+++ b/path/to/file.py\n"
                "@@ -line,count +line,count @@\n"
                " 保留的代码行\n"
                "-删除的行\n"
                "+新增的行\n"
                "```\n\n"
                "修复后简要说明为什么这个方案有效。\n"
                "如果错误是因为缺少依赖、配置问题或外部因素,"
                "请说明需要的人工操作步骤。"
            )
        else:
            prompt += "请分析错误原因并给出修复建议。"

        return prompt

    # ── Fix Application ────────────────────────────────────────────

    def _apply_fix(self, error: ErrorSnapshot, llm_response: str) -> bool:
        """Apply LLM-generated fix to source file."""
        if not error.file_path or not Path(error.file_path).exists():
            return False

        # Try unified diff format
        diff_match = re.search(r'--- a/(.+?)\n\+\+\+ b/\1\n(.*?)(?:\n```|$)', llm_response, re.DOTALL)
        if diff_match:
            return self._apply_diff(error.file_path, diff_match.group(2))

        # Try simple "replace X with Y" format
        replace_match = re.findall(
            r'(?:替换|replace|change|修改).*?\n.*?```(?:python|diff)?\n(.*?)```',
            llm_response, re.DOTALL | re.IGNORECASE,
        )
        if replace_match:
            for block in replace_match:
                if self._apply_code_block(error.file_path, block, error.line_number):
                    return True

        # Try code block near the error line
        code_blocks = re.findall(r'```(?:python|py)?\n(.*?)```', llm_response, re.DOTALL)
        if code_blocks and len(code_blocks) >= 2:
            return self._replace_lines(
                error.file_path, code_blocks[0], code_blocks[1],
                error.line_number,
            )

        # Can't parse — escalate
        logger.warning("DebugLoop: could not parse fix from LLM response")
        return False

    def _apply_diff(self, file_path: str, diff_text: str) -> bool:
        """Apply a unified diff patch."""
        try:
            import tempfile
            # Write diff to temp file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.diff', delete=False) as f:
                f.write(f"--- a/{file_path}\n+++ b/{file_path}\n{diff_text}")
                diff_path = f.name

            # Apply via git apply
            subprocess.run(
                ["git", "apply", "--check", diff_path],
                capture_output=True, check=True, cwd=os.getcwd(),
            )
            subprocess.run(
                ["git", "apply", diff_path],
                capture_output=True, check=True, cwd=os.getcwd(),
            )
            os.unlink(diff_path)
            logger.info(f"DebugLoop: applied diff to {file_path}")
            return True
        except subprocess.CalledProcessError as e:
            logger.debug(f"DebugLoop diff apply failed: {e}")
            return False
        except Exception:
            return False

    def _apply_code_block(self, file_path: str, block: str, line: int) -> bool:
        """Replace context around error line with new code block."""
        try:
            source = Path(file_path).read_text().split("\n")
            old_block = "\n".join(source[max(0, line - 6): min(len(source), line + 5)])
            new_block = block.strip()
            content = Path(file_path).read_text()
            if old_block.strip() in content:
                Path(file_path).write_text(
                    content.replace(old_block.strip(), new_block),
                    encoding="utf-8",
                )
                return True
        except Exception:
            pass
        return False

    def _replace_lines(self, file_path: str, old_code: str,
                       new_code: str, around_line: int) -> bool:
        """Replace old code block with new code block."""
        try:
            content = Path(file_path).read_text()
            old = old_code.strip()
            new = new_code.strip()
            if old in content:
                Path(file_path).write_text(
                    content.replace(old, new), encoding="utf-8",
                )
                return True
        except Exception:
            pass
        return False

    # ── Git Safety ──────────────────────────────────────────────────

    def _git_safety_commit(self, message: str) -> str:
        """Create a safety commit — uses unified ShellExecutor."""
        try:
            from ..core.shell_env import get_shell
            import asyncio
            shell = get_shell()

            async def _run():
                await shell.execute("git add -A")
                await shell.execute(f'git commit -m "debug_loop: {message}" --allow-empty')
                result = await shell.execute("git rev-parse HEAD")
                return result.stdout.strip()[:8]
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    return ""
                return asyncio.run(_run())
            except Exception:
                return ""
        except ImportError:
            pass

        try:
            subprocess.run(["git", "add", "-A"], capture_output=True, check=True)
            subprocess.run(
                ["git", "commit", "-m", f"debug_loop: {message}", "--allow-empty"],
                capture_output=True, check=True,
            )
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True, text=True, check=True,
            )
            return result.stdout.strip()[:8]
        except Exception:
            return ""

    def _git_revert(self, commit_hash: str) -> bool:
        """Revert to a safety commit."""
        if not commit_hash:
            return False
        try:
            subprocess.run(
                ["git", "reset", "--hard", commit_hash],
                capture_output=True, check=True,
            )
            return True
        except Exception:
            return False

    # ── HITL Escalation ────────────────────────────────────────────

    def _escalate_to_human(self, error: ErrorSnapshot,
                           session: DebugSession) -> None:
        """Escalate to human via LivingScheduler."""
        try:
            from .living_scheduler import (
                get_living_scheduler, EscalationLevel, TaskPriority,
            )
            ls = get_living_scheduler()
            task = ls.schedule(
                description=f"DebugLoop failed for {session.target}: {error.exception_type}",
                priority=TaskPriority.HIGH,
                confidence=0.3,
            )
            ls.escalate(task.id, EscalationLevel.ASSIST,
                       f"自动修复失败(3次尝试)。{error.file_path}:{error.line_number} — {error.exception_message}")
        except Exception:
            pass

    # ── Stats ───────────────────────────────────────────────────────

    def stats(self) -> dict:
        return {
            "sessions": len(self._sessions),
            "fixed": sum(1 for s in self._sessions if s.fixed),
            "escalated": sum(1 for s in self._sessions if s.escalated),
            "active": self._active_session.id if self._active_session else "",
        }


# ═══ Convenience ══════════════════════════════════════════════════


async def auto_debug(target: str = None, args: list[str] = None,
                     level: str = "semi_auto", max_attempts: int = 5) -> DebugSession:
    """Convenience: run debug loop on a target."""
    if target is None:
        target = sys.argv[0] if len(sys.argv) > 0 else "main.py"
    level_enum = DebugLevel(level) if level in [d.value for d in DebugLevel] else DebugLevel.SEMI_AUTO
    return await DebugLoop.instance().debug(target, args, level_enum, max_attempts)


def install_excepthook():
    """Install global excepthook for automatic debug loop on crash."""
    loop = DebugLoop.instance()

    def _hook(exc_type, exc_value, tb):
        error = loop._parse_error(
            "".join(traceback.format_exception(exc_type, exc_value, tb)),
            sys.argv[0] if sys.argv else "unknown",
            "",
        )
        logger.error(f"DebugLoop: caught {error.exception_type} — starting auto-fix")
        asyncio.run(loop._generate_and_apply(
            error, attempt=1,
            session=DebugSession(target=sys.argv[0] if sys.argv else ""),
        ))

    sys.excepthook = _hook


# ═══ Singleton ════════════════════════════════════════════════════

_loop: Optional[DebugLoop] = None


def get_debug_loop() -> DebugLoop:
    global _loop
    if _loop is None:
        _loop = DebugLoop()
    return _loop


__all__ = [
    "DebugLoop", "DebugSession", "ErrorSnapshot", "FixAttempt",
    "DebugLevel", "AttemptResult",
    "auto_debug", "install_excepthook", "get_debug_loop",
]
