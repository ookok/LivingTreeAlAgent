"""
记忆系统深度集成测试（简化版）
============================

测试记忆系统的完整集成和创新功能：
1. 统一记忆融合引擎
2. 记忆推理引擎
3. 跨模块交互

注：跳过依赖复杂外部模块的测试

Author: LivingTreeAlAgent Team
Date: 2026-04-30
"""

import pytest
import asyncio
from unittest.mock import Mock, patch

# 导入记忆系统模块（只导入不依赖复杂外部模块的模块）
from client.src.business.memory_fusion_engine import (
    MemoryFusionEngine,
    MemorySource,
    FusionStrategy,
    get_memory_fusion_engine,
)
from client.src.business.memory_reasoning_engine import (
    MemoryReasoningEngine,
    ReasoningType,
    get_reasoning_engine,
)
from client.src.business.shared_memory_system import (
    SharedMemorySystem,
    SharingScope,
    PermissionLevel,
    get_shared_memory,
)


class TestMemoryFusionEngine:
    """记忆融合引擎测试"""
    
    def test_create_engine(self):
        """测试创建融合引擎"""
        engine = get_memory_fusion_engine()
        assert isinstance(engine, MemoryFusionEngine)
    
    def test_configure_engine(self):
        """测试配置融合引擎"""
        engine = get_memory_fusion_engine()
        
        # 配置权重
        engine.configure(weights={
            MemorySource.AUTO_MEMORY: 0.3,
            MemorySource.SHARED: 0.2,
        }, strategy="weighted")
        
        stats = engine.get_stats()
        assert stats["strategy"] == "weighted"
    
    @pytest.mark.asyncio
    async def test_fusion_query(self):
        """测试融合查询"""
        engine = get_memory_fusion_engine()
        
        # 添加一些测试数据到共享记忆
        shared = get_shared_memory()
        shared.store("电商系统架构设计", "user1", SharingScope.PUBLIC)
        
        # 执行融合查询（使用指定的源）
        result = await engine.query("电商系统", sources=[MemorySource.SHARED])
        
        assert hasattr(result, 'sources')
        assert hasattr(result, 'fused_content')
        assert hasattr(result, 'confidence')
    
    def test_get_stats(self):
        """测试获取统计信息"""
        engine = get_memory_fusion_engine()
        stats = engine.get_stats()
        
        assert "modules" in stats
        assert "weights" in stats
        assert "strategy" in stats


class TestMemoryReasoningEngine:
    """记忆推理引擎测试"""
    
    def test_create_engine(self):
        """测试创建推理引擎"""
        engine = get_reasoning_engine()
        assert isinstance(engine, MemoryReasoningEngine)
    
    @pytest.mark.asyncio
    async def test_reason_causal(self):
        """测试因果推理"""
        engine = get_reasoning_engine()
        
        # 设置 mock LLM
        engine.set_llm_callable(lambda prompt: "步骤1: 分析问题\n步骤2: 收集证据\n步骤3: 得出结论\n结论: 这是一个因果关系")
        
        result = await engine.reason("为什么电商系统需要微服务架构？", ReasoningType.CAUSAL)
        
        assert hasattr(result, 'query')
        assert hasattr(result, 'final_conclusion')
        assert hasattr(result, 'steps')
        assert len(result.steps) > 0
    
    @pytest.mark.asyncio
    async def test_reason_analogical(self):
        """测试类比推理"""
        engine = get_reasoning_engine()
        
        # 设置 mock LLM
        engine.set_llm_callable(lambda prompt: "步骤1: 比较两个场景\n步骤2: 找出相似点\n结论: 可以借鉴电商系统的设计")
        
        result = await engine.reason("社交平台和电商系统有什么相似之处？", ReasoningType.ANALOGICAL)
        
        assert result.reasoning_id is not None
        assert result.overall_confidence > 0
    
    @pytest.mark.asyncio
    async def test_reason_chained(self):
        """测试链式推理（不依赖外部记忆）"""
        engine = get_reasoning_engine()
        
        # 直接测试链式推理，不依赖外部记忆模块
        result = await engine.reason("微服务架构有什么优点？", max_steps=3)
        
        assert len(result.steps) > 0
        assert result.overall_confidence > 0
    
    def test_explain_reasoning(self):
        """测试解释推理过程"""
        engine = get_reasoning_engine()
        
        from client.src.business.memory_reasoning_engine import ReasoningResult, ReasoningStep
        
        step1 = ReasoningStep(
            step_id="step_1",
            type=ReasoningType.DEDUCTIVE,
            premise="用户查询微服务架构",
            conclusion="分析问题类型",
            confidence=0.9
        )
        
        result = ReasoningResult(
            reasoning_id="test_reason",
            query="微服务架构的优点",
            final_conclusion="微服务架构具有高可用性",
            steps=[step1],
            overall_confidence=0.9,
            execution_time=0.1
        )
        
        explanation = engine.explain_reasoning(result)
        
        assert isinstance(explanation, str)
        assert "推理过程" in explanation


