"""
Phase 4: 多模态交互集成
=========================

AI 原生 OS 的多模态交互能力：
1. 文本交互 - 自然语言理解与生成
2. 代码交互 - 代码解析、生成、优化
3. 语音交互 - 语音转文本、文本转语音
4. 图像交互 - 图表、流程图、UI设计
5. 文档交互 - PDF、Word、Markdown

Author: AI Native OS Team
"""

from __future__ import annotations

import re
import json
import base64
import hashlib
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple, Union, Callable
from collections import defaultdict
from enum import Enum


# ============================================================================
# 模态类型定义
# ============================================================================

class ModalityType(Enum):
    """模态类型"""
    TEXT = "text"                    # 纯文本
    CODE = "code"                    # 代码
    VOICE = "voice"                  # 语音
    IMAGE = "image"                  # 图像
    DOCUMENT = "document"            # 文档
    VIDEO = "video"                  # 视频
    STRUCTURED = "structured"        # 结构化数据
    MIXED = "mixed"                  # 混合模态


class InteractionMode(Enum):
    """交互模式"""
    CONVERSATION = "conversation"     # 对话模式
    COMMAND = "command"              # 命令模式
    COLLABORATION = "collaboration" # 协作模式
    AUTONOMOUS = "autonomous"       # 自主模式


class MediaFormat(Enum):
    """媒体格式"""
    # 文本
    PLAIN = "plain"
    MARKDOWN = "markdown"
    HTML = "html"
    LATEX = "latex"

    # 代码
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    JAVA = "java"
    CPP = "cpp"
    GO = "go"
    RUST = "rust"
    SQL = "sql"

    # 数据
    JSON = "json"
    YAML = "yaml"
    XML = "xml"
    CSV = "csv"

    # 图像
    PNG = "png"
    JPG = "jpg"
    SVG = "svg"
    PLANTUML = "plantuml"
    Mermaid = "mermaid"

    # 文档
    PDF = "pdf"
    DOCX = "docx"
    PPTX = "pptx"


# ============================================================================
# 数据结构
# ============================================================================

class ContentBlock:
    """内容块"""
    def __init__(
        self,
        block_id: str = None,
        modality: str = "text",
        content: str = "",
        format_type: str = "plain",
        metadata: Dict[str, Any] = None,
        language: str = "",
        annotations: List[Dict] = None
    ):
        self.block_id = block_id or str(uuid.uuid4())
        self.modality = modality
        self.content = content
        self.format_type = format_type
        self.metadata = metadata or {}
        self.language = language
        self.annotations = annotations or []
        self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict:
        return {
            "block_id": self.block_id,
            "modality": self.modality,
            "content": self.content,
            "format_type": self.format_type,
            "metadata": self.metadata,
            "language": self.language,
            "annotations": self.annotations,
            "timestamp": self.timestamp
        }


class MultimodalMessage:
    """多模态消息"""
    def __init__(
        self,
        message_id: str = None,
        user_id: str = "",
        twin_id: str = "",
        content_blocks: List[ContentBlock] = None,
        interaction_mode: str = "conversation",
        context_reference: str = "",
        metadata: Dict[str, Any] = None
    ):
        self.message_id = message_id or str(uuid.uuid4())
        self.user_id = user_id
        self.twin_id = twin_id
        self.content_blocks = content_blocks or []
        self.interaction_mode = interaction_mode
        self.context_reference = context_reference
        self.metadata = metadata or {}
        self.timestamp = datetime.now().isoformat()

        # 自动检测主模态
        self.primary_modality = self._detect_primary_modality()

    def _detect_primary_modality(self) -> str:
        """检测主模态"""
        if not self.content_blocks:
            return "text"

        # 优先级: code > voice > image > text
        for block in self.content_blocks:
            if block.modality == "code":
                return "code"
            elif block.modality == "voice":
                return "voice"
            elif block.modality == "image":
                return "image"

        return "text"

    def add_block(self, block: ContentBlock) -> None:
        """添加内容块"""
        self.content_blocks.append(block)
        self.primary_modality = self._detect_primary_modality()

    def get_text_content(self) -> str:
        """获取文本内容"""
        texts = []
        for block in self.content_blocks:
            if block.modality in ["text", "code"]:
                texts.append(block.content)
        return "\n".join(texts)

    def get_code_blocks(self) -> List[Tuple[str, str]]:
        """获取代码块列表 (语言, 代码)"""
        code_blocks = []
        for block in self.content_blocks:
            if block.modality == "code":
                code_blocks.append((block.language or "plain", block.content))
        return code_blocks

    def to_dict(self) -> Dict:
        return {
            "message_id": self.message_id,
            "user_id": self.user_id,
            "twin_id": self.twin_id,
            "content_blocks": [b.to_dict() for b in self.content_blocks],
            "interaction_mode": self.interaction_mode,
            "context_reference": self.context_reference,
            "primary_modality": self.primary_modality,
            "metadata": self.metadata,
            "timestamp": self.timestamp
        }


