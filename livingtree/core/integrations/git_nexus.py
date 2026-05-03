"""
GitNexus — 统一代码智能引擎

整合功能：
1. Git 仓库分析 — 提交历史、贡献者、热点识别、blame
2. 代码结构分析 — AST 解析、实体/关系提取、依赖图
3. 智能代码搜索 — 倒排索引、模糊匹配、相似代码推荐
4. 代码质量分析 — 复杂度、可维护性、重构建议、安全检查

从 client/src/business/git_nexus/ 迁移，修复了 3 个 bug：
  - ClassDef 重复处理导致弹栈永远为 True
  - 质量分析器 file_path 硬编码为"dummy.py"
  - 相似度计算未使用 Jaccard 导致分数不准
"""

from __future__ import annotations

import ast
import hashlib
import os
import re
import subprocess
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


# ═══════════════════════════════════════════════════════════════════════
# 共享数据类型
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class CommitInfo:
    """提交信息"""
    hash: str
    author: str
    email: str
    date: datetime
    message: str
    files_changed: int = 0
    insertions: int = 0
    deletions: int = 0


@dataclass
class Contributor:
    """贡献者信息"""
    name: str
    email: str
    commits: int = 0
    insertions: int = 0
    deletions: int = 0
    files_touched: int = 0


@dataclass
class FileHistory:
    """文件历史"""
    file_path: str
    commits: List[CommitInfo] = field(default_factory=list)
    authors: List[str] = field(default_factory=list)
    total_changes: int = 0
    last_modified: Optional[datetime] = None


@dataclass
class RepositoryStats:
    """仓库统计"""
    total_commits: int = 0
    total_files: int = 0
    total_lines: int = 0
    contributors: List[Contributor] = field(default_factory=list)
    top_files: List[Tuple[str, int]] = field(default_factory=list)
    activity_trend: Dict[str, int] = field(default_factory=dict)
    languages: Dict[str, float] = field(default_factory=dict)


@dataclass
class HotspotInfo:
    """热点信息"""
    file_path: str
    change_frequency: int
    recent_activity: bool
    complexity: int
    risk_level: str  # low | medium | high | critical


@dataclass
class CodeEntity:
    """代码实体"""
    id: str
    type: str  # function | class | method | variable | import
    name: str
    file_path: str
    line_start: int
    line_end: int
    docstring: Optional[str] = None
    parent_id: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    decorators: List[str] = field(default_factory=list)


@dataclass
class CodeRelation:
    """代码关系"""
    source_id: str
    target_id: str
    relation_type: str  # calls | imports | inherits | uses
    line_number: int


@dataclass
class FileStructure:
    """文件结构"""
    file_path: str
    functions: List[CodeEntity] = field(default_factory=list)
    classes: List[CodeEntity] = field(default_factory=list)
    imports: List[CodeEntity] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)


@dataclass
class SearchResult:
    """搜索结果"""
    score: float
    entity: Optional[CodeEntity] = None
    snippet: str = ""
    match_type: str = "content"  # name | content | docstring | dependency | similar


@dataclass
class CodeRecommendation:
    """代码推荐"""
    entity: CodeEntity
    relevance: float
    reason: str


@dataclass
class QualityMetrics:
    """质量指标"""
    file_path: str
    total_lines: int = 0
    blank_lines: int = 0
    comment_lines: int = 0
    function_count: int = 0
    class_count: int = 0
    cyclomatic_complexity: int = 1
    halstead_volume: float = 0.0
    maintainability_index: float = 0.0
    code_duplication: float = 0.0
    longest_function: int = 0
    average_function_length: float = 0.0


@dataclass
class RefactoringSuggestion:
    """重构建议"""
    file_path: str
    line_number: int
    severity: str  # low | medium | high | critical
    category: str  # complexity | duplication | naming | security | performance
    description: str
    suggestion: str


# ═══════════════════════════════════════════════════════════════════════
# 1. GitAnalyzer — Git 仓库分析器
# ═══════════════════════════════════════════════════════════════════════

_EXT_TO_LANG: Dict[str, str] = {
    '.py': 'Python', '.js': 'JavaScript', '.ts': 'TypeScript',
    '.vue': 'Vue', '.java': 'Java', '.cpp': 'C++', '.c': 'C',
    '.go': 'Go', '.rs': 'Rust', '.tsx': 'TypeScript React',
    '.jsx': 'JavaScript React', '.html': 'HTML', '.css': 'CSS',
    '.md': 'Markdown', '.json': 'JSON', '.yaml': 'YAML',
    '.yml': 'YAML', '.xml': 'XML', '.sql': 'SQL',
    '.sh': 'Shell', '.bat': 'Batch', '.txt': 'Text',
    '.kt': 'Kotlin', '.swift': 'Swift', '.dart': 'Dart',
}


def _safe_run(cmd: str, cwd: str) -> str:
    """安全执行 shell 命令"""
    try:
        result = subprocess.run(
            cmd, cwd=cwd, shell=True, capture_output=True,
            text=True, encoding='utf-8', errors='replace',
        )
        return result.stdout.strip()
    except Exception:
        return ""


