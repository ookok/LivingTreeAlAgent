"""
Project Analyzer - 项目信息采集器
采集 GitHub 项目和本地项目的完整信息用于匹配分析
"""

import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set
from enum import Enum


class ProjectType(Enum):
    """项目类型"""
    UNKNOWN = "unknown"
    WEB_BACKEND = "web_backend"
    WEB_FRONTEND = "web_frontend"
    FULLSTACK = "fullstack"
    MOBILE = "mobile"
    DESKTOP = "desktop"
    LIBRARY = "library"
    CLI_TOOL = "cli_tool"
    AI_ML = "ai_ml"
    DATA_SCIENCE = "data_science"
    DEVOPS = "devops"
    IDE_PLUGIN = "ide_plugin"


@dataclass
class GitHubMetadata:
    """GitHub 项目元数据"""
    url: str
    owner: str
    repo: str
    name: str
    description: str
    stars: int = 0
    forks: int = 0
    language: str = ""
    topics: List[str] = field(default_factory=list)
    license: str = ""
    created_at: str = ""
    updated_at: str = ""
    default_branch: str = "main"
    open_issues: int = 0
    watchers: int = 0


@dataclass
class DependencyInfo:
    """依赖信息"""
    language: str
    manager: str  # pip, npm, maven, gradle, etc.
    file_path: str
    raw_dependencies: Dict[str, str] = field(default_factory=dict)


@dataclass
class CodeStructure:
    """代码结构"""
    root_files: List[str] = field(default_factory=list)
    directories: List[str] = field(default_factory=list)
    file_count: int = 0
    total_lines: int = 0
    language_distribution: Dict[str, int] = field(default_factory=dict)
    main_directories: Dict[str, int] = field(default_factory=dict)  # dir -> file_count


@dataclass
class ArchitectureInfo:
    """架构信息"""
    pattern: str = "unknown"  # mvc, layered, microservices, monolith, plugin, etc.
    components: List[str] = field(default_factory=list)
    entry_points: List[str] = field(default_factory=list)
    config_patterns: List[str] = field(default_factory=list)
    test_patterns: List[str] = field(default_factory=list)


@dataclass
class BusinessInfo:
    """业务信息"""
    features: List[str] = field(default_factory=list)
    user_types: List[str] = field(default_factory=list)
    integrations: List[str] = field(default_factory=list)
    pain_points: List[str] = field(default_factory=list)


@dataclass
class ProjectData:
    """完整的项目数据"""
    # 元数据
    metadata: Optional[GitHubMetadata] = None
    
    # 技术栈
    project_type: ProjectType = ProjectType.UNKNOWN
    languages: Set[str] = field(default_factory=set)
    frameworks: Set[str] = field(default_factory=set)
    databases: Set[str] = field(default_factory=set)
    tools: Set[str] = field(default_factory=set)
    
    # 代码结构
    structure: CodeStructure = field(default_factory=CodeStructure)
    
    # 架构
    architecture: ArchitectureInfo = field(default_factory=ArchitectureInfo)
    
    # 业务
    business: BusinessInfo = field(default_factory=BusinessInfo)
    
    # 依赖
    dependencies: List[DependencyInfo] = field(default_factory=list)
    
    # 原始数据
    raw_data: Dict = field(default_factory=dict)


