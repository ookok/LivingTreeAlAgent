"""
分布式内容生成器 (Distributed Content Generator)
================================================

多节点协同创作：不同节点专精不同创作类型，竞品生成，混合编辑。

核心功能：
1. 多节点并行生成：同时调度多个 AI 节点生成多个版本
2. 智能混合编辑：选中不同版本的段落，AI 自动融合
3. 风格锚点统一：通过样本统一所有节点的输出风格
4. 上下文感知：根据选中的代码/文本自动构建提示
"""

import asyncio
import hashlib
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional


class GenerationType(Enum):
    """创作类型"""
    TEXT = "text"           # 文本创作
    CODE = "code"           # 代码生成
    IMAGE = "image"          # 图片生成
    DOCUMENT = "document"   # 文档创作
    ANALYSIS = "analysis"   # 分析报告


class ToneStyle(Enum):
    """风格选项"""
    ACADEMIC = "academic"       # 学术严谨
    CASUAL = "casual"           # 通俗易懂
    HUMOROUS = "humorous"       # 幽默风趣
    TECHNICAL = "technical"     # 技术简洁
    CREATIVE = "creative"       # 创意文学
    BUSINESS = "business"       # 商务正式


@dataclass
class NodeCapability:
    """节点能力描述"""
    node_id: str
    node_name: str
    model_type: str                    # claude/gpt/local
    supported_types: list[GenerationType]
    supported_tones: list[ToneStyle]
    latency_ms: float = 0              # 预估延迟
    cost_per_1k_tokens: float = 0      # 成本
    reputation: float = 1.0            # 信誉评分


@dataclass
class GenerationVersion:
    """生成版本"""
    version_id: str
    node_id: str
    node_name: str
    content: str
    tone: ToneStyle
    generation_type: GenerationType
    created_at: datetime
    latency_ms: float
    tokens_used: int
    metadata: dict = field(default_factory=dict)


@dataclass
class GenerationResult:
    """生成结果"""
    request_id: str
    prompt: str
    versions: list[GenerationVersion]
    best_version: Optional[GenerationVersion] = None
    created_at: datetime = field(default_factory=datetime.now)
    total_tokens: int = 0
    total_cost: float = 0

    def get_version(self, tone: ToneStyle) -> Optional[GenerationVersion]:
        """获取指定风格的版本"""
        for v in self.versions:
            if v.tone == tone:
                return v
        return None

    def merge_versions(self, selections: dict[ToneStyle, tuple[int, int]]) -> str:
        """
        混合编辑：合并不同版本的段落

        Args:
            selections: {ToneStyle: (start_paragraph, end_paragraph)}
            例如: {ToneStyle.ACADEMIC: (0, 2), ToneStyle.CASUAL: (3, 5)}

        Returns:
            融合后的文本
        """
        merged = []
        for tone, (start, end) in sorted(selections.items(), key=lambda x: x[1][0]):
            version = self.get_version(tone)
            if version:
                paragraphs = version.content.split("\n\n")
                merged.extend(paragraphs[start:end])
        return "\n\n".join(merged)


