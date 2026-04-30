"""
测试 PASK 主动式智能体模块
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from loguru import logger
logger.remove()
logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}", colorize=False)

from client.src.business.pask_integration import (
    HybridMemory,
    DemandDetector,
    ProactiveAgent,
    PASKConfig
)


async def test_pask_integration():
    """测试 PASK 集成"""
    print("=" * 60)
    print("测试 PASK 主动式智能体")
    print("参考论文: https://arxiv.org/abs/2604.08000")
    print("=" * 60)

    # 初始化组件
    memory = HybridMemory()
    detector = DemandDetector()
    agent = ProactiveAgent()
    
    print("\n[1] 测试混合记忆系统")
    memory.set_active_user("test_user_001")
    
    # 添加工作空间上下文
    memory.add_context("用户询问如何学习 Python")
    memory.add_context("用户之前问过机器学习相关问题")
    
    # 添加用户偏好
    memory.add_preference("用户喜欢技术学习")
    memory.add_preference("用户对 AI 感兴趣")
    
    # 添加全局知识
    memory.add_knowledge("Python 是一种流行的编程语言")
    memory.add_knowledge("机器学习是 AI 的一个分支")
    
    stats = memory.get_stats()
    print(f"✓ 工作空间条目: {stats['workspace_entries']}")
    print(f"✓ 用户数量: {stats['user_count']}")
    print(f"✓ 全局条目: {stats['global_entries']}")
    print(f"✓ 活跃用户: {stats['active_user']}")
    
    # 搜索测试
    results = memory.search_all("Python")
    print(f"✓ 搜索 'Python' 找到 {len(results)} 条结果")

    print("\n[2] 测试需求检测")
    messages = [
        "你好，我想学习编程",
        "Python 难学吗？",
        "有没有好的教程推荐？"
    ]
    
    for msg in messages:
        result = detector.process_message(msg)
        intents = [i["intent_type"] for i in result["intents"]]
        print(f"✓ 消息: '{msg}'")
        print(f"  意图: {intents}")
    
    # 检测潜在需求
    latent_needs = detector.get_latent_needs()
    print(f"\n✓ 检测到 {len(latent_needs)} 个潜在需求")
    for need in latent_needs:
        print(f"  - {need.description} (优先级: {need.priority():.2f})")

    print("\n[3] 测试主动式智能体")
    # 转换需求格式并生成行为
    needs_dict = [need.to_dict() for need in latent_needs]
    actions = await agent.generate_actions(needs_dict)
    
    print(f"✓ 生成 {len(actions)} 个主动行为")
    for action in actions:
        print(f"  - [{action.action_type}] {action.description} (置信度: {action.confidence:.2f})")
    
    # 执行行为
    executed = []
    for _ in range(len(actions)):
        action = await agent.execute_next_action()
        if action:
            executed.append(action)
    
    print(f"\n✓ 执行了 {len(executed)} 个行为")
    
    stats = agent.get_stats()
    print(f"\n[4] 主动式智能体统计:")
    print(f"  待执行: {stats['pending_actions']}")
    print(f"  已执行: {stats['executed_actions']}")
    print(f"  置信度阈值: {stats['confidence_threshold']}")
    print(f"  最小间隔: {stats['min_interval_seconds']} 秒")

    print("\n[5] 测试配置系统")
    config = PASKConfig()
    config.proactive.enable_proactivity = True
    config.proactive.max_actions_per_session = 10
    print(f"✓ 配置加载成功")
    print(f"  主动模式: {'开启' if config.proactive.enable_proactivity else '关闭'}")
    print(f"  最大行为数: {config.proactive.max_actions_per_session}")

    print("\n" + "=" * 60)
    print("PASK 测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_pask_integration())