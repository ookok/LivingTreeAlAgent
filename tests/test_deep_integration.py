"""
深度集成测试
===========

测试优化系统的深度集成：
1. 智能优化引擎测试
2. 钩子管理器测试
3. 集成启动器测试
4. 端到端优化流程测试

Author: LivingTreeAlAgent Team
Date: 2026-04-30
"""

import pytest
import asyncio

# 导入集成组件
from client.src.business import (
    integrate_optimization,
    get_intelligent_optimization_engine,
    get_hook_manager,
    optimized_model_call,
)


class TestIntelligentOptimizationEngine:
    """智能优化引擎测试"""
    
    def test_create_engine(self):
        """测试创建智能优化引擎"""
        engine = get_intelligent_optimization_engine()
        assert engine is not None
    
    def test_make_decision(self):
        """测试智能决策"""
        engine = get_intelligent_optimization_engine()
        
        decision = engine.make_decision("帮我写一个Python函数", {})
        
        assert decision.decision is not None
        assert decision.confidence >= 0
        assert decision.strategy is not None
        assert decision.explanation is not None
        
        print(f"决策: {decision.decision.value}")
        print(f"置信度: {decision.confidence:.2f}")
        print(f"策略: {decision.strategy}")
        print(f"说明: {decision.explanation}")
    
    def test_set_profile(self):
        """测试设置配置文件"""
        engine = get_intelligent_optimization_engine()
        
        # 测试切换到激进配置
        result = engine.set_profile("aggressive")
        assert result is True
        assert engine.get_profile().name == "激进优化"
        
        # 测试切换到保守配置
        result = engine.set_profile("conservative")
        assert result is True
        assert engine.get_profile().name == "保守优化"
        
        # 测试切换到代码优化配置
        result = engine.set_profile("code_focused")
        assert result is True
        assert engine.get_profile().name == "代码优化"
    
    def test_get_dashboard_stats(self):
        """测试获取仪表盘统计"""
        engine = get_intelligent_optimization_engine()
        stats = engine.get_dashboard_stats()
        
        assert "total_calls" in stats
        assert "optimization_rate" in stats
        assert "avg_decision_confidence" in stats
        assert "active_profile" in stats
        
        print("\n仪表盘统计:")
        for key, value in stats.items():
            print(f"  {key}: {value}")
    
    def test_get_recommendations(self):
        """测试获取建议"""
        engine = get_intelligent_optimization_engine()
        recommendations = engine.get_recommendations()
        
        assert isinstance(recommendations, list)
        print(f"\n优化建议: {recommendations}")


class TestHookManager:
    """钩子管理器测试"""
    
    def test_create_hook_manager(self):
        """测试创建钩子管理器"""
        hook_manager = get_hook_manager()
        assert hook_manager is not None
    
    def test_enable_disable(self):
        """测试启用/禁用"""
        hook_manager = get_hook_manager()
        
        hook_manager.enable()
        assert hook_manager.is_enabled() is True
        
        hook_manager.disable()
        assert hook_manager.is_enabled() is False
        
        hook_manager.enable()
    
    def test_register_hook(self):
        """测试注册钩子"""
        from client.src.business.optimization_hook_manager import HookPoint, HookResult, HookContext
        
        hook_manager = get_hook_manager()
        
        def test_hook(context: HookContext) -> HookResult:
            return HookResult(success=True)
        
        hook_manager.register_hook(HookPoint.PROMPT_GENERATION, test_hook)
        
        # 验证钩子已注册
        hooks = hook_manager._hooks[HookPoint.PROMPT_GENERATION]
        assert len([h for h in hooks if h[1] == test_hook]) > 0
    
    def test_optimized_model_call_decorator(self):
        """测试优化模型调用装饰器"""
        @optimized_model_call(model_type="claude-3-sonnet")
        def test_model(prompt: str):
            return f"响应: {prompt}"
        
        result, metadata = test_model("测试提示")
        
        assert "响应: 测试提示" in result
        assert isinstance(metadata, dict)


class TestIntegrationBootstrapper:
    """集成启动器测试"""
    
    @pytest.mark.asyncio
    async def test_integrate_all(self):
        """测试深度集成所有优化"""
        result = await integrate_optimization()
        
        assert result["success"] is True
        assert "modules" in result
        assert "message" in result
        
        print("\n集成结果:")
        print(f"  成功: {result['success']}")
        print(f"  消息: {result['message']}")
        print("  模块状态:")
        for module in result["modules"]:
            status = "✓" if module["success"] else "✗"
            print(f"    {status} {module['name']}: {module.get('message', '')}")


class TestEndToEndOptimization:
    """端到端优化流程测试"""
    
    @pytest.mark.asyncio
    async def test_full_optimization_flow(self):
        """测试完整优化流程"""
        # 1. 深度集成
        await integrate_optimization()
        
        # 2. 获取优化引擎
        engine = get_intelligent_optimization_engine()
        
        # 3. 模拟模型调用
        def mock_model(prompt: str):
            return f"处理完成: {len(prompt)} 字符"
        
        # 4. 执行优化调用
        response, metadata = await engine.optimize_and_call(
            "帮我写一个Python函数来计算斐波那契数列",
            mock_model,
            model_type="claude-3-sonnet"
        )
        
        # 5. 验证结果
        assert response is not None
        assert "处理完成" in response
        assert isinstance(metadata, dict)
        
        print("\n端到端测试结果:")
        print(f"  响应: {response}")
        print(f"  决策: {metadata.get('decision')}")
        print(f"  置信度: {metadata.get('confidence')}")
        print(f"  说明: {metadata.get('explanation')}")
    
    @pytest.mark.asyncio
    async def test_multiple_calls(self):
        """测试多次调用的自适应优化"""
        # 深度集成
        await integrate_optimization()
        
        engine = get_intelligent_optimization_engine()
        
        def mock_model(prompt: str):
            return f"响应: {prompt[:20]}..."
        
        # 多次调用不同类型的查询
        queries = [
            "帮我写一个Python函数",
            "解释这段代码",
            "总结这份文档",
            "搜索相关信息",
            "优化这段代码",
        ]
        
        for i, query in enumerate(queries):
            response, metadata = await engine.optimize_and_call(
                query,
                mock_model,
                model_type="claude-3-sonnet"
            )
            print(f"\n调用 {i+1}: {query}")
            print(f"  决策: {metadata.get('decision')}")
            print(f"  置信度: {metadata.get('confidence', 0):.2f}")
        
        # 获取最终统计
        stats = engine.get_dashboard_stats()
        print(f"\n最终统计:")
        print(f"  总调用数: {stats['total_calls']}")
        print(f"  优化率: {stats['optimization_rate']:.1%}")
        print(f"  平均决策置信度: {stats['avg_decision_confidence']:.2f}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])