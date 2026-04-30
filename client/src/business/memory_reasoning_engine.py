"""
记忆推理引擎 (Memory Reasoning Engine)
=====================================

基于记忆进行高级推理和决策：
1. 因果推理 - 从记忆中推断因果关系
2. 类比推理 - 基于相似记忆进行类比
3. 演绎推理 - 从一般到特殊的推理
4. 归纳推理 - 从特殊到一般的归纳
5. 溯因推理 - 基于证据推断最佳解释

核心特性：
- 多步推理链
- 记忆增强的推理
- 可解释的推理过程
- 置信度评估

Author: LivingTreeAlAgent Team
Date: 2026-04-30
"""

import json
import time
import asyncio
from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from uuid import uuid4

logger = __import__('logging').getLogger(__name__)


class ReasoningType(Enum):
    """推理类型"""
    CAUSAL = "causal"           # 因果推理
    ANALOGICAL = "analogical"   # 类比推理
    DEDUCTIVE = "deductive"     # 演绎推理
    INDUCTIVE = "inductive"     # 归纳推理
    ABDUCTIVE = "abductive"     # 溯因推理
    CHAINED = "chained"         # 链式推理


class ReasoningStep:
    """推理步骤"""
    def __init__(self, step_id: str, type: ReasoningType, 
                 premise: str, conclusion: str, confidence: float):
        self.step_id = step_id
        self.type = type
        self.premise = premise
        self.conclusion = conclusion
        self.confidence = confidence
        self.used_memories: List[str] = []
    
    def to_dict(self):
        return {
            "step_id": self.step_id,
            "type": self.type.value,
            "premise": self.premise,
            "conclusion": self.conclusion,
            "confidence": self.confidence,
            "used_memories": self.used_memories,
        }


@dataclass
class ReasoningResult:
    """推理结果"""
    reasoning_id: str
    query: str
    final_conclusion: str
    steps: List[ReasoningStep]
    overall_confidence: float
    execution_time: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MemoryEvidence:
    """记忆证据"""
    memory_id: str
    content: str
    relevance: float
    source: str


