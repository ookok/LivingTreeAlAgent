"""
提示词生成器
Prompt Generator - 模板实例化、智能优化
"""

import re
import json
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
import threading

from .models import (
    MessagePattern, TemplateConfig, VariableDefinition,
    ThinkingConfig, ThinkingStyle, ThinkingDepth,
    OutputConfig, OutputFormat, ContextConfig
)
from .variable_resolver import VariableResolver, ResolverContext
from .pattern_matcher import MatchResult, IntentResult


@dataclass
class GeneratedPrompt:
    """生成的提示词"""
    content: str                              # 提示词内容
    system_prompt: str = ""                   # 系统提示词
    user_prompt: str = ""                     # 用户提示词
    variables: Dict[str, Any] = field(default_factory=dict)  # 使用的变量
    context: Dict[str, Any] = field(default_factory=dict)     # 上下文信息
    metadata: Dict[str, Any] = field(default_factory=dict)     # 元数据
    warnings: List[str] = field(default_factory=list)         # 警告信息
    confidence: float = 0.0                    # 生成置信度

    def to_dict(self) -> Dict:
        return {
            "content": self.content,
            "system_prompt": self.system_prompt,
            "user_prompt": self.user_prompt,
            "variables": self.variables,
            "context": self.context,
            "metadata": self.metadata,
            "warnings": self.warnings,
            "confidence": self.confidence
        }


@dataclass
class GenerationOptions:
    """生成选项"""
    include_system_prompt: bool = True        # 包含系统提示词
    include_reasoning: bool = True            # 包含推理过程
    include_examples: bool = False            # 包含示例
    max_length: int = 4000                    # 最大长度
    style: str = "default"                    # 输出风格
    format: OutputFormat = OutputFormat.MARKDOWN  # 输出格式


