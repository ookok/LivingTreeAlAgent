"""
自我进化深度集成测试
====================

测试自我进化模块与系统的深度集成：
1. 进化集成层测试
2. 自我进化引擎集成测试
3. 开放式进化集成测试
4. 强化学习改进集成测试
5. 完整集成流程测试

Author: LivingTreeAlAgent Team
Date: 2026-04-30
"""

import pytest
import asyncio

# 导入集成组件
from client.src.business import (
    integrate_optimization,
    get_integration_bootstrapper,
    get_evolution_integration_layer,
)


class TestEvolutionIntegrationLayer:
    """进化集成层测试"""
    
    @pytest.mark.asyncio
    async def test_initialize_evolution_integration(self):
        """测试初始化进化集成层"""
        from client.src.business.evolution_integration_layer import initialize_evolution_integration
        
        result = await initialize_evolution_integration()
        
        assert result["success"] is True
        print(f"进化集成层初始化: {'成功' if result['success'] else '失败'}")
    
    def test_get_integration_layer(self):
        """测试获取集成层实例"""
        layer = get_evolution_integration_layer()
        
        assert layer is not None
        assert hasattr(layer, 'get_status')
        assert hasattr(layer, 'get_stats')
        assert hasattr(layer, 'get_deployed_strategies')
    
    @pytest.mark.asyncio
    async def test_integration_status(self):
        """测试集成状态"""
        layer = get_evolution_integration_layer()
        
        # 启动前状态应为 INITIALIZING
        await layer.initialize()
        
        # 启动后状态应为 RUNNING
        assert layer.get_status().value == "running"


class TestDeepIntegration:
    """深度集成测试"""
    
    @pytest.mark.asyncio
    async def test_full_integration(self):
        """测试完整深度集成"""
        print("开始深度集成测试...")
        
        result = await integrate_optimization()
        
        assert result["success"] is True
        assert "modules" in result
        assert len(result["modules"]) > 0
        
        print("\n集成模块状态:")
        for module in result["modules"]:
            status = "✓" if module["success"] else "✗"
            print(f"  {status} {module['name']}: {module.get('message', '')}")
        
        print(f"\n集成消息: {result['message']}")
    
    def test_get_all_components(self):
        """测试获取所有组件"""
        bootstrapper = get_integration_bootstrapper()
        
        # 获取各个组件
        engine = bootstrapper.get_engine()
        hook_manager = bootstrapper.get_hook_manager()
        evolution_engine = bootstrapper.get_evolution_engine()
        open_evolution = bootstrapper.get_open_evolution()
        rl_improvement = bootstrapper.get_rl_improvement()
        evolution_integration = bootstrapper.get_evolution_integration()
        
        # 验证所有组件都已初始化
        assert engine is not None, "智能优化引擎未初始化"
        assert hook_manager is not None, "钩子管理器未初始化"
        assert evolution_engine is not None, "自我进化引擎未初始化"
        assert open_evolution is not None, "开放式进化未初始化"
        assert rl_improvement is not None, "强化学习改进未初始化"
        assert evolution_integration is not None, "进化集成层未初始化"
        
        print("\n所有组件已成功初始化:")
        print("  ✓ 智能优化引擎")
        print("  ✓ 钩子管理器")
        print("  ✓ 自我进化引擎")
        print("  ✓ 开放式进化")
        print("  ✓ 强化学习改进")
        print("  ✓ 进化集成层")
    
    @pytest.mark.asyncio
    async def test_evolution_cycle(self):
        """测试进化周期"""
        layer = get_evolution_integration_layer()
        
        # 执行几次进化步骤
        for i in range(3):
            # 模拟触发进化
            stats_before = layer.get_stats()
            
            # 手动触发进化
            layer.trigger_evolution("test")
            
            stats_after = layer.get_stats()
            
            print(f"\n进化周期 {i+1}:")
            print(f"  总进化周期: {stats_after.total_evolution_cycles}")
            print(f"  成功部署: {stats_after.successful_deployments}")
            print(f"  失败部署: {stats_after.failed_deployments}")


class TestIntegrationStats:
    """集成统计测试"""
    
    @pytest.mark.asyncio
    async def test_get_integration_stats(self):
        """测试获取集成统计"""
        await integrate_optimization()
        
        bootstrapper = get_integration_bootstrapper()
        stats = bootstrapper.get_integration_stats()
        
        assert "total_calls" in stats or "evolution" in stats
        
        print("\n集成统计:")
        for key, value in stats.items():
            print(f"  {key}: {value}")


class TestEndToEndEvolution:
    """端到端进化测试"""
    
    @pytest.mark.asyncio
    async def test_end_to_end_evolution(self):
        """测试端到端进化流程"""
        print("\n=== 端到端进化测试 ===")
        
        # 1. 深度集成
        print("1. 深度集成所有组件...")
        await integrate_optimization()
        
        # 2. 获取组件
        bootstrapper = get_integration_bootstrapper()
        evolution_engine = bootstrapper.get_evolution_engine()
        open_evolution = bootstrapper.get_open_evolution()
        rl_improvement = bootstrapper.get_rl_improvement()
        integration_layer = bootstrapper.get_evolution_integration()
        
        # 3. 执行自我进化
        print("\n2. 执行自我进化步骤...")
        for i in range(3):
            step = await evolution_engine.execute_evolution_step()
            print(f"   步骤 {i+1}: {step.strategy.name} -> 奖励={step.reward.value:.2f}")
        
        # 4. 执行开放式进化
        print("\n3. 执行开放式进化...")
        for i in range(2):
            result = open_evolution.evolve()
            print(f"   世代 {result['generation']}: 种群大小={result['population_size']}, 新颖策略={result['novelty_count']}")
        
        # 5. 执行强化学习
        print("\n4. 执行强化学习...")
        from client.src.business.rl_driven_improvement import StateFeature
        
        rl_improvement.start_episode()
        rl_improvement.set_current_state({
            StateFeature.SYSTEM_LOAD: 0.5,
            StateFeature.OPTIMIZATION_RATE: 0.7,
            StateFeature.CACHE_HIT_RATE: 0.8,
            StateFeature.COST_EFFICIENCY: 0.75,
            StateFeature.USER_SATISFACTION: 0.8,
        })
        action = rl_improvement.select_action()
        print(f"   选择动作: {action.type.value}")
        rl_improvement.end_episode(10.0)
        
        # 6. 检查集成层状态
        print("\n5. 检查集成状态...")
        stats = integration_layer.get_stats()
        print(f"   总进化周期: {stats.total_evolution_cycles}")
        print(f"   成功部署: {stats.successful_deployments}")
        
        print("\n=== 端到端进化测试完成 ===")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])