class MemoryReasoningEngine:
    """
    记忆推理引擎
    
    核心功能：
    1. 基于记忆进行多种类型的推理
    2. 构建推理链
    3. 评估推理置信度
    4. 提供可解释的推理过程
    """
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        # 记忆融合引擎
        self._fusion_engine = None
        
        # LLM 调用函数（用于复杂推理）
        self._llm_callable = None
        
        # 推理模板
        self._reasoning_templates = {
            ReasoningType.CAUSAL: """
分析以下事件之间的因果关系：

事件A：{event_a}
事件B：{event_b}

请判断：
1. A是否导致B？
2. B是否导致A？
3. 是否有共同原因？
4. 是否只是相关关系？

解释你的推理过程：
""",
            
            ReasoningType.ANALOGICAL: """
比较以下两个场景：

场景1：{scenario1}
场景2：{scenario2}

请找出它们之间的相似之处和不同之处，并说明可以从场景1中学到什么应用到场景2。

类比分析：
""",
            
            ReasoningType.DEDUCTIVE: """
给定以下前提：

前提1：{premise1}
前提2：{premise2}

请基于这些前提进行演绎推理，得出结论。

演绎过程：
""",
            
            ReasoningType.INDUCTIVE: """
基于以下观察：

观察1：{observation1}
观察2：{observation2}
观察3：{observation3}

请归纳出一般规律或原则。

归纳结论：
""",
            
            ReasoningType.ABDUCTIVE: """
根据以下证据：

证据1：{evidence1}
证据2：{evidence2}

请推断最可能的解释或原因。

溯因推理：
""",
        }
        
        self._initialized = True
        logger.info("[MemoryReasoningEngine] 记忆推理引擎初始化完成")
    
    def set_llm_callable(self, llm_callable: Callable[[str], str]):
        """设置 LLM 调用函数"""
        self._llm_callable = llm_callable
    
    def _get_fusion_engine(self):
        """延迟加载融合引擎"""
        if not self._fusion_engine:
            from client.src.business.memory_fusion_engine import get_memory_fusion_engine
            self._fusion_engine = get_memory_fusion_engine()
        return self._fusion_engine
    
    async def reason(self, query: str, reasoning_type: ReasoningType = None,
                    max_steps: int = 5) -> ReasoningResult:
        """
        执行记忆增强的推理
        
        Args:
            query: 用户查询
            reasoning_type: 推理类型（可选，自动检测）
            max_steps: 最大推理步数
            
        Returns:
            ReasoningResult: 推理结果
        """
        start_time = time.time()
        reasoning_id = f"reason_{uuid4().hex[:8]}"
        
        # 自动检测推理类型
        if not reasoning_type:
            reasoning_type = self._detect_reasoning_type(query)
        
        # 获取相关记忆作为证据
        evidence = await self._gather_evidence(query)
        
        # 执行推理
        steps = await self._execute_reasoning(query, reasoning_type, evidence, max_steps)
        
        # 计算总体置信度
        overall_confidence = self._calculate_overall_confidence(steps)
        
        # 生成最终结论
        final_conclusion = self._synthesize_conclusion(steps)
        
        return ReasoningResult(
            reasoning_id=reasoning_id,
            query=query,
            final_conclusion=final_conclusion,
            steps=steps,
            overall_confidence=overall_confidence,
            execution_time=time.time() - start_time,
            metadata={
                "reasoning_type": reasoning_type.value,
                "evidence_count": len(evidence),
            }
        )
    
    def _detect_reasoning_type(self, query: str) -> ReasoningType:
        """
        根据查询自动检测推理类型
        
        Args:
            query: 用户查询
            
        Returns:
            推理类型
        """
        query_lower = query.lower()
        
        # 检测因果推理关键词
        causal_keywords = ["为什么", "因为", "导致", "原因", "影响", "结果", "所以"]
        if any(kw in query_lower for kw in causal_keywords):
            return ReasoningType.CAUSAL
        
        # 检测类比推理关键词
        analogical_keywords = ["类似", "好比", "如同", "就像", "相比", "比较"]
        if any(kw in query_lower for kw in analogical_keywords):
            return ReasoningType.ANALOGICAL
        
        # 检测演绎推理关键词
        deductive_keywords = ["如果", "那么", "因此", "由此", "结论"]
        if any(kw in query_lower for kw in deductive_keywords):
            return ReasoningType.DEDUCTIVE
        
        # 检测归纳推理关键词
        inductive_keywords = ["通常", "一般", "总是", "规律", "总结"]
        if any(kw in query_lower for kw in inductive_keywords):
            return ReasoningType.INDUCTIVE
        
        # 默认使用链式推理
        return ReasoningType.CHAINED
    
    async def _gather_evidence(self, query: str) -> List[MemoryEvidence]:
        """
        从记忆中收集推理所需的证据
        
        Args:
            query: 用户查询
            
        Returns:
            记忆证据列表
        """
        evidence = []
        
        try:
            fusion_engine = self._get_fusion_engine()
            result = await fusion_engine.query(query)
            
            for source in result.sources:
                for item in source.get("items", []):
                    content = item.get("content", "")
                    if content:
                        evidence.append(MemoryEvidence(
                            memory_id=item.get("id", str(uuid4())),
                            content=content[:200],
                            relevance=item.get("relevance", 0.5),
                            source=source.get("source", "unknown")
                        ))
            
        except Exception as e:
            logger.error(f"[MemoryReasoningEngine] 收集证据失败: {e}")
        
        return evidence[:10]  # 最多使用10条证据
    
    async def _execute_reasoning(self, query: str, reasoning_type: ReasoningType,
                                evidence: List[MemoryEvidence], max_steps: int) -> List[ReasoningStep]:
        """
        执行推理过程
        
        Args:
            query: 用户查询
            reasoning_type: 推理类型
            evidence: 证据列表
            max_steps: 最大步数
            
        Returns:
            推理步骤列表
        """
        steps = []
        
        if reasoning_type == ReasoningType.CHAINED:
            # 链式推理：逐步构建推理链
            steps = await self._execute_chained_reasoning(query, evidence, max_steps)
        else:
            # 使用 LLM 进行特定类型的推理
            steps = await self._execute_specialized_reasoning(query, reasoning_type, evidence)
        
        return steps
    
    async def _execute_chained_reasoning(self, query: str, evidence: List[MemoryEvidence],
                                        max_steps: int) -> List[ReasoningStep]:
        """
        执行链式推理
        
        Args:
            query: 用户查询
            evidence: 证据列表
            max_steps: 最大步数
            
        Returns:
            推理步骤列表
        """
        steps = []
        
        # 步骤1：理解问题
        step1 = ReasoningStep(
            step_id="step_1",
            type=ReasoningType.DEDUCTIVE,
            premise=f"用户查询: {query}",
            conclusion=f"分析问题：{self._analyze_question(query)}",
            confidence=0.95
        )
        steps.append(step1)
        
        # 步骤2：收集证据
        if evidence:
            evidence_summary = "\n".join([f"- {e.content[:100]} (相关性: {e.relevance})" for e in evidence[:5]])
            step2 = ReasoningStep(
                step_id="step_2",
                type=ReasoningType.INDUCTIVE,
                premise=f"收集到 {len(evidence)} 条相关记忆",
                conclusion=f"关键证据：\n{evidence_summary}",
                confidence=0.85
            )
            step2.used_memories = [e.memory_id for e in evidence]
            steps.append(step2)
        
        # 步骤3：综合分析
        if len(steps) > 1:
            step3 = ReasoningStep(
                step_id="step_3",
                type=ReasoningType.ABDUCTIVE,
                premise=f"问题分析: {steps[0].conclusion}\n证据: {steps[1].conclusion if len(steps) > 1 else '无'}",
                conclusion=self._synthesize_analysis(query, evidence),
                confidence=0.8
            )
            steps.append(step3)
        
        return steps[:max_steps]
    
    async def _execute_specialized_reasoning(self, query: str, reasoning_type: ReasoningType,
                                            evidence: List[MemoryEvidence]) -> List[ReasoningStep]:
        """
        执行特定类型的推理（使用LLM）
        
        Args:
            query: 用户查询
            reasoning_type: 推理类型
            evidence: 证据列表
            
        Returns:
            推理步骤列表
        """
        steps = []
        
        if not self._llm_callable:
            # 没有LLM，使用简单推理
            step = ReasoningStep(
                step_id="step_1",
                type=reasoning_type,
                premise=f"查询: {query}\n证据: {[e.content[:50] for e in evidence]}",
                conclusion=f"基于记忆证据进行{reasoning_type.value}推理",
                confidence=0.6
            )
            steps.append(step)
            return steps
        
        # 使用LLM进行推理
        try:
            # 构建推理提示
            template = self._reasoning_templates.get(reasoning_type, "")
            
            # 填充模板参数
            if evidence:
                evidence_text = "\n".join([f"证据{i+1}: {e.content}" for i, e in enumerate(evidence[:3])])
            else:
                evidence_text = "暂无直接证据"
            
            prompt = f"""
推理类型: {reasoning_type.value}
用户查询: {query}
可用证据:
{evidence_text}

请按照以下格式输出推理过程：
步骤1: [推理步骤描述]
步骤2: [推理步骤描述]
...
结论: [最终结论]
"""
            
            response = self._llm_callable(prompt)
            
            # 解析响应
            lines = response.strip().split("\n")
            step_count = 0
            
            for line in lines:
                line = line.strip()
                if line.startswith("步骤"):
                    step_id = f"step_{step_count + 1}"
                    step_content = line[3:].strip()
                    step = ReasoningStep(
                        step_id=step_id,
                        type=reasoning_type,
                        premise=f"证据: {evidence_text[:100]}",
                        conclusion=step_content,
                        confidence=0.7
                    )
                    steps.append(step)
                    step_count += 1
                elif line.startswith("结论"):
                    conclusion = line[3:].strip()
                    step = ReasoningStep(
                        step_id=f"step_{step_count + 1}",
                        type=reasoning_type,
                        premise="\n".join([s.conclusion for s in steps]),
                        conclusion=conclusion,
                        confidence=0.8
                    )
                    steps.append(step)
            
        except Exception as e:
            logger.error(f"[MemoryReasoningEngine] LLM推理失败: {e}")
            step = ReasoningStep(
                step_id="step_1",
                type=reasoning_type,
                premise=f"查询: {query}",
                conclusion="推理过程出错",
                confidence=0.1
            )
            steps.append(step)
        
        return steps
    
    def _analyze_question(self, query: str) -> str:
        """分析问题类型"""
        query_lower = query.lower()
        
        if "为什么" in query_lower:
            return "这是一个原因类问题，需要找出因果关系"
        elif "如何" in query_lower:
            return "这是一个方法类问题，需要提供解决方案"
        elif "什么" in query_lower:
            return "这是一个定义类问题，需要解释概念"
        elif "是否" in query_lower:
            return "这是一个判断类问题，需要做出决策"
        else:
            return "这是一个综合性问题"
    
    def _synthesize_analysis(self, query: str, evidence: List[MemoryEvidence]) -> str:
        """综合分析证据"""
        if not evidence:
            return "没有找到相关记忆，基于通用知识回答"
        
        # 简单的综合：提取关键信息
        key_points = []
        for e in evidence:
            if e.relevance > 0.5:
                key_points.append(e.content[:100])
        
        if key_points:
            return f"基于记忆分析：\n{chr(10).join(key_points)}"
        else:
            return "记忆相关性较低，使用通用知识"
    
    def _calculate_overall_confidence(self, steps: List[ReasoningStep]) -> float:
        """计算总体置信度"""
        if not steps:
            return 0.0
        
        # 置信度 = 各步骤置信度的几何平均
        product = 1.0
        for step in steps:
            product *= step.confidence
        
        return product ** (1 / len(steps))
    
    def _synthesize_conclusion(self, steps: List[ReasoningStep]) -> str:
        """综合所有步骤生成最终结论"""
        if not steps:
            return "无法得出结论"
        
        # 使用最后一步作为结论
        last_step = steps[-1]
        return last_step.conclusion
    
    def explain_reasoning(self, result: ReasoningResult) -> str:
        """
        生成推理过程的自然语言解释
        
        Args:
            result: 推理结果
            
        Returns:
            自然语言解释
        """
        lines = []
        lines.append(f"推理ID: {result.reasoning_id}")
        lines.append(f"查询: {result.query}")
        lines.append(f"推理类型: {result.metadata.get('reasoning_type', '未知')}")
        lines.append("")
        lines.append("推理过程:")
        
        for i, step in enumerate(result.steps, 1):
            lines.append(f"{i}. [{step.type.value}] {step.conclusion} (置信度: {step.confidence:.2f})")
        
        lines.append("")
        lines.append(f"结论: {result.final_conclusion}")
        lines.append(f"总体置信度: {result.overall_confidence:.2f}")
        lines.append(f"执行时间: {result.execution_time:.2f}秒")
        
        return "\n".join(lines)


# 便捷函数
def get_reasoning_engine() -> MemoryReasoningEngine:
    """获取记忆推理引擎单例"""
    return MemoryReasoningEngine()


__all__ = [
    "ReasoningType",
    "ReasoningStep",
    "ReasoningResult",
    "MemoryEvidence",
    "MemoryReasoningEngine",
    "get_reasoning_engine",
]