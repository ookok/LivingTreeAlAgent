# -*- coding: utf-8 -*-
"""
意图保持型压缩器 (Intent-Preserving Compressor)
==============================================

为 AI 原生操作系统设计的上下文压缩核心模块。

核心理念：
- 代码签名化：接口 > 实现，保留签名丢弃实现
- 分层上下文金字塔：建立层级化的上下文结构
- 结构化意图编码：将模糊意图转化为可执行的结构化表示

参考 AI 原生操作系统愿景文档：
- 意图保持型压缩：在有限 Token 内无损传递需求
- 代码签名化（接口 > 实现）
- 分层上下文金字塔
- 结构化意图编码

Author: Hermes Desktop Team
Date: 2026-04-24
"""

import re
import hashlib
import time
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import threading

# ─── 数据结构 ────────────────────────────────────────────────────────────────

class IntentType(Enum):
    """意图类型枚举"""
    CODE_GENERATION = "code_generation"      # 代码生成
    CODE_MODIFICATION = "code_modification"  # 代码修改
    CODE_ANALYSIS = "code_analysis"          # 代码分析
    DEBUG = "debug"                          # 调试
    REFACTOR = "refactor"                    # 重构
    QUERY = "query"                          # 查询/问答
    CONVERSATION = "conversation"            # 对话/闲聊
    SYSTEM = "system"                         # 系统操作
    UNKNOWN = "unknown"                       # 未知


class CodeSignatureType(Enum):
    """代码签名类型"""
    FUNCTION = "function"          # 函数签名
    CLASS = "class"                # 类签名
    INTERFACE = "interface"        # 接口签名
    MODULE = "module"              # 模块签名
    API = "api"                    # API 签名
    CONFIG = "config"              # 配置签名


@dataclass
class IntentSignature:
    """
    意图签名 - 结构化编码的用户意图

    结构化表示：
    - intent_type: 意图类型
    - action: 具体动作（如 create, modify, delete, analyze）
    - target: 目标对象（如函数名、类名、文件名）
    - constraints: 约束条件（如性能要求、兼容性要求）
    - context: 上下文线索
    """
    intent_type: IntentType
    action: str = ""
    target: str = ""
    subject: str = ""              # 主语/执行者
    constraints: List[str] = field(default_factory=list)  # 约束条件列表
    context: str = ""              # 上下文摘要
    raw_query: str = ""            # 原始查询

    def to_compact_string(self) -> str:
        """转换为紧凑字符串（节省 token）"""
        parts = [f"[{self.intent_type.value}]"]
        if self.action:
            parts.append(f"@{self.action}")
        if self.target:
            parts.append(f"#{self.target}")
        if self.subject:
            parts.append(f"${self.subject}")
        if self.constraints:
            cons_str = "|".join(self.constraints[:3])  # 最多3个约束
            parts.append(f"({cons_str})")
        return " ".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.intent_type.value,
            "action": self.action,
            "target": self.target,
            "subject": self.subject,
            "constraints": self.constraints,
            "context": self.context,
        }


@dataclass
class CodeSignature:
    """
    代码签名 - 提取代码的核心接口信息

    与完整代码的区别：
    - 函数签名：保留参数类型和返回值，丢弃函数体
    - 类签名：保留类名和公开方法，丢弃实现
    - 模块签名：保留导出列表，丢弃实现细节
    """
    signature_type: CodeSignatureType
    name: str
    signature: str                    # 完整签名行
    parameters: List[Dict[str, str]] = field(default_factory=list)  # 参数列表
    return_type: str = ""
    decorators: List[str] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    docstring: str = ""               # 文档字符串（简洁版）
    public_methods: List[str] = field(default_factory=list)  # 公开方法列表
    source_file: str = ""
    line_number: int = 0

    def to_minimal_string(self) -> str:
        """转换为最小化字符串（最大化压缩）"""
        parts = [f"{self.signature_type.value}:{self.name}"]
        if self.parameters:
            params = ",".join(p.get("name", "?") for p in self.parameters[:5])
            parts.append(f"({params})")
        if self.return_type:
            parts.append(f"->{self.return_type}")
        return "".join(parts)


