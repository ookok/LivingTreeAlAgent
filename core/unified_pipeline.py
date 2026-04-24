# -*- coding: utf-8 -*-
"""
统一处理流水线 - Unified Processing Pipeline
==============================================

职责：
1. 接收用户 Query
2. 执行 L0 意图分类
3. 执行 L1-L2 检索路由
4. 执行 L3-L4 深度生成
5. 结果缓存与技能固化

复用模块：
- QueryIntentClassifier (意图分类)
- IntelligentRouter (智能路由)
- UnifiedCache (统一缓存)
- KnowledgeBaseLayer (知识库)
- DeepSearchWikiSystem (深度搜索)
- SkillEvolutionAgent (技能固化)

Author: Hermes Desktop Team
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Iterator

logger = logging.getLogger(__name__)


# ── 枚举定义 ────────────────────────────────────────────────────────────────


class IntentType(Enum):
    """意图类型枚举"""
    FACTUAL = "factual"                    # 事实查询
    CONVERSATIONAL = "conversational"      # 对话类
    PROCEDURAL = "procedural"              # 流程/代码类
    CREATIVE = "creative"                  # 创意类
    TASK = "task"                          # 任务执行
    WRITING = "writing"                    # 写作类
    UNKNOWN = "unknown"                    # 未知


# ── 数据结构 ────────────────────────────────────────────────────────────────


@dataclass
class PipelineContext:
    """
    流水线上下文
    
    用于在流水线各步骤间传递数据和状态
    """
    # 输入
    user_id: str = ""
    session_id: str = ""
    query: str = ""
    
    # 中间结果
    intent: IntentType = IntentType.UNKNOWN
    raw_intent: str = ""
    route_decision: Dict[str, Any] = field(default_factory=dict)
    retrieved_context: List[Any] = field(default_factory=list)
    
    # 输出
    response: str = ""
    sources: List[Any] = field(default_factory=list)
    confidence: float = 0.0
    
    # 需求澄清
    needs_clarification: bool = False
    clarification_prompt: str = ""
    
    # 执行追踪
    execution_trace: List[Dict[str, Any]] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)
    
    # 缓存
    cache_hit: bool = False
    
    def add_trace(self, stage: str, detail: str, duration: float = 0):
        """添加执行追踪"""
        self.execution_trace.append({
            "stage": stage,
            "detail": detail,
            "duration": duration,
            "timestamp": time.time() - self.start_time
        })
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "user_id": self.user_id,
            "session_id": self.session_id,
            "query": self.query[:100] + "..." if len(self.query) > 100 else self.query,
            "intent": self.intent.value,
            "needs_clarification": self.needs_clarification,
            "response_length": len(self.response),
            "confidence": self.confidence,
            "cache_hit": self.cache_hit,
            "trace_count": len(self.execution_trace)
        }


# ── 统一流水线 ───────────────────────────────────────────────────────────────


class UnifiedPipeline:
    """
    统一处理流水线

    7 步处理流程：
    1. Clarification - 需求澄清检查
    2. Intent Classify - L0 意图分类
    3. Cache Lookup - 缓存查询
    4. Route & Retrieve - L1-L2 路由与检索
    5. Deep Generate - L3-L4 深度生成
    6. Cache Write - 结果缓存
    7. Skill Consolidate - 技能固化

    使用示例：
    ```python
    pipeline = UnifiedPipeline()

    # 同步调用
    result = pipeline.process(
        user_id="user_001",
        query="帮我分析一下 Python 的异步编程"
    )

    # 流式调用
    for chunk in pipeline.process_stream(query):
        print(chunk, end="", flush=True)
    ```
    """

    def __init__(
        self,
        ollama_url: Optional[str] = None,
        embed_model: Optional[str] = None,
        l0_model: Optional[str] = None,
        l3_model: Optional[str] = None,
        l4_model: Optional[str] = None,
        **kwargs
    ):
        # 从配置模块获取默认值
        from core.config_provider import (
            get_ollama_url, get_l0_model, get_l3_model,
            get_l4_model, get_embedding_model
        )

        self._init_config(
            ollama_url=ollama_url or get_ollama_url(),
            embed_model=embed_model or get_embedding_model(),
            l0_model=l0_model or get_l0_model(),
            l3_model=l3_model or get_l3_model(),
            l4_model=l4_model or get_l4_model()
        )

        # 组件延迟初始化
        self._intent_classifier = None
        self._router = None
        self._knowledge_base = None
        self._unified_cache = None
        self._wiki_generator = None
        self._skill_agent = None
        self._clarifier = None
        self._memory_palace = None
        self._ollama_client = None

        logger.info(f"UnifiedPipeline 初始化完成 (ollama_url={self.ollama_url})")

    def _init_config(self, **kwargs):
        """初始化配置"""
        from core.config_provider import get_default_model
        self.ollama_url = kwargs.get("ollama_url", get_ollama_url())
        self.embed_model = kwargs.get("embed_model", "nomic-embed-text")
        self.l0_model = kwargs.get("l0_model", get_default_model("l0"))
        self.l3_model = kwargs.get("l3_model", get_default_model("l3"))
        self.l4_model = kwargs.get("l4_model", get_default_model("l4"))
        self.compress_model = kwargs.get("compress_model", get_default_model("l1"))
    
    # ── 属性懒加载 ──────────────────────────────────────────────────────────
    
    @property
    def intent_classifier(self):
        """L0 意图分类器"""
        if self._intent_classifier is None:
            from core.fusion_rag.intent_classifier import QueryIntentClassifier
            self._intent_classifier = QueryIntentClassifier()
        return self._intent_classifier
    
    @property
    def router(self):
        """智能路由器"""
        if self._router is None:
            from core.fusion_rag.intelligent_router import IntelligentRouter
            self._router = IntelligentRouter()
        return self._router
    
    @property
    def knowledge_base(self):
        """知识库"""
        if self._knowledge_base is None:
            from core.fusion_rag.knowledge_base import KnowledgeBaseLayer
            self._knowledge_base = KnowledgeBaseLayer()
        return self._knowledge_base
    
    @property
    def unified_cache(self):
        """统一缓存"""
        if self._unified_cache is None:
            from unified_cache import UnifiedCache
            self._unified_cache = UnifiedCache()
        return self._unified_cache
    
    @property
    def wiki_generator(self):
        """Wiki 生成器"""
        if self._wiki_generator is None:
            from core.deep_search_wiki.wiki_generator import WikiGenerator
            self._wiki_generator = WikiGenerator()
        return self._wiki_generator
    
    @property
    def skill_agent(self):
        """技能进化 Agent"""
        if self._skill_agent is None:
            from core.skill_evolution.agent_loop import SkillEvolutionAgent
            self._skill_agent = SkillEvolutionAgent()
        return self._skill_agent
    
    @property
    def clarifier(self):
        """需求澄清器"""
        if self._clarifier is None:
            from core.conversational_clarifier import ConversationalClarifier
            self._clarifier = ConversationalClarifier()
        return self._clarifier
    
    @property
    def memory_palace(self):
        """记忆宫殿"""
        if self._memory_palace is None:
            from core.memory_palace.models import MemoryPalace
            self._memory_palace = MemoryPalace()
        return self._memory_palace
    
    @property
    def ollama_client(self):
        """Ollama 客户端"""
        if self._ollama_client is None:
            from core.ollama_client import OllamaClient
            self._ollama_client = OllamaClient(base_url=self.ollama_url)
        return self._ollama_client
    
    # ── 核心处理流程 ────────────────────────────────────────────────────────
    
    def process(
        self,
        user_id: str,
        query: str,
        session_id: str = "",
        use_cache: bool = True,
        enable_skill: bool = True,
        enable_clarification: bool = True
    ) -> PipelineContext:
        """
        处理用户请求（同步版本）
        
        Args:
            user_id: 用户 ID
            query: 用户查询
            session_id: 会话 ID
            use_cache: 是否使用缓存
            enable_skill: 是否启用技能系统
            enable_clarification: 是否启用需求澄清
            
        Returns:
            PipelineContext: 处理上下文（含结果）
        """
        ctx = PipelineContext(
            user_id=user_id,
            query=query,
            session_id=session_id
        )
        
        try:
            # Step 1: 需求澄清检查
            if enable_clarification:
                self._step_clarification(ctx)
                if ctx.needs_clarification:
                    ctx.add_trace("clarification", "needs clarification, waiting")
                    return ctx
            
            # Step 2: L0 意图分类
            self._step_intent_classify(ctx)
            
            # Step 3: 缓存检查
            if use_cache:
                cached = self._step_cache_lookup(ctx)
                if cached:
                    ctx.response = cached
                    ctx.cache_hit = True
                    ctx.add_trace("cache", "hit")
                    return ctx
            
            # Step 4: L1-L2 路由与检索
            self._step_route_and_retrieve(ctx)
            
            # Step 5: L3-L4 深度生成
            self._step_deep_generate(ctx)
            
            # Step 6: 结果缓存
            if use_cache:
                self._step_cache_write(ctx)
            
            # Step 7: 技能固化（异步）
            if enable_skill and ctx.intent == IntentType.TASK:
                self._step_skill_consolidate(ctx)
            
        except Exception as e:
            logger.error(f"Pipeline 处理失败: {e}")
            ctx.response = f"处理出错: {str(e)}"
            ctx.add_trace("error", str(e))
        
        return ctx
    
    def process_stream(
        self,
        user_id: str,
        query: str,
        session_id: str = "",
        enable_clarification: bool = True
    ) -> Iterator[str]:
        """
        处理用户请求（流式版本）
        
        Yields:
            str: 生成的文本块
        """
        ctx = PipelineContext(
            user_id=user_id,
            query=query,
            session_id=session_id
        )
        
        try:
            # 前置处理
            if enable_clarification:
                self._step_clarification(ctx)
                if ctx.needs_clarification:
                    yield ctx.clarification_prompt
                    return
            
            self._step_intent_classify(ctx)
            self._step_route_and_retrieve(ctx)
            
            # 流式生成
            for chunk in self._step_deep_generate_stream(ctx):
                yield chunk
                
        except Exception as e:
            logger.error(f"Pipeline 流式处理失败: {e}")
            yield f"处理出错: {str(e)}"
    
    # ── 流水线步骤实现 ─────────────────────────────────────────────────────
    
    def _step_clarification(self, ctx: PipelineContext):
        """
        Step 1: 需求澄清检查
        
        复用 ConversationalClarifier 检测模糊需求
        """
        start = time.time()
        
        # 使用 ConversationalClarifier
        is_ambiguous = self.clarifier.should_prompt(ctx.query)
        
        if is_ambiguous:
            ctx.needs_clarification = True
            ctx.clarification_prompt = self._generate_clarification_prompt(ctx.query)
            logger.info(f"检测到模糊需求: {ctx.query[:50]}...")
        
        ctx.add_trace("clarification", f"needs={is_ambiguous}", time.time() - start)
    
    def _generate_clarification_prompt(self, query: str) -> str:
        """生成澄清提示"""
        return f"""您的需求「{query}」可能不够明确。

