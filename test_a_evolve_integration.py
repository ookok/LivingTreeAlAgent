"""
A-EVOLVE 集成测试

验证 A-EVOLVE 框架与本项目的集成功能
"""

import time
import json
from pathlib import Path

from client.src.business.skill_evolution import (
    create_agent,
    EvolutionStrategyType,
    get_skill_health,
    evolve_skill_with_feedback,
)


def test_a_evolve_integration():
    """测试 A-EVOLVE 集成"""
    print("=== A-EVOLVE 集成测试 ===")
    
    # 创建 Agent
    agent = create_agent(
        db_path="~/.hermes-desktop/evolution/test_a_evolve.db",
        workspace_root="."
    )
    
    print(f"Agent 创建成功: {agent}")
    print(f"A-EVOLVE 配置: {agent.a_evolve_config}")
    
    # 测试 1: 执行任务并观察技能进化
    print("\n测试 1: 执行任务")
    task_description = "读取当前目录的文件列表"
    result = agent.execute_task(task_description)
    
    print(f"任务执行完成，状态: {result.status}")
    print(f"执行记录数: {len(result.execution_records)}")
    
    # 测试 2: 查看技能健康状态
    if result.skill_id:
        print(f"\n测试 2: 查看技能健康状态")
        from client.src.business.skill_evolution import TaskSkill
        from client.src.business.skill_evolution.database import EvolutionDatabase
        
        db = EvolutionDatabase(Path("~/.hermes-desktop/evolution/test_a_evolve.db").expanduser())
        skill = db.get_skill(result.skill_id)
        
        if skill:
            print(f"技能名称: {skill.name}")
            print(f"技能状态: {skill.evolution_status.value}")
            print(f"成功率: {skill.success_rate:.2f}")
            print(f"使用次数: {skill.use_count}")
            
            # 获取健康报告
            health = get_skill_health(skill, db)
            print("\n健康报告:")
            print(json.dumps(health, ensure_ascii=False, indent=2))
    
    # 测试 3: 手动触发进化
    if result.skill_id:
        print("\n测试 3: 手动触发进化")
        feedback = {
            "success": True,
            "duration": 1.5,
            "manual_evolution": True,
        }
        success = evolve_skill_with_feedback(result.skill_id, feedback, agent.db)
        print(f"进化结果: {'成功' if success else '失败'}")
    
    # 测试 4: 批量进化
    print("\n测试 4: 批量进化")
    skills = agent.db.get_all_skills()
    print(f"当前技能数量: {len(skills)}")
    
    for skill in skills:
        print(f"- {skill.name} (ID: {skill.skill_id}, 状态: {skill.evolution_status.value})")
    
    # 测试 5: 资源优化
    print("\n测试 5: 资源优化")
    if hasattr(agent.a_evolve_integrator, 'optimize_resource_allocation'):
        allocation = agent.a_evolve_integrator.optimize_resource_allocation()
        print(f"资源分配: {allocation}")
    
    # 测试 6: 进化建议
    if skills:
        print("\n测试 6: 进化建议")
        skill = skills[0]
        suggestions = agent.a_evolve_integrator.get_evolution_suggestions(skill)
        print(f"技能 '{skill.name}' 的进化建议:")
        for suggestion in suggestions:
            print(f"  - {suggestion['message']} (优先级: {suggestion['priority']})")
    
    print("\n=== 测试完成 ===")


if __name__ == "__main__":
    test_a_evolve_integration()
