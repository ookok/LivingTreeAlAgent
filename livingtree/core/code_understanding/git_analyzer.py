"""
Git 分析器 (Git Analyzer)

分析 Git 仓库的提交历史和代码演进：
- 提交历史分析
- 代码变更统计
- 提交者活跃度分析
- 热点文件识别
"""

import logging
import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class GitCommitInfo:
    hash: str
    author: str
    date: datetime
    message: str
    files_changed: int = 0
    insertions: int = 0
    deletions: int = 0


@dataclass
class FileHistory:
    file_path: str
    total_changes: int = 0
    last_modified: Optional[datetime] = None
    authors: List[str] = field(default_factory=list)
    churn_rate: float = 0.0


@dataclass
class RepoAnalysis:
    repo_path: str
    total_commits: int = 0
    total_contributors: int = 0
    age_days: int = 0
    hot_files: List[FileHistory] = field(default_factory=list)
    contributor_stats: Dict[str, Dict[str, int]] = field(default_factory=dict)


class GitAnalyzer:

    def __init__(self, repo_path: str = "."):
        self.repo_path = repo_path
        self._git_available = self._check_git()

    def _check_git(self) -> bool:
        try:
            subprocess.run(
                ["git", "--version"], capture_output=True,
                cwd=self.repo_path, timeout=5)
            return True
        except Exception:
            logger.warning(f"Git 不可用或仓库路径无效: {self.repo_path}")
            return False

    def is_available(self) -> bool:
        return self._git_available

    def get_commit_history(self, max_commits: int = 100) -> List[GitCommitInfo]:
        if not self._git_available:
            return []

        try:
            result = subprocess.run(
                ["git", "log", f"-{max_commits}",
                 "--format=%H|%an|%ai|%s"],
                capture_output=True, text=True,
                cwd=self.repo_path, timeout=30)

            commits = []
            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue
                parts = line.split('|', 3)
                if len(parts) >= 4:
                    try:
                        date = datetime.strptime(
                            parts[2][:19], "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        date = datetime.now()
                    commits.append(GitCommitInfo(
                        hash=parts[0][:8], author=parts[1],
                        date=date, message=parts[3]))

            return commits
        except Exception as e:
            logger.error(f"获取 Git 历史失败: {e}")
            return []

    def analyze_repository(self) -> Optional[RepoAnalysis]:
        if not self._git_available:
            return None

        try:
            log_result = subprocess.run(
                ["git", "log", "--format=%H|%an|%ai"],
                capture_output=True, text=True,
                cwd=self.repo_path, timeout=60)

            lines = log_result.stdout.strip().split('\n')
            commits = [l for l in lines if l]

            contributors = set()
            for line in commits:
                parts = line.split('|')
                if len(parts) >= 2:
                    contributors.add(parts[1])

            analysis = RepoAnalysis(
                repo_path=self.repo_path,
                total_commits=len(commits),
                total_contributors=len(contributors))

            if commits:
                last = commits[0]
                first = commits[-1]
                try:
                    last_date = datetime.strptime(
                        last.split('|')[2][:19], "%Y-%m-%d %H:%M:%S")
                    first_date = datetime.strptime(
                        first.split('|')[2][:19], "%Y-%m-%d %H:%M:%S")
                    analysis.age_days = (last_date - first_date).days
                except Exception:
                    pass

            analysis.hot_files = self._get_hot_files()
            return analysis

        except Exception as e:
            logger.error(f"仓库分析失败: {e}")
            return None

    def _get_hot_files(self, top_n: int = 10) -> List[FileHistory]:
        try:
            result = subprocess.run(
                ["git", "log", "--format=", "--name-only"],
                capture_output=True, text=True,
                cwd=self.repo_path, timeout=30)

            file_counts: Dict[str, int] = {}
            for line in result.stdout.strip().split('\n'):
                line = line.strip()
                if line:
                    file_counts[line] = file_counts.get(line, 0) + 1

            sorted_files = sorted(file_counts.items(),
                                  key=lambda x: -x[1])[:top_n]

            return [FileHistory(
                file_path=fp, total_changes=count,
                churn_rate=count / max(1, count))
                for fp, count in sorted_files]

        except Exception:
            return []

    def get_file_changes(self, file_path: str,
                         max_commits: int = 50) -> List[GitCommitInfo]:
        if not self._git_available:
            return []

        try:
            result = subprocess.run(
                ["git", "log", f"-{max_commits}",
                 "--format=%H|%an|%ai|%s", "--", file_path],
                capture_output=True, text=True,
                cwd=self.repo_path, timeout=30)

            commits = []
            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue
                parts = line.split('|', 3)
                if len(parts) >= 4:
                    try:
                        date = datetime.strptime(
                            parts[2][:19], "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        date = datetime.now()
                    commits.append(GitCommitInfo(
                        hash=parts[0][:8], author=parts[1],
                        date=date, message=parts[3]))

            return commits
        except Exception:
            return []


__all__ = [
    "GitCommitInfo", "FileHistory", "RepoAnalysis",
    "GitAnalyzer",
]