class PromptGenerator:
    """提示词生成器"""

    # 思考阶段模板
    THINKING_STAGES = {
        ThinkingStyle.STRUCTURED: [
            {"name": "问题理解", "description": "理解核心问题", "steps": ["识别关键问题", "分析问题背景", "明确解决目标"]},
            {"name": "信息分析", "description": "分析相关信息", "steps": ["收集相关信息", "验证信息准确性", "识别信息关联"]},
            {"name": "方案构思", "description": "构思解决方案", "steps": ["生成初步想法", "评估可行性", "优化方案设计"]},
            {"name": "评估决策", "description": "评估并决策", "steps": ["评估方案优缺点", "比较备选方案", "做出最终选择"]},
            {"name": "行动计划", "description": "制定行动计划", "steps": ["分解实施步骤", "分配资源责任", "制定时间计划"]}
        ],
        ThinkingStyle.STEP_BY_STEP: [
            {"name": "第一步", "description": "初步分析", "steps": ["理解输入", "识别关键点"]},
            {"name": "第二步", "description": "深入分析", "steps": ["详细分析", "找出关联"]},
            {"name": "第三步", "description": "方案形成", "steps": ["形成方案", "验证方案"]},
            {"name": "第四步", "description": "结论输出", "steps": ["总结结论", "提供建议"]}
        ],
        ThinkingStyle.BRAINSTORM: [
            {"name": "发散思考", "description": "自由联想", "steps": ["列出所有想法", "不评判质量"]},
            {"name": "关联探索", "description": "寻找关联", "steps": ["建立连接", "组合想法"]},
            {"name": "收敛聚焦", "description": "筛选优化", "steps": ["评估价值", "优化完善"]}
        ],
        ThinkingStyle.FREE: [
            {"name": "思考", "description": "自由思考", "steps": ["自然思考过程"]}
        ]
    }

    # 深度配置
    DEPTH_CONFIG = {
        ThinkingDepth.SHALLOW: {"max_stages": 2, "steps_per_stage": 2},
        ThinkingDepth.MEDIUM: {"max_stages": 4, "steps_per_stage": 3},
        ThinkingDepth.DEEP: {"max_stages": 6, "steps_per_stage": 5}
    }

    def __init__(self, resolver: VariableResolver = None):
        self._resolver = resolver or VariableResolver()
        self._custom_templates: Dict[str, str] = {}
        self._custom_thinking_prompts: Dict[str, str] = {}
        self._optimization_callbacks: List[Callable] = []
        self._lock = threading.Lock()

    def register_template(self, name: str, template: str):
        """注册自定义模板"""
        self._custom_templates[name] = template

    def register_thinking_prompt(self, style: str, prompt: str):
        """注册自定义思考提示"""
        self._custom_thinking_prompts[style] = prompt

    def register_optimization_callback(self, callback: Callable):
        """注册优化回调"""
        if callback not in self._optimization_callbacks:
            self._optimization_callbacks.append(callback)

    def generate(
        self,
        pattern: MessagePattern,
        context: ResolverContext,
        options: GenerationOptions = None
    ) -> GeneratedPrompt:
        """生成提示词"""
        if options is None:
            options = GenerationOptions()

        prompt = GeneratedPrompt(content="")
        prompt.variables = {}
        prompt.warnings = []

        # 1. 解析模板变量
        try:
            resolved_content = self._resolver.resolve(
                pattern.template.content,
                pattern.template.variables,
                context
            )
            prompt.variables = self._resolver.resolve_all(
                pattern.template.variables,
                context
            )
        except Exception as e:
            prompt.warnings.append(f"变量解析警告: {str(e)}")
            resolved_content = pattern.template.content

        # 2. 构建系统提示词
        if options.include_system_prompt:
            prompt.system_prompt = self._build_system_prompt(pattern, options)

        # 3. 构建用户提示词
        prompt.user_prompt = resolved_content

        # 4. 添加思考过程
        if options.include_reasoning and pattern.enhancement.thinking.enabled:
            thinking_prompt = self._build_thinking_prompt(pattern, options)
            if thinking_prompt:
                prompt.user_prompt += "\n\n" + thinking_prompt

        # 5. 添加输出格式要求
        output_format = self._build_output_format(pattern, options)
        prompt.user_prompt += "\n\n" + output_format

        # 6. 组合最终内容
        prompt.content = prompt.user_prompt
        if prompt.system_prompt:
            prompt.content = prompt.system_prompt + "\n\n" + prompt.user_prompt

        # 7. 截断处理
        if len(prompt.content) > options.max_length:
            prompt.warnings.append(f"内容过长，已截断至 {options.max_length} 字符")
            prompt.content = prompt.content[:options.max_length]

        # 8. 记录元数据
        prompt.metadata = {
            "pattern_id": pattern.id,
            "pattern_name": pattern.name,
            "generated_at": datetime.now().isoformat(),
            "template_type": pattern.template.template_type.value,
            "thinking_enabled": pattern.enhancement.thinking.enabled,
            "output_format": pattern.output.format.value
        }

        # 9. 计算置信度
        prompt.confidence = self._calculate_confidence(pattern, context)

        return prompt

    def generate_quick(
        self,
        template_content: str,
        variables: Dict[str, Any],
        context: ResolverContext = None
    ) -> str:
        """快速生成（简化版本）"""
        if context is None:
            context = ResolverContext()

        # 简单变量替换
        result = template_content
        for var_name, var_value in variables.items():
            placeholder = f"{{{var_name}}}"
            if placeholder in result:
                result = result.replace(placeholder, str(var_value))

        return result

    def _build_system_prompt(
        self,
        pattern: MessagePattern,
        options: GenerationOptions
    ) -> str:
        """构建系统提示词"""
        parts = []

        # 基本角色设定
        parts.append(f"你是一个{self._get_role_description(pattern)}。")

        # 风格要求
        if pattern.enhancement.thinking.style == ThinkingStyle.STRUCTURED:
            parts.append("请以结构化、逻辑清晰的方式回答。")
        elif pattern.enhancement.thinking.style == ThinkingStyle.FREE:
            parts.append("请以自由、灵活的方式回答。")

        # 质量要求
        parts.append("请确保回答准确、完整、有帮助。")

        return "\n".join(parts)

    def _get_role_description(self, pattern: MessagePattern) -> str:
        """获取角色描述"""
        category = pattern.category.value if hasattr(pattern.category, 'value') else str(pattern.category)

        role_map = {
            "analysis": "专业分析师",
            "writing": "专业写作助手",
            "coding": "资深程序员",
            "learning": "知识讲解专家",
            "brainstorm": "创意顾问",
            "decision": "决策顾问",
            "planning": "规划专家",
            "research": "研究员",
            "creative": "创意专家",
            "professional": "专业人士",
            "general": "AI助手"
        }

        return role_map.get(category, "专业助手")

    def _build_thinking_prompt(
        self,
        pattern: MessagePattern,
        options: GenerationOptions
    ) -> str:
        """构建思考过程提示"""
        thinking = pattern.enhancement.thinking
        if not thinking.enabled:
            return ""

        style_key = thinking.style.value if hasattr(thinking.style, 'value') else str(thinking.style)
        depth_key = thinking.depth.value if hasattr(thinking.depth, 'value') else str(thinking.depth)

        # 获取阶段模板
        stages = self.THINKING_STAGES.get(thinking.style, self.THINKING_STAGES[ThinkingStyle.STRUCTURED])

        # 根据深度限制
        depth_cfg = self.DEPTH_CONFIG.get(thinking.depth, self.DEPTH_CONFIG[ThinkingDepth.MEDIUM])
        max_stages = min(len(stages), depth_cfg["max_stages"])
        stages = stages[:max_stages]

        # 构建思考过程
        thinking_parts = ["## 思考过程\n"]

        if thinking.show_steps:
            for stage in stages:
                thinking_parts.append(f"### {stage['name']}: {stage['description']}")
                steps = stage.get("steps", [])[:depth_cfg["steps_per_stage"]]
                for step in steps:
                    thinking_parts.append(f"- {step}")
                thinking_parts.append("")

        if thinking.show_assumptions:
            thinking_parts.append("### 假设条件\n")
            thinking_parts.append("- [列出你的关键假设]\n")

        if thinking.show_alternatives:
            thinking_parts.append("### 备选方案\n")
            thinking_parts.append("- [如有，简要说明备选方案]\n")

        return "\n".join(thinking_parts)

    def _build_output_format(
        self,
        pattern: MessagePattern,
        options: GenerationOptions
    ) -> str:
        """构建输出格式要求"""
        output = pattern.output
        parts = ["## 输出要求\n"]

        # 格式要求
        format_str = output.format.value if hasattr(output.format, 'value') else str(output.format)
        if format_str == "markdown":
            parts.append("- 使用Markdown格式输出")
        elif format_str == "plain":
            parts.append("- 使用纯文本格式输出")
        elif format_str == "json":
            parts.append("- 使用JSON格式输出")

        # 长度限制
        if output.length_limit > 0:
            parts.append(f"- 控制在{output.length_limit}字以内")

        # 置信度展示
        if output.show_confidence:
            parts.append("- 标注答案的置信度")

        # 推理过程展示
        if output.show_reasoning and pattern.enhancement.thinking.enabled:
            parts.append("- 展示完整的推理过程")

        return "\n".join(parts)

    def _calculate_confidence(
        self,
        pattern: MessagePattern,
        context: ResolverContext
    ) -> float:
        """计算生成置信度"""
        confidence = 0.5  # 基础置信度

        # 变量完整度加分
        total_required = sum(1 for v in pattern.template.variables.values() if v.required)
        if total_required > 0:
            # 检查模板中使用的变量是否都有值
            resolved_count = sum(
                1 for v in pattern.template.variables.values()
                if v.required and v.name in pattern.template.content
            )
            completeness = resolved_count / total_required
            confidence += completeness * 0.3

        # 历史成功率加分
        if pattern.metadata.usage_count > 0:
            confidence += pattern.metadata.success_rate * 0.2

        return min(confidence, 1.0)

    def optimize_prompt(
        self,
        prompt: GeneratedPrompt,
        feedback: str = None,
        target_metrics: Dict[str, float] = None
    ) -> GeneratedPrompt:
        """优化提示词"""
        optimized = GeneratedPrompt(content=prompt.content)
        optimized.system_prompt = prompt.system_prompt
        optimized.user_prompt = prompt.user_prompt
        optimized.variables = prompt.variables.copy()
        optimized.context = prompt.context.copy()
        optimized.metadata = prompt.metadata.copy()
        optimized.warnings = prompt.warnings.copy()
        optimized.confidence = prompt.confidence

        # 调用所有优化回调
        for callback in self._optimization_callbacks:
            try:
                optimized = callback(optimized, feedback, target_metrics)
            except Exception as e:
                optimized.warnings.append(f"优化回调错误: {str(e)}")

        # 基本优化
        if feedback:
            optimized = self._apply_feedback(optimized, feedback)

        return optimized

    def _apply_feedback(
        self,
        prompt: GeneratedPrompt,
        feedback: str
    ) -> GeneratedPrompt:
        """应用反馈优化"""
        # 简单的反馈处理
        feedback_lower = feedback.lower()

        if "太短" in feedback or "详细" in feedback:
            prompt.warnings.append("建议: 用户反馈内容可以更详细")

        if "太长" in feedback or "简洁" in feedback:
            prompt.warnings.append("建议: 内容可以更简洁")

        if "不清楚" in feedback or "模糊" in feedback:
            prompt.warnings.append("建议: 表达可以更清晰")

        return prompt

    def batch_generate(
        self,
        patterns: List[MessagePattern],
        context: ResolverContext,
        options: GenerationOptions = None
    ) -> List[GeneratedPrompt]:
        """批量生成"""
        return [
            self.generate(pattern, context, options)
            for pattern in patterns
        ]

    def preview(
        self,
        pattern: MessagePattern,
        sample_variables: Dict[str, Any] = None,
        context: ResolverContext = None
    ) -> GeneratedPrompt:
        """预览模式效果"""
        if context is None:
            context = ResolverContext()

        # 使用示例变量填充
        if sample_variables:
            for var_name, var_def in pattern.template.variables.items():
                if var_name not in context.custom_data:
                    context.custom_data[var_name] = sample_variables.get(var_name, var_def.default)

        return self.generate(pattern, context)