class GitHubAnalyzer:
    """GitHub 项目分析器"""
    
    # 常见编程语言
    LANGUAGES = {
        'py': 'Python', 'js': 'JavaScript', 'ts': 'TypeScript', 'java': 'Java',
        'go': 'Go', 'rs': 'Rust', 'cpp': 'C++', 'c': 'C', 'rb': 'Ruby',
        'php': 'PHP', 'swift': 'Swift', 'kt': 'Kotlin', 'cs': 'C#',
        'scala': 'Scala', 'r': 'R', 'lua': 'Lua', 'sh': 'Shell'
    }
    
    # 框架关键词
    FRAMEWORK_PATTERNS = {
        'web_backend': ['django', 'flask', 'fastapi', 'express', 'spring', 'rails', 'laravel', 'asp.net', 'gin', 'echo'],
        'web_frontend': ['react', 'vue', 'angular', 'svelte', 'next', 'nuxt', 'gatsby'],
        'desktop': ['pyqt', 'pyqt5', 'pyqt6', 'tkinter', 'electron', 'tauri', 'wxpython'],
        'mobile': ['flutter', 'react native', 'ionic', 'xamarin'],
        'ai_ml': ['tensorflow', 'pytorch', 'keras', 'scikit', 'transformers', 'langchain'],
        'data': ['pandas', 'numpy', 'spark', 'dask'],
    }
    
    # 数据库关键词
    DB_PATTERNS = {
        'postgresql': ['postgresql', 'postgres', 'psycopg', 'pg-sql'],
        'mysql': ['mysql', 'pymysql', 'sqlalchemy-mysql'],
        'mongodb': ['mongodb', 'pymongo', 'mongodriver'],
        'redis': ['redis', 'redis-py', 'ioredis'],
        'sqlite': ['sqlite', 'aiosqlite', 'sqlcipher'],
        'elasticsearch': ['elasticsearch', 'es-dsl'],
    }
    
    def __init__(self):
        self.github_token = os.environ.get('GITHUB_TOKEN', '')
    
    async def analyze(self, github_url: str) -> ProjectData:
        """分析 GitHub 项目"""
        data = ProjectData()
        
        # 解析 URL
        metadata = self._parse_github_url(github_url)
        if not metadata:
            return data
        
        data.metadata = metadata
        
        # 获取仓库信息
        repo_info = await self._fetch_repo_info(metadata.owner, metadata.repo)
        if repo_info:
            self._update_from_repo_info(data, repo_info)
        
        # 分析 README
        readme_content = await self._fetch_readme(metadata.owner, metadata.repo)
        if readme_content:
            self._analyze_readme(data, readme_content)
        
        # 获取文件结构
        structure = await self._fetch_file_structure(metadata.owner, metadata.repo)
        if structure:
            self._analyze_structure(data, structure)
        
        # 获取依赖文件
        deps = await self._fetch_dependencies(metadata.owner, metadata.repo)
        data.dependencies = deps
        self._analyze_dependencies(data, deps)
        
        # 分析架构模式
        self._analyze_architecture_pattern(data)
        
        return data
    
    def _parse_github_url(self, url: str) -> Optional[GitHubMetadata]:
        """解析 GitHub URL"""
        patterns = [
            r'github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$',
            r'github\.com/([^/]+)/([^/]+?)(?:/tree/[^/]+)?$',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return GitHubMetadata(
                    url=url,
                    owner=match.group(1),
                    repo=match.group(2).replace('.git', '')
                )
        
        return None
    
    async def _fetch_repo_info(self, owner: str, repo: str) -> Dict:
        """获取仓库信息"""
        import aiohttp
        
        url = f"https://api.github.com/repos/{owner}/{repo}"
        headers = {'Accept': 'application/vnd.github.v3+json'}
        if self.github_token:
            headers['Authorization'] = f'token {self.github_token}'
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=10) as resp:
                    if resp.status == 200:
                        return await resp.json()
        except Exception:
            pass
        
        return {}
    
    def _update_from_repo_info(self, data: ProjectData, info: Dict):
        """从仓库信息更新数据"""
        data.metadata.stars = info.get('stargazers_count', 0)
        data.metadata.forks = info.get('forks_count', 0)
        data.metadata.language = info.get('language', '')
        data.metadata.topics = info.get('topics', [])
        data.metadata.license = info.get('license', {}).get('name', '')
        data.metadata.description = info.get('description', '')
        data.metadata.open_issues = info.get('open_issues_count', 0)
        data.metadata.watchers = info.get('watchers_count', 0)
        
        if data.metadata.language:
            data.languages.add(data.metadata.language)
    
    async def _fetch_readme(self, owner: str, repo: str) -> str:
        """获取 README 内容"""
        import aiohttp
        
        # 尝试多种 README 名称
        readme_names = ['README.md', 'README.rst', 'README.txt', 'README']
        
        for name in readme_names:
            url = f"https://api.github.com/repos/{owner}/{repo}/contents/{name}"
            headers = {'Accept': 'application/vnd.github.v3.raw'}
            if self.github_token:
                headers['Authorization'] = f'token {self.github_token}'
            
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers, timeout=10) as resp:
                        if resp.status == 200:
                            return await resp.text()
            except Exception:
                continue
        
        return ""
    
    def _analyze_readme(self, data: ProjectData, content: str):
        """分析 README 内容"""
        content_lower = content.lower()
        
        # 提取特性列表
        feature_patterns = [
            r'[-*]\s*([A-Z][^\n]{10,80})',
            r'\*\*([^*]+)\*\*:',  # **Feature:**
            r'##\s+([A-Z][^\n]+)',  # ## Feature
        ]
        
        for pattern in feature_patterns:
            matches = re.findall(pattern, content)
            for match in matches[:10]:  # 最多10个
                feature = match.strip().strip(':*')
                if len(feature) > 10:
                    data.business.features.append(feature)
        
        # 识别用户类型
        user_patterns = [
            (r'developer[s]?', '开发者'),
            (r'enterprise[s]?', '企业用户'),
            (r'business|company', '企业用户'),
            (r'individual[s]?', '个人用户'),
            (r'data scientist', '数据科学家'),
            (r'machine learning', 'ML工程师'),
        ]
        
        for pattern, user_type in user_patterns:
            if re.search(pattern, content_lower):
                if user_type not in data.business.user_types:
                    data.business.user_types.append(user_type)
        
        # 识别集成
        integrations = ['api', 'webhook', 'oauth', 'sso', 'ldap', 'slack', 'discord']
        for integ in integrations:
            if integ in content_lower:
                data.business.integrations.append(integ)
        
        # 去重
        data.business.features = list(dict.fromkeys(data.business.features))[:20]
    
    async def _fetch_file_structure(self, owner: str, repo: str) -> Dict:
        """获取文件结构"""
        import aiohttp
        
        url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/HEAD?recursive=1"
        headers = {'Accept': 'application/vnd.github.v3+json'}
        if self.github_token:
            headers['Authorization'] = f'token {self.github_token}'
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=15) as resp:
                    if resp.status == 200:
                        return await resp.json()
        except Exception:
            pass
        
        return {}
    
    def _analyze_structure(self, data: ProjectData, tree_data: Dict):
        """分析文件结构"""
        tree = tree_data.get('tree', [])
        
        # 提取目录和文件
        dirs = set()
        files = []
        
        for item in tree:
            path = item.get('path', '')
            if item.get('type') == 'tree':
                dirs.add(path)
            else:
                files.append(path)
        
        # 统计语言分布
        lang_dist = {}
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            lang = self.LANGUAGES.get(ext.lstrip('.'), 'Other')
            lang_dist[lang] = lang_dist.get(lang, 0) + 1
        
        # 提取主要目录
        main_dirs = {}
        for d in dirs:
            parts = d.split('/')
            if len(parts) >= 2:
                top_dir = parts[0]
                main_dirs[top_dir] = main_dirs.get(top_dir, 0) + 1
        
        # 过滤常见无关目录
        skip_dirs = {'.github', 'node_modules', '__pycache__', '.git', 'vendor', 'dist', 'build'}
        for skip in skip_dirs:
            main_dirs.pop(skip, None)
        
        # 排序并取前10
        main_dirs = dict(sorted(main_dirs.items(), key=lambda x: -x[1])[:10])
        
        data.structure = CodeStructure(
            root_files=[f for f in files if '/' not in f],
            directories=list(dirs)[:50],
            file_count=len(files),
            total_lines=len(files) * 200,  # 估算
            language_distribution=lang_dist,
            main_directories=main_dirs
        )
        
        # 识别入口点
        entry_patterns = ['main.py', 'app.py', 'index.js', 'index.ts', 'main.go', 'main.rs', 'main.dart']
        for f in files:
            if any(os.path.basename(f) == ep for ep in entry_patterns):
                data.architecture.entry_points.append(f)
    
    async def _fetch_dependencies(self, owner: str, repo: str) -> List[DependencyInfo]:
        """获取依赖文件"""
        import aiohttp
        
        dep_files = [
            ('requirements.txt', 'pip', 'python'),
            ('setup.py', 'pip', 'python'),
            ('pyproject.toml', 'pip', 'python'),
            ('package.json', 'npm', 'javascript'),
            ('go.mod', 'go', 'go'),
            ('Cargo.toml', 'cargo', 'rust'),
            ('pom.xml', 'maven', 'java'),
            ('build.gradle', 'gradle', 'java'),
            ('Gemfile', 'bundler', 'ruby'),
            ('composer.json', 'composer', 'php'),
        ]
        
        deps = []
        
        for filename, manager, lang in dep_files:
            url = f"https://api.github.com/repos/{owner}/{repo}/contents/{filename}"
            headers = {'Accept': 'application/vnd.github.v3.raw'}
            if self.github_token:
                headers['Authorization'] = f'token {self.github_token}'
            
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers, timeout=10) as resp:
                        if resp.status == 200:
                            content = await resp.text()
                            dep_info = DependencyInfo(
                                language=lang,
                                manager=manager,
                                file_path=filename,
                                raw_dependencies=self._parse_dependencies(content, manager)
                            )
                            deps.append(dep_info)
            except Exception:
                continue
        
        return deps
    
    def _parse_dependencies(self, content: str, manager: str) -> Dict[str, str]:
        """解析依赖文件"""
        deps = {}
        
        if manager == 'pip':
            for line in content.split('\n'):
                line = line.strip()
                if line and not line.startswith('#'):
                    # 处理各种格式: pkg==1.0, pkg>=1.0, pkg~=1.0
                    match = re.match(r'^([a-zA-Z0-9_-]+)(?:[=<>~!]+.*)?', line)
                    if match:
                        deps[match.group(1).lower()] = line
        
        elif manager == 'npm':
            try:
                import json
                data = json.loads(content)
                for name, version in data.get('dependencies', {}).items():
                    deps[name] = version
                for name, version in data.get('devDependencies', {}).items():
                    deps[f"dev:{name}"] = version
            except:
                pass
        
        return deps
    
    def _analyze_dependencies(self, data: ProjectData, deps: List[DependencyInfo]):
        """分析依赖"""
        all_deps = {}
        
        for dep_info in deps:
            for name, version in dep_info.raw_dependencies.items():
                all_deps[name] = version
        
        # 识别框架
        all_deps_str = ' '.join(all_deps.keys()).lower()
        for category, patterns in self.FRAMEWORK_PATTERNS.items():
            for pattern in patterns:
                if pattern in all_deps_str:
                    data.frameworks.add(pattern)
                    break
        
        # 识别数据库
        for db_name, patterns in self.DB_PATTERNS.items():
            for pattern in patterns:
                if pattern in all_deps_str:
                    data.databases.add(db_name)
                    break
        
        # 确定项目类型
        if any(f in all_deps_str for f in ['tensorflow', 'torch', 'transformers', 'langchain']):
            data.project_type = ProjectType.AI_ML
        elif any(f in all_deps_str for f in ['pyqt', 'pyqt5', 'pyqt6', 'tkinter', 'electron']):
            data.project_type = ProjectType.DESKTOP
        elif any(f in all_deps_str for f in ['django', 'flask', 'fastapi', 'express']):
            data.project_type = ProjectType.WEB_BACKEND
        elif any(f in all_deps_str for f in ['react', 'vue', 'angular']):
            data.project_type = ProjectType.WEB_FRONTEND
    
    def _analyze_architecture_pattern(self, data: ProjectData):
        """分析架构模式"""
        dirs = set(data.structure.directories)
        root_files = set(data.structure.root_files)
        main_dirs = data.structure.main_directories
        
        # 插件化模式
        plugin_dirs = ['plugins', 'extensions', 'addons', 'modules', 'integrations']
        if any(d in dirs for d in plugin_dirs):
            data.architecture.pattern = 'plugin'
            data.architecture.components.extend([d for d in plugin_dirs if d in dirs])
        
        # MVC 模式
        mvc_dirs = ['models', 'views', 'controllers']
        mvc_count = sum(1 for d in mvc_dirs if d in dirs)
        if mvc_count >= 2:
            data.architecture.pattern = 'mvc'
        
        # 分层架构
        layered_dirs = ['domain', 'application', 'infrastructure', 'presentation']
        layered_count = sum(1 for d in layered_dirs if d in dirs)
        if layered_count >= 2:
            data.architecture.pattern = 'layered'
        
        # 微服务 (通过目录判断)
        service_indicators = ['service', 'gateway', 'registry', 'config']
        if any(d in dirs for d in service_indicators):
            data.architecture.pattern = 'microservices'
        
        # 单体 (src + 无明确模式)
        if 'src' in dirs and data.architecture.pattern == 'unknown':
            data.architecture.pattern = 'monolith'
        
        # 测试模式
        test_patterns = ['tests', 'test', '__tests__', 'spec']
        data.architecture.test_patterns = [t for t in test_patterns if t in dirs]
        
        # 配置模式
        config_patterns = ['config', 'conf', 'settings', '.github/workflows']
        for pattern in config_patterns:
            if pattern in dirs:
                data.architecture.config_patterns.append(pattern)


