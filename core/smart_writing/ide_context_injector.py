"""
IDE 上下文注入器
================

感知项目结构、活跃文件，自动注入相关上下文到 AI。

核心功能:
1. 项目结构感知 - 目录树、语言统计、技术栈检测
2. 活跃文件追踪 - 当前编辑的文件、最近修改的文件
3. 上下文注入策略 - 按需加载、智能压缩、相关性排序

使用方式:
    from core.smart_writing.ide_context_injector import IDEContextInjector

    injector = IDEContextInjector(project_root="/path/to/project")
    
    # 获取当前上下文
    context = injector.get_context(
        active_file="/path/to/file.py",
        query="帮我重构这个函数"
    )
    
    # 注入到 Agent
    chat.set_ide_context(context)
"""

import os
import re
import json
import time
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import threading

# ============== 配置 ==============

# 忽略的目录
IGNORE_DIRS = {
    '.git', '.svn', '.hg', 'node_modules', '__pycache__', '.pytest_cache',
    'venv', '.venv', 'env', '.env', 'build', 'dist', '.egg-info',
    '.idea', '.vscode', '.vs', 'target', 'bin', 'obj', '.gradle',
    '.next', '.nuxt', 'coverage', '.coverage', '.tox', '.mypy_cache',
    '.DS_Store', 'Thumbs.db', '.cache', '.tmp', 'temp'
}

# 忽略的文件
IGNORE_FILES = {
    '.gitignore', '.gitattributes', '.editorconfig', '.prettierrc',
    'package-lock.json', 'yarn.lock', 'poetry.lock', ' Pipfile.lock',
    'requirements.txt', 'setup.py', 'MANIFEST.in', 'Makefile',
    'Dockerfile', '.dockerignore', 'docker-compose.yml'
}

# 语言到扩展名映射
LANGUAGE_EXTENSIONS = {
    'Python': ['.py', '.pyi', '.pyx'],
    'JavaScript': ['.js', '.mjs', '.cjs'],
    'TypeScript': ['.ts', '.tsx'],
    'Java': ['.java'],
    'C#': ['.cs'],
    'C++': ['.cpp', '.cc', '.cxx', '.h', '.hpp'],
    'C': ['.c', '.h'],
    'Go': ['.go'],
    'Rust': ['.rs'],
    'Ruby': ['.rb'],
    'PHP': ['.php'],
    'Swift': ['.swift'],
    'Kotlin': ['.kt', '.kts'],
    'Scala': ['.scala'],
    'HTML': ['.html', '.htm'],
    'CSS': ['.css', '.scss', '.sass', '.less'],
    'SQL': ['.sql'],
    'Shell': ['.sh', '.bash', '.zsh'],
    'PowerShell': ['.ps1', '.psm1'],
    'Markdown': ['.md', '.mdx'],
    'JSON': ['.json'],
    'YAML': ['.yaml', '.yml'],
    'TOML': ['.toml'],
    'XML': ['.xml'],
    'Vue': ['.vue'],
    'Svelte': ['.svelte'],
}

# 扩展名到语言的逆向映射
EXT_TO_LANGUAGE = {}
for lang, exts in LANGUAGE_EXTENSIONS.items():
    for ext in exts:
        EXT_TO_LANGUAGE[ext] = lang

# 配置文件映射
CONFIG_FILES = {
    'package.json': 'JavaScript/Node.js',
    'tsconfig.json': 'TypeScript',
    'pyproject.toml': 'Python',
    'setup.py': 'Python',
    'requirements.txt': 'Python',
    'Pipfile': 'Python',
    'Cargo.toml': 'Rust',
    'go.mod': 'Go',
    'pom.xml': 'Java',
    'build.gradle': 'Java/Kotlin',
    'composer.json': 'PHP',
    'Gemfile': 'Ruby',
    'Dockerfile': 'Docker',
    'docker-compose.yml': 'Docker',
    'Makefile': 'Make',
    '.eslintrc': 'ESLint',
    'prettier.config.js': 'Prettier',
    'webpack.config.js': 'Webpack',
    'vite.config.ts': 'Vite',
    'next.config.js': 'Next.js',
    'nuxt.config.ts': 'Nuxt.js',
}


