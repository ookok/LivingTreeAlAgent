# -*- coding: utf-8 -*-
"""
代码动作处理器 - CodeGenerationHandler, CodeReviewHandler, CodeDebugHandler
========================================================================

处理所有代码相关意图的执行：
- 代码生成 (CODE_GENERATION, CODE_IMPLEMENTATION, API_DESIGN, DATABASE_DESIGN, UI_GENERATION)
- 代码审查 (CODE_REVIEW, CODE_VERIFICATION, SECURITY_CHECK, PERFORMANCE_ANALYSIS)
- 代码调试 (DEBUGGING, BUG_FIX, ERROR_RESOLUTION, ISSUE_ANALYSIS)
- 代码修改 (CODE_MODIFICATION, CODE_REFACTOR, CODE_OPTIMIZATION, CODE_MIGRATION)
- 测试生成 (TEST_GENERATION)
- 部署配置 (DEPLOYMENT, CONFIGURATION, ENVIRONMENT_SETUP)
- 文档生成 (DOCUMENTATION)

v2.0: 所有 Handler 共享 LLMClient（自动回退 requests→urllib），带重试和错误分类
from __future__ import annotations
"""


import re
import time
import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..intent_types import IntentType

from ..intent_types import IntentType
from .base import (
    BaseActionHandler,
    ActionContext,
    ActionResult,
    ActionResultStatus,
    LLMClient,
    LLMError,
    get_llm_client,
)

logger = logging.getLogger(__name__)


# ── 公共 LLM 调用方法 ──────────────────────────────────────────────────


def call_llm(ctx: ActionContext, prompt: str, system: str = "") -> str:
    """
    统一 LLM 调用入口

    - 自动使用共享 LLMClient
    - 超时重试 + 错误分类
    - 返回纯文本内容

    Raises:
        RuntimeError: LLM 调用失败（含错误分类信息）
    """
    client = get_llm_client(
        default_url=ctx.ollama_url,
        default_model=ctx.model_name,
        default_timeout=ctx.timeout,
    )
    try:
        result = client.chat(
            prompt=prompt,
            model=ctx.model_name,
            temperature=ctx.temperature,
            timeout=ctx.timeout,
            system_prompt=system,
            stream=ctx.stream,
        )
        content = result.get("content", "")
        if not content.strip():
            raise RuntimeError("LLM 返回空内容")
        return content
    except LLMError as e:
        raise RuntimeError(f"[{e.error_type}] {e}")


# ── 代码生成处理器 ─────────────────────────────────────────────────────