class LocalAnalyzer:
    """本地项目分析器"""
    
    def __init__(self, root_path: str):
        self.root_path = Path(root_path)
        self.ignore_dirs = {
            '__pycache__', '.git', '.svn', 'node_modules', '.venv', 'venv',
            'env', '.env', 'dist', 'build', 'out', '.idea', '.vscode',
            'vendor', 'target', 'bin', 'obj', '.cache', '.pytest_cache'
        }
        self.ignore_files = {
            '.DS_Store', 'Thumbs.db', '*.pyc', '*.pyo', '*.so', '*.dll',
            '*.exe', '*.o', '*.a', '*.lib', 'package-lock.json'
        }
    
    def analyze(self) -> ProjectData:
        """分析本地项目"""
        data = ProjectData()
        
        if not self.root_path.exists():
            return data
        
        # 分析项目类型
        data.project_type = self._detect_project_type()
        
        # 收集文件
        all_files = self._collect_files()
        
        # 分析代码结构
        self._analyze_code_structure(data, all_files)
        
        # 分析依赖
        self._analyze_local_dependencies(data)
        
        # 分析架构
        self._analyze_local_architecture(data)
        
        # 分析业务
        self._analyze_local_business(data)
        
        return data
    
    def _detect_project_type(self) -> ProjectType:
        """检测项目类型"""
        root_files = list(self.root_path.iterdir())
        
        # Python 项目
        if any(f.name in ['setup.py', 'pyproject.toml', 'requirements.txt'] for f in root_files if f.is_file()):
            # 检查具体类型
            req_file = self.root_path / 'requirements.txt'
            if req_file.exists():
                content = req_file.read_text(encoding='utf-8', errors='ignore').lower()
                if 'pyqt' in content or 'pyside' in content:
                    return ProjectType.DESKTOP
                if 'tensorflow' in content or 'torch' in content or 'transformers' in content:
                    return ProjectType.AI_ML
                if 'django' in content or 'flask' in content or 'fastapi' in content:
                    return ProjectType.WEB_BACKEND
        
        # JavaScript/TypeScript
        if (self.root_path / 'package.json').exists():
            content = (self.root_path / 'package.json').read_text(encoding='utf-8', errors='ignore').lower()
            if 'electron' in content:
                return ProjectType.DESKTOP
            if 'react' in content or 'vue' in content or 'angular' in content:
                return ProjectType.WEB_FRONTEND
            return ProjectType.WEB_BACKEND
        
        # Java
        if any((self.root_path / f).exists() for f in ['pom.xml', 'build.gradle', 'build.gradle.kts']):
            return ProjectType.WEB_BACKEND
        
        # Go
        if (self.root_path / 'go.mod').exists():
            return ProjectType.WEB_BACKEND
        
        # IDE 插件
        for pattern in ['*.vsix', '*.ideplugin', '.vscodeignore']:
            if list(self.root_path.glob(pattern)):
                return ProjectType.IDE_PLUGIN
        
        return ProjectType.UNKNOWN
    
    def _collect_files(self) -> List[Path]:
        """收集所有源文件"""
        files = []
        
        for root, dirs, filenames in os.walk(self.root_path):
            # 过滤忽略目录
            dirs[:] = [d for d in dirs if d not in self.ignore_dirs]
            
            root_path = Path(root)
            for filename in filenames:
                # 过滤忽略文件
                if any(filename.match(pat) for pat in self.ignore_files):
                    continue
                files.append(root_path / filename)
        
        return files
    
    def _analyze_code_structure(self, data: ProjectData, files: List[Path]):
        """分析代码结构"""
        root_files = []
        dirs = set()
        lang_dist = {}
        main_dirs = {}
        total_lines = 0
        
        for f in files:
            rel_path = f.relative_to(self.root_path)
            
            # 根目录文件
            if len(rel_path.parts) == 1:
                root_files.append(str(rel_path))
            
            # 目录统计
            if len(rel_path.parts) > 1:
                top_dir = rel_path.parts[0]
                if top_dir not in self.ignore_dirs:
                    main_dirs[top_dir] = main_dirs.get(top_dir, 0) + 1
            
            # 目录收集
            if len(rel_path.parts) > 1:
                dirs.add(str(Path(*rel_path.parts[:-1])))
            
            # 语言统计
            ext = f.suffix.lower().lstrip('.')
            lang = {
                'py': 'Python', 'js': 'JavaScript', 'ts': 'TypeScript',
                'java': 'Java', 'go': 'Go', 'rs': 'Rust', 'cpp': 'C++',
                'c': 'C', 'rb': 'Ruby', 'php': 'PHP', 'swift': 'Swift',
                'kt': 'Kotlin', 'cs': 'C#', 'html': 'HTML', 'css': 'CSS',
                'json': 'JSON', 'yaml': 'YAML', 'yml': 'YAML', 'md': 'Markdown',
                'qml': 'QML', 'ui': 'Qt UI', 'tsx': 'TypeScript', 'jsx': 'JavaScript'
            }.get(ext, 'Other')
            
            lang_dist[lang] = lang_dist.get(lang, 0) + 1
            data.languages.add(lang)
            
            # 统计行数 (小文件全读，大文件估算)
            try:
                if f.stat().st_size < 100000:  # < 100KB
                    total_lines += len(f.read_text(encoding='utf-8', errors='ignore').splitlines())
                else:
                    total_lines += f.stat().st_size // 50  # 估算
            except:
                total_lines += 10  # 默认
        
        # 过滤主要目录
        skip = self.ignore_dirs | {'.git', '.github', 'docs', 'examples', 'test'}
        main_dirs = {k: v for k, v in sorted(main_dirs.items(), key=lambda x: -x[1])[:10] if k not in skip}
        
        data.structure = CodeStructure(
            root_files=root_files,
            directories=list(dirs)[:50],
            file_count=len(files),
            total_lines=total_lines,
            language_distribution=lang_dist,
            main_directories=main_dirs
        )
        
        # 入口点
        entry_patterns = ['main.py', 'app.py', '__main__.py', 'index.js', 'main.go']
        for f in files:
            if f.name in entry_patterns:
                data.architecture.entry_points.append(str(f.relative_to(self.root_path)))
    
    def _analyze_local_dependencies(self, data: ProjectData):
        """分析本地依赖"""
        deps = []
        
        # requirements.txt
        req_file = self.root_path / 'requirements.txt'
        if req_file.exists():
            content = req_file.read_text(encoding='utf-8', errors='ignore')
            deps.append(DependencyInfo(
                language='Python',
                manager='pip',
                file_path='requirements.txt',
                raw_dependencies=self._parse_req(content)
            ))
        
        # package.json
        pkg_file = self.root_path / 'package.json'
        if pkg_file.exists():
            try:
                import json
                pkg_data = json.loads(pkg_file.read_text(encoding='utf-8'))
                all_deps = {}
                all_deps.update(pkg_data.get('dependencies', {}))
                all_deps.update({f"dev:{k}": v for k, v in pkg_data.get('devDependencies', {}).items()})
                deps.append(DependencyInfo(
                    language='JavaScript',
                    manager='npm',
                    file_path='package.json',
                    raw_dependencies=all_deps
                ))
            except:
                pass
        
        data.dependencies = deps
        
        # 识别框架和数据库
        all_deps_str = ' '.join(str(d) for dep in deps for d in dep.raw_dependencies.keys()).lower()
        
        # 框架
        frameworks = {
            'pyqt': 'PyQt', 'pyqt5': 'PyQt5', 'pyqt6': 'PyQt6', 'pyside': 'PySide',
            'django': 'Django', 'flask': 'Flask', 'fastapi': 'FastAPI',
            'tensorflow': 'TensorFlow', 'torch': 'PyTorch', 'transformers': 'Transformers',
            'react': 'React', 'vue': 'Vue', 'angular': 'Angular',
            'electron': 'Electron', 'tauri': 'Tauri',
        }
        
        for key, name in frameworks.items():
            if key in all_deps_str:
                data.frameworks.add(name)
        
        # 数据库
        dbs = {
            'psycopg': 'PostgreSQL', 'postgres': 'PostgreSQL', 'mysql': 'MySQL',
            'pymongo': 'MongoDB', 'redis': 'Redis', 'sqlite': 'SQLite',
            'elasticsearch': 'Elasticsearch', 'sqlalchemy': 'SQLAlchemy',
        }
        
        for key, name in dbs.items():
            if key in all_deps_str:
                data.databases.add(name)
    
    def _parse_req(self, content: str) -> Dict[str, str]:
        """解析 requirements.txt"""
        deps = {}
        for line in content.split('\n'):
            line = line.strip()
            if line and not line.startswith('#'):
                match = re.match(r'^([a-zA-Z0-9_-]+)(?:[=<>~!]+.*)?', line)
                if match:
                    deps[match.group(1).lower()] = line
        return deps
    
    def _analyze_local_architecture(self, data: ProjectData):
        """分析本地架构"""
        dirs = set(data.structure.directories)
        main_dirs = data.structure.main_directories
        
        # 插件模式
        plugin_dirs = ['plugins', 'extensions', 'addons', 'modules', 'integrations', 'skills']
        found_plugins = [d for d in plugin_dirs if d in dirs or d in main_dirs]
        if found_plugins:
            data.architecture.pattern = 'plugin'
            data.architecture.components.extend(found_plugins)
        
        # MVC
        mvc_dirs = ['models', 'views', 'controllers', 'view', 'model', 'controller']
        if sum(1 for d in mvc_dirs if d in dirs) >= 2:
            data.architecture.pattern = 'mvc'
        
        # 分层
        layered_dirs = ['domain', 'application', 'infrastructure', 'presentation', 'service', 'repository']
        if sum(1 for d in layered_dirs if d in dirs) >= 2:
            data.architecture.pattern = 'layered'
        
        # 微服务
        service_indicators = ['services', 'service', 'gateway', 'registry']
        if any(d in dirs for d in service_indicators):
            data.architecture.pattern = 'microservices'
        
        # 单体
        if 'src' in dirs and data.architecture.pattern == 'unknown':
            data.architecture.pattern = 'monolith'
        
        # IDE 插件特定
        if data.project_type == ProjectType.IDE_PLUGIN:
            data.architecture.pattern = 'plugin'
            data.architecture.components.extend(['panel', 'action', 'handler', 'adapter'])
        
        # 配置目录
        config_dirs = ['config', 'configs', 'settings', '.github/workflows']
        data.architecture.config_patterns = [d for d in config_dirs if d in dirs]
        
        # 测试目录
        test_patterns = ['tests', 'test', '__tests__', 'spec', 'testing']
        data.architecture.test_patterns = [t for t in test_patterns if t in dirs or t in main_dirs]
    
    def _analyze_local_business(self, data: ProjectData):
        """分析本地业务"""
        # 从 README 和文档提取
        for readme_name in ['README.md', 'README.rst', 'README.txt']:
            readme_file = self.root_path / readme_name
            if readme_file.exists():
                try:
                    content = readme_file.read_text(encoding='utf-8', errors='ignore')
                    self._extract_business_info(data, content)
                except:
                    pass
                break
        
        # 从代码注释提取功能
        self._extract_features_from_code(data)
    
    def _extract_business_info(self, data: ProjectData, content: str):
        """从文档提取业务信息"""
        content_lower = content.lower()
        
        # 特性
        feature_patterns = [
            r'[-*]\s*([A-Z][^\n]{10,80})',
            r'\*\*([^*]+)\*\*:',  
            r'##\s+([A-Z][^\n]+)',  
        ]
        
        for pattern in feature_patterns:
            matches = re.findall(pattern, content)
            for match in matches[:5]:
                feature = match.strip().strip(':*')
                if len(feature) > 10:
                    data.business.features.append(feature)
        
        # 用户类型
        user_patterns = [
            (r'developer[s]?', '开发者'),
            (r'utilisateur[s]?', '用户'),
            (r'个人', '个人用户'),
            (r'企业', '企业用户'),
        ]
        
        for pattern, user_type in user_patterns:
            if re.search(pattern, content_lower):
                if user_type not in data.business.user_types:
                    data.business.user_types.append(user_type)
        
        data.business.features = list(dict.fromkeys(data.business.features))[:15]
    
    def _extract_features_from_code(self, data: ProjectData):
        """从代码提取功能暗示"""
        # 扫描包含 AI/智能 相关的文件
        for pattern in ['**/*agent*.py', '**/*ai*.py', '**/*intent*.py', '**/*evolution*.py']:
            for f in self.root_path.glob(pattern):
                try:
                    content = f.read_text(encoding='utf-8', errors='ignore')[:500]
                    # 简单提取类名和函数名
                    classes = re.findall(r'class\s+(\w+)', content)
                    functions = re.findall(r'def\s+(\w+)', content)
                    
                    for c in classes[:3]:
                        if len(c) > 3:
                            data.business.features.append(f"智能{c.replace('Agent','').replace('Engine','')}")
                    for func in functions[:3]:
                        if len(func) > 3 and 'test' not in func:
                            data.business.features.append(f"执行{func}")
                except:
                    pass
        
        data.business.features = list(dict.fromkeys(data.business.features))[:15]


# 工厂函数
def create_github_analyzer() -> GitHubAnalyzer:
    """创建 GitHub 分析器"""
    return GitHubAnalyzer()


def create_local_analyzer(root_path: str) -> LocalAnalyzer:
    """创建本地分析器"""
    return LocalAnalyzer(root_path)


if __name__ == '__main__':
    # 测试
    import asyncio
    
    async def test():
        analyzer = create_github_analyzer()
        
        # 测试 LivingTreeAI
        result = await analyzer.analyze('https://github.com/username/livingtreeai')
        print(f"Project: {result.metadata.name if result.metadata else 'N/A'}")
        print(f"Type: {result.project_type.value}")
        print(f"Languages: {result.languages}")
        print(f"Frameworks: {result.frameworks}")
        print(f"Architecture: {result.architecture.pattern}")
        print(f"Features: {result.business.features[:5]}")
    
    asyncio.run(test())
