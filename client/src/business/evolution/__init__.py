"""
Full migration complete. → livingtree.core.evolution_extra

核心功能：经验系统、技能评估、策略引擎、进化日志、技能发现
"""

from typing import List, Optional, Dict, Any

from .experience_system import (
    ExperienceSystem,
    Experience,
    SkillUsage,
    HumanFeedback,
    TaskType,
    FeedbackType,
    ExperienceSummary
)

from .skill_evaluator import (
    SkillEvaluator,
    Skill,
    SkillMetric,
    SkillExample,
    SkillCategory,
    SkillStatus
)

from .policy_engine import (
    PolicyEngine,
    Policy,
    PolicyRule,
    PolicyInsight,
    PolicyType,
    PolicyAction
)

from .evolution_logger import (
    EvolutionLogger,
    EvolutionEvent,
    EvolutionPhase,
    EvolutionEventType,
    EvolutionImpact
)

from .skill_discovery import (
    SkillDiscoveryEngine,
    PatternMatch,
    DiscoveryResult
)

class EvolutionSystem:
    def __init__(self, data_path: str = "./data/evolution"):
        self.experience_system = ExperienceSystem(f"{data_path}/experiences")
        self.skill_evaluator = SkillEvaluator(f"{data_path}/skills")
        self.policy_engine = PolicyEngine(f"{data_path}/policies")
        self.evolution_logger = EvolutionLogger(f"{data_path}/logs")
        self.skill_discovery = SkillDiscoveryEngine(
            self.experience_system,
            self.skill_evaluator
        )
        
        self._initialize_default_skills()
    
    def _initialize_default_skills(self):
        default_skills = [
            Skill(
                name="generate_code",
                description="根据需求描述生成代码",
                category=SkillCategory.CODE,
                input_schema={
                    "type": "object",
                    "properties": {
                        "requirements": {"type": "string", "description": "代码需求描述"},
                        "language": {"type": "string", "description": "目标编程语言"},
                        "framework": {"type": "string", "description": "目标框架"}
                    },
                    "required": ["requirements"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "code": {"type": "string", "description": "生成的代码"},
                        "file_path": {"type": "string", "description": "建议的文件路径"}
                    }
                },
                examples=[
                    SkillExample(
                        input={"requirements": "创建一个用户登录API", "language": "Python", "framework": "FastAPI"},
                        output={"code": "from fastapi import FastAPI\n...", "file_path": "app/api/auth.py"},
                        description="生成FastAPI登录接口"
                    )
                ],
                status=SkillStatus.ACTIVE,
                version="1.0.0"
            ),
            Skill(
                name="write_document",
                description="根据大纲和上下文编写技术文档",
                category=SkillCategory.DOCUMENT,
                input_schema={
                    "type": "object",
                    "properties": {
                        "outline": {"type": "array", "items": {"type": "string"}, "description": "文档大纲"},
                        "context": {"type": "string", "description": "上下文信息"},
                        "style": {"type": "string", "description": "写作风格"}
                    },
                    "required": ["outline"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "content": {"type": "string", "description": "文档内容"},
                        "sections": {"type": "array", "items": {"type": "string"}}
                    }
                },
                examples=[
                    SkillExample(
                        input={"outline": ["项目概述", "技术架构", "API说明"], "context": "员工管理系统", "style": "技术文档"},
                        output={"content": "# 员工管理系统文档\n...", "sections": ["项目概述", "技术架构", "API说明"]},
                        description="编写技术方案文档"
                    )
                ],
                status=SkillStatus.ACTIVE,
                version="1.0.0"
            ),
            Skill(
                name="analyze_data",
                description="分析数据并提取洞察",
                category=SkillCategory.ANALYSIS,
                input_schema={
                    "type": "object",
                    "properties": {
                        "data": {"type": "object", "description": "待分析的数据"},
                        "analysis_type": {"type": "string", "description": "分析类型"},
                        "parameters": {"type": "object", "description": "分析参数"}
                    },
                    "required": ["data"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "insights": {"type": "array", "items": {"type": "string"}, "description": "洞察列表"},
                        "visualizations": {"type": "array", "items": {"type": "string"}}
                    }
                },
                examples=[
                    SkillExample(
                        input={"data": {"sales": [100, 200, 150]}, "analysis_type": "trend", "parameters": {}},
                        output={"insights": ["销售呈上升趋势"], "visualizations": []},
                        description="销售数据分析"
                    )
                ],
                status=SkillStatus.ACTIVE,
                version="1.0.0"
            ),
            Skill(
                name="create_ui_component",
                description="创建UI组件",
                category=SkillCategory.UI,
                input_schema={
                    "type": "object",
                    "properties": {
                        "component_type": {"type": "string", "description": "组件类型"},
                        "props": {"type": "object", "description": "组件属性"},
                        "framework": {"type": "string", "description": "前端框架"}
                    },
                    "required": ["component_type"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "code": {"type": "string", "description": "组件代码"},
                        "preview": {"type": "string", "description": "预览HTML"}
                    }
                },
                examples=[
                    SkillExample(
                        input={"component_type": "table", "props": {"columns": ["name", "age"]}, "framework": "Vue"},
                        output={"code": "<template>...</template>", "preview": "<table>...</table>"},
                        description="创建Vue表格组件"
                    )
                ],
                status=SkillStatus.ACTIVE,
                version="1.0.0"
            )
        ]
        
        for skill in default_skills:
            if not self.skill_evaluator.get_skill(skill.name):
                self.skill_evaluator.register_skill(skill)
    
    def record_experience(
        self,
        task_type: TaskType,
        task_description: str,
        skills_used: List[SkillUsage],
        success: bool,
        execution_time: float,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        experience_id = self.experience_system.record_experience(
            task_type=task_type,
            task_description=task_description,
            skills_used=skills_used,
            success=success,
            execution_time=execution_time,
            metadata=metadata
        )
        
        self.evolution_logger.log_experience(experience_id, task_type.value, success)
        
        for su in skills_used:
            self.skill_evaluator.record_usage(su.skill_name, su.success, su.execution_time)
        
        return experience_id
    
    def add_feedback(self, experience_id: str, feedback: HumanFeedback):
        self.experience_system.add_feedback(experience_id, feedback)
        self.evolution_logger.log_feedback(feedback.feedback_type.value, feedback.rating)
        
        insights = self.policy_engine.analyze_experience({
            "experience_id": experience_id,
            "task_type": self._get_experience_task_type(experience_id),
            "success": self._get_experience_success(experience_id),
            "human_feedback": {
                "feedback_type": feedback.feedback_type.value,
                "rating": feedback.rating,
                "comments": feedback.comments
            }
        })
        
        if insights:
            self.policy_engine.update_policy(insights)
            for insight in insights:
                self.evolution_logger.log_insight(insight.insight_id, {
                    "description": insight.description,
                    "policy_name": insight.policy_name,
                    "confidence": insight.confidence
                })
    
    def _get_experience_task_type(self, experience_id: str) -> str:
        for exp in self.experience_system.experiences:
            if exp.experience_id == experience_id:
                return exp.task_type.value
        return "other"
    
    def _get_experience_success(self, experience_id: str) -> bool:
        for exp in self.experience_system.experiences:
            if exp.experience_id == experience_id:
                return exp.success
        return False
    
    def run_skill_discovery(self) -> DiscoveryResult:
        result = self.skill_discovery.run_full_discovery()
        
        for skill in result.new_skills:
            self.evolution_logger.log_skill_learned(skill.name, {
                "description": skill.description,
                "category": skill.category.value
            })
        
        for improvement in result.improved_skills:
            self.evolution_logger.log_skill_improved(improvement["skill_name"], improvement["suggestion"])
        
        return result
    
    def get_evolution_summary(self, days: int = 7) -> Dict[str, Any]:
        return {
            "experience_summary": self.experience_system.get_summary(),
            "skill_summary": {
                "total_skills": len(self.skill_evaluator.get_all_skills()),
                "top_skills": self.skill_evaluator.get_top_performing_skills(5),
                "low_performing": self.skill_evaluator.get_low_performing_skills()
            },
            "policy_summary": {
                "total_policies": len(self.policy_engine.policies),
                "suggestions": self.policy_engine.suggest_policy_changes()
            },
            "evolution_summary": self.evolution_logger.get_evolution_summary(days)
        }
    
    def suggest_skills(self, task_description: str) -> List[Dict[str, Any]]:
        return self.skill_discovery.suggest_skill_combination(task_description)
    
    def get_recent_events(self, limit: int = 20) -> List[EvolutionEvent]:
        return self.evolution_logger.get_recent_events(limit)
    
    def export_data(self) -> Dict[str, Any]:
        return {
            "experiences": [exp.experience_id for exp in self.experience_system.experiences],
            "skills": [skill.name for skill in self.skill_evaluator.get_all_skills()],
            "policies": list(self.policy_engine.policies.keys()),
            "events_count": len(self.evolution_logger.events)
        }

__all__ = [
    "EvolutionSystem",
    "ExperienceSystem",
    "Experience",
    "SkillUsage",
    "HumanFeedback",
    "TaskType",
    "FeedbackType",
    "ExperienceSummary",
    "SkillEvaluator",
    "Skill",
    "SkillMetric",
    "SkillExample",
    "SkillCategory",
    "SkillStatus",
    "PolicyEngine",
    "Policy",
    "PolicyRule",
    "PolicyInsight",
    "PolicyType",
    "PolicyAction",
    "EvolutionLogger",
    "EvolutionEvent",
    "EvolutionPhase",
    "EvolutionEventType",
    "EvolutionImpact",
    "SkillDiscoveryEngine",
    "PatternMatch",
    "DiscoveryResult"
]