@dataclass
class ContextLayer:
    """
    上下文金字塔的一层

    分层策略：
    - Layer 0 (系统): 系统提示、角色定义
    - Layer 1 (意图): 用户意图签名
    - Layer 2 (结构): 代码签名、关键数据结构
    - Layer 3 (细节): 具体实现细节（可压缩）
    - Layer 4 (历史): 历史对话摘要
    """
    layer_id: int
    layer_name: str
    content: str
    tokens: int
    priority: int                    # 优先级（越高越重要）
    is_compressible: bool = True      # 是否可压缩

    def __lt__(self, other):
        # 按优先级降序排列
        return self.priority > other.priority


# ─── 意图识别器 ────────────────────────────────────────────────────────────────

class IntentRecognizer:
    """
    意图识别器

    功能：
    1. 识别用户意图类型
    2. 提取意图签名
    3. 结构化编码意图

    规则 + LLM 混合模式：
    - 规则快速分类（覆盖 80% 常见场景）
    - LLM 细粒度提取（覆盖复杂场景）
    """

    # 意图关键词模式
    INTENT_PATTERNS = {
        IntentType.CODE_GENERATION: [
            r"生成代码", r"写一个", r"帮我创建", r"实现一个",
            r"如何实现", r"怎么写", r"代码示例",
            r"create.*function", r"implement.*class",
        ],
        IntentType.CODE_MODIFICATION: [
            r"修改", r"改动", r"调整", r"更新",
            r"修改.*代码", r"把.*改成", r"把.*改为",
            r"change.*to", r"modify", r"update.*code",
        ],
        IntentType.CODE_ANALYSIS: [
            r"分析", r"解释", r"说明", r"理解",
            r"这段代码.*什么", r"代码.*作用",
            r"analyze", r"explain.*code",
        ],
        IntentType.DEBUG: [
            r"报错", r"错误", r"bug", r"问题", r"修复",
            r"调试", r"不工作", r"失败",
            r"error", r"exception", r"debug", r"fix",
        ],
        IntentType.REFACTOR: [
            r"重构", r"优化.*代码", r"精简", r"清理",
            r"重写", r"改进.*代码",
            r"refactor", r"optimize.*code",
        ],
        IntentType.QUERY: [
            r"是什么", r"如何", r"怎么", r"为什么",
            r"有没有", r"能否", r"可以.*吗",
            r"what.*is", r"how.*to", r"why",
        ],
        IntentType.CONVERSATION: [
            r"你好", r"谢谢", r"再见", r"聊聊天",
            r"随便问问", r"介绍一下",
            r"hi", r"hello", r"thanks", r"bye",
        ],
        IntentType.SYSTEM: [
            r"重启", r"关闭", r"设置", r"配置",
            r"export", r"import", r"save",
        ],
    }

    # 动作词提取
    ACTION_PATTERNS = [
        (r"生成|创建|新建|写|添加", "create"),
        (r"修改|改动|调整|更新|编辑", "modify"),
        (r"删除|移除|去掉", "delete"),
        (r"查询|获取|拉取|读取", "query"),
        (r"分析|解释|说明", "analyze"),
        (r"调试|排查|修复", "debug"),
        (r"优化|精简|重构", "optimize"),
        (r"执行|运行|启动", "execute"),
    ]

    def __init__(self, use_llm: bool = False):
        self.use_llm = use_llm
        self._compile_patterns()

    def _compile_patterns(self):
        """预编译正则表达式"""
        self._intent_regex = {}
        for intent_type, patterns in self.INTENT_PATTERNS.items():
            combined = "|".join(patterns)
            self._intent_regex[intent_type] = re.compile(combined, re.IGNORECASE)

        self._action_regex = [(re.compile(p, re.IGNORECASE), a) for p, a in self.ACTION_PATTERNS]

    def recognize(self, query: str) -> IntentSignature:
        """
        识别用户意图

        Args:
            query: 用户查询

        Returns:
            IntentSignature: 结构化的意图签名
        """
        query = query.strip()

        # 1. 识别意图类型
        intent_type = self._recognize_type(query)

        # 2. 提取动作
        action = self._extract_action(query)

        # 3. 提取目标
        target = self._extract_target(query)

        # 4. 提取约束
        constraints = self._extract_constraints(query)

        # 5. 提取主语
        subject = self._extract_subject(query)

        return IntentSignature(
            intent_type=intent_type,
            action=action,
            target=target,
            subject=subject,
            constraints=constraints,
            context="",
            raw_query=query,
        )

    def _recognize_type(self, query: str) -> IntentType:
        """识别意图类型"""
        scores = {}

        for intent_type, regex in self._intent_regex.items():
            matches = regex.findall(query)
            scores[intent_type] = len(matches)

        if not scores or max(scores.values()) == 0:
            return IntentType.UNKNOWN

        # 返回得分最高的类型
        return max(scores.items(), key=lambda x: x[1])[0]

    def _extract_action(self, query: str) -> str:
        """提取动作词"""
        for regex, action in self._action_regex:
            if regex.search(query):
                return action
        return "interact"

    def _extract_target(self, query: str) -> str:
        """提取目标对象"""
        # 模式：名词/函数名/类名
        patterns = [
            r'([A-Z][a-zA-Z0-9_]+)',           # 类名（PascalCase）
            r'([a-z_]+)\s*\(',                  # 函数名
            r'[`\'"]?([a-zA-Z_][a-zA-Z0-9_]*)',  # 一般标识符
            r'在\s+([^\s]+)',                    # "在xxx"
        ]

        for pattern in patterns:
            match = re.search(pattern, query)
            if match:
                return match.group(1)

        return ""

    def _extract_constraints(self, query: str) -> List[str]:
        """提取约束条件"""
        constraints = []

        # 性能约束
        perf_patterns = [
            (r'性能.*?要|需要.*?性能|快|高效', 'performance'),
            (r'内存.*?小|占用.*?低|省内存', 'low_memory'),
            (r'并发.*?|支持.*?并发', 'concurrent'),
        ]
        for pattern, constraint in perf_patterns:
            if re.search(pattern, query):
                constraints.append(constraint)

        # 兼容性约束
        compat_patterns = [
            (r'兼容.*?|支持.*?版本|Python.*?3', 'compatibility'),
            (r'跨平台|多平台', 'cross_platform'),
            (r'浏览器.*?兼容|移动端', 'client_compatibility'),
        ]
        for pattern, constraint in compat_patterns:
            if re.search(pattern, query):
                constraints.append(constraint)

        # 质量约束
        quality_patterns = [
            (r'安全|防止.*?攻击', 'security'),
            (r'可维护|易读|清晰', 'maintainability'),
            (r'测试.*?通过|单元测试', 'testable'),
        ]
        for pattern, constraint in quality_patterns:
            if re.search(pattern, query):
                constraints.append(constraint)

        return constraints

    def _extract_subject(self, query: str) -> str:
        """提取主语/执行者"""
        # 模式：我/你/系统
        if re.search(r'帮我|我.*?需要|我想', query):
            return "user"
        elif re.search(r'系统|系统.*?应该', query):
            return "system"
        else:
            return "assistant"


