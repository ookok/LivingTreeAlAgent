# -*- coding: utf-8 -*-

"""
IntentEvolutionEngine - 意图演化引擎

实现"模糊意图的渐进澄清"：
- AI 不需要一开始想清楚所有细节
- 在执行中逐步明确意图
- 基于 Agent 发现的上下文，迭代演化意图

核心流程：
    模糊意图 → 探索上下文 → AI 澄清 → 部分执行 → 反馈 → 再澄清 → ...
"""

import logging
import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum

from .intent_types import Intent, IntentType
from .intent_engine import IntentEngine

logger = logging.getLogger(__name__)


class IntentClarity(Enum):
    """意图清晰度"""
    VAGUE = "vague"           # 非常模糊，无法执行
    PARTIAL = "partial"         # 部分明确，可以部分执行
    CLEAR = "clear"            # 基本明确
    CRYSTAL_CLEAR = "crystal_clear"  # 完全明确，可以完整执行


class EvolutionStatus(Enum):
    """演化状态"""
    EXPLORING = "exploring"       # 探索上下文中
    CLARIFYING = "clarifying"     # AI 正在澄清
    PARTIALLY_EXECUTING = "partially_executing"  # 部分执行中
    AWAITING_FEEDBACK = "awaiting_feedback"  # 等待执行反馈
    CONVERGED = "converged"     # 意图已收敛
    FAILED = "failed"            # 演化失败


@dataclass
class ClarificationStep:
    """澄清步骤"""
    step_id: str
    timestamp: float
    trigger: str                     # 触发原因（如 "user_input", "execution_feedback"）
    vague_intent: str                # 当时的模糊意图
    context_gathered: Dict[str, Any]  # 收集到的上下文
    clarified_intent: str            # 澄清后的意图描述
    confidence: float = 0.0
    can_execute_partial: bool = False
    partial_result: Optional[str] = None


@dataclass
class IntentGraph:
    """意图演化图

    记录意图从模糊到清晰的完整演化过程。
    """
    root_intent: str                          # 初始模糊意图
    steps: List[ClarificationStep] = field(default_factory=list)
    current_clarity: IntentClarity = IntentClarity.VAGUE
    status: EvolutionStatus = EvolutionStatus.EXPLORING
    final_intent: Optional[Intent] = None     # 最终结构化意图

    def add_step(self, step: ClarificationStep):
        self.steps.append(step)

    def get_latest_intent(self) -> Optional[str]:
        if not self.steps:
            return self.root_intent
        return self.steps[-1].clarified_intent

    def get_context(self) -> Dict[str, Any]:
        """合并所有步骤的上下文"""
        merged = {}
        for step in self.steps:
            merged.update(step.context_gathered)
        return merged

    def is_converged(self) -> bool:
        return self.status == EvolutionStatus.CONVERGED


