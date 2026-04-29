"""简化的知识集成测试"""

import sys
import os

# 添加必要的路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 直接导入必要的模块
from knowledge import KnowledgeBase, KnowledgeEntry, KnowledgeType, KnowledgeLicense
from agency_integration.knowledge_importer import KnowledgeImporter, RoleKnowledge


def test_knowledge_integration():
    """测试知识集成"""
    print("=== 简化知识集成测试 ===")
    
    # 初始化知识库
    kb = KnowledgeBase("test_node")
    
    # 初始化知识导入器
    knowledge_importer = KnowledgeImporter({})
    
    # 测试获取角色知识
    print("\n=== 测试获取角色知识 ===")
    roles = knowledge_importer.knowledge_base.get("roles", {})
    print(f"可用角色: {list(roles.keys())}")
    
    # 测试集成角色知识到知识库
    print("\n=== 测试集成角色知识到知识库 ===")
    for role_name, role_data in roles.items():
        print(f"\n集成角色: {role_name}")
        
        # 集成技能知识
        skills_entry = KnowledgeEntry(
            knowledge_id=f"skill_{role_name.replace(' ', '_').lower()}",
            knowledge_type=KnowledgeType.SKILL,
            title=f"{role_name} 技能",
            content={
                "skills": role_data.get("skills", []),
                "domain": role_data.get("domain", ""),
                "role": role_name
            },
            source_node="test_node",
            license=KnowledgeLicense.OPEN,
            tags=[role_data.get("domain", ""), "skill", "role"],
            domain=role_data.get("domain", ""),
            confidence=0.9,
            contributors=["test_node"]
        )
        skill_id = kb.add(skills_entry)
        print(f"  添加技能知识: {skill_id}")
        
        # 集成最佳实践知识
        best_practices = role_data.get("best_practices", [])
        if best_practices:
            best_practices_entry = KnowledgeEntry(
                knowledge_id=f"practice_{role_name.replace(' ', '_').lower()}",
                knowledge_type=KnowledgeType.REASONING_PATTERN,
                title=f"{role_name} 最佳实践",
                content={
                    "practices": best_practices,
                    "role": role_name
                },
                source_node="test_node",
                license=KnowledgeLicense.OPEN,
                tags=[role_data.get("domain", ""), "practice", "role"],
                domain=role_data.get("domain", ""),
                confidence=0.85,
                contributors=["test_node"]
            )
            practice_id = kb.add(best_practices_entry)
            print(f"  添加最佳实践知识: {practice_id}")
    
    # 测试知识库统计
    print("\n=== 测试知识库统计 ===")
    stats = kb.get_stats()
    print(f"知识库总知识数: {stats.total_knowledge}")
    print(f"按类型统计: {stats.by_type}")
    print(f"按领域统计: {stats.by_domain}")
    
    print("\n=== 测试完成 ===")


if __name__ == "__main__":
    test_knowledge_integration()
