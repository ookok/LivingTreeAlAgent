# -*- coding: utf-8 -*-
"""
HermesAgent Pipeline 集成适配器
HermesAgent Pipeline Integration Adapter
=======================================

将 UnifiedPipeline 集成到 HermesAgent 的适配层。

功能：
1. 提供 HermesAgent.send_message_pipeline() 方法，使用统一流水线处理
2. 保持向后兼容，现有代码无需修改
3. 支持渐进式迁移

使用方法：
```python
from client.src.business.agent_pipeline_adapter import HermesAgentPipelineAdapter

# 方式 1: 直接使用流水线
adapter = HermesAgentPipelineAdapter()
result = adapter.process(user_id="user1", query="Python 异步编程")

# 方式 2: 集成到 HermesAgent
agent = HermesAgent()
agent.use_pipeline = True  # 启用流水线
for chunk in agent.send_message("Python 异步编程"):
    logger.info(chunk)
```

Author: Hermes Desktop Team
"""

from client.src.business.logger import get_logger
logger = get_logger('agent_pipeline_adapter')

from __future__ import annotations

import logging
from typing import Optional, Iterator, Dict, Any, List

from client.src.business.unified_pipeline import (
    UnifiedPipeline,
    PipelineContext,
    IntentType,
)
from client.src.business.ollama_client import StreamChunk

logger = logging.getLogger(__name__)


class HermesAgentPipelineAdapter:
    """
    HermesAgent 流水线适配器
    
    提供独立的流水线处理能力，可以单独使用，
    也可以与 HermesAgent 配合使用。
    """
    
    def __init__(
        self,
        ollama_url: str = "http://localhost:11434",
        enable_skill: bool = True,
        enable_clarification: bool = True
    ):
        self._pipeline: Optional[UnifiedPipeline] = None
        self._ollama_url = ollama_url
        self.enable_skill = enable_skill
        self.enable_clarification = enable_clarification
    
    @property
    def pipeline(self) -> UnifiedPipeline:
        """延迟初始化流水线"""
        if self._pipeline is None:
            self._pipeline = UnifiedPipeline(ollama_url=self._ollama_url)
        return self._pipeline
    
    def process(
        self,
        user_id: str,
        query: str,
        session_id: str = ""
    ) -> PipelineContext:
        """
        处理用户请求（同步）
        
        Args:
            user_id: 用户 ID
            query: 用户查询
            session_id: 会话 ID
            
        Returns:
            PipelineContext: 处理结果
        """
        return self.pipeline.process(
            user_id=user_id,
            query=query,
            session_id=session_id,
            use_cache=True,
            enable_skill=self.enable_skill,
            enable_clarification=self.enable_clarification
        )
    
    def process_stream(
        self,
        user_id: str,
        query: str,
        session_id: str = ""
    ) -> Iterator[str]:
        """
        处理用户请求（流式）
        
        Args:
            user_id: 用户 ID
            query: 用户查询
            session_id: 会话 ID
            
        Yields:
            str: 生成的文本块
        """
        for chunk in self.pipeline.process_stream(
            user_id=user_id,
            query=query,
            session_id=session_id,
            enable_clarification=self.enable_clarification
        ):
            yield chunk
    
    def get_intent(self, query: str) -> IntentType:
        """快速获取意图类型"""
        ctx = PipelineContext(query=query)
        self.pipeline._step_intent_classify(ctx)
        return ctx.intent
    
    def search_knowledge(
        self,
        query: str,
        top_k: int = 5
    ) -> List[Any]:
        """快速知识检索"""
        ctx = PipelineContext(query=query)
        self.pipeline._step_route_and_retrieve(ctx)
        return ctx.retrieved_context


# ── HermesAgent Mixin ──────────────────────────────────────────────────────