class GitAnalyzer:
    """Git 仓库分析器 — 提交历史、贡献者、热点识别"""

    def __init__(self, repo_path: str):
        self._repo_path = Path(repo_path)
        if not self._repo_path.exists():
            raise ValueError(f"仓库路径不存在: {self._repo_path}")
        if not (self._repo_path / ".git").exists():
            raise ValueError(f"不是有效的 Git 仓库: {self._repo_path}")
        self._commits_cache: Dict[str, CommitInfo] = {}
        self._contributors_cache: Dict[str, Contributor] = {}
        self._file_history_cache: Dict[str, FileHistory] = {}

    def _run(self, cmd: str) -> str:
        return _safe_run(cmd, str(self._repo_path))

    # ── 仓库信息 ──

    def get_repo_info(self) -> Dict[str, Any]:
        """获取仓库基本信息"""
        return {
            "name": self._repo_path.name,
            "path": str(self._repo_path),
            "branch": self._run("git rev-parse --abbrev-ref HEAD"),
            "remote_url": self._run("git config --get remote.origin.url"),
            "last_commit": self._run("git rev-parse HEAD")[:7],
        }

    def get_repository_stats(self) -> RepositoryStats:
        """获取仓库完整统计"""
        commits = self.get_commits()
        contributors = self.get_contributors()

        lines_output = self._run(
            "git ls-files | xargs wc -l | tail -1 | awk '{print $1}'"
        )
        total_lines = int(lines_output) if lines_output.isdigit() else 0

        files_output = self._run("git ls-files | wc -l")
        total_files = int(files_output) if files_output.isdigit() else 0

        hotspots = self.get_hotspots(1)
        top_files = [(h.file_path, h.change_frequency) for h in hotspots[:10]]

        activity_trend: Dict[str, int] = defaultdict(int)
        for c in commits:
            activity_trend[c.date.strftime("%Y-%m")] += 1

        languages = self._detect_languages()

        return RepositoryStats(
            total_commits=len(commits),
            total_files=total_files,
            total_lines=total_lines,
            contributors=contributors,
            top_files=top_files,
            activity_trend=dict(activity_trend),
            languages=languages,
        )

    # ── 提交历史 ──

    def get_commits(self, limit: int = 100) -> List[CommitInfo]:
        """获取提交历史"""
        output = self._run(
            f"git log --oneline --format='%H|%an|%ae|%ad|%s' --numstat -n {limit}"
        )
        commits: List[CommitInfo] = []
        lines = output.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1; continue
            parts = line.split('|')
            if len(parts) >= 5:
                try:
                    commit_date = datetime.strptime(parts[3], "%a %b %d %H:%M:%S %Y %z")
                except ValueError:
                    commit_date = datetime.now()

                insertions = deletions = files_changed = 0
                i += 1
                while i < len(lines) and lines[i].strip() and not lines[i].startswith('|'):
                    stat_parts = lines[i].strip().split('\t')
                    if len(stat_parts) >= 3:
                        try:
                            insertions += int(stat_parts[0]) if stat_parts[0] != '-' else 0
                            deletions += int(stat_parts[1]) if stat_parts[1] != '-' else 0
                            files_changed += 1
                        except ValueError:
                            pass
                    i += 1

                commits.append(CommitInfo(
                    hash=parts[0][:7], author=parts[1], email=parts[2],
                    date=commit_date, message='|'.join(parts[4:]),
                    files_changed=files_changed,
                    insertions=insertions, deletions=deletions,
                ))
            else:
                i += 1

        self._commits_cache = {c.hash: c for c in commits}
        return commits

    def search_by_message(self, pattern: str) -> List[CommitInfo]:
        """按提交消息搜索"""
        output = self._run(
            f"git log --oneline --format='%H|%an|%ae|%ad|%s' --grep='{pattern}'"
        )
        commits = []
        for line in output.split('\n'):
            if not line.strip():
                continue
            parts = line.strip().split('|')
            if len(parts) >= 5:
                try:
                    d = datetime.strptime(parts[3], "%a %b %d %H:%M:%S %Y %z")
                except ValueError:
                    d = datetime.now()
                commits.append(CommitInfo(
                    hash=parts[0][:7], author=parts[1], email=parts[2],
                    date=d, message=parts[4], files_changed=0,
                ))
        return commits

    # ── 贡献者 ──

    def get_contributors(self) -> List[Contributor]:
        """获取贡献者列表"""
        output = self._run("git log --format='%an|%ae' | sort -u")
        contributors: List[Contributor] = []
        seen: Set[str] = set()
        for line in output.split('\n'):
            line = line.strip()
            if not line or line in seen:
                continue
            seen.add(line)
            parts = line.split('|')
            if len(parts) >= 2:
                stats = self._get_contributor_stats(parts[0], parts[1])
                contributors.append(Contributor(
                    name=parts[0], email=parts[1],
                    commits=stats['commits'],
                    insertions=stats['insertions'],
                    deletions=stats['deletions'],
                    files_touched=stats['files_touched'],
                ))
        contributors.sort(key=lambda c: c.commits, reverse=True)
        self._contributors_cache = {c.email: c for c in contributors}
        return contributors

    def _get_contributor_stats(self, name: str, email: str) -> Dict[str, int]:
        commits_out = self._run(f"git log --author='{name}' --oneline | wc -l")
        commits = int(commits_out) if commits_out.isdigit() else 0
        stats_out = self._run(
            f"git log --author='{name}' --numstat --format='' | "
            "awk '{insert+=$1; delete+=$2; files++} END {print insert, delete, files}'"
        )
        parts = stats_out.split()
        return {
            "commits": commits,
            "insertions": int(parts[0]) if len(parts) > 0 else 0,
            "deletions": int(parts[1]) if len(parts) > 1 else 0,
            "files_touched": int(parts[2]) if len(parts) > 2 else 0,
        }

    # ── 文件历史 ──

    def get_file_history(self, file_path: str) -> FileHistory:
        """获取文件历史"""
        if file_path in self._file_history_cache:
            return self._file_history_cache[file_path]

        output = self._run(
            f"git log --oneline --format='%H|%an|%ad|%s' -- '{file_path}'"
        )
        commits: List[CommitInfo] = []
        authors: Set[str] = set()

        for line in output.split('\n'):
            if not line.strip():
                continue
            parts = line.strip().split('|')
            if len(parts) >= 4:
                try:
                    d = datetime.strptime(parts[2], "%a %b %d %H:%M:%S %Y %z")
                except ValueError:
                    d = datetime.now()
                commits.append(CommitInfo(
                    hash=parts[0][:7], author=parts[1], email="",
                    date=d, message=parts[3], files_changed=1,
                ))
                authors.add(parts[1])

        last_modified = commits[0].date if commits else datetime.now()
        history = FileHistory(
            file_path=file_path, commits=commits,
            authors=list(authors), total_changes=len(commits),
            last_modified=last_modified,
        )
        self._file_history_cache[file_path] = history
        return history

    def get_change_history(self, file_path: str,
                           since_date: Optional[datetime] = None) -> List[CommitInfo]:
        """获取文件变更历史（可指定日期范围）"""
        history = self.get_file_history(file_path)
        if since_date:
            return [c for c in history.commits if c.date >= since_date]
        return history.commits

    def get_blame(self, file_path: str) -> Dict[int, Tuple[str, str, str]]:
        """获取文件 blame 信息"""
        output = self._run(f"git blame --line-porcelain '{file_path}'")
        blame: Dict[int, Tuple[str, str, str]] = {}
        cur_line = 0
        cur_author = cur_hash = cur_date = ""

        for line in output.split('\n'):
            if line.startswith('author '):
                cur_author = line[7:]
            elif line.startswith('committer-time '):
                try:
                    ts = int(line[16:])
                    cur_date = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
                except ValueError:
                    cur_date = ""
            elif line.startswith(' ') or line.startswith('\t'):
                cur_line += 1
                blame[cur_line] = (cur_hash[:7], cur_author, cur_date)
            elif line and ' ' not in line:
                cur_hash = line
        return blame

    # ── 热点识别 ──

    def get_hotspots(self, threshold: int = 10) -> List[HotspotInfo]:
        """识别代码热点"""
        output = self._run(
            "git log --numstat --format='' | awk '{print $3}' | sort | uniq -c | sort -rn"
        )
        hotspots = []
        for line in output.split('\n'):
            if not line.strip():
                continue
            parts = line.split()
            if len(parts) >= 2:
                count = int(parts[0])
                file_path = ' '.join(parts[1:])
                if count >= threshold:
                    recent = self._is_recently_modified(file_path)
                    complexity = self._estimate_complexity(file_path, count)
                    risk = self._calculate_risk(count, complexity, recent)
                    hotspots.append(HotspotInfo(
                        file_path=file_path, change_frequency=count,
                        recent_activity=recent, complexity=complexity,
                        risk_level=risk,
                    ))
        return hotspots

    def _is_recently_modified(self, file_path: str) -> bool:
        history = self.get_file_history(file_path)
        if history.commits and history.last_modified:
            return (datetime.now() - history.last_modified).days <= 30
        return False

    def _estimate_complexity(self, file_path: str, change_count: int) -> int:
        complexity = 1
        if change_count > 50:
            complexity += 3
        elif change_count > 20:
            complexity += 2
        if file_path.endswith(('.py', '.java', '.cpp', '.ts', '.go', '.rs', '.kt', '.swift')):
            complexity += 2
        elif file_path.endswith(('.js', '.tsx', '.vue', '.dart')):
            complexity += 1
        return complexity

    def _calculate_risk(self, change_freq: int, complexity: int, recent: bool) -> str:
        score = (3 if change_freq > 50 else 2 if change_freq > 20 else 1)
        score += complexity + (1 if recent else 0)
        if score >= 8: return "critical"
        if score >= 6: return "high"
        if score >= 4: return "medium"
        return "low"

    def _detect_languages(self) -> Dict[str, float]:
        output = self._run("git ls-files")
        lang_counts: Dict[str, int] = defaultdict(int)
        total = 0
        for line in output.split('\n'):
            line = line.strip()
            if not line:
                continue
            ext = Path(line).suffix.lower()
            if ext:
                lang_counts[_EXT_TO_LANG.get(ext, 'Other')] += 1
                total += 1
        if total == 0:
            return {}
        return {lang: count / total for lang, count in lang_counts.items()}


