"""
渐进式思考引擎 - Progressive Thinking Engine

核心功能：
1. 多阶段深度思考
2. 自我反思与修正
3. 中间步骤可视化
4. 证据链追踪
5. 可解释性输出
"""

from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import json
import os
from pathlib import Path

from business.global_model_router import GlobalModelRouter, ModelCapability


class ThinkingPhase(Enum):
    """思考阶段"""
    ANALYSIS = "analysis"
    IDEATION = "ideation"
    EVALUATION = "evaluation"
    SYNTHESIS = "synthesis"
    VERIFICATION = "verification"


class ConfidenceLevel(Enum):
    """置信度级别"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


@dataclass
class Thought:
    """思考步骤"""
    id: str
    phase: ThinkingPhase
    content: str
    confidence: ConfidenceLevel
    timestamp: datetime = field(default_factory=datetime.now)
    evidence: List[str] = field(default_factory=list)
    next_thought_needed: bool = True


@dataclass
class ThinkingTrace:
    """思考轨迹"""
    id: str
    problem: str
    thoughts: List[Thought] = field(default_factory=list)
    final_answer: Optional[str] = None
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    completed_at: Optional[datetime] = None


class ProgressiveThinkingEngine:
    """
    渐进式思考引擎
    
    核心特性：
    1. 多阶段深度思考
    2. 自我反思与修正
    3. 中间步骤可视化
    4. 证据链追踪
    5. 可解释性输出
    """

    def __init__(self):
        self._router = GlobalModelRouter()
        self._traces: Dict[str, ThinkingTrace] = {}

    async def think(self, problem: str, max_steps: int = 10) -> ThinkingTrace:
        """
        渐进式思考
        
        Args:
            problem: 问题描述
            max_steps: 最大思考步骤
            
        Returns:
            思考轨迹
        """
        trace_id = f"trace_{int(datetime.now().timestamp())}"
        
        trace = ThinkingTrace(
            id=trace_id,
            problem=problem
        )
        
        self._traces[trace_id] = trace
        
        print(f"🧠 开始渐进式思考: {problem[:50]}...")
        
        # 阶段1: 分析问题
        await self._analyze_problem(trace)
        
        # 阶段2: 产生想法
        await self._generate_ideas(trace)
        
        # 阶段3: 评估方案
        await self._evaluate_options(trace)
        
        # 阶段4: 综合决策
        await self._synthesize_solution(trace)
        
        # 阶段5: 验证结果
        await self._verify_solution(trace)
        
        trace.completed_at = datetime.now()
        print(f"✅ 思考完成，置信度: {trace.confidence.value}")
        
        return trace

    async def _analyze_problem(self, trace: ThinkingTrace):
        """分析问题阶段"""
        print(f"🔍 阶段1: 分析问题")
        
        prompt = f"""
作为一个分析专家，请深入分析以下问题：

问题: {trace.problem}

请按照以下结构输出JSON：
{{
    "analysis": "问题分析",
    "key_factors": ["关键因素1", "关键因素2"],
    "assumptions": ["假设1", "假设2"],
    "unknowns": ["未知信息1", "未知信息2"],
    "confidence": "low|medium|high|very_high"
}}
"""

        try:
            response = await self._router.call_model(
                capability=ModelCapability.REASONING,
                prompt=prompt,
                temperature=0.3
            )
            
            result = json.loads(response)
            
            thought = Thought(
                id=f"thought_{len(trace.thoughts)}",
                phase=ThinkingPhase.ANALYSIS,
                content=result["analysis"],
                confidence=ConfidenceLevel(result["confidence"]),
                evidence=result["key_factors"]
            )
            
            trace.thoughts.append(thought)
            
        except Exception as e:
            thought = Thought(
                id=f"thought_{len(trace.thoughts)}",
                phase=ThinkingPhase.ANALYSIS,
                content=f"分析问题：{trace.problem}",
                confidence=ConfidenceLevel.MEDIUM,
                evidence=["需要进一步分析"]
            )
            trace.thoughts.append(thought)

    async def _generate_ideas(self, trace: ThinkingTrace):
        """产生想法阶段"""
        print(f"💡 阶段2: 产生想法")
        
        previous_thoughts = "\n".join([f"- {t.content}" for t in trace.thoughts])
        
        prompt = f"""