class PipelineMixin:
    """
    Pipeline 混入类
    
    提供流水线功能的混入类，可以添加到任何 Agent 类中。
    
    使用示例：
    ```python
    class MyAgent(PipelineMixin, HermesAgent):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._init_pipeline()
    ```
    """
    
    def _init_pipeline(self):
        """初始化流水线"""
        self._pipeline_adapter: Optional[HermesAgentPipelineAdapter] = None
        self._use_pipeline: bool = False
    
    @property
    def use_pipeline(self) -> bool:
        """是否启用流水线"""
        return self._use_pipeline
    
    @use_pipeline.setter
    def use_pipeline(self, value: bool):
        """设置是否启用流水线"""
        self._use_pipeline = value
        if value and self._pipeline_adapter is None:
            self._pipeline_adapter = HermesAgentPipelineAdapter()
    
    @property
    def pipeline(self) -> HermesAgentPipelineAdapter:
        """获取流水线适配器"""
        if self._pipeline_adapter is None:
            self._pipeline_adapter = HermesAgentPipelineAdapter()
        return self._pipeline_adapter
    
    def process_with_pipeline(
        self,
        query: str,
        user_id: str = "default",
        session_id: str = ""
    ) -> PipelineContext:
        """
        使用流水线处理请求（同步）
        
        Args:
            query: 用户查询
            user_id: 用户 ID
            session_id: 会话 ID
            
        Returns:
            PipelineContext: 处理结果
        """
        return self.pipeline.process(
            user_id=user_id,
            query=query,
            session_id=session_id or self.session_id
        )
    
    def send_message_pipeline(
        self,
        text: str
    ) -> Iterator[StreamChunk]:
        """
        使用流水线的消息发送（流式）
        
        Args:
            text: 用户消息
            
        Yields:
            StreamChunk: 流式响应块
        """
        # 使用流水线处理
        for chunk in self.pipeline.process_stream(
            user_id=self.user_id or "default",
            query=text,
            session_id=self.session_id
        ):
            yield StreamChunk(delta=chunk)
        
        # 追加到会话历史
        self.session_db.append_message(self.session_id, "user", text)
        
        # TODO: 记录 assistant 响应到会话历史


# ── 工厂函数 ────────────────────────────────────────────────────────────────


def create_pipeline_agent(
    agent_class=None,
    use_pipeline: bool = True
):
    """
    创建支持流水线的 Agent 实例
    
    Args:
        agent_class: Agent 类（默认 HermesAgent）
        use_pipeline: 是否启用流水线
        
    Returns:
        支持流水线的 Agent 实例
    """
    if agent_class is None:
        from client.src.business.agent import HermesAgent

        agent_class = HermesAgent
    
    # 动态创建支持流水线的类
    class PipelineAgent(PipelineMixin, agent_class):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._init_pipeline()
            if use_pipeline:
                self.use_pipeline = True
    
    return PipelineAgent


# ── 测试入口 ────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    logger.info("=" * 50)
    logger.info("测试 HermesAgent Pipeline 适配器")
    logger.info("=" * 50)
    
    # 测试独立适配器
    adapter = HermesAgentPipelineAdapter()
    
    # 快速意图分类
    logger.info("\n[1] 快速意图分类测试")
    intent = adapter.get_intent("Python 异步编程的原理是什么？")
    logger.info(f"    查询: Python 异步编程的原理是什么？")
    logger.info(f"    意图: {intent.value}")
    
    intent2 = adapter.get_intent("帮我写一个排序算法")
    logger.info(f"    查询: 帮我写一个排序算法")
    logger.info(f"    意图: {intent2.value}")
    
    # 完整流水线测试
    logger.info("\n[2] 完整流水线测试")
    result = adapter.process(
        user_id="test_user",
        query="Python 异步编程",
        session_id="test_session"
    )
    
    logger.info(f"    意图: {result.intent.value}")
    logger.info(f"    置信度: {result.confidence:.2f}")
    logger.info(f"    缓存命中: {result.cache_hit}")
    logger.info(f"    需要澄清: {result.needs_clarification}")
    logger.info(f"    响应长度: {len(result.response)}")
    logger.info(f"    执行步骤: {len(result.execution_trace)}")
    
    logger.info("\n[3] 执行追踪")
    logger.info(adapter.pipeline.get_execution_trace(result))
    
    logger.info("\n[4] 响应预览")
    logger.info(result.response[:300] + "..." if len(result.response) > 300 else result.response)
    
    # 测试工厂函数
    logger.info("\n[5] 测试工厂函数")
    try:
        PipelineAgent = create_pipeline_agent()
        logger.info(f"    创建 PipelineAgent: {PipelineAgent}")
    except Exception as e:
        logger.info(f"    跳过（需要完整 HermesAgent 环境）: {e}")
    
    logger.info("\n" + "=" * 50)
    logger.info("测试完成")
    logger.info("=" * 50)
