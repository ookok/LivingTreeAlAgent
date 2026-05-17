"""Developer tools — expose full dev toolkit to LLM via tool calls.

P0: list_dir, grep_code
P1: git_status, git_diff, git_commit, git_push, git_branch, run_test
P2: browser_fetch (expose existing capability)
P3: notify_slack, notify_feishu, notify_dingtalk

All tools return plain text output — LLM-friendly, no JSON wrapping needed.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from loguru import logger


# ═══ P0: File & Code Operations ═══

def list_dir(path: str = ".") -> str:
    """List directory contents with file sizes and types."""
    p = Path(path)
    if not p.exists():
        return f"Path not found: {path}"
    if not p.is_dir():
        return f"Not a directory: {path}"

    lines = [f"{p.absolute()} ({'directory' if p.is_dir() else 'file'})"]
    try:
        items = sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
        for item in items[:50]:
            suffix = "/" if item.is_dir() else ""
            try:
                size = item.stat().st_size
                if size > 1024 * 1024:
                    size_str = f"{size / (1024 * 1024):.1f}MB"
                elif size > 1024:
                    size_str = f"{size / 1024:.0f}KB"
                else:
                    size_str = f"{size}B"
            except Exception:
                size_str = "?"
            lines.append(f"  {size_str:>8}  {item.name}{suffix}")
        if len(items) > 50:
            lines.append(f"  ... ({len(items) - 50} more items)")
    except PermissionError:
        lines.append("  [Permission denied]")

    return "\n".join(lines)


def grep_code(pattern: str, path: str = ".", glob: str = "*.py") -> str:
    """Search codebase for pattern using ripgrep or Python fallback."""
    try:
        # Try ripgrep first (fast)
        result = subprocess.run(
            ["rg", "--no-heading", "-n", "--max-count", "20", pattern, "-g", glob, path],
            capture_output=True, text=True, timeout=10, cwd=str(Path.cwd()),
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout[:8000]
        if result.returncode == 1:
            return f"No matches for '{pattern}' in {path}/{glob}"
    except (FileNotFoundError, Exception):
        pass

    # Python fallback
    lines = []
    p = Path(path)
    if not p.exists():
        return f"Path not found: {path}"
    for f in p.rglob(glob):
        try:
            content = f.read_text(encoding="utf-8", errors="replace")
            for i, line in enumerate(content.split("\n"), 1):
                if pattern.lower() in line.lower():
                    lines.append(f"{f}:{i}: {line.strip()[:200]}")
                    if len(lines) >= 30:
                        break
            if len(lines) >= 30:
                break
        except Exception:
            continue

    if not lines:
        return f"No matches for '{pattern}' in {path}/{glob}"
    return "\n".join(lines)


# ═══ P1: Git Operations ═══

def _run_git(args: str, timeout: float = 30) -> str:
    try:
        result = subprocess.run(
            f"git {args}", shell=True, capture_output=True, text=True,
            timeout=timeout, cwd=str(Path.cwd()),
        )
        output = result.stdout.strip() or result.stderr.strip()
        return output[:5000] if output else "(no output)"
    except subprocess.TimeoutExpired:
        return "Git command timed out"
    except Exception as e:
        return f"Git error: {e}"


def git_status() -> str:
    """Show working tree status."""
    return _run_git("status --short --branch")


def git_diff(file: str = "") -> str:
    """Show working tree changes. Optional: specific file."""
    target = f"-- {file}" if file else ""
    return _run_git(f"diff --stat {target}")


def git_commit(message: str) -> str:
    """Stage all changes and commit with message."""
    _run_git("add -A")
    return _run_git(f'commit -m "{message}"', timeout=60)


def git_push() -> str:
    """Push current branch to remote."""
    return _run_git("push", timeout=60)


def git_branch(action: str = "list", name: str = "") -> str:
    """Branch management: list, create <name>, switch <name>."""
    if action == "list":
        return _run_git("branch -a")
    elif action == "create" and name:
        return _run_git(f"checkout -b {name}")
    elif action == "switch" and name:
        return _run_git(f"checkout {name}")
    return "Usage: git_branch list|create|switch <name>"


def run_test(test_path: str = "tests/") -> str:
    """Run pytest and return results."""
    try:
        result = subprocess.run(
            ["python", "-m", "pytest", test_path, "-q", "--tb=short"],
            capture_output=True, text=True, timeout=120, cwd=str(Path.cwd()),
        )
        return (result.stdout + result.stderr)[:5000]
    except subprocess.TimeoutExpired:
        return "Tests timed out (120s)"
    except FileNotFoundError:
        return "pytest not installed"
    except Exception as e:
        return f"Test error: {e}"


# ═══ P2: Browser Fetch ═══

async def browser_fetch(url: str, task: str = "extract main content") -> str:
    """Open a URL in headless browser and perform a task."""
    try:
        from ..capability.browser_agent import get_browser_agent
        agent = get_browser_agent()
        result = await agent.browse(url, task)
        if hasattr(result, 'success') and result.success:
            text = getattr(result, 'items', [])
            if isinstance(text, list):
                return "\n".join(str(t)[:2000] for t in text[:5])
            return str(text)[:5000]
        return f"Browser error: {getattr(result, 'error', 'unknown')}"
    except ImportError:
        return "browser_agent not available — install playwright + scrapling"
    except Exception as e:
        return f"Browser error: {e}"


# ═══ P3: Notifications ═══

def notify_slack(message: str, channel: str = "#general") -> str:
    """Send message to Slack. Requires SLACK_WEBHOOK_URL env var."""
    import os
    url = os.environ.get("SLACK_WEBHOOK_URL", "")
    if not url:
        return "SLACK_WEBHOOK_URL not set. Configure via: livingtree config"
    try:
        import json as _json
        import urllib.request as _req
        data = _json.dumps({"text": message, "channel": channel}).encode()
        _req.urlopen(_req.Request(url, data=data, headers={"Content-Type": "application/json"}))
        return f"Sent to Slack {channel}"
    except Exception as e:
        return f"Slack error: {e}"


def notify_feishu(message: str) -> str:
    """Send message to Feishu. Requires FEISHU_WEBHOOK_URL env var."""
    import os
    url = os.environ.get("FEISHU_WEBHOOK_URL", "")
    if not url:
        return "FEISHU_WEBHOOK_URL not set."
    try:
        import json as _json
        import urllib.request as _req
        data = _json.dumps({"msg_type": "text", "content": {"text": message}}).encode()
        _req.urlopen(_req.Request(url, data=data, headers={"Content-Type": "application/json"}))
        return "Sent to Feishu"
    except Exception as e:
        return f"Feishu error: {e}"


def notify_dingtalk(message: str) -> str:
    """Send message to DingTalk. Requires DINGTALK_WEBHOOK_URL env var."""
    import os
    url = os.environ.get("DINGTALK_WEBHOOK_URL", "")
    if not url:
        return "DINGTALK_WEBHOOK_URL not set."
    try:
        import json as _json
        import urllib.request as _req
        data = _json.dumps({"msgtype": "text", "text": {"content": message}}).encode()
        _req.urlopen(_req.Request(url, data=data, headers={"Content-Type": "application/json"}))
        return "Sent to DingTalk"
    except Exception as e:
        return f"DingTalk error: {e}"


# ── Tool registration ──

TOOLS = {
    "list_dir": {"func": list_dir, "desc": "List directory contents with file sizes.", "params": "path"},
    "grep_code": {"func": grep_code, "desc": "Search codebase for pattern (uses ripgrep or Python fallback).", "params": "pattern [path] [glob]"},
    "git_status": {"func": git_status, "desc": "Show working tree status.", "params": ""},
    "git_diff": {"func": git_diff, "desc": "Show working tree changes.", "params": "[file]"},
    "git_commit": {"func": git_commit, "desc": "Stage all changes and commit with message.", "params": "message"},
    "git_push": {"func": git_push, "desc": "Push current branch to remote.", "params": ""},
    "git_branch": {"func": git_branch, "desc": "Branch management: list, create <name>, switch <name>.", "params": "action [name]"},
    "run_test": {"func": run_test, "desc": "Run pytest and return results.", "params": "[test_path]"},
    "browser_fetch": {"func": browser_fetch, "desc": "Open URL in headless browser and perform a task.", "params": "url [task]", "async": True},
    "notify_slack": {"func": notify_slack, "desc": "Send message to Slack.", "params": "message [channel]"},
    "notify_feishu": {"func": notify_feishu, "desc": "Send message to Feishu.", "params": "message"},
    "notify_dingtalk": {"func": notify_dingtalk, "desc": "Send message to DingTalk.", "params": "message"},
}
