"""
GitHub 项目集成模块
支持从 GitHub 克隆、编辑、提交和推送项目
"""

import os
import asyncio
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class GitHubProject:
    """GitHub 项目信息"""
    owner: str
    repo: str
    branch: str = "main"
    local_path: Optional[str] = None
    clone_url: Optional[str] = None
    
    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.repo}"
    
    @property
    def https_url(self) -> str:
        return f"https://github.com/{self.full_name}.git"
    
    @property
    def ssh_url(self) -> str:
        return f"git@github.com:{self.full_name}.git"


class GitHubProjectManager:
    """
    GitHub 项目管理器
    支持：
    - 克隆仓库
    - 拉取更新
    - 提交更改
    - 推送代码
    - 查看差异
    """
    
    def __init__(self, workspace_path: str = None):
        self.workspace_path = Path(workspace_path or os.path.expanduser("~/.hermes-desktop/smart_ide_workspace"))
        self.workspace_path.mkdir(parents=True, exist_ok=True)
        self._projects: Dict[str, GitHubProject] = {}
    
    def _run_git_command(self, args: List[str], cwd: str = None, timeout: int = 300) -> Tuple[int, str, str]:
        """执行 git 命令"""
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=cwd or str(self.workspace_path),
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", "Command timed out"
        except FileNotFoundError:
            return -1, "", "Git not found. Please install Git."
        except Exception as e:
            return -1, "", str(e)
    
    def parse_repo_url(self, url_or_name: str) -> Tuple[str, str]:
        """解析仓库 URL 或名称"""
        # 已经是完整 URL
        if url_or_name.startswith("https://github.com/") or url_or_name.startswith("git@github.com:"):
            if url_or_name.startswith("https://github.com/"):
                # https://github.com/owner/repo
                parts = url_or_name.replace("https://github.com/", "").replace(".git", "").split("/")
            else:
                # git@github.com:owner/repo
                parts = url_or_name.replace("git@github.com:", "").replace(".git", "").split("/")
            return parts[0], parts[1]
        
        # 简化格式: owner/repo 或 just repo name
        if "/" in url_or_name:
            parts = url_or_name.split("/")
            return parts[0], parts[1]
        else:
            # 假设是当前用户的仓库
            return "owner", url_or_name
    
    async def clone(
        self,
        repo: str,
        branch: str = "main",
        use_ssh: bool = False,
        depth: int = 1
    ) -> Tuple[bool, str]:
        """
        克隆仓库
        
        Args:
            repo: 仓库地址 (owner/repo 或 URL)
            branch: 分支名
            use_ssh: 是否使用 SSH 克隆
            depth: 克隆深度
            
        Returns:
            (是否成功, 消息/本地路径)
        """
        owner, repo_name = self.parse_repo_url(repo)
        project = GitHubProject(owner=owner, repo=repo_name, branch=branch)
        
        local_path = self.workspace_path / repo_name
        project.local_path = str(local_path)
        
        # 检查是否已存在
        if local_path.exists():
            return True, f"项目已存在: {local_path}"
        
        # 构建克隆命令
        url = project.ssh_url if use_ssh else project.https_url
        args = ["clone", "--branch", branch, "--depth", str(depth)]
        
        if depth == 1:
            args.append("--single-branch")
        
        args.extend([url, str(local_path)])
        
        returncode, stdout, stderr = self._run_git_command(args)
        
        if returncode == 0:
            self._projects[project.full_name] = project
            return True, str(local_path)
        else:
            return False, f"克隆失败: {stderr}"
    
    async def pull(self, project_path: str) -> Tuple[bool, str]:
        """拉取更新"""
        if not os.path.exists(project_path):
            return False, "项目路径不存在"
        
        returncode, stdout, stderr = self._run_git_command(["pull", "--ff-only"], cwd=project_path)
        
        if returncode == 0:
            return True, "拉取成功"
        else:
            return False, f"拉取失败: {stderr}"
    
    async def commit_and_push(
        self,
        project_path: str,
        message: str,
        author_name: str = None,
        author_email: str = None,
        push_branch: str = None
    ) -> Tuple[bool, str]:
        """
        提交并推送更改
        
        Args:
            project_path: 项目本地路径
            message: 提交信息
            author_name: 作者名称
            author_email: 作者邮箱
            push_branch: 推送分支
            
        Returns:
            (是否成功, 消息)
        """
        if not os.path.exists(project_path):
            return False, "项目路径不存在"
        
        # 检查是否有更改
        returncode, stdout, _ = self._run_git_command(["status", "--porcelain"], cwd=project_path)
        if returncode != 0:
            return False, f"检查状态失败: {stdout}"
        
        if not stdout.strip():
            return True, "没有需要提交的更改"
        
        # 配置作者信息
        if author_name:
            self._run_git_command(["config", "user.name", author_name], cwd=project_path)
        if author_email:
            self._run_git_command(["config", "user.email", author_email], cwd=project_path)
        
        # 添加所有更改
        returncode, _, stderr = self._run_git_command(["add", "-A"], cwd=project_path)
        if returncode != 0:
            return False, f"添加文件失败: {stderr}"
        
        # 提交
        returncode, _, stderr = self._run_git_command(["commit", "-m", message], cwd=project_path)
        if returncode != 0:
            return False, f"提交失败: {stderr}"
        
        # 获取当前分支
        if push_branch is None:
            returncode, stdout, _ = self._run_git_command(["rev-parse", "--abbrev-ref", "HEAD"], cwd=project_path)
            if returncode != 0:
                return False, "获取分支失败"
            push_branch = stdout.strip()
        
        # 推送
        returncode, stdout, stderr = self._run_git_command(
            ["push", "-u", "origin", push_branch],
            cwd=project_path
        )
        
        if returncode == 0:
            return True, f"推送成功到 {push_branch}"
        else:
            return False, f"推送失败: {stderr}"
    
    async def get_status(self, project_path: str) -> Dict:
        """获取项目状态"""
        if not os.path.exists(project_path):
            return {"error": "项目路径不存在"}
        
        result = {"path": project_path, "files": [], "branch": "", "ahead": 0, "behind": 0}
        
        # 获取分支
        returncode, stdout, _ = self._run_git_command(["rev-parse", "--abbrev-ref", "HEAD"], cwd=project_path)
        if returncode == 0:
            result["branch"] = stdout.strip()
        
        # 获取状态
        returncode, stdout, _ = self._run_git_command(["status", "--porcelain"], cwd=project_path)
        if returncode == 0:
            for line in stdout.strip().split("\n"):
                if line:
                    status = line[:2]
                    filepath = line[3:]
                    result["files"].append({"status": status, "file": filepath})
        
        # 获取领先/落后
        returncode, stdout, _ = self._run_git_command(["status", "-sb"], cwd=project_path)
        if returncode == 0 and "..." in stdout:
            parts = stdout.split("\n")[0].split("...")
            if len(parts) == 2:
                remote_branch = parts[1].split("[")[0].strip()
                result["remote_branch"] = remote_branch
        
        return result
    
    async def get_branches(self, project_path: str) -> List[str]:
        """获取分支列表"""
        if not os.path.exists(project_path):
            return []
        
        returncode, stdout, _ = self._run_git_command(["branch", "-a"], cwd=project_path)
        if returncode == 0:
            branches = []
            for line in stdout.strip().split("\n"):
                line = line.strip()
                if line.startswith("*"):
                    line = line[1:].strip()
                if line:
                    branches.append(line.replace("remotes/", ""))
            return branches
        
        return []
    
    async def checkout_branch(self, project_path: str, branch: str) -> Tuple[bool, str]:
        """切换分支"""
        if not os.path.exists(project_path):
            return False, "项目路径不存在"
        
        returncode, stdout, stderr = self._run_git_command(["checkout", branch], cwd=project_path)
        
        if returncode == 0:
            return True, f"已切换到分支: {branch}"
        else:
            return False, f"切换失败: {stderr}"
    
    async def create_branch(
        self,
        project_path: str,
        branch: str,
        start_point: str = None
    ) -> Tuple[bool, str]:
        """创建新分支"""
        if not os.path.exists(project_path):
            return False, "项目路径不存在"
        
        args = ["checkout", "-b", branch]
        if start_point:
            args.append(start_point)
        
        returncode, stdout, stderr = self._run_git_command(args, cwd=project_path)
        
        if returncode == 0:
            return True, f"已创建并切换到分支: {branch}"
        else:
            return False, f"创建分支失败: {stderr}"
    
    async def get_diff(self, project_path: str, file: str = None) -> str:
        """获取差异"""
        if not os.path.exists(project_path):
            return ""
        
        args = ["diff"]
        if file:
            args.append(file)
        
        returncode, stdout, stderr = self._run_git_command(args, cwd=project_path)
        return stdout if returncode == 0 else stderr
    
    def list_projects(self) -> List[Dict]:
        """列出所有已克隆的项目"""
        projects = []
        for path in self.workspace_path.iterdir():
            if path.is_dir() and (path / ".git").exists():
                # 尝试获取远程信息
                returncode, stdout, _ = self._run_git_command(
                    ["remote", "get-url", "origin"],
                    cwd=str(path)
                )
                remote_url = stdout.strip() if returncode == 0 else ""
                
                projects.append({
                    "name": path.name,
                    "path": str(path),
                    "remote": remote_url
                })
        
        return projects
    
    def get_workspace_path(self) -> str:
        """获取工作区路径"""
        return str(self.workspace_path)


# 全局单例
_github_manager: Optional[GitHubProjectManager] = None


def get_github_project_manager() -> GitHubProjectManager:
    """获取 GitHub 项目管理器单例"""
    global _github_manager
    if _github_manager is None:
        _github_manager = GitHubProjectManager()
    return _github_manager
