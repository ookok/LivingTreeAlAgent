"""
推理分析工具
使用推理模型进行深度分析，展示思考过程

功能：
1. 文本分析（情节漏洞、人物一致性、文风评估）
2. 决策支持（多方案对比）
3. 问题诊断（错误分析、根因定位）
"""

import json
import time
from typing import Optional, Callable, Dict, Any, List
from dataclasses import dataclass

from core.reasoning_client import (
    ReasoningModelClient,
    ReasoningConfig,
    GenerationResult
)


@dataclass
class AnalysisResult:
    """分析结果"""
    task: str                      # 分析任务类型
    final_answer: str              # 最终结论
    reasoning: str                 # 完整思考过程
    steps: List[str]               # 分解的步骤
    confidence: float              # 置信度
    recommendations: List[str]      # 建议
    input_params: Dict[str, Any]   # 输入参数
    duration: float                # 耗时


class ReasoningAnalyzer:
    """
    推理分析工具

    使用支持思考过程的模型进行深度分析
    """

    # 分析任务模板
    TASK_TEMPLATES = {
        "plot_hole": {
            "description": "情节漏洞检测",
            "system_prompt": """你是一位专业的小说编辑，擅长分析故事情节的逻辑漏洞。

分析原则：
1. 时间线一致性：检查事件发生的时间是否矛盾
2. 因果逻辑：事件之间的因果关系是否合理
3. 人物动机：角色行为是否符合其性格和背景
4. 世界观一致：是否与已建立的规则冲突

请详细分析每个可能的问题点。""",
            "prompt_template": """请分析以下文本中的情节漏洞：

{text}

请逐步思考：
1. 首先，理解故事的当前状态和发展
2. 然后，识别所有涉及的人物和时间点
3. 接着，检查每个因果关系是否合理
4. 最后，列出发现的所有问题

格式：
【发现的问题】
1. [问题描述]
   - 位置：[在文本中的位置]
   - 类型：[时间矛盾/逻辑漏洞/动机不足/其他]
   - 影响：[对故事的影响程度]

【修复建议】
1. [具体的修复方案]"""
        },

        "character_consistency": {
            "description": "人物一致性分析",
            "system_prompt": """你是一位专业的人物塑造分析师，擅长检查文学作品中的角色一致性。

分析维度：
1. 性格特征：角色是否始终保持一致的性格
2. 行为逻辑：角色行为是否符合其性格设定
3. 语言风格：对话是否符合角色背景
4. 成长曲线：角色的变化是否合理可信

请全面分析每个角色的表现。""",
            "prompt_template": """请分析以下文本中的人物一致性：

{text}

请逐步思考：
1. 首先，识别出所有主要人物
2. 然后，提取每个角色的关键特征
3. 接着，检查人物在文本中的行为是否一致
4. 最后，评估人物的对话风格是否符合其背景

格式：
【人物分析】
1. [角色名]
   - 性格特征：[描述]
   - 行为一致性：[评分 1-10]
   - 发现的问题：[如有]

【总体评估】
- 一致性评分：[1-10]
- 主要问题：[列出]
- 改进建议：[建议]"""
        },

        "style_evaluation": {
            "description": "文风评估",
            "system_prompt": """你是一位专业的文学评论家，擅长评估写作风格和语言运用。

评估维度：
1. 文字流畅度：句子结构是否自然
2. 修辞手法：是否恰当使用比喻、拟人等
3. 情感表达：是否能引发读者共鸣
4. 整体风格：是否符合作品类型和受众

请客观评价文本的写作质量。""",
            "prompt_template": """请评估以下文本的写作风格：

{text}

请逐步思考：
1. 首先，识别文体的基本特征
2. 然后，分析语言特点和修辞手法
3. 接着，评估情感表达的效果
4. 最后，给出整体风格评价

格式：
【文体特征】
- 类型：[小说/散文/议论文等]
- 风格：[正式/轻松/诗意等]
- 目标读者：[推测]

【优点】
1. [具体优点]
2. [具体优点]

【可改进点】
1. [改进建议]
2. [改进建议]

【整体评分】
- 流畅度：[1-10]
- 感染力：[1-10]
- 创新性：[1-10]"""
        },

        "decision_support": {
            "description": "决策支持",
            "system_prompt": """你是一位专业的决策顾问，擅长分析问题和提供多方案对比。

分析原则：
1. 全面性：考虑所有可能的选项
2. 可行性：评估每个方案的执行难度
3. 风险评估：识别潜在风险和应对措施
4. 权衡分析：明确利弊得失

请客观分析每个方案的优缺点。""",
            "prompt_template": """请帮助分析以下决策问题：

背景：{context}

问题：{question}

请逐步思考：
1. 首先，明确决策的目标和约束条件
2. 然后，列出所有可能的方案
3. 接着，分析每个方案的优缺点
4. 最后，给出推荐和理由

格式：
【目标分析】
- 主要目标：[描述]
- 次要目标：[描述]
- 约束条件：[列出]

【方案对比】
| 方案 | 优点 | 缺点 | 风险 | 推荐度 |
|------|------|------|------|--------|
| A    | ...  | ...  | ...  | ★★★    |
| B    | ...  | ...  | ...  | ★★☆    |

【推荐方案】
- 首选：[方案名]
- 理由：[解释]"""
        },

        "problem_diagnosis": {
            "description": "问题诊断",
            "system_prompt": """你是一位专业的技术诊断专家，擅长分析问题并定位根本原因。

诊断方法：
1. 现象观察：准确理解问题表现
2. 数据分析：从错误信息中提取关键线索
3. 假设验证：逐个排查可能的原因
4. 根因定位：找到最根本的原因

请系统性地分析每个问题。""",
            "prompt_template": """请诊断以下问题：

问题描述：{question}

相关信息：{context}

请逐步思考：
1. 首先，理解问题的具体表现
2. 然后，从错误信息中提取关键线索
3. 接着，列出可能的原因并逐一排查
4. 最后，确定最可能的原因

格式：
【问题现象】
- 表现：[具体症状]
- 环境：[操作系统、软件版本等]
- 错误信息：[如有]

【可能原因】
1. [原因1] - 可能性：高/中/低
2. [原因2] - 可能性：高/中/低

【根因分析】
最可能的原因：[描述]
诊断依据：[解释]

【解决方案】
1. [具体步骤]
2. [具体步骤]

【预防建议】
- [如何避免再次发生]"""
        },

        "code_review": {
            "description": "代码审查",
            "system_prompt": """你是一位资深的代码审查专家，擅长发现代码中的问题和改进点。

审查维度：
1. 正确性：逻辑是否正确处理边界情况
2. 效率：时间和空间复杂度
3. 可读性：命名、注释、结构
4. 安全性：潜在的安全漏洞
5. 最佳实践：是否符合语言/框架的最佳实践

请全面审查代码质量。""",
            "prompt_template": """请审查以下代码：

语言/框架：{language}

代码：
```{language}
{code}
```

请逐步思考：
1. 首先，理解代码的功能和结构
2. 然后，分析每个函数/方法的逻辑
3. 接着，检查边界情况和错误处理
4. 最后，评估整体设计

格式：
【功能概述】
- 主要功能：[描述]
- 输入输出：[描述]

【发现的问题】
| 问题 | 严重性 | 位置 | 建议 |
|------|--------|------|------|
| ...  | 高/中/低 | ...  | ...  |

【改进建议】
1. [具体改进建议]

【评分】
- 正确性：[1-10]
- 效率：[1-10]
- 可读性：[1-10]
- 总体：[1-10]"""
        }
    }

    def __init__(
        self,
        model_name: str = "deepseek-r1:7b",
        base_url: str = "http://localhost:11434",
        reasoning_client: ReasoningModelClient = None
    ):
        """
        初始化推理分析工具

        Args:
            model_name: 推理模型名称
            base_url: Ollama API 地址
            reasoning_client: 已有的推理客户端（可选）
        """
        if reasoning_client:
            self.client = reasoning_client
        else:
            config = ReasoningConfig(
                model_name=model_name,
                base_url=base_url
            )
            self.client = ReasoningModelClient(config)

        self._connect()

    def _connect(self):
        """连接模型"""
        if not self.client.is_connected():
            self.client.connect()

    # ── 通用分析 ───────────────────────────────────────────────────

    def analyze(
        self,
        task: str,
        text: str = None,
        context: str = None,
        question: str = None,
        language: str = None,
        code: str = None,
        show_reasoning: bool = True,
        progress_callback: Callable[[str], None] = None
    ) -> AnalysisResult:
        """
        执行分析任务

        Args:
            task: 任务类型（plot_hole/character_consistency/style_evaluation 等）
            text: 要分析的文本
            context: 背景上下文
            question: 问题描述
            language: 代码语言
            code: 代码内容
            show_reasoning: 是否显示思考过程
            progress_callback: 进度回调

        Returns:
            AnalysisResult
        """
        start_time = time.time()

        # 获取模板
        template = self.TASK_TEMPLATES.get(task)
        if not template:
            return AnalysisResult(
                task=task,
                final_answer=f"未知任务类型: {task}",
                reasoning="",
                steps=[],
                confidence=0.0,
                recommendations=[],
                input_params={},
                duration=time.time() - start_time
            )

        # 构建提示词
        prompt_vars = {}
        if text:
            prompt_vars["text"] = text
        if context:
            prompt_vars["context"] = context
        if question:
            prompt_vars["question"] = question
        if language:
            prompt_vars["language"] = language
        if code:
            prompt_vars["code"] = code

        # 填充模板
        try:
            prompt = template["prompt_template"].format(**prompt_vars)
        except KeyError as e:
            return AnalysisResult(
                task=task,
                final_answer=f"模板变量缺失: {e}",
                reasoning="",
                steps=[],
                confidence=0.0,
                recommendations=[],
                input_params={},
                duration=time.time() - start_time
            )

        # 执行生成
        reasoning_content = []
        final_content = []

        def reasoning_cb(text: str):
            reasoning_content.append(text)
            if progress_callback:
                progress_callback(f"[思考] {text[:50]}...")

        def stream_cb(text: str):
            final_content.append(text)
            if progress_callback:
                progress_callback(f"[回答] {text[:50]}...")

        result = self.client.generate(
            prompt=prompt,
            system_prompt=template["system_prompt"],
            reasoning_callback=reasoning_cb,
            stream_callback=stream_cb
        )

        # 解析结果
        full_reasoning = "".join(reasoning_content)
        full_answer = "".join(final_content)

        # 提取步骤和建议
        steps = self._extract_steps(full_reasoning + full_answer)
        recommendations = self._extract_recommendations(full_answer)
        confidence = self._estimate_confidence(full_reasoning)

        return AnalysisResult(
            task=task,
            final_answer=full_answer,
            reasoning=full_reasoning,
            steps=steps,
            confidence=confidence,
            recommendations=recommendations,
            input_params=result.input_params,
            duration=time.time() - start_time
        )

    def _extract_steps(self, text: str) -> List[str]:
        """提取思考步骤"""
        steps = []

        # 尝试提取编号步骤
        import re
        step_patterns = [
            r'(?:^|\n)\s*(\d+)[.、：:]\s*(.+)',
            r'(?:首先|然后|接着|最后)[，,](.+)',
            r'\[?步骤\s*(\d+)\]?\s*[:：]\s*(.+)',
        ]

        for pattern in step_patterns:
            matches = re.findall(pattern, text, re.MULTILINE)
            if matches:
                for match in matches:
                    if isinstance(match, tuple):
                        steps.append(f"{match[0]}. {match[1]}")
                    else:
                        steps.append(match)
                break

        return steps[:10]  # 最多10步

    def _extract_recommendations(self, text: str) -> List[str]:
        """提取建议"""
        recommendations = []

        import re

        # 查找建议部分
        sections = re.split(r'【[^】]+】', text)

        for section in sections:
            if any(keyword in section for keyword in ['建议', '改进', '修复', '推荐']):
                # 提取列表项
                items = re.findall(r'^\s*[\d一二三四五六七八九十]+[.、：:]\s*(.+?)$', section, re.MULTILINE)
                recommendations.extend(items)

        return recommendations[:5]  # 最多5条

    def _estimate_confidence(self, reasoning: str) -> float:
        """估计置信度"""
        if not reasoning:
            return 0.5

        # 基于思考长度估计
        length_score = min(len(reasoning) / 1000, 1.0) * 0.3

        # 基于关键词
        keywords = ['可能', '应该', '大概', '也许']
        uncertainty = sum(1 for kw in keywords if kw in reasoning) / len(keywords)

        base = 0.7
        confidence = base + length_score - uncertainty * 0.2

        return max(0.0, min(1.0, confidence))

    # ── 便捷方法 ───────────────────────────────────────────────────

    def analyze_plot_holes(self, text: str) -> AnalysisResult:
        """分析情节漏洞"""
        return self.analyze("plot_hole", text=text)

    def analyze_character(self, text: str) -> AnalysisResult:
        """分析人物一致性"""
        return self.analyze("character_consistency", text=text)

    def evaluate_style(self, text: str) -> AnalysisResult:
        """评估文风"""
        return self.analyze("style_evaluation", text=text)

    def support_decision(self, question: str, context: str = "") -> AnalysisResult:
        """决策支持"""
        return self.analyze("decision_support", question=question, context=context)

    def diagnose_problem(self, question: str, context: str = "") -> AnalysisResult:
        """问题诊断"""
        return self.analyze("problem_diagnosis", question=question, context=context)

    def review_code(self, code: str, language: str = "python") -> AnalysisResult:
        """代码审查"""
        return self.analyze("code_review", code=code, language=language)

    # ── 批量分析 ──────────────────────────────────────────────────

    def batch_analyze(
        self,
        items: List[Dict[str, str]],
        task: str,
        callback: Callable[[int, int, AnalysisResult], None] = None
    ) -> List[AnalysisResult]:
        """
        批量分析

        Args:
            items: 项目列表，每项包含分析所需的字段
            task: 任务类型
            callback: 完成回调 (index, total, result)

        Returns:
            分析结果列表
        """
        results = []

        for i, item in enumerate(items):
            # 确保重连
            if not self.client.is_connected():
                self.client.reconnect()

            # 执行分析
            result = self.analyze(task, **item)

            results.append(result)

            # 回调
            if callback:
                callback(i + 1, len(items), result)

            # 间隔
            if i < len(items) - 1:
                time.sleep(0.5)

        return results

    # ── 统计信息 ──────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "client_stats": self.client.get_connection_stats(),
            "available_models": self.client.list_available_reasoning_models(),
            "supported_tasks": list(self.TASK_TEMPLATES.keys())
        }

    def close(self):
        """关闭"""
        self.client.close()


# ── 单例 ──────────────────────────────────────────────────────────

_reasoning_analyzer: Optional[ReasoningAnalyzer] = None


def get_reasoning_analyzer(
    model_name: str = "deepseek-r1:7b",
    base_url: str = "http://localhost:11434"
) -> ReasoningAnalyzer:
    """获取推理分析器单例"""
    global _reasoning_analyzer

    if _reasoning_analyzer is None:
        _reasoning_analyzer = ReasoningAnalyzer(model_name, base_url)

    return _reasoning_analyzer
