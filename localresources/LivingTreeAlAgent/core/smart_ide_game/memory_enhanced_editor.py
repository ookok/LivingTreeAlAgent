"""
记忆增强编辑器模块
提供代码记忆、项目记忆、领域记忆等功能
"""
import re
import asyncio
import hashlib
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import json
import os


@dataclass
class CodeMemory:
    """代码记忆"""
    id: str
    content: str
    context: str  # 使用上下文
    language: str
    tags: List[str] = field(default_factory=list)
    usage_count: int = 0
    success_count: int = 0
    fail_count: int = 0
    last_used: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    embedding: Optional[List[float]] = None  # 未来用于语义搜索
    file_path: Optional[str] = None  # 来源文件


@dataclass
class ProjectMemory:
    """项目记忆"""
    project_path: str
    project_name: str
    language: str
    structure: Dict[str, str] = field(default_factory=dict)  # 文件路径 -> 类型
    dependencies: List[str] = field(default_factory=list)
    conventions: Dict[str, str] = field(default_factory=dict)  # 命名规范等
    templates: List[str] = field(default_factory=list)
    last_opened: datetime = field(default_factory=datetime.now)
    settings: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DomainMemory:
    """领域记忆"""
    domain: str  # 如: "web", "database", "ai"
    concepts: Dict[str, str] = field(default_factory=dict)  # 概念 -> 定义
    patterns: List[str] = field(default_factory=list)  # 设计模式
    best_practices: List[str] = field(default_factory=list)
    common_errors: Dict[str, str] = field(default_factory=dict)  # 错误 -> 解决方案
    api_examples: Dict[str, str] = field(default_factory=dict)  # API -> 示例


@dataclass
class PersonalStyle:
    """个人编码风格"""
    indentation: str = "    "  # 空格数
    quote_style: str = "double"  # double, single
    naming_convention: str = "snake_case"  # snake_case, camelCase, PascalCase
    bracket_style: str = "same_line"  # same_line, new_line
    import_order: List[str] = field(default_factory=list)
    comment_style: str = "#"  # #, //
    docstring_style: str = "google"  # google, numpy, sphinx


@dataclass
class Snippet:
    """代码片段"""
    id: str
    name: str
    description: str
    code: str
    language: str
    tags: List[str] = field(default_factory=list)
    trigger: str = ""  # 触发词
    usage_count: int = 0
    is_favorite: bool = False
    created_at: datetime = field(default_factory=datetime.now)


