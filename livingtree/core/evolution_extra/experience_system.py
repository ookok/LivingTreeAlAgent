from typing import List, Optional, Dict, Any
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import json
import os

class TaskType(Enum):
    CODE_GENERATION = "code_generation"
    DOCUMENT_WRITING = "document_writing"
    DATA_ANALYSIS = "data_analysis"
    TASK_PLANNING = "task_planning"
    UI_GENERATION = "ui_generation"
    OTHER = "other"

class FeedbackType(Enum):
    THUMBS_UP = "thumbs_up"
    THUMBS_DOWN = "thumbs_down"
    DETAILED = "detailed"

@dataclass
class SkillUsage:
    skill_name: str
    input_params: Dict[str, Any]
    output_result: Any
    execution_time: float
    success: bool

@dataclass
class HumanFeedback:
    feedback_type: FeedbackType
    rating: Optional[int] = None
    comments: Optional[str] = None
    suggested_improvements: Optional[List[str]] = None
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class Experience:
    experience_id: str
    task_type: TaskType
    task_description: str
    skills_used: List[SkillUsage]
    success: bool
    execution_time: float
    human_feedback: Optional[HumanFeedback] = None
    improvements: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ExperienceSummary:
    task_type: TaskType
    total_count: int
    success_rate: float
    avg_execution_time: float
    top_skills: List[str]
    common_improvements: List[str]