# ─── 代码签名提取器 ────────────────────────────────────────────────────────────

class CodeSignatureExtractor:
    """
    代码签名提取器

    核心功能：
    1. 从代码中提取签名（函数、类、接口）
    2. 丢弃实现细节，保留接口
    3. 生成最小化的代码表示
    """

    # 语言支持
    SUPPORTED_LANGUAGES = {
        "python": {
            "function": r'def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(([^)]*)\)\s*(?:->\s*([^:]+))?\s*:',
            "class": r'class\s+([A-Z][a-zA-Z0-9_]*)\s*(?:\([^)]+\))?\s*:',
            "decorator": r'@([a-zA-Z_][a-zA-Z0-9_]*)',
        },
        "javascript": {
            "function": r'(?:function\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\(([^)]*)\)|const\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>)',
            "class": r'class\s+([A-Z][a-zA-Z0-9_]*)\s*(?:extends\s+\w+)?\s*\{',
        },
        "java": {
            "function": r'(?:public|private|protected)?\s*(?:static)?\s*([a-zA-Z_][a-zA-Z0-9_<>[\],\s]*?)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(([^)]*)\)\s*(?:throws\s+\w+\s*)?\{',
            "class": r'class\s+([A-Z][a-zA-Z0-9_]*)\s*(?:extends\s+\w+)?\s*(?:implements\s+[\w,\s]+)?\s*\{',
        },
        "typescript": {
            "interface": r'interface\s+([A-Z][a-zA-Z0-9_]*)\s*\{([^}]+)\}',
            "function": r'(?:const|function)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*[=:]?\s*(?:\([^)]*\)|<[^>]+>)\s*(?::\s*[^=]+)?\s*=>',
        },
    }

    def __init__(self):
        self._compile_patterns()

    def _compile_patterns(self):
        """编译所有语言的正则表达式"""
        self._patterns = {}
        for lang, patterns in self.SUPPORTED_LANGUAGES.items():
            self._patterns[lang] = {
                key: re.compile(pattern, re.MULTILINE)
                for key, pattern in patterns.items()
            }

    def extract_from_code(self, code: str, language: str = "python") -> List[CodeSignature]:
        """
        从代码中提取签名

        Args:
            code: 源代码
            language: 编程语言

        Returns:
            List[CodeSignature]: 提取的签名列表
        """
        if language not in self._patterns:
            return []

        signatures = []
        patterns = self._patterns[language]

        # 提取函数签名
        if "function" in patterns:
            for match in patterns["function"].finditer(code):
                sig = self._parse_function_match(match, language)
                if sig:
                    signatures.append(sig)

        # 提取类签名
        if "class" in patterns:
            for match in patterns["class"].finditer(code):
                sig = self._parse_class_match(match, code, language)
                if sig:
                    signatures.append(sig)

        # 提取接口签名
        if "interface" in patterns:
            for match in patterns["interface"].finditer(code):
                sig = self._parse_interface_match(match)
                if sig:
                    signatures.append(sig)

        return signatures

    def _parse_function_match(self, match: re.Match, language: str) -> Optional[CodeSignature]:
        """解析函数匹配"""
        groups = match.groups()

        if language == "python":
            name = groups[0] if groups[0] else ""
            params_str = groups[1] if groups[1] else ""
            return_type = groups[2] if groups[2] else ""
        elif language == "javascript":
            # JavaScript 可能有不同的捕获组格式
            name = next((g for g in groups if g), "")
            params_str = ""
            return_type = ""
        else:
            name = ""
            params_str = ""
            return_type = ""

        if not name:
            return None

        # 解析参数
        params = self._parse_parameters(params_str, language)

        # 构建签名字符串
        if language == "python":
            sig_str = f"def {name}({params_str})"
            if return_type:
                sig_str += f" -> {return_type}"
        else:
            sig_str = f"{name}({params_str})"

        return CodeSignature(
            signature_type=CodeSignatureType.FUNCTION,
            name=name,
            signature=sig_str,
            parameters=params,
            return_type=return_type,
        )

    def _parse_class_match(self, match: re.Match, code: str, language: str) -> Optional[CodeSignature]:
        """解析类匹配"""
        name = match.group(1) if match.group(1) else ""

        if not name:
            return None

        # 提取公开方法
        public_methods = self._extract_public_methods(code, language)

        return CodeSignature(
            signature_type=CodeSignatureType.CLASS,
            name=name,
            signature=f"class {name}",
            public_methods=public_methods,
        )

    def _parse_interface_match(self, match: re.Match) -> Optional[CodeSignature]:
        """解析接口匹配"""
        name = match.group(1) if match.group(1) else ""
        body = match.group(2) if match.group(2) else ""

        if not name:
            return None

        return CodeSignature(
            signature_type=CodeSignatureType.INTERFACE,
            name=name,
            signature=f"interface {name} {{ {body} }}",
        )

    def _parse_parameters(self, params_str: str, language: str) -> List[Dict[str, str]]:
        """解析参数列表"""
        params = []

        if not params_str.strip():
            return params

        # 按逗号分割
        parts = params_str.split(",")

        for part in parts[:10]:  # 最多10个参数
            part = part.strip()
            if not part:
                continue

            if language == "python":
                # Python: name 或 name: type
                if ":" in part:
                    name, ptype = part.split(":", 1)
                    params.append({"name": name.strip(), "type": ptype.strip()})
                else:
                    params.append({"name": part, "type": "Any"})
            elif language in ("javascript", "typescript"):
                # JS/TS: name 或 name: type
                if ":" in part:
                    name, ptype = part.split(":", 1)
                    params.append({"name": name.strip(), "type": ptype.strip()})
                else:
                    params.append({"name": part, "type": "any"})

        return params

    def _extract_public_methods(self, code: str, language: str) -> List[str]:
        """提取类的公开方法"""
        methods = []

        if language == "python":
            # 查找 def xxx(self, ...) 模式
            pattern = re.compile(r'def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\([^)]*\)\s*(?:->\s*[^:]+)?\s*:')
            for match in pattern.finditer(code):
                method_name = match.group(1)
                # 排除私有方法
                if not method_name.startswith("_") and method_name != "__init__":
                    methods.append(method_name)
        elif language in ("javascript", "typescript"):
            # 查找 methodName(...) 模式
            pattern = re.compile(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*\([^)]*\)\s*\{')
            for match in pattern.finditer(code):
                method_name = match.group(1)
                if not method_name.startswith("_"):
                    methods.append(method_name)

        return methods[:10]  # 最多10个方法

    def compress_code(self, code: str, language: str = "python", keep_signatures_only: bool = True) -> str:
        """
        压缩代码（保留签名丢弃实现）

        Args:
            code: 源代码
            language: 编程语言
            keep_signatures_only: 是否只保留签名

        Returns:
            str: 压缩后的代码
        """
        signatures = self.extract_from_code(code, language)

        if not signatures:
            return self._fallback_compress(code, language)

        if keep_signatures_only:
            # 只保留签名
            return "\n".join(sig.to_minimal_string() for sig in signatures)
        else:
            # 保留签名 + 简短注释
            parts = []
            for sig in signatures:
                parts.append(sig.signature)
                if sig.docstring:
                    parts.append(f"    # {sig.docstring[:50]}")
            return "\n".join(parts)

    def _fallback_compress(self, code: str, language: str) -> str:
        """降级压缩策略"""
        lines = code.split("\n")
        compressed = []

        for line in lines:
            stripped = line.strip()
            # 保留空行、注释、文档字符串
            if not stripped:
                continue
            if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
                # 简短注释
                if len(stripped) < 100:
                    compressed.append(stripped)
            elif "def " in stripped or "class " in stripped or "function " in stripped:
                # 函数/类定义行
                compressed.append(stripped.split(":")[0] if ":" in stripped else stripped[:80])

        # 合并并截断
        result = "\n".join(compressed[:20])
        if len(compressed) > 20:
            result += f"\n... ({len(compressed) - 20} more lines)"
        return result


# ─── 分层上下文金字塔 ──────────────────────────────────────────────────────────

class ContextPyramid:
    """
    分层上下文金字塔

    将上下文组织为分层结构，确保重要信息优先保留：

    Layer 0: 系统层 - 系统提示、角色定义
    Layer 1: 意图层 - 用户意图签名
    Layer 2: 结构层 - 代码签名、关键数据结构
    Layer 3: 细节层 - 具体实现细节（可压缩）
    Layer 4: 历史层 - 历史对话摘要
    """

    # 层级定义
    LAYER_DEFINITIONS = {
        0: {"name": "system", "priority": 100, "max_tokens": 1000},
        1: {"name": "intent", "priority": 95, "max_tokens": 500},
        2: {"name": "structure", "priority": 80, "max_tokens": 2000},
        3: {"name": "detail", "priority": 50, "max_tokens": 5000},
        4: {"name": "history", "priority": 30, "max_tokens": 3000},
    }

    def __init__(self, max_total_tokens: int = 8000):
        self.max_total_tokens = max_total_tokens
        self.layers: Dict[int, ContextLayer] = {}
        self._lock = threading.Lock()

    def add_content(self, layer_id: int, content: str, priority: int = None) -> ContextLayer:
        """添加内容到指定层"""
        with self._lock:
            if layer_id not in self.LAYER_DEFINITIONS:
                raise ValueError(f"Invalid layer_id: {layer_id}")

            definition = self.LAYER_DEFINITIONS[layer_id]
            layer_priority = priority if priority is not None else definition["priority"]

            tokens = self._estimate_tokens(content)

            layer = ContextLayer(
                layer_id=layer_id,
                layer_name=definition["name"],
                content=content,
                tokens=tokens,
                priority=layer_priority,
            )

            self.layers[layer_id] = layer
            return layer

    def build(self) -> str:
        """
        构建压缩后的上下文

        策略：
        1. 按优先级排序各层
        2. 从高优先级开始，选择内容直到达到 token 限制
        3. 超出时压缩低优先级内容

        Returns:
            str: 压缩后的上下文
        """
        with self._lock:
            if not self.layers:
                return ""

            # 按优先级排序
            sorted_layers = sorted(self.layers.values())

            # 构建上下文
            parts = []
            current_tokens = 0

            for layer in sorted_layers:
                layer_def = self.LAYER_DEFINITIONS.get(layer.layer_id, {})

                if current_tokens + layer.tokens <= self.max_total_tokens:
                    # 直接添加
                    parts.append(f"=== {layer.layer_name.upper()} ===")
                    parts.append(layer.content)
                    current_tokens += layer.tokens
                elif layer.is_compressible and layer.tokens > layer_def.get("max_tokens", 1000):
                    # 压缩后添加
                    compressed = self._compress_layer(layer)
                    compressed_tokens = self._estimate_tokens(compressed)

                    if current_tokens + compressed_tokens <= self.max_total_tokens:
                        parts.append(f"=== {layer.layer_name.upper()} (compressed) ===")
                        parts.append(compressed)
                        current_tokens += compressed_tokens
                # 如果无法添加，跳过该层

            return "\n\n".join(parts)

    def _compress_layer(self, layer: ContextLayer) -> str:
        """压缩单层内容"""
        if layer.tokens <= 1000:
            return layer.content

        # 按行截断，保留开头和结尾
        lines = layer.content.split("\n")
        if len(lines) <= 10:
            return layer.content

        # 保留前 N 行和后 N 行
        keep_lines = 5
        compressed_lines = lines[:keep_lines]
        compressed_lines.append(f"... [{len(lines) - keep_lines * 2} lines omitted] ...")
        compressed_lines.extend(lines[-keep_lines:])

        return "\n".join(compressed_lines)

    def _estimate_tokens(self, text: str) -> int:
        """估算 token 数"""
        if not text:
            return 0
        # 简化的估算
        char_count = len(text)
        has_chinese = bool(re.search(r'[\u4e00-\u9fff]', text))
        if has_chinese:
            return int(char_count * 0.7)
        return int(char_count / 3.5)

    def clear(self):
        """清空所有层"""
        with self._lock:
            self.layers.clear()

    def get_summary(self) -> Dict[str, Any]:
        """获取金字塔摘要"""
        with self._lock:
            total_tokens = sum(layer.tokens for layer in self.layers.values())
            return {
                "total_layers": len(self.layers),
                "total_tokens": total_tokens,
                "max_tokens": self.max_total_tokens,
                "utilization": f"{total_tokens / self.max_total_tokens:.1%}",
                "layers": {
                    layer.layer_name: {
                        "tokens": layer.tokens,
                        "priority": layer.priority,
                    }
                    for layer in self.layers.values()
                }
            }


# ─── 意图保持型压缩器 ─────────────────────────────────────────────────────────

class IntentPreservingCompressor:
    """
    意图保持型压缩器

    核心设计原则：
    1. 意图无损：用户的核心意图必须保留
    2. 代码签名化：保留接口，丢弃实现
    3. 分层组织：建立上下文金字塔
    4. 结构化编码：将模糊意图转化为结构化表示

    使用流程：
    1. IntentRecognizer: 识别用户意图，生成 IntentSignature
    2. CodeSignatureExtractor: 从代码中提取签名
    3. ContextPyramid: 组织分层上下文
    4. 压缩输出：生成保留意图的压缩文本
    """

    def __init__(
        self,
        max_tokens: int = 8000,
        preserve_intent: bool = True,
        code_signature_only: bool = True,
    ):
        self.max_tokens = max_tokens
        self.preserve_intent = preserve_intent
        self.code_signature_only = code_signature_only

        self.intent_recognizer = IntentRecognizer()
        self.code_extractor = CodeSignatureExtractor()
        self.pyramid = ContextPyramid(max_total_tokens=max_tokens)

        # 统计
        self._stats = {
            "total_compressions": 0,
            "intent_signatures": 0,
            "code_signatures": 0,
            "layers_created": 0,
            "tokens_saved": 0,
        }

    def compress(self, query: str, context: str = "", code: str = "", language: str = "python") -> Dict[str, Any]:
        """
        执行意图保持型压缩

        Args:
            query: 用户查询
            context: 额外上下文
            code: 代码片段
            language: 编程语言

        Returns:
            {
                "compressed": str,          # 压缩后的内容
                "intent_signature": dict,   # 意图签名
                "code_signatures": list,    # 代码签名列表
                "pyramid_summary": dict,     # 金字塔摘要
                "stats": dict,              # 统计信息
            }
        """
        self.pyramid.clear()

        # 1. 识别意图
        intent_sig = self.intent_recognizer.recognize(query)
        self._stats["intent_signatures"] += 1

        # 2. 提取代码签名
        code_sigs = []
        if code:
            code_sigs = self.code_extractor.extract_from_code(code, language)
            self._stats["code_signatures"] += len(code_sigs)

        # 3. 构建分层金字塔
        # Layer 0: 意图签名（最高优先级）
        self.pyramid.add_content(
            layer_id=0,
            content=intent_sig.to_compact_string(),
            priority=100
        )

        # Layer 1: 原始查询摘要
        query_summary = self._summarize_query(query)
        self.pyramid.add_content(
            layer_id=1,
            content=query_summary,
            priority=95
        )

        # Layer 2: 代码签名
        if code_sigs:
            code_sig_str = "\n".join(sig.to_minimal_string() for sig in code_sigs)
            self.pyramid.add_content(
                layer_id=2,
                content=code_sig_str,
                priority=80
            )

        # Layer 3: 上下文细节
        if context:
            self.pyramid.add_content(
                layer_id=3,
                content=context,
                priority=50,
            )

        # Layer 4: 原始代码（仅在有空间时添加）
        if code and self.code_signature_only:
            # 只添加代码签名，不添加原始代码
            pass
        elif code:
            compressed_code = self.code_extractor.compress_code(code, language)
            self.pyramid.add_content(
                layer_id=4,
                content=compressed_code,
                priority=30
            )

        # 4. 构建压缩输出
        compressed = self.pyramid.build()

        # 5. 统计
        original_tokens = self._estimate_tokens(query) + self._estimate_tokens(context) + self._estimate_tokens(code)
        compressed_tokens = self._estimate_tokens(compressed)
        self._stats["tokens_saved"] += original_tokens - compressed_tokens
        self._stats["total_compressions"] += 1

        return {
            "compressed": compressed,
            "intent_signature": intent_sig.to_dict(),
            "code_signatures": [
                {
                    "type": sig.signature_type.value,
                    "name": sig.name,
                    "signature": sig.signature,
                }
                for sig in code_sigs
            ],
            "pyramid_summary": self.pyramid.get_summary(),
            "stats": {
                "original_tokens": original_tokens,
                "compressed_tokens": compressed_tokens,
                "compression_ratio": f"{(1 - compressed_tokens / max(original_tokens, 1)):.1%}",
            }
        }

    def _summarize_query(self, query: str) -> str:
        """生成查询摘要"""
        # 简单策略：截断过长的查询
        if len(query) <= 100:
            return query

        # 尝试提取关键部分
        sentences = re.split(r'[。！？\n]', query)
        if sentences:
            # 保留第一句和最后一句
            summary = sentences[0]
            if len(sentences) > 1:
                summary += " ... " + sentences[-1]
            return summary[:100]

        return query[:100] + "..."

    def _estimate_tokens(self, text: str) -> int:
        """估算 token 数"""
        if not text:
            return 0
        char_count = len(text)
        has_chinese = bool(re.search(r'[\u4e00-\u9fff]', text))
        if has_chinese:
            return int(char_count * 0.7)
        return int(char_count / 3.5)

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self._stats,
            "compression_efficiency": f"{self._stats['tokens_saved'] / max(self._stats['total_compressions'], 1):.0f} tokens/compression",
        }


# ─── 便捷函数 ─────────────────────────────────────────────────────────────────

def create_compressor(max_tokens: int = 8000) -> IntentPreservingCompressor:
    """创建意图保持型压缩器"""
    return IntentPreservingCompressor(max_tokens=max_tokens)


def quick_compress(query: str, context: str = "", code: str = "") -> str:
    """快速压缩（返回压缩文本）"""
    compressor = IntentPreservingCompressor()
    result = compressor.compress(query, context, code)
    return result["compressed"]