class TestMemoryIntegration:
    """记忆系统集成测试"""
    
    @pytest.mark.asyncio
    async def test_full_memory_workflow(self):
        """测试完整的记忆工作流（简化版）"""
        # 1. 共享记忆存储
        shared = get_shared_memory()
        shared.store("在线教育平台最佳实践", "user1", SharingScope.TEAM)
        
        # 2. 融合查询
        fusion = get_memory_fusion_engine()
        fusion_result = await fusion.query("在线教育平台", sources=[MemorySource.SHARED])
        
        assert fusion_result.confidence >= 0
        
        # 3. 记忆推理
        reasoning = get_reasoning_engine()
        reasoning.set_llm_callable(lambda prompt: "步骤1: 分析需求\n步骤2: 参考最佳实践\n结论: 需要用户、课程、学习进度三个核心模块")
        
        reason_result = await reasoning.reason("如何设计在线教育平台？")
        
        assert reason_result.final_conclusion is not None
        assert reason_result.overall_confidence > 0
        
        print("完整记忆工作流测试通过！")
    
    def test_memory_insights(self):
        """测试记忆洞察生成（简化版）"""
        # 获取洞察（不依赖复杂模块，不传入conversation_id）
        fusion = get_memory_fusion_engine()
        insights = fusion.get_insights()
        
        assert isinstance(insights, list)
        
        print("记忆洞察测试通过！")


class TestSharedMemory:
    """共享记忆系统测试"""
    
    def test_store_and_retrieve(self):
        """测试存储和检索"""
        shared = get_shared_memory()
        
        # 存储公共记忆
        item_id = shared.store("公共知识", "user1", SharingScope.PUBLIC)
        assert item_id is not None
        
        # 不同用户检索
        results = shared.retrieve("公共知识", "user2")
        assert len(results) > 0
    
    def test_permissions(self):
        """测试权限控制"""
        shared = get_shared_memory()
        
        # 存储私有记忆
        item_id = shared.store("私有数据", "owner", SharingScope.PRIVATE)
        
        # 其他用户无法访问
        results = shared.retrieve("私有数据", "other_user")
        assert len(results) == 0
        
        # 授予权限
        shared.grant_permission(item_id, "other_user", PermissionLevel.READ)
        
        # 现在可以访问
        results = shared.retrieve("私有数据", "other_user")
        assert len(results) > 0
    
    def test_version_history(self):
        """测试版本历史"""
        shared = get_shared_memory()
        
        item_id = shared.store("v1", "user1")
        shared.update(item_id, "v2", "user1")
        shared.update(item_id, "v3", "user1")
        
        history = shared.get_version_history(item_id, "user1")
        assert len(history) >= 3
    
    def test_rollback(self):
        """测试版本回滚"""
        shared = get_shared_memory()
        
        item_id = shared.store("原始", "user1")
        original = shared._memory_store[item_id].content
        
        shared.update(item_id, "修改后", "user1")
        
        history = shared.get_version_history(item_id, "user1")
        original_version = history[0].version_id
        
        shared.rollback(item_id, original_version, "user1")
        
        assert shared._memory_store[item_id].content == original


if __name__ == "__main__":
    pytest.main([__file__, "-v"])