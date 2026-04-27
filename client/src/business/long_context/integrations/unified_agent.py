"""
ProgressiveUnderstanding 集成层
=============================

将渐进式理解与 Agent Chat、知识库、深度搜索、技能进化深度集成。

集成架构:
┌─────────────────────────────────────────────────────────────────────────────┐
│                          UnifiedAgentSystem                                 │
│                           统一智能体系统                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐     │
│  │                     Agent Chat Layer                                │     │
│  │  EnhancedAgentChat + IntentClassifier + ChatContextManager          │     │
│  └─────────────────────────────────────────────────────────────────────┘     │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐     │
│  │                  ProgressiveUnderstanding                            │     │
│  │                  渐进式理解核心                                      │     │
│  │                                                                      │     │
│  │   Phase 1: 差异化压缩 + 语义分块 (AdaptiveCompressor + Chunker)      │     │
│  │   Phase 2: 分层混合分析 (LayeredHybridAnalyzer)                     │     │
│  │   Phase 3: 多智能体协同 (MultiAgentCoordinator)                       │     │
│  │   Phase 4: 知识积累 + 收敛检测 (KnowledgeAccumulator)                │     │
│  └─────────────────────────────────────────────────────────────────────┘     │
│                                    │                                        │
│          ┌─────────────────────────┼─────────────────────────┐            │
│          ▼                         ▼                         ▼            │
│  ┌───────────────┐     ┌───────────────┐     ┌───────────────┐            │
│  │   知识库层     │     │   深度搜索层   │     │  技能进化层    │            │
│  │ KnowledgeBase │     │ DeepSearchWiki│     │SkillEvolution │            │
│  └───────────────┘     └───────────────┘     └───────────────┘            │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

使用示例:
    from client.src.business.long_context.integrations import UnifiedAgent

    # 创建统一智能体
    agent = UnifiedAgent(depth="deep")

    # Agent Chat 风格调用
    result = await agent.chat("分析这个代码库...")

    # 渐进式理解结果
    understanding = result.understanding
    knowledge = understanding.accumulated_knowledge

    # 获取知识图谱
    graph = understanding.get_knowledge_graph()
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Awaitable
from enum import Enum

# Phase 1-4 组件
from client.src.business.long_context.progressive_understanding_impl import (
    ProgressiveUnderstanding,
    ProgressiveResult,
    UnderstandingConfig,
    UnderstandingDepth,
    ComprehensionPhase,
    ComprehensionState,
    KnowledgeAccumulator,
    KnowledgeItem,
)

# Agent Chat 组件
from client.src.business.agent_chat_enhancer import (
    EnhancedAgentChat,
    ChatIntentClassifier,
    ChatContextManager,
    IntentAnalysis,
    ChatIntent,
    IntentCategory,
    GuidanceGenerator,
)

# 知识库组件
try:
    from core.fusion_rag.knowledge_base import KnowledgeBaseLayer
    from client.src.business.knowledge_vector_db import KnowledgeBaseVectorStore
    KB_AVAILABLE = True
except ImportError:
    KB_AVAILABLE = False

# 深度搜索组件
try:
    from client.src.business.deep_search_wiki import DeepSearchWikiSystem, WikiPage
    SEARCH_AVAILABLE = True
except ImportError:
    SEARCH_AVAILABLE = False

# 技能进化组件
try:
    from client.src.business.skill_evolution import (
        SkillEvolutionAgent,
        EvolutionEngine,
        TaskContext,
        TaskStatus,
        TaskSkill,
        create_agent,
    )
    SKILL_AVAILABLE = True
except ImportError:
    SKILL_AVAILABLE = False


class IntegrationMode(Enum):
    """集成模式"""
    STANDALONE = "standalone"      # 独立模式（只用渐进式理解）
    CHAT_ENHANCED = "chat_enhanced"  # Chat 增强模式
    KNOWLEDGE_FUSED = "knowledge_fused"  # 知识融合模式
    FULL = "full"                 # 全功能模式（所有组件）


@dataclass
class IntegrationConfig:
    """集成配置"""
    # 集成模式
    mode: IntegrationMode = IntegrationMode.FULL

    # 渐进式理解配置
    understanding_depth: UnderstandingDepth = UnderstandingDepth.STANDARD
    max_iterations: int = 2
    use_compression: bool = True
    use_layered: bool = True
    use_multi_agent: bool = True

    # Agent Chat 配置
    enable_intent: bool = True
    enable_guidance: bool = True
    max_history: int = 20

    # 知识库配置
    enable_knowledge_base: bool = True
    kb_top_k: int = 10

    # 深度搜索配置
    enable_deep_search: bool = True
    search_max_results: int = 10

    # 技能进化配置
    enable_skill_evolution: bool = True
    auto_consolidate: bool = True


@dataclass
class IntegratedResult:
    """集成结果"""
    # 原始响应
    response: str

    # 渐进式理解结果
    understanding: ProgressiveResult

    # 意图分析（如果启用）
    intent: Optional[IntentAnalysis] = None

    # 知识库结果（如果启用）
    knowledge_results: List[Dict] = field(default_factory=list)

    # 深度搜索结果（如果启用）
    wiki: Optional[Any] = None

    # 执行统计
    stats: Dict[str, Any] = field(default_factory=dict)

    # 建议的追问
    suggested_questions: List[str] = field(default_factory=list)


class UnifiedAgent:
    """
    统一智能体系统

    整合渐进式理解、Agent Chat、知识库、深度搜索、技能进化

    使用方式:
        agent = UnifiedAgent(depth="deep")
        result = await agent.chat("帮我分析这个代码库")
        print(result.response)
        print(result.understanding.key_insights)
    """

    def __init__(self, config: Optional[IntegrationConfig] = None):
        self.config = config or IntegrationConfig()
        self._init_components()

    def _init_components(self):
        """初始化各组件"""
        # 1. 渐进式理解核心
        self.understander = ProgressiveUnderstanding(
            UnderstandingConfig(
                depth=self.config.understanding_depth,
                max_iterations=self.config.max_iterations,
                use_compression=self.config.use_compression,
                use_layered=self.config.use_layered,
                use_multi_agent=self.config.use_multi_agent,
            )
        )

        # 2. Agent Chat 组件
        if self.config.enable_intent or self.config.enable_guidance:
            self.intent_classifier = ChatIntentClassifier()
            self.context_manager = ChatContextManager(
                max_messages=self.config.max_history
            )
            self.guidance_generator = GuidanceGenerator()

        # 3. 知识库组件
        if self.config.enable_knowledge_base and KB_AVAILABLE:
            self.knowledge_base = KnowledgeBaseLayer()
            self.vector_kb = KnowledgeBaseVectorStore()

        # 4. 深度搜索组件
        if self.config.enable_deep_search and SEARCH_AVAILABLE:
            self.wiki_system = DeepSearchWikiSystem()

        # 5. 技能进化组件
        if self.config.enable_skill_evolution and SKILL_AVAILABLE:
            try:
                self.skill_agent = create_agent()
            except Exception as e:
                print(f"[UnifiedAgent] 技能进化初始化失败: {e}")
                self.skill_agent = None

    # ==================== 对话接口 ====================

    async def chat(self, message: str, session_id: str = "default") -> IntegratedResult:
        """
        主对话入口

        Args:
            message: 用户消息
            session_id: 会话 ID

        Returns:
            IntegratedResult: 包含所有结果的综合响应
        """
        start_time = time.time()
        stats = {}

        # 1. 意图识别（如果启用）
        intent = None
        if hasattr(self, 'intent_classifier'):
            ctx = self.context_manager.get_context(session_id) if hasattr(self, 'context_manager') else None
            intent = self.intent_classifier.classify(message, ctx)
            stats['intent'] = {
                'type': intent.intent.value,
                'confidence': intent.confidence,
                'need_knowledge': intent.need_knowledge,
                'need_deep_search': intent.need_deep_search,
            }

        # 2. 决定处理策略
        strategy = self._decide_strategy(intent)

        # 3. 根据策略执行
        if strategy == "quick":
            # 快速响应（短查询）
            response, understanding = await self._quick_response(message)
        elif strategy == "understand":
            # 渐进式理解（需要深度分析）
            response, understanding = await self._deep_understand(message)
        elif strategy == "knowledge":
            # 知识库增强
            response, understanding = await self._knowledge_augmented(message)
        elif strategy == "search":
            # 深度搜索增强
            response, understanding = await self._search_augmented(message)
        else:
            # 全功能模式
            response, understanding = await self._full_mode(message)

        # 4. 生成追问
        suggested = self._generate_guidance(message, response, intent)

        # 5. 更新上下文
        if hasattr(self, 'context_manager'):
            self.context_manager.add_message(
                session_id, 'user', message, intent.intent if intent else None
            )
            self.context_manager.add_message(session_id, 'assistant', response)

        # 6. 更新统计
        stats['duration'] = time.time() - start_time
        stats['strategy'] = strategy
        stats['phase'] = understanding.current_phase.value if understanding else "unknown"

        return IntegratedResult(
            response=response,
            understanding=understanding,
            intent=intent,
            knowledge_results=understanding.knowledge_results if understanding else [],
            wiki=understanding.wiki if understanding and hasattr(understanding, 'wiki') else None,
            stats=stats,
            suggested_questions=suggested,
        )

    def _decide_strategy(self, intent: Optional[IntentAnalysis]) -> str:
        """决定处理策略"""
        if intent is None:
            return "understand"

        # 短查询快速响应
        if len(intent.intent.value) < 50 and intent.confidence > 0.8:
            if intent.category in [IntentCategory.CONVERSATION]:
                return "quick"

        # 需要深度搜索
        if intent.need_deep_search:
            return "search"

        # 需要知识库
        if intent.need_knowledge:
            return "knowledge"

        # 代码生成、分析等需要深度理解
        if intent.category in [IntentCategory.TASK, IntentCategory.REASONING]:
            return "understand"

        return "understand"

    async def _quick_response(self, message: str) -> tuple:
        """快速响应"""
        # 不使用渐进式理解，直接返回简单响应
        understanding = ProgressiveResult(
            session_id="quick",
            current_phase=ComprehensionPhase.INITIAL,
            understanding_level=0.1,
            key_insights=[],
            knowledge_results=[],
        )
        response = f"收到: {message}"
        return response, understanding

    async def _deep_understand(self, message: str) -> tuple:
        """深度理解"""
        understanding = await self.understander.understand(
            message,
            task="深度分析"
        )

        # 生成响应
        response = self._generate_response_from_understanding(understanding)

        return response, understanding

    async def _knowledge_augmented(self, message: str) -> tuple:
        """知识库增强理解"""
        # 1. 先检索知识库
        kb_results = []
        if hasattr(self, 'knowledge_base'):
            kb_results = self.knowledge_base.search(message, top_k=self.config.kb_top_k)

        # 2. 渐进式理解（传入知识库结果）
        understanding = await self.understander.understand(
            message,
            task="结合知识库深度分析",
            initial_context={"knowledge_base": kb_results}
        )

        # 3. 生成响应
        response = self._generate_response_from_understanding(understanding, kb_results)

        return response, understanding

    async def _search_augmented(self, message: str) -> tuple:
        """深度搜索增强"""
        # 1. 提取搜索主题
        topic = self._extract_search_topic(message)

        # 2. 深度搜索
        wiki = None
        if hasattr(self, 'wiki_system') and topic:
            wiki = await self.wiki_system.generate_async(topic, use_search=True)

        # 3. 渐进式理解（传入 Wiki 结果）
        wiki_content = wiki.summary if wiki else ""
        understanding = await self.understander.understand(
            message,
            task="结合搜索结果深度分析",
            initial_context={"wiki": wiki_content, "wiki_topic": topic}
        )

        # 4. 生成响应
        response = self._generate_response_from_understanding(
            understanding,
            wiki_sections=wiki.sections if wiki else []
        )

        return response, understanding

    async def _full_mode(self, message: str) -> tuple:
        """全功能模式"""
        # 1. 并行执行知识库搜索和深度搜索
        kb_task = None
        search_task = None

        if hasattr(self, 'knowledge_base'):
            kb_task = asyncio.create_task(
                self._search_knowledge(message)
            )

        if hasattr(self, 'wiki_system'):
            topic = self._extract_search_topic(message)
            if topic:
                search_task = asyncio.create_task(
                    self.wiki_system.generate_async(topic, use_search=True)
                )

        # 2. 等待结果
        kb_results = await kb_task if kb_task else []
        wiki = await search_task if search_task else None

        # 3. 渐进式理解
        understanding = await self.understander.understand(
            message,
            task="全功能深度分析",
            initial_context={
                "knowledge_base": kb_results,
                "wiki": wiki.summary if wiki else "",
                "wiki_sections": wiki.sections if wiki else [],
            }
        )

        # 4. 生成响应
        response = self._generate_response_from_understanding(
            understanding,
            kb_results,
            wiki.sections if wiki else []
        )

        return response, understanding

    async def _search_knowledge(self, query: str) -> List[Dict]:
        """搜索知识库"""
        if hasattr(self, 'knowledge_base'):
            return self.knowledge_base.search(query, top_k=self.config.kb_top_k)
        return []

    def _extract_search_topic(self, message: str) -> Optional[str]:
        """从消息中提取搜索主题"""
        # 简单实现：取消息的前 20 个字符作为主题
        if len(message) > 20:
            # 尝试找到句子边界
            for sep in ['。', '.', '？', '?']:
                if sep in message:
                    return message[:message.index(sep)]
        return message[:30] if message else None

    def _generate_response_from_understanding(
        self,
        understanding: ProgressiveResult,
        kb_results: List[Dict] = None,
        wiki_sections: List[Any] = None,
    ) -> str:
        """从理解结果生成响应"""
        parts = []

        # 1. 核心洞察
        if understanding.key_insights:
            parts.append("## 🔍 核心洞察\n")
            for i, insight in enumerate(understanding.key_insights[:3], 1):
                parts.append(f"{i}. {insight}\n")

        # 2. 知识库结果（如果有）
        if kb_results and understanding.knowledge_results:
            parts.append("\n## 📚 相关知识\n")
            for r in understanding.knowledge_results[:3]:
                content = r.get('content', '')[:100]
                parts.append(f"- {content}...\n")

        # 3. Wiki 内容（如果有）
        if wiki_sections:
            parts.append("\n## 📖 深度分析\n")
            for section in wiki_sections[:2]:
                title = section.title if hasattr(section, 'title') else str(section)
                content = section.content if hasattr(section, 'content') else ''
                if len(content) > 200:
                    content = content[:200] + "..."
                parts.append(f"### {title}\n{content}\n")

        # 4. 理解阶段
        if understanding.current_phase:
            phase_desc = {
                ComprehensionPhase.INITIAL: "初步理解",
                ComprehensionPhase.SURFACE: "表面理解",
                ComprehensionPhase.DEEP: "深度理解",
                ComprehensionPhase.INTEGRATED: "整合理解",
                ComprehensionPhase.VALIDATED: "验证完成",
            }
            phase_name = phase_desc.get(understanding.current_phase, str(understanding.current_phase))
            parts.append(f"\n> 理解进度: {phase_name} ({understanding.understanding_level:.0%})\n")

        return "".join(parts) if parts else "已完成分析。"

    def _generate_guidance(
        self,
        message: str,
        response: str,
        intent: Optional[IntentAnalysis]
    ) -> List[str]:
        """生成追问建议"""
        if not hasattr(self, 'guidance_generator') or not intent:
            return []

        ctx = None
        if hasattr(self, 'context_manager'):
            ctx = self.context_manager.get_context("default")

        guidance = self.guidance_generator.generate(
            intent=intent.intent,
            response=response,
            context=ctx,
            user_message=message,
        )

        return guidance.questions[:3]

    # ==================== 知识管理 ====================

    def get_knowledge_graph(self, session_id: str = "default") -> Optional[Dict]:
        """获取知识图谱"""
        return self.understander.get_knowledge_graph(session_id)

    def get_session_status(self, session_id: str = "default") -> Dict:
        """获取会话状态"""
        return self.understander.get_session_status(session_id)

    def get_accumulated_knowledge(self, session_id: str = "default") -> List[KnowledgeItem]:
        """获取积累的知识"""
        if hasattr(self.understander, '_sessions'):
            session = self.understander._sessions.get(session_id)
            if session:
                return list(session.context.knowledge_base.values())
        return []

    # ==================== 技能进化 ====================

    async def evolve_skill(
        self,
        task_description: str,
        execution_result: Any
    ) -> Optional[TaskSkill]:
        """将成功的执行固化为技能"""
        if not hasattr(self, 'skill_agent') or not self.skill_agent:
            return None

        try:
            task_context = self.skill_agent.execute_task(
                task_description=task_description,
                task_type="evolved_skill",
            )

            if task_context.status == TaskStatus.COMPLETED:
                # 触发技能固化
                if hasattr(self.skill_agent, '_try_consolidate'):
                    self.skill_agent._try_consolidate()
                    return task_context.skill_id

            return None
        except Exception as e:
            print(f"[UnifiedAgent] 技能进化失败: {e}")
            return None


# ==================== 便捷工厂 ====================

def create_unified_agent(
    depth: str = "standard",
    mode: str = "full"
) -> UnifiedAgent:
    """
    创建统一智能体

    Args:
        depth: 理解深度 ("quick", "standard", "deep", "comprehensive")
        mode: 集成模式 ("standalone", "chat_enhanced", "knowledge_fused", "full")

    Returns:
        UnifiedAgent 实例
    """
    depth_map = {
        "quick": UnderstandingDepth.QUICK,
        "standard": UnderstandingDepth.STANDARD,
        "deep": UnderstandingDepth.DEEP,
        "comprehensive": UnderstandingDepth.COMPREHENSIVE,
    }

    mode_map = {
        "standalone": IntegrationMode.STANDALONE,
        "chat_enhanced": IntegrationMode.CHAT_ENHANCED,
        "knowledge_fused": IntegrationMode.KNOWLEDGE_FUSED,
        "full": IntegrationMode.FULL,
    }

    config = IntegrationConfig(
        understanding_depth=depth_map.get(depth, UnderstandingDepth.STANDARD),
        mode=mode_map.get(mode, IntegrationMode.FULL),
    )

    return UnifiedAgent(config)


# ==================== 使用示例 ====================

async def example_usage():
    """使用示例"""
    print("=" * 60)
    print("UnifiedAgent 使用示例")
    print("=" * 60)

    # 1. 创建统一智能体（深度理解 + 全功能）
    agent = create_unified_agent(depth="deep", mode="full")

    # 2. Agent Chat 风格对话
    print("\n[1] 测试 Agent Chat 风格对话")
    result = await agent.chat("分析 Python 异步编程的优势和劣势")

    print(f"\n响应:\n{result.response[:500]}...")
    print(f"\n理解进度: {result.understanding.understanding_level:.0%}")
    print(f"核心洞察数: {len(result.understanding.key_insights)}")

    if result.intent:
        print(f"意图类型: {result.intent.intent.value}")
        print(f"置信度: {result.intent.confidence:.0%}")

    # 3. 追问建议
    if result.suggested_questions:
        print(f"\n追问建议:")
        for q in result.suggested_questions:
            print(f"  - {q}")

    # 4. 知识图谱
    print("\n[2] 知识图谱")
    graph = agent.get_knowledge_graph(result.understanding.session_id)
    if graph:
        print(f"  节点数: {len(graph.get('nodes', []))}")
        print(f"  边数: {len(graph.get('edges', []))}")

    # 5. 积累的知识
    print("\n[3] 积累的知识")
    knowledge = agent.get_accumulated_knowledge(result.understanding.session_id)
    print(f"  知识条目: {len(knowledge)}")
    for k in knowledge[:3]:
        print(f"  - {k.content[:50]}...")

    # 6. 执行统计
    print("\n[4] 执行统计")
    print(f"  策略: {result.stats.get('strategy')}")
    print(f"  耗时: {result.stats.get('duration', 0):.2f}s")
    print(f"  理解阶段: {result.stats.get('phase')}")


if __name__ == "__main__":
    asyncio.run(example_usage())