# ============ 提示词优化器 ============

class PromptOptimizer:
    """提示词优化器"""

    def __init__(self, generator: PromptGenerator):
        self._generator = generator
        self._optimization_rules: List[Callable] = []
        self._init_default_rules()

    def _init_default_rules(self):
        """初始化默认优化规则"""
        self._optimization_rules = [
            self._remove_redundancy,
            self._improve_clarity,
            self._balance_length,
            self._enhance_structure
        ]

    def optimize(
        self,
        prompt: GeneratedPrompt,
        rules: List[str] = None
    ) -> GeneratedPrompt:
        """应用优化规则"""
        optimized = GeneratedPrompt(content=prompt.content)
        optimized.system_prompt = prompt.system_prompt
        optimized.user_prompt = prompt.user_prompt
        optimized.variables = prompt.variables.copy()
        optimized.context = prompt.context.copy()
        optimized.metadata = prompt.metadata.copy()
        optimized.warnings = prompt.warnings.copy()
        optimized.confidence = prompt.confidence

        target_rules = rules or [r.__name__ for r in self._optimization_rules]

        for rule in self._optimization_rules:
            if rule.__name__ in target_rules:
                try:
                    optimized = rule(optimized)
                except Exception:
                    pass

        return optimized

    def _remove_redundancy(self, prompt: GeneratedPrompt) -> GeneratedPrompt:
        """移除冗余"""
        content = prompt.content

        # 移除多余空行
        content = re.sub(r'\n{3,}', '\n\n', content)

        # 移除重复的词
        words = content.split()
        seen = set()
        unique_words = []
        for word in words:
            if word not in seen or len(word) < 3:
                unique_words.append(word)
                seen.add(word)
        content = ' '.join(unique_words)

        prompt.content = content
        return prompt

    def _improve_clarity(self, prompt: GeneratedPrompt) -> GeneratedPrompt:
        """提高清晰度"""
        content = prompt.content

        # 确保指令明确
        if not any(ind in content for ind in ['请', '请帮', '请按照']):
            content = '请回答: ' + content

        prompt.content = content
        return prompt

    def _balance_length(self, prompt: GeneratedPrompt) -> GeneratedPrompt:
        """平衡长度"""
        content = prompt.content
        words = len(content.split())

        if words < 20:
            prompt.warnings.append("内容可能过短，建议添加更多细节")
        elif words > 2000:
            prompt.warnings.append("内容可能过长，建议精简")

        return prompt

    def _enhance_structure(self, prompt: GeneratedPrompt) -> GeneratedPrompt:
        """增强结构"""
        content = prompt.content

        # 确保有基本结构
        if '##' not in content:
            # 添加基本标题
            lines = content.split('\n')
            if len(lines) > 3:
                content = '## 任务\n' + '\n'.join(lines[:3]) + '\n\n## 详细要求\n' + '\n'.join(lines[3:])

        prompt.content = content
        return prompt


# 全局实例
_generator_instance = None


def get_prompt_generator(resolver: VariableResolver = None) -> PromptGenerator:
    """获取提示词生成器实例"""
    global _generator_instance
    if _generator_instance is None:
        _generator_instance = PromptGenerator(resolver)
    return _generator_instance