为了更好地帮助您，请问：
1. 具体需要什么类型的内容？（报告/代码/分析/教程等）
2. 有什么具体的要求或限制？
3. 希望达到什么效果？

请补充说明，我会为您生成更准确的结果。"""
    
    def _step_intent_classify(self, ctx: PipelineContext):
        """
        Step 2: L0 意图分类
        
        复用 QueryIntentClassifier
        """
        start = time.time()
        
        try:
            # 使用 QueryIntentClassifier
            raw_intent = self.intent_classifier.classify(ctx.query)
            ctx.raw_intent = raw_intent
            
            # 映射到 IntentType
            ctx.intent = self._map_intent(raw_intent)
            
        except Exception as e:
            logger.warning(f"意图分类失败: {e}，使用默认 UNKNOWN")
            ctx.intent = IntentType.UNKNOWN
            ctx.raw_intent = "unknown"
        
        ctx.add_trace("intent", f"{ctx.intent.value} ({ctx.raw_intent})", time.time() - start)
        logger.debug(f"意图分类: {ctx.intent.value}")
    
    def _map_intent(self, raw_intent: str) -> IntentType:
        """映射原始意图到 IntentType"""
        raw = raw_intent.lower().strip()
        
        mapping = {
            "factual": IntentType.FACTUAL,
            "fact": IntentType.FACTUAL,
            "query": IntentType.FACTUAL,
            "search": IntentType.FACTUAL,
            "conversational": IntentType.CONVERSATIONAL,
            "chat": IntentType.CONVERSATIONAL,
            "dialog": IntentType.CONVERSATIONAL,
            "procedural": IntentType.PROCEDURAL,
            "code": IntentType.PROCEDURAL,
            "task": IntentType.TASK,
            "execute": IntentType.TASK,
            "creative": IntentType.CREATIVE,
            "generate": IntentType.CREATIVE,
            "writing": IntentType.WRITING,
            "write": IntentType.WRITING,
        }
        
        return mapping.get(raw, IntentType.UNKNOWN)
    
    def _step_cache_lookup(self, ctx: PipelineContext) -> Optional[str]:
        """
        Step 3: 缓存查询
        
        复用 UnifiedCache
        """
        start = time.time()
        
        try:
            cached = self.unified_cache.get(
                query=ctx.query,
                user_id=ctx.user_id
            )
            ctx.add_trace("cache_lookup", f"hit={cached is not None}", time.time() - start)
            return cached
        except Exception as e:
            logger.warning(f"缓存查询失败: {e}")
            ctx.add_trace("cache_lookup", "error", time.time() - start)
            return None
    
    def _step_route_and_retrieve(self, ctx: PipelineContext):
        """
        Step 4: L1-L2 路由与检索
        
        复用 IntelligentRouter + KnowledgeBaseLayer
        """
        start = time.time()
        
        try:
            # 使用 IntelligentRouter
            ctx.route_decision = self.router.route(
                query=ctx.query,
                intent=ctx.intent.value
            )
            
            # 根据路由决策执行检索
            if ctx.route_decision.get("use_knowledge_base", True):
                top_k = ctx.route_decision.get("top_k", 5)
                ctx.retrieved_context = self.knowledge_base.search(
                    query=ctx.query,
                    top_k=top_k
                )
            
            ctx.add_trace(
                "route_retrieve",
                f"sources={len(ctx.retrieved_context)}, route={ctx.route_decision.get('route_type', 'unknown')}",
                time.time() - start
            )
            
        except Exception as e:
            logger.warning(f"路由检索失败: {e}")
            ctx.add_trace("route_retrieve", "error", time.time() - start)
    
    def _step_deep_generate(self, ctx: PipelineContext):
        """
        Step 5: L3-L4 深度生成（同步）
        
        根据意图选择生成策略
        """
        start = time.time()
        
        try:
            if ctx.intent == IntentType.FACTUAL and len(ctx.retrieved_context) > 0:
                # 有检索结果 → 基于上下文生成
                ctx.response = self._generate_with_context(ctx)
                
            elif ctx.intent in [IntentType.CREATIVE, IntentType.WRITING]:
                # 需要深度生成 → 使用 WikiGenerator
                wiki_page = self.wiki_generator.generate(
                    topic=ctx.query,
                    search_results=ctx.retrieved_context,
                    use_search=True
                )
                ctx.response = self._format_wiki_response(wiki_page)
                ctx.sources = wiki_page.sources
                ctx.confidence = wiki_page.confidence
                
            elif ctx.intent == IntentType.TASK:
                # 任务执行 → 调用技能系统
                ctx.response = self._generate_task_response(ctx)
                
            else:
                # 默认 → 直接 LLM 生成
                ctx.response = self._generate_direct(ctx)
            
            ctx.add_trace("generate", f"length={len(ctx.response)}", time.time() - start)
            
        except Exception as e:
            logger.error(f"深度生成失败: {e}")
            ctx.response = f"生成失败: {str(e)}"
            ctx.add_trace("generate", "error", time.time() - start)
    
    def _step_deep_generate_stream(self, ctx: PipelineContext) -> Iterator[str]:
        """
        Step 5: L3-L4 深度生成（流式）
        
        TODO: 实现流式生成
        """
        # 目前使用同步版本作为 fallback
        self._step_deep_generate(ctx)
        yield ctx.response
    
    def _step_cache_write(self, ctx: PipelineContext):
        """
        Step 6: 结果缓存
        
        复用 UnifiedCache
        """
        start = time.time()
        
        try:
            self.unified_cache.set(
                query=ctx.query,
                response=ctx.response,
                user_id=ctx.user_id
            )
            ctx.add_trace("cache_write", "success", time.time() - start)
        except Exception as e:
            logger.warning(f"缓存写入失败: {e}")
            ctx.add_trace("cache_write", "error", time.time() - start)
    
    def _step_skill_consolidate(self, ctx: PipelineContext):
        """
        Step 7: 技能固化（异步）
        
        复用 SkillEvolutionAgent
        """
        start = time.time()
        
        try:
            # 异步执行，不阻塞主流程
            # 使用 SkillEvolutionAgent 的 execute_task
            self.skill_agent.execute_task(
                task_description=ctx.query,
                context=ctx.retrieved_context
            )
            ctx.add_trace("skill", "consolidate triggered", time.time() - start)
        except Exception as e:
            logger.warning(f"技能固化失败: {e}")
            ctx.add_trace("skill", "error", time.time() - start)
    
    # ── 辅助方法 ───────────────────────────────────────────────────────────
    
    def _generate_with_context(self, ctx: PipelineContext) -> str:
        """基于检索上下文生成回答"""
        # 构建上下文提示
        if not ctx.retrieved_context:
            return self._generate_direct(ctx)
        
        context_parts = []
        for i, item in enumerate(ctx.retrieved_context):
            if isinstance(item, dict):
                content = item.get("content", str(item))
            else:
                content = str(item)
            context_parts.append(f"[{i+1}] {content[:200]}")
        
        context_text = "\n".join(context_parts)
        
        prompt = f"""基于以下参考资料回答问题。如果没有足够信息，请如实说明。

