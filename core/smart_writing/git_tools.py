"""
Git 操作工具
============

提供安全的 Git 操作接口：
1. 状态查看 - git status, git diff
2. 分支操作 - 列出、创建、切换分支
3. 提交操作 - git add, git commit, git push
4. 历史查看 - git log, git show
5. 远程操作 - git fetch, git pull

使用方式:
    from core.smart_writing.git_tools import GitTools

    tools = GitTools(project_root="/path/to/project")
    result = tools.status()
    result = tools.commit("feat: add new feature")
    result = tools.create_branch("feature/new-feature")
"""

import os
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

from .tool_definition import (
    Tool, ToolParameter, ToolResult, ToolStatus,
    ToolRegistry, ToolCategory
)


# ============== Git 工具类 ==============

class GitTools:
    """
    Git 操作工具集

    提供安全的 Git 操作能力。
    """

    def __init__(
        self,
        project_root: str,
        registry: Optional[ToolRegistry] = None,
    ):
        """
        初始化

        Args:
            project_root: 项目根目录
            registry: 工具注册表（可选）
        """
        self.project_root = Path(project_root).resolve()
        self.registry = registry

        # 注册工具
        if registry:
            self._register_tools()

    def _register_tools(self):
        """注册 Git 工具"""
        self.registry.register_tool(
            Tool(
                name="git_status",
                description="查看 Git 状态",
                category=ToolCategory.GIT,
                parameters=[
                    ToolParameter("short", "bool", "简短格式", required=False, default=False),
                ],
                returns="Git 状态",
                readonly=True,
                tags={"git", "status"},
            ),
            self._git_status_handler
        )

        self.registry.register_tool(
            Tool(
                name="git_diff",
                description="查看文件变更",
                category=ToolCategory.GIT,
                parameters=[
                    ToolParameter("file", "str", "文件路径（可选）", required=False, default=None),
                    ToolParameter("cached", "bool", "是否查看暂存区", required=False, default=False),
                ],
                returns="文件变更",
                readonly=True,
                tags={"git", "diff"},
            ),
            self._git_diff_handler
        )

        self.registry.register_tool(
            Tool(
                name="git_log",
                description="查看提交历史",
                category=ToolCategory.GIT,
                parameters=[
                    ToolParameter("limit", "int", "显示数量", required=False, default=10),
                    ToolParameter("file", "str", "文件路径（可选）", required=False, default=None),
                ],
                returns="提交历史",
                readonly=True,
                tags={"git", "log"},
            ),
            self._git_log_handler
        )

        self.registry.register_tool(
            Tool(
                name="git_branch",
                description="列出/创建/删除分支",
                category=ToolCategory.GIT,
                parameters=[
                    ToolParameter("action", "str", "操作：list/create/delete/checkout", required=False, default="list"),
                    ToolParameter("name", "str", "分支名", required=False, default=None),
                    ToolParameter("force", "bool", "是否强制", required=False, default=False),
                ],
                returns="分支列表或操作结果",
                tags={"git", "branch"},
            ),
            self._git_branch_handler
        )

        self.registry.register_tool(
            Tool(
                name="git_add",
                description="暂存文件",
                category=ToolCategory.GIT,
                parameters=[
                    ToolParameter("files", "str", "文件路径（. 表示全部）", required=True),
                ],
                returns="暂存结果",
                tags={"git", "add"},
            ),
            self._git_add_handler
        )

        self.registry.register_tool(
            Tool(
                name="git_commit",
                description="提交更改",
                category=ToolCategory.GIT,
                parameters=[
                    ToolParameter("message", "str", "提交信息", required=True),
                    ToolParameter("all", "bool", "是否自动暂存所有文件", required=False, default=False),
                ],
                returns="提交结果",
                danger=True,
                confirm_required=True,
                tags={"git", "commit"},
            ),
            self._git_commit_handler
        )

        self.registry.register_tool(
            Tool(
                name="git_push",
                description="推送到远程",
                category=ToolCategory.GIT,
                parameters=[
                    ToolParameter("remote", "str", "远程名", required=False, default="origin"),
                    ToolParameter("branch", "str", "分支名", required=False, default=None),
                    ToolParameter("force", "bool", "是否强制推送", required=False, default=False),
                ],
                returns="推送结果",
                danger=True,
                confirm_required=True,
                tags={"git", "push"},
            ),
            self._git_push_handler
        )

        self.registry.register_tool(
            Tool(
                name="git_pull",
                description="从远程拉取",
                category=ToolCategory.GIT,
                parameters=[
                    ToolParameter("remote", "str", "远程名", required=False, default="origin"),
                    ToolParameter("branch", "str", "分支名", required=False, default=None),
                ],
                returns="拉取结果",
                tags={"git", "pull"},
            ),
            self._git_pull_handler
        )

        self.registry.register_tool(
            Tool(
                name="git_checkout",
                description="切换分支或恢复文件",
                category=ToolCategory.GIT,
                parameters=[
                    ToolParameter("target", "str", "分支名或文件路径", required=True),
                    ToolParameter("create_branch", "str", "创建并切换到新分支", required=False, default=None),
                    ToolParameter("force", "bool", "是否强制", required=False, default=False),
                ],
                returns="切换结果",
                danger=True,
                confirm_required=True,
                tags={"git", "checkout"},
            ),
            self._git_checkout_handler
        )

        self.registry.register_tool(
            Tool(
                name="git_revert",
                description="撤销提交",
                category=ToolCategory.GIT,
                parameters=[
                    ToolParameter("commit", "str", "提交哈希", required=True),
                ],
                returns="撤销结果",
                danger=True,
                confirm_required=True,
                tags={"git", "revert"},
            ),
            self._git_revert_handler
        )

    def _run_git(self, *args, **kwargs) -> Tuple[int, str, str]:
        """运行 Git 命令"""
        cmd = ["git"] + list(args)
        result = subprocess.run(
            cmd,
            cwd=str(self.project_root),
            capture_output=True,
            text=True,
        )
        return result.returncode, result.stdout, result.stderr

    # ============== 工具处理器 ==============

    def _git_status_handler(
        self,
        short: bool = False,
    ) -> ToolResult:
        """Git 状态处理器"""
        args = ["status"]
        if short:
            args.append("--short")

        returncode, stdout, stderr = self._run_git(*args)

        return ToolResult(
            call_id="",
            tool_name="git_status",
            status=ToolStatus.SUCCESS if returncode == 0 else ToolStatus.FAILED,
            result={
                "output": stdout,
                "short": short,
            },
            message=f"Git 状态: {len(stdout.split(chr(10)))} 行",
            output_preview=stdout[:500] if stdout else None,
        )

    def _git_diff_handler(
        self,
        file: Optional[str] = None,
        cached: bool = False,
    ) -> ToolResult:
        """Git diff 处理器"""
        args = ["diff"]
        if cached:
            args.append("--cached")
        if file:
            args.append("--")
            args.append(file)

        returncode, stdout, stderr = self._run_git(*args)

        return ToolResult(
            call_id="",
            tool_name="git_diff",
            status=ToolStatus.SUCCESS if returncode == 0 else ToolStatus.FAILED,
            result={
                "output": stdout,
                "file": file,
                "cached": cached,
            },
            message=f"Git diff: {len(stdout.split(chr(10)))} 行变更",
            output_preview=stdout[:1000] if stdout else None,
        )

    def _git_log_handler(
        self,
        limit: int = 10,
        file: Optional[str] = None,
    ) -> ToolResult:
        """Git log 处理器"""
        args = ["log", f"--max-count={limit}", "--pretty=format:%h %s (%an)"]
        if file:
            args.append("--")
            args.append(file)

        returncode, stdout, stderr = self._run_git(*args)

        commits = []
        if stdout:
            for line in stdout.split('\n'):
                if line.strip():
                    parts = line.split(' ', 2)
                    if len(parts) >= 3:
                        commits.append({
                            "hash": parts[0],
                            "message": parts[2] if len(parts) > 2 else "",
                            "author": parts[1].strip('()'),
                        })

        return ToolResult(
            call_id="",
            tool_name="git_log",
            status=ToolStatus.SUCCESS if returncode == 0 else ToolStatus.FAILED,
            result={
                "commits": commits,
                "count": len(commits),
            },
            message=f"显示 {len(commits)} 条提交记录",
        )

    def _git_branch_handler(
        self,
        action: str = "list",
        name: Optional[str] = None,
        force: bool = False,
    ) -> ToolResult:
        """Git 分支处理器"""
        if action == "list":
            returncode, stdout, stderr = self._run_git("branch", "-a")
            branches = []
            current = ""
            if stdout:
                for line in stdout.split('\n'):
                    if line.strip():
                        is_current = line.startswith('*')
                        branch_name = line.lstrip('* ').strip()
                        if is_current:
                            current = branch_name
                        branches.append({
                            "name": branch_name,
                            "current": is_current,
                            "remote": '/' in branch_name,
                        })

            return ToolResult(
                call_id="",
                tool_name="git_branch",
                status=ToolStatus.SUCCESS if returncode == 0 else ToolStatus.FAILED,
                result={
                    "branches": branches,
                    "current": current,
                },
                message=f"当前分支: {current}",
            )

        elif action == "create" and name:
            args = ["branch"]
            if force:
                args.append("-M")
            else:
                args.append(name)
            returncode, stdout, stderr = self._run_git(*args)
            return ToolResult(
                call_id="",
                tool_name="git_branch",
                status=ToolStatus.SUCCESS if returncode == 0 else ToolStatus.FAILED,
                result={"branch": name, "created": True},
                message=f"创建分支: {name}",
            )

        elif action == "delete" and name:
            args = ["branch", "-d" if not force else "-D", name]
            returncode, stdout, stderr = self._run_git(*args)
            return ToolResult(
                call_id="",
                tool_name="git_branch",
                status=ToolStatus.SUCCESS if returncode == 0 else ToolStatus.FAILED,
                result={"branch": name, "deleted": True},
                message=f"删除分支: {name}",
            )

        else:
            return ToolResult(
                call_id="",
                tool_name="git_branch",
                status=ToolStatus.FAILED,
                error=f"未知操作: {action}",
            )

    def _git_add_handler(self, files: str) -> ToolResult:
        """Git add 处理器"""
        returncode, stdout, stderr = self._run_git("add", files)

        return ToolResult(
            call_id="",
            tool_name="git_add",
            status=ToolStatus.SUCCESS if returncode == 0 else ToolStatus.FAILED,
            result={
                "files": files,
                "staged": returncode == 0,
            },
            message=f"暂存文件: {files}",
        )

    def _git_commit_handler(
        self,
        message: str,
        all: bool = False,
    ) -> ToolResult:
        """Git commit 处理器"""
        args = ["commit", "-m", message]
        if all:
            args.insert(1, "-a")

        returncode, stdout, stderr = self._run_git(*args)

        # 提取提交哈希
        commit_hash = ""
        if returncode == 0 and stdout:
            match = re.search(r'\[(\w+)\s+[\da-f]+\]', stdout)
            if match:
                commit_hash = match.group(1)

        return ToolResult(
            call_id="",
            tool_name="git_commit",
            status=ToolStatus.SUCCESS if returncode == 0 else ToolStatus.FAILED,
            result={
                "message": message,
                "commit_hash": commit_hash,
                "committed": returncode == 0,
            },
            message=f"提交成功: {commit_hash}" if returncode == 0 else f"提交失败: {stderr}",
        )

    def _git_push_handler(
        self,
        remote: str = "origin",
        branch: Optional[str] = None,
        force: bool = False,
    ) -> ToolResult:
        """Git push 处理器"""
        args = ["push"]
        if force:
            args.append("--force")
        args.append(remote)
        if branch:
            args.append(branch)

        returncode, stdout, stderr = self._run_git(*args)

        return ToolResult(
            call_id="",
            tool_name="git_push",
            status=ToolStatus.SUCCESS if returncode == 0 else ToolStatus.FAILED,
            result={
                "remote": remote,
                "branch": branch,
                "pushed": returncode == 0,
            },
            message=f"推送到 {remote}/{branch or '当前分支'}" if returncode == 0 else f"推送失败: {stderr}",
        )

    def _git_pull_handler(
        self,
        remote: str = "origin",
        branch: Optional[str] = None,
    ) -> ToolResult:
        """Git pull 处理器"""
        args = ["pull", remote]
        if branch:
            args.append(branch)

        returncode, stdout, stderr = self._run_git(*args)

        return ToolResult(
            call_id="",
            tool_name="git_pull",
            status=ToolStatus.SUCCESS if returncode == 0 else ToolStatus.FAILED,
            result={
                "remote": remote,
                "branch": branch,
                "pulled": returncode == 0,
            },
            message=f"从 {remote} 拉取" if returncode == 0 else f"拉取失败: {stderr}",
        )

    def _git_checkout_handler(
        self,
        target: str,
        create_branch: Optional[str] = None,
        force: bool = False,
    ) -> ToolResult:
        """Git checkout 处理器"""
        args = ["checkout"]
        if create_branch:
            args.extend(["-b", create_branch])
        elif force:
            args.append("--force")
        args.append(target)

        returncode, stdout, stderr = self._run_git(*args)

        return ToolResult(
            call_id="",
            tool_name="git_checkout",
            status=ToolStatus.SUCCESS if returncode == 0 else ToolStatus.FAILED,
            result={
                "target": target,
                "new_branch": create_branch,
                "checked_out": returncode == 0,
            },
            message=f"切换到: {create_branch or target}" if returncode == 0 else f"切换失败: {stderr}",
        )

    def _git_revert_handler(self, commit: str) -> ToolResult:
        """Git revert 处理器"""
        returncode, stdout, stderr = self._run_git("revert", "--no-edit", commit)

        return ToolResult(
            call_id="",
            tool_name="git_revert",
            status=ToolStatus.SUCCESS if returncode == 0 else ToolStatus.FAILED,
            result={
                "reverted_commit": commit,
                "reverted": returncode == 0,
            },
            message=f"撤销提交: {commit[:8]}" if returncode == 0 else f"撤销失败: {stderr}",
        )

    # ============== 便捷方法 ==============

    def status(self, short: bool = False) -> ToolResult:
        """查看状态"""
        return self._git_status_handler(short)

    def diff(self, file: Optional[str] = None, cached: bool = False) -> ToolResult:
        """查看变更"""
        return self._git_diff_handler(file, cached)

    def log(self, limit: int = 10, file: Optional[str] = None) -> ToolResult:
        """查看历史"""
        return self._git_log_handler(limit, file)

    def branch(self, action: str = "list", name: Optional[str] = None) -> ToolResult:
        """分支操作"""
        return self._git_branch_handler(action, name)

    def add(self, files: str) -> ToolResult:
        """暂存文件"""
        return self._git_add_handler(files)

    def commit(self, message: str, all: bool = False) -> ToolResult:
        """提交"""
        return self._git_commit_handler(message, all)

    def push(self, remote: str = "origin", branch: Optional[str] = None, force: bool = False) -> ToolResult:
        """推送"""
        return self._git_push_handler(remote, branch, force)

    def pull(self, remote: str = "origin", branch: Optional[str] = None) -> ToolResult:
        """拉取"""
        return self._git_pull_handler(remote, branch)

    def checkout(self, target: str, create_branch: Optional[str] = None, force: bool = False) -> ToolResult:
        """切换"""
        return self._git_checkout_handler(target, create_branch, force)


# ============== 导出 ==============

__all__ = [
    'GitTools',
]
