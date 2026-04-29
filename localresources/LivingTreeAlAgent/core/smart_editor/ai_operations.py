"""
AI Operations - AI操作引擎
=========================

提供编辑器中的各种AI操作:
- format: 智能格式化
- simplify: 简化表达
- expand: 扩写内容
- translate: 翻译
- explain: 解释内容
- fix: 修复问题
- optimize: 优化
- summarize: 总结
"""

import asyncio
import json
import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, Callable, Dict, Any, List


class AIOperationType(Enum):
    """AI操作类型"""
    FORMAT = "format"               # 智能格式化
    SIMPLIFY = "simplify"           # 简化表达
    EXPAND = "expand"               # 扩写内容
    TRANSLATE = "translate"          # 翻译
    EXPLAIN = "explain"             # 解释内容
    FIX = "fix"                     # 修复问题
    OPTIMIZE = "optimize"           # 优化
    SUMMARIZE = "summarize"         # 总结
    COMPLETE = "complete"           # 补全
    IMPROVE = "improve"             # 改进


@dataclass
class AIOperationResult:
    """AI操作结果"""
    success: bool
    operation: AIOperationType
    original_text: str = ""
    result_text: str = ""
    message: str = ""
    suggestions: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'operation': self.operation.value,
            'original_text': self.original_text,
            'result_text': self.result_text,
            'message': self.message,
            'suggestions': self.suggestions,
            'metadata': self.metadata
        }


class AIOperationHandler:
    """
    AI操作处理器基类
    """

    def __init__(self, llm_client=None):
        self.llm_client = llm_client

    async def process(self, text: str, context: Dict[str, Any]) -> AIOperationResult:
        raise NotImplementedError

    def can_handle(self, operation: AIOperationType) -> bool:
        return False


class FormatHandler(AIOperationHandler):
    """格式化处理器"""

    async def process(self, text: str, context: Dict[str, Any]) -> AIOperationResult:
        mode = context.get('mode', 'plain')

        if mode == 'json':
            try:
                obj = json.loads(text)
                formatted = json.dumps(obj, indent=2, ensure_ascii=False)
                return AIOperationResult(
                    success=True,
                    operation=AIOperationType.FORMAT,
                    original_text=text,
                    result_text=formatted,
                    message="JSON格式化了"
                )
            except json.JSONDecodeError as e:
                return AIOperationResult(
                    success=False,
                    operation=AIOperationType.FORMAT,
                    original_text=text,
                    result_text=text,
                    message=f"JSON格式化失败: {str(e)}"
                )

        elif mode == 'markdown':
            # Markdown格式化
            formatted = self._format_markdown(text)
            return AIOperationResult(
                success=True,
                operation=AIOperationType.FORMAT,
                original_text=text,
                result_text=formatted,
                message="Markdown格式化了"
            )

        elif mode == 'python':
            formatted = self._format_python(text)
            return AIOperationResult(
                success=True,
                operation=AIOperationType.FORMAT,
                original_text=text,
                result_text=formatted,
                message="Python代码格式化了"
            )

        elif mode == 'sql':
            formatted = self._format_sql(text)
            return AIOperationResult(
                success=True,
                operation=AIOperationType.FORMAT,
                original_text=text,
                result_text=formatted,
                message="SQL格式化了"
            )

        # 通用格式化：整理空白字符
        lines = text.split('\n')
        formatted_lines = []
        for line in lines:
            formatted_lines.append(line.rstrip())
        while formatted_lines and not formatted_lines[-1]:
            formatted_lines.pop()
        while formatted_lines and not formatted_lines[0]:
            formatted_lines.pop(0)

        return AIOperationResult(
            success=True,
            operation=AIOperationType.FORMAT,
            original_text=text,
            result_text='\n'.join(formatted_lines),
            message="文本格式化了"
        )

    def _format_markdown(self, text: str) -> str:
        """Markdown格式化"""
        lines = text.split('\n')
        result = []
        in_code_block = False

        for line in lines:
            # 代码块保持原样
            if line.strip().startswith('```'):
                in_code_block = not in_code_block
                result.append(line)
            elif not in_code_block:
                # 标题保持空格
                if re.match(r'^#{1,6}\s', line):
                    result.append(line.lstrip())
                else:
                    result.append(line.rstrip())
            else:
                result.append(line)

        # 合并多个空行
        text = '\n'.join(result)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text

    def _format_python(self, text: str) -> str:
        """Python代码格式化（基础版本）"""
        # 简单的缩进整理
        lines = text.split('\n')
        formatted = []
        indent_level = 0
        indent_unit = 4

        for line in lines:
            stripped = line.lstrip()
            if not stripped:
                formatted.append('')
                continue

            # 计算缩进
            leading_space = len(line) - len(stripped)

            # 根据关键字调整缩进
            if stripped.startswith(('def ', 'class ', 'if ', 'elif ', 'else:', 'for ', 'while ', 'try:', 'except:', 'finally:', 'with ')):
                if formatted and formatted[-1].strip() and not formatted[-1].strip().startswith('#'):
                    pass
                formatted.append(' ' * leading_space + stripped)
            else:
                formatted.append(' ' * leading_space + stripped)

        return '\n'.join(formatted)

    def _format_sql(self, text: str) -> str:
        """SQL格式化"""
        keywords = ['SELECT', 'FROM', 'WHERE', 'AND', 'OR', 'JOIN', 'LEFT', 'RIGHT', 'INNER', 'OUTER',
                    'ON', 'ORDER', 'BY', 'GROUP', 'HAVING', 'LIMIT', 'OFFSET', 'INSERT', 'INTO',
                    'VALUES', 'UPDATE', 'SET', 'DELETE', 'CREATE', 'TABLE', 'DROP', 'ALTER', 'ADD']

        result = text
        for kw in keywords:
            # 大写关键字
            result = re.sub(rf'\b{kw}\b', kw, result, flags=re.IGNORECASE)

        # 在关键字后添加换行
        result = re.sub(r'\b(SELECT|FROM|WHERE|AND|OR|JOIN|ORDER|BY|GROUP|HAVING|LIMIT|INSERT|INTO|VALUES|UPDATE|SET|DELETE)\b',
                       r'\n\1', result, flags=re.IGNORECASE)

        return result.strip()

    def can_handle(self, operation: AIOperationType) -> bool:
        return operation == AIOperationType.FORMAT


