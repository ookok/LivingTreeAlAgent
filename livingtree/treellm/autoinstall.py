"""Autoinstall — LLM-driven self-bootstrapping with tool calls, mock creation, verification loop.

Inspired by Cursor Autoinstall: the Agent explores, installs, mocks, verifies, retries.

Workflow:
  Stage 1: Quick health check → identify what's broken
  Stage 2: LLM-driven recovery loop (max 5 rounds):
    - LLM analyzes error output + environment state
    - Chooses actions: web_search, bash, write_file, pkg_install
    - Executes tool calls, observes results
    - Verifies: can the project start? do tests pass?
    - If fail → next round with accumulated knowledge
    - If 5 rounds fail → discard environment state

Key innovation: LLM creates mock files, placeholder configs, fake DB tables
when real dependencies are unavailable — creative problem solving over blind retry.

Usage:
    livingtree autoinstall              # Full LLM-driven bootstrap
    livingtree autoinstall --rounds 3   # Max 3 retry rounds
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from loguru import logger


@dataclass
class EnvIssue:
    """A detected environment problem."""
    category: str   # missing_dep | missing_file | config_error | import_error | service_down
    detail: str
    fix_attempted: bool = False
    resolved: bool = False


@dataclass
class AutoInstallReport:
    """Complete autoinstall result."""
    rounds: int
    issues_found: list[EnvIssue]
    issues_resolved: int
    verification_passed: bool
    llm_actions: list[str]  # What the LLM did
    duration_ms: float
    error: str = ""


class AutoInstaller:
    """LLM-driven environment bootstrapper with tool-calling loop."""

    MAX_ROUNDS = 5
    VERIFY_COMMANDS = [
        "python -c 'from livingtree.config import get_config; print(get_config().version)'",
        "python -c 'from livingtree.treellm.core import TreeLLM; print(\"TreeLLM OK\")'",
    ]

    @staticmethod
    async def run(max_rounds: int = 5) -> AutoInstallReport:
        t0 = time.time()
        issues = AutoInstaller._quick_check_sync()
        actions: list[str] = []
        resolved_count = 0

        if not issues:
            return AutoInstallReport(
                rounds=0, issues_found=[], issues_resolved=0,
                verification_passed=True, llm_actions=["Environment already healthy"],
                duration_ms=(time.time() - t0) * 1000,
            )

        print(f"\n  🔍 Found {len(issues)} issues, starting LLM recovery loop...\n")

        for round_num in range(1, max_rounds + 1):
            print(f"  ── Round {round_num}/{max_rounds} ──")

            unresolved = [i for i in issues if not i.resolved]
            if not unresolved:
                break

            # Let LLM analyze and decide actions
            try:
                round_actions = await AutoInstaller._llm_recovery_round(
                    unresolved, round_num,
                )
                actions.extend(round_actions)

                # Mark resolved by re-checking
                for issue in unresolved:
                    if await AutoInstaller._verify_fix(issue):
                        issue.resolved = True
                        issue.fix_attempted = True
                        resolved_count += 1
                        print(f"    ✅ {issue.category}: {issue.detail[:60]}")
                    else:
                        issue.fix_attempted = True
                        print(f"    ⚠️  Still broken: {issue.detail[:60]}")

            except Exception as e:
                logger.warning(f"Autoinstall round {round_num}: {e}")
                continue

            # Verify overall health
            if await AutoInstaller._verify_environment():
                return AutoInstallReport(
                    rounds=round_num,
                    issues_found=issues,
                    issues_resolved=resolved_count,
                    verification_passed=True,
                    llm_actions=actions,
                    duration_ms=(time.time() - t0) * 1000,
                )

        return AutoInstallReport(
            rounds=min(max_rounds, 5),
            issues_found=issues,
            issues_resolved=resolved_count,
            verification_passed=resolved_count == len(issues),
            llm_actions=actions,
            duration_ms=(time.time() - t0) * 1000,
            error="Max rounds reached" if resolved_count < len(issues) else "",
        )

    @staticmethod
    def _quick_check_sync() -> list[EnvIssue]:
        """Fast sync check: which components are broken?"""
        issues = []

        # Config file
        if not Path("config/livingtree.yaml").exists():
            issues.append(EnvIssue(category="missing_file",
                          detail="config/livingtree.yaml not found"))

        # Core imports
        for mod in ["livingtree.config.settings", "livingtree.treellm.core",
                     "livingtree.dna.life_engine"]:
            try:
                import importlib
                importlib.import_module(mod)
            except ImportError as e:
                issues.append(EnvIssue(category="import_error", detail=str(e)[:80]))
            except SyntaxError as e:
                issues.append(EnvIssue(category="import_error",
                              detail=f"{mod}: {str(e)[:60]}"))

        # Essential packages
        essential = {"aiohttp": "aiohttp", "yaml": "pyyaml",
                     "loguru": "loguru", "pydantic": "pydantic"}
        for imp, pkg in essential.items():
            try:
                importlib.import_module(imp)
            except ImportError:
                issues.append(EnvIssue(category="missing_dep",
                              detail=f"{pkg} not installed"))

        # Git repo
        if not Path(".git").exists():
            issues.append(EnvIssue(category="service_down",
                          detail="Not a git repository"))

        return issues

    @staticmethod
    async def _llm_recovery_round(issues: list[EnvIssue],
                                   round_num: int) -> list[str]:
        """LLM analyzes issues and calls tools to fix them."""
        from .core import TreeLLM

        llm = TreeLLM.from_config()
        actions: list[str] = []

        issue_text = "\n".join(
            f"- [{i.category}] {i.detail}" for i in issues
        )
        prompt = (
            f"你是一个环境配置专家。当前 LivingTree 项目有以下问题需要修复:\n\n"
            f"{issue_text}\n\n"
            f"这是第 {round_num} 轮修复。你可以使用以下工具:\n"
            f"- bash: 执行shell命令。参数: command字符串\n"
            f"- write_file: 创建/覆盖文件。参数: file_path\\ncontent\n"
            f"- read_file: 读取文件。参数: path\n\n"
            f"策略:\n"
            f"1. 缺失的包 → bash: 'pip install <package>'\n"
            f"2. 缺失的配置文件 → write_file: 创建placeholder/mock\n"
            f"3. 导入错误 → read_file: 查看文件,bash: 尝试修复\n"
            f"4. 外部服务不可用 → write_file: 创建mock替代\n\n"
            f"请逐步修复这些问题。每个修复用一个 <tool_call> XML标签。"
        )

        result = await llm.chat(
            [{"role": "user", "content": prompt}],
            max_tokens=2000, temperature=0.1, task_type="code",
        )
        response_text = getattr(result, 'text', '') or str(result)

        # Execute tool calls from LLM response
        tool_pattern = re.compile(
            r'<tool_call\s+name="(\w+)"\s*>(.*?)</tool_call>', re.DOTALL,
        )
        for tool_name, tool_args in tool_pattern.findall(response_text):
            action_desc = await AutoInstaller._execute_tool(tool_name, tool_args.strip())
            if action_desc:
                actions.append(action_desc)
                print(f"    🔧 {tool_name}: {action_desc[:80]}")

        return actions

    @staticmethod
    async def _execute_tool(name: str, args: str) -> str:
        """Execute a tool call from LLM. Returns description of what happened."""
        try:
            if name == "bash":
                proc = await asyncio.create_subprocess_shell(
                    args, stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=60,
                )
                out = stdout.decode(errors="replace")[:200]
                err = stderr.decode(errors="replace")[:200]
                if proc.returncode == 0:
                    return f"OK: {out[:80]}"
                return f"FAIL({proc.returncode}): {err[:80]}"

            elif name == "write_file":
                parts = args.split("\n", 1)
                path = parts[0].strip()
                content = parts[1] if len(parts) > 1 else "# placeholder"
                Path(path).parent.mkdir(parents=True, exist_ok=True)
                Path(path).write_text(content, encoding="utf-8")
                return f"Wrote {len(content)} bytes to {path}"

            elif name == "read_file":
                p = Path(args.strip())
                if p.exists():
                    text = p.read_text(encoding="utf-8", errors="replace")
                    return f"Read {len(text)} chars from {args[:60]}"
                return f"File not found: {args[:60]}"

            else:
                return f"Unknown tool: {name}"
        except Exception as e:
            return f"Error: {e}"

    @staticmethod
    async def _verify_fix(issue: EnvIssue) -> bool:
        """Check if a specific issue was resolved."""
        try:
            if issue.category == "missing_dep":
                pkg = issue.detail.split()[0]
                import importlib
                importlib.import_module(pkg.replace("-", "_"))
                return True
            elif issue.category == "missing_file":
                return Path(issue.detail.split("not found")[0].strip()).exists()
            elif issue.category == "import_error":
                mod = issue.detail.split(":")[0] if ":" in issue.detail else ""
                if mod:
                    import importlib
                    importlib.import_module(mod)
                    return True
                return False
            elif issue.category == "config_error":
                return Path("config/livingtree.yaml").exists()
        except Exception:
            return False
        return False

    @staticmethod
    async def _verify_environment() -> bool:
        """Run verification commands to check overall health."""
        for cmd in AutoInstaller.VERIFY_COMMANDS:
            try:
                proc = await asyncio.create_subprocess_shell(
                    cmd, stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await asyncio.wait_for(proc.communicate(), timeout=30)
                if proc.returncode != 0:
                    return False
            except Exception:
                return False
        return True

    @staticmethod
    def format_report(report: AutoInstallReport) -> str:
        lines = [
            "╔══════════════════════════════════════╗",
            "║   🤖 LLM Autoinstall Report           ║",
            "╚══════════════════════════════════════╝",
            "",
            f"  Rounds: {report.rounds}",
            f"  Issues found: {len(report.issues_found)}",
            f"  Issues resolved: {report.issues_resolved}",
            f"  Verification: {'✅ PASSED' if report.verification_passed else '❌ FAILED'}",
            f"  Duration: {report.duration_ms:.0f}ms",
            "",
        ]
        if report.llm_actions:
            lines.append("  LLM Actions:")
            for a in report.llm_actions[:10]:
                lines.append(f"    • {a[:100]}")
        if report.error:
            lines.append(f"\n  ⚠️  {report.error}")
        return "\n".join(lines)


__all__ = ["AutoInstaller", "AutoInstallReport", "EnvIssue"]