# ═══════════════════════════════════════════════════════════════════════
# 2. CodeAnalyzer — AST 代码结构分析器
# ═══════════════════════════════════════════════════════════════════════

class CodeAnalyzer:
    """代码分析器 — AST 解析，提取函数、类、依赖关系"""

    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)
        self.entities: Dict[str, CodeEntity] = {}
        self.relations: List[CodeRelation] = []
        self.file_structures: Dict[str, FileStructure] = {}
        self.entity_by_name: Dict[str, List[CodeEntity]] = {}

    def analyze_project(self) -> None:
        """分析整个项目"""
        self.entities.clear()
        self.relations.clear()
        self.file_structures.clear()
        self.entity_by_name.clear()

        for root, dirs, files in os.walk(self.repo_path):
            dirs[:] = [d for d in dirs if d not in ('.git', '__pycache__', 'node_modules', 'venv', '.venv', 'dist', 'build')]
            for file in files:
                if file.endswith('.py'):
                    self._analyze_file(os.path.join(root, file))

        self._build_relations()

    def _analyze_file(self, file_path: str) -> None:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            tree = ast.parse(content)
            entities, imports = self._parse_ast(tree, file_path, content)

            for entity in entities:
                self.entities[entity.id] = entity
                if entity.name not in self.entity_by_name:
                    self.entity_by_name[entity.name] = []
                self.entity_by_name[entity.name].append(entity)

            self.file_structures[file_path] = FileStructure(
                file_path=file_path,
                functions=[e for e in entities if e.type in ('function', 'method')],
                classes=[e for e in entities if e.type == 'class'],
                imports=imports,
                dependencies=[imp.name for imp in imports],
            )
        except Exception:
            pass  # 非 Python 文件或语法错误，跳过

    def _parse_ast(self, tree: ast.AST, file_path: str,
                   content: str) -> Tuple[List[CodeEntity], List[CodeEntity]]:
        """解析 AST — 修复: 不再重复处理 ClassDef"""
        entities: List[CodeEntity] = []
        imports: List[CodeEntity] = []
        class_stack: List[CodeEntity] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                parent_id = class_stack[-1].id if class_stack else None
                is_method = bool(class_stack)
                entity = CodeEntity(
                    id=_gen_id(file_path, node.lineno),
                    type='method' if is_method else 'function',
                    name=node.name,
                    file_path=file_path,
                    line_start=node.lineno,
                    line_end=getattr(node, 'end_lineno', node.lineno),
                    docstring=ast.get_docstring(node),
                    parent_id=parent_id,
                    dependencies=self._extract_dependencies(node),
                    decorators=[d.id for d in node.decorator_list if isinstance(d, ast.Name)],
                )
                entities.append(entity)

            elif isinstance(node, ast.ClassDef):
                entity = CodeEntity(
                    id=_gen_id(file_path, node.lineno),
                    type='class',
                    name=node.name,
                    file_path=file_path,
                    line_start=node.lineno,
                    line_end=getattr(node, 'end_lineno', node.lineno),
                    docstring=ast.get_docstring(node),
                    dependencies=self._extract_base_classes(node),
                )
                entities.append(entity)
                class_stack.append(entity)

            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    imports.append(CodeEntity(
                        id=_gen_id(file_path, node.lineno),
                        type='import', name=alias.name,
                        file_path=file_path,
                        line_start=node.lineno, line_end=node.lineno,
                    ))

        return entities, imports

    @staticmethod
    def _extract_dependencies(node: ast.AST) -> List[str]:
        deps: Set[str] = set()
        for child in ast.walk(node):
            if isinstance(child, ast.Name):
                deps.add(child.id)
            elif isinstance(child, ast.Attribute):
                deps.add(child.attr)
        return list(deps)

    @staticmethod
    def _extract_base_classes(node: ast.ClassDef) -> List[str]:
        bases = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                bases.append(base.id)
            elif isinstance(base, ast.Attribute):
                bases.append(base.attr)
        return bases

    def _build_relations(self) -> None:
        """构建实体间关系"""
        for entity in self.entities.values():
            if entity.dependencies:
                for dep_name in entity.dependencies:
                    if dep_name in self.entity_by_name:
                        for target in self.entity_by_name[dep_name]:
                            if target.file_path != entity.file_path:
                                self.relations.append(CodeRelation(
                                    source_id=entity.id,
                                    target_id=target.id,
                                    relation_type='uses',
                                    line_number=entity.line_start,
                                ))

    def get_entity(self, entity_id: str) -> Optional[CodeEntity]:
        return self.entities.get(entity_id)

    def find_by_name(self, name: str) -> List[CodeEntity]:
        return self.entity_by_name.get(name, [])

    def get_file_structure(self, file_path: str) -> Optional[FileStructure]:
        return self.file_structures.get(file_path)

    def get_related_entities(self, entity_id: str) -> List[CodeEntity]:
        related_ids: Set[str] = set()
        for rel in self.relations:
            if rel.source_id == entity_id:
                related_ids.add(rel.target_id)
            elif rel.target_id == entity_id:
                related_ids.add(rel.source_id)
        return [self.entities[eid] for eid in related_ids if eid in self.entities]

    def get_dependency_graph(self, file_path: str) -> Dict[str, Any]:
        structure = self.get_file_structure(file_path)
        if not structure:
            return {}
        exports = []
        internal_deps: List[str] = []
        for func in structure.functions:
            exports.append(func.name)
            if func.dependencies:
                internal_deps.extend(func.dependencies)
        for cls in structure.classes:
            exports.append(cls.name)
            if cls.dependencies:
                internal_deps.extend(cls.dependencies)
        return {
            'file': file_path,
            'imports': [imp.name for imp in structure.imports],
            'exports': exports,
            'internal_deps': list(set(internal_deps)),
        }

    def get_project_overview(self) -> Dict[str, Any]:
        stats: Dict[str, int] = {
            'total_files': len(self.file_structures),
            'total_entities': len(self.entities),
            'total_relations': len(self.relations),
        }
        type_counts: Dict[str, int] = defaultdict(int)
        func_count = 0
        class_count = 0
        for entity in self.entities.values():
            type_counts[entity.type] = type_counts.get(entity.type, 0) + 1
            if entity.type in ('function', 'method'):
                func_count += 1
            elif entity.type == 'class':
                class_count += 1
        stats['total_functions'] = func_count
        stats['total_classes'] = class_count
        stats['entity_types'] = dict(type_counts)
        return stats


