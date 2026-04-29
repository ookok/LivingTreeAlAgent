"""
思考引擎 - Thinking Engine

个性化思考生成器，根据人格配置和认知空间生成独特的思考内容。

思考类型：
1. 深度思考（Deep Thought）- 深入分析某个主题
2. 自由联想（Free Association）- 跨领域连接
3. 反思总结（Reflection）- 对交流内容的反思
4. 创意发散（Divergent）- 探索多种可能性
"""

import hashlib
import json
import time
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from enum import Enum

from .personality import PersonalityProfile, PersonalityDimension
from .cognition_space import CognitiveSpace


class ThoughtType(Enum):
    """思考类型"""
    DEEP_THINKING = "deep_thinking"       # 深度思考
    FREE_ASSOCIATION = "free_association" # 自由联想
    REFLECTION = "reflection"             # 反思
    DIVERGENT = "divergent"              # 创意发散
    ANALYTICAL = "analytical"            # 分析推理
    SYNTHETIC = "synthetic"              # 综合归纳


@dataclass
class Thought:
    """思考结果"""
    thought_id: str
    thinker_id: str                     # 思考者ID
    thought_type: ThoughtType

    # 内容
    content: str                         # 思考内容
    topic: str                           # 主题
    keywords: List[str] = field(default_factory=list)

    # 质量指标
    depth_score: float = 0.0             # 深度评分
    creativity_score: float = 0.0         # 创意评分
    logical_score: float = 0.0            # 逻辑评分

    # 元数据
    reasoning_chain: List[str] = field(default_factory=list)  # 推理链
    influenced_by: List[str] = field(default_factory=list)    # 受哪些思考影响

    # 时间
    created_at: float = field(default_factory=time.time)
    processing_time: float = 0.0         # 处理耗时

    def to_dict(self) -> Dict[str, Any]:
        return {
            "thought_id": self.thought_id,
            "thinker_id": self.thinker_id,
            "thought_type": self.thought_type.value,
            "content": self.content,
            "topic": self.topic,
            "keywords": self.keywords,
            "depth_score": self.depth_score,
            "creativity_score": self.creativity_score,
            "logical_score": self.logical_score,
            "reasoning_chain": self.reasoning_chain,
            "influenced_by": self.influenced_by,
            "created_at": self.created_at,
            "processing_time": self.processing_time,
        }


@dataclass
class ThinkingContext:
    """思考上下文"""
    # 输入
    input_prompt: str = ""               # 输入提示
    reference_thoughts: List[str] = field(default_factory=list)  # 参考思考ID

    # 环境
    current_topics: List[str] = field(default_factory=list)       # 当前话题
    recent_interactions: List[Dict] = field(default_factory=list)  # 最近交互

    # 目标
    target_audience: str = ""           # 目标受众
    communication_goal: str = ""         # 交流目标