class DistributedGenerator:
    """
    分布式内容生成器

    用法:
        generator = DistributedGenerator()

        # 注册创作节点
        generator.register_node(NodeCapability(
            node_id="claude-node",
            node_name="Claude 学术节点",
            model_type="claude",
            supported_types=[GenerationType.TEXT, GenerationType.CODE],
            supported_tones=[ToneStyle.ACADEMIC, ToneStyle.TECHNICAL]
        ))

        # 并行生成多个版本
        result = await generator.generate_parallel(
            prompt="写一段关于量子计算的科普",
            generation_types=[GenerationType.TEXT],
            tones=[ToneStyle.ACADEMIC, ToneStyle.CASUAL, ToneStyle.HUMOROUS]
        )
    """

    def __init__(self, data_dir: str = "./data/creative"):
        self.data_dir = data_dir
        self.nodes: dict[str, GenerationNode] = {}
        self.history: list[GenerationResult] = []
        self._style_anchors: dict[ToneStyle, list[str]] = {tone: [] for tone in ToneStyle}

    def register_node(self, capability: NodeCapability) -> None:
        """注册一个创作节点"""
        self.nodes[capability.node_id] = GenerationNode(capability)
        print(f"[DistributedGenerator] 注册节点: {capability.node_name} ({capability.model_type})")

    def unregister_node(self, node_id: str) -> None:
        """注销节点"""
        if node_id in self.nodes:
            del self.nodes[node_id]

    def set_style_anchor(self, tone: ToneStyle, samples: list[str]) -> None:
        """
        设置风格锚点（用于统一多节点输出风格）

        Args:
            tone: 目标风格
            samples: 风格样本文本
        """
        self._style_anchors[tone].extend(samples)
        print(f"[DistributedGenerator] 设置风格锚点: {tone.value}, {len(samples)} 个样本")

    def _select_nodes_for_task(
        self,
        generation_type: GenerationType,
        tone: ToneStyle
    ) -> list[GenerationNode]:
        """为任务选择最合适的节点"""
        candidates = []
        for node in self.nodes.values():
            if (generation_type in node.capability.supported_types and
                tone in node.capability.supported_tones):
                # 计算综合评分：延迟 * 成本 * (1/信誉)
                score = (
                    node.capability.latency_ms *
                    node.capability.cost_per_1k_tokens *
                    (1 / node.capability.reputation)
                )
                candidates.append((score, node))
        # 按评分排序，选择最优节点
        candidates.sort(key=lambda x: x[0])
        return [node for _, node in candidates[:3]]  # 最多3个节点

    async def generate_parallel(
        self,
        prompt: str,
        generation_types: list[GenerationType] = None,
        tones: list[ToneStyle] = None,
        max_nodes_per_version: int = 1,
        context: dict[str, Any] = None
    ) -> GenerationResult:
        """
        并行生成多个版本

        Args:
            prompt: 创作提示
            generation_types: 创作类型列表
            tones: 风格列表（每个风格生成一个版本）
            max_nodes_per_version: 每个版本最多使用的节点数
            context: 额外上下文（代码、文档等）

        Returns:
            GenerationResult: 包含所有版本的结果
        """
        if generation_types is None:
            generation_types = [GenerationType.TEXT]
        if tones is None:
            tones = [ToneStyle.CASUAL]
        if context is None:
            context = {}

        request_id = hashlib.sha256(f"{prompt}{time.time()}".encode()).hexdigest()[:12]

        # 构建增强提示（加入风格锚点）
        enhanced_prompts = {}
        for tone in tones:
            base_prompt = prompt
            if self._style_anchors[tone]:
                anchors_text = "\n\n风格参考:\n" + "\n".join(
                    f"- {s[:100]}..." for s in self._style_anchors[tone][:3]
                )
                base_prompt += anchors_text
            enhanced_prompts[tone] = base_prompt

        # 并行调度节点生成
        tasks = []
        version_descriptions = []

        for tone in tones:
            selected_nodes = self._select_nodes_for_task(
                generation_types[0], tone
            )[:max_nodes_per_version]

            for node in selected_nodes:
                tasks.append(
                    self._generate_single(
                        request_id=request_id,
                        node=node,
                        prompt=enhanced_prompts[tone],
                        generation_type=generation_types[0],
                        tone=tone,
                        context=context
                    )
                )
                version_descriptions.append((node, tone))

        # 执行所有生成任务
        version_results = await asyncio.gather(*tasks, return_exceptions=True)

        # 收集成功的结果
        versions = []
        for i, result in enumerate(version_results):
            if isinstance(result, GenerationVersion):
                versions.append(result)
            elif isinstance(result, Exception):
                print(f"[DistributedGenerator] 版本 {i} 生成失败: {result}")

        # 选择最佳版本（基于延迟和信誉）
        best_version = None
        if versions:
            best_version = min(
                versions,
                key=lambda v: v.latency_ms * (1 / v.metadata.get("reputation", 1))
            )

        generation_result = GenerationResult(
            request_id=request_id,
            prompt=prompt,
            versions=versions,
            best_version=best_version,
                total_tokens=sum(v.tokens_used for v in versions),
            total_cost=sum(
                v.tokens_used * v.metadata.get("cost_per_1k", 0) / 1000
                for v in versions
            )
        )

        self.history.append(generation_result)
        return generation_result

    async def _generate_single(
        self,
        request_id: str,
        node: GenerationNode,
        prompt: str,
        generation_type: GenerationType,
        tone: ToneStyle,
        context: dict[str, Any]
    ) -> GenerationVersion:
        """在单个节点上生成内容"""
        start_time = time.time()

        try:
            # 调用节点的实际生成接口
            content = await node.generate(
                prompt=prompt,
                generation_type=generation_type,
                tone=tone,
                context=context
            )

            latency_ms = (time.time() - start_time) * 1000
            tokens_used = len(content) // 4  # 粗略估算

            return GenerationVersion(
                version_id=f"{request_id}-{node.capability.node_id}",
                node_id=node.capability.node_id,
                node_name=node.capability.node_name,
                content=content,
                tone=tone,
                generation_type=generation_type,
                created_at=datetime.now(),
                latency_ms=latency_ms,
                tokens_used=tokens_used,
                metadata={
                    "model_type": node.capability.model_type,
                    "reputation": node.capability.reputation,
                    "cost_per_1k": node.capability.cost_per_1k_tokens
                }
            )
        except Exception as e:
            raise Exception(f"节点 {node.capability.node_id} 生成失败: {e}")

    async def generate_with_context(
        self,
        prompt: str,
        context_content: str,
        context_type: str = "code",  # code/text/document/html
        tones: list[ToneStyle] = None
    ) -> GenerationResult:
        """
        基于上下文的生成（用于"即圈即生"功能）

        Args:
            prompt: 创作指令
            context_content: 上下文内容（选中的代码/文本）
            context_type: 上下文类型
            tones: 期望的风格列表
        """
        if tones is None:
            tones = [ToneStyle.CASUAL]

        # 构建增强提示
        context_prefix = {
            "code": "请分析和重构以下代码：\n\n",
            "text": "请参考以下文本的风格：\n\n",
            "document": "请参考以下文档：\n\n",
            "html": "请参考以下 HTML 结构：\n\n"
        }.get(context_type, "请参考以下内容：\n\n")

        enhanced_prompt = context_prefix + context_content + "\n\n" + prompt

        return await self.generate_parallel(
            prompt=enhanced_prompt,
            generation_types=[GenerationType.CODE if context_type == "code" else GenerationType.TEXT],
            tones=tones,
            context={"context_content": context_content, "context_type": context_type}
        )

    def get_generation_history(self, limit: int = 50) -> list[GenerationResult]:
        """获取生成历史"""
        return self.history[-limit:]

    def get_node_status(self) -> dict[str, dict]:
        """获取所有节点状态"""
        return {
            node_id: {
                "name": node.capability.node_name,
                "model": node.capability.model_type,
                "types": [t.value for t in node.capability.supported_types],
                "latency_ms": node.capability.latency_ms,
                "reputation": node.capability.reputation
            }
            for node_id, node in self.nodes.items()
        }


class GenerationNode:
    """创作节点"""

    def __init__(self, capability: NodeCapability):
        self.capability = capability
        self._generation_handler: Optional[Callable] = None

    def set_handler(self, handler: Callable) -> None:
        """设置生成处理器"""
        self._generation_handler = handler

    async def generate(
        self,
        prompt: str,
        generation_type: GenerationType,
        tone: ToneStyle,
        context: dict[str, Any]
    ) -> str:
        """调用节点生成内容"""
        if self._generation_handler:
            return await self._generation_handler(
                prompt=prompt,
                generation_type=generation_type,
                tone=tone,
                context=context
            )

        # 默认实现：模拟生成
        await asyncio.sleep(0.1)  # 模拟延迟
        return f"[{self.capability.node_name}] 生成内容: {prompt[:50]}..."


def create_distributed_generator(data_dir: str = "./data/creative") -> DistributedGenerator:
    """创建分布式生成器实例"""
    return DistributedGenerator(data_dir=data_dir)