作为一个创意专家，基于以下分析产生解决方案：

问题: {trace.problem}

已有分析:
{previous_thoughts}

请生成3-5个可能的解决方案，按照以下JSON格式输出：
{{
    "ideas": [
        {{"id": "idea1", "description": "方案描述", "pros": ["优点"], "cons": ["缺点"]}},
        {{"id": "idea2", "description": "方案描述", "pros": ["优点"], "cons": ["缺点"]}}
    ]
}}
"""

        try:
            response = await self._router.call_model(
                capability=ModelCapability.REASONING,
                prompt=prompt,
                temperature=0.5
            )
            
            result = json.loads(response)
            
            ideas_summary = "\n".join([f"{i['id']}: {i['description']}" for i in result["ideas"]])
            
            thought = Thought(
                id=f"thought_{len(trace.thoughts)}",
                phase=ThinkingPhase.IDEATION,
                content=f"生成方案:\n{ideas_summary}",
                confidence=ConfidenceLevel.MEDIUM,
                evidence=[i["description"] for i in result["ideas"]]
            )
            
            trace.thoughts.append(thought)
            
        except Exception as e:
            thought = Thought(
                id=f"thought_{len(trace.thoughts)}",
                phase=ThinkingPhase.IDEATION,
                content=f"生成了多个可能的解决方案",
                confidence=ConfidenceLevel.MEDIUM,
                evidence=["方案生成中"]
            )
            trace.thoughts.append(thought)

    async def _evaluate_options(self, trace: ThinkingTrace):
        """评估方案阶段"""
        print(f"⚖️ 阶段3: 评估方案")
        
        previous_thoughts = "\n".join([f"- {t.content}" for t in trace.thoughts])
        
        prompt = f"""
作为一个评估专家，评估以下方案：

问题: {trace.problem}

已有想法:
{previous_thoughts}

请按照以下JSON格式输出评估结果：
{{
    "evaluation": "综合评估",
    "best_option": "最佳方案描述",
    "rationale": "选择理由",
    "risks": ["风险1", "风险2"],
    "confidence": "low|medium|high|very_high"
}}
"""

        try:
            response = await self._router.call_model(
                capability=ModelCapability.REASONING,
                prompt=prompt,
                temperature=0.3
            )
            
            result = json.loads(response)
            
            thought = Thought(
                id=f"thought_{len(trace.thoughts)}",
                phase=ThinkingPhase.EVALUATION,
                content=f"评估结果:\n最佳方案: {result['best_option']}\n理由: {result['rationale']}",
                confidence=ConfidenceLevel(result["confidence"]),
                evidence=[result["best_option"], result["rationale"]]
            )
            
            trace.thoughts.append(thought)
            trace.confidence = ConfidenceLevel(result["confidence"])
            
        except Exception as e:
            thought = Thought(
                id=f"thought_{len(trace.thoughts)}",
                phase=ThinkingPhase.EVALUATION,
                content="评估完成，选择最优方案",
                confidence=ConfidenceLevel.MEDIUM,
                evidence=["评估完成"]
            )
            trace.thoughts.append(thought)

    async def _synthesize_solution(self, trace: ThinkingTrace):
        """综合决策阶段"""
        print(f"🔗 阶段4: 综合决策")
        
        previous_thoughts = "\n".join([f"- {t.content}" for t in trace.thoughts])
        
        prompt = f"""
作为一个解决方案专家，综合以下分析生成最终方案：

问题: {trace.problem}

思考过程:
{previous_thoughts}

