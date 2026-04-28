"""
A-EVOLVE 核心功能测试

测试 A-EVOLVE 框架的核心功能，不依赖外部模块
"""

import time
import json
from pathlib import Path

# 直接测试 A-EVOLVE 核心模块
from client.src.business.skill_evolution.evolution_strategy import (
    EvolutionStrategyType,
    TargetedEvolutionStrategy,
    ScalingEvolutionStrategy,
    OpenEndedEvolutionStrategy,
    EvolutionStrategyManager,
)

from client.src.business.skill_evolution.models import (
    TaskSkill,
    SkillEvolutionStatus,
    generate_skill_id,
)

from client.src.business.skill_evolution.database import EvolutionDatabase


def test_evolution_strategies():
    """测试进化策略"""
    print("=== 测试进化策略 ===")
    
    # 创建测试技能
    test_skill = TaskSkill(
        skill_id=generate_skill_id("test_skill"),
        name="测试技能",
        description="测试 A-EVOLVE 进化功能",
        trigger_patterns=["测试", "A-EVOLVE"],
        execution_flow=[
            {
                "phase": "execute",
                "tool": "file_read",
                "args": {"path": "."},
                "success": True,
                "duration": 0.5,
            },
        ],
        tool_sequence=["file_read"],
        success_rate=0.8,
        use_count=5,
        failed_count=1,
        avg_duration=0.5,
        total_duration=2.5,
        evolution_status=SkillEvolutionStatus.GROWING,
    )
    
    print(f"测试技能创建成功: {test_skill.name}")
    print(f"初始状态: {test_skill.evolution_status.value}")
    print(f"初始成功率: {test_skill.success_rate}")
    
    # 测试目标导向策略
    print("\n1. 测试目标导向策略:")
    targeted_strategy = TargetedEvolutionStrategy()
    metrics = targeted_strategy.evaluate_skill(test_skill)
    print(f"评估指标: {metrics}")
    
    feedback = {
        "success": True,
        "duration": 0.4,
    }
    evolved_skill = targeted_strategy.evolve_skill(test_skill, feedback)
    print(f"进化后执行流程: {len(evolved_skill.execution_flow)} 步骤")
    print(f"是否需要进化: {targeted_strategy.should_evolve(evolved_skill)}")
    
    # 测试进化缩放策略
    print("\n2. 测试进化缩放策略:")
    scaling_strategy = ScalingEvolutionStrategy()
    metrics = scaling_strategy.evaluate_skill(test_skill)
    print(f"资源效率: {metrics}")
    
    evolved_skill = scaling_strategy.evolve_skill(test_skill, feedback)
    print(f"进化后工具序列: {evolved_skill.tool_sequence}")
    print(f"是否需要进化: {scaling_strategy.should_evolve(evolved_skill)}")
    
    # 测试开放适应策略
    print("\n3. 测试开放适应策略:")
    open_ended_strategy = OpenEndedEvolutionStrategy()
    metrics = open_ended_strategy.evaluate_skill(test_skill)
    print(f"适应能力指标: {metrics}")
    
    evolved_skill = open_ended_strategy.evolve_skill(test_skill, feedback)
    print(f"是否需要进化: {open_ended_strategy.should_evolve(evolved_skill)}")
    print(f"反馈历史长度: {len(evolved_skill.metadata.get('feedback_history', []))}")


def test_strategy_manager():
    """测试策略管理器"""
    print("\n=== 测试策略管理器 ===")
    
    # 创建临时数据库
    db_path = Path("~/.hermes-desktop/evolution/test_strategy.db").expanduser()
    db = EvolutionDatabase(db_path)
    
    # 创建策略管理器
    manager = EvolutionStrategyManager(db)
    
    # 测试策略选择
    test_skill = TaskSkill(
        skill_id=generate_skill_id("test_strategy"),
        name="策略测试技能",
        description="测试策略选择",
        evolution_status=SkillEvolutionStatus.SEED,
    )
    
    strategy = manager.select_strategy(test_skill)
    print(f"种子状态技能选择策略: {strategy.get_name()}")
    
    test_skill.evolution_status = SkillEvolutionStatus.GROWING
    strategy = manager.select_strategy(test_skill)
    print(f"成长状态技能选择策略: {strategy.get_name()}")
    
    test_skill.evolution_status = SkillEvolutionStatus.MATURED
    strategy = manager.select_strategy(test_skill)
    print(f"成熟状态技能选择策略: {strategy.get_name()}")
    
    # 测试进化建议
    suggestions = manager.get_evolution_suggestions(test_skill)
    print("\n进化建议:")
    for suggestion in suggestions:
        print(f"  - {suggestion['message']} (优先级: {suggestion['priority']})")


def test_a_evolve_integration():
    """测试 A-EVOLVE 集成"""
    print("\n=== 测试 A-EVOLVE 集成 ===")
    
    from client.src.business.skill_evolution.a_evolve_integration import (
        AEvolveConfig,
        AEvolveIntegrator,
    )
    
    # 创建临时数据库
    db_path = Path("~/.hermes-desktop/evolution/test_a_evolve_integration.db").expanduser()
    db = EvolutionDatabase(db_path)
    
    # 创建 A-EVOLVE 集成器
    config = AEvolveConfig(
        enabled=True,
        verbose=True,
        evolution_interval=60,
    )
    
    integrator = AEvolveIntegrator(db, config)
    print(f"A-EVOLVE 集成器创建成功: {integrator}")
    
    # 测试资源优化
    allocation = integrator.optimize_resource_allocation()
    print(f"资源分配: {allocation}")
    
    # 清理
    integrator.shutdown()
    print("集成器关闭成功")


if __name__ == "__main__":
    print("A-EVOLVE 核心功能测试开始")
    
    try:
        test_evolution_strategies()
        test_strategy_manager()
        test_a_evolve_integration()
        print("\n所有测试通过!")
    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n测试完成")