def _gen_id(file_path: str, line: int) -> str:
    return hashlib.md5(f"{file_path}:{line}".encode()).hexdigest()


# ═══════════════════════════════════════════════════════════════════════
# 3. CodeSearcher — 智能代码搜索器
# ═══════════════════════════════════════════════════════════════════════

class CodeSearcher:
    """智能代码搜索器 — 倒排索引 + 模糊匹配 + 相似度推荐"""

    def __init__(self, code_analyzer: CodeAnalyzer):
        self.code_analyzer = code_analyzer
        self._inverted_index: Dict[str, List[CodeEntity]] = {}
        self._build_index()

    def _build_index(self) -> None:
        self._inverted_index.clear()
        for entity in self.code_analyzer.entities.values():
            for term in self._extract_terms(entity):
                if term not in self._inverted_index:
                    self._inverted_index[term] = []
                self._inverted_index[term].append(entity)

    @staticmethod
    def _extract_terms(entity: CodeEntity) -> List[str]:
        terms: List[str] = []
        if entity.name:
            terms.extend(entity.name.lower().replace('-', '_').split('_'))
        if entity.docstring:
            for word in re.findall(r'\w+', entity.docstring.lower()):
                if len(word) > 2:
                    terms.append(word)
        if entity.dependencies:
            for dep in entity.dependencies:
                terms.extend(dep.lower().split('_'))
        return list(set(terms))

    def search(self, query: str, limit: int = 10) -> List[SearchResult]:
        """智能搜索代码"""
        results: List[SearchResult] = []
        query_terms = [w for w in re.findall(r'\w+', query.lower()) if len(w) > 1]

        for entity in self.code_analyzer.entities.values():
            score, match_type = self._calculate_score(entity, query_terms, query.lower())
            if score > 0:
                results.append(SearchResult(
                    score=score, entity=entity,
                    snippet=self._get_snippet(entity),
                    match_type=match_type,
                ))

        results.sort(key=lambda x: -x.score)
        return results[:limit]

    @staticmethod
    def _calculate_score(entity: CodeEntity, query_terms: List[str],
                         query_lower: str) -> Tuple[float, str]:
        score = 0.0
        match_type = 'content'
        name_lower = entity.name.lower()

        if query_lower == name_lower:
            score += 10
            match_type = 'name'
        elif query_lower in name_lower:
            score += 5
            match_type = 'name'

        for term in query_terms:
            if term in name_lower:
                score += 2

        if entity.docstring:
            doc_lower = entity.docstring.lower()
            if query_lower in doc_lower:
                score += 3
                match_type = 'docstring'
            for term in query_terms:
                if term in doc_lower:
                    score += 1

        if entity.dependencies:
            for dep in entity.dependencies:
                if query_lower in dep.lower():
                    score += 2
                    match_type = 'dependency'

        for term in query_terms:
            if term == entity.type:
                score += 3

        return score, match_type

    @staticmethod
    def _get_snippet(entity: CodeEntity, context_lines: int = 2) -> str:
        try:
            with open(entity.file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            start = max(0, entity.line_start - 1 - context_lines)
            end = min(len(lines), entity.line_end + context_lines)
            return ''.join(lines[start:end]).strip()[:500]
        except Exception:
            return ""

    def recommend_code(self, context_entity: CodeEntity,
                       limit: int = 5) -> List[CodeRecommendation]:
        """根据上下文推荐相关代码"""
        recommendations: List[CodeRecommendation] = []
        related = self.code_analyzer.get_related_entities(context_entity.id)

        for entity in related:
            relevance = self._calculate_relevance(context_entity, entity)
            if relevance > 0:
                reasons = []
                if context_entity.file_path == entity.file_path:
                    reasons.append("同一文件")
                if context_entity.type == entity.type:
                    reasons.append("相同类型")
                if entity.dependencies and context_entity.name in entity.dependencies:
                    reasons.append("存在依赖关系")
                recommendations.append(CodeRecommendation(
                    entity=entity, relevance=relevance,
                    reason=", ".join(reasons) if reasons else "相关代码",
                ))

        recommendations.sort(key=lambda x: -x.relevance)
        return recommendations[:limit]

    @staticmethod
    def _calculate_relevance(source: CodeEntity, target: CodeEntity) -> float:
        relevance = 0.0
        if source.type == target.type:
            relevance += 2
        if source.file_path == target.file_path:
            relevance += 1
        if target.dependencies and source.name in target.dependencies:
            relevance += 3
        return relevance

    def find_similar_code(self, entity: CodeEntity,
                          limit: int = 5) -> List[SearchResult]:
        """查找相似代码 — 使用 Jaccard 相似度"""
        results: List[SearchResult] = []
        for other in self.code_analyzer.entities.values():
            if other.id == entity.id:
                continue
            similarity = self._calculate_similarity(entity, other)
            if similarity > 0.3:
                results.append(SearchResult(
                    score=similarity, entity=other,
                    snippet=self._get_snippet(other),
                    match_type='similar',
                ))
        results.sort(key=lambda x: -x.score)
        return results[:limit]

    @staticmethod
    def _calculate_similarity(e1: CodeEntity, e2: CodeEntity) -> float:
        """Jaccard 相似度计算"""
        weights = [
            (1.0, lambda: 1.0 if e1.type == e2.type else 0.0),
            (1.0, lambda: 1.0 if e1.name == e2.name else 0.0),
        ]
        if e1.dependencies and e2.dependencies:
            set1, set2 = set(e1.dependencies), set(e2.dependencies)
            jaccard = len(set1 & set2) / len(set1 | set2) if set1 | set2 else 0
            weights.append((2.0, lambda: jaccard))
        if e1.decorators and e2.decorators:
            set1, set2 = set(e1.decorators), set(e2.decorators)
            weights.append((1.0, lambda: 1.0 if set1 & set2 else 0.0))

        total_weight = sum(w for w, _ in weights)
        if total_weight == 0:
            return 0.0
        return sum(w * fn() for w, fn in weights) / total_weight


# ═══════════════════════════════════════════════════════════════════════
# 4. QualityAnalyzer — 代码质量分析器
# ═══════════════════════════════════════════════════════════════════════

class QualityAnalyzer:
    """代码质量分析器 — 复杂度、可维护性、重构建议、安全检查"""

    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)

    def analyze_file(self, file_path: str) -> Optional[QualityMetrics]:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            lines = content.split('\n')
            tree = ast.parse(content)
            return self._calculate_metrics(lines, tree, content, file_path)
        except Exception:
            return None

    def analyze_project(self) -> Dict[str, QualityMetrics]:
        results: Dict[str, QualityMetrics] = {}
        for root, dirs, files in os.walk(self.repo_path):
            dirs[:] = [d for d in dirs if d not in ('.git', '__pycache__', 'node_modules', 'venv')]
            for file in files:
                if file.endswith('.py'):
                    fp = os.path.join(root, file)
                    metrics = self.analyze_file(fp)
                    if metrics:
                        results[fp] = metrics
        return results

    def _calculate_metrics(self, lines: List[str], tree: ast.AST,
                           content: str, file_path: str) -> QualityMetrics:
        """计算质量指标 — 修复: file_path 使用实际路径"""
        total_lines = len(lines)
        blank_lines = sum(1 for line in lines if line.strip() == "")
        comment_lines = sum(1 for line in lines if line.strip().startswith('#'))

        func_count = 0
        class_count = 0
        total_func_len = 0
        longest_func = 0
        complexity = 1

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                func_count += 1
                func_len = getattr(node, 'end_lineno', node.lineno) - node.lineno + 1
                total_func_len += func_len
                longest_func = max(longest_func, func_len)
                complexity += self._count_complexity(node)
            elif isinstance(node, ast.ClassDef):
                class_count += 1

        avg_func_len = total_func_len / func_count if func_count > 0 else 0
        halstead = self._calculate_halstead(tree)
        mi = self._calculate_maintainability(total_lines, comment_lines, complexity, halstead)
        duplication = self._calculate_duplication(lines)

        return QualityMetrics(
            file_path=file_path,
            total_lines=total_lines,
            blank_lines=blank_lines,
            comment_lines=comment_lines,
            function_count=func_count,
            class_count=class_count,
            cyclomatic_complexity=complexity,
            halstead_volume=halstead,
            maintainability_index=mi,
            code_duplication=duplication,
            longest_function=longest_func,
            average_function_length=avg_func_len,
        )

    @staticmethod
    def _count_complexity(node: ast.AST) -> int:
        count = 0
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.For, ast.While, ast.And, ast.Or, ast.IfExp)):
                count += 1
            elif isinstance(child, ast.Try):
                count += len(child.handlers)
        return count

    @staticmethod
    def _calculate_halstead(tree: ast.AST) -> float:
        operators: Set[str] = set()
        operands: Set[str] = set()
        op_cnt = 0
        on_cnt = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.operator):
                operators.add(type(node).__name__)
                op_cnt += 1
            elif isinstance(node, ast.Constant):
                operands.add(str(node.value))
                on_cnt += 1
            elif isinstance(node, ast.Name):
                operands.add(node.id)
                on_cnt += 1
        if len(operators) == 0 or len(operands) == 0:
            return 0.0
        vocabulary = len(operators) + len(operands)
        return float((op_cnt + on_cnt) * vocabulary.bit_length())

    @staticmethod
    def _calculate_maintainability(total_lines: int, comment_lines: int,
                                    complexity: int, halstead: float) -> float:
        if total_lines == 0:
            return 0.0
        comment_ratio = comment_lines / total_lines
        mi = max(0.0, 171 - 5.2 * (halstead / total_lines) - 0.23 * complexity - 16.2 * comment_ratio)
        return mi

    @staticmethod
    def _calculate_duplication(lines: List[str]) -> float:
        stripped = [line.strip() for line in lines if line.strip()]
        unique = set(stripped)
        return 1.0 - (len(unique) / len(stripped)) if stripped else 0.0

    def get_refactoring_suggestions(self, file_path: str) -> List[RefactoringSuggestion]:
        suggestions: List[RefactoringSuggestion] = []
        metrics = self.analyze_file(file_path)
        if not metrics:
            return suggestions

        if metrics.cyclomatic_complexity > 15:
            suggestions.append(RefactoringSuggestion(
                file_path=file_path, line_number=1, severity='high',
                category='complexity',
                description=f"文件圈复杂度过高 ({metrics.cyclomatic_complexity})",
                suggestion="建议拆分函数，降低单个函数复杂度",
            ))
        if metrics.code_duplication > 0.3:
            suggestions.append(RefactoringSuggestion(
                file_path=file_path, line_number=1, severity='medium',
                category='duplication',
                description=f"代码重复率较高 ({metrics.code_duplication:.1%})",
                suggestion="建议抽取公共代码为函数或类",
            ))
        if metrics.average_function_length > 50:
            suggestions.append(RefactoringSuggestion(
                file_path=file_path, line_number=1, severity='medium',
                category='complexity',
                description=f"平均函数长度过长 ({metrics.average_function_length:.1f}行)",
                suggestion="建议拆分过长的函数",
            ))
        if metrics.maintainability_index < 65:
            suggestions.append(RefactoringSuggestion(
                file_path=file_path, line_number=1, severity='high',
                category='complexity',
                description=f"可维护性指数较低 ({metrics.maintainability_index:.1f})",
                suggestion="建议增加注释，降低复杂度",
            ))

        suggestions.extend(self._check_naming(file_path))
        suggestions.extend(self._check_security(file_path))
        return suggestions

    def _check_naming(self, file_path: str) -> List[RefactoringSuggestion]:
        suggestions: List[RefactoringSuggestion] = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                tree = ast.parse(f.read())
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    if not node.name.islower() or ('_' not in node.name and len(node.name) > 1):
                        suggestions.append(RefactoringSuggestion(
                            file_path=file_path, line_number=node.lineno,
                            severity='low', category='naming',
                            description=f"函数 '{node.name}' 命名不符合 snake_case 规范",
                            suggestion="建议使用 snake_case 命名规范",
                        ))
                elif isinstance(node, ast.ClassDef):
                    if not node.name[0].isupper():
                        suggestions.append(RefactoringSuggestion(
                            file_path=file_path, line_number=node.lineno,
                            severity='low', category='naming',
                            description=f"类 '{node.name}' 命名不符合 PascalCase 规范",
                            suggestion="建议使用 PascalCase 命名规范",
                        ))
        except Exception:
            pass
        return suggestions

    def _check_security(self, file_path: str) -> List[RefactoringSuggestion]:
        suggestions: List[RefactoringSuggestion] = []
        patterns = [
            (r'eval\(', 'eval函数使用', 'high'),
            (r'exec\(', 'exec函数使用', 'high'),
            (r'os\.system\(', 'os.system调用', 'medium'),
            (r'subprocess\.Popen\(', 'subprocess调用', 'medium'),
            (r'pickle\.load', 'pickle反序列化', 'high'),
            (r'__reduce__', 'pickle魔术方法', 'high'),
        ]
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            for pattern, desc, severity in patterns:
                for match in re.finditer(pattern, content):
                    line_num = content.count('\n', 0, match.start()) + 1
                    suggestions.append(RefactoringSuggestion(
                        file_path=file_path, line_number=line_num,
                        severity=severity, category='security',
                        description=f"检测到 {desc}",
                        suggestion="请确认此代码是否安全，避免使用危险函数",
                    ))
        except Exception:
            pass
        return suggestions

    def get_project_quality_summary(self) -> Dict[str, Any]:
        all_metrics = self.analyze_project()
        if not all_metrics:
            return {}
        values = list(all_metrics.values())
        return {
            'total_files': len(all_metrics),
            'average_complexity': sum(m.cyclomatic_complexity for m in values) / len(values),
            'average_maintainability': sum(m.maintainability_index for m in values) / len(values),
            'average_duplication': sum(m.code_duplication for m in values) / len(values),
            'high_risk_files': sum(1 for m in values if m.cyclomatic_complexity > 15),
            'low_maintainability_files': sum(1 for m in values if m.maintainability_index < 65),
        }


