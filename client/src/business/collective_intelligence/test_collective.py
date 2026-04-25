"""
Collective Intelligence Module Tests
集体智能系统测试
"""

import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def test_agent_profiles():
    """Test 1: Agent Profiles"""
    print("\n" + "="*50)
    print("Test 1: Agent Profiles")
    print("="*50)
    
    from agent_profiles import AgentProfile, AgentRole, ExpertiseLevel, Expertise
    
    # 创建Agent
    agent1 = AgentProfile(
        agent_id="agent1",
        name="Code Agent",
        role=AgentRole.EXPERT,
        description="Expert in coding"
    )
    
    # 添加专业知识
    agent1.add_expertise("Python", ExpertiseLevel.EXPERT)
    agent1.add_expertise("Testing", ExpertiseLevel.PROFICIENT)
    
    # 更新统计
    agent1.total_tasks_completed = 10
    agent1.successful_tasks = 9
    
    print(f"  Agent: {agent1.name}")
    print(f"  Role: {agent1.role.value}")
    print(f"  Success Rate: {agent1.success_rate:.1%}")
    print(f"  Python Level: {agent1.get_expertise_level('Python').value}")
    
    print("  [PASS]")
    return True


async def test_knowledge_base():
    """Test 2: Knowledge Base"""
    print("\n" + "="*50)
    print("Test 2: Knowledge Base")
    print("="*50)
    
    from knowledge_base import SharedKnowledgeBase, KnowledgeQuery
    
    kb = SharedKnowledgeBase()
    
    # 添加知识
    entry1 = await kb.add_knowledge(
        content="Python list comprehensions are efficient for data transformation",
        source_agent="agent1",
        domain="programming",
        tags=["python", "performance"]
    )
    
    entry2 = await kb.add_knowledge(
        content="Use async/await for I/O bound operations",
        source_agent="agent2",
        domain="programming",
        tags=["async", "performance"]
    )
    
    # 搜索
    result = await kb.search(KnowledgeQuery("python list performance", limit=5))
    
    print(f"  Knowledge entries: {len(result.entries)}")
    print(f"  Total matches: {result.total_matches}")
    print(f"  Search time: {result.search_time:.3f}s")
    
    # 验证
    await kb.verify_knowledge(entry1.entry_id, "agent3")
    await kb.verify_knowledge(entry1.entry_id, "agent4")
    
    print(f"  Verified entries: {await kb.get_verified_count()}")
    
    print("  [PASS]")
    return True


async def test_consensus_engine():
    """Test 3: Consensus Engine"""
    print("\n" + "="*50)
    print("Test 3: Consensus Engine")
    print("="*50)
    
    from consensus_engine import ConsensusEngine, ConsensusStrategy
    
    engine = ConsensusEngine()
    
    # 定义投票者和权重
    voters = {
        "agent1": 1.0,
        "agent2": 0.8,
        "agent3": 0.9
    }
    
    # 定义选项
    options = [
        "Use approach A",
        "Use approach B",
        "Use approach C"
    ]
    
    # 达成共识
    result = await engine.reach_consensus(
        topic="Best approach for the task",
        options=options,
        voters=voters,
        strategy=ConsensusStrategy.MAJORITY
    )
    
    print(f"  Success: {result.success}")
    print(f"  Agreed option: {result.agreed_option}")
    print(f"  Confidence: {result.confidence:.2f}")
    print(f"  Vote counts: {result.vote_counts}")
    print(f"  Elapsed time: {result.elapsed_time:.3f}s")
    
    print("  [PASS]")
    return True