class IntentEvolutionEngine:
    """意图演化引擎

    让模糊意图逐步演化成可执行的结构化意图。

    用法：
        engine = IntentEvolutionEngine()
        result = await engine.evolve("整理一下这个项目")
        print(result.final_intent)  # 结构化 Intent 对象
    """

    def __init__(
        self,
        max_iterations: int = 5,
        clarity_threshold: float = 0.8,
        project_root: Optional[str] = None,
    ):
        """
        Args:
            max_iterations: 最大演化迭代次数
            clarity_threshold: 清晰度阈值（达到后停止演化）
            project_root: 项目根目录（用于探索上下文）
        """
        self.max_iterations = max_iterations
        self.clarity_threshold = clarity_threshold
        self.project_root = project_root
        self._intent_engine = IntentEngine()

    async def evolve(
        self,
        vague_intent: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> "EvolutionResult":
        """演化模糊意图

        Args:
            vague_intent: 初始模糊意图（如"整理一下这个项目"）
            context: 初始上下文（可选）

        Returns:
            EvolutionResult: 演化结果（含最终意图 + 演化过程）
        """
        intent_graph = IntentGraph(
            root_intent=vague_intent,
            status=EvolutionStatus.EXPLORING,
            current_clarity=IntentClarity.VAGUE,
        )

        for iteration in range(self.max_iterations):
            logger.info(f"[IntentEvolution] 迭代 {iteration + 1}/{self.max_iterations}")

            # 1. 探索上下文（如果是前几轮）
            if iteration == 0 or intent_graph.status == EvolutionStatus.AWAITING_FEEDBACK:
                context_new = await self._explore_context(intent_graph)
                intent_graph = self._merge_context(intent_graph, context_new)

            # 2. AI 澄清意图
            clarified = await self._ai_clarify(intent_graph        )
            step = ClarificationStep(
                step_id=f"step_{iteration}",
                timestamp=time.time(),
                trigger="execution_feedback" if iteration > 0 else "user_input",
                vague_intent=intent_graph.get_latest_intent() or vague_intent,
                context_gathered=intent_graph.get_context(),
                clarified_intent=clarified["clarified_intent"],
                confidence=clarified.get("confidence", 0.5),
                can_execute_partial=clarified.get("can_execute_partial", False),
            )
            intent_graph.add_step(step)

            # 3. 评估清晰度
            clarity = self._assess_clarity(step.clarified_intent, intent_graph.get_context())
            intent_graph.current_clarity = clarity

            logger.info(f"[IntentEvolution] 当前清晰度: {clarity.value}, 置信度: {step.confidence:.2f}")

            # 4. 如果足够清晰，尝试结构化
            if clarity in (IntentClarity.CLEAR, IntentClarity.CRYSTAL_CLEAR):
                try:
                    structured = self._intent_engine.parse(step.clarified_intent)
                    intent_graph.final_intent = structured

                    # 如果能完整执行，收敛
                    if clarity == IntentClarity.CRYSTAL_CLEAR or step.confidence >= self.clarity_threshold:
                        intent_graph.status = EvolutionStatus.CONVERGED
                        logger.info(f"[IntentEvolution] 意图已收敛: {structured.get_summary()}")
                        break
                except Exception as e:
                    logger.warning(f"[IntentEvolution] 结构化失败，继续演化: {e}")

            # 5. 部分执行（如果可以）
            if step.can_execute_partial and intent_graph.status != EvolutionStatus.CONVERGED:
                partial_result = await self._execute_partial(step.clarified_intent, intent_graph)
                step.partial_result = partial_result
                intent_graph.status = EvolutionStatus.AWAITING_FEEDBACK
                logger.info(f"[IntentEvolution] 部分执行完成，等待反馈")

        # 构建结果
        return EvolutionResult(
            success=intent_graph.status == EvolutionStatus.CONVERGED,
            intent_graph=intent_graph,
            final_intent=intent_graph.final_intent,
            iterations=len(intent_graph.steps),
            clarity=intent_graph.current_clarity,
            evolution_history=[s.clarified_intent for s in intent_graph.steps],
        )

    async def _explore_context(self, graph: IntentGraph) -> Dict[str, Any]:
        """探索上下文

        基于当前意图，自动探索相关上下文：
        - 项目结构（如果是项目相关意图）
        - 文件内容（如果意图涉及特定文件）
        - 现有代码（如果意图涉及修改）
        """
        context = {}
        current_intent = graph.get_latest_intent() or graph.root_intent
        intent_lower = current_intent.lower()

        # 探索项目结构
        if any(w in intent_lower for w in ["项目", "代码", "文件", "目录", "project", "code", "file"]):
            if self.project_root:
                context["project_structure"] = await self._get_project_structure()
                context["file_types"] = await self._get_file_type_summary()

        # 探索特定文件类型
        if "图片" in intent_lower or "image" in intent_lower:
            context["images"] = await self._find_files_by_pattern("*.png", "*.jpg", "*.jpeg", "*.gif")
        if "文档" in intent_lower or "doc" in intent_lower:
            context["documents"] = await self._find_files_by_pattern("*.md", "*.txt", "*.pdf")
        if "测试" in intent_lower or "test" in intent_lower:
            context["tests"] = await self._find_files_by_pattern("*test*.py", "*_test.py")

        return context

    async def _get_project_structure(self) -> str:
        """获取项目目录结构（简化版）"""
        import os
        if not self.project_root or not os.path.isdir(self.project_root):
            return ""
        lines = []
        for root, dirs, files in os.walk(self.project_root):
            depth = root.replace(self.project_root, "").count(os.sep)
            if depth > 2:
                continue
            indent = "  " * depth
            lines.append(f"{indent}{os.path.basename(root)}/")
            sub_indent = "  " * (depth + 1)
            for f in sorted(files)[:10]:  # 每个目录最多10个文件
                lines.append(f"{sub_indent}{f}")
        return "\n".join(lines)

    async def _get_file_type_summary(self) -> Dict[str, int]:
        """统计项目中的文件类型"""
        import os
        from collections import Counter
        if not self.project_root or not os.path.isdir(self.project_root):
            return {}
        counter: Counter = Counter()
        for root, _, files in os.walk(self.project_root):
            for f in files:
                ext = os.path.splitext(f)[1].lower() or "no_ext"
                counter[ext] += 1
        return dict(counter.most_common(10))

    async def _find_files_by_pattern(self, *patterns) -> List[str]:
        """按模式查找文件"""
        import glob
        import os
        if not self.project_root:
            return []
        results = []
        for pattern in patterns:
            path = os.path.join(self.project_root, "**", pattern)
            results.extend(glob.glob(path, recursive=True))
        return results[:20]  # 最多返回20个

    async def _ai_clarify(self, graph: IntentGraph) -> Dict[str, Any]:
        """用 AI 澄清意图

        将当前模糊意图 + 已收集的上下文 发送给 AI，
        让 AI 输出澄清后的意图。
        """
        from client.src.business.ollama_client import OllamaClient, OllamaConfig

        current_intent = graph.get_latest_intent() or graph.root_intent
        context = graph.get_context()

        # 构建提示词
        prompt = self._build_clarification_prompt(current_intent, context, graph)

        try:
            from client.src.business.ollama_client import OllamaClient, OllamaConfig
            config = OllamaConfig()
            client = OllamaClient(config)
            response = client.generate(prompt, config)

            # 解析 AI 响应
            return self._parse_clarification_response(response)
        except Exception as e:
            logger.error(f"[IntentEvolution] AI 澄清失败: {e}")
            # 降级：返回原始意图
            return {
                "clarified_intent": current_intent,
                "confidence": 0.3,
                "can_execute_partial": False,
                "reasoning": f"AI 调用失败: {e}",
            }

    def _build_clarification_prompt(
        self, vague_intent: str, context: Dict[str, Any], graph: IntentGraph,
    ) -> str:
        """构建澄清提示词"""
        sections = [
            "你是一个意图澄清助手。用户给出了一个模糊的请求，请基于上下文将其澄清为具体可执行的意图。",
            "",
            f"## 用户原始请求\n{vague_intent}",
        ]

        if context:
            sections.append("")
            sections.append("## 已收集的上下文")
            for key, value in context.items():
                if isinstance(value, str) and len(value) > 500:
                    value = value[:500] + "..."
                sections.append(f"- {key}: {value}")

        if len(graph.steps) > 0:
            sections.append("")
            sections.append("## 之前的澄清历史")
            for i, step in enumerate(graph.steps):
                sections.append(f"{i+1}. {step.clarified_intent}")

        sections.extend([
            "",
            "## 输出要求",
            "请以 JSON 格式输出：",
            "```json",
            "{",
            '  "clarified_intent": "澄清后的具体意图描述",',
            '  "confidence": 0.0-1.0,  // 对澄清结果的置信度',
            '  "can_execute_partial": true/false,  // 是否可以部分执行',
            '  "key_actions": ["动作1", "动作2"],  // 关键动作列表',
            '  "missing_info": ["缺失信息1"],  // 仍缺失的信息',
            '  "reasoning": "澄清思路"',
            "}",
            "```",
        ])

        return "\n".join(sections)

    def _parse_clarification_response(self, response: str) -> Dict[str, Any]:
        """解析 AI 的澄清响应"""
        import json
        import re

        # 尝试从响应中提取 JSON
        json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # 尝试直接解析整个响应
        try:
            return json.loads(response)
        except (json.JSONDecodeError, TypeError):
            pass

        # 都无法解析，从文本中提取
        return {
            "clarified_intent": response[:500],
            "confidence": 0.5,
            "can_execute_partial": False,
            "reasoning": "无法解析 AI 响应，使用原始输出",
        }

    def _assess_clarity(self, clarified_intent: str, context: Dict[str, Any]) -> IntentClarity:
        """评估意图清晰度"""
        intent_lower = clarified_intent.lower()

        # 检查是否包含具体动作
        action_words = ["创建", "修改", "删除", "查找", "生成", "create", "update", "delete", "find", "generate"]
        has_action = any(w in intent_lower for w in action_words)

        # 检查是否包含具体目标
        has_target = len(intent_lower) > 20  # 简单启发：描述越长越具体

        # 检查是否有明确范围
        has_scope = any(w in intent_lower for w in ["所有", "全部", "特定", "某个", "only", "all", "specific"])

        score = 0.0
        if has_action:
            score += 0.3
        if has_target:
            score += 0.3
        if has_scope:
            score += 0.2
        if context:
            score += 0.2 * min(len(context) / 5, 1.0)

        if score >= 0.8:
            return IntentClarity.CRYSTAL_CLEAR
        elif score >= 0.6:
            return IntentClarity.CLEAR
        elif score >= 0.3:
            return IntentClarity.PARTIAL
        else:
            return IntentClarity.VAGUE

    async def _execute_partial(self, clarified_intent: str, graph: IntentGraph) -> str:
        """执行部分意图（探索性执行）"""
        # 这里可以调用现有的执行器进行部分执行
        # 例如：列出相关文件、生成预览等
        logger.info(f"[IntentEvolution] 部分执行: {clarified_intent[:50]}...")
        return f"部分执行结果（模拟）: {clarified_intent[:50]}..."

    def _merge_context(self, graph: IntentGraph, new_context: Dict[str, Any]) -> IntentGraph:
        """合并新上下文到意图图"""
        if graph.steps:
            graph.steps[-1].context_gathered.update(new_context)
        return graph


@dataclass
class EvolutionResult:
    """演化结果"""
    success: bool
    intent_graph: IntentGraph
    final_intent: Optional[Intent] = None
    iterations: int = 0
    clarity: IntentClarity = IntentClarity.VAGUE
    evolution_history: List[str] = None
    error: Optional[str] = None

    def __post_init__(self):
        if self.evolution_history is None:
            self.evolution_history = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "final_intent": self.final_intent.to_dict() if self.final_intent else None,
            "iterations": self.iterations,
            "clarity": self.clarity.value,
            "evolution_history": self.evolution_history,
            "error": self.error,
        }