class CodeGenerationHandler(BaseActionHandler):
    """
    代码生成处理器

    覆盖意图：
    - CODE_GENERATION / CODE_IMPLEMENTATION / API_DESIGN / DATABASE_DESIGN / UI_GENERATION
    - CODE_MODIFICATION / CODE_REFACTOR / CODE_OPTIMIZATION / CODE_MIGRATION
    - TEST_GENERATION
    - DOCUMENTATION
    - DEPLOYMENT / CONFIGURATION / ENVIRONMENT_SETUP
    - FILE_OPERATION / FOLDER_STRUCTURE

    执行流程：
    1. 构建代码生成提示（含技术栈、约束）
    2. 调用 LLM 生成代码（自动重试+回退）
    3. 后处理（格式化、提取代码块）
    """

    @property
    def name(self) -> str:
        return "code_generation"

    @property
    def supported_intents(self) -> List[IntentType]:
        return [
            IntentType.CODE_GENERATION,
            IntentType.CODE_IMPLEMENTATION,
            IntentType.API_DESIGN,
            IntentType.DATABASE_DESIGN,
            IntentType.UI_GENERATION,
            IntentType.CODE_MODIFICATION,
            IntentType.CODE_REFACTOR,
            IntentType.CODE_OPTIMIZATION,
            IntentType.CODE_MIGRATION,
            IntentType.TEST_GENERATION,
            IntentType.DOCUMENTATION,
            IntentType.DEPLOYMENT,
            IntentType.CONFIGURATION,
            IntentType.ENVIRONMENT_SETUP,
            IntentType.FILE_OPERATION,
            IntentType.FOLDER_STRUCTURE,
        ]

    @property
    def priority(self) -> int:
        return 10  # 高优先级

    def handle(self, ctx: ActionContext) -> ActionResult:
        """执行代码生成"""
        start = time.time()
        intent = ctx.intent

        # 构建提示
        prompt = self._build_prompt(ctx)
        system = "你是一个高级编程助手。请直接输出代码，使用 Markdown 代码块格式。"

        # 调用 LLM
        try:
            output = call_llm(ctx, prompt, system=system)
        except RuntimeError as e:
            return self._make_error(f"LLM 调用失败: {e}")

        # 后处理
        code_blocks = self._extract_code_blocks(output)

        execution_time = time.time() - start

        result = self._make_result(
            output=output,
            output_type="code",
            suggestions=self._generate_suggestions(intent),
            artifacts=code_blocks if code_blocks else [],
        )
        result.steps = [
            {"name": "构建提示", "detail": f"意图: {intent.intent_type.value}" , "duration": 0.01},
            {"name": "LLM 生成", "detail": f"模型: {ctx.model_name}", "duration": execution_time * 0.9},
            {"name": "后处理", "detail": f"提取 {len(code_blocks)} 个代码块", "duration": execution_time * 0.1},
        ]
        result.execution_time = execution_time

        return result

    def _build_prompt(self, ctx: ActionContext) -> str:
        """构建代码生成提示"""
        intent = ctx.intent
        parts = []

        # 任务描述
        parts.append(f"## 任务\n{intent.raw_input}")

        # 意图类型
        parts.append(f"## 意图类型\n{intent.intent_type.value}")

        # 技术栈
        if intent.tech_stack:
            parts.append(f"## 技术栈\n{', '.join(intent.tech_stack)}")

        # 约束条件
        if intent.constraints:
            parts.append("## 约束条件")
            for c in intent.constraints:
                req = "[必须]" if c.required else "[建议]"
                parts.append(f"- {req} {c.name}: {c.value}")

        # 质量要求
        parts.append("""## 质量要求
1. 代码清晰、有注释
2. 遵循最佳实践
3. 包含必要的错误处理
4. 考虑边界情况

请直接输出代码，使用 Markdown 代码块格式。如果涉及多个文件，分别用代码块标注文件路径。""")

        return "\n\n".join(parts)

    def _extract_code_blocks(self, text: str) -> List[str]:
        """提取 Markdown 代码块，返回带内容和文件名的列表"""
        pattern = r'```(\w*)\n(.*?)```'
        matches = re.findall(pattern, text, re.DOTALL)
        blocks = []
        for i, (lang, code) in enumerate(matches):
            # 尝试检测文件路径注释
            first_line = code.split('\n')[0] if code else ""
            if first_line.startswith("# ") or first_line.startswith("// "):
                fname = first_line.lstrip("# ").lstrip("// ").strip()
                blocks.append(f"{fname}.{lang or 'txt'}")
            else:
                blocks.append(f"block_{i+1}.{lang or 'txt'}")
        return blocks

    def _generate_suggestions(self, intent) -> List[str]:
        """生成后续建议"""
        suggestions = ["可以尝试运行生成的代码"]
        if IntentType.CODE_GENERATION in (intent.intent_type,):
            suggestions.append("建议编写对应的单元测试")
        if intent.tech_stack:
            suggestions.append(f"考虑使用 {intent.tech_stack[0]} 的最新版本")
        return suggestions


# ── 代码审查处理器 ─────────────────────────────────────────────────────


