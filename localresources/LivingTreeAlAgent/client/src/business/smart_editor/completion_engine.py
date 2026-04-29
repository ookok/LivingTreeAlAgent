"""
Completion Engine - 智能补全引擎
==============================

提供上下文感知的智能补全功能

支持的补全类型:
- 单词补全
- 代码补全
- 语义补全
- 配置补全
- 模板补全
"""

import re
import asyncio
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Dict, Any, Optional, Callable, Set


class CompletionKind(Enum):
    """补全类型"""
    TEXT = "text"                    # 普通文本
    WORD = "word"                   # 单词
    SNIPPET = "snippet"             # 代码片段
    TEMPLATE = "template"           # 模板
    FUNCTION = "function"            # 函数
    CLASS = "class"                 # 类
    VARIABLE = "variable"           # 变量
    PROPERTY = "property"           # 属性
    METHOD = "method"               # 方法
    MODULE = "module"               # 模块
    KEYWORD = "keyword"             # 关键字
    COMMAND = "command"             # 命令


@dataclass
class CompletionItem:
    """
    补全项

    Attributes:
        label: 显示的标签
        kind: 补全类型
        text: 插入的文本
        detail: 详细信息
        documentation: 文档说明
        score: 匹配分数
        icon: 图标名称
        shortcuts: 快捷键
    """
    label: str
    kind: CompletionKind = CompletionKind.TEXT
    text: str = ""
    detail: str = ""
    documentation: str = ""
    score: float = 0.0
    icon: str = ""
    shortcuts: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.text:
            self.text = self.label

    def to_dict(self) -> Dict[str, Any]:
        return {
            'label': self.label,
            'kind': self.kind.value,
            'text': self.text,
            'detail': self.detail,
            'documentation': self.documentation,
            'score': self.score,
        }

    def matches(self, prefix: str) -> float:
        """计算与前缀的匹配分数"""
        if not prefix:
            return 1.0

        prefix_lower = prefix.lower()
        label_lower = self.label.lower()

        # 完全匹配
        if label_lower == prefix_lower:
            return 1.0

        # 开头匹配
        if label_lower.startswith(prefix_lower):
            return 0.9

        # 包含匹配
        if prefix_lower in label_lower:
            return 0.7

        # 模糊匹配（编辑距离）
        score = self._fuzzy_match(prefix_lower, label_lower)
        return score

    def _fuzzy_match(self, s1: str, s2: str) -> float:
        """简单的模糊匹配"""
        if not s1 or not s2:
            return 0.0

        # 计算公共前缀长度
        common = 0
        for c1, c2 in zip(s1, s2):
            if c1 == c2:
                common += 1
            else:
                break

        if common == 0:
            return 0.0

        return common / len(s1) * 0.5


@dataclass
class CompletionContext:
    """补全上下文"""
    prefix: str = ""                    # 光标前的前缀
    suffix: str = ""                    # 光标后的后缀
    current_line: str = ""              # 当前行
    full_content: str = ""              # 完整内容
    cursor_pos: int = 0                 # 光标位置
    mode: str = "plain"                 # 编辑模式
    language: Optional[str] = None      # 编程语言
    context_type: str = "plain_text"     # 上下文类型


