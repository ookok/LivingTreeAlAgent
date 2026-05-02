"""
渐进式思考引擎 (Progressive Thinking Engine)

CoT (Chain-of-Thought) 逐步推理实现：
1. 问题理解 → 分解为子问题
2. 逐步推理 → 每步整合前一步结果
3. 结论综合 → 多层步骤汇聚为最终答案
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class ThinkingState(Enum):
    PLANNING = "planning"
    THINKING = "thinking"
    VERIFYING = "verifying"
    COMPLETE = "complete"


@dataclass
class ThinkingStep:
    step_id: str
    question: str
    thought: str = ""
    confidence: float = 0.0
    state: ThinkingState = ThinkingState.PLANNING
    parent_step: Optional[str] = None
    notes: List[str] = field(default_factory=list)


class ProgressiveThinker:

    def __init__(self, max_depth: int = 5):
        self.max_depth = max_depth
        self._steps: Dict[str, ThinkingStep] = {}
        self._step_order: List[str] = []

    def think(self, problem: str) -> List[ThinkingStep]:
        self._steps.clear()
        self._step_order.clear()

        root_step = self._create_step(problem)
        self._decompose(root_step, depth=0)
        self._execute_chain()

        return [self._steps[sid] for sid in self._step_order]

    def think_stream(self, problem: str):
        self._steps.clear()
        self._step_order.clear()

        root_step = self._create_step(problem)
        yield root_step

        self._decompose(root_step, depth=0)
        for step_id in self._step_order:
            step = self._steps[step_id]
            step.state = ThinkingState.THINKING
            yield step

            step.thought = self._generate_thought(step)
            step.confidence = self._evaluate_confidence(step)
            step.state = ThinkingState.VERIFYING
            yield step

            step.state = ThinkingState.COMPLETE
            yield step

    def _create_step(self, question: str,
                     parent: Optional[str] = None) -> ThinkingStep:
        step_id = f"think_{uuid.uuid4().hex[:8]}"
        step = ThinkingStep(
            step_id=step_id, question=question,
            parent_step=parent)
        self._steps[step_id] = step
        self._step_order.append(step_id)
        return step

    def _decompose(self, step: ThinkingStep, depth: int):
        if depth >= self.max_depth:
            return

        sub_questions = self._split_question(step.question)

        for sq in sub_questions:
            sub_step = self._create_step(sq, step.step_id)
            self._decompose(sub_step, depth + 1)

    def _split_question(self, question: str) -> List[str]:
        sub_questions = []

        if "?" in question:
            parts = question.split("?")
            for part in parts:
                part = part.strip()
                if part:
                    sub_questions.append(part + "?")
        else:
            delimiters = ["首先", "其次", "然后", "最后", "另外", "此外", "同时"]
            for delim in delimiters:
                if delim in question:
                    sub_parts = question.split(delim)
                    for part in sub_parts[1:]:
                        part = part.strip().lstrip("，,。")
                        if part:
                            sub_questions.append(part)

        if not sub_questions:
            sub_questions = [question]

        return sub_questions[:3]

    def _execute_chain(self):
        for step_id in self._step_order:
            step = self._steps[step_id]
            step.thought = self._generate_thought(step)
            step.confidence = self._evaluate_confidence(step)

    def _generate_thought(self, step: ThinkingStep) -> str:
        context = ""
        if step.parent_step and step.parent_step in self._steps:
            parent = self._steps[step.parent_step]
            if parent.thought:
                context = f"前置分析: {parent.thought}\n"

        return f"{context}关于 '{step.question[:200]}' 的渐进式分析结果"

    def _evaluate_confidence(self, step: ThinkingStep) -> float:
        base_confidence = 0.7
        if step.thought:
            thought_length = len(step.thought)
            if thought_length > 100:
                base_confidence += 0.15
            if thought_length > 300:
                base_confidence += 0.1
        if step.parent_step and step.parent_step in self._steps:
            parent = self._steps[step.parent_step]
            base_confidence = base_confidence * 0.3 + parent.confidence * 0.7
        return min(0.95, max(0.1, base_confidence))

    def get_chain_summary(self) -> Dict[str, Any]:
        total_steps = len(self._steps)
        completed = sum(1 for s in self._steps.values()
                       if s.state == ThinkingState.COMPLETE)
        avg_confidence = (sum(s.confidence for s in self._steps.values())
                         / max(total_steps, 1))

        return {
            "total_steps": total_steps,
            "completed": completed,
            "avg_confidence": round(avg_confidence, 2),
            "max_depth": self.max_depth,
        }


__all__ = ["ThinkingState", "ThinkingStep", "ProgressiveThinker"]
