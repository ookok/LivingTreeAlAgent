"""知识集成测试"""

import sys
import os

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from knowledge_integration import KnowledgeIntegrator
from living_tree_ai.knowledge import KnowledgeBase


def test_knowledge_integration():
    """测试知识集成"""
    print("=== 知识集成测试 ===")
    
    # 初始化知识库
    kb = KnowledgeBase("test_node")
    
    # 初始化知识集成器
    integrator = KnowledgeIntegrator(kb, "test_node")
    
    # 测试集成单个角色知识
    print("\n=== 测试集成单个角色知识 ===")
    role_name = "Full Stack Engineer"
    knowledge_ids = integrator.integrate_role_knowledge(role_name)
    print(f"集成 {role_name} 知识: {len(knowledge_ids)} 条")
    
    # 测试集成所有角色知识
    print("\n=== 测试集成所有角色知识 ===")
    integration_results = integrator.integrate_all_roles()
    print(f"集成了 {len(integration_results)} 个角色")
    for role, ids in integration_results.items():
        print(f"  {role}: {len(ids)} 条知识")
    
    # 测试获取已集成的角色
    print("\n=== 测试获取已集成的角色 ===")
    integrated_roles = integrator.get_integrated_roles()
    print(f"已集成的角色: {integrated_roles}")
    
    # 测试获取角色知识统计
    print("\n=== 测试获取角色知识统计 ===")
    stats = integrator.get_role_knowledge_stats()
    print("角色知识统计:")
    for role, count in stats.items():
        print(f"  {role}: {count} 条知识")
    
    # 测试更新角色知识
    print("\n=== 测试更新角色知识 ===")
    update_result = integrator.update_role_knowledge(role_name)
    print(f"更新 {role_name} 知识: {'成功' if update_result else '失败'}")
    
    # 测试移除角色知识
    print("\n=== 测试移除角色知识 ===")
    removed_count = integrator.remove_role_knowledge(role_name)
    print(f"移除 {role_name} 知识: {removed_count} 条")
    
    # 测试知识库统计
    print("\n=== 测试知识库统计 ===")
    kb_stats = kb.get_stats()
    print(f"知识库总知识数: {kb_stats.total_knowledge}")
    print(f"按类型统计: {kb_stats.by_type}")
    print(f"按领域统计: {kb_stats.by_domain}")
    
    print("\n=== 测试完成 ===")


if __name__ == "__main__":
    test_knowledge_integration()
