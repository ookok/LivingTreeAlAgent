"""
Agent Prompt 构建器
将 Karpathy Skills 准则注入到 Agent 的系统提示中
"""

import os
from pathlib import Path
from typing import Optional
from .rules import KARPATHY_RULES_TEXT


class AgentType:
    """Agent 类型枚举"""
    CODE_ARCHITECT = "code_architect"
    DEBUG_SPECIALIST = "debug_specialist"
    CODE_GENERATOR = "code_generator"
    REFACTOR_AGENT = "refactor_agent"
    REVIEW_AGENT = "review_agent"
    GENERAL = "general"


# Agent 基础提示模板
AGENT_BASE_PROMPTS = {
    AgentType.CODE_ARCHITECT: """你是一个代码架构师。
专注于系统架构、模式设计、可扩展性分析。
使用工具：code_analysis, mermaid_gen, doc_generator。
永远不写无注释的代码。
设计时考虑最小化依赖和复杂度。""",

    AgentType.DEBUG_SPECIALIST: """你是一个 bug 猎人。
分析日志、运行测试、追踪根本原因。
优先使用工具：query_logs, run_test, explain_error。
在诊断过程中主动识别潜在风险。""",

    AgentType.CODE_GENERATOR: """你是一个代码生成专家。
根据需求生成高质量、简洁的代码。
优先实现正确性，其次是性能。
生成代码后进行自检：是否存在过度设计？""",

    AgentType.REFACTOR_AGENT: """你是一个代码重构专家。
改进现有代码的质量和可维护性。
遵循最小变更原则：只改必要的部分。
重构前先验证当前行为，重构后确保行为一致。""",

    AgentType.REVIEW_AGENT: """你是一个代码审查专家。
审查代码质量、安全性、性能。
指出问题时给出具体的改进建议。
关注边界情况和错误处理。""",

    AgentType.GENERAL: """你是一个通用的 AI 编程助手。
尽力理解用户需求，提供最佳解决方案。
遇到模糊问题时主动询问澄清。""",
}


class AgentPromptBuilder:
    """Agent Prompt 构建器"""

    def __init__(self):
        self._cache: dict[str, str] = {}
        self._rules_template = KARPATHY_RULES_TEXT

    def build(
        self,
        agent_type: str,
        custom_base: Optional[str] = None,
        include_karpathy: bool = True,
        extra_context: Optional[str] = None,
    ) -> str:
        """
        构建完整的 Agent System Prompt

        Args:
            agent_type: Agent 类型
            custom_base: 自定义基础提示（覆盖默认）
            include_karpathy: 是否注入 Karpathy 准则
            extra_context: 额外上下文（如项目信息）

        Returns:
            完整的 System Prompt
        """
        cache_key = f"{agent_type}:{include_karpathy}:{hash(extra_context or '')}"

        if cache_key in self._cache:
            return self._cache[cache_key]

        # 1. 基础提示
        if custom_base:
            base_prompt = custom_base
        else:
            base_prompt = AGENT_BASE_PROMPTS.get(agent_type, AGENT_BASE_PROMPTS[AgentType.GENERAL])

        # 2. 注入 Karpathy 准则
        if include_karpathy:
            karpathy_section = f"\n\n{KARPATHY_RULES_TEXT}\n"
        else:
            karpathy_section = ""

        # 3. 额外上下文
        context_section = f"\n\n## 当前上下文\n{extra_context}\n" if extra_context else ""

        # 4. 交互约束
        interaction_rules = """
## 交互约束
- 当检测到需求歧义时，必须先列出可能解读，等待用户确认后再执行
- 复杂任务先输出≤3步计划，列明成功标准
- 代码生成后进行自检（过度设计/最小变更）
- 关键决策点展示权衡供用户选择
"""

        # 组装完整提示
        full_prompt = f"""# System Prompt

{base_prompt}
{karpathy_section}
{context_section}
{interaction_rules}
"""

        self._cache[cache_key] = full_prompt
        return full_prompt

    def build_for_llm(self, llm_backend: str = "ollama") -> str:
        """
        构建 LLM 专用的系统提示（用于 Ollama/Claude 等）

        Args:
            llm_backend: LLM 后端类型

        Returns:
            System Prompt
        """
        if llm_backend == "ollama":
            base = AGENT_BASE_PROMPTS[AgentType.CODE_GENERATOR]
        else:
            base = AGENT_BASE_PROMPTS[AgentType.GENERAL]

        return self.build(agent_type=AgentType.GENERAL, custom_base=base, include_karpathy=True)

    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()


# 全局单例
_builder = None


def get_builder() -> AgentPromptBuilder:
    """获取全局 Prompt 构建器"""
    global _builder
    if _builder is None:
        _builder = AgentPromptBuilder()
    return _builder


def build_karpathy_agent_prompt(
    agent_type: str,
    custom_base: Optional[str] = None,
    extra_context: Optional[str] = None,
) -> str:
    """
    快速构建函数：返回带 Karpathy 准则的 Agent Prompt

    Args:
        agent_type: Agent 类型
        custom_base: 自定义基础提示
        extra_context: 额外上下文

    Returns:
        完整的 System Prompt
    """
    return get_builder().build(
        agent_type=agent_type,
        custom_base=custom_base,
        include_karpathy=True,
        extra_context=extra_context,
    )


# 预定义的 Agent Prompt（可直接使用）
def get_code_architect_prompt(project_context: Optional[str] = None) -> str:
    """获取代码架构师 Prompt"""
    return build_karpathy_agent_prompt(
        agent_type=AgentType.CODE_ARCHITECT,
        extra_context=project_context,
    )


def get_debug_specialist_prompt() -> str:
    """获取调试专家 Prompt"""
    return build_karpathy_agent_prompt(agent_type=AgentType.DEBUG_SPECIALIST)


def get_code_generator_prompt() -> str:
    """获取代码生成器 Prompt"""
    return build_karpathy_agent_prompt(agent_type=AgentType.CODE_GENERATOR)


def get_refactor_prompt(project_context: Optional[str] = None) -> str:
    """获取重构专家 Prompt"""
    return build_karpathy_agent_prompt(
        agent_type=AgentType.REFACTOR_AGENT,
        extra_context=project_context,
    )