class ExperienceSystem:
    def __init__(self, storage_path: str = "./data/experiences"):
        self.storage_path = storage_path
        self.experiences: List[Experience] = []
        os.makedirs(storage_path, exist_ok=True)
        self._load_experiences()
    
    def _load_experiences(self):
        for filename in os.listdir(self.storage_path):
            if filename.endswith(".json"):
                filepath = os.path.join(self.storage_path, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        experience = self._from_dict(data)
                        self.experiences.append(experience)
                except Exception as e:
                    print(f"Error loading experience {filename}: {e}")
    
    def _save_experience(self, experience: Experience):
        filepath = os.path.join(self.storage_path, f"{experience.experience_id}.json")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self._to_dict(experience), f, indent=2, default=str)
    
    def _to_dict(self, experience: Experience) -> Dict[str, Any]:
        return {
            "experience_id": experience.experience_id,
            "task_type": experience.task_type.value,
            "task_description": experience.task_description,
            "skills_used": [
                {
                    "skill_name": su.skill_name,
                    "input_params": su.input_params,
                    "output_result": su.output_result,
                    "execution_time": su.execution_time,
                    "success": su.success
                } for su in experience.skills_used
            ],
            "success": experience.success,
            "execution_time": experience.execution_time,
            "human_feedback": {
                "feedback_type": experience.human_feedback.feedback_type.value,
                "rating": experience.human_feedback.rating,
                "comments": experience.human_feedback.comments,
                "suggested_improvements": experience.human_feedback.suggested_improvements,
                "timestamp": experience.human_feedback.timestamp.isoformat()
            } if experience.human_feedback else None,
            "improvements": experience.improvements,
            "timestamp": experience.timestamp.isoformat(),
            "metadata": experience.metadata
        }
    
    def _from_dict(self, data: Dict[str, Any]) -> Experience:
        return Experience(
            experience_id=data["experience_id"],
            task_type=TaskType(data["task_type"]),
            task_description=data["task_description"],
            skills_used=[
                SkillUsage(
                    skill_name=su["skill_name"],
                    input_params=su["input_params"],
                    output_result=su["output_result"],
                    execution_time=su["execution_time"],
                    success=su["success"]
                ) for su in data["skills_used"]
            ],
            success=data["success"],
            execution_time=data["execution_time"],
            human_feedback=HumanFeedback(
                feedback_type=FeedbackType(data["human_feedback"]["feedback_type"]),
                rating=data["human_feedback"]["rating"],
                comments=data["human_feedback"]["comments"],
                suggested_improvements=data["human_feedback"]["suggested_improvements"],
                timestamp=datetime.fromisoformat(data["human_feedback"]["timestamp"])
            ) if data["human_feedback"] else None,
            improvements=data.get("improvements", []),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            metadata=data.get("metadata", {})
        )
    
    def record_experience(
        self,
        task_type: TaskType,
        task_description: str,
        skills_used: List[SkillUsage],
        success: bool,
        execution_time: float,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        experience_id = f"exp_{int(datetime.now().timestamp())}"
        experience = Experience(
            experience_id=experience_id,
            task_type=task_type,
            task_description=task_description,
            skills_used=skills_used,
            success=success,
            execution_time=execution_time,
            metadata=metadata or {}
        )
        self.experiences.append(experience)
        self._save_experience(experience)
        return experience_id
    
    def add_feedback(self, experience_id: str, feedback: HumanFeedback):
        for experience in self.experiences:
            if experience.experience_id == experience_id:
                experience.human_feedback = feedback
                self._save_experience(experience)
                break
    
    def add_improvements(self, experience_id: str, improvements: List[str]):
        for experience in self.experiences:
            if experience.experience_id == experience_id:
                experience.improvements.extend(improvements)
                self._save_experience(experience)
                break
    
    def get_experiences_by_type(self, task_type: TaskType) -> List[Experience]:
        return [e for e in self.experiences if e.task_type == task_type]
    
    def get_recent_experiences(self, limit: int = 10) -> List[Experience]:
        return sorted(self.experiences, key=lambda x: x.timestamp, reverse=True)[:limit]
    
    def get_summary(self, task_type: Optional[TaskType] = None) -> ExperienceSummary:
        if task_type:
            filtered = self.get_experiences_by_type(task_type)
        else:
            filtered = self.experiences
        
        if not filtered:
            return ExperienceSummary(
                task_type=task_type or TaskType.OTHER,
                total_count=0,
                success_rate=0.0,
                avg_execution_time=0.0,
                top_skills=[],
                common_improvements=[]
            )
        
        total = len(filtered)
        success_count = sum(1 for e in filtered if e.success)
        avg_time = sum(e.execution_time for e in filtered) / total
        
        skill_usage = {}
        for e in filtered:
            for su in e.skills_used:
                skill_usage[su.skill_name] = skill_usage.get(su.skill_name, 0) + 1
        
        top_skills = [s for s, _ in sorted(skill_usage.items(), key=lambda x: -x[1])][:5]
        
        improvement_counts = {}
        for e in filtered:
            for imp in e.improvements:
                improvement_counts[imp] = improvement_counts.get(imp, 0) + 1
        
        common_improvements = [i for i, _ in sorted(improvement_counts.items(), key=lambda x: -x[1])][:5]
        
        return ExperienceSummary(
            task_type=task_type or TaskType.OTHER,
            total_count=total,
            success_rate=success_count / total,
            avg_execution_time=avg_time,
            top_skills=top_skills,
            common_improvements=common_improvements
        )
    
    def get_skill_performance(self, skill_name: str) -> Dict[str, float]:
        usages = []
        for experience in self.experiences:
            for su in experience.skills_used:
                if su.skill_name == skill_name:
                    usages.append(su)
        
        if not usages:
            return {"usage_count": 0, "success_rate": 0.0, "avg_execution_time": 0.0}
        
        success_count = sum(1 for u in usages if u.success)
        avg_time = sum(u.execution_time for u in usages) / len(usages)
        
        return {
            "usage_count": len(usages),
            "success_rate": success_count / len(usages),
            "avg_execution_time": avg_time
        }
    
    def get_human_feedback_summary(self) -> Dict[str, Any]:
        feedbacks = [e.human_feedback for e in self.experiences if e.human_feedback]
        
        if not feedbacks:
            return {"total_feedbacks": 0, "positive_ratio": 0.0, "average_rating": 0.0}
        
        positive_count = sum(1 for f in feedbacks if f.feedback_type == FeedbackType.THUMBS_UP)
        ratings = [f.rating for f in feedbacks if f.rating is not None]
        
        return {
            "total_feedbacks": len(feedbacks),
            "positive_ratio": positive_count / len(feedbacks),
            "average_rating": sum(ratings) / len(ratings) if ratings else 0.0
        }
