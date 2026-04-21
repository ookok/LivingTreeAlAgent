"""知识导入器 - 将 agency-agents 角色知识导入到知识库"""

import json
import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass


@dataclass
class RoleKnowledge:
    """角色知识"""
    role_name: str
    domain: str
    skills: List[str]
    workflows: List[str]
    best_practices: List[str]
    common_challenges: List[str]
    resources: List[str]


class KnowledgeImporter:
    """知识导入器"""
    
    def __init__(self, knowledge_base: Dict[str, Any], data_dir: str = "~/.living_tree_ai/agency"):
        """初始化知识导入器"""
        self.knowledge_base = knowledge_base
        self.data_dir = os.path.expanduser(data_dir)
        
        # 确保数据目录存在
        os.makedirs(self.data_dir, exist_ok=True)
        
        # 加载内置角色知识
        self.load_builtin_knowledge()
        
    def load_builtin_knowledge(self):
        """加载内置角色知识"""
        # 内置角色知识定义
        builtin_knowledge = [
            {
                "role_name": "Full Stack Engineer",
                "domain": "engineering",
                "skills": ["Python", "JavaScript", "React", "Django", "API设计", "数据库"],
                "workflows": ["full_stack_dev"],
                "best_practices": [
                    "遵循代码规范",
                    "编写单元测试",
                    "使用版本控制",
                    "文档化代码"
                ],
                "common_challenges": [
                    "技术债务",
                    "需求变更",
                    "性能优化",
                    "安全性"
                ],
                "resources": [
                    "MDN Web Docs",
                    "Stack Overflow",
                    "GitHub",
                    "Python官方文档"
                ]
            },
            {
                "role_name": "UI Designer",
                "domain": "design",
                "skills": ["Figma", "Photoshop", "User Experience", "色彩理论", "排版"],
                "workflows": ["ui_design"],
                "best_practices": [
                    "以用户为中心",
                    "保持一致性",
                    "注重细节",
                    "迭代设计"
                ],
                "common_challenges": [
                    "需求理解",
                    "资源限制",
                    "跨平台适配",
                    "反馈整合"
                ],
                "resources": [
                    "Dribbble",
                    "Behance",
                    "Figma Community",
                    "Material Design"
                ]
            }
        ]
        
        for knowledge_data in builtin_knowledge:
            knowledge = RoleKnowledge(**knowledge_data)
            self.import_role_knowledge(knowledge)
        
        print(f"[KnowledgeImporter] 加载了 {len(builtin_knowledge)} 个内置角色知识")
    
    def import_role_knowledge(self, knowledge: RoleKnowledge):
        """导入角色知识"""
        # 构建知识结构
        role_knowledge = {
            "domain": knowledge.domain,
            "skills": knowledge.skills,
            "workflows": knowledge.workflows,
            "best_practices": knowledge.best_practices,
            "common_challenges": knowledge.common_challenges,
            "resources": knowledge.resources,
            "last_updated": "2026-04-20"
        }
        
        # 存储到知识库
        if "roles" not in self.knowledge_base:
            self.knowledge_base["roles"] = {}
        
        self.knowledge_base["roles"][knowledge.role_name] = role_knowledge
        
        # 同时按领域存储
        if "domains" not in self.knowledge_base:
            self.knowledge_base["domains"] = {}
        
        if knowledge.domain not in self.knowledge_base["domains"]:
            self.knowledge_base["domains"][knowledge.domain] = {
                "roles": [],
                "skills": set(),
                "resources": set()
            }
        
        if knowledge.role_name not in self.knowledge_base["domains"][knowledge.domain]["roles"]:
            self.knowledge_base["domains"][knowledge.domain]["roles"].append(knowledge.role_name)
        
        # 合并技能和资源
        for skill in knowledge.skills:
            self.knowledge_base["domains"][knowledge.domain]["skills"].add(skill)
        
        for resource in knowledge.resources:
            self.knowledge_base["domains"][knowledge.domain]["resources"].add(resource)
        
        # 保存到文件
        self.save_role_knowledge(knowledge)
        
        print(f"[KnowledgeImporter] 导入角色知识: {knowledge.role_name}")
    
    def import_domain_knowledge(self, domain: str, knowledge: Dict[str, Any]):
        """导入领域知识"""
        if "domains" not in self.knowledge_base:
            self.knowledge_base["domains"] = {}
        
        self.knowledge_base["domains"][domain] = {
            **self.knowledge_base["domains"].get(domain, {}),
            **knowledge,
            "last_updated": "2026-04-20"
        }
        
        print(f"[KnowledgeImporter] 导入领域知识: {domain}")
    
    def get_role_knowledge(self, role_name: str) -> Optional[Dict[str, Any]]:
        """获取角色知识"""
        if "roles" in self.knowledge_base:
            return self.knowledge_base["roles"].get(role_name)
        return None
    
    def get_domain_knowledge(self, domain: str) -> Optional[Dict[str, Any]]:
        """获取领域知识"""
        if "domains" in self.knowledge_base:
            return self.knowledge_base["domains"].get(domain)
        return None
    
    def save_role_knowledge(self, knowledge: RoleKnowledge):
        """保存角色知识到文件"""
        knowledge_dir = os.path.join(self.data_dir, "knowledge")
        os.makedirs(knowledge_dir, exist_ok=True)
        
        filename = f"{knowledge.role_name.replace(' ', '_').lower()}.json"
        file_path = os.path.join(knowledge_dir, filename)
        
        knowledge_data = {
            "role_name": knowledge.role_name,
            "domain": knowledge.domain,
            "skills": knowledge.skills,
            "workflows": knowledge.workflows,
            "best_practices": knowledge.best_practices,
            "common_challenges": knowledge.common_challenges,
            "resources": knowledge.resources
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(knowledge_data, f, indent=2, ensure_ascii=False)
    
    def load_role_knowledge(self, knowledge_dir: Optional[str] = None):
        """从文件加载角色知识"""
        if knowledge_dir is None:
            knowledge_dir = os.path.join(self.data_dir, "knowledge")
        
        if not os.path.exists(knowledge_dir):
            print(f"[KnowledgeImporter] 知识目录不存在: {knowledge_dir}")
            return
        
        for filename in os.listdir(knowledge_dir):
            if filename.endswith('.json'):
                file_path = os.path.join(knowledge_dir, filename)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        knowledge_data = json.load(f)
                    
                    knowledge = RoleKnowledge(**knowledge_data)
                    self.import_role_knowledge(knowledge)
                except Exception as e:
                    print(f"[KnowledgeImporter] 加载角色知识失败 {filename}: {e}")
    
    def update_role_knowledge(self, role_name: str, updates: Dict[str, Any]):
        """更新角色知识"""
        if "roles" not in self.knowledge_base or role_name not in self.knowledge_base["roles"]:
            print(f"[KnowledgeImporter] 角色知识不存在: {role_name}")
            return
        
        # 更新知识
        self.knowledge_base["roles"][role_name].update(updates)
        self.knowledge_base["roles"][role_name]["last_updated"] = "2026-04-20"
        
        print(f"[KnowledgeImporter] 更新角色知识: {role_name}")
    
    def delete_role_knowledge(self, role_name: str):
        """删除角色知识"""
        if "roles" in self.knowledge_base and role_name in self.knowledge_base["roles"]:
            # 获取领域信息
            domain = self.knowledge_base["roles"][role_name].get("domain")
            
            # 从知识库中删除
            del self.knowledge_base["roles"][role_name]
            
            # 从领域中移除
            if domain and "domains" in self.knowledge_base and domain in self.knowledge_base["domains"]:
                if role_name in self.knowledge_base["domains"][domain]["roles"]:
                    self.knowledge_base["domains"][domain]["roles"].remove(role_name)
            
            # 删除文件
            knowledge_dir = os.path.join(self.data_dir, "knowledge")
            filename = f"{role_name.replace(' ', '_').lower()}.json"
            file_path = os.path.join(knowledge_dir, filename)
            
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"[KnowledgeImporter] 删除角色知识文件: {file_path}")
            
            print(f"[KnowledgeImporter] 删除角色知识: {role_name}")