class MultimodalResponse:
    """多模态响应"""
    def __init__(
        self,
        response_id: str = None,
        message_id: str = "",
        content_blocks: List[ContentBlock] = None,
        suggested_actions: List[Dict] = None,
        context_update: Dict = None,
        metadata: Dict = None
    ):
        self.response_id = response_id or str(uuid.uuid4())
        self.message_id = message_id
        self.content_blocks = content_blocks or []
        self.suggested_actions = suggested_actions or []
        self.context_update = context_update or {}
        self.metadata = metadata or {}
        self.timestamp = datetime.now().isoformat()

    def add_text(self, text: str, format_type: str = "markdown") -> None:
        """添加文本块"""
        self.content_blocks.append(ContentBlock(
            modality="text",
            content=text,
            format_type=format_type
        ))

    def add_code(
        self,
        code: str,
        language: str = "python",
        annotations: List[Dict] = None
    ) -> None:
        """添加代码块"""
        self.content_blocks.append(ContentBlock(
            modality="code",
            content=code,
            language=language,
            annotations=annotations or []
        ))

    def add_image(
        self,
        image_data: str,
        format_type: str = "png",
        description: str = ""
    ) -> None:
        """添加图像块"""
        self.content_blocks.append(ContentBlock(
            modality="image",
            content=image_data,
            format_type=format_type,
            metadata={"description": description}
        ))

    def add_action(self, action: Dict) -> None:
        """添加建议动作"""
        self.suggested_actions.append(action)

    def to_dict(self) -> Dict:
        return {
            "response_id": self.response_id,
            "message_id": self.message_id,
            "content_blocks": [b.to_dict() for b in self.content_blocks],
            "suggested_actions": self.suggested_actions,
            "context_update": self.context_update,
            "metadata": self.metadata,
            "timestamp": self.timestamp
        }


# ============================================================================
# 多模态处理器
# ============================================================================