class CodeMemoryStore:
    """代码记忆存储"""

    def __init__(self, storage_path: str = None):
        self.storage_path = storage_path or os.path.expanduser("~/.hermes-desktop/code_memory")
        os.makedirs(self.storage_path, exist_ok=True)
        self.memories: Dict[str, CodeMemory] = {}
        self._load_memories()

    def _load_memories(self):
        """加载记忆"""
        index_file = os.path.join(self.storage_path, "index.json")
        if os.path.exists(index_file):
            try:
                with open(index_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for item in data.get("memories", []):
                        self.memories[item["id"]] = CodeMemory(
                            id=item["id"],
                            content=item["content"],
                            context=item.get("context", ""),
                            language=item.get("language", ""),
                            tags=item.get("tags", []),
                            usage_count=item.get("usage_count", 0),
                            success_count=item.get("success_count", 0),
                            fail_count=item.get("fail_count", 0),
                            created_at=datetime.fromisoformat(item.get("created_at", datetime.now().isoformat())),
                            updated_at=datetime.fromisoformat(item.get("updated_at", datetime.now().isoformat())),
                        )
            except Exception as e:
                print(f"Failed to load memories: {e}")

    def _save_memories(self):
        """保存记忆"""
        index_file = os.path.join(self.storage_path, "index.json")
        data = {
            "memories": [
                {
                    "id": m.id,
                    "content": m.content,
                    "context": m.context,
                    "language": m.language,
                    "tags": m.tags,
                    "usage_count": m.usage_count,
                    "success_count": m.success_count,
                    "fail_count": m.fail_count,
                    "created_at": m.created_at.isoformat(),
                    "updated_at": m.updated_at.isoformat(),
                }
                for m in self.memories.values()
            ]
        }
        try:
            with open(index_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Failed to save memories: {e}")

    def add_memory(
        self,
        code: str,
        context: str,
        language: str,
        tags: List[str] = None,
        file_path: str = None
    ) -> CodeMemory:
        """添加记忆"""
        memory_id = hashlib.md5(f"{code}:{datetime.now().isoformat()}".encode()).hexdigest()[:12]

        memory = CodeMemory(
            id=memory_id,
            content=code,
            context=context,
            language=language,
            tags=tags or [],
            file_path=file_path
        )

        self.memories[memory_id] = memory
        self._save_memories()

        return memory

    def find_similar(self, query: str, language: str = None, limit: int = 5) -> List[CodeMemory]:
        """查找相似记忆"""
        results = []
        query_lower = query.lower()
        query_words = set(re.findall(r'\w+', query_lower))

        for memory in self.memories.values():
            # 语言过滤
            if language and memory.language != language:
                continue

            # 计算相似度
            content_words = set(re.findall(r'\w+', memory.content.lower()))
            context_words = set(re.findall(r'\w+', memory.context.lower()))

            # 简单词匹配
            matches = len(query_words & content_words) + len(query_words & context_words)
            similarity = matches / max(len(query_words), 1)

            if similarity > 0.1:
                results.append((memory, similarity))

        # 按相似度排序
        results.sort(key=lambda x: -x[1])
        return [r[0] for r in results[:limit]]

    def search_by_tag(self, tag: str) -> List[CodeMemory]:
        """按标签搜索"""
        return [m for m in self.memories.values() if tag in m.tags]

    def get_most_used(self, limit: int = 10) -> List[CodeMemory]:
        """获取最常用的记忆"""
        return sorted(
            self.memories.values(),
            key=lambda m: -m.usage_count
        )[:limit]

    def record_usage(self, memory_id: str, success: bool = True):
        """记录使用"""
        if memory_id in self.memories:
            memory = self.memories[memory_id]
            memory.usage_count += 1
            memory.last_used = datetime.now()
            if success:
                memory.success_count += 1
            else:
                memory.fail_count += 1
            memory.updated_at = datetime.now()
            self._save_memories()

    def delete_memory(self, memory_id: str) -> bool:
        """删除记忆"""
        if memory_id in self.memories:
            del self.memories[memory_id]
            self._save_memories()
            return True
        return False


class ProjectMemoryManager:
    """项目记忆管理器"""

    def __init__(self, storage_path: str = None):
        self.storage_path = storage_path or os.path.expanduser("~/.hermes-desktop/project_memory")
        os.makedirs(self.storage_path, exist_ok=True)
        self.projects: Dict[str, ProjectMemory] = {}
        self.current_project: Optional[ProjectMemory] = None
        self._load_projects()

    def _load_projects(self):
        """加载项目"""
        index_file = os.path.join(self.storage_path, "projects.json")
        if os.path.exists(index_file):
            try:
                with open(index_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for item in data.get("projects", []):
                        self.projects[item["project_path"]] = ProjectMemory(
                            project_path=item["project_path"],
                            project_name=item["project_name"],
                            language=item.get("language", ""),
                            structure=item.get("structure", {}),
                            dependencies=item.get("dependencies", []),
                            conventions=item.get("conventions", {}),
                            templates=item.get("templates", []),
                            last_opened=datetime.fromisoformat(item.get("last_opened", datetime.now().isoformat())),
                            settings=item.get("settings", {}),
                        )
            except Exception as e:
                print(f"Failed to load projects: {e}")

    def _save_projects(self):
        """保存项目"""
        index_file = os.path.join(self.storage_path, "projects.json")
        data = {
            "projects": [
                {
                    "project_path": p.project_path,
                    "project_name": p.project_name,
                    "language": p.language,
                    "structure": p.structure,
                    "dependencies": p.dependencies,
                    "conventions": p.conventions,
                    "templates": p.templates,
                    "last_opened": p.last_opened.isoformat(),
                    "settings": p.settings,
                }
                for p in self.projects.values()
            ]
        }
        with open(index_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def open_project(self, project_path: str) -> Optional[ProjectMemory]:
        """打开项目"""
        if project_path in self.projects:
            project = self.projects[project_path]
        else:
            # 创建新项目记忆
            project = ProjectMemory(
                project_path=project_path,
                project_name=os.path.basename(project_path),
                language=self._detect_language(project_path)
            )
            self.projects[project_path] = project

        project.last_opened = datetime.now()
        self.current_project = project
        self._analyze_project(project)
        self._save_projects()

        return project

    def _detect_language(self, project_path: str) -> str:
        """检测项目语言"""
        extensions = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".java": "java",
            ".cpp": "cpp",
            ".go": "go",
            ".rs": "rust",
            ".rb": "ruby",
            ".php": "php",
        }

        for root, dirs, files in os.walk(project_path):
            # 跳过隐藏目录和常见非源码目录
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', '__pycache__', 'venv', '.git']]
            
            for file in files:
                ext = os.path.splitext(file)[1]
                if ext in extensions:
                    return extensions[ext]

        return "unknown"

    def _analyze_project(self, project: ProjectMemory):
        """分析项目"""
        project.structure = {}

        for root, dirs, files in os.walk(project.project_path):
            # 跳过特定目录
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', '__pycache__', 'venv', '.git', 'build', 'dist']]
            
            for file in files:
                rel_path = os.path.relpath(os.path.join(root, file), project.project_path)
                ext = os.path.splitext(file)[1]
                
                if ext in ['.py', '.js', '.ts', '.java', '.cpp', '.go', '.rs']:
                    project.structure[rel_path] = "source"
                elif ext in ['.json', '.yaml', '.toml', '.ini', '.cfg']:
                    project.structure[rel_path] = "config"
                elif ext in ['.md', '.rst', '.txt']:
                    project.structure[rel_path] = "doc"
                else:
                    project.structure[rel_path] = "other"

    def add_convention(self, key: str, value: str):
        """添加规范"""
        if self.current_project:
            self.current_project.conventions[key] = value
            self._save_projects()

    def get_convention(self, key: str) -> Optional[str]:
        """获取规范"""
        if self.current_project:
            return self.current_project.conventions.get(key)
        return None

    def close_project(self):
        """关闭项目"""
        if self.current_project:
            self.current_project.last_opened = datetime.now()
            self._save_projects()
        self.current_project = None


class DomainMemoryStore:
    """领域记忆存储"""

    def __init__(self, storage_path: str = None):
        self.storage_path = storage_path or os.path.expanduser("~/.hermes-desktop/domain_memory")
        os.makedirs(self.storage_path, exist_ok=True)
        self.domains: Dict[str, DomainMemory] = {}
        self._load_domains()
        self._init_default_domains()

    def _load_domains(self):
        """加载领域"""
        if os.path.exists(self.storage_path):
            for filename in os.listdir(self.storage_path):
                if filename.endswith('.json'):
                    domain_name = filename[:-5]
                    filepath = os.path.join(self.storage_path, filename)
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            self.domains[domain_name] = DomainMemory(
                                domain=domain_name,
                                concepts=data.get("concepts", {}),
                                patterns=data.get("patterns", []),
                                best_practices=data.get("best_practices", []),
                                common_errors=data.get("common_errors", {}),
                                api_examples=data.get("api_examples", {}),
                            )
                    except Exception as e:
                        print(f"Failed to load domain {domain_name}: {e}")

    def _save_domain(self, domain: DomainMemory):
        """保存领域"""
        filepath = os.path.join(self.storage_path, f"{domain.domain}.json")
        data = {
            "concepts": domain.concepts,
            "patterns": domain.patterns,
            "best_practices": domain.best_practices,
            "common_errors": domain.common_errors,
            "api_examples": domain.api_examples,
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _init_default_domains(self):
        """初始化默认领域"""
        default_domains = {
            "python": DomainMemory(
                domain="python",
                concepts={
                    "PEP 8": "Python代码风格指南",
                    "GIL": "全局解释器锁，限制多线程执行",
                    "装饰器": "修改函数行为的函数",
                    "生成器": "使用yield的函数，返回迭代器",
                },
                patterns=[
                    "单例模式: 使用__new__方法",
                    "工厂模式: 使用函数返回类实例",
                    "观察者模式: 使用callable对象",
                ],
                best_practices=[
                    "使用列表/字典推导式",
                    "使用with语句管理资源",
                    "使用类型注解提高可读性",
                ],
                common_errors={
                    "NameError": "变量未定义或拼写错误",
                    "TypeError": "操作类型不兼容",
                    "IndentationError": "缩进不一致",
                }
            ),
            "javascript": DomainMemory(
                domain="javascript",
                concepts={
                    "闭包": "函数可以访问外部作用域的变量",
                    "原型链": "对象继承机制",
                    "Promise": "异步编程的Promise对象",
                    "async/await": "异步函数的语法糖",
                },
                patterns=[
                    "模块模式: 使用IIFE或ES6模块",
                    "工厂模式: 函数返回对象",
                    "观察者模式: 事件监听器",
                ],
                best_practices=[
                    "使用const/let替代var",
                    "使用箭头函数保持this",
                    "使用解构赋值",
                ],
                common_errors={
                    "ReferenceError": "变量未声明",
                    "TypeError": "操作null/undefined",
                    "SyntaxError": "语法错误",
                }
            ),
            "web": DomainMemory(
                domain="web",
                concepts={
                    "RESTful": "REST架构风格的API设计",
                    "CORS": "跨域资源共享",
                    "JWT": "JSON Web Token认证",
                    "WebSocket": "双向实时通信",
                },
                patterns=[
                    "MVC模式: Model-View-Controller",
                    "SPA: 单页应用",
                    "PWA: 渐进式Web应用",
                ],
                best_practices=[
                    "使用语义化HTML",
                    "响应式设计",
                    "性能优化: 压缩、缓存、CDN",
                ],
                common_errors={
                    "CORS错误": "服务器未配置CORS",
                    "跨域请求失败": "检查Access-Control-Allow-Origin",
                }
            ),
            "database": DomainMemory(
                domain="database",
                concepts={
                    "ACID": "原子性、一致性、隔离性、持久性",
                    "索引": "加速查询的数据结构",
                    "事务": "一组数据库操作",
                    "ORM": "对象关系映射",
                },
                patterns=[
                    "Repository模式: 数据访问抽象",
                    "Unit of Work: 事务管理",
                    "CQRS: 命令查询职责分离",
                ],
                best_practices=[
                    "使用参数化查询防止SQL注入",
                    "创建适当的索引",
                    "定期备份数据",
                ],
                common_errors={
                    "SQL注入": "使用参数化查询",
                    "死锁": "减少事务持有时间",
                }
            ),
            "ai": DomainMemory(
                domain="ai",
                concepts={
                    "LLM": "大型语言模型",
                    "RAG": "检索增强生成",
                    "Prompt Engineering": "提示工程",
                    "Fine-tuning": "微调预训练模型",
                },
                patterns=[
                    "Few-shot Learning: 提供示例",
                    "Chain of Thought: 思考链",
                    "Retrieval Augmented: 检索+生成",
                ],
                best_practices=[
                    "清晰具体的指令",
                    "分解复杂任务",
                    "验证模型输出",
                ],
                common_errors={
                    "幻觉": "模型生成不真实信息",
                    "Prompt注入": "恶意指令覆盖原任务",
                }
            )
        }

        for name, domain in default_domains.items():
            if name not in self.domains:
                self.domains[name] = domain
                self._save_domain(domain)

    def get_domain(self, domain: str) -> Optional[DomainMemory]:
        """获取领域"""
        return self.domains.get(domain)

    def add_concept(self, domain: str, concept: str, definition: str):
        """添加概念"""
        if domain in self.domains:
            self.domains[domain].concepts[concept] = definition
            self._save_domain(self.domains[domain])

    def add_pattern(self, domain: str, pattern: str):
        """添加模式"""
        if domain in self.domains:
            if pattern not in self.domains[domain].patterns:
                self.domains[domain].patterns.append(pattern)
                self._save_domain(self.domains[domain])

    def add_error_solution(self, domain: str, error: str, solution: str):
        """添加错误解决方案"""
        if domain in self.domains:
            self.domains[domain].common_errors[error] = solution
            self._save_domain(self.domains[domain])


class SnippetManager:
    """代码片段管理器"""

    def __init__(self, storage_path: str = None):
        self.storage_path = storage_path or os.path.expanduser("~/.hermes-desktop/snippets")
        os.makedirs(self.storage_path, exist_ok=True)
        self.snippets: Dict[str, Snippet] = {}
        self._load_snippets()
        self._init_default_snippets()

    def _load_snippets(self):
        """加载片段"""
        index_file = os.path.join(self.storage_path, "index.json")
        if os.path.exists(index_file):
            try:
                with open(index_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for item in data.get("snippets", []):
                        self.snippets[item["id"]] = Snippet(
                            id=item["id"],
                            name=item["name"],
                            description=item.get("description", ""),
                            code=item["code"],
                            language=item.get("language", ""),
                            tags=item.get("tags", []),
                            trigger=item.get("trigger", ""),
                            usage_count=item.get("usage_count", 0),
                            is_favorite=item.get("is_favorite", False),
                            created_at=datetime.fromisoformat(item.get("created_at", datetime.now().isoformat())),
                        )
            except Exception as e:
                print(f"Failed to load snippets: {e}")

    def _save_snippets(self):
        """保存片段"""
        index_file = os.path.join(self.storage_path, "index.json")
        data = {
            "snippets": [
                {
                    "id": s.id,
                    "name": s.name,
                    "description": s.description,
                    "code": s.code,
                    "language": s.language,
                    "tags": s.tags,
                    "trigger": s.trigger,
                    "usage_count": s.usage_count,
                    "is_favorite": s.is_favorite,
                    "created_at": s.created_at.isoformat(),
                }
                for s in self.snippets.values()
            ]
        }
        with open(index_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _init_default_snippets(self):
        """初始化默认片段"""
        defaults = [
            Snippet(
                id="python_class",
                name="Python Class",
                description="Python类模板",
                code="class {class_name}:\n    def __init__(self{params}):\n        pass",
                language="python",
                tags=["class", "template"],
                trigger="class"
            ),
            Snippet(
                id="python_function",
                name="Python Function",
                description="Python函数模板",
                code="def {function_name}({params}) -> {return_type}:\n    \"\"\"文档字符串\"\"\"\n    pass",
                language="python",
                tags=["function", "template"],
                trigger="def"
            ),
            Snippet(
                id="js_arrow",
                name="Arrow Function",
                description="JavaScript箭头函数",
                code="const {name} = ({params}) => {\n    {body}\n};",
                language="javascript",
                tags=["function", "arrow"],
                trigger="arrow"
            ),
            Snippet(
                id="try_catch",
                name="Try-Catch",
                description="异常处理块",
                code="try {\n    {try_block}\n} catch (error) {\n    {catch_block}\n}",
                language="javascript",
                tags=["exception", "error"],
                trigger="try"
            ),
        ]

        for snippet in defaults:
            if snippet.id not in self.snippets:
                self.snippets[snippet.id] = snippet

        if defaults:
            self._save_snippets()

    def create_snippet(
        self,
        name: str,
        code: str,
        language: str,
        description: str = "",
        tags: List[str] = None,
        trigger: str = ""
    ) -> Snippet:
        """创建片段"""
        import uuid
        snippet = Snippet(
            id=str(uuid.uuid4())[:8],
            name=name,
            code=code,
            language=language,
            description=description,
            tags=tags or [],
            trigger=trigger or name
        )
        self.snippets[snippet.id] = snippet
        self._save_snippets()
        return snippet

    def find_by_trigger(self, trigger: str) -> Optional[Snippet]:
        """通过触发词查找"""
        for snippet in self.snippets.values():
            if snippet.trigger.lower() == trigger.lower():
                return snippet
        return None

    def search(self, query: str, language: str = None) -> List[Snippet]:
        """搜索片段"""
        query_lower = query.lower()
        results = []

        for snippet in self.snippets.values():
            if language and snippet.language != language:
                continue

            if (query_lower in snippet.name.lower() or
                query_lower in snippet.description.lower() or
                any(query_lower in tag.lower() for tag in snippet.tags)):
                results.append(snippet)

        return results

    def record_usage(self, snippet_id: str):
        """记录使用"""
        if snippet_id in self.snippets:
            self.snippets[snippet_id].usage_count += 1
            self._save_snippets()


class MemoryEnhancedEditor:
    """记忆增强编辑器"""

    def __init__(self, storage_path: str = None):
        self.code_memory = CodeMemoryStore(storage_path)
        self.project_memory = ProjectMemoryManager(storage_path)
        self.domain_memory = DomainMemoryStore(storage_path)
        self.snippet_manager = SnippetManager(storage_path)
        self.personal_style = PersonalStyle()
        self._load_personal_style()

    def _load_personal_style(self):
        """加载个人风格"""
        style_file = os.path.join(self.storage_path or "", "personal_style.json")
        if os.path.exists(style_file):
            try:
                with open(style_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.personal_style = PersonalStyle(**data)
            except:
                pass

    def _save_personal_style(self):
        """保存个人风格"""
        style_file = os.path.join(self.storage_path or "", "personal_style.json")
        with open(style_file, 'w', encoding='utf-8') as f:
            json.dump({
                "indentation": self.personal_style.indentation,
                "quote_style": self.personal_style.quote_style,
                "naming_convention": self.personal_style.naming_convention,
                "bracket_style": self.personal_style.bracket_style,
                "import_order": self.personal_style.import_order,
                "comment_style": self.personal_style.comment_style,
                "docstring_style": self.personal_style.docstring_style,
            }, f, indent=2)

    def remember_code(
        self,
        code: str,
        context: str,
        language: str,
        tags: List[str] = None,
        file_path: str = None
    ):
        """记忆代码"""
        return self.code_memory.add_memory(code, context, language, tags, file_path)

    def recall_similar(self, query: str, language: str = None) -> List[CodeMemory]:
        """回忆相似代码"""
        return self.code_memory.find_similar(query, language)

    def get_snippet(self, trigger: str) -> Optional[Snippet]:
        """获取代码片段"""
        snippet = self.snippet_manager.find_by_trigger(trigger)
        if snippet:
            self.snippet_manager.record_usage(snippet.id)
        return snippet

    def open_project(self, project_path: str) -> ProjectMemory:
        """打开项目"""
        return self.project_memory.open_project(project_path)

    def get_convention(self, key: str) -> Optional[str]:
        """获取项目规范"""
        return self.project_memory.get_convention(key)

    def apply_personal_style(self, code: str, language: str) -> str:
        """应用个人风格"""
        # 简单的风格转换
        if self.personal_style.indentation == "    ":
            # 保持默认
            pass

        return code

    def get_editor_stats(self) -> Dict[str, Any]:
        """获取编辑器统计"""
        return {
            "code_memories": len(self.code_memory.memories),
            "projects": len(self.project_memory.projects),
            "domains": len(self.domain_memory.domains),
            "snippets": len(self.snippet_manager.snippets),
            "most_used_snippet": self.snippet_manager.snippets[
                max(self.snippet_manager.snippets.keys(),
                    key=lambda k: self.snippet_manager.snippets[k].usage_count)
            ].name if self.snippet_manager.snippets else None,
        }
