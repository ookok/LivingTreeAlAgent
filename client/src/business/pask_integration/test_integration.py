"""
测试 PASK 与现有模块的集成
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from loguru import logger
logger.remove()
logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}", colorize=False)

from business.pask_integration import (
    MemoryIntegrator,
    AgentIntegrator,
    SkillIntegrator,
    RAGIntegrator,
    initialize_integrations
)


async def test_integrations():
    """测试所有集成"""
    print("=" * 60)
    print("测试 PASK 与现有模块的集成")
    print("=" * 60)
    
    # 初始化集成
    print("\n[1] 初始化集成器")
    initialize_integrations()
    print("✓ 集成器初始化完成")
    
    # 测试 MemoryIntegrator
    print("\n[2] 测试 MemoryIntegrator")
    memory_integrator = MemoryIntegrator.get_instance()
    
    # 添加上下文
    memory_integrator.add_context("用户想学习 Python 编程")
    memory_integrator.add_context("用户之前问过机器学习问题")
    
    # 添加偏好
    memory_integrator.add_preference("用户喜欢技术学习内容")
    
    # 添加知识
    memory_integrator.add_knowledge("Python 是一种解释型编程语言")
    
    stats = memory_integrator.get_stats()
    print(f"✓ 工作空间条目: {stats['pask_workspace']}")
    print(f"✓ 全局条目: {stats['pask_global']}")
    print(f"✓ MemoryManager 状态: {stats['memory_manager']}")
    
    # 搜索测试
    results = memory_integrator.search_all("Python")
    print(f"✓ 搜索 'Python' 找到 {len(results)} 条结果")
    
    # 测试 AgentIntegrator
    print("\n[3] 测试 AgentIntegrator")
    agent_integrator = AgentIntegrator.get_instance()
    
    # 处理消息
    result = await agent_integrator.process_message(
        user_id="test_user",
        message="你好，我想学习编程，Python 难学吗？"
    )
    
    print(f"✓ 检测到 {len(result['latent_needs'])} 个潜在需求")
    print(f"✓ 生成 {len(result['generated_actions'])} 个主动行为")
    
    # 获取统计
    stats = agent_integrator.get_stats()
    print(f"✓ 检测器历史长度: {stats['detector_history_length']}")
    print(f"✓ 待执行行为: {stats['pending_actions']}")
    print(f"✓ 已执行行为: {stats['executed_actions']}")
    
    # 测试 SkillIntegrator
    print("\n[4] 测试 SkillIntegrator")
    skill_integrator = SkillIntegrator.get_instance()
    
    stats = skill_integrator.get_stats()
    print(f"✓ 技能构建器: {stats['skill_builder_status']}")
    print(f"✓ 封装引擎: {stats['encapsulation_engine_status']}")
    print(f"✓ 评分系统: {stats['rating_system_status']}")
    print(f"✓ 版本控制: {stats['version_control_status']}")
    
    # 测试 RAGIntegrator
    print("\n[5] 测试 RAGIntegrator")
    rag_integrator = RAGIntegrator.get_instance()
    
    # 更新缓存
    rag_integrator.update_cache("Python 是什么？", "Python 是一种流行的编程语言")
    
    # 获取缓存
    cached = rag_integrator.get_cached_response("Python 是什么？")
    if cached:
        print(f"✓ 缓存命中: {cached[:30]}...")
    
    stats = rag_integrator.get_stats()
    print(f"✓ 精确缓存大小: {stats['exact_cache_size']}")
    print(f"✓ 会话缓存大小: {stats['session_cache_size']}")
    
    print("\n" + "=" * 60)
    print("PASK 集成测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_integrations())