class TextProcessor:
    """文本处理器"""

    # 意图模式
    INTENT_PATTERNS = {
        "create": [r"create", r"新建", r"创建", r"添加"],
        "modify": [r"modify", r"update", r"edit", r"修改", r"编辑"],
        "delete": [r"delete", r"remove", r"删除", r"移除"],
        "search": [r"search", r"find", r"query", r"搜索", r"查找"],
        "explain": [r"explain", r"understand", r"解释", r"理解"],
        "execute": [r"run", r"execute", r"运行", r"执行"],
        "debug": [r"debug", r"fix", r"bug", r"调试", r"修复"],
        "review": [r"review", r"check", r"审核", r"检查"]
    }

    @classmethod
    def extract_intent(cls, text: str) -> Dict[str, Any]:
        """提取意图"""
        text_lower = text.lower()

        intent = {
            "primary_action": "general",
            "confidence": 0.5,
            "entities": []
        }

        # 匹配动作
        for action, patterns in cls.INTENT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    intent["primary_action"] = action
                    intent["confidence"] = 0.8
                    break

        # 提取实体
        entities = re.findall(r'`([^`]+)`|(\w+)\.', text)
        intent["entities"] = [e[0] or e[1] for e in entities]

        return intent

    @classmethod
    def extract_code_blocks(cls, text: str) -> List[Tuple[str, str]]:
        """提取代码块"""
        code_blocks = []

        # Markdown 代码块
        pattern = r'```(\w+)?\n(.*?)```'
        matches = re.findall(pattern, text, re.DOTALL)

        for lang, code in matches:
            code_blocks.append((lang or "plain", code.strip()))

        return code_blocks

    @classmethod
    def format_response(cls, text: str, format_type: str = "markdown") -> str:
        """格式化响应"""
        if format_type == "markdown":
            # 确保 Markdown 格式正确
            text = cls._fix_markdown(text)
        elif format_type == "html":
            text = cls._markdown_to_html(text)
        elif format_type == "plain":
            text = cls._strip_markdown(text)

        return text

    @staticmethod
    def _fix_markdown(text: str) -> str:
        """修复 Markdown 格式"""
        lines = text.split("\n")
        fixed_lines = []
        in_code_block = False

        for line in lines:
            # 代码块标记
            if line.strip().startswith("```"):
                in_code_block = not in_code_block

            # 如果不在代码块中，确保标题有空格
            if not in_code_block:
                for i in range(1, 7):
                    if line.startswith("#" * i) and not line.startswith("#" * (i + 1)):
                        if line[i] != " ":
                            line = line[:i] + " " + line[i:]
                        break

            fixed_lines.append(line)

        return "\n".join(fixed_lines)

    @staticmethod
    def _markdown_to_html(text: str) -> str:
        """Markdown 转 HTML"""
        html = text
        # 标题
        for i in range(6, 0, -1):
            html = re.sub(
                rf'^#{{{i}}}\s+(.+)$',
                rf'<h{i}>\1</h{i}>',
                html,
                flags=re.MULTILINE
            )
        # 粗体
        html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
        # 斜体
        html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)
        # 代码
        html = re.sub(r'`([^`]+)`', r'<code>\1</code>', html)

        return html

    @staticmethod
    def _strip_markdown(text: str) -> str:
        """移除 Markdown 格式"""
        text = re.sub(r'#{1,6}\s+', '', text)
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'\*(.+?)\*', r'\1', text)
        text = re.sub(r'`([^`]+)`', r'\1', text)
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
        return text


class CodeProcessor:
    """代码处理器"""

    # 支持的语言
    SUPPORTED_LANGUAGES = {
        "python", "javascript", "typescript", "java", "cpp", "c",
        "go", "rust", "ruby", "php", "swift", "kotlin", "scala",
        "sql", "html", "css", "shell", "bash", "powershell"
    }

    @classmethod
    def detect_language(cls, code: str) -> str:
        """检测代码语言"""
        # 简单启发式检测
        if re.search(r'def\s+\w+\s*\(', code):
            return "python"
        elif re.search(r'function\s+\w+\s*\(', code) or re.search(r'=>\s*{', code):
            return "javascript"
        elif re.search(r'public\s+(class|interface|void)', code):
            return "java"
        elif re.search(r'func\s+\w+\s*\(', code) and 'package' not in code:
            return "swift"
        elif re.search(r'SELECT|INSERT|UPDATE|DELETE', code, re.IGNORECASE):
            return "sql"
        elif re.search(r'<[a-z]+[^>]*>.*?</[a-z]+>', code, re.DOTALL):
            return "html"

        return "plain"

    @classmethod
    def extract_signatures(cls, code: str, language: str) -> Dict[str, Any]:
        """提取代码签名"""
        signatures = {
            "functions": [],
            "classes": [],
            "imports": [],
            "exports": []
        }

        if language == "python":
            # 函数
            signatures["functions"] = re.findall(
                r'def\s+(\w+)\s*\(([^)]*)\)',
                code
            )
            # 类
            signatures["classes"] = re.findall(
                r'class\s+(\w+)(?:\([^)]*\))?:',
                code
            )
            # 导入
            signatures["imports"] = re.findall(
                r'(?:from\s+(\S+)\s+import|import\s+(\S+))',
                code
            )

        elif language in ["javascript", "typescript"]:
            # 函数
            signatures["functions"] = re.findall(
                r'(?:function\s+(\w+)|const\s+(\w+)\s*=\s*(?:async\s*)?\(|(\w+)\s*:\s*(?:async\s*)?\()',
                code
            )
            # 类
            signatures["classes"] = re.findall(r'class\s+(\w+)', code)
            # 导出
            signatures["exports"] = re.findall(r'export\s+(?:default\s+)?(\w+)', code)

        return signatures

    @classmethod
    def validate_syntax(cls, code: str, language: str) -> Tuple[bool, List[str]]:
        """验证语法（简单检查）"""
        errors = []

        # 基本括号匹配
        brackets = {'(': ')', '[': ']', '{': '}'}
        stack = []

        for i, char in enumerate(code):
            if char in brackets:
                stack.append((char, i))
            elif char in brackets.values():
                if not stack:
                    errors.append(f"Unmatched closing bracket at position {i}")
                else:
                    open_char, _ = stack.pop()
                    if brackets.get(open_char) != char:
                        errors.append(
                            f"Mismatched bracket: expected {brackets[open_char]}, got {char}"
                        )

        if stack:
            errors.append(f"Unclosed brackets: {len(stack)} remaining")

        return len(errors) == 0, errors

    @classmethod
    def format_code(cls, code: str, language: str) -> str:
        """格式化代码"""
        if language == "python":
            return cls._format_python(code)
        return code

    @staticmethod
    def _format_python(code: str) -> str:
        """格式化 Python 代码（简单版本）"""
        lines = code.split("\n")
        formatted = []
        indent_level = 0

        for line in lines:
            stripped = line.strip()

            # 减少缩进
            if stripped.startswith(("return", "break", "continue", "pass", "raise")):
                if indent_level > 0:
                    indent_level -= 1

            formatted.append("    " * indent_level + stripped)

            # 增加缩进
            if stripped.endswith(":") and not stripped.startswith("#"):
                indent_level += 1

        return "\n".join(formatted)


