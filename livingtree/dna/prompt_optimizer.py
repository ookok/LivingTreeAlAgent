"""PromptOptimizer — AI-driven prompt enhancement inspired by prompt-optimizer.

Four capabilities:
  1. Preprocess: auto-enhance user prompts before LLM call
  2. Role templates: few-shot examples + quality gates for 8+ roles
  3. Multi-round: /optimize command for iterative refinement
  4. Context: auto-extract @variables from user input

Uses free provider (no extra model needed) for one-shot optimization.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger


@dataclass
class OptimizeResult:
    original: str
    optimized: str
    rounds: int = 1
    improvements: list[str] = field(default_factory=list)
    quality_score: float = 0.0


@dataclass
class RoleTemplate:
    name: str
    role_prompt: str
    few_shot_examples: list[dict] = field(default_factory=list)
    quality_gates: list[str] = field(default_factory=list)
    output_format: str = ""


# ═══ Enhanced role templates with few-shot ═══

ROLE_TEMPLATES: dict[str, RoleTemplate] = {
    "环评专家": RoleTemplate(
        name="环评专家",
        role_prompt="你是资深环境影响评价工程师，熟悉GB/T3840-1991等国家标准。",
        few_shot_examples=[
            {"input": "分析工厂对周围大气的影响", "output": "根据GB/T3840-1991，采用高斯烟羽模型...需计算SO2、NOx、PM10的最大落地浓度..."},
        ],
        quality_gates=["引用国家标准", "包含数值计算", "给出明确结论"],
        output_format="## 环评分析\n\n### 1. 污染源分析\n{source}\n\n### 2. 扩散模型\n{model}\n\n### 3. 计算结果\n{results}\n\n### 4. 结论与建议\n{conclusion}",
    ),
    "代码审查": RoleTemplate(
        name="代码审查",
        role_prompt="你是资深代码审查专家，擅长发现安全漏洞和性能问题。",
        few_shot_examples=[
            {"input": "审查这段登录代码", "output": "发现3个问题：1) SQL注入风险 2) 密码未哈希 3) 缺少速率限制。修复建议: ..."},
        ],
        quality_gates=["识别安全风险", "提供具体修复方案", "考虑边界情况"],
        output_format="## 代码审查\n\n### 安全问题\n{security}\n\n### 性能问题\n{performance}\n\n### 改进建议\n{improvements}",
    ),
    "数据分析师": RoleTemplate(
        name="数据分析师",
        role_prompt="你是资深数据分析师，擅长Python/SQL和数据可视化。",
        few_shot_examples=[
            {"input": "分析销售趋势", "output": "使用pandas读取数据→按月份聚合→matplotlib绘制趋势图→发现Q3峰值与促销活动相关"},
        ],
        quality_gates=["数据来源明确", "包含可视化建议", "给出可执行结论"],
        output_format="## 分析报告\n\n### 数据概览\n{overview}\n\n### 趋势分析\n{trends}\n\n### 关键发现\n{findings}\n\n### 建议\n{recommendations}",
    ),
    "全栈工程师": RoleTemplate(
        name="全栈工程师",
        role_prompt="你是资深全栈工程师，精通Python/React/SQL，能输出可直接运行的代码。",
        few_shot_examples=[
            {"input": "创建一个用户管理API", "output": "```python\nfrom fastapi import FastAPI\n...\n```\n配套React组件: ...\n数据库迁移: ..."},
        ],
        quality_gates=["代码可直接运行", "包含错误处理", "有测试用例"],
        output_format="## 实现方案\n\n### 后端 (FastAPI)\n```python\n{backend}\n```\n\n### 前端 (React)\n```tsx\n{frontend}\n```\n\n### 数据库\n```sql\n{database}\n```",
    ),
    "技术文档": RoleTemplate(
        name="技术文档",
        role_prompt="你是资深技术文档工程师，擅长将复杂概念转化为清晰文档。需要同时生成中英文版本。",
        few_shot_examples=[
            {"input": "写个API文档", "output": "## API Reference\n\n### GET /api/users\n返回用户列表。\n\n#### 参数\n| Name | Type | Description |\n..."},
        ],
        quality_gates=["结构清晰", "示例完整", "包含错误码说明"],
        output_format="## 中文版\n{zh}\n\n## English\n{en}",
    ),
    "AI研究员": RoleTemplate(
        name="AI研究员",
        role_prompt="你是资深AI研究工程师，专精大模型微调和推理优化。",
        few_shot_examples=[
            {"input": "如何提升Qwen模型推理速度", "output": "使用vLLM部署+FP8量化+continuous batching，实测吞吐提升300%+"},
        ],
        quality_gates=["引用最新技术", "有实验数据支撑", "给出实施步骤"],
        output_format="## 技术方案\n\n### 背景\n{background}\n\n### 方法\n{method}\n\n### 预期效果\n{expected}\n\n### 实施步骤\n{steps}",
    ),
}

# ═══ Prompt preprocessing ═══

PRESET_OPTIMIZATIONS: dict[str, str] = {
    "生图": "补充: 分辨率(1024x1024), 风格(写实/动漫/赛博朋克), 色调(暖/冷), 细节程度(高), 输出格式(PNG)",
    "写代码": "补充: 语言(指定), 框架(指定), 需要注释, 需要错误处理, 需要测试用例",
    "分析数据": "补充: 数据格式(CSV/JSON/Excel), 分析维度(趋势/对比/分布), 需要可视化, 需要结论",
    "搜索": "补充: 搜索范围(学术/新闻/技术文档), 时间范围(最近), 结果数量(5-10), 需要来源链接",
    "翻译": "补充: 目标语言, 保持原文格式, 术语一致, 需要双语对照",
    "写报告": "补充: 报告类型(技术/商业/学术), 包含摘要, 分章节, 引用来源, 字数要求",
    "总结": "补充: 总结长度(200-500字), 保留关键数据, 结构化输出, 标注时间节点",
    "对话": "补充: 角色设定, 回复风格(正式/轻松), 需要中文回复",
}

ENHANCE_PATTERNS = [
    (r"^(生[成张]?|画|做)(\S*图)", "生图", "生成一张 {match} 的高质量图片"),
    (r"^(写|帮我写)(\S*代码|程序)", "写代码", "编写 {match}"),
    (r"^(分析|帮我分析)", "分析数据", "帮我分析以下数据，给出趋势和结论"),
    (r"^(搜|查|找)", "搜索", "搜索以下关键词并返回相关结果"),
    (r"^(翻译|帮我翻译)", "翻译", "请翻译以下内容"),
    (r"^(总结|帮我总结|概括)", "总结", "请总结以下内容，保留关键信息"),
]


async def preprocess_prompt(user_input: str, hub=None) -> str:
    """Auto-enhance user prompt before sending to LLM.

    Uses pattern matching (fast, ~0ms) for common cases.
    For complex inputs, uses a free provider for one-shot optimization.
    """
    enhanced = user_input.strip()

    # Step 1: Pattern-based quick enhancement (~0ms)
    for pattern, category, template in ENHANCE_PATTERNS:
        m = re.match(pattern, user_input)
        if m:
            tips = PRESET_OPTIMIZATIONS.get(category, "")
            enhanced = template.replace("{match}", m.group(0))
            if tips:
                enhanced += f"\n\n{tips}"
            break

    # Step 2: Context variable extraction
    enhanced = extract_context_vars(enhanced)

    # Step 3: One-shot deep optimization if hub available and prompt is short
    if hub and len(user_input) < 50 and user_input == enhanced:
        try:
            enhanced = await _deep_optimize(user_input, hub)
        except Exception as e:
            logger.debug(f"Deep optimize: {e}")

    return enhanced


async def _deep_optimize(user_input: str, hub) -> str:
    """Use a free LLM to do one-shot deep prompt optimization."""
    llm = hub.world.consciousness._llm
    provider = getattr(llm, '_elected', '') or "auto"

    optimize_prompt = (
        f"你是提示词优化专家。将以下简单需求转化为专业提示词，补充：\n"
        f"1. 风格要求和输出格式\n2. 质量标准\n3. 边界条件和约束\n\n"
        f"原始需求: {user_input}\n\n"
        f"只需输出优化后的提示词，不要解释。"
    )

    try:
        result = await llm.chat(
            messages=[{"role": "user", "content": optimize_prompt}],
            provider=provider,
            temperature=0.3,
            max_tokens=500,
            timeout=10,
        )
        if result and result.text:
            return result.text.strip()
    except Exception:
        pass

    return user_input


# ═══ Context variable extraction ═══

def extract_context_vars(text: str) -> str:
    """Auto-extract and resolve context variables from text.

    Supports:
      @path/to/file  → inject file content
      {{var}}        → resolve from environment/context
      #tag           → treat as topic hint
    """
    # @path references
    for m in re.finditer(r'@([^\s,，。；;]+)', text):
        path = m.group(1)
        p = Path(path)
        if p.exists() and p.is_file():
            try:
                content = p.read_text(errors="replace")[:2000]
                text = text.replace(m.group(0), f"[FILE: {path}]\n{content}\n[/FILE]")
                logger.debug(f"Injected file: {path} ({len(content)} chars)")
            except Exception:
                pass

    # {{var}} references from environment
    for m in re.finditer(r'\{\{(\w+)\}\}', text):
        var = m.group(1)
        import os
        val = os.environ.get(var, os.environ.get(var.upper(), ""))
        if val:
            text = text.replace(m.group(0), val)

    return text


# ═══ Multi-round optimization ═══

async def optimize_prompt(
    user_input: str,
    role: str = "",
    rounds: int = 3,
    hub=None,
) -> OptimizeResult:
    """Multi-round iterative prompt optimization with comparison."""
    if not hub:
        return OptimizeResult(original=user_input, optimized=user_input)

    llm = hub.world.consciousness._llm
    provider = getattr(llm, '_elected', '') or "auto"
    improvements: list[str] = []
    current = user_input
    original = user_input

    template = ROLE_TEMPLATES.get(role) if role else None

    for rnd in range(rounds):
        if rnd == 0:
            # Round 1: Basic enhancement with role template
            system_msg = "你是提示词优化专家。将简单需求转化为专业提示词。只需输出优化结果，不要解释。"
            if template:
                system_msg += f"\n当前角色: {template.name}\n角色设定: {template.role_prompt}"
            round_prompt = f"优化以下提示词:\n{current}"
        elif rnd == 1:
            # Round 2: Add quality requirements
            round_prompt = (
                f"进一步优化以下提示词，要求:\n"
                f"1. 补充输出格式规范\n"
                f"2. 添加质量标准\n"
                f"3. 填补边界条件\n\n"
                f"{current}"
            )
        else:
            # Round 3+: Specific improvements
            round_prompt = (
                f"最终优化以下提示词，使其达到专业水准:\n"
                f"1. 结构清晰，分步骤\n"
                f"2. 包含成功标准\n"
                f"3. 精炼语言，删除冗余\n\n"
                f"{current}"
            )

        try:
            result = await llm.chat(
                messages=[{"role": "user", "content": round_prompt}],
                provider=provider,
                temperature=0.5,
                max_tokens=800,
                timeout=15,
            )
            if result and result.text and len(result.text) > len(current) * 0.5:
                improvements.append(f"Round {rnd + 1}: {len(result.text) - len(current)} chars added")
                current = result.text.strip()
        except Exception as e:
            logger.debug(f"Optimize round {rnd}: {e}")
            break

    quality = min(1.0, len(current) / max(len(original), 1) * 0.3 + 0.5)

    return OptimizeResult(
        original=original,
        optimized=current,
        rounds=rounds,
        improvements=improvements,
        quality_score=quality,
    )


# ═══ Role template application ═══

def apply_role(user_input: str, role_name: str) -> str:
    """Apply a role template to a user prompt."""
    template = ROLE_TEMPLATES.get(role_name)
    if not template:
        return user_input

    parts = [template.role_prompt]

    # Add few-shot examples
    if template.few_shot_examples:
        parts.append("\n示例:")
        for ex in template.few_shot_examples[:2]:
            parts.append(f"用户: {ex['input']}\n助手: {ex['output']}")

    # Add quality gates
    if template.quality_gates:
        parts.append("\n质量要求: " + ", ".join(template.quality_gates))

    # Add output format
    if template.output_format:
        parts.append(f"\n输出格式:\n{template.output_format}")

    parts.append(f"\n---\n用户输入: {user_input}")

    return "\n".join(parts)


# ═══ Global functions ═══

async def preprocess(user_input: str, hub=None, role: str = "") -> str:
    """Full preprocessing pipeline: enhance → apply role → extract context."""
    text = await preprocess_prompt(user_input, hub)
    if role:
        text = apply_role(text, role)
    return text


async def multi_optimize(user_input: str, role: str = "", rounds: int = 3, hub=None):
    return await optimize_prompt(user_input, role, rounds, hub)


def get_roles() -> list[str]:
    return list(ROLE_TEMPLATES.keys())


def get_role(name: str) -> RoleTemplate | None:
    return ROLE_TEMPLATES.get(name)
