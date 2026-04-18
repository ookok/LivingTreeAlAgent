"""
AI 写作助手
全学科智能写作助手 - 核心集成模块

功能：
1. 整合 Hermes Agent 进行智能写作
2. 学科自适应工作空间
3. 多格式输出支持
4. 实时协作编辑
"""

import json
import re
from pathlib import Path
from typing import Optional, Callable, Iterator
from dataclasses import dataclass, field
from enum import Enum

from writing.intent_detector import IntentDetector, IntentResult, DocType, SubjectDomain, WritingFormat
from writing.latex_processor import LatexProcessor
from writing.outline_generator import OutlineGenerator
from writing.citation_manager import CitationManager


class WritingMode(Enum):
    """写作模式"""
    AUTO = "auto"                # 自动模式（AI 主导）
    ASSIST = "assist"            # 辅助模式（用户主导）
    REVIEW = "review"            # 审阅模式
    COLLABORATE = "collaborate"  # 协作模式


@dataclass
class WritingContext:
    """写作上下文"""
    project_name: str = ""
    doc_type: DocType = DocType.GENERAL
    subject: SubjectDomain = SubjectDomain.GENERAL
    target_format: WritingFormat = WritingFormat.MARKDOWN
    language: str = "zh"
    template: Optional[str] = None
    outline: Optional[list] = None
    citations: list = field(default_factory=list)
    custom_instructions: str = ""


