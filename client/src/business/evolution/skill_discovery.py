from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, field
import re
import json
from collections import defaultdict
from .experience_system import ExperienceSystem, TaskType, SkillUsage
from .skill_evaluator import SkillEvaluator, Skill, SkillCategory, SkillStatus, SkillExample

@dataclass
class PatternMatch:
    pattern_id: str
    frequency: int
    avg_success_rate: float
    examples: List[Dict[str, Any]]
    suggested_skill_name: str
    suggested_description: str

@dataclass
class DiscoveryResult:
    discovered_patterns: List[PatternMatch]
    new_skills: List[Skill]
    improved_skills: List[Dict[str, Any]]

class SkillDiscoveryEngine:
    def __init__(self, experience_system: ExperienceSystem, skill_evaluator: SkillEvaluator):
        self.experience_system = experience_system
        self.skill_evaluator = skill_evaluator
    
    def discover_patterns(
        self,
        min_frequency: int = 3,
        min_success_rate: float = 0.7
    ) -> List[PatternMatch]:
        experiences = self.experience_system.get_recent_experiences(100)
        
        pattern_groups = defaultdict(list)
        
        for exp in experiences:
            for skill_usage in exp.skills_used:
                pattern_key = self._extract_pattern_key(exp.task_type, skill_usage)
                pattern_groups[pattern_key].append({
                    "experience": exp,
                    "skill_usage": skill_usage
                })
        
        patterns = []
        for pattern_key, instances in pattern_groups.items():
            if len(instances) < min_frequency:
                continue
            
            success_count = sum(1 for inst in instances if inst["skill_usage"].success)
            success_rate = success_count / len(instances)
            
            if success_rate < min_success_rate:
                continue
            
            examples = []
            for inst in instances[:3]:
                examples.append({
                    "task_description": inst["experience"].task_description,
                    "input_params": inst["skill_usage"].input_params,
                    "output_type": type(inst["skill_usage"].output_result).__name__
                })
            
            task_type, skill_name = pattern_key
            patterns.append(PatternMatch(
                pattern_id=f"pattern_{task_type.value}_{skill_name}",
                frequency=len(instances),
                avg_success_rate=success_rate,
                examples=examples,
                suggested_skill_name=self._generate_skill_name(task_type, skill_name),
                suggested_description=self._generate_description(task_type, skill_name)
            ))
        
        return sorted(patterns, key=lambda x: (-x.frequency, -x.avg_success_rate))
    
    def _extract_pattern_key(self, task_type: TaskType, skill_usage: SkillUsage) -> Tuple[str, str]:
        return (task_type.value, skill_usage.skill_name)
    
    def _generate_skill_name(self, task_type: TaskType, base_name: str) -> str:
        type_prefix = {
            TaskType.CODE_GENERATION: "code_",
            TaskType.DOCUMENT_WRITING: "doc_",
            TaskType.DATA_ANALYSIS: "analyze_",
            TaskType.UI_GENERATION: "ui_"
        }.get(task_type, "")
        return f"{type_prefix}{base_name}"
    
    def _generate_description(self, task_type: TaskType, skill_name: str) -> str:
        type_desc = {
            TaskType.CODE_GENERATION: "代码生成",
            TaskType.DOCUMENT_WRITING: "文档编写",
            TaskType.DATA_ANALYSIS: "数据分析",
            TaskType.UI_GENERATION: "UI生成",
            TaskType.TASK_PLANNING: "任务规划"
        }.get(task_type, "任务处理")
        
        return f"在{type_desc}任务中使用{skill_name}"
    
    def discover_new_skills(self) -> List[Skill]:
        patterns = self.discover_patterns()
        new_skills = []
        
        for pattern in patterns:
            existing_skill = self.skill_evaluator.get_skill(pattern.suggested_skill_name)
            if existing_skill:
                continue
            
            examples = []
            for example in pattern.examples:
                examples.append(SkillExample(
                    input=example["input_params"],
                    output={"type": example["output_type"]},
                    description=example["task_description"][:50] + "..." if len(example["task_description"]) > 50 else example["task_description"]
                ))
            
            category = self._infer_category(pattern.suggested_skill_name)
            
            new_skill = Skill(
                name=pattern.suggested_skill_name,
                description=pattern.suggested_description,
                category=category,
                input_schema=self._infer_input_schema(pattern.examples),
                output_schema={"type": "object"},
                examples=examples,
                status=SkillStatus.EXPERIMENTAL,
                version="1.0.0"
            )
            
            new_skills.append(new_skill)
            self.skill_evaluator.register_skill(new_skill)
        
        return new_skills
    
    def _infer_category(self, skill_name: str) -> SkillCategory:
        if "code" in skill_name.lower():
            return SkillCategory.CODE
        elif "doc" in skill_name.lower() or "document" in skill_name.lower():
            return SkillCategory.DOCUMENT
        elif "analyze" in skill_name.lower() or "data" in skill_name.lower():
            return SkillCategory.ANALYSIS
        elif "ui" in skill_name.lower() or "view" in skill_name.lower():
            return SkillCategory.UI
        else:
            return SkillCategory.OTHER
    
    def _infer_input_schema(self, examples: List[Dict[str, Any]]) -> Dict[str, Any]:
        schema = {"type": "object", "properties": {}}
        
        for example in examples:
            if "input_params" in example:
                for key, value in example["input_params"].items():
                    if key not in schema["properties"]:
                        schema["properties"][key] = {
                            "type": self._get_json_type(value),
                            "examples": []
                        }
                    if value not in schema["properties"][key]["examples"]:
                        schema["properties"][key]["examples"].append(value)
        
        return schema
    
    def _get_json_type(self, value) -> str:
        if isinstance(value, str):
            return "string"
        elif isinstance(value, int):
            return "integer"
        elif isinstance(value, float):
            return "number"
        elif isinstance(value, bool):
            return "boolean"
        elif isinstance(value, list):
            return "array"
        elif isinstance(value, dict):
            return "object"
        else:
            return "string"
    
    def improve_existing_skills(self) -> List[Dict[str, Any]]:
        improvements = []
        
        for skill in self.skill_evaluator.get_all_skills():
            perf = self.skill_evaluator.get_skill_performance(skill.name)
            
            if perf["success_rate"] < 0.6 and perf["usage_count"] >= 5:
                improvements.append({
                    "skill_name": skill.name,
                    "issue": "成功率低",
                    "current_rate": perf["success_rate"],
                    "suggestion": self._generate_improvement_suggestion(skill, perf),
                    "confidence": 0.85
                })
            
            if perf["avg_execution_time"] > 30:
                improvements.append({
                    "skill_name": skill.name,
                    "issue": "执行时间过长",
                    "current_time": perf["avg_execution_time"],
                    "suggestion": "考虑优化算法或引入缓存机制",
                    "confidence": 0.75
                })
        
        return sorted(improvements, key=lambda x: -x["confidence"])
    
    def _generate_improvement_suggestion(self, skill: Skill, performance: Dict[str, Any]) -> str:
        if skill.status == SkillStatus.EXPERIMENTAL:
            return "该技能仍在实验阶段，建议收集更多数据"
        
        if performance["avg_user_rating"] < 3:
            return "用户评价较低，建议改进输出质量"
        
        return "分析失败案例，优化输入参数验证和错误处理"
    
    def analyze_skill_gaps(self) -> List[Dict[str, Any]]:
        experiences = self.experience_system.get_recent_experiences(50)
        
        failed_experiences = [e for e in experiences if not e.success]
        
        gaps = []
        for exp in failed_experiences:
            if not exp.skills_used:
                gaps.append({
                    "task_type": exp.task_type.value,
                    "task_description": exp.task_description,
                    "gap_type": "missing_skill",
                    "suggestion": f"为{exp.task_type.value}任务添加合适的技能"
                })
            else:
                for su in exp.skills_used:
                    if not su.success:
                        gaps.append({
                            "task_type": exp.task_type.value,
                            "task_description": exp.task_description,
                            "gap_type": "skill_failure",
                            "failed_skill": su.skill_name,
                            "suggestion": f"改进或替换{su.skill_name}技能"
                        })
        
        return gaps[:10]
    
    def run_full_discovery(self) -> DiscoveryResult:
        self.discover_patterns()
        new_skills = self.discover_new_skills()
        improvements = self.improve_existing_skills()
        patterns = self.discover_patterns()
        
        return DiscoveryResult(
            discovered_patterns=patterns,
            new_skills=new_skills,
            improved_skills=improvements
        )
    
    def suggest_skill_combination(self, task_description: str) -> List[Dict[str, Any]]:
        skills = self.skill_evaluator.get_all_skills()
        active_skills = [s for s in skills if s.status == SkillStatus.ACTIVE]
        
        suggestions = []
        for skill in active_skills:
            relevance = self._calculate_relevance(skill, task_description)
            if relevance > 0.3:
                perf = self.skill_evaluator.get_skill_performance(skill.name)
                suggestions.append({
                    "skill_name": skill.name,
                    "description": skill.description,
                    "relevance": relevance,
                    "success_rate": perf["success_rate"],
                    "usage_count": perf["usage_count"],
                    "avg_time": perf["avg_execution_time"]
                })
        
        return sorted(suggestions, key=lambda x: (-x["relevance"], -x["success_rate"]))[:5]
    
    def _calculate_relevance(self, skill: Skill, task_description: str) -> float:
        score = 0.0
        task_words = set(task_description.lower().split())
        
        skill_words = set(skill.description.lower().split())
        overlap = task_words.intersection(skill_words)
        score += len(overlap) / max(len(skill_words), 1)
        
        for example in skill.examples:
            example_words = set(example.description.lower().split())
            example_overlap = task_words.intersection(example_words)
            score += (len(example_overlap) / max(len(example_words), 1)) * 0.3
        
        return min(score, 1.0)