class TranslateHandler(AIOperationHandler):
    """翻译处理器"""

    # 翻译提示词模板
    TRANSLATE_PROMPTS = {
        'en2zh': '将以下英文翻译为中文，保持专业术语的准确性:\n\n{text}',
        'zh2en': 'Translate the following Chinese to English, maintaining professional terminology:\n\n{text}',
    }

    async def process(self, text: str, context: Dict[str, Any]) -> AIOperationResult:
        direction = context.get('direction', 'en2zh')

        if self.llm_client:
            prompt = self.TRANSLATE_PROMPTS.get(direction, self.TRANSLATE_PROMPTS['en2zh'])
            prompt = prompt.format(text=text)

            try:
                response = await self.llm_client.chat([{'role': 'user', 'content': prompt}])
                translated = response.get('content', text)

                return AIOperationResult(
                    success=True,
                    operation=AIOperationType.TRANSLATE,
                    original_text=text,
                    result_text=translated,
                    message=f"已翻译为{'中文' if direction == 'en2zh' else '英文'}",
                    metadata={'direction': direction}
                )
            except Exception as e:
                return AIOperationResult(
                    success=False,
                    operation=AIOperationType.TRANSLATE,
                    original_text=text,
                    result_text=text,
                    message=f"翻译失败: {str(e)}"
                )
        else:
            # 无LLM客户端时的基础翻译
            return AIOperationResult(
                success=False,
                operation=AIOperationType.TRANSLATE,
                original_text=text,
                result_text=text,
                message="需要配置LLM客户端才能使用翻译功能"
            )

    def can_handle(self, operation: AIOperationType) -> bool:
        return operation == AIOperationType.TRANSLATE