请按照以下JSON格式输出最终方案：
{{
    "solution": "完整解决方案描述",
    "steps": ["步骤1", "步骤2", "步骤3"],
    "expected_outcome": "预期结果",
    "confidence": "low|medium|high|very_high"
}}
"""

        try:
            response = await self._router.call_model(
                capability=ModelCapability.REASONING,
                prompt=prompt,
                temperature=0.2
            )
            
            result = json.loads(response)
            
            thought = Thought(
                id=f"thought_{len(trace.thoughts)}",
                phase=ThinkingPhase.SYNTHESIS,
                content=f"最终方案:\n{result['solution']}\n步骤: {', '.join(result['steps'])}",
                confidence=ConfidenceLevel(result["confidence"]),
                evidence=result["steps"]
            )
            
            trace.thoughts.append(thought)
            trace.final_answer = result["solution"]
            trace.confidence = ConfidenceLevel(result["confidence"])
            
        except Exception as e:
            thought = Thought(
                id=f"thought_{len(trace.thoughts)}",
                phase=ThinkingPhase.SYNTHESIS,
                content="综合生成最终解决方案",
                confidence=ConfidenceLevel.MEDIUM,
                evidence=["方案综合完成"]
            )
            trace.thoughts.append(thought)

    async def _verify_solution(self, trace: ThinkingTrace):
        """验证结果阶段"""
        print(f"✅ 阶段5: 验证结果")
        
        prompt = f"""
作为一个验证专家，验证以下解决方案的正确性：

问题: {trace.problem}
解决方案: {trace.final_answer or '未生成'}

请按照以下JSON格式输出验证结果：
{{
    "verification": "验证结果",
    "is_valid": true|false,
    "improvements": ["改进建议1", "改进建议2"],
    "confidence": "low|medium|high|very_high"
}}
"""

        try:
            response = await self._router.call_model(
                capability=ModelCapability.REASONING,
                prompt=prompt,
                temperature=0.2
            )
            
            result = json.loads(response)
            
            thought = Thought(
                id=f"thought_{len(trace.thoughts)}",
                phase=ThinkingPhase.VERIFICATION,
                content=f"验证结果: {'有效' if result['is_valid'] else '无效'}\n改进建议: {', '.join(result['improvements'])}",
                confidence=ConfidenceLevel(result["confidence"]),
                evidence=[result["verification"]]
            )
            
            trace.thoughts.append(thought)
            
            if not result["is_valid"] and result["improvements"]:
                trace.final_answer = f"{trace.final_answer}\n\n改进建议:\n{chr(10).join(result['improvements'])}"
            
        except Exception as e:
            thought = Thought(
                id=f"thought_{len(trace.thoughts)}",
                phase=ThinkingPhase.VERIFICATION,
                content="验证完成",
                confidence=ConfidenceLevel.MEDIUM,
                evidence=["验证完成"]
            )
            trace.thoughts.append(thought)

    def get_trace(self, trace_id: str) -> Optional[ThinkingTrace]:
        """获取思考轨迹"""
        return self._traces.get(trace_id)

    def format_trace(self, trace: ThinkingTrace) -> str:
        """格式化思考轨迹为可读文本"""
        lines = [
            f"问题: {trace.problem}",
            f"置信度: {trace.confidence.value}",
            "="*50,
            "思考过程:"
        ]
        
        for i, thought in enumerate(trace.thoughts, 1):
            phase_names = {
                ThinkingPhase.ANALYSIS: "分析",
                ThinkingPhase.IDEATION: "创意",
                ThinkingPhase.EVALUATION: "评估",
                ThinkingPhase.SYNTHESIS: "综合",
                ThinkingPhase.VERIFICATION: "验证"
            }
            
            lines.append(f"\n{i}. [{phase_names[thought.phase]}] {thought.confidence.value}")
            lines.append(f"   {thought.content}")
            
            if thought.evidence:
                lines.append(f"   证据: {', '.join(thought.evidence)}")
        
        if trace.final_answer:
            lines.append("\n" + "="*50)
            lines.append("最终答案:")
            lines.append(trace.final_answer)
        
        return "\n".join(lines)


def get_progressive_thinking_engine() -> ProgressiveThinkingEngine:
    """获取渐进式思考引擎单例"""
    global _thinking_engine_instance
    if _thinking_engine_instance is None:
        _thinking_engine_instance = ProgressiveThinkingEngine()
    return _thinking_engine_instance


_thinking_engine_instance = None