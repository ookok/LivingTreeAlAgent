"""
Context Engine - 上下文感知引擎
==============================

根据用户编辑的内容和场景，提供上下文感知的AI辅助

功能:
- 场景识别 (writing_config / writing_code / chatting)
- 意图推断
- 模式推荐
- 工具建议
"""

import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, Any, List, Optional, Set


class ContextType(Enum):
    """上下文类型"""
    PLAIN_TEXT = "plain_text"           # 纯文本
    CONFIG = "config"                  # 配置编辑
    CODE = "code"                       # 代码编写
    NOTE = "note"                       # 笔记
    CHAT = "chat"                       # 对话
    FORM = "form"                       # 表单填写
    DOCUMENT = "document"               # 文档


@dataclass
class EditorContext:
    """
    编辑器上下文信息

    包含当前编辑状态的所有上下文信息，用于AI辅助决策
    """
    # 基本信息
    context_type: ContextType = ContextType.PLAIN_TEXT
    file_path: Optional[str] = None
    file_extension: Optional[str] = None

    # 内容分析
    language: Optional[str] = None          # 编程语言
    framework: Optional[str] = None       # 框架
    document_type: Optional[str] = None    # 文档类型

    # 用户意图推断
    user_intent: List[str] = field(default_factory=list)
    detected_patterns: List[str] = field(default_factory=list)

    # 建议的工具和操作
    suggested_tools: List[str] = field(default_factory=list)
    suggested_completions: List[str] = field(default_factory=list)

    # 语法/语义信息
    syntax_errors: List[Dict[str, Any]] = field(default_factory=list)
    semantic_hints: List[str] = field(default_factory=list)

    # 额外元数据
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'context_type': self.context_type.value,
            'file_path': self.file_path,
            'file_extension': self.file_extension,
            'language': self.language,
            'framework': self.framework,
            'document_type': self.document_type,
            'user_intent': self.user_intent,
            'detected_patterns': self.detected_patterns,
            'suggested_tools': self.suggested_tools,
            'suggested_completions': self.suggested_completions,
            'syntax_errors': self.syntax_errors,
            'semantic_hints': self.semantic_hints,
            'metadata': self.metadata,
        }


# 场景检测模式
CONTEXT_PATTERNS = {
    ContextType.CONFIG: {
        'files': [r'\.json$', r'\.yaml$', r'\.yml$', r'\.toml$', r'\.ini$', r'\.conf$', r'\.config$'],
        'content': [
            r'^\s*\{',  # JSON
            r'^\w+:\s*$',  # YAML key
            r'\[.*\]\s*=',  # INI section
        ],
        'tools': ['format', 'validate', 'beautify', 'default_values'],
    },
    ContextType.CODE: {
        'files': [r'\.py$', r'\.js$', r'\.ts$', r'\.java$', r'\.go$', r'\.rs$', r'\.c$', r'\.cpp$', r'\.h$'],
        'content': [
            r'\bdef\s+\w+',  # Python
            r'\bfunction\s+\w+',  # JS
            r'\bfunc\s+\w+',  # Go
            r'\bfn\s+\w+',  # Rust
            r'\bclass\s+\w+',  # OOP
            r'\bimport\s+',  # Import
            r'\brequire\s*\(',  # Require
        ],
        'tools': ['format', 'lint', 'debug', 'api_completion', 'bug_detection'],
    },
    ContextType.NOTE: {
        'files': [r'\.md$', r'\.txt$', r'\.note$'],
        'content': [
            r'^#+\s',  # Markdown heading
            r'^\s*[-*+]\s',  # List
            r'\*\*.*?\*\*',  # Bold
            r'\[\[.*?\]\]',  # Wiki link
        ],
        'tools': ['format', 'summarize', 'publish', 'toc_generate'],
    },
    ContextType.CHAT: {
        'files': [],
        'content': [
            r'^用户:',  # Chat format
            r'^AI:',  # Chat format
            r'^>',  # Quote
        ],
        'tools': ['translate', 'summarize', 'emoji', 'response_suggestions'],
    },
    ContextType.DOCUMENT: {
        'files': [r'\.docx?$', r'\.pdf$', r'\.odt$'],
        'content': [
            r'^标题',  # Chinese title
            r'^第[一二三\d]+章',  # Chapter
            r'^\d+\.\d+',  # Numbered section
        ],
        'tools': ['format', 'toc_generate', 'export'],
    },
}

# 意图关键词映射
INTENT_KEYWORDS = {
    'create': ['创建', '新建', '新增', 'add new', 'create', 'new'],
    'modify': ['修改', '编辑', '更新', 'edit', 'modify', 'update', 'change'],
    'delete': ['删除', '移除', 'delete', 'remove'],
    'query': ['查询', '搜索', '查找', 'query', 'search', 'find'],
    'analyze': ['分析', '统计', 'analyze', 'statistics', 'count'],
    'configure': ['配置', '设置', 'config', 'setting', 'setup'],
    'test': ['测试', 'test', 'testing'],
    'deploy': ['部署', '发布', 'deploy', 'release', 'publish'],
    'debug': ['调试', 'debug', 'bug', 'fix'],
    'optimize': ['优化', 'optimize', 'performance'],
    'document': ['文档', '注释', 'document', 'comment', 'doc'],
}