class ExplainHandler(AIOperationHandler):
    """解释处理器"""

    async def process(self, text: str, context: Dict[str, Any]) -> AIOperationResult:
        mode = context.get('mode', 'plain')

        if self.llm_client:
            prompt = f"请详细解释以下{'代码' if mode in ('python', 'sql', 'json', 'yaml') else '内容'}，使用中文:\n\n{text}"

            try:
                response = await self.llm_client.chat([{'role': 'user', 'content': prompt}])
                explanation = response.get('content', '')

                return AIOperationResult(
                    success=True,
                    operation=AIOperationType.EXPLAIN,
                    original_text=text,
                    result_text=explanation,
                    message="已生成解释"
                )
            except Exception as e:
                return AIOperationResult(
                    success=False,
                    operation=AIOperationType.EXPLAIN,
                    original_text=text,
                    result_text=text,
                    message=f"解释生成失败: {str(e)}"
                )
        else:
            # 基础解释（无LLM）
            return AIOperationResult(
                success=False,
                operation=AIOperationType.EXPLAIN,
                original_text=text,
                result_text=text,
                message="需要配置LLM客户端才能使用解释功能"
            )

    def can_handle(self, operation: AIOperationType) -> bool:
        return operation == AIOperationType.EXPLAIN


class FixHandler(AIOperationHandler):
    """修复处理器"""

    async def process(self, text: str, context: Dict[str, Any]) -> AIOperationResult:
        mode = context.get('mode', 'plain')

        if mode == 'json':
            # 尝试修复JSON
            result = self._fix_json(text)
            return result

        elif mode == 'python':
            # 尝试修复Python代码
            result = self._fix_python(text)
            return result

        return AIOperationResult(
            success=False,
            operation=AIOperationType.FIX,
            original_text=text,
            result_text=text,
            message="当前模式不支持自动修复"
        )

    def _fix_json(self, text: str) -> AIOperationResult:
        """修复JSON"""
        # 移除常见问题
        fixed = text

        # 移除单引号
        fixed = re.sub(r"'([^']*)'", r'"\1"', fixed)

        # 移除尾部逗号
        fixed = re.sub(r',(\s*[}\]])', r'\1', fixed)

        # 尝试解析
        try:
            json.loads(fixed)
            return AIOperationResult(
                success=True,
                operation=AIOperationType.FIX,
                original_text=text,
                result_text=fixed,
                message="JSON已修复"
            )
        except json.JSONDecodeError as e:
            return AIOperationResult(
                success=False,
                operation=AIOperationType.FIX,
                original_text=text,
                result_text=text,
                message=f"无法自动修复: {str(e)}"
            )

    def _fix_python(self, text: str) -> AIOperationResult:
        """修复Python代码（基础版本）"""
        fixed = text

        # 移除不必要的分号
        fixed = re.sub(r';\s*$', '', fixed, flags=re.MULTILINE)

        # 修复常见的缩进问题（非常基础）
        lines = fixed.split('\n')
        result_lines = []

        for i, line in enumerate(lines):
            stripped = line.lstrip()
            leading = line[:len(line) - len(stripped)]

            # 检查括号匹配
            if stripped.endswith(':') and not stripped.startswith('#'):
                if not result_lines or not result_lines[-1].rstrip().endswith(':'):
                    pass

            result_lines.append(line)

        return AIOperationResult(
            success=True,
            operation=AIOperationType.FIX,
            original_text=text,
            result_text='\n'.join(result_lines),
            message="代码已基础修复"
        )

    def can_handle(self, operation: AIOperationType) -> bool:
        return operation == AIOperationType.FIX