class VoiceProcessor:
    """语音处理器"""

    @classmethod
    def text_to_speech_config(cls, text: str, voice: str = "default") -> Dict[str, Any]:
        """文本转语音配置"""
        return {
            "text": text,
            "voice": voice,
            "rate": 1.0,
            "pitch": 1.0,
            "format": "mp3"
        }

    @classmethod
    def speech_to_text_config(cls, audio_data: str, language: str = "zh-CN") -> Dict[str, Any]:
        """语音转文本配置"""
        return {
            "audio_data": audio_data,
            "language": language,
            "model": "whisper"
        }

    @classmethod
    def extract_commands(cls, transcript: str) -> List[Dict[str, str]]:
        """从语音转录中提取命令"""
        commands = []

        # 常见命令模式
        patterns = [
            (r'运行(\w+)', 'run'),
            (r'执行(\w+)', 'execute'),
            (r'创建(\w+)', 'create'),
            (r'打开(\w+)', 'open'),
            (r'关闭(\w+)', 'close')
        ]

        for pattern, action in patterns:
            matches = re.findall(pattern, transcript)
            for match in matches:
                commands.append({
                    "action": action,
                    "target": match,
                    "confidence": 0.9
                })

        return commands


class ImageProcessor:
    """图像处理器"""

    @classmethod
    def extract_diagram_type(cls, description: str) -> str:
        """提取图表类型"""
        desc_lower = description.lower()

        if any(k in desc_lower for k in ["flow", "流程", "process"]):
            return "flowchart"
        elif any(k in desc_lower for k in ["class", "uml", "结构"]):
            return "uml"
        elif any(k in desc_lower for k in ["sequence", "时序", "时间"]):
            return "sequence"
        elif any(k in desc_lower for k in ["architecture", "架构"]):
            return "architecture"
        elif any(k in desc_lower for k in ["mind", "思维", "brain"]):
            return "mindmap"

        return "generic"

    @classmethod
    def generate_plantuml(cls, description: str, diagram_type: str) -> str:
        """生成 PlantUML 代码"""
        if diagram_type == "flowchart":
            return cls._generate_flowchart(description)
        elif diagram_type == "sequence":
            return cls._generate_sequence(description)
        elif diagram_type == "class":
            return cls._generate_class(description)

        return "@startuml\n!theme plain\n' Generic diagram\n@enduml"

    @staticmethod
    def _generate_flowchart(description: str) -> str:
        """生成流程图"""
        return f"""@startuml
skinparam defaultTextAlignment center

start
:Parse intent from query;
:Understand context;
if (Context sufficient?) then (yes)
  :Generate response;
else (no)
  :Request clarification;
endif
:Return response;
stop
@enduml"""

    @staticmethod
    def _generate_sequence(description: str) -> str:
        """生成时序图"""
        return """@startuml
participant User
participant "AI Engine" as AI
participant "Context Manager" as CM
participant "Knowledge Base" as KB

User -> AI: Query
AI -> CM: Get context
CM -> KB: Search
KB --> CM: Results
CM --> AI: Context
AI -> AI: Process & Generate
AI --> User: Response
@enduml"""

    @staticmethod
    def _generate_class(description: str) -> str:
        """生成类图"""
        return """@startuml
class ContextManager {
  +compress()
  +verify()
  +index()
}
class DigitalTwin {
  +learn()
  +evolve()
  +predict()
}
class KnowledgeBase {
  +store()
  +retrieve()
  +update()
}
ContextManager --> DigitalTwin
DigitalTwin --> KnowledgeBase
@enduml"""