参考资料：
{context_text}

问题：{ctx.query}

要求：
1. 基于资料准确回答
2. 如资料不足，说明不知道
3. 简洁明了

回答："""
        
        return self._call_llm(prompt, model=self.l4_model)
    
    def _generate_direct(self, ctx: PipelineContext) -> str:
        """直接生成回答"""
        prompt = f"问题：{ctx.query}\n\n请简洁准确地回答："
        return self._call_llm(prompt, model=self.l3_model)
    
    def _generate_task_response(self, ctx: PipelineContext) -> str:
        """生成任务执行响应"""
        prompt = f"""分析以下任务，分解执行步骤：

任务：{ctx.query}

请：
1. 分析任务类型和目标
2. 列出执行步骤
3. 说明可能需要的工具或资源

回答："""
        
        return self._call_llm(prompt, model=self.l3_model)
    
    def _format_wiki_response(self, wiki_page) -> str:
        """格式化 Wiki 页面响应"""
        parts = []
        
        # 标题
        parts.append(f"# {wiki_page.topic}\n")
        
        # 摘要
        if wiki_page.summary:
            parts.append(f"## 概述\n{wiki_page.summary}\n")
        
        # 章节
        for section in wiki_page.sections:
            parts.append(f"## {section.title}\n{section.content}\n")
        
        # 来源
        if wiki_page.sources:
            parts.append("\n## 参考来源\n")
            for src in wiki_page.sources[:5]:
                parts.append(f"- {src.title}: {src.url}\n")
        
        return "\n".join(parts)
    
    def _call_llm(
        self,
        prompt: str,
        model: str = None,
        stream: bool = False
    ) -> str:
        """调用 LLM"""
        model = model or self.l4_model
        
        try:
            response = self.ollama_client.generate(
                prompt=prompt,
                model=model,
                stream=stream
            )
            
            if isinstance(response, dict):
                return response.get("response", "")
            return str(response)
            
        except Exception as e:
            logger.error(f"LLM 调用失败: {e}")
            return f"抱歉，生成失败: {str(e)}"
    
    # ── 工具方法 ───────────────────────────────────────────────────────────
    
    def get_execution_trace(self, ctx: PipelineContext) -> str:
        """获取执行追踪报告"""
        lines = ["执行追踪报告:", "-" * 40]
        
        for trace in ctx.execution_trace:
            lines.append(
                f"[{trace['stage']}] {trace['detail']} "
                f"({trace['duration']:.3f}s @ {trace['timestamp']:.2f}s)"
            )
        
        return "\n".join(lines)


# ── 单例模式 ────────────────────────────────────────────────────────────────


_pipeline_instance: Optional[UnifiedPipeline] = None


def get_pipeline() -> UnifiedPipeline:
    """获取流水线单例"""
    global _pipeline_instance
    if _pipeline_instance is None:
        _pipeline_instance = UnifiedPipeline()
    return _pipeline_instance


# ── 测试入口 ────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    
    pipeline = UnifiedPipeline()
    
    # 测试同步调用
    print("=" * 50)
    print("测试 UnifiedPipeline")
    print("=" * 50)
    
    result = pipeline.process(
        user_id="test_user",
        query="Python 异步编程",
        session_id="test_session"
    )
    
    print(f"\n意图: {result.intent.value}")
    print(f"置信度: {result.confidence:.2f}")
    print(f"缓存命中: {result.cache_hit}")
    print(f"需要澄清: {result.needs_clarification}")
    print(f"\n响应长度: {len(result.response)}")
    print(f"\n响应预览:\n{result.response[:500]}...")
    
    print(f"\n执行追踪:\n{pipeline.get_execution_trace(result)}")