# ═══════════════════════════════════════════════════════════════════════
# 5. GitNexus — 统一代码智能引擎入口
# ═══════════════════════════════════════════════════════════════════════

class GitNexus:
    """GitNexus — 代码智能引擎，整合 Git 分析 + 代码分析 + 搜索 + 质量"""

    def __init__(self, repo_path: str = "."):
        self.repo_path = Path(repo_path).resolve()
        self.git_analyzer: Optional[GitAnalyzer] = None
        self.code_analyzer: Optional[CodeAnalyzer] = None
        self.code_searcher: Optional[CodeSearcher] = None
        self.quality_analyzer: Optional[QualityAnalyzer] = None
        self._initialized = False

    def initialize(self) -> bool:
        """初始化所有分析器"""
        try:
            rp = str(self.repo_path)
            self.git_analyzer = GitAnalyzer(rp)
            self.code_analyzer = CodeAnalyzer(rp)
            self.code_analyzer.analyze_project()
            self.code_searcher = CodeSearcher(self.code_analyzer)
            self.quality_analyzer = QualityAnalyzer(rp)
            self._initialized = True
            return True
        except Exception as e:
            print(f"GitNexus 初始化失败: {e}")
            return False

    def ensure_initialized(self) -> None:
        if not self._initialized:
            self.initialize()

    # ── Git 仓库分析 ──

    def get_repo_info(self) -> Dict[str, Any]:
        self.ensure_initialized()
        return self.git_analyzer.get_repo_info() if self.git_analyzer else {}

    def get_commits(self, limit: int = 100) -> List[CommitInfo]:
        self.ensure_initialized()
        return self.git_analyzer.get_commits(limit) if self.git_analyzer else []

    def get_contributors(self) -> List[Contributor]:
        self.ensure_initialized()
        return self.git_analyzer.get_contributors() if self.git_analyzer else []

    def get_file_history(self, file_path: str) -> Optional[FileHistory]:
        self.ensure_initialized()
        return self.git_analyzer.get_file_history(file_path) if self.git_analyzer else None

    def get_hotspots(self, threshold: int = 10) -> List[HotspotInfo]:
        self.ensure_initialized()
        return self.git_analyzer.get_hotspots(threshold) if self.git_analyzer else []

    def get_repository_stats(self) -> Optional[RepositoryStats]:
        self.ensure_initialized()
        return self.git_analyzer.get_repository_stats() if self.git_analyzer else None

    def search_commits(self, pattern: str) -> List[CommitInfo]:
        self.ensure_initialized()
        return self.git_analyzer.search_by_message(pattern) if self.git_analyzer else []

    def get_blame(self, file_path: str) -> Dict[int, Any]:
        self.ensure_initialized()
        return self.git_analyzer.get_blame(file_path) if self.git_analyzer else {}

    # ── 代码结构分析 ──

    def get_project_overview(self) -> Dict[str, Any]:
        self.ensure_initialized()
        return self.code_analyzer.get_project_overview() if self.code_analyzer else {}

    def get_file_structure(self, file_path: str) -> Optional[FileStructure]:
        self.ensure_initialized()
        return self.code_analyzer.get_file_structure(file_path) if self.code_analyzer else None

    def get_entity(self, entity_id: str) -> Optional[CodeEntity]:
        self.ensure_initialized()
        return self.code_analyzer.get_entity(entity_id) if self.code_analyzer else None

    def find_by_name(self, name: str) -> List[CodeEntity]:
        self.ensure_initialized()
        return self.code_analyzer.find_by_name(name) if self.code_analyzer else []

    def get_dependency_graph(self, file_path: str) -> Dict[str, Any]:
        self.ensure_initialized()
        return self.code_analyzer.get_dependency_graph(file_path) if self.code_analyzer else {}

    # ── 智能搜索 ──

    def search_code(self, query: str, limit: int = 10) -> List[SearchResult]:
        self.ensure_initialized()
        return self.code_searcher.search(query, limit) if self.code_searcher else []

    def recommend_code(self, entity_id: str, limit: int = 5) -> List[CodeRecommendation]:
        self.ensure_initialized()
        if self.code_searcher and self.code_analyzer:
            entity = self.code_analyzer.get_entity(entity_id)
            if entity:
                return self.code_searcher.recommend_code(entity, limit)
        return []

    def find_similar_code(self, entity_id: str, limit: int = 5) -> List[SearchResult]:
        self.ensure_initialized()
        if self.code_searcher and self.code_analyzer:
            entity = self.code_analyzer.get_entity(entity_id)
            if entity:
                return self.code_searcher.find_similar_code(entity, limit)
        return []

    # ── 质量分析 ──

    def analyze_file_quality(self, file_path: str) -> Optional[QualityMetrics]:
        self.ensure_initialized()
        return self.quality_analyzer.analyze_file(file_path) if self.quality_analyzer else None

    def analyze_project_quality(self) -> Dict[str, QualityMetrics]:
        self.ensure_initialized()
        return self.quality_analyzer.analyze_project() if self.quality_analyzer else {}

    def get_refactoring_suggestions(self, file_path: str) -> List[RefactoringSuggestion]:
        self.ensure_initialized()
        return self.quality_analyzer.get_refactoring_suggestions(file_path) if self.quality_analyzer else []

    def get_project_quality_summary(self) -> Dict[str, Any]:
        self.ensure_initialized()
        return self.quality_analyzer.get_project_quality_summary() if self.quality_analyzer else {}

    # ── 综合分析 ──

    def get_comprehensive_report(self) -> Dict[str, Any]:
        self.ensure_initialized()
        report: Dict[str, Any] = {
            'repo_info': self.get_repo_info(),
            'stats': {},
            'quality': {},
            'code_overview': {},
        }
        if self.git_analyzer:
            report['stats'] = {
                'commits': len(self.get_commits(1000)),
                'contributors': len(self.get_contributors()),
                'hotspots': len(self.get_hotspots()),
            }
        if self.code_analyzer:
            report['code_overview'] = self.get_project_overview()
        if self.quality_analyzer:
            report['quality'] = self.get_project_quality_summary()
        return report

    def refresh(self) -> None:
        self._initialized = False
        self.initialize()

    def __repr__(self) -> str:
        return f"GitNexus(repo_path='{self.repo_path}', initialized={self._initialized})"


# ═══════════════════════════════════════════════════════════════════════
# 便捷工厂
# ═══════════════════════════════════════════════════════════════════════

def create_git_nexus(repo_path: str = ".") -> GitNexus:
    """创建并初始化 GitNexus 实例"""
    nexus = GitNexus(repo_path)
    nexus.initialize()
    return nexus