# 编程语言检测
LANGUAGE_PATTERNS = {
    'python': [r'\bdef\s+\w+', r'\bimport\s+\w+', r'\bfrom\s+\w+\s+import', r'\bclass\s+\w+.*:'],
    'javascript': [r'\bfunction\s+\w+', r'\bconst\s+\w+\s*=', r'\blet\s+\w+\s*=', r'=>'],
    'typescript': [r':\s*(string|number|boolean|any|void)\b', r'\binterface\s+\w+', r'\btype\s+\w+\s*='],
    'sql': [r'\bSELECT\b', r'\bFROM\b', r'\bWHERE\b', r'\bJOIN\b'],
    'html': [r'<\w+>', r'</\w+>', r'<!DOCTYPE'],
    'css': [r'\{\s*[\w-]+\s*:', r'\.[\w-]+\s*\{', r'#[\w-]+\s*\{'],
    'json': [r'^\s*\{', r'^\s*\[', r'"[^"]+"\s*:\s*'],
    'yaml': [r'^\w+:\s*$', r'^\s*-\s+\w+', r'^\s*\|\s*$'],
    'go': [r'\bpackage\s+\w+', r'\bfunc\s+\w+', r'\bimport\s+"'],
    'rust': [r'\bfn\s+\w+', r'\blet\s+mut\b', r'\bimpl\s+\w+', r'\bpub\s+'],
    'java': [r'\bpublic\s+class\b', r'\bprivate\s+\w+', r'\bSystem\.out\.'],
}