# ============== 数据类 ==============

@dataclass
class FileNode:
    """文件/目录节点"""
    path: str
    name: str
    is_dir: bool
    size: int = 0
    modified: float = 0
    language: Optional[str] = None
    children: List['FileNode'] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'path': self.path,
            'name': self.name,
            'is_dir': self.is_dir,
            'size': self.size,
            'modified': self.modified,
            'language': self.language,
            'children': [c.to_dict() for c in self.children]
        }


@dataclass
class ProjectStats:
    """项目统计信息"""
    root: str
    total_files: int = 0
    total_dirs: int = 0
    language_counts: Dict[str, int] = field(default_factory=dict)
    config_files: List[str] = field(default_factory=list)
    main_languages: List[Tuple[str, int]] = field(default_factory=list)  # (语言, 文件数)
    tech_stack: List[str] = field(default_factory=list)  # 检测到的技术栈

    def to_dict(self) -> Dict[str, Any]:
        return {
            'root': self.root,
            'total_files': self.total_files,
            'total_dirs': self.total_dirs,
            'language_counts': self.language_counts,
            'main_languages': self.main_languages,
            'tech_stack': self.tech_stack,
        }


@dataclass
class ActiveFile:
    """活跃文件信息"""
    path: str
    content: Optional[str] = None
    cursor_line: int = 0
    cursor_col: int = 0
    selection_start: Optional[Tuple[int, int]] = None
    selection_end: Optional[Tuple[int, int]] = None
    modified: bool = False
    last_access: float = field(default_factory=time.time)
    language: Optional[str] = field(default=None)

    def __post_init__(self):
        if self.language is None:
            self.language = EXT_TO_LANGUAGE.get(Path(self.path).suffix)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'path': self.path,
            'cursor_line': self.cursor_line,
            'cursor_col': self.cursor_col,
            'modified': self.modified,
            'last_access': self.last_access,
            'language': self.language,
        }


@dataclass
class IDEContext:
    """IDE 上下文"""
    project_root: str
    project_stats: ProjectStats
    active_files: List[ActiveFile] = field(default_factory=list)
    file_tree: Optional[FileNode] = None
    recent_files: List[str] = field(default_factory=list)
    imports: Dict[str, List[str]] = field(default_factory=dict)  # 文件 -> 导入的模块
    symbols: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)  # 文件 -> 符号列表
    relevance_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'project_root': self.project_root,
            'stats': self.project_stats.to_dict() if self.project_stats else {},
            'active_files': [f.to_dict() for f in self.active_files],
            'file_tree': self.file_tree.to_dict() if self.file_tree else None,
            'recent_files': self.recent_files,
            'language': self.project_stats.main_languages[0][0] if self.project_stats.main_languages else None,
            'tech_stack': self.project_stats.tech_stack if self.project_stats else [],
        }

    def get_summary(self) -> str:
        """生成上下文摘要"""
        parts = []
        parts.append(f"项目: {self.project_root}")
        if self.project_stats:
            parts.append(f"文件数: {self.project_stats.total_files}")
            if self.project_stats.main_languages:
                langs = ', '.join([f"{l}({c})" for l, c in self.project_stats.main_languages[:3]])
                parts.append(f"语言: {langs}")
            if self.project_stats.tech_stack:
                stack = ', '.join(self.project_stats.tech_stack[:5])
                parts.append(f"技术栈: {stack}")
        if self.active_files:
            active = [Path(f.path).name for f in self.active_files[:3]]
            parts.append(f"活跃: {', '.join(active)}")
        return ' | '.join(parts)


