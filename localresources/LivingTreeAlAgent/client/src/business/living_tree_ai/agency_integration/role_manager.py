"""
角色管理器 - 管理 agency-agents 角色模板

增强版：支持角色能力矩阵、动态角色组合、角色协作工作流
借鉴 agency-agents 专业化分工理念
"""

import json
import os
import uuid
from typing import Dict, List, Optional, Set, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
import numpy as np


class SkillLevel(Enum):
    """技能等级"""
    BEGINNER = 1
    INTERMEDIATE = 2
    ADVANCED = 3
    EXPERT = 4
    MASTER = 5


@dataclass
class Skill:
    """技能定义"""
    name: str
    level: SkillLevel = SkillLevel.INTERMEDIATE
    years_experience: int = 0
    certifications: List[str] = field(default_factory=list)


@dataclass
class SkillMatrix:
    """角色能力矩阵"""
    role_name: str
    skills: Dict[str, Skill] = field(default_factory=dict)
    overall_score: float = 0.0
    updated_at: float = 0

    def calculate_overall_score(self) -> float:
        """计算总分"""
        if not self.skills:
            return 0.0
        total = sum(s.level.value for s in self.skills.values())
        self.overall_score = total / len(self.skills)
        return self.overall_score

    def get_skill_vector(self) -> List[float]:
        """获取技能向量"""
        return [s.level.value for s in self.skills.values()]

    def compare_with(self, other: 'SkillMatrix') -> float:
        """比较两个技能矩阵的相似度"""
        if not self.skills or not other.skills:
            return 0.0

        common_skills = set(self.skills.keys()) & set(other.skills.keys())
        if not common_skills:
            return 0.0

        diff = sum(
            abs(self.skills[s].level.value - other.skills[s].level.value)
            for s in common_skills
        )
        max_diff = len(common_skills) * (SkillLevel.MASTER.value - SkillLevel.BEGINNER.value)

        return 1.0 - (diff / max_diff)


@dataclass
class RoleTemplate:
    """角色模板"""
    name: str
    domain: str
    skills: List[str]
    description: str
    workflow: str
    deliverables: List[str]
    skill_matrix: Optional[SkillMatrix] = None
    collaboration_roles: List[str] = field(default_factory=list)
    max_instances: int = 1


@dataclass
class RoleInstance:
    """角色实例"""
    instance_id: str
    role_name: str
    agent_id: str
    agent_name: str
    workspace_id: Optional[str] = None
    status: str = "idle"
    current_task: Optional[str] = None
    completed_tasks: List[str] = field(default_factory=list)
    skill_matrix: Optional[SkillMatrix] = None


@dataclass
class CollaborationWorkflow:
    """协作工作流"""
    workflow_id: str
    name: str
    description: str
    steps: List['WorkflowStep'] = field(default_factory=list)
    roles_required: List[str] = field(default_factory=list)


@dataclass
class WorkflowStep:
    """工作流步骤"""
    step_id: str
    name: str
    role: str
    action: str
    inputs: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)
    depends_on: List[str] = field(default_factory=list)