async def test_collective_memory():
    """Test 4: Collective Memory"""
    print("\n" + "="*50)
    print("Test 4: Collective Memory")
    print("="*50)
    
    from collective_memory import CollectiveMemory
    
    memory = CollectiveMemory()
    
    # 存储经验
    entry1 = await memory.store_shared_memory(
        content="Testing is crucial for code quality",
        event_type="insight",
        agents_involved=["agent1", "agent2"],
        importance=0.8
    )
    
    entry2 = await memory.store_shared_memory(
        content="Refactoring improved performance by 30%",
        event_type="success",
        agents_involved=["agent3"],
        outcome="success",
        lessons=["Regular refactoring helps"]
    )
    
    # 搜索记忆
    memories = await memory.search_memories("testing", limit=10)
    
    print(f"  Stored memories: 2")
    print(f"  Search results: {len(memories)}")
    
    # 发现模式
    pattern = await memory.discover_pattern(
        source_memory_ids=[entry1.entry_id, entry2.entry_id],
        name="Quality Driven Development",
        description="Focus on testing and refactoring",
        trigger_conditions=["low_test_coverage", "performance_issues"]
    )
    
    print(f"  Pattern discovered: {pattern.name}")
    print(f"  Success rate: {pattern.success_rate:.1%}")
    
    print("  [PASS]")
    return True


async def test_collective_intelligence():
    """Test 5: Collective Intelligence System"""
    print("\n" + "="*50)
    print("Test 5: Collective Intelligence System")
    print("="*50)
    
    from collective_intelligence import (
        CollectiveIntelligence, AgentProfile, AgentRole, ExpertiseLevel
    )
    
    # 创建系统
    ci = CollectiveIntelligence()
    
    # 注册Agent
    agent1 = AgentProfile(
        agent_id="agent1",
        name="Python Expert",
        role=AgentRole.EXPERT,
        description="Python development expert"
    )
    agent1.add_expertise("Python", ExpertiseLevel.EXPERT)
    
    agent2 = AgentProfile(
        agent_id="agent2",
        name="Testing Expert",
        role=AgentRole.EXPERT,
        description="Testing specialist"
    )
    agent2.add_expertise("Testing", ExpertiseLevel.EXPERT)
    
    ci.register_agent(agent1)
    ci.register_agent(agent2)
    
    # 共享知识
    await ci.share_knowledge(
        agent_id="agent1",
        content="Use pytest for Python testing",
        domain="testing"
    )
    
    # 集体学习
    await ci.collective_learn(
        experience="Successfully refactored legacy code",
        agents_involved=["agent1", "agent2"],
        outcome="success",
        lessons=["Modular design is key"]
    )
    
    # 创建任务
    task = ci.create_task(
        description="Optimize database queries",
        required_expertise=["Python", "Database"]
    )
    
    # 分配任务
    await ci.assign_task(task.task_id, ["agent1", "agent2"])
    
    # 执行协作
    result = await ci.collaborate(task)
    
    print(f"  Collaboration success: {result.success}")
    print(f"  Contributions: {len(result.contributions)}")
    print(f"  Total time: {result.total_time:.3f}s")
    
    # 获取统计
    stats = await ci.get_stats()
    print(f"  Total agents: {stats['total_agents']}")
    print(f"  Knowledge entries: {stats['knowledge_entries']}")
    
    print("  [PASS]")
    return True


async def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("[COLLECTIVE INTELLIGENCE TEST SUITE]")
    print("="*60)
    
    results = []
    
    tests = [
        ("Agent Profiles", test_agent_profiles),
        ("Knowledge Base", test_knowledge_base),
        ("Consensus Engine", test_consensus_engine),
        ("Collective Memory", test_collective_memory),
        ("Collective Intelligence", test_collective_intelligence)
    ]
    
    for name, test_func in tests:
        try:
            await test_func()
            results.append((name, True))
        except Exception as e:
            print(f"\n[FAIL] {name}: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # Summary
    print("\n" + "="*60)
    print("[TEST SUMMARY]")
    print("="*60)
    passed = sum(1 for _, s in results if s)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    
    for name, success in results:
        status = "[OK]" if success else "[FAIL]"
        print(f"  {status} {name}")
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