class DocumentProcessor:
    """文档处理器"""

    SUPPORTED_FORMATS = {"pdf", "docx", "pptx", "markdown", "txt"}

    @classmethod
    def detect_format(cls, filename: str) -> str:
        """检测文档格式"""
        ext = filename.lower().split('.')[-1]

        format_map = {
            "md": "markdown",
            "txt": "text",
            "pdf": "pdf",
            "docx": "docx",
            "pptx": "pptx"
        }

        return format_map.get(ext, "unknown")

    @classmethod
    def extract_structure(cls, content: str, format_type: str) -> Dict[str, Any]:
        """提取文档结构"""
        structure = {
            "title": "",
            "sections": [],
            "code_blocks": [],
            "images": [],
            "tables": []
        }

        if format_type == "markdown":
            structure = cls._extract_markdown_structure(content)

        return structure

    @staticmethod
    def _extract_markdown_structure(content: str) -> Dict[str, Any]:
        """提取 Markdown 结构"""
        structure = {
            "title": "",
            "sections": [],
            "code_blocks": [],
            "images": [],
            "tables": []
        }

        lines = content.split("\n")
        current_section = None

        for line in lines:
            # 标题
            if line.startswith("# "):
                structure["title"] = line[2:].strip()
                current_section = structure["title"]
            elif line.startswith("## "):
                current_section = line[3:].strip()
                structure["sections"].append({
                    "level": 2,
                    "title": current_section,
                    "content": []
                })
            elif line.startswith("### "):
                structure["sections"].append({
                    "level": 3,
                    "title": line[4:].strip(),
                    "content": []
                })

            # 代码块
            if line.strip().startswith("```"):
                structure["code_blocks"].append(line.strip())

            # 图片
            img_match = re.search(r'!\[([^\]]*)\]\(([^)]+)\)', line)
            if img_match:
                structure["images"].append({
                    "alt": img_match.group(1),
                    "url": img_match.group(2)
                })

        return structure


# ============================================================================
# 多模态交互管理器
# ============================================================================

