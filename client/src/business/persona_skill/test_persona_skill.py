# -*- coding: utf-8 -*-
"""
Persona Skill 系统测试
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from core.persona_skill import (
    PersonaEngine, PersonaRegistry, PersonaSkill,
    PersonaCategory, PersonaTier, consult
)


def test_registry():
    """测试注册表"""
    print("\n" + "="*50)
    print("测试 1: PersonaRegistry")
    print("="*50)
    
    registry = PersonaRegistry()
    
    # 列出所有角色
    personas = registry.list_all()
    print(f"\n已加载角色数: {len(personas)}")
    
    for p in personas:
        print(f"  {p.icon} {p.name} [{p.tier.value}] - ★{p.star}")
    
    # 按类别统计
    print("\n按类别统计:")
    for cat in PersonaCategory:
        count = len(registry.list_by_category(cat))
        if count > 0:
            print(f"  {cat.value}: {count}")
    
    # 获取统计
    stats = registry.get_stats()
    print(f"\n总角色数: {stats['total']}")
    print(f"内置: {stats['builtin']}, 自定义: {stats['custom']}")
    
    print("\n✅ Registry 测试通过")


def test_engine():
    """测试引擎"""
    print("\n" + "="*50)
    print("测试 2: PersonaEngine")
    print("="*50)
    
    engine = PersonaEngine()
    
    # 测试意图检测
    print("\n意图检测测试:")
    test_queries = [
        "有个客户价格卡在9折，怎么破？",
        "产品设计要怎么简化？",
        "这笔投资有什么风险？",
    ]
    
    for query in test_queries:
        recommendations = engine.detect_intent(query)
        if recommendations:
            top = recommendations[0]
            print(f"  '{query[:15]}...' → 推荐: {top['icon']} {top['name']} (score: {top['score']:.2f})")
    
    print("\n✅ Engine 测试通过")


def test_sync_consult():
    """测试同步咨询"""
    print("\n" + "="*50)
    print("测试 3: 同步咨询")
    print("="*50)
    
    # 这需要配置 LLM 网关，演示模式会返回模拟响应
    result = asyncio.run(asyncio.to_thread(
        lambda: PersonaEngine().invoke_sync(
            "有个客户价格卡在9折，怎么破？",
            persona_id="colleague_sales"
        )
    ))
    
    print(f"\n调用结果:")
    print(f"  成功: {result.success}")
    print(f"  角色: {result.persona_name}")
    print(f"  响应: {result.response[:100]}...")


def test_persona_workflow():
    """测试完整工作流"""
    print("\n" + "="*50)
    print("测试 4: 完整工作流")
    print("="*50)
    
    engine = PersonaEngine()
    
    # 激活角色
    print("\n1. 激活角色: 金牌销售同事")
    engine.switch_persona("colleague_sales")
    
    # 获取当前角色
    current = engine.get_current_persona()
    print(f"   当前角色: {current.icon} {current.name}")
    
    # 异步调用
    print("\n2. 异步调用...")
    result = asyncio.run(engine.invoke(
        task="客户说别家比我们便宜20%，怎么处理？",
        use_memory=False  # 测试时禁用记忆
    ))
    
    print(f"\n3. 响应:")
    print(f"   成功: {result.success}")
    print(f"   延迟: {result.latency_ms:.0f}ms")
    if result.success:
        print(f"   响应预览: {result.response[:150]}...")
    
    print("\n✅ 工作流测试通过")


def test_quick_consult():
    """测试快捷函数"""
    print("\n" + "="*50)
    print("测试 5: 快捷咨询函数")
    print("="*50)
    
    # 这是异步函数
    async def quick_test():
        result = await PersonaEngine().invoke(
            task="马斯克会如何评估这个技术方案？",
            persona_id="musk",
            use_memory=False
        )
        return result
    
    result = asyncio.run(quick_test())
    print(f"\n咨询结果:")
    print(f"  角色: {result.persona_name}")
    print(f"  响应: {result.response[:100]}...")


def main():
    print("="*60)
    print("Persona Skill 系统测试")
    print("="*60)
    
    try:
        test_registry()
        test_engine()
        test_sync_consult()
        test_persona_workflow()
        test_quick_consult()
        
        print("\n" + "="*60)
        print("🎉 所有测试通过!")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
