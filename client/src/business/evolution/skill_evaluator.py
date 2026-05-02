from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import json
import os

class SkillCategory(Enum):
    CODE = "code"
    DOCUMENT = "document"
    ANALYSIS = "analysis"
    TOOL = "tool"
    UI = "ui"
    OTHER = "other"

class SkillStatus(Enum):
    ACTIVE = "active"
    DISABLED = "disabled"
    EXPERIMENTAL = "experimental"

@dataclass
class SkillExample:
    input: Dict[str, Any]
    output: Any
    description: str

@dataclass
class SkillMetric:
    usage_count: int = 0
    success_count: int = 0
    avg_execution_time: float = 0.0
    total_execution_time: float = 0.0
    user_ratings: List[int] = field(default_factory=list)
    last_used: Optional[datetime] = None
    first_used: Optional[datetime] = None

@dataclass
class Skill:
    name: str
    description: str
    category: SkillCategory
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    examples: List[SkillExample] = field(default_factory=list)
    status: SkillStatus = SkillStatus.ACTIVE
    metrics: SkillMetric = field(default_factory=SkillMetric)
    source_type: str = "internal"
    source_path: Optional[str] = None
    version: str = "1.0.0"
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

class SkillEvaluator:
    def __init__(self, storage_path: str = "./data/skills"):
        self.storage_path = storage_path
        self.skills: Dict[str, Skill] = {}
        os.makedirs(storage_path, exist_ok=True)
        self._load_skills()
    
    def _load_skills(self):
        for filename in os.listdir(self.storage_path):
            if filename.endswith(".json"):
                filepath = os.path.join(self.storage_path, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        skill = self._from_dict(data)
                        self.skills[skill.name] = skill
                except Exception as e:
                    print(f"Error loading skill {filename}: {e}")
    
    def _save_skill(self, skill: Skill):
        filepath = os.path.join(self.storage_path, f"{skill.name}.json")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self._to_dict(skill), f, indent=2, default=str)
    
    def _to_dict(self, skill: Skill) -> Dict[str, Any]:
        return {
            "name": skill.name,
            "description": skill.description,
            "category": skill.category.value,
            "input_schema": skill.input_schema,
            "output_schema": skill.output_schema,
            "examples": [
                {
                    "input": ex.input,
                    "output": ex.output,
                    "description": ex.description
                } for ex in skill.examples
            ],
            "status": skill.status.value,
            "metrics": {
                "usage_count": skill.metrics.usage_count,
                "success_count": skill.metrics.success_count,
                "avg_execution_time": skill.metrics.avg_execution_time,
                "total_execution_time": skill.metrics.total_execution_time,
                "user_ratings": skill.metrics.user_ratings,
                "last_used": skill.metrics.last_used.isoformat() if skill.metrics.last_used else None,
                "first_used": skill.metrics.first_used.isoformat() if skill.metrics.first_used else None
            },
            "source_type": skill.source_type,
            "source_path": skill.source_path,
            "version": skill.version,
            "created_at": skill.created_at.isoformat(),
            "updated_at": skill.updated_at.isoformat()
        }
    
    def _from_dict(self, data: Dict[str, Any]) -> Skill:
        return Skill(
            name=data["name"],
            description=data["description"],
            category=SkillCategory(data["category"]),
            input_schema=data["input_schema"],
            output_schema=data["output_schema"],
            examples=[
                SkillExample(
                    input=ex["input"],
                    output=ex["output"],
                    description=ex["description"]
                ) for ex in data.get("examples", [])
            ],
            status=SkillStatus(data["status"]),
            metrics=SkillMetric(
                usage_count=data["metrics"]["usage_count"],
                success_count=data["metrics"]["success_count"],
                avg_execution_time=data["metrics"]["avg_execution_time"],
                total_execution_time=data["metrics"]["total_execution_time"],
                user_ratings=data["metrics"]["user_ratings"],
                last_used=datetime.fromisoformat(data["metrics"]["last_used"]) if data["metrics"]["last_used"] else None,
                first_used=datetime.fromisoformat(data["metrics"]["first_used"]) if data["metrics"]["first_used"] else None
            ),
            source_type=data.get("source_type", "internal"),
            source_path=data.get("source_path"),
            version=data.get("version", "1.0.0"),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"])
        )
    
    def register_skill(self, skill: Skill):
        self.skills[skill.name] = skill
        self._save_skill(skill)
    
    def unregister_skill(self, skill_name: str):
        if skill_name in self.skills:
            del self.skills[skill_name]
            filepath = os.path.join(self.storage_path, f"{skill_name}.json")
            if os.path.exists(filepath):
                os.remove(filepath)
    
    def record_usage(self, skill_name: str, success: bool, execution_time: float):
        if skill_name not in self.skills:
            return
        
        skill = self.skills[skill_name]
        skill.metrics.usage_count += 1
        if success:
            skill.metrics.success_count += 1
        skill.metrics.total_execution_time += execution_time
        skill.metrics.avg_execution_time = skill.metrics.total_execution_time / skill.metrics.usage_count
        skill.metrics.last_used = datetime.now()
        if not skill.metrics.first_used:
            skill.metrics.first_used = datetime.now()
        skill.updated_at = datetime.now()
        self._save_skill(skill)
    
    def record_user_rating(self, skill_name: str, rating: int):
        if skill_name not in self.skills:
            return
        
        skill = self.skills[skill_name]
        if 1 <= rating <= 5:
            skill.metrics.user_ratings.append(rating)
            skill.updated_at = datetime.now()
            self._save_skill(skill)
    
    def get_skill(self, skill_name: str) -> Optional[Skill]:
        return self.skills.get(skill_name)
    
    def get_all_skills(self) -> List[Skill]:
        return list(self.skills.values())
    
    def get_skills_by_category(self, category: SkillCategory) -> List[Skill]:
        return [s for s in self.skills.values() if s.category == category]
    
    def get_top_performing_skills(self, limit: int = 5) -> List[Skill]:
        active_skills = [s for s in self.skills.values() if s.status == SkillStatus.ACTIVE and s.metrics.usage_count > 0]
        return sorted(active_skills, key=lambda s: (s.metrics.success_count / s.metrics.usage_count, -s.metrics.usage_count), reverse=True)[:limit]
    
    def get_low_performing_skills(self, threshold: float = 0.5) -> List[Skill]:
        return [
            s for s in self.skills.values()
            if s.status == SkillStatus.ACTIVE and s.metrics.usage_count >= 5
            and (s.metrics.success_count / s.metrics.usage_count) < threshold
        ]
    
    def get_skill_performance(self, skill_name: str) -> Dict[str, Any]:
        skill = self.skills.get(skill_name)
        if not skill:
            return {
                "found": False,
                "name": skill_name,
                "success_rate": 0.0,
                "avg_execution_time": 0.0,
                "usage_count": 0,
                "avg_user_rating": 0.0
            }
        
        metrics = skill.metrics
        success_rate = metrics.success_count / metrics.usage_count if metrics.usage_count > 0 else 0.0
        avg_user_rating = sum(metrics.user_ratings) / len(metrics.user_ratings) if metrics.user_ratings else 0.0
        
        return {
            "found": True,
            "name": skill.name,
            "description": skill.description,
            "category": skill.category.value,
            "success_rate": success_rate,
            "avg_execution_time": metrics.avg_execution_time,
            "usage_count": metrics.usage_count,
            "avg_user_rating": avg_user_rating,
            "last_used": metrics.last_used.isoformat() if metrics.last_used else None,
            "status": skill.status.value
        }
    
    def suggest_skills(self, task_description: str) -> List[Dict[str, Any]]:
        active_skills = [s for s in self.skills.values() if s.status == SkillStatus.ACTIVE]
        
        suggestions = []
        for skill in active_skills:
            relevance = self._calculate_relevance(skill, task_description)
            if relevance > 0.3:
                perf = self.get_skill_performance(skill.name)
                suggestions.append({
                    "name": skill.name,
                    "description": skill.description,
                    "category": skill.category.value,
                    "relevance": relevance,
                    "success_rate": perf["success_rate"],
                    "usage_count": perf["usage_count"]
                })
        
        return sorted(suggestions, key=lambda x: (x["relevance"], x["success_rate"]), reverse=True)[:5]
    
    def _calculate_relevance(self, skill: Skill, task_description: str) -> float:
        score = 0.0
        description_words = set(task_description.lower().split())
        
        skill_words = set(skill.description.lower().split())
        overlap = description_words.intersection(skill_words)
        score += len(overlap) / max(len(skill_words), 1)
        
        for example in skill.examples:
            example_words = set(example.description.lower().split())
            example_overlap = description_words.intersection(example_words)
            score += (len(example_overlap) / max(len(example_words), 1)) * 0.2
        
        return min(score, 1.0)
    
    def update_skill(self, skill_name: str, updates: Dict[str, Any]):
        if skill_name not in self.skills:
            return
        
        skill = self.skills[skill_name]
        if "description" in updates:
            skill.description = updates["description"]
        if "category" in updates:
            skill.category = SkillCategory(updates["category"])
        if "status" in updates:
            skill.status = SkillStatus(updates["status"])
        if "input_schema" in updates:
            skill.input_schema = updates["input_schema"]
        if "output_schema" in updates:
            skill.output_schema = updates["output_schema"]
        if "version" in updates:
            skill.version = updates["version"]
        
        skill.updated_at = datetime.now()
        self._save_skill(skill)
