"""
Git 仓库分析器 - GitNexus 风格

核心功能：
1. 仓库结构分析
2. 提交历史分析
3. 代码变更追踪
4. 贡献者分析
5. 代码热点识别
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import os
import re
from pathlib import Path
import subprocess
from collections import defaultdict
from operator import itemgetter


@dataclass
class CommitInfo:
    """提交信息"""
    hash: str
    author: str
    email: str
    date: datetime
    message: str
    files_changed: int
    insertions: int
    deletions: int


@dataclass
class Contributor:
    """贡献者信息"""
    name: str
    email: str
    commits: int
    insertions: int
    deletions: int
    files_touched: int


@dataclass
class FileHistory:
    """文件历史"""
    file_path: str
    commits: List[CommitInfo]
    authors: List[str]
    total_changes: int
    last_modified: datetime


@dataclass
class RepositoryStats:
    """仓库统计"""
    total_commits: int
    total_files: int
    total_lines: int
    contributors: List[Contributor]
    top_files: List[Tuple[str, int]]
    activity_trend: Dict[str, int]
    languages: Dict[str, float]


@dataclass
class HotspotInfo:
    """热点信息"""
    file_path: str
    change_frequency: int
    recent_activity: bool
    complexity: int
    risk_level: str  # low, medium, high, critical


class GitAnalyzer:
    """
    Git 仓库分析器 - GitNexus 风格
    
    核心特性：
    1. 仓库结构分析
    2. 提交历史分析
    3. 代码变更追踪
    4. 贡献者分析
    5. 代码热点识别
    """

    def __init__(self, repo_path: str):
        self._repo_path = Path(repo_path)
        self._validate_repo()
        
        self._commits_cache: Dict[str, CommitInfo] = {}
        self._contributors_cache: Dict[str, Contributor] = {}
        self._file_history_cache: Dict[str, FileHistory] = {}

    def _validate_repo(self):
        """验证仓库路径"""
        if not self._repo_path.exists():
            raise ValueError(f"仓库路径不存在: {self._repo_path}")
        
        git_dir = self._repo_path / ".git"
        if not git_dir.exists():
            raise ValueError(f"不是有效的 Git 仓库: {self._repo_path}")

    def _run_git_command(self, cmd: str) -> str:
        """执行 Git 命令"""
        try:
            result = subprocess.run(
                cmd,
                cwd=str(self._repo_path),
                shell=True,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace'
            )
            return result.stdout.strip()
        except Exception as e:
            return f"命令执行失败: {e}"

    def get_repo_info(self) -> Dict[str, Any]:
        """获取仓库基本信息"""
        info = {
            "name": self._repo_path.name,
            "path": str(self._repo_path),
            "branch": self._get_current_branch(),
            "remote_url": self._get_remote_url(),
            "last_commit": self._get_last_commit()
        }
        return info

    def _get_current_branch(self) -> str:
        """获取当前分支"""
        output = self._run_git_command("git rev-parse --abbrev-ref HEAD")
        return output

    def _get_remote_url(self) -> str:
        """获取远程仓库URL"""
        output = self._run_git_command("git config --get remote.origin.url")
        return output

    def _get_last_commit(self) -> str:
        """获取最后提交Hash"""
        output = self._run_git_command("git rev-parse HEAD")
        return output[:7] if output else ""

    def get_commits(self, limit: int = 100) -> List[CommitInfo]:
        """获取提交历史"""
        output = self._run_git_command(
            f"git log --oneline --format='%H|%an|%ae|%ad|%s' --numstat -n {limit}"
        )
        
        commits = []
        lines = output.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
                continue
            
            parts = line.split('|')
            if len(parts) >= 5:
                commit_hash = parts[0]
                author = parts[1]
                email = parts[2]
                date_str = parts[3]
                message = '|'.join(parts[4:])
                
                # 解析日期
                try:
                    commit_date = datetime.strptime(date_str, "%a %b %d %H:%M:%S %Y %z")
                except:
                    commit_date = datetime.now()
                
                # 读取变更统计
                insertions = 0
                deletions = 0
                files_changed = 0
                i += 1
                while i < len(lines) and lines[i].strip() and not lines[i].startswith('|'):
                    stat_line = lines[i].strip()
                    if stat_line:
                        stat_parts = stat_line.split('\t')
                        if len(stat_parts) >= 3:
                            try:
                                insertions += int(stat_parts[0]) if stat_parts[0] != '-' else 0
                                deletions += int(stat_parts[1]) if stat_parts[1] != '-' else 0
                                files_changed += 1
                            except:
                                pass
                    i += 1
                
                commits.append(CommitInfo(
                    hash=commit_hash[:7],
                    author=author,
                    email=email,
                    date=commit_date,
                    message=message,
                    files_changed=files_changed,
                    insertions=insertions,
                    deletions=deletions
                ))
            else:
                i += 1
        
        self._commits_cache = {c.hash: c for c in commits}
        return commits

    def get_contributors(self) -> List[Contributor]:
        """获取贡献者列表"""
        output = self._run_git_command(
            "git log --format='%an|%ae' | sort -u"
        )
        
        contributors = []
        seen = set()
        
        for line in output.split('\n'):
            line = line.strip()
            if not line or line in seen:
                continue
            
            seen.add(line)
            parts = line.split('|')
            if len(parts) >= 2:
                name = parts[0]
                email = parts[1]
                
                # 获取该贡献者的统计
                stats = self._get_contributor_stats(name, email)
                contributors.append(Contributor(
                    name=name,
                    email=email,
                    commits=stats['commits'],
                    insertions=stats['insertions'],
                    deletions=stats['deletions'],
                    files_touched=stats['files_touched']
                ))
        
        # 按提交数排序
        contributors.sort(key=lambda c: c.commits, reverse=True)
        self._contributors_cache = {c.email: c for c in contributors}
        
        return contributors

    def _get_contributor_stats(self, name: str, email: str) -> Dict[str, int]:
        """获取贡献者统计"""
        # 获取提交数
        commits_output = self._run_git_command(
            f"git log --author='{name}' --oneline | wc -l"
        )
        commits = int(commits_output) if commits_output.isdigit() else 0
        
        # 获取变更统计
        stats_output = self._run_git_command(
            f"git log --author='{name}' --numstat --format='' | awk '{{insert+=$1; delete+=$2; files++}} END {{print insert, delete, files}}'"
        )
        parts = stats_output.split()
        insertions = int(parts[0]) if len(parts) > 0 else 0
        deletions = int(parts[1]) if len(parts) > 1 else 0
        files_touched = int(parts[2]) if len(parts) > 2 else 0
        
        return {
            "commits": commits,
            "insertions": insertions,
            "deletions": deletions,
            "files_touched": files_touched
        }

    def get_file_history(self, file_path: str) -> FileHistory:
        """获取文件历史"""
        if file_path in self._file_history_cache:
            return self._file_history_cache[file_path]
        
        output = self._run_git_command(
            f"git log --oneline --format='%H|%an|%ad|%s' -- '{file_path}'"
        )
        
        commits = []
        authors = set()
        total_changes = 0
        
        for line in output.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            parts = line.split('|')
            if len(parts) >= 4:
                commit_hash = parts[0]
                author = parts[1]
                date_str = parts[2]
                message = parts[3]
                
                try:
                    commit_date = datetime.strptime(date_str, "%a %b %d %H:%M:%S %Y %z")
                except:
                    commit_date = datetime.now()
                
                commits.append(CommitInfo(
                    hash=commit_hash[:7],
                    author=author,
                    email="",
                    date=commit_date,
                    message=message,
                    files_changed=1,
                    insertions=0,
                    deletions=0
                ))
                authors.add(author)
                total_changes += 1
        
        last_modified = commits[0].date if commits else datetime.now()
        
        history = FileHistory(
            file_path=file_path,
            commits=commits,
            authors=list(authors),
            total_changes=total_changes,
            last_modified=last_modified
        )
        
        self._file_history_cache[file_path] = history
        return history

    def get_hotspots(self, threshold: int = 10) -> List[HotspotInfo]:
        """识别代码热点"""
        output = self._run_git_command(
            "git log --numstat --format='' | awk '{print $3}' | sort | uniq -c | sort -rn"
        )
        
        hotspots = []
        
        for line in output.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            parts = line.split()
            if len(parts) >= 2:
                count = int(parts[0])
                file_path = ' '.join(parts[1:])
                
                if count >= threshold:
                    # 判断最近活跃度
                    recent_activity = self._is_recently_modified(file_path)
                    
                    # 估算复杂度（基于文件大小和变更频率）
                    complexity = self._estimate_complexity(file_path, count)
                    
                    # 计算风险等级
                    risk_level = self._calculate_risk(count, complexity, recent_activity)
                    
                    hotspots.append(HotspotInfo(
                        file_path=file_path,
                        change_frequency=count,
                        recent_activity=recent_activity,
                        complexity=complexity,
                        risk_level=risk_level
                    ))
        
        return hotspots

    def _is_recently_modified(self, file_path: str) -> bool:
        """判断文件是否最近修改"""
        history = self.get_file_history(file_path)
        if history.commits:
            days_since_modified = (datetime.now() - history.last_modified).days
            return days_since_modified <= 30
        return False

    def _estimate_complexity(self, file_path: str, change_count: int) -> int:
        """估算代码复杂度"""
        complexity = 0
        
        # 基于变更频率
        if change_count > 50:
            complexity += 3
        elif change_count > 20:
            complexity += 2
        else:
            complexity += 1
        
        # 基于文件类型
        if file_path.endswith(('.py', '.java', '.cpp', '.ts')):
            complexity += 2
        elif file_path.endswith(('.js', '.tsx', '.vue')):
            complexity += 1
        
        return complexity

    def _calculate_risk(self, change_freq: int, complexity: int, recent: bool) -> str:
        """计算风险等级"""
        score = 0
        
        if change_freq > 50:
            score += 3
        elif change_freq > 20:
            score += 2
        else:
            score += 1
        
        score += complexity
        
        if recent:
            score += 1
        
        if score >= 8:
            return "critical"
        elif score >= 6:
            return "high"
        elif score >= 4:
            return "medium"
        else:
            return "low"

    def get_repository_stats(self) -> RepositoryStats:
        """获取仓库完整统计"""
        commits = self.get_commits()
        contributors = self.get_contributors()
        
        # 统计总行数
        lines_output = self._run_git_command(
            "git ls-files | xargs wc -l | tail -1 | awk '{print $1}'"
        )
        total_lines = int(lines_output) if lines_output.isdigit() else 0
        
        # 统计文件数
        files_output = self._run_git_command("git ls-files | wc -l")
        total_files = int(files_output) if files_output.isdigit() else 0
        
        # 获取热门文件
        hotspots = self.get_hotspots(1)
        top_files = [(h.file_path, h.change_frequency) for h in hotspots[:10]]
        
        # 活动趋势（按月份）
        activity_trend = defaultdict(int)
        for commit in commits:
            month_key = commit.date.strftime("%Y-%m")
            activity_trend[month_key] += 1
        
        # 语言分布（简单版本）
        languages = self._detect_languages()
        
        return RepositoryStats(
            total_commits=len(commits),
            total_files=total_files,
            total_lines=total_lines,
            contributors=contributors,
            top_files=top_files,
            activity_trend=dict(activity_trend),
            languages=languages
        )

    def _detect_languages(self) -> Dict[str, float]:
        """检测语言分布"""
        output = self._run_git_command("git ls-files")
        
        lang_counts = defaultdict(int)
        total = 0
        
        for line in output.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            ext = Path(line).suffix.lower()
            if ext:
                lang = self._ext_to_lang(ext)
                lang_counts[lang] += 1
                total += 1
        
        if total == 0:
            return {}
        
        return {lang: count / total for lang, count in lang_counts.items()}

    def _ext_to_lang(self, ext: str) -> str:
        """扩展名到语言映射"""
        lang_map = {
            '.py': 'Python',
            '.js': 'JavaScript',
            '.ts': 'TypeScript',
            '.vue': 'Vue',
            '.java': 'Java',
            '.cpp': 'C++',
            '.c': 'C',
            '.go': 'Go',
            '.rs': 'Rust',
            '.tsx': 'TypeScript',
            '.jsx': 'JavaScript',
            '.html': 'HTML',
            '.css': 'CSS',
            '.md': 'Markdown',
            '.json': 'JSON',
            '.yaml': 'YAML',
            '.yml': 'YAML',
            '.xml': 'XML',
            '.sql': 'SQL',
            '.sh': 'Shell',
            '.bat': 'Batch',
            '.txt': 'Text'
        }
        return lang_map.get(ext, 'Other')

    def get_change_history(self, file_path: str, since_date: Optional[datetime] = None) -> List[CommitInfo]:
        """获取文件变更历史（指定日期范围）"""
        history = self.get_file_history(file_path)
        
        if since_date:
            return [c for c in history.commits if c.date >= since_date]
        
        return history.commits

    def search_by_message(self, pattern: str) -> List[CommitInfo]:
        """按提交消息搜索"""
        output = self._run_git_command(
            f"git log --oneline --format='%H|%an|%ae|%ad|%s' --grep='{pattern}'"
        )
        
        commits = []
        for line in output.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            parts = line.split('|')
            if len(parts) >= 5:
                try:
                    commit_date = datetime.strptime(parts[3], "%a %b %d %H:%M:%S %Y %z")
                except:
                    commit_date = datetime.now()
                
                commits.append(CommitInfo(
                    hash=parts[0][:7],
                    author=parts[1],
                    email=parts[2],
                    date=commit_date,
                    message=parts[4],
                    files_changed=0,
                    insertions=0,
                    deletions=0
                ))
        
        return commits

    def get_blame(self, file_path: str) -> Dict[int, Tuple[str, str, str]]:
        """获取文件 blame 信息"""
        output = self._run_git_command(
            f"git blame --line-porcelain '{file_path}'"
        )
        
        blame_info = {}
        current_line = 0
        current_author = ""
        current_hash = ""
        current_date = ""
        
        for line in output.split('\n'):
            if line.startswith('author '):
                current_author = line[7:]
            elif line.startswith('committer-time '):
                try:
                    timestamp = int(line[16:])
                    current_date = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")
                except:
                    current_date = ""
            elif line.startswith(' ') or line.startswith('\t'):
                current_line += 1
                blame_info[current_line] = (current_hash[:7], current_author, current_date)
            elif line and ' ' not in line:
                current_hash = line
        
        return blame_info


def get_git_analyzer(repo_path: str) -> GitAnalyzer:
    """获取 Git 分析器实例"""
    return GitAnalyzer(repo_path)