class ContextEngine:
    """
    上下文感知引擎

    分析编辑内容，识别场景和意图，提供智能建议
    """

    def __init__(self):
        self.current_context: Optional[EditorContext] = None
        self._history: List[EditorContext] = []
        self._max_history = 50

    def analyze(self, content: str, cursor_pos: int = 0, file_path: str = None) -> EditorContext:
        """
        分析上下文

        Args:
            content: 编辑内容
            cursor_pos: 光标位置
            file_path: 文件路径

        Returns:
            EditorContext: 分析得到的上下文
        """
        ctx = EditorContext()

        if file_path:
            ctx.file_path = file_path
            ctx.file_extension = self._get_extension(file_path)

        # 检测上下文类型
        ctx.context_type = self._detect_context_type(content, file_path)

        # 检测编程语言
        ctx.language = self._detect_language(content)

        # 推断用户意图
        ctx.user_intent = self._detect_intent(content)

        # 检测常用模式
        ctx.detected_patterns = self._detect_patterns(content, ctx.context_type)

        # 获取建议的工具
        ctx.suggested_tools = self._get_suggested_tools(ctx.context_type, ctx.detected_patterns)

        # 分析语法错误（如果有）
        ctx.syntax_errors = self._analyze_syntax(content, ctx.context_type, ctx.language)

        # 生成语义提示
        ctx.semantic_hints = self._generate_hints(content, ctx)

        # 保存上下文
        self.current_context = ctx
        self._add_to_history(ctx)

        return ctx

    def _get_extension(self, file_path: str) -> str:
        """获取文件扩展名"""
        match = re.search(r'\.([\w]+)$', file_path, re.IGNORECASE)
        return match.group(1) if match else ''

    def _detect_context_type(self, content: str, file_path: str = None) -> ContextType:
        """检测上下文类型"""
        content_stripped = content.strip()

        # 文件名检测
        if file_path:
            ext = self._get_extension(file_path)
            for ctx_type, patterns in CONTEXT_PATTERNS.items():
                for pattern in patterns.get('files', []):
                    if re.search(pattern, file_path, re.IGNORECASE):
                        return ctx_type

        # 内容检测
        for ctx_type, patterns in CONTEXT_PATTERNS.items():
            for pattern in patterns.get('content', []):
                if re.search(pattern, content, re.MULTILINE):
                    return ctx_type

        # 默认根据内容特征判断
        if not content_stripped:
            return ContextType.PLAIN_TEXT

        # 检查是否是对话格式
        if re.match(r'^(用户|AI|me:|ai:)', content_stripped, re.MULTILINE):
            return ContextType.CHAT

        # 短文本可能是表单/配置
        if len(content_stripped) < 500:
            # 包含冒号但不像是代码
            if ':' in content_stripped and '\n' in content_stripped:
                if not any(re.search(p, content) for p in LANGUAGE_PATTERNS.values()):
                    return ContextType.CONFIG

        return ContextType.PLAIN_TEXT

    def _detect_language(self, content: str) -> Optional[str]:
        """检测编程语言"""
        for lang, patterns in LANGUAGE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, content, re.MULTILINE):
                    return lang
        return None

    def _detect_intent(self, content: str) -> List[str]:
        """检测用户意图"""
        intents = []
        content_lower = content.lower()

        for intent, keywords in INTENT_KEYWORDS.items():
            for keyword in keywords:
                if keyword in content_lower:
                    if intent not in intents:
                        intents.append(intent)
                    break

        return intents

    def _detect_patterns(self, content: str, context_type: ContextType) -> List[str]:
        """检测常用模式"""
        patterns = []

        if context_type == ContextType.CODE:
            # 检测设计模式
            if re.search(r'\bclass\s+\w+.*:\s*.*def\s+\w+', content):
                patterns.append('class_with_methods')
            if re.search(r'\breturn\s+\w+', content):
                patterns.append('function_return')
            if re.search(r'\bif\s+.*:\s*.*else:', content):
                patterns.append('if_else')
            if re.search(r'\bfor\s+.*in\s+.*:', content):
                patterns.append('for_loop')
            if re.search(r'\btry:\s*.*except', content, re.DOTALL):
                patterns.append('try_except')

        elif context_type == ContextType.CONFIG:
            # 检测配置模式
            if re.search(r'\[[\w\s]+\]', content):
                patterns.append('ini_sections')
            if re.search(r'^\w+:\s*\|', content, re.MULTILINE):
                patterns.append('yaml_block')
            if re.search(r'"[^"]+":\s*\n\s*"', content):
                patterns.append('nested_json')

        elif context_type == ContextType.NOTE:
            # 检测笔记模式
            if re.search(r'^#+\s', content, re.MULTILINE):
                patterns.append('headings')
            if re.search(r'\[\[.*?\]\]', content):
                patterns.append('wiki_links')
            if re.search(r'!\[\[.*?\]\]', content):
                patterns.append('embedded_images')

        return patterns

    def _get_suggested_tools(self, context_type: ContextType, detected_patterns: List[str]) -> List[str]:
        """获取建议的工具"""
        base_tools = CONTEXT_PATTERNS.get(context_type, {}).get('tools', [])

        # 根据检测到的模式添加特定工具
        if 'class_with_methods' in detected_patterns:
            base_tools.extend(['refactor', 'extract_method'])
        if 'nested_json' in detected_patterns:
            base_tools.extend(['flatten', 'expand'])

        return list(set(base_tools))

    def _analyze_syntax(self, content: str, context_type: ContextType, language: str = None) -> List[Dict[str, Any]]:
        """分析语法错误"""
        errors = []

        if context_type == ContextType.CONFIG or language == 'json':
            try:
                import json
                json.loads(content)
            except json.JSONDecodeError as e:
                errors.append({
                    'type': 'json_syntax',
                    'message': str(e),
                    'line': e.lineno,
                    'column': e.colno,
                })

        elif language == 'python':
            # 基础Python语法检查
            lines = content.split('\n')
            for i, line in enumerate(lines, 1):
                stripped = line.strip()
                # 检查常见问题
                if stripped.endswith(':') and not stripped.startswith('#'):
                    # 检查缩进
                    if i < len(lines) and not lines[i].startswith(' ' * 4) and not lines[i].startswith('\t'):
                        if lines[i].strip() and not lines[i].strip().startswith('#'):
                            errors.append({
                                'type': 'python_indent',
                                'message': '缺少缩进',
                                'line': i + 1,
                            })

        return errors

    def _generate_hints(self, content: str, ctx: EditorContext) -> List[str]:
        """生成语义提示"""
        hints = []

        if ctx.context_type == ContextType.CONFIG:
            if ctx.detected_patterns:
                hints.append("建议使用配置模板")
            if ctx.syntax_errors:
                hints.append("检测到语法错误")

        elif ctx.context_type == ContextType.CODE:
            if 'class_with_methods' in ctx.detected_patterns:
                hints.append("这是一个类定义")
            if ctx.language == 'python':
                hints.append("可用的Python标准库函数")

        elif ctx.context_type == ContextType.NOTE:
            hints.append("可生成目录结构")
            hints.append("可发布到博客")

        return hints

    def _add_to_history(self, ctx: EditorContext):
        """添加到历史"""
        self._history.append(ctx)
        if len(self._history) > self._max_history:
            self._history.pop(0)

    def get_history(self) -> List[EditorContext]:
        """获取历史上下文"""
        return self._history.copy()

    def learn_user_preference(self, action: str, context_type: ContextType):
        """
        学习用户偏好

        记录用户在不同上下文下常做的操作
        """
        if self.current_context:
            self.current_context.metadata.setdefault('user_preferences', {}) \
                .setdefault(context_type.value, []).append(action)

    def get_recommended_action(self) -> Optional[str]:
        """获取推荐的操作"""
        if not self.current_context:
            return None

        prefs = self.current_context.metadata.get('user_preferences', {})
        ctx_prefs = prefs.get(self.current_context.context_type.value, [])

        if ctx_prefs:
            # 返回最常用的操作
            from collections import Counter
            return Counter(ctx_prefs).most_common(1)[0][0]

        # 默认推荐
        tools = self.current_context.suggested_tools
        return tools[0] if tools else None


# 全局实例
_global_context_engine: Optional[ContextEngine] = None


def get_context_engine() -> ContextEngine:
    """获取全局上下文引擎"""
    global _global_context_engine
    if _global_context_engine is None:
        _global_context_engine = ContextEngine()
    return _global_context_engine