@dataclass
class WritingResult:
    """写作结果"""
    success: bool
    content: str = ""
    format: WritingFormat = WritingFormat.MARKDOWN
    errors: list = field(default_factory=list)
    suggestions: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class AIWriter:
    """
    AI 写作助手

    整合 Hermes Agent 的能力，提供：
    - 意图驱动的写作
    - 学科自适应工作空间
    - LaTeX 公式处理
    - 智能大纲生成
    - 文献管理
    """

    def __init__(self, agent=None):
        """
        初始化 AI 写作助手

        Args:
            agent: Hermes Agent 实例（可选）
        """
        self.agent = agent
        self.intent_detector = IntentDetector()
        self.latex_processor = LatexProcessor()
        self.outline_generator = OutlineGenerator()
        self.citation_manager = CitationManager()

        # 当前写作上下文
        self.current_context = WritingContext()

        # 写作历史
        self._history: list[WritingContext] = []

    def set_agent(self, agent):
        """设置 Hermes Agent"""
        self.agent = agent

    def analyze_input(self, content: str = None, file_path: str = None) -> IntentResult:
        """
        分析输入内容，识别写作意图

        Args:
            content: 文本内容
            file_path: 文件路径

        Returns:
            IntentResult: 意图识别结果
        """
        from writing.intent_detector import AnalysisContext

        if file_path:
            return self.intent_detector.detect_from_file(file_path)

        if content:
            ctx = AnalysisContext(file_content=content)
            return self.intent_detector.detect(ctx)

        # 空输入，返回默认
        return IntentResult(
            doc_type=DocType.GENERAL,
            subject=SubjectDomain.GENERAL,
            suggested_format=WritingFormat.MARKDOWN,
            confidence=0.0,
            reasoning="无输入内容"
        )

    def set_context(self, context: WritingContext):
        """设置写作上下文"""
        self.current_context = context

        # 同步到子模块
        if context.outline:
            self.outline_generator.set_template(context.doc_type, context.subject)

    def create_document(self, title: str, content: str = "", section: str = "introduction") -> WritingResult:
        """
        创建文档

        Args:
            title: 文档标题
            content: 初始内容
            section: 章节类型

        Returns:
            WritingResult: 写作结果
        """
        result = WritingResult(success=False)

        try:
            # 根据上下文生成内容
            if not content and self.agent:
                content = self._generate_content(title, section)

            # 应用格式
            formatted = self._apply_format(title, content)

            result.success = True
            result.content = formatted
            result.format = self.current_context.target_format

        except Exception as e:
            result.errors.append(str(e))

        return result

    def continue_writing(self, current_content: str, instruction: str = "") -> WritingResult:
        """
        继续写作

        Args:
            current_content: 当前内容
            instruction: 写作指令

        Returns:
            WritingResult: 写作结果
        """
        result = WritingResult(success=False)

        if not self.agent:
            result.errors.append("Agent 未设置，无法继续写作")
            return result

        try:
            # 构建提示
            prompt = self._build_continue_prompt(current_content, instruction)

            # 调用 AI
            response = self._call_ai(prompt)

            result.success = True
            result.content = current_content + "\n\n" + response
            result.suggestions = self._extract_suggestions(response)

        except Exception as e:
            result.errors.append(str(e))

        return result

    def revise_text(self, text: str, instruction: str) -> WritingResult:
        """
        修改文本

        Args:
            text: 待修改文本
            instruction: 修改指令

        Returns:
            WritingResult: 修改结果
        """
        result = WritingResult(success=False)

        if not self.agent:
            result.errors.append("Agent 未设置")
            return result

        try:
            # 检查是否涉及 LaTeX
            formulas = self.latex_processor.extract_from_text(text)

            if formulas and ('公式' in instruction or 'latex' in instruction.lower()):
                # 公式修改
                new_formulas = []
                for formula in formulas:
                    parsed = self.latex_processor.parse(formula)
                    transformed = self.latex_processor.transform(parsed.latex, instruction)
                    new_formulas.append(transformed)

                # 替换原公式
                new_text = text
                for old, new in zip(formulas, new_formulas):
                    new_text = new_text.replace(old, new)

                result.content = new_text
            else:
                # 文本修改
                prompt = f"""请根据以下指令修改文本：

指令: {instruction}

原文:
{text}

请直接输出修改后的文本，保持原有格式。"""

                response = self._call_ai(prompt)
                result.content = response

            result.success = True

        except Exception as e:
            result.errors.append(str(e))

        return result

    def generate_outline(self, topic: str, doc_type: DocType = None) -> list:
        """
        生成大纲

        Args:
            topic: 主题
            doc_type: 文档类型

        Returns:
            list: 大纲结构
        """
        doc_type = doc_type or self.current_context.doc_type
        return self.outline_generator.generate(topic, doc_type, self.current_context.subject)

    def add_citation(self, ref_text: str) -> str:
        """
        添加引用

        Args:
            ref_text: 参考文献文本

        Returns:
            str: BibTeX 格式
        """
        bibtex = self.citation_manager.parse_and_convert(ref_text)
        self.current_context.citations.append(bibtex)
        return bibtex

    def insert_equation(self, equation: str, description: str = "") -> str:
        """
        插入公式

        Args:
            equation: 公式内容（自然语言或 LaTeX）
            description: 公式描述

        Returns:
            str: 格式化后的 LaTeX
        """
        # 解析公式
        if '$' not in equation and '\\' not in equation:
            # 自然语言描述，需要 AI 转换
            if self.agent:
                prompt = f"""将以下数学描述转换为标准 LaTeX 公式：

描述: {equation}

请只输出 LaTeX 代码，用 $$ 包裹。"""

                try:
                    response = self._call_ai(prompt)
                    equation = response.strip()
                    if equation.startswith('$$') and equation.endswith('$$'):
                        equation = equation[2:-2]
                except Exception:
                    pass

        # 验证并解析
        parsed = self.latex_processor.parse(equation)

        if parsed.semantic_description:
            # 可以将描述加入注释
            pass

        # 格式化输出
        return self.latex_processor.convert_to_display(parsed.latex)

    def _generate_content(self, title: str, section: str) -> str:
        """生成内容"""
        if not self.agent:
            return f"# {title}\n\n[内容待生成]"

        prompt = f"""请为以下内容生成 {section} 部分：

标题: {title}
类型: {self.current_context.doc_type.value}
学科: {self.current_context.subject.value}
语言: {self.current_context.language}

请生成内容，使用 {self.current_context.target_format.value} 格式。"""

        return self._call_ai(prompt)

    def _apply_format(self, title: str, content: str) -> str:
        """应用格式"""
        fmt = self.current_context.target_format

        if fmt == WritingFormat.LATEX:
            return self._to_latex(title, content)
        elif fmt == WritingFormat.MARKDOWN:
            return f"# {title}\n\n{content}"
        else:
            return content

    def _to_latex(self, title: str, content: str) -> str:
        """转换为 LaTeX"""
        template = r"""\documentclass{article}
\title{%s}
\author{}
\date{%s}

\begin{document}
\maketitle

%s

\end{document}"""

        from datetime import datetime
        date = datetime.now().strftime("%Y-%m-%d")

        return template % (title, date, content)

    def _build_continue_prompt(self, current_content: str, instruction: str) -> str:
        """构建继续写作提示"""
        parts = []

        parts.append("请继续以下文本的写作，保持相同的风格和格式：\n")
        parts.append(f"当前内容:\n{current_content}\n")

        if instruction:
            parts.append(f"\n写作指令: {instruction}")

        return "".join(parts)

    def _call_ai(self, prompt: str) -> str:
        """调用 AI"""
        if not self.agent:
            return "[AI 未连接]"

        # 简化实现 - 实际应该使用 agent.send_message
        return f"[AI 响应: {prompt[:50]}...]"

    def _extract_suggestions(self, content: str) -> list:
        """提取建议"""
        suggestions = []

        # 检查是否有 TODO 或建议标记
        todos = re.findall(r'TODO[:：]\s*(.+)', content)
        suggestions.extend(todos)

        return suggestions

    def export_document(self, content: str, output_path: str, format: WritingFormat = None) -> bool:
        """
        导出文档

        Args:
            content: 文档内容
            output_path: 输出路径
            format: 输出格式

        Returns:
            bool: 是否成功
        """
        format = format or self.current_context.target_format

        try:
            path = Path(output_path)

            if format == WritingFormat.LATEX:
                path = path.with_suffix('.tex')
            elif format == WritingFormat.DOCX:
                path = path.with_suffix('.docx')
            elif format == WritingFormat.MARKDOWN:
                path = path.with_suffix('.md')
            else:
                path = path.with_suffix('.txt')

            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding='utf-8')

            return True

        except Exception:
            return False


# 单例
_writer: Optional[AIWriter] = None


def get_ai_writer(agent=None) -> AIWriter:
    """获取 AI 写作助手单例"""
    global _writer
    if _writer is None:
        _writer = AIWriter(agent)
    return _writer
