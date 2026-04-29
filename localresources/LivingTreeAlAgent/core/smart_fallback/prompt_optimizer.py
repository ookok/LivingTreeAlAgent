"""
Enhanced Prompt Optimizer - 增强提示词优化器
==========================================

基于现有 message_patterns/prompt_generator.py 的 PromptOptimizer 增强
专门为降级链场景优化用户查询

优化策略:
1. 结构增强 - 添加 Markdown 格式要求
2. 角色设定 - 指定专业角色
3. 约束添加 - 添加质量约束和格式要求
4. 上下文补全 - 补充缺失的上下文信息
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any


class QueryType(Enum):
    """查询类型"""
    GENERAL = "general"           # 通用问题
    TECHNICAL = "technical"      # 技术问题
    CODE = "code"               # 代码相关
    ANALYSIS = "analysis"       # 分析类
    WRITING = "writing"         # 写作类
    CREATIVE = "creative"       # 创意类
    KNOWLEDGE = "knowledge"      # 知识问答
    NEWS = "news"               # 新闻/实时


@dataclass
class OptimizationResult:
    """优化结果"""
    original: str               # 原始查询
    optimized: str              # 优化后提示词
    query_type: QueryType       # 识别的查询类型
    confidence: float           # 优化置信度
    optimizations_applied: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "original": self.original,
            "optimized": self.optimized,
            "query_type": self.query_type.value,
            "confidence": self.confidence,
            "optimizations_applied": self.optimizations_applied,
            "warnings": self.warnings,
        }


class EnhancedPromptOptimizer:
    """
    增强提示词优化器

    在本地模型回答质量不佳时，优化用户查询以提升外部AI回答质量
    """

    # 查询类型关键词
    QUERY_TYPE_KEYWORDS = {
        QueryType.TECHNICAL: [
            "技术", "原理", "架构", "设计", "实现", "方法", "算法",
            "how", "why", "what", "原理", "机制", "系统"
        ],
        QueryType.CODE: [
            "代码", "编程", "函数", "调试", "bug", "error",
            "code", "function", "debug", "syntax", "import"
        ],
        QueryType.ANALYSIS: [
            "分析", "对比", "比较", "评估", "优缺点",
            "analyze", "compare", "evaluate", "pros", "cons"
        ],
        QueryType.WRITING: [
            "写作", "文章", "报告", "文档", "撰写", "起草",
            "write", "article", "report", "draft"
        ],
        QueryType.CREATIVE: [
            "创意", "想象", "故事", "设计", "灵感",
            "creative", "imagine", "story", "design", "idea"
        ],
        QueryType.NEWS: [
            "今天", "最新", "新闻", "最近", "当下",
            "today", "news", "latest", "recent", "current"
        ],
    }

    # 角色设定模板
    ROLE_TEMPLATES = {
        QueryType.TECHNICAL: "你是一位资深的软件架构师和技术专家，具有10年以上经验。",
        QueryType.CODE: "你是一位专业的程序员，精通多种编程语言和最佳实践。",
        QueryType.ANALYSIS: "你是一位专业分析师，擅长逻辑分析和数据洞察。",
        QueryType.WRITING: "你是一位专业作家和内容编辑，擅长各类文体的撰写。",
        QueryType.CREATIVE: "你是一位创意专家，思维活跃，想象力丰富。",
        QueryType.NEWS: "你是一位新闻分析师，熟悉各领域最新动态。",
        QueryType.GENERAL: "你是一位知识渊博的AI助手。",
        QueryType.KNOWLEDGE: "你是一位百科全书式的知识专家。",
    }

    # 结构化模板
    STRUCTURE_TEMPLATES = {
        QueryType.TECHNICAL: """
## 回答要求
1. 技术原理清晰阐述
2. 结合实际案例说明
3. 给出可落地的建议
4. 如有代码示例，请提供完整可运行代码

## 格式要求
- 使用 Markdown 格式
- 适当使用代码块
- 重点内容加粗""",
        QueryType.CODE: """
## 回答要求
1. 给出完整可运行的代码示例
2. 代码需要添加注释
3. 解释关键逻辑和实现思路
4. 如有多种实现方式，请对比说明

## 格式要求
- 代码使用标准格式化
- 主要语言使用代码块标注""",
        QueryType.ANALYSIS: """
## 回答要求
1. 全面分析问题的各个方面
2. 给出正反两面观点
3. 提供数据或案例支撑
4. 最终给出明确的建议

## 格式要求
- 使用对比表格展示
- 重点数据突出显示""",
        QueryType.WRITING: """
## 回答要求
1. 内容专业、准确、完整
2. 逻辑清晰，层次分明
3. 语言流畅，易于理解

## 格式要求
- 使用标准书面语
- 适当使用标题和小标题""",
        QueryType.CREATIVE: """
## 回答要求
1. 创意新颖独特
2. 富有想象力和启发性
3. 思路可以天马行空

## 格式要求
- 可以使用列表或脑图形式
- 鼓励图文并茂""",
        QueryType.NEWS: """
## 回答要求
1. 准确、客观、真实
2. 注明信息来源
3. 分析事件影响和意义