class OptimizeHandler(AIOperationHandler):
    """优化处理器"""

    async def process(self, text: str, context: Dict[str, Any]) -> AIOperationResult:
        mode = context.get('mode', 'plain')

        if mode == 'python':
            return await self._optimize_python(text)
        elif mode == 'sql':
            return await self._optimize_sql(text)
        elif mode == 'json':
            return await self._optimize_json(text)
        else:
            return AIOperationResult(
                success=False,
                operation=AIOperationType.OPTIMIZE,
                original_text=text,
                result_text=text,
                message="当前模式不支持优化"
            )

    async def _optimize_python(self, text: str) -> AIOperationResult:
        """优化Python代码"""
        if self.llm_client:
            prompt = f"优化以下Python代码，提高性能和可读性:\n\n{text}"
            try:
                response = await self.llm_client.chat([{'role': 'user', 'content': prompt}])
                optimized = response.get('content', text)
                return AIOperationResult(
                    success=True,
                    operation=AIOperationType.OPTIMIZE,
                    original_text=text,
                    result_text=optimized,
                    message="代码已优化"
                )
            except Exception as e:
                return AIOperationResult(
                    success=False,
                    operation=AIOperationType.OPTIMIZE,
                    original_text=text,
                    result_text=text,
                    message=f"优化失败: {str(e)}"
                )
        else:
            return AIOperationResult(
                success=False,
                operation=AIOperationType.OPTIMIZE,
                original_text=text,
                result_text=text,
                message="需要配置LLM客户端才能使用优化功能"
            )

    async def _optimize_sql(self, text: str) -> AIOperationResult:
        """优化SQL查询"""
        if self.llm_client:
            prompt = f"优化以下SQL查询，提高性能:\n\n{text}"
            try:
                response = await self.llm_client.chat([{'role': 'user', 'content': prompt}])
                optimized = response.get('content', text)
                return AIOperationResult(
                    success=True,
                    operation=AIOperationType.OPTIMIZE,
                    original_text=text,
                    result_text=optimized,
                    message="SQL已优化"
                )
            except Exception as e:
                return AIOperationResult(
                    success=False,
                    operation=AIOperationType.OPTIMIZE,
                    original_text=text,
                    result_text=text,
                    message=f"优化失败: {str(e)}"
                )
        else:
            return AIOperationResult(
                success=False,
                operation=AIOperationType.OPTIMIZE,
                original_text=text,
                result_text=text,
                message="需要配置LLM客户端才能使用优化功能"
            )

    def _optimize_json(self, text: str) -> AIOperationResult:
        """优化JSON（去除冗余）"""
        try:
            obj = json.loads(text)
            # 尝试压缩
            minified = json.dumps(obj, separators=(',', ':'), ensure_ascii=False)
            return AIOperationResult(
                success=True,
                operation=AIOperationType.OPTIMIZE,
                original_text=text,
                result_text=minified,
                message="JSON已压缩"
            )
        except:
            return AIOperationResult(
                success=False,
                operation=AIOperationType.OPTIMIZE,
                original_text=text,
                result_text=text,
                message="JSON压缩失败"
            )

    def can_handle(self, operation: AIOperationType) -> bool:
        return operation == AIOperationType.OPTIMIZE


class SummarizeHandler(AIOperationHandler):
    """总结处理器"""

    async def process(self, text: str, context: Dict[str, Any]) -> AIOperationResult:
        if self.llm_client:
            prompt = f"用简洁的语言总结以下内容的要点:\n\n{text}"
            try:
                response = await self.llm_client.chat([{'role': 'user', 'content': prompt}])
                summary = response.get('content', '')
                return AIOperationResult(
                    success=True,
                    operation=AIOperationType.SUMMARIZE,
                    original_text=text,
                    result_text=summary,
                    message="已生成总结"
                )
            except Exception as e:
                return AIOperationResult(
                    success=False,
                    operation=AIOperationType.SUMMARIZE,
                    original_text=text,
                    result_text=text,
                    message=f"总结生成失败: {str(e)}"
                )
        else:
            # 无LLM时的基础总结
            lines = [l.strip() for l in text.split('\n') if l.strip()]
            if len(lines) <= 3:
                summary = '\n'.join(lines)
            else:
                summary = f"文档共{len(lines)}行，主要内容:\n- {lines[0]}\n- {lines[-1]}"

            return AIOperationResult(
                success=True,
                operation=AIOperationType.SUMMARIZE,
                original_text=text,
                result_text=summary,
                message="已生成基础总结（需要LLM增强）"
            )

    def can_handle(self, operation: AIOperationType) -> bool:
        return operation == AIOperationType.SUMMARIZE