class ThinkingEngine:
    """
    思考引擎

    根据人格配置和认知空间生成个性化思考。
    """

    def __init__(
        self,
        personality: PersonalityProfile,
        cognitive_space: CognitiveSpace,
        llm_client: Optional[Any] = None,  # LLM客户端
    ):
        self.personality = personality
        self.cognition = cognitive_space
        self.llm_client = llm_client

        # 思考历史
        self.thought_history: List[Thought] = []
        self.topic_thought_count: Dict[str, int] = {}

    def think(
        self,
        thought_type: ThoughtType,
        topic: str,
        context: Optional[ThinkingContext] = None,
    ) -> Thought:
        """
        执行思考

        Args:
            thought_type: 思考类型
            topic: 思考主题
            context: 思考上下文

        Returns:
            Thought: 思考结果
        """
        start_time = time.time()
        thought_id = self._generate_thought_id(topic, thought_type)

        # 激活相关认知概念
        activated = self.cognition.activate_concept(topic)
        for concept_id in activated:
            if concept_id in self.cognition.concepts:
                self.cognition.concepts[concept_id].activate()

        # 根据人格决定思考风格
        thinking_style = self.personality.get_cognitive_style()

        # 生成思考内容
        if self.llm_client:
            content = self._generate_with_llm(thought_type, topic, context)
        else:
            content = self._generate_synthetic(thought_type, topic, context)

        # 评估质量
        depth, creativity, logical = self._evaluate_thought(content, thought_type)

        thought = Thought(
            thought_id=thought_id,
            thinker_id=self.personality.profile_id,
            thought_type=thought_type,
            content=content,
            topic=topic,
            keywords=self._extract_keywords(content),
            depth_score=depth,
            creativity_score=creativity,
            logical_score=logical,
            reasoning_chain=self._build_reasoning_chain(thought_type, topic),
            influenced_by=context.reference_thoughts if context else [],
            processing_time=time.time() - start_time,
        )

        # 记录历史
        self.thought_history.append(thought)
        self.topic_thought_count[topic] = self.topic_thought_count.get(topic, 0) + 1

        return thought

    def _generate_with_llm(
        self,
        thought_type: ThoughtType,
        topic: str,
        context: Optional[ThinkingContext],
    ) -> str:
        """使用LLM生成思考"""
        # 构建提示
        style = self.personality.get_cognitive_style()
        prompt = self._build_prompt(thought_type, topic, style, context)

        # 调用LLM
        response = self.llm_client.generate(prompt)
        return response

    def _generate_synthetic(
        self,
        thought_type: ThoughtType,
        topic: str,
        context: Optional[ThinkingContext],
    ) -> str:
        """综合多个维度生成思考（无LLM时）"""
        style = self.personality.get_cognitive_style()

        # 基于思考类型生成不同风格的内容
        if thought_type == ThoughtType.DEEP_THINKING:
            return self._synthetic_deep_thinking(topic, style)
        elif thought_type == ThoughtType.FREE_ASSOCIATION:
            return self._synthetic_free_association(topic, style)
        elif thought_type == ThoughtType.DIVERGENT:
            return self._synthetic_divergent(topic, style)
        elif thought_type == ThoughtType.ANALYTICAL:
            return self._synthetic_analytical(topic, style)
        else:
            return self._synthetic_reflection(topic, style)

    def _synthetic_deep_thinking(self, topic: str, style: Dict) -> str:
        """生成深度思考"""
        depth = self.personality.get_dimension(PersonalityDimension.DEPTH)
        logical = self.personality.get_dimension(PersonalityDimension.LOGICAL)

        content = f"关于「{topic}」的深度思考：\n\n"

        if logical > 0.6:
            content += "【逻辑分析】\n"
            content += f"首先，我们需要明确「{topic}」的核心定义和边界条件。\n"
            content += "从因果关系来看，其运作机制可以分解为以下几个层次：\n"
            content += "1. 表面现象层：观察到的直接表现\n"
            content += "2. 运作机理层：背后的驱动因素\n"
            content += "3. 本质规律层：根本性的运作逻辑\n\n"

        if depth > 0.6:
            content += "【深层含义】\n"
            content += f"「{topic}」不仅仅是一个独立的现象，它折射出更深层的存在性问题。\n"
            content += "如果我们将其放在更宏观的框架中审视，会发现...\n\n"

        content += f"【综合结论】\n"
        content += f"基于以上分析，「{topic}」的核心要义在于理解其多层次结构，"
        content += f"既要见树木，也要见森林。"

        return content

    def _synthetic_free_association(self, topic: str, style: Dict) -> str:
        """生成自由联想"""
        creative = self.personality.get_dimension(PersonalityDimension.CREATIVE)
        breadth = self.personality.get_dimension(PersonalityDimension.BREADTH)

        content = f"从「{topic}」出发的自由联想：\n\n"

        # 获取激活的概念
        activated = self.cognition.get_activation_map(5)

        if creative > 0.6:
            content += "【跨界连接】\n"
            content += f"「{topic}」让我想到了艺术创作中的随机性——\n"
            content += "有时候最深刻的洞见来自于看似无关领域的碰撞。\n\n"

        if breadth > 0.6:
            domains = self.personality.expertise_domains.keys()
            content += f"【多维视角】\n"
            content += f"从{domains}的角度来看，\n"
            content += f"「{topic}」呈现出完全不同的面貌...\n\n"

        content += "【灵感捕捉】\n"
        content += "这种联想可能暂时难以形成完整的论述，但它打开了一扇新的窗口。"

        return content

    def _synthetic_divergent(self, topic: str, style: Dict) -> str:
        """生成创意发散"""
        adventurous = self.personality.get_dimension(PersonalityDimension.ADVENTUROUS)

        content = f"探索「{topic}」的多种可能性：\n\n"

        if adventurous > 0.6:
            content += "【路径A - 传统方案】\n"
            content += "最直接的做法是...\n\n"
            content += "【路径B - 激进方案】\n"
            content += "如果我们颠覆现有假设...\n\n"
            content += "【路径C - 创新方案】\n"
            content += "一个意想不到的方向是...\n\n"

        content += "【可能性评估】\n"
        content += "每条路径都有其价值和风险，关键在于选择与目标最匹配的方向。"

        return content

    def _synthetic_analytical(self, topic: str, style: Dict) -> str:
        """生成分析推理"""
        logical = self.personality.get_dimension(PersonalityDimension.LOGICAL)
        cautious = self.personality.get_dimension(PersonalityDimension.CAUTIOUS)

        content = f"「{topic}」的系统分析：\n\n"

        content += "【问题界定】\n"
        content += f"我们需要回答的核心问题是：「{topic}」的本质是什么？\n\n"

        content += "【论据收集】\n"
        content += "从已知信息来看...\n\n"

        content += "【逻辑推演】\n"
        if logical > 0.6:
            content += "基于演绎推理，我们可以得出...\n"
        content += "基于归纳推理，我们可以假设...\n\n"

        if cautious > 0.6:
            content += "【注意事项】\n"
            content += "需要警惕的陷阱是...\n"

        content += "【结论】\n"
        content += "综合以上分析，初步结论是..."

        return content

    def _synthetic_reflection(self, topic: str, style: Dict) -> str:
        """生成反思"""
        empathetic = self.personality.get_dimension(PersonalityDimension.EMPATHETIC)

        content = f"对「{topic}」的反思：\n\n"

        content += "【自我追问】\n"
        content += "为什么这个问题吸引了我？\n"
        content += "我的既有认知如何影响了我的判断？\n\n"

        if empathetic > 0.6:
            content += "【共情思考】\n"
            content += "从他人的视角来看「{topic}」，会有怎样不同的理解？\n\n"

        content += "【认知升级】\n"
        content += "通过这次思考，我对「{topic}」的理解发生了怎样的变化？"

        return content

    def _build_prompt(
        self,
        thought_type: ThoughtType,
        topic: str,
        style: Dict,
        context: Optional[ThinkingContext],
    ) -> str:
        """构建LLM提示"""
        prompt = f"你是一个具有以下认知风格的AI：\n"
        prompt += f"- 思考风格：{style.get('thinking_style', 'balanced')}\n"
        prompt += f"- 表达风格：{style.get('expression_style', 'clear')}\n"
        prompt += f"- 专长领域：{', '.join(style.get('primary_domains', []))}\n\n"

        prompt += f"请以{thought_type.value}的方式，就「{topic}」这个主题进行思考。\n"
        prompt += "要求：\n"
        prompt += "1. 体现你的独特认知风格\n"
        prompt += "2. 展现深度分析和独到见解\n"
        prompt += "3. 内容原创，有思考价值\n\n"

        if context and context.input_prompt:
            prompt += f"参考信息：{context.input_prompt}\n"

        return prompt

    def _evaluate_thought(
        self,
        content: str,
        thought_type: ThoughtType,
    ) -> Tuple[float, float, float]:
        """评估思考质量"""
        # 简单的启发式评估
        depth = min(1.0, len(content) / 500 * 0.5 + 0.3)

        # 创意评分：基于词汇多样性
        words = set(content.split())
        creativity = min(1.0, len(words) / 100 * 0.5 + 0.3)

        # 逻辑评分：基于结构化表达
        structure_markers = ["首先", "其次", "因此", "然而", "综上所述"]
        logical = min(1.0, sum(1 for m in structure_markers if m in content) / 5 * 0.6 + 0.3)

        return depth, creativity, logical

    def _extract_keywords(self, content: str) -> List[str]:
        """提取关键词"""
        # 简单提取：取最常见的实词
        words = content.split()
        word_freq = {}
        for w in words:
            if len(w) > 2:
                word_freq[w] = word_freq.get(w, 0) + 1

        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        return [w for w, _ in sorted_words[:10]]

    def _build_reasoning_chain(self, thought_type: ThoughtType, topic: str) -> List[str]:
        """构建推理链"""
        chain = []
        chain.append(f"识别主题：{topic}")
        chain.append(f"选择思考模式：{thought_type.value}")
        chain.append("激活相关认知概念")
        chain.append("应用人格特质进行思考")
        chain.append("生成思考内容")
        return chain

    def _generate_thought_id(self, topic: str, thought_type: ThoughtType) -> str:
        """生成思考ID"""
        raw = f"{self.personality.profile_id}:{topic}:{thought_type.value}:{time.time()}"
        return f"thought_{hashlib.sha256(raw.encode()).hexdigest()[:16]}"

    def get_thought_statistics(self) -> Dict[str, Any]:
        """获取思考统计"""
        if not self.thought_history:
            return {"total_thoughts": 0}

        total = len(self.thought_history)
        avg_depth = sum(t.depth_score for t in self.thought_history) / total
        avg_creativity = sum(t.creativity_score for t in self.thought_history) / total
        avg_logical = sum(t.logical_score for t in self.thought_history) / total
        total_time = sum(t.processing_time for t in self.thought_history)

        return {
            "total_thoughts": total,
            "avg_depth": avg_depth,
            "avg_creativity": avg_creativity,
            "avg_logical": avg_logical,
            "total_processing_time": total_time,
            "topic_distribution": self.topic_thought_count.copy(),
        }