class MultimodalInteractionManager:
    """多模态交互管理器"""

    def __init__(self, twin_id: str = ""):
        self.twin_id = twin_id

        # 处理器
        self.text_processor = TextProcessor()
        self.code_processor = CodeProcessor()
        self.voice_processor = VoiceProcessor()
        self.image_processor = ImageProcessor()
        self.document_processor = DocumentProcessor()

        # 上下文管理器（可注入）
        self.context_manager = None

        # 历史
        self.message_history: List[MultimodalMessage] = []
        self.response_history: List[MultimodalResponse] = []

    def set_context_manager(self, context_manager) -> None:
        """设置上下文管理器"""
        self.context_manager = context_manager

    def parse_message(
        self,
        content: Union[str, Dict, List],
        user_id: str = "",
        interaction_mode: str = "conversation"
    ) -> MultimodalMessage:
        """解析多模态消息"""
        message = MultimodalMessage(
            user_id=user_id,
            twin_id=self.twin_id,
            interaction_mode=interaction_mode
        )

        # 字符串输入
        if isinstance(content, str):
            # 提取文本和代码块
            code_blocks = self.text_processor.extract_code_blocks(content)

            if code_blocks:
                # 有代码块，添加代码
                for lang, code in code_blocks:
                    message.add_block(ContentBlock(
                        modality="code",
                        content=code,
                        language=lang,
                        format_type=lang
                    ))

                # 剩余文本
                text_only = re.sub(r'```[\w]*\n.*?```', '', content, flags=re.DOTALL)
                if text_only.strip():
                    message.add_block(ContentBlock(
                        modality="text",
                        content=text_only.strip()
                    ))
            else:
                message.add_block(ContentBlock(
                    modality="text",
                    content=content
                ))

        # 字典输入
        elif isinstance(content, dict):
            blocks = content.get("blocks", [])
            for block in blocks:
                message.add_block(ContentBlock(
                    modality=block.get("modality", "text"),
                    content=block.get("content", ""),
                    language=block.get("language", ""),
                    format_type=block.get("format", "plain")
                ))

        # 列表输入
        elif isinstance(content, list):
            for item in content:
                if isinstance(item, dict):
                    message.add_block(ContentBlock(
                        modality=item.get("modality", "text"),
                        content=item.get("content", ""),
                        language=item.get("language", "")
                    ))
                else:
                    message.add_block(ContentBlock(
                        modality="text",
                        content=str(item)
                    ))

        # 保存历史
        self.message_history.append(message)

        return message

    def generate_response(
        self,
        message: MultimodalMessage,
        context: str = "",
        options: Dict[str, Any] = None
    ) -> MultimodalResponse:
        """生成多模态响应"""
        options = options or {}
        response = MultimodalResponse(message_id=message.message_id)

        # 获取主模态
        primary_modality = message.primary_modality

        # 文本处理
        if primary_modality in ["text", "mixed"]:
            text_content = message.get_text_content()
            intent = self.text_processor.extract_intent(text_content)

            # 生成文本响应
            response_text = self._generate_text_response(
                text_content,
                intent,
                context
            )
            response.add_text(response_text)

        # 代码处理
        code_blocks = message.get_code_blocks()
        if code_blocks:
            for lang, code in code_blocks:
                # 分析代码
                signatures = self.code_processor.extract_signatures(code, lang)
                valid, errors = self.code_processor.validate_syntax(code, lang)

                if not valid:
                    response.add_text(f"[Code Analysis] Found {len(errors)} issues")
                    for error in errors:
                        response.add_text(f"  - {error}")

        # 添加建议动作
        if message.primary_modality == "text":
            response.add_action({
                "type": "quick_command",
                "label": "Format Code",
                "command": "/format"
            })
            response.add_action({
                "type": "quick_command",
                "label": "Explain",
                "command": "/explain"
            })

        # 保存历史
        self.response_history.append(response)

        return response

    def _generate_text_response(
        self,
        text: str,
        intent: Dict[str, Any],
        context: str
    ) -> str:
        """生成文本响应"""
        action = intent.get("primary_action", "general")
        entities = intent.get("entities", [])

        # 基于意图生成响应
        responses = {
            "create": f"理解创建请求。目标: {', '.join(entities) if entities else '未指定'}",
            "modify": f"理解修改请求。将更新: {', '.join(entities) if entities else '相关组件'}",
            "delete": f"理解删除请求。将移除: {', '.join(entities) if entities else '指定内容'}",
            "search": f"正在搜索: {', '.join(entities) if entities else '相关内容'}",
            "explain": f"正在分析: {', '.join(entities) if entities else '内容'}",
            "execute": f"准备执行: {', '.join(entities) if entities else '指定操作'}",
            "debug": f"正在调试: {', '.join(entities) if entities else '问题'}",
            "review": f"正在审核: {', '.join(entities) if entities else '代码'}"
        }

        base_response = responses.get(action, f"理解请求: {text[:50]}...")

        # 添加上下文信息
        if context:
            base_response += f"\n\n[Context: {len(context)} chars loaded]"

        return base_response

    def create_visualization(
        self,
        data: Dict[str, Any],
        viz_type: str = "chart"
    ) -> ContentBlock:
        """创建可视化"""
        if viz_type == "chart":
            return self._create_chart(data)
        elif viz_type == "diagram":
            return self._create_diagram(data)
        elif viz_type == "table":
            return self._create_table(data)

        return ContentBlock(modality="text", content="Unsupported visualization type")

    def _create_chart(self, data: Dict[str, Any]) -> ContentBlock:
        """创建图表"""
        chart_type = data.get("type", "bar")
        chart_data = data.get("data", {})

        # 生成 Chart.js 配置
        config = {
            "type": chart_type,
            "data": chart_data,
            "options": {
                "responsive": True,
                "maintainAspectRatio": False
            }
        }

        return ContentBlock(
            modality="image",
            content=json.dumps(config),
            format_type="chartjs",
            metadata={"chart_type": chart_type}
        )

    def _create_diagram(self, data: Dict[str, Any]) -> ContentBlock:
        """创建图表"""
        description = data.get("description", "")
        diagram_type = self.image_processor.extract_diagram_type(description)
        plantuml = self.image_processor.generate_plantuml(description, diagram_type)

        return ContentBlock(
            modality="image",
            content=plantuml,
            format_type="plantuml",
            metadata={"diagram_type": diagram_type}
        )

    def _create_table(self, data: Dict[str, Any]) -> ContentBlock:
        """创建表格"""
        headers = data.get("headers", [])
        rows = data.get("rows", [])

        # 生成 Markdown 表格
        table = "| " + " | ".join(headers) + " |\n"
        table += "| " + " | ".join(["---"] * len(headers)) + " |\n"

        for row in rows:
            table += "| " + " | ".join(str(cell) for cell in row) + " |\n"

        return ContentBlock(
            modality="text",
            content=table,
            format_type="markdown"
        )

    def get_conversation_context(self) -> str:
        """获取对话上下文"""
        contexts = []

        # 最近 N 条消息
        recent_messages = self.message_history[-5:]

        for msg in recent_messages:
            text = msg.get_text_content()
            if text:
                contexts.append(f"[{msg.primary_modality}] {text[:200]}")

        return "\n\n".join(contexts)

    def to_dict(self) -> Dict:
        """序列化"""
        return {
            "twin_id": self.twin_id,
            "message_history_count": len(self.message_history),
            "response_history_count": len(self.response_history)
        }


