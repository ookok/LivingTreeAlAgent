"""知识集成模块 - 将 agency-agents 角色知识集成到 LivingTreeAI 知识系统"""

import sys
import os

# 添加父目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Dict, List, Optional
from knowledge import KnowledgeBase, KnowledgeEntry, KnowledgeType, KnowledgeLicense
from knowledge_importer import KnowledgeImporter, RoleKnowledge


class KnowledgeIntegrator:
    """知识集成器"""
    
    def __init__(self, knowledge_base: KnowledgeBase, node_id: str):
        """初始化知识集成器"""
        self.knowledge_base = knowledge_base
        self.node_id = node_id
        self.knowledge_importer = KnowledgeImporter({})
    
    def integrate_role_knowledge(self, role_name: str) -> List[str]:
        """集成角色知识到知识库"""
        # 获取角色知识
        role_knowledge = self.knowledge_importer.get_role_knowledge(role_name)
        if not role_knowledge:
            print(f"[KnowledgeIntegrator] 角色知识不存在: {role_name}")
            return []
        
        knowledge_ids = []
        
        # 集成技能知识
        skills_entry = KnowledgeEntry(
            knowledge_id=f"skill_{role_name.replace(' ', '_').lower()}",
            knowledge_type=KnowledgeType.SKILL,
            title=f"{role_name} 技能",
            content={
                "skills": role_knowledge.get("skills", []),
                "domain": role_knowledge.get("domain", ""),
                "role": role_name
            },
            source_node=self.node_id,
            license=KnowledgeLicense.OPEN,
            tags=[role_knowledge.get("domain", ""), "skill", "role"],
            domain=role_knowledge.get("domain", ""),
            confidence=0.9,
            contributors=[self.node_id]
        )
        skill_id = self.knowledge_base.add(skills_entry)
        knowledge_ids.append(skill_id)
        
        # 集成最佳实践知识
        best_practices = role_knowledge.get("best_practices", [])
        if best_practices:
            best_practices_entry = KnowledgeEntry(
                knowledge_id=f"practice_{role_name.replace(' ', '_').lower()}",
                knowledge_type=KnowledgeType.REASONING_PATTERN,
                title=f"{role_name} 最佳实践",
                content={
                    "practices": best_practices,
                    "role": role_name
                },
                source_node=self.node_id,
                license=KnowledgeLicense.OPEN,
                tags=[role_knowledge.get("domain", ""), "practice", "role"],
                domain=role_knowledge.get("domain", ""),
                confidence=0.85,
                contributors=[self.node_id]
            )
            practice_id = self.knowledge_base.add(best_practices_entry)
            knowledge_ids.append(practice_id)
        
        # 集成常见挑战知识
        common_challenges = role_knowledge.get("common_challenges", [])
        if common_challenges:
            challenges_entry = KnowledgeEntry(
                knowledge_id=f"challenge_{role_name.replace(' ', '_').lower()}",
                knowledge_type=KnowledgeType.REASONING_PATTERN,
                title=f"{role_name} 常见挑战",
                content={
                    "challenges": common_challenges,
                    "role": role_name
                },
                source_node=self.node_id,
                license=KnowledgeLicense.OPEN,
                tags=[role_knowledge.get("domain", ""), "challenge", "role"],
                domain=role_knowledge.get("domain", ""),
                confidence=0.8,
                contributors=[self.node_id]
            )
            challenge_id = self.knowledge_base.add(challenges_entry)
            knowledge_ids.append(challenge_id)
        
        # 集成资源知识
        resources = role_knowledge.get("resources", [])
        if resources:
            resources_entry = KnowledgeEntry(
                knowledge_id=f"resource_{role_name.replace(' ', '_').lower()}",
                knowledge_type=KnowledgeType.FACT,
                title=f"{role_name} 资源",
                content={
                    "resources": resources,
                    "role": role_name
                },
                source_node=self.node_id,
                license=KnowledgeLicense.OPEN,
                tags=[role_knowledge.get("domain", ""), "resource", "role"],
                domain=role_knowledge.get("domain", ""),
                confidence=0.95,
                contributors=[self.node_id]
            )
            resource_id = self.knowledge_base.add(resources_entry)
            knowledge_ids.append(resource_id)
        
        print(f"[KnowledgeIntegrator] 集成角色知识 {role_name}: {len(knowledge_ids)} 条知识")
        return knowledge_ids
    
    def integrate_all_roles(self) -> Dict[str, List[str]]:
        """集成所有角色知识"""
        integration_results = {}
        
        # 获取所有角色
        roles = self.knowledge_importer.knowledge_base.get("roles", {})
        for role_name in roles:
            knowledge_ids = self.integrate_role_knowledge(role_name)
            integration_results[role_name] = knowledge_ids
        
        print(f"[KnowledgeIntegrator] 集成了 {len(integration_results)} 个角色的知识")
        return integration_results
    
    def update_role_knowledge(self, role_name: str) -> bool:
        """更新角色知识"""
        # 先删除旧知识
        self.remove_role_knowledge(role_name)
        
        # 重新集成
        knowledge_ids = self.integrate_role_knowledge(role_name)
        return len(knowledge_ids) > 0
    
    def remove_role_knowledge(self, role_name: str) -> int:
        """移除角色知识"""
        removed_count = 0
        role_key = role_name.replace(' ', '_').lower()
        
        # 查找并删除相关知识
        knowledge_ids_to_remove = []
        for knowledge_id, entry in self.knowledge_base.entries.items():
            if role_key in knowledge_id or role_name in str(entry.content):
                knowledge_ids_to_remove.append(knowledge_id)
        
        for knowledge_id in knowledge_ids_to_remove:
            if self.knowledge_base.delete(knowledge_id):
                removed_count += 1
        
        print(f"[KnowledgeIntegrator] 移除角色知识 {role_name}: {removed_count} 条知识")
        return removed_count
    
    def get_integrated_roles(self) -> List[str]:
        """获取已集成的角色列表"""
        integrated_roles = set()
        
        for entry in self.knowledge_base.entries.values():
            if "role" in entry.tags:
                # 从内容中提取角色名称
                content = entry.content
                if isinstance(content, dict) and "role" in content:
                    integrated_roles.add(content["role"])
        
        return list(integrated_roles)
    
    def get_role_knowledge_stats(self) -> Dict[str, int]:
        """获取角色知识统计"""
        stats = {}
        
        for entry in self.knowledge_base.entries.values():
            if "role" in entry.tags:
                content = entry.content
                if isinstance(content, dict) and "role" in content:
                    role_name = content["role"]
                    stats[role_name] = stats.get(role_name, 0) + 1
        
        return stats