class SnippetLibrary:
    """
    代码片段库

    常用代码片段模板
    """

    # Python片段
    PYTHON_SNIPPETS = [
        CompletionItem(
            label="def",
            kind=CompletionKind.SNIPPET,
            text="def ${1:function_name}($2):\n    $3\n    pass",
            detail="定义函数",
            documentation="def function_name(params):\n    pass"
        ),
        CompletionItem(
            label="class",
            kind=CompletionKind.SNIPPET,
            text="class ${1:ClassName}:\n    def __init__(self$2):\n        $3",
            detail="定义类",
            documentation="class ClassName:\n    def __init__(self):\n        pass"
        ),
        CompletionItem(
            label="if",
            kind=CompletionKind.SNIPPET,
            text="if ${1:condition}:\n    $2",
            detail="if语句",
            documentation="if condition:\n    pass"
        ),
        CompletionItem(
            label="for",
            kind=CompletionKind.SNIPPET,
            text="for ${1:item} in ${2:iterable}:\n    $3",
            detail="for循环",
            documentation="for item in iterable:\n    pass"
        ),
        CompletionItem(
            label="try",
            kind=CompletionKind.SNIPPET,
            text="try:\n    $1\nexcept ${2:Exception} as ${3:e}:\n    $4",
            detail="try-except块",
            documentation="try:\n    pass\nexcept Exception as e:\n    pass"
        ),
        CompletionItem(
            label="with",
            kind=CompletionKind.SNIPPET,
            text="with ${1:context_manager} as ${2:target}:\n    $3",
            detail="with语句",
            documentation="with context_manager as target:\n    pass"
        ),
        CompletionItem(
            label="async def",
            kind=CompletionKind.SNIPPET,
            text="async def ${1:function_name}($2):\n    $3",
            detail="异步函数",
            documentation="async def function_name(params):\n    pass"
        ),
        CompletionItem(
            label="lambda",
            kind=CompletionKind.SNIPPET,
            text="lambda ${1:x}: ${2:expression}",
            detail="lambda表达式",
            documentation="lambda x: expression"
        ),
        CompletionItem(
            label="list comprehension",
            kind=CompletionKind.SNIPPET,
            text="[$1 for ${2:item} in ${3:iterable}]",
            detail="列表推导式",
            documentation="[item for item in iterable]"
        ),
        CompletionItem(
            label="dict comprehension",
            kind=CompletionKind.SNIPPET,
            text="{$1: $2 for ${3:key}, $4 in ${5:iterable}.items()}",
            detail="字典推导式",
            documentation="{k: v for k, v in iterable.items()}"
        ),
    ]

    # SQL片段
    SQL_SNIPPETS = [
        CompletionItem(
            label="SELECT",
            kind=CompletionKind.SNIPPET,
            text="SELECT ${1:*} FROM ${2:table} WHERE ${3:condition};",
            detail="查询语句",
            documentation="SELECT * FROM table WHERE condition;"
        ),
        CompletionItem(
            label="INSERT",
            kind=CompletionKind.SNIPPET,
            text="INSERT INTO ${1:table} (${2:columns}) VALUES (${3:values});",
            detail="插入语句",
            documentation="INSERT INTO table (columns) VALUES (values);"
        ),
        CompletionItem(
            label="UPDATE",
            kind=CompletionKind.SNIPPET,
            text="UPDATE ${1:table} SET ${2:column} = ${3:value} WHERE ${4:condition};",
            detail="更新语句",
            documentation="UPDATE table SET column = value WHERE condition;"
        ),
        CompletionItem(
            label="CREATE TABLE",
            kind=CompletionKind.SNIPPET,
            text="CREATE TABLE ${1:table_name} (\n    id INT PRIMARY KEY AUTO_INCREMENT,\n    ${2:column} ${3:VARCHAR(255)},\n    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n);",
            detail="创建表",
            documentation="CREATE TABLE table_name (\n    id INT PRIMARY KEY AUTO_INCREMENT,\n    column VARCHAR(255),\n    created_at TIMESTAMP\n);"
        ),
        CompletionItem(
            label="JOIN",
            kind=CompletionKind.SNIPPET,
            text="${1:INNER} JOIN ${2:table2} ON ${3:table1}.${4:id} = ${2}.${5:foreign_key}",
            detail="连接查询",
            documentation="INNER JOIN table2 ON table1.id = table2.foreign_key"
        ),
    ]

    # JSON片段
    JSON_SNIPPETS = [
        CompletionItem(
            label="object",
            kind=CompletionKind.SNIPPET,
            text='{\n    "${1:key}": "${2:value}"\n}',
            detail="JSON对象",
            documentation='{\n    "key": "value"\n}'
        ),
        CompletionItem(
            label="array",
            kind=CompletionKind.SNIPPET,
            text='[\n    "${1:item}"\n]',
            detail="JSON数组",
            documentation='["item"]'
        ),
        CompletionItem(
            label="nested",
            kind=CompletionKind.SNIPPET,
            text='{\n    "${1:parent}": {\n        "${2:child}": "${3:value}"\n    }\n}',
            detail="嵌套对象",
            documentation='{\n    "parent": {\n        "child": "value"\n    }\n}'
        ),
    ]

    # YAML片段
    YAML_SNIPPETS = [
        CompletionItem(
            label="key-value",
            kind=CompletionKind.SNIPPET,
            text="${1:key}: ${2:value}",
            detail="YAML键值对",
            documentation="key: value"
        ),
        CompletionItem(
            label="list",
            kind=CompletionKind.SNIPPET,
            text="${1:items}:\n    - ${2:item1}\n    - ${3:item2}",
            detail="YAML列表",
            documentation="items:\n    - item1\n    - item2"
        ),
        CompletionItem(
            label="nested",
            kind=CompletionKind.SNIPPET,
            text="${1:parent}:\n    ${2:child}: ${3:value}",
            detail="YAML嵌套",
            documentation="parent:\n    child: value"
        ),
        CompletionItem(
            label="block",
            kind=CompletionKind.SNIPPET,
            text="${1:key}: |\n    ${2:content}",
            detail="多行文本块",
            documentation="key: |\n    content"
        ),
    ]

    # Markdown片段
    MARKDOWN_SNIPPETS = [
        CompletionItem(
            label="heading1",
            kind=CompletionKind.SNIPPET,
            text="# ${1:标题}",
            detail="一级标题",
            documentation="# 标题"
        ),
        CompletionItem(
            label="heading2",
            kind=CompletionKind.SNIPPET,
            text="## ${1:标题}",
            detail="二级标题",
            documentation="## 标题"
        ),
        CompletionItem(
            label="link",
            kind=CompletionKind.SNIPPET,
            text="[${1:链接文本}](${2:URL})",
            detail="链接",
            documentation="[链接文本](URL)"
        ),
        CompletionItem(
            label="code",
            kind=CompletionKind.SNIPPET,
            text="`${1:code}`",
            detail="行内代码",
            documentation="`code`"
        ),
        CompletionItem(
            label="code block",
            kind=CompletionKind.SNIPPET,
            text="```${1:language}\n${2:code}\n```",
            detail="代码块",
            documentation="```language\ncode\n```"
        ),
        CompletionItem(
            label="table",
            kind=CompletionKind.SNIPPET,
            text="| ${1:列1} | ${2:列2} | ${3:列3} |\n| --- | --- | --- |\n| ${4:数据1} | ${5:数据2} | ${6:数据3} |",
            detail="表格",
            documentation="| 列1 | 列2 | 列3 |\n| --- | --- | --- |\n| 数据1 | 数据2 | 数据3 |"
        ),
        CompletionItem(
            label="list",
            kind=CompletionKind.SNIPPET,
            text="- ${1:item1}\n- ${2:item2}\n- ${3:item3}",
            detail="无序列表",
            documentation="- item1\n- item2\n- item3"
        ),
    ]

    # 通用片段
    GENERAL_SNIPPETS = [
        CompletionItem(
            label="TODO",
            kind=CompletionKind.SNIPPET,
            text="TODO: ${1:需要完成的任务}",
            detail="待办事项",
            documentation="TODO: 需要完成的任务"
        ),
        CompletionItem(
            label="FIXME",
            kind=CompletionKind.SNIPPET,
            text="FIXME: ${1:需要修复的问题}",
            detail="待修复问题",
            documentation="FIXME: 需要修复的问题"
        ),
        CompletionItem(
            label="NOTE",
            kind=CompletionKind.SNIPPET,
            text="NOTE: ${1:备注信息}",
            detail="备注",
            documentation="NOTE: 备注信息"
        ),
    ]

    @classmethod
    def get_snippets(cls, language: str) -> List[CompletionItem]:
        """获取指定语言的代码片段"""
        snippets_map = {
            'python': cls.PYTHON_SNIPPETS,
            'sql': cls.SQL_SNIPPETS,
            'json': cls.JSON_SNIPPETS,
            'yaml': cls.YAML_SNIPPETS,
            'markdown': cls.MARKDOWN_SNIPPETS,
        }
        return snippets_map.get(language.lower(), [])

    @classmethod
    def get_all_snippets(cls) -> List[CompletionItem]:
        """获取所有代码片段"""
        return (
            cls.PYTHON_SNIPPETS +
            cls.SQL_SNIPPETS +
            cls.JSON_SNIPPETS +
            cls.YAML_SNIPPETS +
            cls.MARKDOWN_SNIPPETS +
            cls.GENERAL_SNIPPETS
        )


