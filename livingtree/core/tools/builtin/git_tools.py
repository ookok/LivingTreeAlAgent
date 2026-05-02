"""
Git 操作工具
"""

import subprocess
from pathlib import Path
from typing import Any

from ..registry import ToolRegistry


def _run_git(path: str, args: list[str], timeout: int = 30) -> tuple[int, str, str]:
    try:
        r = subprocess.run(
            ["git"] + args, capture_output=True, text=True,
            cwd=path, timeout=timeout,
        )
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "命令超时"
    except FileNotFoundError:
        return -1, "", "未找到 git 命令"


def _find_git_root(path: str) -> str:
    p = Path(path).resolve()
    while p != p.parent:
        if (p / ".git").is_dir():
            return str(p)
        p = p.parent
    return ""


def _git_status_handler(ctx: dict, path: str = ".") -> str:
    repo = _find_git_root(path)
    if not repo:
        return f"未找到 Git 仓库: {path}"
    code, stdout, stderr = _run_git(repo, ["status", "--short"])
    if code != 0:
        return f"Git status 失败: {stderr}"
    return stdout.strip() or "工作区干净"


def _git_log_handler(ctx: dict, path: str = ".", limit: int = 20,
                     author: str = "", oneline: bool = True) -> str:
    repo = _find_git_root(path)
    if not repo:
        return f"未找到 Git 仓库: {path}"
    args = ["log", f"-n{limit}"]
    if oneline:
        args.append("--oneline")
    if author:
        args.extend(["--author", author])
    code, stdout, stderr = _run_git(repo, args)
    if code != 0:
        return f"Git log 失败: {stderr}"
    return stdout.strip() or "无提交记录"


def _git_diff_handler(ctx: dict, path: str = ".", staged: bool = False,
                      file_path: str = "") -> str:
    repo = _find_git_root(path)
    if not repo:
        return f"未找到 Git 仓库: {path}"
    args = ["diff"]
    if staged:
        args.append("--staged")
    if file_path:
        args.extend(["--", file_path])
    code, stdout, stderr = _run_git(repo, args, timeout=60)
    if code != 0:
        return f"Git diff 失败: {stderr}"
    output = stdout.strip()
    if not output:
        return "无变更"
    lines = output.split("\n")
    if len(lines) > 300:
        output = "\n".join(lines[:300]) + f"\n... (diff 被截断，共 {len(lines)} 行)"
    return output


def _git_branch_handler(ctx: dict, path: str = ".") -> str:
    repo = _find_git_root(path)
    if not repo:
        return f"未找到 Git 仓库: {path}"
    code, stdout, stderr = _run_git(repo, ["branch", "-a"])
    if code != 0:
        return f"Git branch 失败: {stderr}"
    return stdout.strip() or "无分支"


def register_git_tools():
    ToolRegistry.register(
        "git_status", "查看 Git 仓库状态",
        {"type": "object", "properties": {
            "path": {"type": "string", "description": "仓库路径，默认当前目录"},
        }, "required": []},
        _git_status_handler, "git"
    )
    ToolRegistry.register(
        "git_log", "查看 Git 提交日志",
        {"type": "object", "properties": {
            "path": {"type": "string", "description": "仓库路径"},
            "limit": {"type": "integer", "description": "最大条目数，默认20"},
            "author": {"type": "string", "description": "按作者过滤"},
            "oneline": {"type": "boolean", "description": "单行显示，默认true"},
        }, "required": []},
        _git_log_handler, "git"
    )
    ToolRegistry.register(
        "git_diff", "查看 Git 变更差异",
        {"type": "object", "properties": {
            "path": {"type": "string", "description": "仓库路径"},
            "staged": {"type": "boolean", "description": "仅查看暂存区变更"},
            "file_path": {"type": "string", "description": "限制到特定文件"},
        }, "required": []},
        _git_diff_handler, "git"
    )
    ToolRegistry.register(
        "git_branch", "列出所有 Git 分支",
        {"type": "object", "properties": {
            "path": {"type": "string", "description": "仓库路径"},
        }, "required": []},
        _git_branch_handler, "git"
    )