# ============================================================================
# 便捷函数
# ============================================================================

def create_multimodal_manager(twin_id: str = "") -> MultimodalInteractionManager:
    """创建多模态交互管理器"""
    return MultimodalInteractionManager(twin_id)


def parse_multimodal(content: Union[str, Dict, List], **kwargs) -> MultimodalMessage:
    """快速解析多模态消息"""
    manager = MultimodalInteractionManager()
    return manager.parse_message(content, **kwargs)


def generate_multimodal_response(
    content: Union[str, Dict, List],
    context: str = "",
    **kwargs
) -> MultimodalResponse:
    """快速生成多模态响应"""
    manager = MultimodalInteractionManager()
    message = manager.parse_message(content, **kwargs)
    return manager.generate_response(message, context)


# ============================================================================
# 测试
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("[TEST] Phase 4: Multimodal Interaction Integration")
    print("=" * 60)

    # Test 1: Create Manager
    print("\n[Test 1] Create Multimodal Manager")
    manager = create_multimodal_manager("twin_001")
    print(f"  Twin ID: {manager.twin_id}")
    print(f"  Processors: text/code/voice/image/document")

    # Test 2: Parse Text Message
    print("\n[Test 2] Parse Text Message")
    message = manager.parse_message("帮我创建一个用户管理类", user_id="user_001")
    print(f"  Message ID: {message.message_id}")
    print(f"  Primary Modality: {message.primary_modality}")
    print(f"  Blocks: {len(message.content_blocks)}")

    # Test 3: Parse Mixed Content
    print("\n[Test 3] Parse Mixed Content")
    mixed_content = """
    请帮我优化这段代码：

    ```python
    def calculate(a,b):
        return a+b
    ```

    另外，请解释一下这个函数的用途。
    """
    message = manager.parse_message(mixed_content)
    print(f"  Primary Modality: {message.primary_modality}")
    print(f"  Blocks: {len(message.content_blocks)}")
    for block in message.content_blocks:
        print(f"    - {block.modality}: {block.language or block.format_type}")

    # Test 4: Generate Response
    print("\n[Test 4] Generate Response")
    response = manager.generate_response(
        message,
        context="User management module"
    )
    print(f"  Response ID: {response.response_id}")
    print(f"  Blocks: {len(response.content_blocks)}")
    for block in response.content_blocks:
        print(f"    Content: {block.content[:50]}...")

    # Test 5: Code Processor
    print("\n[Test 5] Code Processor")
    code = """
    import os
    from typing import List

    class UserManager:
        def __init__(self):
            self.users = []

        def add_user(self, name: str) -> bool:
            self.users.append(name)
            return True

        def get_users(self) -> List[str]:
            return self.users
    """
    lang = CodeProcessor.detect_language(code)
    print(f"  Detected Language: {lang}")

    signatures = CodeProcessor.extract_signatures(code, lang)
    print(f"  Classes: {[s[0] for s in signatures['classes']]}")
    print(f"  Functions: {[s[0] for s in signatures['functions']]}")

    valid, errors = CodeProcessor.validate_syntax(code, lang)
    print(f"  Valid: {valid}")

    # Test 6: Text Processor
    print("\n[Test 6] Text Processor")
    intent = TextProcessor.extract_intent("创建用户管理类和登录函数")
    print(f"  Intent: {intent['primary_action']}")
    print(f"  Entities: {intent['entities']}")

    code_blocks = TextProcessor.extract_code_blocks(mixed_content)
    print(f"  Code Blocks Found: {len(code_blocks)}")

    # Test 7: Image Processor
    print("\n[Test 7] Image Processor")
    diagram_type = ImageProcessor.extract_diagram_type("创建一个用户认证流程图")
    print(f"  Diagram Type: {diagram_type}")

    plantuml = ImageProcessor.generate_plantuml("流程图", diagram_type)
    print(f"  PlantUML Generated: {len(plantuml)} chars")

    # Test 8: Voice Processor
    print("\n[Test 8] Voice Processor")
    commands = VoiceProcessor.extract_commands("请运行这个程序并打开设置")
    print(f"  Commands Extracted: {len(commands)}")
    for cmd in commands:
        print(f"    {cmd}")

    # Test 9: Document Processor
    print("\n[Test 9] Document Processor")
    md_content = """# User Management

## Features
- User registration
- User login

## Code
```python
class User:
    pass
```
"""
    structure = DocumentProcessor.extract_structure(md_content, "markdown")
    print(f"  Title: {structure['title']}")
    print(f"  Sections: {len(structure['sections'])}")
    print(f"  Code Blocks: {len(structure['code_blocks'])}")

    # Test 10: Visualization
    print("\n[Test 10] Visualization")
    chart_data = {
        "type": "bar",
        "data": {
            "labels": ["Jan", "Feb", "Mar"],
            "datasets": [{"label": "Sales", "data": [100, 150, 200]}]
        }
    }
    chart_block = manager.create_visualization(chart_data, "chart")
    print(f"  Chart Type: {chart_block.metadata.get('chart_type')}")

    table_data = {
        "headers": ["Name", "Type", "Status"],
        "rows": [["UserManager", "class", "active"], ["login", "method", "active"]]
    }
    table_block = manager.create_visualization(table_data, "table")
    print(f"  Table Content: {table_block.content[:100]}...")

    # Test 11: Conversation Context
    print("\n[Test 11] Conversation Context")
    manager.parse_message("第一个问题")
    manager.parse_message("第二个问题")
    manager.parse_message("第三个问题")
    context = manager.get_conversation_context()
    print(f"  Context Length: {len(context)} chars")
    print(f"  Recent Messages: 3")

    # Test 12: Multimodal Message Dict
    print("\n[Test 12] Multimodal Message Serialization")
    message = manager.parse_message({"blocks": [
        {"modality": "text", "content": "Hello"},
        {"modality": "code", "language": "python", "content": "print('hi')"}
    ]})
    data = message.to_dict()
    print(f"  Serialized Keys: {list(data.keys())}")

    print("\n" + "=" * 60)
    print("[COMPLETE] Phase 4 Tests")
    print("=" * 60)