class KeywordLibrary:
    """
    关键字库

    各种编程语言的关键字
    """

    PYTHON_KEYWORDS = [
        'and', 'as', 'assert', 'async', 'await', 'break', 'class', 'continue',
        'def', 'del', 'elif', 'else', 'except', 'False', 'finally', 'for',
        'from', 'global', 'if', 'import', 'in', 'is', 'lambda', 'None',
        'nonlocal', 'not', 'or', 'pass', 'raise', 'return', 'True', 'try',
        'while', 'with', 'yield', 'self', 'cls'
    ]

    SQL_KEYWORDS = [
        'SELECT', 'FROM', 'WHERE', 'AND', 'OR', 'NOT', 'IN', 'IS', 'NULL',
        'AS', 'ORDER', 'BY', 'ASC', 'DESC', 'GROUP', 'HAVING', 'LIMIT',
        'OFFSET', 'JOIN', 'LEFT', 'RIGHT', 'INNER', 'OUTER', 'ON',
        'INSERT', 'INTO', 'VALUES', 'UPDATE', 'SET', 'DELETE',
        'CREATE', 'TABLE', 'INDEX', 'DROP', 'ALTER', 'ADD', 'COLUMN',
        'PRIMARY', 'KEY', 'FOREIGN', 'REFERENCES', 'UNIQUE', 'DEFAULT',
        'CHECK', 'CONSTRAINT', 'DISTINCT', 'ALL', 'EXISTS', 'BETWEEN',
        'LIKE', 'CASE', 'WHEN', 'THEN', 'ELSE', 'END', 'UNION', 'INTERSECT'
    ]

    JSON_KEYWORDS = [
        'true', 'false', 'null'
    ]

    @classmethod
    def get_keywords(cls, language: str) -> List[str]:
        """获取指定语言的关键字"""
        keywords_map = {
            'python': cls.PYTHON_KEYWORDS,
            'sql': cls.SQL_KEYWORDS,
            'json': cls.JSON_KEYWORDS,
        }
        return keywords_map.get(language.lower(), [])


