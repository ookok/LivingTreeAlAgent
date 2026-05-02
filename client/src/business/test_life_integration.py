"""
生命系统集成测试

测试覆盖：
1. 生命系统与RAG引擎集成
2. 生命系统与用户画像系统集成
3. 生命系统与记忆系统集成
4. 综合查询接口测试
"""

import asyncio
import sys
import os

# 使用__import__导入标准库的platform，避免项目中的platform.py干扰
import importlib
_platform_module = importlib.import_module('platform', package=None)
sys.modules['platform'] = _platform_module

# 现在可以安全地添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入所需模块
from cell_framework import LifeEngine, CellRegistry
from life_integration import LifeIntegration
from enhanced_rag import EnhancedRAGEngine, EnhancedUserProfile


async def test_life_integration():
    """测试生命系统集成"""
    print("\n" + "="*60)
    print("[Test 1] 生命系统集成测试")
    print("="*60)
    
    # 创建生命引擎
    life_engine = LifeEngine()
    print("✓ 创建生命引擎")
    
    # 创建集成层
    integration = LifeIntegration(life_engine)
    await integration.initialize()
    print("✓ 创建生命集成层")
    
    # 检查状态
    status = integration.get_status()
    print("✓ 集成层状态:")
    print(f"  - RAG可用: {status['fusion_rag_available']}")
    print(f"  - 用户画像可用: {status['hermes_agent_available']}")
    print(f"  - 记忆系统可用: {status['memory_system_available']}")
    print(f"  - 搜索系统可用: {status['search_system_available']}")
    print(f"  - 模型中心可用: {status['model_hub_available']}")
    
    print("\n✓ 生命系统集成测试完成！")


async def test_enhanced_rag():
    """测试增强版RAG引擎"""
    print("\n" + "="*60)
    print("[Test 2] 增强版RAG引擎测试")
    print("="*60)
    
    # 创建生命引擎和集成层
    life_engine = LifeEngine()
    integration = LifeIntegration(life_engine)
    await integration.initialize()
    
    # 创建增强RAG引擎
    enhanced_rag = EnhancedRAGEngine(integration)
    print("✓ 创建增强版RAG引擎")
    
    # 执行查询
    queries = [
        "什么是细胞AI？",
        "如何实现自主进化？",
        "生命系统的核心能力是什么？"
    ]
    
    for query in queries:
        result = await enhanced_rag.query(query)
        print(f"✓ 查询: '{query}'")
        print(f"  - 置信度: {result.confidence:.2f}")
        print(f"  - 意图类型: {result.intent.get('type', 'unknown')}")
        print(f"  - 来源数量: {len(result.sources)}")
    
    print("\n✓ 增强版RAG引擎测试完成！")


async def test_enhanced_user_profile():
    """测试增强版用户画像系统"""
    print("\n" + "="*60)
    print("[Test 3] 增强版用户画像系统测试")
    print("="*60)
    
    # 创建生命引擎和集成层
    life_engine = LifeEngine()
    integration = LifeIntegration(life_engine)
    await integration.initialize()
    
    # 创建增强用户画像系统
    enhanced_profile = EnhancedUserProfile(integration)
    print("✓ 创建增强版用户画像系统")
    
    # 模拟用户交互
    user_id = "test_user_001"
    
    interactions = [
        {"query": "帮我写一段Python代码", "type": "code"},
        {"query": "解释一下机器学习", "type": "knowledge"},
        {"query": "推荐一些学习资源", "type": "recommendation"}
    ]
    
    for interaction in interactions:
        await enhanced_profile.update_profile(user_id, interaction)
        print(f"✓ 更新用户画像: {interaction['query']}")
    
    # 获取个性化响应
    response = await enhanced_profile.get_personalized_response(user_id, "你好")
    print(f"✓ 个性化响应: {response[:50]}...")
    
    print("\n✓ 增强版用户画像系统测试完成！")


async def test_integrated_query():
    """测试综合查询接口"""
    print("\n" + "="*60)
    print("[Test 4] 综合查询接口测试")
    print("="*60)
    
    # 创建生命引擎和集成层
    life_engine = LifeEngine()
    integration = LifeIntegration(life_engine)
    await integration.initialize()
    
    # 测试各种查询类型
    test_cases = [
        {
            'query': "什么是量子计算？",
            'context': {'type': 'knowledge'},
            'expected_type': 'knowledge'
        },
        {
            'query': "我的偏好是什么？",
            'context': {'user_id': 'user123'},
            'expected_type': 'user'
        },
        {
            'query': "搜索相关文档",
            'context': {'search_depth': 'deep'},
            'expected_type': 'search'
        },
        {
            'query': "生成一份报告",
            'context': {'task_type': 'generation'},
            'expected_type': 'task'
        }
    ]
    
    for test_case in test_cases:
        result = await integration.integrated_query(
            test_case['query'],
            test_case.get('context')
        )
        print(f"✓ 查询: '{test_case['query']}'")
        print(f"  - 成功: {result.success}")
        print(f"  - 置信度: {result.confidence:.2f}")
        print(f"  - 消息: {result.message}")
    
    # 查看集成统计
    stats = integration.get_integration_stats()
    print(f"\n✓ 集成统计:")
    print(f"  - RAG增强次数: {stats['rag_enhancements']}")
    print(f"  - 用户画像增强次数: {stats['profile_enhancements']}")
    print(f"  - 搜索增强次数: {stats['search_enhancements']}")
    print(f"  - 模型优化次数: {stats['model_optimizations']}")
    
    print("\n✓ 综合查询接口测试完成！")


async def test_end_to_end():
    """端到端测试"""
    print("\n" + "="*60)
    print("[Test 5] 端到端测试")
    print("="*60)
    
    # 创建完整的生命系统
    life_engine = LifeEngine()
    integration = LifeIntegration(life_engine)
    await integration.initialize()
    
    enhanced_rag = EnhancedRAGEngine(integration)
    enhanced_profile = EnhancedUserProfile(integration)
    
    print("✓ 创建完整生命系统")
    
    # 模拟完整用户会话
    user_id = "session_user"
    
    # 会话流程
    session = [
        "你好，我想了解细胞AI",
        "它是如何工作的？",
        "能给我举个例子吗？",
        "谢谢，很有帮助！"
    ]
    
    print("\n📋 模拟用户会话:")
    for i, query in enumerate(session):
        # 更新用户画像
        await enhanced_profile.update_profile(user_id, {
            'query': query,
            'turn': i + 1
        })
        
        # 获取响应
        result = await enhanced_rag.query(query)
        
        print(f"\n用户: {query}")
        print(f"系统: {result.content[:60]}...")
        print(f"  (置信度: {result.confidence:.2f})")
    
    print("\n✓ 端到端测试完成！")


async def main():
    """运行所有测试"""
    print("="*60)
    print("生命系统集成测试套件")
    print("="*60)
    
    await test_life_integration()
    await test_enhanced_rag()
    await test_enhanced_user_profile()
    await test_integrated_query()
    await test_end_to_end()
    
    print("\n" + "="*60)
    print("所有集成测试完成！")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())