# ============== 主类 ==============

class IDEContextInjector:
    """
    IDE 上下文注入器

    感知项目结构、追踪活跃文件、自动注入相关上下文。
    """

    def __init__(
        self,
        project_root: Optional[str] = None,
        max_tree_depth: int = 5,
        max_file_size: int = 100 * 1024,  # 100KB
        cache_ttl: int = 60,  # 秒
        watch_interval: float = 2.0,  # 秒
    ):
        """
        初始化

        Args:
            project_root: 项目根目录
            max_tree_depth: 文件树最大深度
            max_file_size: 最大读取文件大小
            cache_ttl: 缓存有效期（秒）
            watch_interval: 文件监控间隔
        """
        self.project_root = project_root or os.getcwd()
        self.max_tree_depth = max_tree_depth
        self.max_file_size = max_file_size
        self.cache_ttl = cache_ttl
        self.watch_interval = watch_interval

        # 缓存
        self._stats_cache: Optional[Tuple[ProjectStats, float]] = None
        self._tree_cache: Optional[Tuple[FileNode, float]] = None
        self._lock = threading.RLock()

        # 活跃文件追踪
        self._active_files: Dict[str, ActiveFile] = {}
        self._recent_files: List[str] = []
        self._max_recent = 20

        # 文件监控
        self._watcher_running = False
        self._watcher_thread: Optional[threading.Thread] = None

        # 语言统计
        self._language_patterns = self._compile_language_patterns()

    def _compile_language_patterns(self) -> Dict[str, re.Pattern]:
        """编译语言特征模式"""
        patterns = {}

        # Python 特征
        patterns['Python'] = re.compile(
            r'(^import\s+|^from\s+\w+\s+import\s+|def\s+\w+\s*\(|class\s+\w+.*:|async\s+def\s+|@\w+\s*$)',
            re.MULTILINE
        )

        # JavaScript 特征
        patterns['JavaScript'] = re.compile(
            r'(^const\s+|^let\s+|^var\s+|function\s+\w+\s*\(|=>\s*{|\.then\s*\(|\.catch\s*\(|async\s+function|require\s*\()',
            re.MULTILINE
        )

        # TypeScript 特征
        patterns['TypeScript'] = re.compile(
            r'(:\s*(string|number|boolean|any|void|never|\w+\[\]|Map<|Set<|Promise<)|interface\s+\w+|type\s+\w+\s*=|<\w+>)',
            re.MULTILINE
        )

        # Go 特征
        patterns['Go'] = re.compile(
            r'(^package\s+\w+|func\s+\w+\s*\(|:=\s*|go\s+\w+|chan\s+\w+|defer\s+)',
            re.MULTILINE
        )

        # Rust 特征
        patterns['Rust'] = re.compile(
            r'(^fn\s+\w+|impl\s+\w+|pub\s+(fn|struct|enum)|let\s+mut\s+|->\s*\w+|&\w+::|\bmatch\s+\w+)',
            re.MULTILINE
        )

        return patterns

    # ============== 项目结构感知 ==============

    def scan_project(self) -> ProjectStats:
        """扫描项目，生成统计信息"""
        with self._lock:
            # 检查缓存
            if self._stats_cache:
                stats, timestamp = self._stats_cache
                if time.time() - timestamp < self.cache_ttl:
                    return stats

            stats = ProjectStats(root=self.project_root)
            self._scan_directory(self.project_root, stats, depth=0)

            # 检测技术栈
            stats.tech_stack = self._detect_tech_stack(stats)

            # 排序主语言
            stats.main_languages = sorted(
                stats.language_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )

            # 缓存
            self._stats_cache = (stats, time.time())
            return stats

    def _scan_directory(self, path: str, stats: ProjectStats, depth: int):
        """递归扫描目录"""
        if depth > self.max_tree_depth:
            return

        try:
            for entry in os.scandir(path):
                name = entry.name

                # 忽略隐藏目录和特定目录
                if entry.is_dir():
                    if name.startswith('.') or name in IGNORE_DIRS:
                        continue
                    stats.total_dirs += 1
                    self._scan_directory(entry.path, stats, depth + 1)

                elif entry.is_file():
                    # 忽略特定文件
                    if name.startswith('.') or name in IGNORE_FILES:
                        continue

                    # 统计
                    stats.total_files += 1

                    # 检测语言
                    ext = Path(name).suffix.lower()
                    if ext in EXT_TO_LANGUAGE:
                        lang = EXT_TO_LANGUAGE[ext]
                        stats.language_counts[lang] = stats.language_counts.get(lang, 0) + 1

                    # 检测配置文件
                    if name in CONFIG_FILES:
                        stats.config_files.append(name)

        except PermissionError:
            pass

    def _detect_tech_stack(self, stats: ProjectStats) -> List[str]:
        """从配置文件中检测技术栈"""
        tech_stack = set()

        for config_file in stats.config_files:
            if config_file in CONFIG_FILES:
                tech_stack.add(CONFIG_FILES[config_file])

        # 从语言推断
        if stats.main_languages:
            top_lang = stats.main_languages[0][0]
            lang_to_stack = {
                'Python': ['Python'],
                'JavaScript': ['Node.js'],
                'TypeScript': ['TypeScript', 'Node.js'],
                'Java': ['Java', 'JVM'],
                'Go': ['Go'],
                'Rust': ['Rust'],
            }
            if top_lang in lang_to_stack:
                tech_stack.add(lang_to_stack[top_lang][0])

        return list(tech_stack)[:10]

    def get_file_tree(
        self,
        root: Optional[str] = None,
        depth: Optional[int] = None
    ) -> FileNode:
        """获取文件树"""
        with self._lock:
            root = root or self.project_root

            # 检查缓存
            if root == self.project_root and self._tree_cache:
                tree, timestamp = self._tree_cache
                if time.time() - timestamp < self.cache_ttl:
                    return tree

            tree = self._build_file_tree(root, root, depth or self.max_tree_depth)

            # 缓存
            if root == self.project_root:
                self._tree_cache = (tree, time.time())

            return tree

    def _build_file_tree(self, path: str, root: str, max_depth: int, depth: int = 0) -> FileNode:
        """构建文件树"""
        node = FileNode(
            path=path,
            name=os.path.basename(path) or path,
            is_dir=os.path.isdir(path),
        )

        if depth >= max_depth:
            return node

        try:
            for entry in sorted(os.scandir(path), key=lambda x: (not x.is_dir(), x.name)):
                name = entry.name

                if entry.is_dir():
                    if name.startswith('.') or name in IGNORE_DIRS:
                        continue
                    child = self._build_file_tree(entry.path, root, max_depth, depth + 1)
                    node.children.append(child)

                elif entry.is_file():
                    if name.startswith('.') or name in IGNORE_FILES:
                        continue
                    ext = Path(name).suffix.lower()
                    child_node = FileNode(
                        path=entry.path,
                        name=name,
                        is_dir=False,
                        language=EXT_TO_LANGUAGE.get(ext),
                        size=entry.stat().st_size,
                        modified=entry.stat().st_mtime,
                    )
                    node.children.append(child_node)

        except PermissionError:
            pass

        return node

    # ============== 活跃文件追踪 ==============

    def set_active_file(
        self,
        path: str,
        content: Optional[str] = None,
        cursor_line: int = 0,
        cursor_col: int = 0,
        selection: Optional[Tuple[Tuple[int, int], Tuple[int, int]]] = None,
    ):
        """设置当前活跃文件"""
        path = os.path.abspath(path)

        active = ActiveFile(
            path=path,
            content=content,
            cursor_line=cursor_line,
            cursor_col=cursor_col,
            selection_start=selection[0] if selection else None,
            selection_end=selection[1] if selection else None,
            modified=False,
        )

        self._active_files[path] = active

        # 更新最近文件
        if path in self._recent_files:
            self._recent_files.remove(path)
        self._recent_files.insert(0, path)
        self._recent_files = self._recent_files[:self._max_recent]

    def get_active_files(self) -> List[ActiveFile]:
        """获取所有活跃文件"""
        # 按最后访问时间排序
        sorted_files = sorted(
            self._active_files.values(),
            key=lambda x: x.last_access,
            reverse=True
        )
        return sorted_files

    def get_recent_files(self, limit: int = 10) -> List[str]:
        """获取最近打开的文件"""
        return self._recent_files[:limit]

    def read_file_content(self, path: str, max_lines: int = 500) -> Optional[str]:
        """读取文件内容（带限制）"""
        path = os.path.abspath(path)

        # 检查是否已缓存
        if path in self._active_files:
            cached = self._active_files[path]
            if cached.content:
                return cached.content

        # 读取文件
        try:
            size = os.path.getsize(path)
            if size > self.max_file_size:
                # 截断大文件
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = [f.readline() for _ in range(max_lines)]
                    return ''.join(lines) + f'\n... [文件过大，已截断，前 {max_lines} 行]'
            else:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    return f.read()
        except Exception:
            return None

    # ============== 代码分析 ==============

    def extract_imports(self, content: str, language: str) -> List[str]:
        """提取导入语句"""
        imports = []

        if language == 'Python':
            # import xxx / from xxx import yyy
            for match in re.finditer(r'^(?:from\s+(\S+?)\s+)?import\s+(.+?)$', content, re.MULTILINE):
                module = match.group(1) or match.group(2).split()[0]
                imports.append(module.strip())

        elif language in ('JavaScript', 'TypeScript'):
            # import xxx / require(xxx)
            for match in re.finditer(
                r'^(?:import\s+.*?\s+from\s+[\'"](.+?)[\'"]|require\s*\([\'"](.+?)[\'"]\))',
                content,
                re.MULTILINE
            ):
                module = match.group(1) or match.group(2)
                imports.append(module)

        elif language == 'Go':
            # import "xxx" / import xxx "xxx"
            for match in re.finditer(r'import\s+(?:"(.+?)"|(\S+?)\s+"(.+?)")', content):
                module = match.group(1) or match.group(3)
                imports.append(module)

        elif language == 'Rust':
            # use xxx::yyy;
            for match in re.finditer(r'^use\s+(.+?);', content, re.MULTILINE):
                imports.append(match.group(1))

        return imports

    def extract_symbols(self, content: str, language: str) -> List[Dict[str, Any]]:
        """提取代码符号（函数、类、变量）"""
        symbols = []

        if language == 'Python':
            # 类
            for match in re.finditer(r'^class\s+(\w+)(?:\([^)]*\))?:', content, re.MULTILINE):
                symbols.append({
                    'type': 'class',
                    'name': match.group(1),
                    'line': content[:match.start()].count('\n') + 1,
                })
            # 函数
            for match in re.finditer(r'^(?:async\s+)?def\s+(\w+)\s*\(', content, re.MULTILINE):
                symbols.append({
                    'type': 'function',
                    'name': match.group(1),
                    'line': content[:match.start()].count('\n') + 1,
                })

        elif language == 'JavaScript':
            # 函数声明
            for match in re.finditer(r'^(?:async\s+)?function\s+(\w+)\s*\(', content, re.MULTILINE):
                symbols.append({
                    'type': 'function',
                    'name': match.group(1),
                    'line': content[:match.start()].count('\n') + 1,
                })
            # const/let/var 函数
            for match in re.finditer(r'^(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\([^)]*\)\s*=>', content, re.MULTILINE):
                symbols.append({
                    'type': 'arrow_function',
                    'name': match.group(1),
                    'line': content[:match.start()].count('\n') + 1,
                })

        elif language == 'TypeScript':
            # 类
            for match in re.finditer(r'^class\s+(\w+)(?:\s+extends\s+\w+)?(?:\s+implements\s+[\w,\s]+)?\s*{', content, re.MULTILINE):
                symbols.append({
                    'type': 'class',
                    'name': match.group(1),
                    'line': content[:match.start()].count('\n') + 1,
                })
            # 接口
            for match in re.finditer(r'^interface\s+(\w+)', content, re.MULTILINE):
                symbols.append({
                    'type': 'interface',
                    'name': match.group(1),
                    'line': content[:match.start()].count('\n') + 1,
                })
            # 函数
            for match in re.finditer(r'^function\s+(\w+)\s*\(', content, re.MULTILINE):
                symbols.append({
                    'type': 'function',
                    'name': match.group(1),
                    'line': content[:match.start()].count('\n') + 1,
                })

        return symbols

    # ============== 上下文获取 ==============

    def get_context(
        self,
        active_file: Optional[str] = None,
        query: Optional[str] = None,
        include_content: bool = False,
        max_context_files: int = 5,
    ) -> IDEContext:
        """
        获取 IDE 上下文

        Args:
            active_file: 当前活跃文件
            query: 用户查询（用于相关性排序）
            include_content: 是否包含文件内容
            max_context_files: 最大上下文文件数

        Returns:
            IDEContext 对象
        """
        # 获取项目统计
        stats = self.scan_project()

        # 设置活跃文件
        if active_file:
            content = self.read_file_content(active_file) if include_content else None
            self.set_active_file(active_file, content=content)

        # 获取活跃文件列表
        active_files = self.get_active_files()[:max_context_files]

        # 获取文件树
        file_tree = self.get_file_tree() if include_content else None

        # 获取最近文件
        recent = self.get_recent_files(limit=10)

        # 分析活跃文件的符号
        symbols = {}
        imports = {}
        for af in active_files:
            if af.content:
                lang = af.language or 'Unknown'
                symbols[af.path] = self.extract_symbols(af.content, lang)
                imports[af.path] = self.extract_imports(af.content, lang)

        # 计算相关性分数
        relevance = self._calculate_relevance(active_files, query) if query else 1.0

        return IDEContext(
            project_root=self.project_root,
            project_stats=stats,
            active_files=active_files,
            file_tree=file_tree,
            recent_files=recent,
            imports=imports,
            symbols=symbols,
            relevance_score=relevance,
        )

    def _calculate_relevance(
        self,
        active_files: List[ActiveFile],
        query: str
    ) -> float:
        """计算上下文相关性"""
        if not query:
            return 1.0

        query_lower = query.lower()
        score = 0.5

        # 查询关键词匹配
        keywords = {
            '重构': ['refactor', '重构', '重写', '优化'],
            '调试': ['debug', '调试', 'bug', '修复', '错误'],
            '测试': ['test', '测试', '单元', 'coverage'],
            '新增': ['add', '新增', '创建', '实现', '写'],
            '审查': ['review', '审查', '检查', 'lint'],
        }

        for intent, kws in keywords.items():
            if any(kw in query_lower for kw in kws):
                score += 0.1

        return min(score, 1.0)

    def get_context_for_llm(
        self,
        active_file: Optional[str] = None,
        query: Optional[str] = None,
        max_tokens: int = 4000,
    ) -> str:
        """
        获取适合 LLM 的上下文文本

        Args:
            active_file: 当前活跃文件
            query: 用户查询
            max_tokens: 最大 token 数（估算）

        Returns:
            格式化的上下文文本
        """
        ctx = self.get_context(
            active_file=active_file,
            query=query,
            include_content=True,
        )

        lines = []
        lines.append("## 项目上下文\n")

        # 项目概览
        lines.append(f"**项目根目录**: {ctx.project_root}")
        if ctx.project_stats:
            lines.append(f"**文件总数**: {ctx.project_stats.total_files}")
            if ctx.project_stats.main_languages:
                langs = ', '.join([f"{l}({c})" for l, c in ctx.project_stats.main_languages[:3]])
                lines.append(f"**主要语言**: {langs}")
            if ctx.project_stats.tech_stack:
                lines.append(f"**技术栈**: {', '.join(ctx.project_stats.tech_stack[:5])}")

        # 活跃文件
        if ctx.active_files:
            lines.append("\n**当前活跃文件**:")
            for af in ctx.active_files[:3]:
                lines.append(f"- {os.path.relpath(af.path, ctx.project_root)}")

        # 符号信息
        if ctx.symbols:
            lines.append("\n**文件符号**:")
            for path, syms in list(ctx.symbols.items())[:3]:
                rel_path = os.path.relpath(path, ctx.project_root)
                lines.append(f"\n{rel_path}:")
                for sym in syms[:10]:
                    lines.append(f"  - [{sym['type']}] {sym['name']}")

        # 导入信息
        if ctx.imports:
            lines.append("\n**导入模块**:")
            all_imports = set()
            for imps in ctx.imports.values():
                all_imports.update(imps)
            lines.append(f"{', '.join(list(all_imports)[:20])}")

        return '\n'.join(lines)

    # ============== 文件监控 ==============

    def start_watching(self):
        """启动文件监控"""
        if self._watcher_running:
            return

        self._watcher_running = True
        self._watcher_thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._watcher_thread.start()

    def stop_watching(self):
        """停止文件监控"""
        self._watcher_running = False
        if self._watcher_thread:
            self._watcher_thread.join(timeout=1)

    def _watch_loop(self):
        """文件监控循环"""
        last_modified = {}

        while self._watcher_running:
            try:
                # 检查活跃文件的修改时间
                for path in list(self._active_files.keys()):
                    try:
                        mtime = os.path.getmtime(path)
                        if path in last_modified and mtime > last_modified[path]:
                            # 文件已修改
                            if path in self._active_files:
                                self._active_files[path].modified = True
                                self._active_files[path].last_access = time.time()

                        last_modified[path] = mtime
                    except (FileNotFoundError, OSError):
                        # 文件已删除
                        if path in self._active_files:
                            del self._active_files[path]

                # 无效化缓存
                with self._lock:
                    if self._stats_cache:
                        stats, ts = self._stats_cache
                        if time.time() - ts > self.cache_ttl:
                            self._stats_cache = None

            except Exception:
                pass

            time.sleep(self.watch_interval)

    # ============== 上下文注入到 Agent ==============

    def inject_to_agent(
        self,
        agent,
        active_file: Optional[str] = None,
        query: Optional[str] = None,
    ):
        """
        将上下文注入到 Agent

        Args:
            agent: Agent 实例
            active_file: 当前活跃文件
            query: 用户查询
        """
        if hasattr(agent, '_ide_context'):
            ctx = self.get_context(active_file=active_file, query=query)
            agent._ide_context = ctx

            # 同时更新系统提示
            if hasattr(agent, 'system_prompt'):
                context_text = self.get_context_for_llm(active_file, query)
                agent.system_prompt += f"\n\n{context_text}"

    # ============== 快捷函数 ==============

    @staticmethod
    def quick_context(
        project_root: str,
        active_file: Optional[str] = None,
        query: Optional[str] = None,
    ) -> str:
        """
        快速获取上下文（静态方法）

        Args:
            project_root: 项目根目录
            active_file: 活跃文件
            query: 查询

        Returns:
            上下文文本
        """
        injector = IDEContextInjector(project_root)
        return injector.get_context_for_llm(active_file, query)


# ============== 导出 ==============

__all__ = [
    'IDEContextInjector',
    'IDEContext',
    'ProjectStats',
    'FileNode',
    'ActiveFile',
]