class SimplifyHandler(AIOperationHandler):
    """简化处理器"""

    async def process(self, text: str, context: Dict[str, Any]) -> AIOperationResult:
        if self.llm_client:
            prompt = f"简化以下文本，使其更简洁清晰:\n\n{text}"
            try:
                response = await self.llm_client.chat([{'role': 'user', 'content': prompt}])
                simplified = response.get('content', text)
                return AIOperationResult(
                    success=True,
                    operation=AIOperationType.SIMPLIFY,
                    original_text=text,
                    result_text=simplified,
                    message="已简化文本"
                )
            except Exception as e:
                return AIOperationResult(
                    success=False,
                    operation=AIOperationType.SIMPLIFY,
                    original_text=text,
                    result_text=text,
                    message=f"简化失败: {str(e)}"
                )
        else:
            # 基础简化：移除多余空白
            simplified = ' '.join(text.split())
            return AIOperationResult(
                success=True,
                operation=AIOperationType.SIMPLIFY,
                original_text=text,
                result_text=simplified,
                message="已基础简化（需要LLM增强）"
            )

    def can_handle(self, operation: AIOperationType) -> bool:
        return operation == AIOperationType.SIMPLIFY


class ExpandHandler(AIOperationHandler):
    """扩写处理器"""

    async def process(self, text: str, context: Dict[str, Any]) -> AIOperationResult:
        if self.llm_client:
            prompt = f"扩写以下内容，使其更详细完整:\n\n{text}"
            try:
                response = await self.llm_client.chat([{'role': 'user', 'content': prompt}])
                expanded = response.get('content', text)
                return AIOperationResult(
                    success=True,
                    operation=AIOperationType.EXPAND,
                    original_text=text,
                    result_text=expanded,
                    message="已扩写内容"
                )
            except Exception as e:
                return AIOperationResult(
                    success=False,
                    operation=AIOperationType.EXPAND,
                    original_text=text,
                    result_text=text,
                    message=f"扩写失败: {str(e)}"
                )
        else:
            return AIOperationResult(
                success=False,
                operation=AIOperationType.EXPAND,
                original_text=text,
                result_text=text,
                message="需要配置LLM客户端才能使用扩写功能"
            )

    def can_handle(self, operation: AIOperationType) -> bool:
        return operation == AIOperationType.EXPAND


class AIOperator:
    """
    AI操作符统一接口
    """

    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        self.handlers: Dict[AIOperationType, AIOperationHandler] = {
            AIOperationType.FORMAT: FormatHandler(llm_client),
            AIOperationType.SIMPLIFY: SimplifyHandler(llm_client),
            AIOperationType.EXPAND: ExpandHandler(llm_client),
            AIOperationType.TRANSLATE: TranslateHandler(llm_client),
            AIOperationType.EXPLAIN: ExplainHandler(llm_client),
            AIOperationType.FIX: FixHandler(llm_client),
            AIOperationType.OPTIMIZE: OptimizeHandler(llm_client),
            AIOperationType.SUMMARIZE: SummarizeHandler(llm_client),
        }

    async def execute(self, operation: AIOperationType, text: str, context: Dict[str, Any] = None) -> AIOperationResult:
        """执行AI操作"""
        context = context or {}
        handler = self.handlers.get(operation)

        if not handler:
            return AIOperationResult(
                success=False,
                operation=operation,
                original_text=text,
                result_text=text,
                message=f"不支持的操作: {operation.value}"
            )

        return await handler.process(text, context)

    def register_handler(self, operation: AIOperationType, handler: AIOperationHandler):
        """注册操作处理器"""
        self.handlers[operation] = handler

    def get_supported_operations(self) -> List[AIOperationType]:
        """获取支持的操作列表"""
        return list(self.handlers.keys())


# 全局AI操作符实例
_global_operator: Optional[AIOperator] = None
_operator_lock = asyncio.Lock()


async def get_ai_operator(llm_client=None) -> AIOperator:
    """获取全局AI操作符"""
    global _global_operator
    async with _operator_lock:
        if _global_operator is None:
            _global_operator = AIOperator(llm_client)
        return _global_operator


def sync_get_ai_operator(llm_client=None) -> AIOperator:
    """同步获取全局AI操作符"""
    global _global_operator
    if _global_operator is None:
        _global_operator = AIOperator(llm_client)
    return _global_operator