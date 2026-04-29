"""
Git智能集成模块
实现语义化提交信息、智能变更分析等功能
"""

import os
import re
import subprocess
import json
from typing import Optional, Dict, List, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime


class CommitType(Enum):
    """提交类型"""
    FEAT = "feat"
    FIX = "fix"
    DOCS = "docs"
    STYLE = "style"
    REFACTOR = "refactor"
    TEST = "test"
    CHORE = "chore"
    PERF = "perf"
    CI = "ci"
    BUILD = "build"


class ChangeType(Enum):
    """变更类型"""
    ADD = "add"
    MODIFY = "modify"
    DELETE = "delete"
    RENAME = "rename"
    COPY = "copy"


@dataclass
class FileChange:
    """文件变更"""
    file_path: str
    change_type: ChangeType
    added_lines: int = 0
    deleted_lines: int = 0
    content: Optional[str] = None
    diff: Optional[str] = None


@dataclass
class CommitInfo:
    """提交信息"""
    commit_type: CommitType
    scope: Optional[str] = None
    subject: str = ""
    body: Optional[str] = None
    footer: Optional[str] = None
    breaking_change: bool = False


class GitAnalyzer:
    """Git分析器"""
    
    def __init__(self, repo_path: str = None):
        self.repo_path = repo_path or os.getcwd()
    
    def _run_git_command(self, command: List[str]) -> Optional[str]:
        """运行Git命令"""
        try:
            result = subprocess.run(
                ['git'] + command,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            print(f"Git命令执行失败: {e.stderr}")
            return None
    
    def get_changed_files(self) -> List[FileChange]:
        """获取变更的文件"""
        files = []
        
        # 获取暂存区和工作区的变更
        output = self._run_git_command(['diff', '--name-status'])
        if output:
            for line in output.strip().split('\n'):
                if line:
                    parts = line.split('\t', 1)
                    if len(parts) >= 2:
                        status, file_path = parts
                        change_type = self._parse_change_type(status)
                        if change_type:
                            # 获取详细的diff信息
                            diff_output = self._run_git_command(['diff', '--', file_path])
                            added, deleted = self._count_lines(diff_output)
                            
                            files.append(FileChange(
                                file_path=file_path,
                                change_type=change_type,
                                added_lines=added,
                                deleted_lines=deleted,
                                diff=diff_output
                            ))
        
        return files
    
    def _parse_change_type(self, status: str) -> Optional[ChangeType]:
        """解析变更类型"""
        if status.startswith('A'):
            return ChangeType.ADD
        elif status.startswith('M'):
            return ChangeType.MODIFY
        elif status.startswith('D'):
            return ChangeType.DELETE
        elif status.startswith('R'):
            return ChangeType.RENAME
        elif status.startswith('C'):
            return ChangeType.COPY
        return None
    
    def _count_lines(self, diff: Optional[str]) -> tuple:
        """统计添加和删除的行数"""
        if not diff:
            return 0, 0
        
        added = 0
        deleted = 0
        
        for line in diff.split('\n'):
            if line.startswith('+') and not line.startswith('+++'):
                added += 1
            elif line.startswith('-') and not line.startswith('---'):
                deleted += 1
        
        return added, deleted
    
    def get_file_content(self, file_path: str) -> Optional[str]:
        """获取文件内容"""
        try:
            with open(os.path.join(self.repo_path, file_path), 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"读取文件失败: {e}")
            return None
    
    def analyze_commit_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """分析提交历史"""
        commits = []
        
        output = self._run_git_command(['log', f'-{limit}', '--pretty=format:%H|%an|%ad|%s', '--date=iso'])
        if output:
            for line in output.strip().split('\n'):
                if line:
                    parts = line.split('|', 3)
                    if len(parts) >= 4:
                        commit_hash, author, date, message = parts
                        commits.append({
                            'hash': commit_hash,
                            'author': author,
                            'date': date,
                            'message': message
                        })
        
        return commits
    
    def get_repo_info(self) -> Dict[str, Any]:
        """获取仓库信息"""
        info = {}
        
        # 获取远程仓库
        remote_output = self._run_git_command(['remote', '-v'])
        if remote_output:
            info['remotes'] = remote_output.strip().split('\n')
        
        # 获取当前分支
        branch_output = self._run_git_command(['branch', '--show-current'])
        if branch_output:
            info['current_branch'] = branch_output.strip()
        
        # 获取状态
        status_output = self._run_git_command(['status', '--porcelain'])
        if status_output:
            info['status'] = status_output.strip().split('\n')
        
        return info


class CommitMessageGenerator:
    """提交信息生成器"""
    
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        self.commit_templates = {
            CommitType.FEAT: "feat({scope}): {subject}",
            CommitType.FIX: "fix({scope}): {subject}",
            CommitType.DOCS: "docs({scope}): {subject}",
            CommitType.STYLE: "style({scope}): {subject}",
            CommitType.REFACTOR: "refactor({scope}): {subject}",
            CommitType.TEST: "test({scope}): {subject}",
            CommitType.CHORE: "chore({scope}): {subject}",
            CommitType.PERF: "perf({scope}): {subject}",
            CommitType.CI: "ci({scope}): {subject}",
            CommitType.BUILD: "build({scope}): {subject}"
        }
    
    def analyze_changes(self, files: List[FileChange]) -> Dict[str, Any]:
        """分析变更"""
        analysis = {
            'total_files': len(files),
            'additions': 0,
            'deletions': 0,
            'file_types': {},
            'change_types': {}
        }
        
        for file in files:
            analysis['additions'] += file.added_lines
            analysis['deletions'] += file.deleted_lines
            
            # 统计文件类型
            ext = os.path.splitext(file.file_path)[1]
            analysis['file_types'][ext] = analysis['file_types'].get(ext, 0) + 1
            
            # 统计变更类型
            analysis['change_types'][file.change_type.value] = analysis['change_types'].get(file.change_type.value, 0) + 1
        
        return analysis
    
    def generate_commit_message(self, files: List[FileChange]) -> Optional[CommitInfo]:
        """生成提交信息"""
        if self.llm_client:
            return self._generate_with_llm(files)
        else:
            return self._generate_with_rules(files)
    
    async def _generate_with_llm(self, files: List[FileChange]) -> Optional[CommitInfo]:
        """使用LLM生成提交信息"""
        try:
            # 构建变更摘要
            change_summary = []
            for file in files:
                change_summary.append(f"- {file.change_type.value}: {file.file_path} (+{file.added_lines}, -{file.deleted_lines})")
            
            prompt = f"""基于以下代码变更，生成语义化的Git提交信息：

变更摘要：
{chr(10).join(change_summary)}

请生成符合Conventional Commits规范的提交信息，包括：
1. 提交类型（feat, fix, docs, style, refactor, test, chore, perf, ci, build）
2. 可选的作用域（scope）
3. 简短的描述（subject）
4. 详细的描述（body，可选）
5. 页脚信息（footer，可选）
6. 是否包含破坏性变更（breaking change）

请返回一个JSON对象，包含上述字段。"""
            
            response = await self.llm_client.generate(prompt)
            
            # 解析JSON
            import json
            try:
                data = json.loads(response)
                commit_info = CommitInfo(
                    commit_type=CommitType(data.get('commit_type', 'feat')),
                    scope=data.get('scope'),
                    subject=data.get('subject', ''),
                    body=data.get('body'),
                    footer=data.get('footer'),
                    breaking_change=data.get('breaking_change', False)
                )
                return commit_info
            except json.JSONDecodeError:
                # 回退到规则生成
                return self._generate_with_rules(files)
        except Exception as e:
            print(f"LLM生成提交信息失败: {e}")
            return self._generate_with_rules(files)
    
    def _generate_with_rules(self, files: List[FileChange]) -> CommitInfo:
        """使用规则生成提交信息"""
        # 简单的规则生成
        if not files:
            return CommitInfo(
                commit_type=CommitType.CHORE,
                subject="Empty commit"
            )
        
        # 分析变更类型
        has_new_files = any(f.change_type == ChangeType.ADD for f in files)
        has_modifications = any(f.change_type == ChangeType.MODIFY for f in files)
        has_deletions = any(f.change_type == ChangeType.DELETE for f in files)
        
        # 确定提交类型
        commit_type = CommitType.CHORE
        if has_new_files:
            commit_type = CommitType.FEAT
        elif has_modifications:
            # 检查是否是修复
            for file in files:
                if 'test' in file.file_path.lower():
                    commit_type = CommitType.TEST
                    break
                elif 'doc' in file.file_path.lower():
                    commit_type = CommitType.DOCS
                    break
                elif any(keyword in file.file_path.lower() for keyword in ['fix', 'bug', 'error']):
                    commit_type = CommitType.FIX
                    break
            else:
                commit_type = CommitType.REFACTOR
        
        # 生成描述
        subject = f"{len(files)} files changed"
        if commit_type == CommitType.FEAT:
            subject = "Add new features"
        elif commit_type == CommitType.FIX:
            subject = "Fix bugs"
        elif commit_type == CommitType.DOCS:
            subject = "Update documentation"
        elif commit_type == CommitType.TEST:
            subject = "Add or update tests"
        
        return CommitInfo(
            commit_type=commit_type,
            subject=subject
        )
    
    def format_commit_message(self, commit_info: CommitInfo) -> str:
        """格式化提交信息"""
        template = self.commit_templates.get(commit_info.commit_type, self.commit_templates[CommitType.CHORE])
        
        # 构建提交信息
        message_parts = []
        
        # 标题
        scope_part = f"{commit_info.scope}" if commit_info.scope else ""
        title = template.format(scope=scope_part, subject=commit_info.subject)
        message_parts.append(title)
        
        # 空行
        message_parts.append("")
        
        # 正文
        if commit_info.body:
            message_parts.append(commit_info.body)
            message_parts.append("")
        
        # 页脚
        if commit_info.footer:
            message_parts.append(commit_info.footer)
            message_parts.append("")
        
        # 破坏性变更
        if commit_info.breaking_change:
            message_parts.append("BREAKING CHANGE: This commit introduces breaking changes")
        
        return '\n'.join(message_parts)


class GitManager:
    """Git管理器"""
    
    def __init__(self, repo_path: str = None, llm_client=None):
        self.repo_path = repo_path or os.getcwd()
        self.analyzer = GitAnalyzer(self.repo_path)
        self.message_generator = CommitMessageGenerator(llm_client)
    
    def stage_all(self) -> bool:
        """暂存所有变更"""
        result = self.analyzer._run_git_command(['add', '.'])
        return result is not None
    
    def commit(self, message: str) -> bool:
        """提交变更"""
        result = self.analyzer._run_git_command(['commit', '-m', message])
        return result is not None
    
    def generate_and_commit(self) -> Optional[str]:
        """生成提交信息并提交"""
        # 获取变更文件
        files = self.analyzer.get_changed_files()
        if not files:
            print("没有变更需要提交")
            return None
        
        # 生成提交信息
        commit_info = self.message_generator.generate_commit_message(files)
        if not commit_info:
            print("生成提交信息失败")
            return None
        
        # 格式化提交信息
        commit_message = self.message_generator.format_commit_message(commit_info)
        
        # 暂存并提交
        if self.stage_all() and self.commit(commit_message):
            return commit_message
        
        return None
    
    def analyze_repo(self) -> Dict[str, Any]:
        """分析仓库"""
        info = {
            'repo_info': self.analyzer.get_repo_info(),
            'commit_history': self.analyzer.analyze_commit_history(5),
            'changed_files': []
        }
        
        # 分析变更文件
        files = self.analyzer.get_changed_files()
        for file in files:
            info['changed_files'].append({
                'file_path': file.file_path,
                'change_type': file.change_type.value,
                'added_lines': file.added_lines,
                'deleted_lines': file.deleted_lines
            })
        
        return info
    
    def get_semantic_commit_suggestion(self) -> Optional[str]:
        """获取语义化提交建议"""
        files = self.analyzer.get_changed_files()
        if not files:
            return None
        
        commit_info = self.message_generator.generate_commit_message(files)
        if not commit_info:
            return None
        
        return self.message_generator.format_commit_message(commit_info)
    
    def detect_merge_conflicts(self) -> List[str]:
        """检测合并冲突"""
        conflicts = []
        
        output = self.analyzer._run_git_command(['diff', '--name-only', '--diff-filter=U'])
        if output:
            conflicts = output.strip().split('\n')
        
        return conflicts
    
    def get_recent_commits(self, days: int = 7) -> List[Dict[str, Any]]:
        """获取最近的提交"""
        return self.analyzer.analyze_commit_history(limit=days * 3)  # 假设每天3个提交


def create_git_manager(repo_path: str = None, llm_client=None) -> GitManager:
    """
    创建Git管理器
    
    Args:
        repo_path: 仓库路径
        llm_client: LLM客户端
        
    Returns:
        GitManager: Git管理器实例
    """
    return GitManager(repo_path, llm_client)