class CodeReviewHandler(BaseActionHandler):
    """
    代码审查处理器

    覆盖意图：
    - CODE_REVIEW / CODE_VERIFICATION / SECURITY_CHECK / PERFORMANCE_ANALYSIS
    - CODE_UNDERSTANDING / CODE_EXPLANATION
    - BEST_PRACTICE
    """

    @property
    def name(self) -> str:
        return "code_review"

    @property
    def supported_intents(self) -> List[IntentType]:
        return [
            IntentType.CODE_REVIEW,
            IntentType.CODE_VERIFICATION,
            IntentType.SECURITY_CHECK,
            IntentType.PERFORMANCE_ANALYSIS,
            IntentType.CODE_UNDERSTANDING,
            IntentType.CODE_EXPLANATION,
            IntentType.BEST_PRACTICE,
        ]

    @property
    def priority(self) -> int:
        return 20

    def handle(self, ctx: ActionContext) -> ActionResult:
        """执行代码审查"""
        start = time.time()
        intent = ctx.intent

        prompt = self._build_review_prompt(ctx)
        system = "你是一个资深代码审查专家。请用中文回答，结构清晰。"

        try:
            output = call_llm(ctx, prompt, system=system)
        except RuntimeError as e:
            return self._make_error(f"代码审查失败: {e}")

        execution_time = time.time() - start

        result = self._make_result(
            output=output,
            output_type="text",
            suggestions=[
                "根据建议优化代码",
                "运行相关测试验证",
                "检查是否有安全漏洞",
            ],
        )
        result.steps = [
            {"name": "代码审查", "detail": f"意图: {intent.intent_type.value}", "duration": execution_time},
        ]
        result.execution_time = execution_time

        return result

    def _build_review_prompt(self, ctx: ActionContext) -> str:
        """构建代码审查提示"""
        intent = ctx.intent

        if intent.intent_type in (
            IntentType.CODE_UNDERSTANDING,
            IntentType.CODE_EXPLANATION,
        ):
            return f"""## 代码解释

用户请求: {intent.raw_input}

请详细解释以下代码：
- 整体功能
- 关键逻辑
- 数据流
- 注意事项

使用中文回答，结构清晰。"""

        return f"""## 代码审查

用户请求: {intent.raw_input}
审查类型: {intent.intent_type.value}
技术栈: {', '.join(intent.tech_stack) if intent.tech_stack else '自动检测'}

请进行全面的代码审查：
1. **代码质量** - 命名、结构、可读性
2. **潜在问题** - Bug、边界情况、异常处理
3. **性能分析** - 时间/空间复杂度、潜在瓶颈
4. **安全检查** - 注入、XSS、认证等
5. **最佳实践** - 是否遵循语言/框架规范
6. **改进建议** - 具体的优化方向

请用表格格式列出发现的问题，按严重程度排序。"""


# ── 代码调试处理器 ─────────────────────────────────────────────────────


class CodeDebugHandler(BaseActionHandler):
    """
    代码调试处理器

    覆盖意图：
    - DEBUGGING / BUG_FIX / ERROR_RESOLUTION / ISSUE_ANALYSIS
    """

    @property
    def name(self) -> str:
        return "code_debug"

    @property
    def supported_intents(self) -> List[IntentType]:
        return [
            IntentType.DEBUGGING,
            IntentType.BUG_FIX,
            IntentType.ERROR_RESOLUTION,
            IntentType.ISSUE_ANALYSIS,
        ]

    @property
    def priority(self) -> int:
        return 5  # 最高优先级（Bug 修复最紧急）

    def handle(self, ctx: ActionContext) -> ActionResult:
        """执行代码调试"""
        start = time.time()
        intent = ctx.intent

        prompt = self._build_debug_prompt(ctx)
        system = "你是一个高级调试专家。请按步骤分析问题，给出具体的修复代码。"

        try:
            output = call_llm(ctx, prompt, system=system)
        except RuntimeError as e:
            return self._make_error(f"调试分析失败: {e}")

        execution_time = time.time() - start

        result = self._make_result(
            output=output,
            output_type="text",
            suggestions=[
                "根据分析修复代码",
                "添加相应的单元测试防止回归",
                "检查是否还有类似问题",
            ],
        )
        result.steps = [
            {"name": "问题分析", "detail": f"意图: {intent.intent_type.value}", "duration": execution_time},
        ]
        result.execution_time = execution_time

        return result

    def _build_debug_prompt(self, ctx: ActionContext) -> str:
        """构建调试分析提示"""
        intent = ctx.intent

        return f"""## 问题调试

用户描述: {intent.raw_input}
问题类型: {intent.intent_type.value}
技术栈: {', '.join(intent.tech_stack) if intent.tech_stack else '自动检测'}

请按以下步骤分析：

### 1. 问题定位
- 错误信息的含义
- 可能的原因
- 关键代码位置

### 2. 根因分析
- 直接原因
- 深层原因
- 是否是常见问题

### 3. 修复方案
- 推荐修复方式
- 修复后的代码
- 验证方法

### 4. 预防措施
- 如何避免类似问题
- 需要添加的测试

请使用中文回答，提供具体的代码示例。"""