## 格式要求
- 简明扼要，突出重点
- 如有时间线，请按时间顺序整理""",
        QueryType.GENERAL: """
## 回答要求
1. 准确、全面、有用
2. 简洁明了，避免冗余
3. 如不确定，请明确说明

## 格式要求
- 使用 Markdown 格式
- 重点内容加粗""",
        QueryType.KNOWLEDGE: """
## 回答要求
1. 知识准确，来源可靠
2. 解释清晰，易于理解
3. 可以扩展相关知识点

## 格式要求
- 使用 Markdown 格式
- 如有定义，使用引用块""",
    }

    def __init__(self):
        pass

    def optimize(self, query: str, context: Optional[Dict[str, Any]] = None) -> OptimizationResult:
        """
        优化用户查询

        Args:
            query: 原始用户查询
            context: 额外上下文

        Returns:
            OptimizationResult: 优化结果
        """
        context = context or {}
        optimizations = []
        warnings = []

        # 1. 识别查询类型
        query_type = self._classify_query(query)
        optimizations.append(f"识别为 {query_type.value} 类型查询")

        # 2. 构建系统提示
        role = self.ROLE_TEMPLATES.get(query_type, self.ROLE_TEMPLATES[QueryType.GENERAL])
        structure = self.STRUCTURE_TEMPLATES.get(query_type, self.STRUCTURE_TEMPLATES[QueryType.GENERAL])

        # 3. 组合优化
        optimized_parts = []

        # 添加角色设定
        if context.get("add_role", True):
            optimized_parts.append(role.strip())

        # 添加结构化要求
        if context.get("add_structure", True):
            optimized_parts.append(structure.strip())

        # 添加原始查询
        optimized_parts.append(f"## 用户问题\n{query}")

        # 4. 添加上下文（如果有）
        if context.get("extra_context"):
            optimized_parts.append(f"\n## 补充信息\n{context['extra_context']}")

        # 5. 特殊优化
        optimized_query = self._apply_special_optimizations(query, query_type)
        if optimized_query != query:
            optimizations.append("应用特殊优化规则")
            # 更新问题部分
            optimized_parts[-1] = f"## 用户问题\n{optimized_query}"

        optimized = "\n\n".join(optimized_parts)

        # 计算置信度
        confidence = self._calculate_confidence(query, query_type)

        return OptimizationResult(
            original=query,
            optimized=optimized,
            query_type=query_type,
            confidence=confidence,
            optimizations_applied=optimizations,
            warnings=warnings,
        )

    def _classify_query(self, query: str) -> QueryType:
        """分类查询类型"""
        query_lower = query.lower()
        scores = {qt: 0 for qt in QueryType}

        for qt, keywords in self.QUERY_TYPE_KEYWORDS.items():
            for keyword in keywords:
                if keyword.lower() in query_lower:
                    scores[qt] += 1

        # 实时性检测（优先级最高）
        news_indicators = ["今天", "最新", "最近", "现在", "today", "latest", "now", "current"]
        if any(ind in query_lower for ind in news_indicators):
            return QueryType.NEWS

        # 返回得分最高的类型
        max_score = max(scores.values())
        if max_score == 0:
            return QueryType.GENERAL

        for qt, score in scores.items():
            if score == max_score:
                return qt

        return QueryType.GENERAL

    def _apply_special_optimizations(self, query: str, query_type: QueryType) -> str:
        """应用特殊优化规则"""

        # 去除口语化表达
        query = re.sub(r"帮我|请帮我|我想知道|问一下", "", query)
        query = re.sub(r"那个|这个|啥|怎么", "", query)
        query = query.strip()

        # 根据类型进一步优化
        if query_type == QueryType.CODE:
            # 代码相关：明确语言或框架
            if not any(lang in query_lower for lang in ["python", "java", "javascript", "c++", "rust", "go"]):
                # 不包含语言，可能需要补全
                pass

        elif query_type == QueryType.NEWS:
            # 新闻类：确保有时间范围
            pass

        return query

    def _calculate_confidence(self, query: str, query_type: QueryType) -> float:
        """计算优化置信度"""
        base = 0.7

        # 长度适中
        if 10 <= len(query) <= 500:
            base += 0.1

        # 有明确关键词
        if any(kw in query.lower() for kw in ["如何", "怎么", "为什么", "what", "how", "why"]):
            base += 0.1

        # 实时性查询降低置信度
        if query_type == QueryType.NEWS:
            base -= 0.2

        return max(0.0, min(1.0, base))

    def batch_optimize(
        self,
        queries: List[str],
        contexts: Optional[List[Dict[str, Any]]] = None,
    ) -> List[OptimizationResult]:
        """批量优化"""
        contexts = contexts or [{} for _ in queries]
        return [self.optimize(q, c) for q, c in zip(queries, contexts)]


# 全局实例
_optimizer: Optional[EnhancedPromptOptimizer] = None


def get_prompt_optimizer() -> EnhancedPromptOptimizer:
    """获取提示词优化器实例"""
    global _optimizer
    if _optimizer is None:
        _optimizer = EnhancedPromptOptimizer()
    return _optimizer