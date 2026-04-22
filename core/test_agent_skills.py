"""
Agent Skills 集成测试脚本
=======================

测试 Agent Skills 的各项功能
"""

import sys
import asyncio
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.agent_skills import (
    AgentSkillsInitializer,
    SkillRegistry,
    SkillCategory,
)


async def test_initialization():
    """测试初始化"""
    print("=" * 60)
    print("测试 1: Agent Skills 初始化")
    print("=" * 60)
    
    initializer = AgentSkillsInitializer()
    result = initializer.initialize()
    
    print(f"\n初始化结果:")
    print(f"  成功: {result['success']}")
    print(f"  注册技能数: {result['skills_registered']}")
    print(f"  注册命令数: {result['commands_registered']}")
    
    return result['success']


async def test_skill_registry():
    """测试技能注册中心"""
    print("\n" + "=" * 60)
    print("测试 2: 技能注册中心")
    print("=" * 60)
    
    initializer = AgentSkillsInitializer()
    initializer.initialize()
    
    registry = initializer.get_registry()
    
    # 列出所有技能
    skills = registry.list_skills()
    print(f"\n已注册技能 ({len(skills)} 个):")
    for skill in skills:
        print(f"  - {skill.id}: {skill.name} [{skill.category.value}]")
        
    # 按类别查询
    print(f"\n按类别查询 - planning:")
    planning_skills = registry.list_skills(SkillCategory.PLANNING)
    for skill in planning_skills:
        print(f"  - {skill.name}")
        
    # 触发词查找
    print(f"\n触发词查找 'test':")
    matched = registry.find_by_trigger("test")
    for skill in matched:
        print(f"  - {skill.name}")
        
    return True


async def test_slash_commands():
    """测试斜杠命令"""
    print("\n" + "=" * 60)
    print("测试 3: 斜杠命令系统")
    print("=" * 60)
    
    initializer = AgentSkillsInitializer()
    initializer.initialize()
    
    slash_cmds = initializer.get_slash_commands()
    
    # 列出所有命令
    commands = slash_cmds.list_commands()
    print(f"\n已注册命令 ({len(commands)} 个):")
    for cmd in commands:
        print(f"  {cmd['command']}: {cmd['description']}")
        
    # 测试命令执行
    print(f"\n测试命令执行:")
    test_inputs = [
        "/spec",
        "/test",
        "/review",
        "/skills",
        "/unknown",
        "hello world",  # 不是命令
    ]
    
    for input_text in test_inputs:
        result = slash_cmds.execute(input_text)
        if result is not None:
            print(f"  输入: {input_text}")
            print(f"  结果: {result}")
            print()
            
    return True


async def test_skill_execution():
    """测试技能执行"""
    print("\n" + "=" * 60)
    print("测试 4: 技能执行")
    print("=" * 60)
    
    initializer = AgentSkillsInitializer()
    initializer.initialize()
    
    executor = initializer.get_executor()
    
    # 执行 Spec 驱动工作流
    result = await executor.execute_skill("spec-driven-development")
    print(f"\n执行 Spec 驱动开发:")
    print(f"  成功: {result.get('success')}")
    print(f"  工作流: {result.get('workflow')}")
    if 'phases' in result:
        print(f"  阶段数: {len(result['phases'])}")
        
    # 执行测试驱动工作流
    result = await executor.execute_skill("test-driven-development")
    print(f"\n执行测试驱动开发:")
    print(f"  成功: {result.get('success')}")
    
    # 执行不存在的技能
    result = await executor.execute_skill("nonexistent")
    print(f"\n执行不存在的技能:")
    print(f"  成功: {result.get('success')}")
    print(f"  错误: {result.get('error')}")
    
    return True


async def test_context_aware():
    """测试上下文感知加载"""
    print("\n" + "=" * 60)
    print("测试 5: 上下文感知加载")
    print("=" * 60)
    
    initializer = AgentSkillsInitializer()
    initializer.initialize()
    
    context_loader = initializer.get_context_loader()
    
    # 测试前端上下文
    context = {
        "task_type": "frontend",
        "file_types": ["jsx", "css"],
        "keywords": ["component"],
    }
    
    skills = context_loader.get_relevant_skills(context)
    print(f"\n前端上下文相关技能 ({len(skills)} 个):")
    for skill in skills:
        print(f"  - {skill.name} (优先级: {skill.priority})")
        
    # 测试后端上下文
    context = {
        "task_type": "backend",
        "file_types": ["py"],
        "keywords": ["api"],
    }
    
    skills = context_loader.get_relevant_skills(context)
    print(f"\n后端上下文相关技能 ({len(skills)} 个):")
    for skill in skills:
        print(f"  - {skill.name} (优先级: {skill.priority})")
        
    return True


async def run_all_tests():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("Agent Skills 集成测试")
    print("=" * 60)
    
    tests = [
        test_initialization,
        test_skill_registry,
        test_slash_commands,
        test_skill_execution,
        test_context_aware,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            result = await test()
            if result:
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"\n❌ 测试失败: {test.__name__}")
            print(f"   错误: {e}")
            failed += 1
            
    print("\n" + "=" * 60)
    print(f"测试结果: {passed} 通过, {failed} 失败")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