class CompletionEngine:
    """
    智能补全引擎

    提供多类型的智能补全
    """

    def __init__(self):
        self._word_set: Set[str] = set()  # 当前文档中的单词
        self._history: List[str] = []      # 补全历史
        self._llm_client = None
        self._max_history = 100

    def set_llm_client(self, client):
        """设置LLM客户端用于语义补全"""
        self._llm_client = client

    def update_words(self, content: str):
        """更新单词库"""
        # 提取所有单词
        words = re.findall(r'\b[\w_]+\b', content)
        self._word_set.update(words)

    def get_word_completions(self, prefix: str) -> List[CompletionItem]:
        """获取单词补全"""
        if len(prefix) < 2:
            return []

        prefix_lower = prefix.lower()
        completions = []

        # 从当前文档中的单词补全
        for word in self._word_set:
            if word.lower().startswith(prefix_lower):
                completions.append(CompletionItem(
                    label=word,
                    kind=CompletionKind.WORD,
                    detail="文档中的词"
                ))

        # 从历史补全
        for word in self._history:
            if word.lower().startswith(prefix_lower) and word not in self._word_set:
                completions.append(CompletionItem(
                    label=word,
                    kind=CompletionKind.WORD,
                    detail="历史补全"
                ))

        # 按分数排序
        for c in completions:
            c.score = c.matches(prefix)

        return sorted(completions, key=lambda x: x.score, reverse=True)[:10]

    def get_keyword_completions(self, prefix: str, language: str) -> List[CompletionItem]:
        """获取关键字补全"""
        keywords = KeywordLibrary.get_keywords(language)
        if not keywords:
            return []

        prefix_lower = prefix.lower()
        completions = []

        for kw in keywords:
            if kw.lower().startswith(prefix_lower):
                completions.append(CompletionItem(
                    label=kw,
                    kind=CompletionKind.KEYWORD,
                    detail=f"{language} 关键字"
                ))

        return sorted(completions, key=lambda x: x.matches(prefix), reverse=True)

    def get_snippet_completions(self, prefix: str, language: str) -> List[CompletionItem]:
        """获取代码片段补全"""
        snippets = SnippetLibrary.get_snippets(language)

        prefix_lower = prefix.lower()
        completions = []

        for snippet in snippets:
            if snippet.label.lower().startswith(prefix_lower):
                c = CompletionItem(
                    label=snippet.label,
                    kind=snippet.kind,
                    text=snippet.text,
                    detail=snippet.detail,
                    documentation=snippet.documentation,
                )
                c.score = c.matches(prefix)
                completions.append(c)

        return sorted(completions, key=lambda x: x.score, reverse=True)

    async def get_ai_completions(
        self,
        prefix: str,
        suffix: str,
        language: str = None
    ) -> List[CompletionItem]:
        """获取AI语义补全"""
        if not self._llm_client or len(prefix) < 3:
            return []

        try:
            prompt = f"根据以下代码前缀，补全最可能的代码片段（只返回一个最可能的补全）:\n\n{prefix}"

            response = await self._llm_client.chat([{'role': 'user', 'content': prompt}])

            if response and 'content' in response:
                suggestion = response['content'].strip()
                # 提取第一行作为补全
                suggestion = suggestion.split('\n')[0][:100]

                return [CompletionItem(
                    label=suggestion[:30] + "...",
                    kind=CompletionKind.SNIPPET,
                    text=suggestion,
                    detail="AI补全",
                    documentation=f"AI建议: {suggestion[:50]}..."
                )]
        except Exception:
            pass

        return []

    def complete(self, context: CompletionContext) -> List[CompletionItem]:
        """
        执行补全

        Returns:
            按分数排序的补全列表
        """
        all_completions = []
        seen_labels = set()

        # 1. 关键字补全
        if context.language:
            for c in self.get_keyword_completions(context.prefix, context.language):
                if c.label not in seen_labels:
                    all_completions.append(c)
                    seen_labels.add(c.label)

        # 2. 代码片段补全
        if context.language:
            for c in self.get_snippet_completions(context.prefix, context.language):
                if c.label not in seen_labels:
                    all_completions.append(c)
                    seen_labels.add(c.label)

        # 3. 单词补全
        for c in self.get_word_completions(context.prefix):
            if c.label not in seen_labels:
                all_completions.append(c)
                seen_labels.add(c.label)

        # 4. 通用代码片段（所有语言）
        if not context.language:
            for c in SnippetLibrary.get_all_snippets():
                if c.label.lower().startswith(context.prefix.lower()):
                    if c.label not in seen_labels:
                        all_completions.append(c)
                        seen_labels.add(c.label)

        # 按分数排序
        all_completions.sort(key=lambda x: x.score, reverse=True)

        # 限制数量
        return all_completions[:20]

    def add_to_history(self, text: str):
        """添加到补全历史"""
        if text and text not in self._history:
            self._history.append(text)
            if len(self._history) > self._max_history:
                self._history.pop(0)

    def learn_from_completion(self, prefix: str, selected: str):
        """从用户的补全选择中学习"""
        if prefix and selected and prefix != selected:
            self.add_to_history(selected)


# 全局实例
_global_completion_engine: Optional[CompletionEngine] = None


def get_completion_engine() -> CompletionEngine:
    """获取全局补全引擎"""
    global _global_completion_engine
    if _global_completion_engine is None:
        _global_completion_engine = CompletionEngine()
    return _global_completion_engine