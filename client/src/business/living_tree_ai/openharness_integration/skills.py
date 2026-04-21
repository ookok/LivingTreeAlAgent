"""OpenHarness 技能系统集成"""

import os
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


@dataclass
class Skill:
    """技能定义"""
    name: str
    description: str
    knowledge: Dict[str, Any]
    dependencies: List[str] = None
    version: str = "1.0.0"


class SkillSystem:
    """OpenHarness 技能系统"""
    
    def __init__(self, skills_dir: str = "~/.living_tree_ai/openharness/skills"):
        """初始化技能系统"""
        self.skills_dir = os.path.expanduser(skills_dir)
        self.skills: Dict[str, Skill] = {}
        self._ensure_skills_dir()
        self._load_builtin_skills()
    
    def _ensure_skills_dir(self):
        """确保技能目录存在"""
        os.makedirs(self.skills_dir, exist_ok=True)
    
    def _load_builtin_skills(self):
        """加载内置技能"""
        # 内置技能定义
        builtin_skills = [
            {
                "name": "web_search",
                "description": "网络搜索技能",
                "knowledge": {
                    "tools": ["search_web"],
                    "prompt": "使用网络搜索工具获取最新信息",
                    "examples": [
                        "搜索最新的 Python 3.12 特性",
                        "查找如何使用 OpenAI API"
                    ]
                },
                "dependencies": []
            },
            {
                "name": "code_generation",
                "description": "代码生成技能",
                "knowledge": {
                    "tools": ["write_file", "run_command"],
                    "prompt": "根据需求生成代码并测试",
                    "examples": [
                        "生成一个 Python 函数来计算斐波那契数列",
                        "创建一个简单的 HTTP 服务器"
                    ]
                },
                "dependencies": []
            },
            {
                "name": "data_analysis",
                "description": "数据分析技能",
                "knowledge": {
                    "tools": ["read_file", "run_command"],
                    "prompt": "分析数据并生成报告",
                    "examples": [
                        "分析销售数据并生成图表",
                        "统计用户行为数据"
                    ]
                },
                "dependencies": []
            }
        ]
        
        for skill_data in builtin_skills:
            skill = Skill(**skill_data)
            self.skills[skill.name] = skill
            self._save_skill(skill)
        
        print(f"[SkillSystem] 加载了 {len(builtin_skills)} 个内置技能")
    
    def load_skill(self, skill_name: str) -> Optional[Skill]:
        """加载技能"""
        # 检查内存中是否已加载
        if skill_name in self.skills:
            return self.skills[skill_name]
        
        # 从文件加载
        skill_file = os.path.join(self.skills_dir, f"{skill_name}.json")
        if os.path.exists(skill_file):
            try:
                with open(skill_file, 'r', encoding='utf-8') as f:
                    skill_data = json.load(f)
                skill = Skill(**skill_data)
                self.skills[skill_name] = skill
                print(f"[SkillSystem] 加载技能: {skill_name}")
                return skill
            except Exception as e:
                print(f"[SkillSystem] 加载技能失败 {skill_name}: {e}")
                return None
        
        print(f"[SkillSystem] 技能不存在: {skill_name}")
        return None
    
    def register_skill(self, skill: Skill):
        """注册技能"""
        self.skills[skill.name] = skill
        self._save_skill(skill)
        print(f"[SkillSystem] 注册技能: {skill.name} - {skill.description}")
    
    def get_skill(self, skill_name: str) -> Optional[Skill]:
        """获取技能"""
        return self.load_skill(skill_name)
    
    def get_all_skills(self) -> List[Dict[str, Any]]:
        """获取所有技能"""
        return [
            {
                "name": skill.name,
                "description": skill.description,
                "version": skill.version,
                "dependencies": skill.dependencies
            }
            for skill in self.skills.values()
        ]
    
    def get_skill_by_tool(self, tool_name: str) -> List[str]:
        """根据工具获取使用该工具的技能"""
        skills = []
        for skill_name, skill in self.skills.items():
            tools = skill.knowledge.get("tools", [])
            if tool_name in tools:
                skills.append(skill_name)
        return skills
    
    def _save_skill(self, skill: Skill):
        """保存技能到文件"""
        skill_data = {
            "name": skill.name,
            "description": skill.description,
            "knowledge": skill.knowledge,
            "dependencies": skill.dependencies,
            "version": skill.version
        }
        
        skill_file = os.path.join(self.skills_dir, f"{skill.name}.json")
        with open(skill_file, 'w', encoding='utf-8') as f:
            json.dump(skill_data, f, indent=2, ensure_ascii=False)
    
    def delete_skill(self, skill_name: str):
        """删除技能"""
        if skill_name in self.skills:
            del self.skills[skill_name]
            
            # 删除文件
            skill_file = os.path.join(self.skills_dir, f"{skill_name}.json")
            if os.path.exists(skill_file):
                os.remove(skill_file)
                print(f"[SkillSystem] 删除技能文件: {skill_file}")
            
            print(f"[SkillSystem] 删除技能: {skill_name}")
        else:
            print(f"[SkillSystem] 技能不存在: {skill_name}")
    
    def update_skill(self, skill: Skill):
        """更新技能"""
        self.register_skill(skill)
        print(f"[SkillSystem] 更新技能: {skill.name}")
