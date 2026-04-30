"""
优先集成（P0）测试脚本

测试以下模块的共享基础设施集成：
1. TrainingManager → 依赖注入 + 配置中心 + 事件总线
2. IndustryGovernance → 统一术语模型 + 事件总线 + 缓存层
3. KnowledgeTierManager → 配置中心 + 缓存层
4. DataConstructor → 统一术语模型 + 缓存层
5. AutoTermTableBuilder → 统一术语模型 + 事件总线
6. FeedbackLearner → 事件总线
"""

import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from client.src.business.shared import (
    get_container,
    get_config,
    get_event_bus,
    EVENTS,
    Term
)


def test_training_manager_integration():
    """测试 TrainingManager 集成"""
    print("=" * 60)
    print("测试 1: TrainingManager 集成")
    print("=" * 60)
    
    from client.src.business.expert_training import create_train_manager
    
    try:
        manager = create_train_manager()
        
        # 检查依赖注入
        assert hasattr(manager, 'container'), "缺少容器"
        assert hasattr(manager, 'config_center'), "缺少配置中心"
        assert hasattr(manager, 'event_bus'), "缺少事件总线"
        
        print("✓ 依赖注入容器集成")
        print("✓ 配置中心集成")
        print("✓ 事件总线集成")
        
        # 检查子模块通过容器解析（允许 None，因为可能降级）
        if manager.data_constructor is not None:
            print("✓ 数据构造器通过容器解析")
        if manager.reasoning_builder is not None:
            print("✓ 思维链构造器通过容器解析")
        if manager.task_framework is not None:
            print("✓ 任务框架通过容器解析")
        if manager.training_strategy is not None:
            print("✓ 训练策略通过容器解析")
        
        return True
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        print("  注意：如果是 IndustrialKnowledgeDiscovery 初始化失败，属于现有代码兼容性问题")
        return False


def test_industry_governance_integration():
    """测试 IndustryGovernance 集成"""
    print("\n" + "=" * 60)
    print("测试 2: IndustryGovernance 集成")
    print("=" * 60)
    
    from client.src.business.fusion_rag import create_industry_governance
    
    try:
        governance = create_industry_governance()
        
        # 检查事件总线
        assert hasattr(governance, 'event_bus'), "缺少事件总线"
        
        # 检查缓存层
        assert hasattr(governance, 'cache'), "缺少缓存层"
        
        # 检查统一术语模型
        assert hasattr(governance, 'term_tables'), "缺少术语表"
        
        # 测试添加术语
        governance.add_term("马达", "电机", "机械制造")
        
        # 测试术语归一化（使用缓存）
        result = governance.normalize_term("马达", "机械制造")
        assert result == "电机", f"术语归一化失败: {result}"
        
        print("✓ 统一术语模型集成")
        print("✓ 事件总线集成")
        print("✓ 缓存层集成")
        
        return True
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        return False


def test_knowledge_tier_manager_integration():
    """测试 KnowledgeTierManager 集成"""
    print("\n" + "=" * 60)
    print("测试 3: KnowledgeTierManager 集成")
    print("=" * 60)
    
    from client.src.business.fusion_rag import create_knowledge_tier_manager
    
    try:
        tier_manager = create_knowledge_tier_manager()
        
        # 检查配置中心
        assert hasattr(tier_manager, 'config_center'), "缺少配置中心"
        
        # 检查缓存层
        assert hasattr(tier_manager, 'cache'), "缺少缓存层"
        
        # 检查层级配置
        assert tier_manager.tier_configs[1].weight == 0.55, "层级权重配置错误"
        
        print("✓ 配置中心集成")
        print("✓ 缓存层集成")
        
        return True
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        return False


def test_data_constructor_integration():
    """测试 DataConstructor 集成"""
    print("\n" + "=" * 60)
    print("测试 4: DataConstructor 集成")
    print("=" * 60)
    
    from client.src.business.expert_training import create_data_constructor
    
    try:
        constructor = create_data_constructor()
        
        # 检查缓存层
        assert hasattr(constructor, 'cache'), "缺少缓存层"
        
        # 检查统一术语模型
        assert hasattr(constructor, 'industry_term_tables'), "缺少术语表"
        
        # 测试缓存功能
        from client.src.business.expert_training.data_constructor import TrainingSample
        samples = [TrainingSample(instruction="test", input_data="test", output="test")]
        constructor.cache_samples(samples, "test_key")
        
        cached = constructor.get_cached_samples("test_key")
        assert cached is not None, "缓存失败"
        
        print("✓ 统一术语模型集成")
        print("✓ 缓存层集成")
        
        return True
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        return False


def test_auto_term_table_builder_integration():
    """测试 AutoTermTableBuilder 集成"""
    print("\n" + "=" * 60)
    print("测试 5: AutoTermTableBuilder 集成")
    print("=" * 60)
    
    from client.src.business.expert_training import create_auto_term_table_builder
    
    try:
        builder = create_auto_term_table_builder()
        
        # 检查事件总线
        assert hasattr(builder, 'event_bus'), "缺少事件总线"
        
        # 检查统一术语模型
        assert builder.terms is not None, "缺少术语列表"
        
        print("✓ 统一术语模型集成")
        print("✓ 事件总线集成")
        
        return True
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        return False


def test_feedback_learner_integration():
    """测试 FeedbackLearner 集成"""
    print("\n" + "=" * 60)
    print("测试 6: FeedbackLearner 集成")
    print("=" * 60)
    
    from client.src.business.fusion_rag import create_feedback_learner
    
    try:
        learner = create_feedback_learner()
        
        # 检查事件总线
        assert hasattr(learner, 'event_bus'), "缺少事件总线"
        
        # 测试记录反馈（会发布事件）
        learner.record_feedback("测试查询", "doc001", "内容", "relevant")
        
        print("✓ 事件总线集成")
        print("✓ 反馈记录功能正常")
        
        return True
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        return False


def main():
    """运行所有测试"""
    print("\n" + "=" * 80)
    print("优先集成（P0）测试套件")
    print("=" * 80)
    
    tests = [
        test_training_manager_integration,
        test_industry_governance_integration,
        test_knowledge_tier_manager_integration,
        test_data_constructor_integration,
        test_auto_term_table_builder_integration,
        test_feedback_learner_integration
    ]
    
    results = []
    for test in tests:
        results.append(test())
    
    print("\n" + "=" * 80)
    print("测试结果汇总")
    print("=" * 80)
    print(f"通过: {sum(results)}/{len(results)}")
    
    if all(results):
        print("\n✅ 所有优先集成测试通过！")
    else:
        print("\n❌ 部分测试失败，请检查")


if __name__ == "__main__":
    main()