class RoleManager:
    """角色管理器 - 增强版"""

    def __init__(self, data_dir: str = "~/.living_tree_ai/agency"):
        """初始化角色管理器"""
        self.data_dir = os.path.expanduser(data_dir)
        self.role_templates: Dict[str, RoleTemplate] = {}
        self.role_nodes: Dict[str, Any] = {}
        self.role_instances: Dict[str, RoleInstance] = {}
        self.collaboration_workflows: Dict[str, CollaborationWorkflow] = {}
        self._skill_definitions: Dict[str, Dict] = {}

        os.makedirs(self.data_dir, exist_ok=True)

        self.load_builtin_templates()
        self.load_builtin_skills()
        self.load_collaboration_workflows()

    def load_builtin_skills(self):
        """加载内置技能定义"""
        self._skill_definitions = {
            "Python": {"category": "programming", "related": ["Django", "Flask", "FastAPI"]},
            "JavaScript": {"category": "programming", "related": ["React", "Vue", "Node.js"]},
            "React": {"category": "frontend", "related": ["JavaScript", "TypeScript"]},
            "TypeScript": {"category": "programming", "related": ["JavaScript", "React"]},
            "SQL": {"category": "database", "related": ["PostgreSQL", "MySQL"]},
            "Data Analysis": {"category": "data", "related": ["Python", "SQL", "Visualization"]},
            "Machine Learning": {"category": "data", "related": ["Python", "Deep Learning"]},
            "Project Management": {"category": "management", "related": ["Agile", "Scrum"]},
            "UI Design": {"category": "design", "related": ["Figma", "User Research"]},
            "Communication": {"category": "soft", "related": []},
            "Leadership": {"category": "soft", "related": []},
            "Problem Solving": {"category": "soft", "related": []},
        }

    def load_builtin_templates(self):
        """加载内置角色模板"""
        builtin_templates = [
            {
                "name": "Full Stack Engineer",
                "domain": "engineering",
                "skills": ["Python", "JavaScript", "React", "SQL"],
                "description": "全栈工程师，负责前后端开发",
                "workflow": "full_stack_dev",
                "deliverables": ["代码", "测试", "文档"],
                "collaboration_roles": ["UI Designer", "Product Manager"],
                "max_instances": 3
            },
            {
                "name": "UI Designer",
                "domain": "design",
                "skills": ["UI Design", "JavaScript", "Communication"],
                "description": "UI设计师，负责用户界面设计",
                "workflow": "ui_design",
                "deliverables": ["设计稿", "原型", "风格指南"],
                "collaboration_roles": ["Full Stack Engineer", "Product Manager"],
                "max_instances": 2
            },
            {
                "name": "Product Manager",
                "domain": "product",
                "skills": ["Project Management", "Communication", "Problem Solving"],
                "description": "产品经理，负责产品规划和管理",
                "workflow": "product_management",
                "deliverables": ["PRD", "用户故事", "产品 roadmap"],
                "collaboration_roles": ["Full Stack Engineer", "UI Designer"],
                "max_instances": 2
            },
            {
                "name": "Data Analyst",
                "domain": "data_analysis",
                "skills": ["Data Analysis", "Python", "SQL"],
                "description": "数据分析师，负责数据分析和可视化",
                "workflow": "data_analysis",
                "deliverables": ["分析报告", "数据可视化", "洞察建议"],
                "collaboration_roles": ["Product Manager"],
                "max_instances": 2
            },
            {
                "name": "Marketing Specialist",
                "domain": "marketing",
                "skills": ["Communication", "Problem Solving", "Leadership"],
                "description": "营销专家，负责市场推广",
                "workflow": "marketing",
                "deliverables": ["营销计划", "内容策略", "推广方案"],
                "collaboration_roles": ["Product Manager"],
                "max_instances": 2
            },
            {
                "name": "AI Research Engineer",
                "domain": "ai",
                "skills": ["Python", "Machine Learning", "Problem Solving"],
                "description": "AI研究工程师，负责算法研发",
                "workflow": "ai_research",
                "deliverables": ["算法模型", "技术报告", "论文"],
                "collaboration_roles": ["Data Analyst", "Full Stack Engineer"],
                "max_instances": 2
            },
            {
                "name": "DevOps Engineer",
                "domain": "infrastructure",
                "skills": ["Python", "Problem Solving"],
                "description": "DevOps工程师，负责运维和自动化",
                "workflow": "devops",
                "deliverables": ["部署脚本", "监控配置", "文档"],
                "collaboration_roles": ["Full Stack Engineer"],
                "max_instances": 2
            },
            {
                "name": "QA Engineer",
                "domain": "quality",
                "skills": ["Problem Solving", "Communication"],
                "description": "测试工程师，负责质量保证",
                "workflow": "qa_testing",
                "deliverables": ["测试计划", "测试报告", "Bug列表"],
                "collaboration_roles": ["Full Stack Engineer"],
                "max_instances": 3
            }
        ]

        for template_data in builtin_templates:
            skills = template_data.get("skills", [])
            skill_matrix = SkillMatrix(
                role_name=template_data["name"],
                skills={
                    s: Skill(name=s, level=SkillLevel.INTERMEDIATE)
                    for s in skills
                }
            )
            skill_matrix.calculate_overall_score()

            template = RoleTemplate(
                skill_matrix=skill_matrix,
                **template_data
            )
            self.role_templates[template.name] = template

        print(f"[RoleManager] 加载了 {len(builtin_templates)} 个内置角色模板")

    def load_collaboration_workflows(self):
        """加载协作工作流"""
        workflows = [
            {
                "workflow_id": "product_development",
                "name": "产品开发流程",
                "description": "从需求到交付的完整协作流程",
                "steps": [
                    {"step_id": "1", "name": "需求分析", "role": "Product Manager",
                     "action": "analyze_requirements", "inputs": [], "outputs": ["PRD"]},
                    {"step_id": "2", "name": "UI设计", "role": "UI Designer",
                     "action": "design_ui", "inputs": ["PRD"], "outputs": ["设计稿"]},
                    {"step_id": "3", "name": "架构设计", "role": "Full Stack Engineer",
                     "action": "design_architecture", "inputs": ["PRD"], "outputs": ["架构文档"]},
                    {"step_id": "4", "name": "前端开发", "role": "Full Stack Engineer",
                     "action": "develop_frontend", "inputs": ["设计稿", "架构文档"], "outputs": ["前端代码"]},
                    {"step_id": "5", "name": "后端开发", "role": "Full Stack Engineer",
                     "action": "develop_backend", "inputs": ["架构文档"], "outputs": ["后端代码"]},
                    {"step_id": "6", "name": "测试", "role": "QA Engineer",
                     "action": "test_features", "inputs": ["前端代码", "后端代码"], "outputs": ["测试报告"]},
                ],
                "roles_required": ["Product Manager", "UI Designer", "Full Stack Engineer", "QA Engineer"]
            },
            {
                "workflow_id": "ai_project",
                "name": "AI项目流程",
                "description": "AI项目从研究到部署的流程",
                "steps": [
                    {"step_id": "1", "name": "需求分析", "role": "Product Manager",
                     "action": "analyze_ai_requirements", "inputs": [], "outputs": ["AI需求文档"]},
                    {"step_id": "2", "name": "数据准备", "role": "Data Analyst",
                     "action": "prepare_data", "inputs": ["AI需求文档"], "outputs": ["训练数据"]},
                    {"step_id": "3", "name": "模型研究", "role": "AI Research Engineer",
                     "action": "research_model", "inputs": ["AI需求文档"], "outputs": ["模型设计"]},
                    {"step_id": "4", "name": "模型训练", "role": "AI Research Engineer",
                     "action": "train_model", "inputs": ["训练数据", "模型设计"], "outputs": ["训练模型"]},
                    {"step_id": "5", "name": "后端集成", "role": "Full Stack Engineer",
                     "action": "integrate_model", "inputs": ["训练模型"], "outputs": ["API服务"]},
                ],
                "roles_required": ["Product Manager", "Data Analyst", "AI Research Engineer", "Full Stack Engineer"]
            }
        ]

        for wf_data in workflows:
            steps = [WorkflowStep(**s) for s in wf_data["steps"]]
            workflow = CollaborationWorkflow(
                workflow_id=wf_data["workflow_id"],
                name=wf_data["name"],
                description=wf_data["description"],
                steps=steps,
                roles_required=wf_data["roles_required"]
            )
            self.collaboration_workflows[workflow.workflow_id] = workflow

        print(f"[RoleManager] 加载了 {len(workflows)} 个协作工作流")

    def create_role_instance(
        self,
        role_name: str,
        agent_id: str,
        agent_name: str,
        workspace_id: Optional[str] = None
    ) -> Optional[RoleInstance]:
        """创建角色实例"""
        if role_name not in self.role_templates:
            print(f"[RoleManager] 角色不存在: {role_name}")
            return None

        template = self.role_templates[role_name]

        existing_count = sum(
            1 for inst in self.role_instances.values()
            if inst.role_name == role_name
        )
        if existing_count >= template.max_instances:
            print(f"[RoleManager] 角色 {role_name} 已达到最大实例数 {template.max_instances}")
            return None

        instance_id = str(uuid.uuid4())

        skill_matrix = None
        if template.skill_matrix:
            skill_matrix = SkillMatrix(
                role_name=role_name,
                skills={
                    s.name: Skill(
                        name=s.name,
                        level=s.level,
                        years_experience=s.years_experience,
                        certifications=s.certifications.copy()
                    )
                    for s in template.skill_matrix.skills.values()
                }
            )

        instance = RoleInstance(
            instance_id=instance_id,
            role_name=role_name,
            agent_id=agent_id,
            agent_name=agent_name,
            workspace_id=workspace_id,
            skill_matrix=skill_matrix
        )

        self.role_instances[instance_id] = instance
        print(f"[RoleManager] 创建角色实例: {role_name} - {agent_name} ({instance_id})")

        return instance

    def get_role_instance(self, instance_id: str) -> Optional[RoleInstance]:
        """获取角色实例"""
        return self.role_instances.get(instance_id)

    def get_agent_roles(self, agent_id: str) -> List[RoleInstance]:
        """获取 Agent 的所有角色"""
        return [
            inst for inst in self.role_instances.values()
            if inst.agent_id == agent_id
        ]

    def release_role_instance(self, instance_id: str) -> bool:
        """释放角色实例"""
        if instance_id in self.role_instances:
            del self.role_instances[instance_id]
            return True
        return False

    def find_compatible_roles(
        self,
        role_name: str,
        min_similarity: float = 0.6
    ) -> List[tuple]:
        """查找兼容的角色（用于角色替换）"""
        if role_name not in self.role_templates:
            return []

        template = self.role_templates[role_name]
        if not template.skill_matrix:
            return []

        compatible = []

        for other_name, other_template in self.role_templates.items():
            if other_name == role_name:
                continue

            if not other_template.skill_matrix:
                continue

            similarity = template.skill_matrix.compare_with(other_template.skill_matrix)

            if similarity >= min_similarity:
                compatible.append((other_name, similarity))

        compatible.sort(key=lambda x: x[1], reverse=True)
        return compatible

    def get_collaboration_team(
        self,
        workflow_id: str
    ) -> List[str]:
        """获取协作团队角色列表"""
        workflow = self.collaboration_workflows.get(workflow_id)
        if not workflow:
            return []
        return workflow.roles_required

    def auto_assign_roles(
        self,
        task_description: str,
        available_agents: List[tuple]
    ) -> List[tuple]:
        """
        自动分配角色

        Args:
            task_description: 任务描述
            available_agents: 可用 Agent 列表 [(agent_id, agent_name), ...]

        Returns:
            List[tuple]: 分配的角色 [(role_name, agent_id), ...]
        """
        task_keywords = task_description.lower().split()

        role_scores = {}
        for role_name, template in self.role_templates.items():
            score = 0
            for keyword in task_keywords:
                if keyword in template.description.lower():
                    score += 2
                if keyword in template.domain.lower():
                    score += 1
                for skill in template.skills:
                    if keyword in skill.lower():
                        score += 1.5

            if score > 0:
                role_scores[role_name] = score

        sorted_roles = sorted(role_scores.items(), key=lambda x: x[1], reverse=True)

        assignments = []
        assigned_agents = set()

        for role_name, score in sorted_roles:
            if len(assignments) >= len(available_agents):
                break

            for agent_id, agent_name in available_agents:
                if agent_id in assigned_agents:
                    continue

                instance = self.create_role_instance(
                    role_name=role_name,
                    agent_id=agent_id,
                    agent_name=agent_name
                )

                if instance:
                    assignments.append((role_name, agent_id, instance.instance_id))
                    assigned_agents.add(agent_id)
                    break

        return assignments

    def get_skill_radar_data(self, role_name: str) -> Optional[Dict]:
        """获取技能雷达图数据"""
        if role_name not in self.role_templates:
            return None

        template = self.role_templates[role_name]
        if not template.skill_matrix:
            return None

        return {
            "labels": list(template.skill_matrix.skills.keys()),
            "values": [s.level.value for s in template.skill_matrix.skills.values()],
            "overall_score": template.skill_matrix.overall_score
        }

    def create_composite_role(
        self,
        name: str,
        base_roles: List[str],
        priority_weights: Optional[Dict[str, float]] = None
    ) -> Optional[RoleTemplate]:
        """
        创建复合角色

        Args:
            name: 复合角色名称
            base_roles: 基础角色列表
            priority_weights: 优先级权重

        Returns:
            Optional[RoleTemplate]: 复合角色模板
        """
        if not base_roles:
            return None

        all_skills = {}
        weights = priority_weights or {}

        for role_name in base_roles:
            if role_name not in self.role_templates:
                continue

            template = self.role_templates[role_name]
            weight = weights.get(role_name, 1.0)

            for skill_name, skill in template.skill_matrix.skills.items():
                if skill_name in all_skills:
                    existing = all_skills[skill_name]
                    existing.level = max(existing.level, SkillLevel(
                        min(int(existing.level.value * weight), SkillLevel.MASTER.value)
                    ))
                else:
                    all_skills[skill_name] = Skill(
                        name=skill_name,
                        level=skill_level_from_value(
                            int(skill.level.value * weight)
                        )
                    )

        skill_matrix = SkillMatrix(
            role_name=name,
            skills=all_skills
        )
        skill_matrix.calculate_overall_score()

        composite = RoleTemplate(
            name=name,
            domain="composite",
            skills=list(all_skills.keys()),
            description=f"复合角色：{' + '.join(base_roles)}",
            workflow="composite",
            deliverables=["综合输出"],
            skill_matrix=skill_matrix,
            collaboration_roles=list(set(
                r for role in base_roles
                if role in self.role_templates
                for r in self.role_templates[role].collaboration_roles
            ))
        )

        self.role_templates[name] = composite
        return composite

    def load_role_templates(self, templates_dir: Optional[str] = None):
        """从目录加载角色模板"""
        if templates_dir is None:
            templates_dir = os.path.join(self.data_dir, "role_templates")

        if not os.path.exists(templates_dir):
            return

        for filename in os.listdir(templates_dir):
            if filename.endswith('.json'):
                file_path = os.path.join(templates_dir, filename)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        template_data = json.load(f)
                    template = RoleTemplate(**template_data)
                    self.role_templates[template.name] = template
                except Exception as e:
                    print(f"[RoleManager] 加载失败 {filename}: {e}")

    def create_role_node(self, role_name: str):
        """根据角色创建专业节点"""
        if role_name not in self.role_templates:
            return None
        return self.role_templates[role_name]

    def get_role_by_domain(self, domain: str) -> List[str]:
        """根据领域获取角色列表"""
        return [
            name for name, template in self.role_templates.items()
            if template.domain == domain
        ]

    def get_all_roles(self) -> List[str]:
        """获取所有角色"""
        return list(self.role_templates.keys())

    def get_role_template(self, role_name: str) -> Optional[RoleTemplate]:
        """获取角色模板"""
        return self.role_templates.get(role_name)

    def save_role_template(self, template: RoleTemplate):
        """保存角色模板"""
        templates_dir = os.path.join(self.data_dir, "role_templates")
        os.makedirs(templates_dir, exist_ok=True)

        filename = f"{template.name.replace(' ', '_').lower()}.json"
        file_path = os.path.join(templates_dir, filename)

        template_data = {
            "name": template.name,
            "domain": template.domain,
            "skills": template.skills,
            "description": template.description,
            "workflow": template.workflow,
            "deliverables": template.deliverables,
            "collaboration_roles": template.collaboration_roles,
            "max_instances": template.max_instances
        }

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(template_data, f, indent=2, ensure_ascii=False)

        self.role_templates[template.name] = template
        print(f"[RoleManager] 保存角色模板: {template.name}")

    def delete_role_template(self, role_name: str):
        """删除角色模板"""
        if role_name in self.role_templates:
            del self.role_templates[role_name]
            print(f"[RoleManager] 删除角色模板: {role_name}")


def skill_level_from_value(value: int) -> SkillLevel:
    """从数值获取技能等级"""
    return SkillLevel(max(1, min(5, value)))


_global_manager: Optional[RoleManager] = None


def get_role_manager() -> RoleManager:
    """获取角色管理器"""
    global _global_manager
    if _global_manager is None:
        _global_manager = RoleManager()
    return _global_manager
